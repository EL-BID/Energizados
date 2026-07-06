"""
JobStore: SQLite-backed job persistence.

Implements schema initialization and CRUD operations for job lifecycle management.
Following web-job-runner spec: single source of truth for job state.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection, Row, connect
from typing import Any, Dict, List, Optional

from energizados.web.models import JobRow, JobStatus

logger = logging.getLogger(__name__)


class JobStore:
    """
    SQLite-backed job persistence store.

    Implements schema initialization and CRUD operations for job lifecycle.
    Thread-safe for web+worker concurrent access (WAL mode).
    """

    def __init__(self, db_path: str = "data/web/jobs.db"):
        """
        Initialize JobStore with SQLite database.

        Args:
            db_path: Path to SQLite database file (created if missing)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_connection(self) -> Connection:
        """
        Get SQLite connection with WAL mode for concurrent access.

        Returns:
            Connection with row factory enabled
        """
        conn = connect(str(self.db_path))
        conn.row_factory = Row
        # Enable WAL mode for concurrent reads (web) + single writer (worker)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self):
        """Create database schema if missing (idempotent)."""
        with self._get_connection() as conn:
            # Create jobs table (single source of truth)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    config_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    run_id TEXT,
                    run_dir TEXT,
                    error TEXT,
                    retried_from TEXT,
                    FOREIGN KEY (retried_from) REFERENCES jobs(job_id)
                )
                """)

            # Create job_events table (reserved for Phase 5 SSE; NOT populated in Phase 1)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    percent INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
                """)

            # Create indexes for FIFO ordering and queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_enqueued ON jobs(status, enqueued_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_events_job_seq ON job_events(job_id, seq)"
            )

            conn.commit()
            logger.info(f"Schema initialized: {self.db_path}")

    def create_job(self, config: Dict[str, Any], config_type: str) -> str:
        """
        Create a new queued job.

        Args:
            config: Merged configuration dict (will be JSON-serialized)
            config_type: Config type ("etl" | "train" | "eda" | "infer")

        Returns:
            job_id: UUID-based job identifier
        """
        job_id = f"job-{uuid.uuid4()}"
        enqueued_at = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, config, config_type, status, enqueued_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, json.dumps(config), config_type, JobStatus.QUEUED.value, enqueued_at),
            )
            conn.commit()
            logger.info(f"Job created: {job_id} ({config_type})")

        return job_id

    def get_job(self, job_id: str) -> Optional[JobRow]:
        """
        Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            JobRow or None if not found
        """
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()

        if row is None:
            return None

        return JobRow.from_row(row)

    def list_jobs(
        self, status_filter: Optional[JobStatus] = None, limit: int = 100
    ) -> List[JobRow]:
        """
        List jobs with optional status filter (FIFO ordered).

        Args:
            status_filter: Optional JobStatus filter
            limit: Maximum jobs to return (default 100)

        Returns:
            List of JobRow ordered by enqueued_at DESC
        """
        with self._get_connection() as conn:
            if status_filter:
                rows = conn.execute(
                    """
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY enqueued_at DESC
                    LIMIT ?
                    """,
                    (status_filter.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM jobs
                    ORDER BY enqueued_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [JobRow.from_row(row) for row in rows]

    def update_status(
        self,
        job_id: str,
        new_status: JobStatus,
        run_id: Optional[str] = None,
        run_dir: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update job status with legal transition validation.

        Args:
            job_id: Job identifier
            new_status: New status (must pass can_transition_to check)
            run_id: Optional run ID (when starting/finishing job)
            run_dir: Optional run directory path
            error: Optional error dict (for failed/aborted)

        Returns:
            True if updated, False if transition illegal or job not found
        """
        job = self.get_job(job_id)
        if job is None:
            return False

        # Validate legal transition
        if not job.can_transition_to(new_status):
            logger.warning(f"Illegal transition: {job.status} → {new_status} for {job_id}")
            return False

        # Build update fields
        updates = ["status = ?", "finished_at = ?"]
        values = [new_status.value]

        # Set finished_at for terminal states
        if new_status.is_terminal:
            values.append(datetime.now(timezone.utc).isoformat())
        else:
            values.append(None)  # Clear finished_at if not terminal

        # Set started_at for queued→running
        if new_status == JobStatus.RUNNING:
            updates.append("started_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())
        elif "started_at" not in updates:
            # Keep existing started_at if already set
            updates.append("started_at = COALESCE(started_at, NULL)")

        # Set run_id and run_dir if provided
        if run_id is not None:
            updates.append("run_id = ?")
            values.append(run_id)

        if run_dir is not None:
            updates.append("run_dir = ?")
            values.append(run_dir)

        # Set error if provided (for failed/aborted)
        if error is not None:
            updates.append("error = ?")
            values.append(json.dumps(error))

        values.append(job_id)  # WHERE clause

        # Column names come from the internal `updates` whitelist built above,
        # never from user input; all values are parameterized.
        query = f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?"  # nosec B608
        with self._get_connection() as conn:
            conn.execute(query, values)
            conn.commit()
            logger.info(f"Job {job_id}: {job.status} → {new_status}")

        return True

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job (marks aborted, no-op otherwise).

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if not running or not found
        """
        job = self.get_job(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return False

        return self.update_status(
            job_id,
            JobStatus.ABORTED,
            error={"error_code": "CANCELLED", "message": "Job cancelled by user"},
        )

    def retry_job(self, job_id: str) -> Optional[str]:
        """
        Retry a failed/aborted/successful job (creates new job_id, leaves original).

        Only terminal jobs may be retried. Retrying a queued or running job is
        rejected to avoid creating duplicate work.

        Args:
            job_id: Original job identifier

        Returns:
            New job_id, or None if original not found or not terminal
        """
        job = self.get_job(job_id)
        if job is None:
            return None

        if not job.is_terminal():
            logger.warning(f"Cannot retry job {job_id}: not terminal (status={job.status.value})")
            return None

        new_job_id = self.create_job(job.config, job.config_type)

        # Link to original job
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET retried_from = ? WHERE job_id = ?", (job_id, new_job_id))
            conn.commit()
            logger.info(f"Job {new_job_id} retries {job_id}")

        return new_job_id

    def purge_old_jobs(self, cutoff_days: int = 30) -> int:
        """
        Delete terminal jobs older than cutoff (idempotent).

        Args:
            cutoff_days: Delete terminal jobs finished more than this many days ago

        Returns:
            Number of jobs deleted
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_days_ago = cutoff - timedelta(days=cutoff_days)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM jobs
                WHERE status IN ('success', 'failed', 'aborted')
                AND finished_at < ?
                """,
                (cutoff_days_ago.isoformat(),),
            )
            deleted_count = cursor.rowcount
            conn.commit()
            logger.info(f"Purged {deleted_count} old jobs (older than {cutoff_days} days)")

        return deleted_count

    def reconcile_running_jobs(self) -> int:
        """
        Atomically set all running jobs to failed (startup reconciliation).

        Called on worker startup to handle orphaned jobs from previous crashes.

        Returns:
            Number of jobs reconciled
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    finished_at = ?,
                    error = ?
                WHERE status = 'running'
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(
                        {
                            "error_code": "WORKER_RESTARTED",
                            "message": "Worker restarted during execution",
                        }
                    ),
                ),
            )
            reconciled_count = cursor.rowcount
            conn.commit()
            logger.info(f"Reconciled {reconciled_count} running jobs (marked failed)")

        return reconciled_count

    def get_next_queued_job(self) -> Optional[JobRow]:
        """
        Get the next queued job (FIFO ordering for worker poll loop).

        Returns:
            Next JobRow or None if queue empty
        """
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM jobs
                WHERE status = 'queued'
                ORDER BY enqueued_at ASC
                LIMIT 1
                """).fetchone()

        if row is None:
            return None

        return JobRow.from_row(row)
