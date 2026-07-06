"""
Energizados Web Console - Cross-platform launcher.

Spawns both the uvicorn web server and the worker process as subprocesses,
handling graceful shutdown on Ctrl-C and SIGTERM. Works on both Windows and Linux.

Usage:
    energizados-web [--host] [--port] [--db-path] [--log-level]
    python -m energizados.web.launcher [--host] [--port] [--db-path] [--log-level]
"""

import argparse
import logging
import signal

# subprocess is used for legitimate local process orchestration (spawn uvicorn + worker).
import subprocess  # nosec B404
import sys
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Process handles for web and worker
_web_process: subprocess.Popen = None
_worker_process: subprocess.Popen = None


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Energizados Web Console - Launch web server and worker"
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind web server (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for web server (default: 8000)",
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default="data/web/jobs.db",
        help="Path to SQLite database (default: data/web/jobs.db)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def _web_argv(host: str, port: int) -> List[str]:
    """Build argv list for uvicorn web server process."""
    return [
        sys.executable,
        "-m",
        "uvicorn",
        "energizados.web.app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]


def _worker_argv(db_path: str, log_level: str) -> List[str]:
    """Build argv list for worker process."""
    return [
        sys.executable,
        "-m",
        "energizados.web.worker",
        "--db-path",
        db_path,
        "--log-level",
        log_level,
    ]


def _prefix_output(process: subprocess.Popen, prefix: str):
    """Stream process output with prefix for log identification."""
    for line in iter(process.stdout.readline, b""):
        if line:
            print(f"[{prefix}] {line.decode('utf-8')}", end="")


def _shutdown(signum=None, frame=None):
    """Gracefully shutdown web and worker processes."""
    logger.info("Shutting down Energizados Web Console...")

    processes = []
    if _web_process:
        processes.append(("web", _web_process))
    if _worker_process:
        processes.append(("worker", _worker_process))

    # Terminate all processes
    for name, process in processes:
        if process.poll() is None:  # Process is still running
            logger.info(f"Stopping {name} process...")
            process.terminate()

    # Wait for graceful shutdown (5 second timeout)
    import time

    timeout = 5
    start = time.time()

    for name, process in processes:
        remaining = timeout - (time.time() - start)
        if remaining > 0:
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning(f"{name} process did not shut down gracefully, forcing...")
                process.kill()

    logger.info("Energizados Web Console stopped")
    sys.exit(0)


def _setup_signal_handlers():
    """Setup signal handlers for graceful shutdown (cross-platform)."""
    # SIGINT (Ctrl-C) works on both Windows and Linux
    signal.signal(signal.SIGINT, _shutdown)

    # SIGTERM is POSIX-only (Linux), guard for Windows compatibility
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)


def main():
    """Main entry point for the launcher."""
    global _web_process, _worker_process

    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("Energizados Web Console starting")
    logger.info(f"Web server: http://{args.host}:{args.port}")
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Log level: {args.log_level}")

    # Setup signal handlers
    _setup_signal_handlers()

    try:
        # Start web server
        web_cmd = _web_argv(args.host, args.port)
        logger.info(f"Starting web server: {' '.join(web_cmd)}")
        # web_cmd is a fixed arg list (sys.executable -m uvicorn ...); no shell, no untrusted input.
        _web_process = subprocess.Popen(
            web_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )  # nosec B603

        # Start worker
        worker_cmd = _worker_argv(args.db_path, args.log_level)
        logger.info(f"Starting worker: {' '.join(worker_cmd)}")
        # worker_cmd is a fixed arg list (sys.executable -m energizados.web.worker); no shell.
        _worker_process = subprocess.Popen(
            worker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )  # nosec B603

        # Stream output from both processes with prefixes
        logger.info("Processes started. Press Ctrl-C to stop.")

        import threading

        web_thread = threading.Thread(
            target=_prefix_output, args=(_web_process, "web"), daemon=True
        )
        worker_thread = threading.Thread(
            target=_prefix_output, args=(_worker_process, "worker"), daemon=True
        )

        web_thread.start()
        worker_thread.start()

        # Wait for either process to exit
        while True:
            # Check if either process has exited
            web_poll = _web_process.poll()
            worker_poll = _worker_process.poll()

            if web_poll is not None:
                logger.error(f"Web server exited with code {web_poll}")
                break
            if worker_poll is not None:
                logger.error(f"Worker exited with code {worker_poll}")
                break

            # Small sleep to prevent busy-waiting
            import time

            time.sleep(0.1)

        # If we reach here, one process has exited - shutdown the other
        _shutdown()

    except KeyboardInterrupt:
        # Already handled by signal handler, but as fallback
        _shutdown()
    except Exception as e:
        logger.error(f"Launcher error: {e}")
        _shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
