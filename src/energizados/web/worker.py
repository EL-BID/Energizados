"""
Worker entrypoint for async job execution.

This module provides the CLI and main entry point for the Energizados web worker process.
Can be run via: python -m energizados.web.worker or energizados-web-worker console script.
"""

import argparse
import logging
import sys

from energizados.web.runner import JobRunner
from energizados.web.store import JobStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Energizados Web Job Worker")

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


def main():
    """Main entry point for worker process."""
    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("Energizados Web Worker starting")
    logger.info(f"Database path: {args.db_path}")

    # Initialize JobStore and JobRunner
    try:
        store = JobStore(db_path=args.db_path)
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
