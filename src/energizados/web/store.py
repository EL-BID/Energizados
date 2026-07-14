"""
JobStore: SQLite-backed job persistence.

Implements schema initialization and CRUD operations for job lifecycle management.
Following web-job-runner spec: single source of truth for job state.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Connection, IntegrityError, Row, connect
from typing import Any, Dict, List, Optional

from energizados.web.models import JobRow, JobStatus

logger = logging.getLogger(__name__)


class JobStore:
    """
    SQLite-backed job persistence store.

    Implements schema initialization and CRUD operations for job lifecycle.
    Thread-safe for web+worker concurrent access (WAL mode).
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize JobStore with SQLite database.

        Resolution order for ``db_path``:

        1. Explicit argument (wins if provided).
        2. ``ENERGIZADOS_JOBS_DB`` environment variable (set by the worker so
           spawned child processes inherit the absolute DB path, which matters
           because children ``os.chdir`` into a project directory before running).
        3. Default ``data/web/jobs.db``.

        Args:
            db_path: Path to SQLite database file (created if missing)
        """
        resolved = db_path or os.environ.get("ENERGIZADOS_JOBS_DB") or "data/web/jobs.db"
        self.db_path = Path(resolved)
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
                    project_path TEXT,
                    FOREIGN KEY (retried_from) REFERENCES jobs(job_id)
                )
                """)

            # Migrate jobs: add project_path column for existing DBs (Phase 1
            # multi-project). Idempotent: only ALTERs if the column is missing.
            jobs_columns = conn.execute("PRAGMA table_info(jobs)").fetchall()
            jobs_col_names = {c[1] for c in jobs_columns}
            if "project_path" not in jobs_col_names:
                logger.info("Migrating jobs: adding project_path TEXT column")
                conn.execute("ALTER TABLE jobs ADD COLUMN project_path TEXT")

            # Migrate jobs: add derived_from_run_id column for existing DBs
            # (Phase 3, ADR-0003 — Run→Run retrain lineage). Idempotent: only
            # ALTERs if the column is missing. Mirrors run_id storage: the value
            # lives in BOTH the jobs row (transport + queryable) and the run's
            # run_metadata.json["derived_from"] (portable Run property). Points to
            # a run_id, distinct from retried_from (which points to a job_id).
            if "derived_from_run_id" not in jobs_col_names:
                logger.info("Migrating jobs: adding derived_from_run_id TEXT column")
                conn.execute("ALTER TABLE jobs ADD COLUMN derived_from_run_id TEXT")

            # Migrate job_events: drop if percent is INTEGER (old schema from Phase 1)
            # Check if job_events table exists and has INTEGER percent column
            existing_tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='job_events'"
            ).fetchall()

            if existing_tables:
                existing_columns = conn.execute("PRAGMA table_info(job_events)").fetchall()
                percent_col = [c for c in existing_columns if c[1] == "percent"]

                # If percent column exists and is INTEGER, drop table for migration
                if percent_col and len(percent_col) > 0 and percent_col[0][2] == "INTEGER":
                    row_count = conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0]
                    if row_count == 0:
                        logger.info(
                            "Migrating job_events.percent: INTEGER → REAL (dropping empty table)"
                        )
                        conn.execute("DROP TABLE job_events")
                    else:
                        logger.warning(
                            f"job_events.percent is INTEGER but table has {row_count} rows; "
                            "skipping migration to avoid data loss"
                        )

            # Create job_events table with corrected schema (percent as REAL nullable)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    percent REAL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(job_id, seq),
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
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_path)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_derived_from ON jobs(derived_from_run_id)"
            )

            conn.commit()
            logger.info(f"Schema initialized: {self.db_path}")

    def create_job(
        self,
        config: Dict[str, Any],
        config_type: str,
        project_path: Optional[str] = None,
        derived_from_run_id: Optional[str] = None,
    ) -> str:
        """
        Create a new queued job.

        Args:
            config: Merged configuration dict (will be JSON-serialized)
            config_type: Config type ("etl" | "train" | "eda" | "infer")
            project_path: Optional absolute path to the owning project. When
                ``None`` the job belongs to the Global view.
            derived_from_run_id: Optional ADR-0003 source run_id for retrain
                lineage (Run→Run). Points to a run_id, NOT a job_id — distinct
                from ``retried_from``. The worker threads this to
                ``ConfigPipelineBuilder(derived_from=...)`` so it lands in
                ``run_metadata.json["derived_from"]`` at finalization. Retry does
                NOT set this (retry is Job→Job via ``retried_from``).

        Returns:
            job_id: UUID-based job identifier
        """
        job_id = f"job-{uuid.uuid4()}"
        enqueued_at = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs
                    (job_id, config, config_type, status, enqueued_at, project_path,
                     derived_from_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    json.dumps(config),
                    config_type,
                    JobStatus.QUEUED.value,
                    enqueued_at,
                    project_path,
                    derived_from_run_id,
                ),
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
        self,
        status_filter: Optional[JobStatus] = None,
        limit: int = 100,
        project_path: Optional[str] = None,
    ) -> List[JobRow]:
        """
        List jobs with optional status and project filters (FIFO ordered).

        Args:
            status_filter: Optional JobStatus filter
            limit: Maximum jobs to return (default 100)
            project_path: Optional absolute project path to filter by. When
                ``None`` (the default) NO project filter is applied and all
                jobs are returned (the legacy Global view). When a concrete
                path string is given, only jobs whose ``project_path`` matches
                exactly are returned.

        Returns:
            List of JobRow ordered by enqueued_at DESC
        """
        clauses: List[str] = []
        params: List[Any] = []

        if status_filter:
            clauses.append("status = ?")
            params.append(status_filter.value)

        # project_path None -> no project filter (Global view = all jobs).
        # A non-None string -> exact match on that project.
        if project_path is not None:
            clauses.append("project_path = ?")
            params.append(project_path)

        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM jobs
                WHERE {where}
                ORDER BY enqueued_at DESC
                LIMIT ?
                """,  # nosec B608 — clauses are static literals, params parameterized
                tuple(params),
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

        new_job_id = self.create_job(job.config, job.config_type, project_path=job.project_path)

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

    def append_job_event(self, job_id: str, event) -> bool:
        """
        Append a progress event to job_events table.

        Args:
            job_id: Job identifier
            event: ProgressEvent from pipeline execution

        Returns:
            True if written, False on error (logged, never raises)

        Note:
            Must NOT raise — called from worker child process callback.
            Errors are logged and swallowed to avoid crashing the job.
        """
        for attempt in range(20):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT COALESCE(MAX(seq), 0) FROM job_events WHERE job_id = ?", (job_id,)
                    )
                    next_seq = cursor.fetchone()[0] + 1
                    conn.execute(
                        "INSERT INTO job_events (job_id, seq, phase, step_name, message, percent, timestamp) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            job_id,
                            next_seq,
                            event.phase,
                            event.step_name,
                            event.message,
                            event.percent,
                            event.timestamp.isoformat(),
                        ),
                    )
                    conn.commit()
                    logger.debug(f"[{job_id}] Event {next_seq}: {event.step_name} - {event.phase}")
                    return True
            except IntegrityError:
                # concurrent writer inserted this seq first; recompute and retry
                continue
            except Exception as e:
                logger.error(f"Failed to write job event for {job_id}: {e}")
                return False
        logger.error(f"Failed to write job event for {job_id}: seq contention after 20 attempts")
        return False

    def get_job_events_since(self, job_id: str, after_seq: int = 0) -> List[Dict[str, Any]]:
        """
        Get job events since a sequence number (for SSE tailing).

        Args:
            job_id: Job identifier
            after_seq: Minimum seq to fetch (exclusive; 0 = fetch all)

        Returns:
            List of event dicts ordered by seq ASC
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT seq, phase, step_name, message, percent, timestamp
                FROM job_events
                WHERE job_id = ? AND seq > ?
                ORDER BY seq ASC
            """,
                (job_id, after_seq),
            ).fetchall()

        return [dict(row) for row in rows]
