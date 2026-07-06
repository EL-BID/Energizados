"""
Tests for JobStore SQLite persistence.

Following strict TDD: tests written first (RED), then implementation (GREEN).
Uses in-memory SQLite for isolation.
"""

from energizados.web.models import JobStatus
from energizados.web.store import JobStore


class TestJobStoreSchema:
    """Test database schema initialization."""

    def test_schema_initialized_on_creation(self, tmp_path):
        """Test that schema is created when JobStore is instantiated."""
        db_path = tmp_path / "test.db"
        store = JobStore(db_path=str(db_path))

        # Verify database file exists
        assert db_path.exists()

        # Verify tables exist (query sqlite_master)
        with store._get_connection() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t["name"] for t in tables]

        assert "jobs" in table_names
        assert "job_events" in table_names

    def test_schema_idempotent(self, tmp_path):
        """Test that schema creation is idempotent (can run multiple times)."""
        db_path = tmp_path / "test.db"

        # Create first store
        JobStore(db_path=str(db_path))

        # Create second store (should not fail)
        store = JobStore(db_path=str(db_path))

        # Schema should still be valid
        with store._get_connection() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t["name"] for t in tables]

        assert "jobs" in table_names
        assert "job_events" in table_names


class TestJobStoreCRUD:
    """Test JobStore CRUD operations."""

    def test_create_job_returns_job_id(self, tmp_path):
        """Test create_job returns a UUID-based job_id."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        config = {
            "train": {"enabled": True, "input_path": "data/test.parquet", "target_column": "target"}
        }
        job_id = store.create_job(config, "train")

        assert job_id is not None
        assert job_id.startswith("job-")
        assert len(job_id) > 36  # "job-" + UUID (UUIDs vary in format)

    def test_create_job_persists_to_database(self, tmp_path):
        """Test created job is persisted in SQLite."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        config = {"etl": {"sample": {"enabled": True}}}
        job_id = store.create_job(config, "etl")

        job = store.get_job(job_id)

        assert job is not None
        assert job.job_id == job_id
        assert job.config == config
        assert job.config_type == "etl"
        assert job.status == JobStatus.QUEUED
        assert job.enqueued_at is not None
        assert job.started_at is None
        assert job.finished_at is None

    def test_get_job_not_found(self, tmp_path):
        """Test get_job returns None for non-existent job."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job = store.get_job("nonexistent-job-id")

        assert job is None

    def test_list_jobs_empty(self, tmp_path):
        """Test list_jobs returns empty list when no jobs exist."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        jobs = store.list_jobs()

        assert jobs == []

    def test_list_jobs_returns_all_jobs(self, tmp_path):
        """Test list_jobs returns all jobs ordered by enqueued_at DESC."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create multiple jobs
        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")
        job3_id = store.create_job({"eda": {}}, "eda")

        jobs = store.list_jobs()

        assert len(jobs) == 3
        # Most recently enqueued first
        assert jobs[0].job_id == job3_id
        assert jobs[1].job_id == job2_id
        assert jobs[2].job_id == job1_id

    def test_list_jobs_with_status_filter(self, tmp_path):
        """Test list_jobs filters by status."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")

        # Mark one as running
        store.update_status(job1_id, JobStatus.RUNNING)

        # Filter for queued jobs
        queued_jobs = store.list_jobs(status_filter=JobStatus.QUEUED)

        assert len(queued_jobs) == 1
        assert queued_jobs[0].job_id == job2_id

    def test_list_jobs_respects_limit(self, tmp_path):
        """Test list_jobs respects limit parameter."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create 5 jobs
        for i in range(5):
            store.create_job({"train": {}}, "train")

        jobs = store.list_jobs(limit=3)

        assert len(jobs) == 3


class TestJobStoreStatusTransitions:
    """Test job status transitions with validation."""

    def test_update_status_queued_to_running(self, tmp_path):
        """Test legal transition: queued → running."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")
        success = store.update_status(
            job_id, JobStatus.RUNNING, run_id="train-123", run_dir="output/train-123"
        )

        assert success is True

        job = store.get_job(job_id)
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.run_id == "train-123"
        assert job.run_dir == "output/train-123"

    def test_update_status_running_to_success(self, tmp_path):
        """Test legal transition: running → success."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING, run_id="train-123")
        success = store.update_status(job_id, JobStatus.SUCCESS)

        assert success is True

        job = store.get_job(job_id)
        assert job.status == JobStatus.SUCCESS
        assert job.finished_at is not None

    def test_update_status_running_to_failed_with_error(self, tmp_path):
        """Test legal transition: running → failed with error."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        error = {"error_code": "CONFIG_ERROR", "message": "Invalid config"}
        success = store.update_status(job_id, JobStatus.FAILED, error=error)

        assert success is True

        job = store.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.finished_at is not None
        assert job.error == error

    def test_update_status_running_to_aborted(self, tmp_path):
        """Test legal transition: running → aborted."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        success = store.update_status(job_id, JobStatus.ABORTED)

        assert success is True

        job = store.get_job(job_id)
        assert job.status == JobStatus.ABORTED
        assert job.finished_at is not None

    def test_update_status_illegal_transition_rejected(self, tmp_path):
        """Test illegal transitions are rejected."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")

        # Illegal: queued → success (must go through running)
        success = store.update_status(job_id, JobStatus.SUCCESS)
        assert success is False

        # Illegal: success → running (terminal state)
        store.update_status(job_id, JobStatus.RUNNING)
        store.update_status(job_id, JobStatus.SUCCESS)
        success = store.update_status(job_id, JobStatus.RUNNING)
        assert success is False


