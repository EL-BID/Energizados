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

    parser.add_argument(
        "--workspace-root",
        type=str,
        default=None,
        help=(
            "Root directory under which new projects are created "
            "(default: data/web/workspace, or $ENERGIZADOS_WORKSPACE_ROOT)"
        ),
    )

    parser.add_argument(
        "--allow-remote",
        action="store_true",
        default=False,
        help=(
            "Opt-in to bind the web console to a non-loopback interface "
            "(--host != 127.0.0.1). Required to start when --host is set to "
            "anything other than 127.0.0.1/localhost. The console has no auth "
            "and accepts arbitrary YAML as job configuration, so this is a "
            "code-execution surface — see docs/web-console/DEPLOYMENT.md."
        ),
    )

    return parser.parse_args()


# Hosts that are considered safe to bind without --allow-remote. Anything else
# (0.0.0.0, an IP on the LAN, a public hostname, etc.) requires explicit opt-in.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _assert_safe_host_or_explicit_opt_in(host: str, allow_remote: bool) -> None:
    """Refuse to start if the host is non-loopback and --allow-remote is unset.

    The web console has no authentication layer and accepts arbitrary YAML as
    job configuration in a context where the worker calls
    ``register_allowed_prefix("src")`` and ``os.chdir(job_dir)``. Binding to
    anything other than loopback exposes a code-execution surface. The default
    bind is 127.0.0.1 (loopback) which contains the blast radius; this guard
    makes the foot-gun explicit when a user asks for a wider bind.

    Args:
        host: Parsed ``--host`` value.
        allow_remote: Parsed ``--allow-remote`` flag.

    Raises:
        SystemExit(2): if ``host`` is non-loopback and ``allow_remote`` is False.
    """
    if allow_remote or host in _LOOPBACK_HOSTS:
        return

    # LOUD stderr warning, fail-closed.
    sys.stderr.write(
        "\n"
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        "!!                                                                    !!\n"
        f"!!  SECURITY: refusing to bind to non-localhost host '{host}'.       !!\n"
        "!!                                                                    !!\n"
        "!!  The Energizados web console has NO authentication and accepts     !!\n"
        "!!  arbitrary YAML as job configuration. Binding to a non-loopback    !!\n"
        "!!  interface exposes a code-execution surface: anyone who can reach  !!\n"
        "!!  this port can submit a job that imports arbitrary Python modules  !!\n"
        "!!  under src/. The default bind (127.0.0.1) contains the blast       !!\n"
        "!!  radius; binding wider requires explicit opt-in.                   !!\n"
        "!!                                                                    !!\n"
        "!!  To override (you have been warned), pass --allow-remote and see   !!\n"
        "!!  docs/web-console/DEPLOYMENT.md for the threat model.              !!\n"
        "!!                                                                    !!\n"
        "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        "\n"
    )
    sys.exit(2)


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


def _worker_argv(db_path: str, log_level: str, workspace_root: str = None) -> List[str]:
    """Build argv list for worker process."""
    argv = [
        sys.executable,
        "-m",
        "energizados.web.worker",
        "--db-path",
        db_path,
        "--log-level",
        log_level,
    ]
    if workspace_root:
        argv.extend(["--workspace-root", workspace_root])
    return argv


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

    # Fail-closed: refuse to bind to a non-loopback interface without explicit
    # opt-in via --allow-remote. See _assert_safe_host_or_explicit_opt_in()
    # for the full rationale and threat model.
    _assert_safe_host_or_explicit_opt_in(args.host, args.allow_remote)

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Resolve workspace root and export to env so both the web (uvicorn) and
    # worker subprocesses share the same ProjectService workspace root.
    import os
    from pathlib import Path

    if args.workspace_root:
        workspace_root = str(Path(args.workspace_root).resolve())
        os.environ["ENERGIZADOS_WORKSPACE_ROOT"] = workspace_root
    else:
        workspace_root = os.environ.get("ENERGIZADOS_WORKSPACE_ROOT", "data/web/workspace")

    logger.info("Energizados Web Console starting")
    logger.info(f"Web server: http://{args.host}:{args.port}")
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Workspace root: {workspace_root}")
    logger.info(f"Log level: {args.log_level}")

    # Setup signal handlers
    _setup_signal_handlers()

    try:
        # Cross-platform detach flags. On Windows, create a new process group
        # so children survive parent console events and don't flash a console
        # window. On POSIX, start_new_session is the modern equivalent.
        popen_kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_kwargs["start_new_session"] = True

        # Start web server
        web_cmd = _web_argv(args.host, args.port)
        logger.info(f"Starting web server: {' '.join(web_cmd)}")
        # web_cmd is a fixed arg list (sys.executable -m uvicorn ...); no shell, no untrusted input.
        _web_process = subprocess.Popen(web_cmd, **popen_kwargs)  # nosec B603

        # Start worker
        worker_cmd = _worker_argv(args.db_path, args.log_level)
        logger.info(f"Starting worker: {' '.join(worker_cmd)}")
        # worker_cmd is a fixed arg list; no shell, no untrusted input.
        _worker_process = subprocess.Popen(worker_cmd, **popen_kwargs)  # nosec B603

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
