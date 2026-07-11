"""
Data models for web job runner.

Defines JobStatus enum and JobRow dataclass for SQLite persistence.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class JobStatus(str, Enum):
    """Job lifecycle states with terminal state detection."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions)."""
        return self in {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.ABORTED}

    @property
    def can_run(self) -> bool:
        """Check if job can transition to RUNNING."""
        return self == JobStatus.QUEUED

    @property
    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return self == JobStatus.RUNNING


@dataclass
class JobRow:
    """Database row representation for a job."""

    job_id: str
    config: Dict[str, Any]  # Parsed JSON config
    config_type: str  # "etl" | "train" | "eda" | "infer"
    status: JobStatus
    enqueued_at: str  # ISO timestamp
    started_at: Optional[str] = None  # ISO timestamp
    finished_at: Optional[str] = None  # ISO timestamp
    run_id: Optional[str] = None  # RunMetadata.run_id
    run_dir: Optional[str] = None  # Path to output/<run_id>
    error: Optional[Dict[str, Any]] = None  # Parsed from format_error
    retried_from: Optional[str] = None  # Parent job_id
    project_path: Optional[str] = None  # Absolute path to the owning project (Global = None)

    @classmethod
    def from_row(cls, row: Any) -> "JobRow":
        """
        Create JobRow from SQLite row.

        Args:
            row: sqlite3.Row object or dict-like with column values

        Returns:
            JobRow instance
        """
        # Parse config JSON if stored as string
        config_value = row["config"]
        if isinstance(config_value, str):
            config = json.loads(config_value)
        else:
            config = config_value

        # Parse error JSON if stored as string
        error_value = row["error"] if "error" in row.keys() else None
        error = (
            json.loads(error_value) if isinstance(error_value, str) and error_value else error_value
        )

        return cls(
            job_id=row["job_id"],
            config=config,
            config_type=row["config_type"],
            status=JobStatus(row["status"]),
            enqueued_at=row["enqueued_at"],
            started_at=row["started_at"] if "started_at" in row.keys() else None,
            finished_at=row["finished_at"] if "finished_at" in row.keys() else None,
            run_id=row["run_id"] if "run_id" in row.keys() else None,
            run_dir=row["run_dir"] if "run_dir" in row.keys() else None,
            error=error,
            retried_from=row["retried_from"] if "retried_from" in row.keys() else None,
            project_path=row["project_path"] if "project_path" in row.keys() else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "job_id": self.job_id,
            "config": self.config,
            "config_type": self.config_type,
            "status": self.status.value,
            "enqueued_at": self.enqueued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "error": self.error,
            "retried_from": self.retried_from,
            "project_path": self.project_path,
        }

    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status.is_terminal

    def can_transition_to(self, new_status: JobStatus) -> bool:
        """
        Check if status transition is legal.

        Legal transitions:
        - queued → running
        - running → success|failed|aborted
        """
        if self.status == JobStatus.QUEUED and new_status == JobStatus.RUNNING:
            return True
        if self.status == JobStatus.RUNNING and new_status.is_terminal:
            return True
        return False
