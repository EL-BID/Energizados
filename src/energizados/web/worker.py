"""
Worker entrypoint for async job execution.

This module provides the CLI and main entry point for the Energizados web worker process.
Can be run via: python -m energizados.web.worker or energizados-web-worker console script.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from energizados.web.runner import JobRunner
from energizados.web.store import JobStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/web/jobs.db"
DEFAULT_WORKSPACE_ROOT = "data/web/workspace"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Energizados Web Job Worker")

    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
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
            f"(default: {DEFAULT_WORKSPACE_ROOT}, or $ENERGIZADOS_WORKSPACE_ROOT)"
        ),
    )

    return parser.parse_args()


def setup_worker(db_path: str, workspace_root: Optional[str] = None) -> Tuple[Path, Optional[Path]]:
    """
    Resolve the worker's db_path and workspace root and export them to env.

    The absolute db_path is exported via ``ENERGIZADOS_JOBS_DB`` so that spawned
    child processes (which ``os.chdir`` into a project directory before running)
    keep writing to the same SQLite file. The workspace root is exported via
    ``ENERGIZADOS_WORKSPACE_ROOT`` and also returned for the worker's own use.

    Workspace root resolution order: explicit arg →
    ``ENERGIZADOS_WORKSPACE_ROOT`` env → ``data/web/workspace`` default.

    Args:
        db_path: Database path from the CLI (absolute or relative).
        workspace_root: Optional workspace root from the CLI.

    Returns:
        ``(abs_db_path, workspace_root_path_or_None)``.
    """
    abs_db = Path(db_path).resolve()
    os.environ["ENERGIZADOS_JOBS_DB"] = str(abs_db)

    resolved_ws: Optional[Path]
    if workspace_root is not None:
        resolved_ws = Path(workspace_root).resolve()
    elif os.environ.get("ENERGIZADOS_WORKSPACE_ROOT"):
        resolved_ws = Path(os.environ["ENERGIZADOS_WORKSPACE_ROOT"]).resolve()
    else:
        resolved_ws = Path(DEFAULT_WORKSPACE_ROOT).resolve()

    return abs_db, resolved_ws


def main():
    """Main entry point for worker process."""
    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("Energizados Web Worker starting")

    # Resolve db_path to absolute and export to env so child processes (which
    # chdir into a project dir) inherit the correct DB path.
    abs_db, workspace_root = setup_worker(db_path=args.db_path, workspace_root=args.workspace_root)
    logger.info(f"Database path: {abs_db}")
    logger.info(f"Workspace root: {workspace_root}")

    # Initialize JobStore and JobRunner
    try:
        store = JobStore(db_path=str(abs_db))
        runner = JobRunner(store=store)

        # Start main execution loop
        runner.run()

    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
