"""
Tests for web job runner models (JobStatus, JobRow).

Following strict TDD: tests written first (RED), then implementation (GREEN).
"""

import json

from energizados.web.models import JobRow, JobStatus


class TestJobStatus:
    """Test JobStatus enum properties and methods."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.ABORTED.value == "aborted"

    def test_is_terminal_property(self):
        """Test is_terminal property identifies terminal states correctly."""
        assert JobStatus.SUCCESS.is_terminal is True
        assert JobStatus.FAILED.is_terminal is True
        assert JobStatus.ABORTED.is_terminal is True
        assert JobStatus.QUEUED.is_terminal is False
        assert JobStatus.RUNNING.is_terminal is False

    def test_can_run_property(self):
        """Test can_run property allows QUEUED to run only."""
        assert JobStatus.QUEUED.can_run is True
        assert JobStatus.RUNNING.can_run is False
        assert JobStatus.SUCCESS.can_run is False
        assert JobStatus.FAILED.can_run is False
        assert JobStatus.ABORTED.can_run is False

    def test_can_cancel_property(self):
        """Test can_cancel property allows RUNNING cancellation only."""
        assert JobStatus.RUNNING.can_cancel is True
        assert JobStatus.QUEUED.can_cancel is False
        assert JobStatus.SUCCESS.can_cancel is False
        assert JobStatus.FAILED.can_cancel is False
        assert JobStatus.ABORTED.can_cancel is False


class TestJobRow:
    """Test JobRow dataclass."""

    def test_job_row_creation(self):
        """Test JobRow creation with all fields."""
        job = JobRow(
            job_id="job-123",
            config={"train": {"enabled": True}},
            config_type="train",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
            started_at="2024-01-01T12:05:00",
            finished_at="2024-01-01T12:30:00",
            run_id="train-20240101_120500",
            run_dir="output/train-20240101_120500",
            error=None,
            retried_from=None,
        )

        assert job.job_id == "job-123"
        assert job.config == {"train": {"enabled": True}}
        assert job.config_type == "train"
        assert job.status == JobStatus.QUEUED
        assert job.enqueued_at == "2024-01-01T12:00:00"
        assert job.started_at == "2024-01-01T12:05:00"
        assert job.finished_at == "2024-01-01T12:30:00"
        assert job.run_id == "train-20240101_120500"
        assert job.run_dir == "output/train-20240101_120500"
        assert job.error is None
        assert job.retried_from is None

    def test_job_row_minimal(self):
        """Test JobRow creation with minimal required fields."""
        job = JobRow(
            job_id="job-123",
            config={"etl": {"enabled": True}},
            config_type="etl",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
        )

        assert job.job_id == "job-123"
        assert job.started_at is None
        assert job.finished_at is None
        assert job.run_id is None
        assert job.run_dir is None
        assert job.error is None
        assert job.retried_from is None

    def test_from_row_with_dict(self):
        """Test from_row factory with dict-like object (RED phase)."""
        row_data = {
            "job_id": "job-456",
            "config": '{"train": {"enabled": true}}',
            "config_type": "train",
            "status": "running",
            "enqueued_at": "2024-01-01T12:00:00",
            "started_at": "2024-01-01T12:05:00",
            "finished_at": None,
            "run_id": None,
            "run_dir": None,
            "error": None,
            "retried_from": None,
        }

        job = JobRow.from_row(row_data)

        assert job.job_id == "job-456"
        assert job.config == {"train": {"enabled": True}}  # JSON parsed
        assert job.config_type == "train"
        assert job.status == JobStatus.RUNNING
        assert job.enqueued_at == "2024-01-01T12:00:00"
        assert job.started_at == "2024-01-01T12:05:00"

    def test_from_row_with_error_json(self):
        """Test from_row with error field as JSON string (RED phase)."""
        row_data = {
            "job_id": "job-789",
            "config": '{"train": {"enabled": true}}',
            "config_type": "train",
            "status": "failed",
            "enqueued_at": "2024-01-01T12:00:00",
            "started_at": "2024-01-01T12:05:00",
            "finished_at": "2024-01-01T12:15:00",
            "run_id": None,
            "run_dir": None,
            "error": '{"error_code": "CONFIG_ERROR", "message": "Invalid config"}',
            "retried_from": None,
        }

        job = JobRow.from_row(row_data)

        assert job.status == JobStatus.FAILED
        assert job.error == {"error_code": "CONFIG_ERROR", "message": "Invalid config"}

    def test_to_dict(self):
        """Test to_dict returns JSON-serializable dict."""
        job = JobRow(
            job_id="job-123",
            config={"train": {"enabled": True}},
            config_type="train",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
            error={"error_code": "TEST_ERROR"},
        )

        result = job.to_dict()

        assert result["job_id"] == "job-123"
        assert result["config"] == {"train": {"enabled": True}}
        assert result["config_type"] == "train"
        assert result["status"] == "queued"  # Enum value
        assert result["enqueued_at"] == "2024-01-01T12:00:00"
        assert result["error"] == {"error_code": "TEST_ERROR"}
        assert "started_at" not in result or result["started_at"] is None

        # Verify JSON serializable
        json.dumps(result)

    def test_is_terminal(self):
        """Test is_terminal method delegates to status."""
        queued_job = JobRow(
            job_id="job-1",
            config={},
            config_type="train",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
        )
        running_job = JobRow(
            job_id="job-2",
            config={},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T12:00:00",
        )
        success_job = JobRow(
            job_id="job-3",
            config={},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T12:00:00",
        )

        assert queued_job.is_terminal() is False
        assert running_job.is_terminal() is False
        assert success_job.is_terminal() is True

    def test_can_transition_to(self):
        """Test legal status transitions."""
        queued_job = JobRow(
            job_id="job-1",
            config={},
            config_type="train",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
        )
        running_job = JobRow(
            job_id="job-2",
            config={},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T12:00:00",
        )
        success_job = JobRow(
            job_id="job-3",
            config={},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T12:00:00",
        )

        # Legal: queued → running
        assert queued_job.can_transition_to(JobStatus.RUNNING) is True
        assert queued_job.can_transition_to(JobStatus.SUCCESS) is False

        # Legal: running → terminal
        assert running_job.can_transition_to(JobStatus.SUCCESS) is True
        assert running_job.can_transition_to(JobStatus.FAILED) is True
        assert running_job.can_transition_to(JobStatus.ABORTED) is True
        assert running_job.can_transition_to(JobStatus.RUNNING) is False

        # Illegal: terminal → anything
        assert success_job.can_transition_to(JobStatus.RUNNING) is False
        assert success_job.can_transition_to(JobStatus.FAILED) is False


class TestJobRowProjectPath:
    """Test project_path field parsing (Phase 1 multi-project)."""

    def test_from_row_with_project_path(self):
        """from_row parses project_path when the column is present."""
        row_data = {
            "job_id": "job-1",
            "config": '{"train": {"enabled": true}}',
            "config_type": "train",
            "status": "queued",
            "enqueued_at": "2024-01-01T12:00:00",
            "started_at": None,
            "finished_at": None,
            "run_id": None,
            "run_dir": None,
            "error": None,
            "retried_from": None,
            "project_path": "/data/workspace/myproj",
        }

        job = JobRow.from_row(row_data)

        assert job.project_path == "/data/workspace/myproj"

    def test_from_row_without_project_path_column(self):
        """from_row does not crash on rows lacking project_path (legacy DBs)."""
        row_data = {
            "job_id": "job-2",
            "config": '{"train": {"enabled": true}}',
            "config_type": "train",
            "status": "queued",
            "enqueued_at": "2024-01-01T12:00:00",
            "started_at": None,
            "finished_at": None,
            "run_id": None,
            "run_dir": None,
            "error": None,
            "retried_from": None,
            # project_path intentionally absent
        }

        job = JobRow.from_row(row_data)

        assert job.project_path is None

    def test_to_dict_includes_project_path(self):
        """to_dict serializes project_path."""
        job = JobRow(
            job_id="job-3",
            config={},
            config_type="train",
            status=JobStatus.QUEUED,
            enqueued_at="2024-01-01T12:00:00",
            project_path="/data/workspace/proj",
        )

        result = job.to_dict()

        assert result["project_path"] == "/data/workspace/proj"
        json.dumps(result)  # JSON serializable