class TestJobStoreCancelRetry:
    """Test cancel and retry operations."""

    def test_cancel_job_running_to_aborted(self, tmp_path):
        """Test cancel marks running job as aborted."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        success = store.cancel_job(job_id)

        assert success is True

        job = store.get_job(job_id)
        assert job.status == JobStatus.ABORTED
        assert job.error is not None
        assert job.error["error_code"] == "CANCELLED"

    def test_cancel_job_queued_no_op(self, tmp_path):
        """Test cancel on queued job is no-op."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")

        success = store.cancel_job(job_id)

        assert success is False

        job = store.get_job(job_id)
        assert job.status == JobStatus.QUEUED  # Unchanged

    def test_cancel_job_nonexistent(self, tmp_path):
        """Test cancel on non-existent job returns False."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        success = store.cancel_job("nonexistent-job-id")

        assert success is False

    def test_retry_job_creates_new_job_id(self, tmp_path):
        """Test retry creates new job with retried_from link."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        original_job_id = store.create_job({"train": {}}, "train")
        store.update_status(original_job_id, JobStatus.RUNNING)
        store.update_status(
            original_job_id, JobStatus.FAILED, error={"error_code": "TRAINING_ERROR"}
        )

        new_job_id = store.retry_job(original_job_id)

        assert new_job_id is not None
        assert new_job_id != original_job_id

        # Verify new job
        new_job = store.get_job(new_job_id)
        assert new_job.status == JobStatus.QUEUED
        assert new_job.config == {"train": {}}
        assert new_job.retried_from == original_job_id

        # Verify original job unchanged
        original_job = store.get_job(original_job_id)
        assert original_job.status == JobStatus.FAILED
        assert original_job.error is not None

    def test_retry_job_nonexistent(self, tmp_path):
        """Test retry on non-existent job returns None."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        new_job_id = store.retry_job("nonexistent-job-id")

        assert new_job_id is None

    def test_retry_job_queued_rejected(self, tmp_path):
        """Retry of a still-queued job must be rejected (no duplicates)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        queued_job_id = store.create_job({"train": {}}, "train")

        new_job_id = store.retry_job(queued_job_id)

        assert new_job_id is None
        # No duplicate job created
        assert len(store.list_jobs()) == 1

    def test_retry_job_running_rejected(self, tmp_path):
        """Retry of a running job must be rejected (no duplicates)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        running_job_id = store.create_job({"train": {}}, "train")
        store.update_status(running_job_id, JobStatus.RUNNING)

        new_job_id = store.retry_job(running_job_id)

        assert new_job_id is None
        assert len(store.list_jobs()) == 1


class TestJobStorePurgeReconcile:
    """Test purge and reconciliation operations."""

    def test_purge_old_jobs_basic(self, tmp_path):
        """Test purge deletes terminal jobs (basic functionality)."""

        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create a terminal job
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)
        store.update_status(job_id, JobStatus.SUCCESS)

        # Manually update the finished_at to be old
        with store._get_connection() as conn:
            old_time = "2020-01-01T00:00:00+00:00"
            conn.execute("UPDATE jobs SET finished_at = ? WHERE job_id = ?", (old_time, job_id))
            conn.commit()

        # Purge jobs older than 30 days (using current date)
        deleted_count = store.purge_old_jobs(cutoff_days=30)

        assert deleted_count >= 1  # Should delete at least our old job

        # Old job should be deleted
        assert store.get_job(job_id) is None

    def test_purge_idempotent(self, tmp_path):
        """Test purge is idempotent (can run multiple times safely)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create and finish a job (with legal transitions)
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)
        store.update_status(job_id, JobStatus.SUCCESS)

        # Manually set finished_at to be very old (100 days ago)
        with store._get_connection() as conn:
            # Get current date and subtract 100 days
            from datetime import datetime, timedelta, timezone

            old_time = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
            conn.execute("UPDATE jobs SET finished_at = ? WHERE job_id = ?", (old_time, job_id))
            conn.commit()

        # First purge with 30-day cutoff
        deleted_count1 = store.purge_old_jobs(cutoff_days=30)
        # Second purge (no more jobs to delete)
        deleted_count2 = store.purge_old_jobs(cutoff_days=30)

        assert deleted_count1 == 1
        assert deleted_count2 == 0

    def test_reconcile_running_jobs_on_startup(self, tmp_path):
        """Test startup reconciliation marks running jobs as failed."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create a running job (simulating worker crash)
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        # Reconcile (simulates worker startup)
        reconciled_count = store.reconcile_running_jobs()

        assert reconciled_count == 1

        job = store.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert job.error["error_code"] == "WORKER_RESTARTED"

    def test_reconcile_idempotent(self, tmp_path):
        """Test reconcile is idempotent (can run multiple times safely)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create a running job
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        # First reconcile
        reconciled_count1 = store.reconcile_running_jobs()
        # Second reconcile (no more running jobs)
        reconciled_count2 = store.reconcile_running_jobs()

        assert reconciled_count1 == 1
        assert reconciled_count2 == 0


class TestJobStoreFIFO:
    """Test FIFO queue ordering for worker."""

    def test_get_next_queued_job_fifo_order(self, tmp_path):
        """Test get_next_queued_job returns jobs in FIFO order."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        # Create jobs in sequence
        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")
        job3_id = store.create_job({"eda": {}}, "eda")

        # Get next job (should be first created)
        next_job = store.get_next_queued_job()

        assert next_job is not None
        assert next_job.job_id == job1_id

        # After marking as running, next job should be job2
        store.update_status(job1_id, JobStatus.RUNNING)
        next_job = store.get_next_queued_job()

        assert next_job.job_id == job2_id

        # After marking job2 as running, next job should be job3
        store.update_status(job2_id, JobStatus.RUNNING)
        next_job = store.get_next_queued_job()

        assert next_job.job_id == job3_id

    def test_get_next_queued_job_empty_queue(self, tmp_path):
        """Test get_next_queued_job returns None when queue is empty."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        next_job = store.get_next_queued_job()

        assert next_job is None

    def test_get_next_queued_job_ignores_running_jobs(self, tmp_path):
        """Test get_next_queued_job ignores running jobs."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")

        # Mark job1 as running
        store.update_status(job1_id, JobStatus.RUNNING)

        # Next queued job should be job2
        next_job = store.get_next_queued_job()

        assert next_job.job_id == job2_id
