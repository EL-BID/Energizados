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


class TestJobStoreSchemaMigration:
    """Test job_events.percent column migration INTEGER → REAL."""

    def test_percent_column_is_real_nullable(self, tmp_path):
        """Schema migration creates percent as REAL nullable."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(job_events)").fetchall()
            percent_col = [c for c in columns if c["name"] == "percent"]

        assert len(percent_col) == 1
        assert percent_col[0]["type"] == "REAL"
        assert percent_col[0]["notnull"] == 0  # Nullable

    def test_migration_idempotent(self, tmp_path):
        """Migration can run multiple times safely."""
        db_path = tmp_path / "test.db"

        # Create first store (triggers migration)
        JobStore(db_path=str(db_path))

        # Create second store (should not fail)
        store = JobStore(db_path=str(db_path))

        # Verify schema still valid
        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(job_events)").fetchall()
            percent_col = [c for c in columns if c["name"] == "percent"]

        assert len(percent_col) == 1
        assert percent_col[0]["type"] == "REAL"


class TestJobStoreAppendEvent:
    """Test append_job_event persistence with monotonic seq."""

    def test_append_event_assigns_monotonic_seq(self, tmp_path):
        """Seq increments monotonically per job (1, 2, 3...)."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event1 = ProgressEvent(
            run_id="unknown",
            step_name="etl",
            phase="start",
            message="Starting ETL",
            percent=0.0,
            timestamp=datetime.now(timezone.utc),
        )

        event2 = ProgressEvent(
            run_id="unknown",
            step_name="etl",
            phase="complete",
            message="ETL complete",
            percent=100.0,
            timestamp=datetime.now(timezone.utc),
        )

        success1 = store.append_job_event(job_id, event1)
        success2 = store.append_job_event(job_id, event2)

        assert success1 is True
        assert success2 is True

        events = store.get_job_events_since(job_id, after_seq=0)
        assert events[0]["seq"] == 1
        assert events[1]["seq"] == 2

    def test_append_event_maps_progressevent_fields(self, tmp_path):
        """All ProgressEvent fields map to job_events columns."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="run-123",
            step_name="training",
            phase="start",
            message="Starting training",
            percent=50.5,  # Float value
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

        store.append_job_event(job_id, event)

        rows = store.get_job_events_since(job_id, after_seq=0)
        assert len(rows) == 1
        assert rows[0]["step_name"] == "training"
        assert rows[0]["phase"] == "start"
        assert rows[0]["message"] == "Starting training"
        assert rows[0]["percent"] == 50.5
        assert rows[0]["timestamp"] == "2024-01-01T12:00:00+00:00"

    def test_append_event_isolated_per_job(self, tmp_path):
        """Seq monotonicity isolated per job (not global)."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")

        event1 = ProgressEvent(
            run_id="unknown",
            step_name="step1",
            phase="start",
            message="Job1 step1",
            percent=0.0,
            timestamp=datetime.now(timezone.utc),
        )
        event2 = ProgressEvent(
            run_id="unknown",
            step_name="step2",
            phase="start",
            message="Job2 step2",
            percent=0.0,
            timestamp=datetime.now(timezone.utc),
        )

        store.append_job_event(job1_id, event1)
        store.append_job_event(job2_id, event2)

        # Each job has seq=1 (not global seq=1, seq=2)
        job1_events = store.get_job_events_since(job1_id, after_seq=0)
        job2_events = store.get_job_events_since(job2_id, after_seq=0)

        assert job1_events[0]["seq"] == 1
        assert job2_events[0]["seq"] == 1

    def test_append_event_handles_write_failure(self, tmp_path):
        """Write failure returns False, logs error, never raises."""
        from datetime import datetime, timezone
        from unittest.mock import patch

        from energizados.api.progress import ProgressEvent

        # Mock store with broken connection
        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="unknown",
            step_name="test",
            phase="start",
            message="Test event",
            percent=0.0,
            timestamp=datetime.now(timezone.utc),
        )

        # Mock _get_connection to raise exception
        with patch.object(store, "_get_connection", side_effect=Exception("DB error")):
            result = store.append_job_event(job_id, event)

        assert result is False  # Returns False, doesn't raise

    def test_append_job_event_concurrent_writers_unique_seq(self, tmp_path):
        """Concurrent writers to same job generate unique monotonic seqs."""
        import threading
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        num_threads = 10
        events_per_thread = 10
        errors = []

        def append_events(thread_id):
            """Append events from one thread (simulates concurrent worker callbacks)."""
            for i in range(events_per_thread):
                event = ProgressEvent(
                    run_id="unknown",
                    step_name=f"thread{thread_id}_step{i}",
                    phase="running",
                    message=f"Thread {thread_id} event {i}",
                    percent=float(i * 10),
                    timestamp=datetime.now(timezone.utc),
                )
                if not store.append_job_event(job_id, event):
                    errors.append(f"Thread {thread_id} failed to write event {i}")

        threads = []
        for t in range(num_threads):
            thread = threading.Thread(target=append_events, args=(t,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # No write failures
        assert not errors, f"Write errors occurred: {errors}"

        # All events persisted with unique seqs
        events = store.get_job_events_since(job_id, after_seq=0)
        expected_count = num_threads * events_per_thread
        assert len(events) == expected_count, f"Expected {expected_count} events, got {len(events)}"

        # Extract seqs and verify they are exactly 1..100 (no gaps, no duplicates)
        seqs = {event["seq"] for event in events}
        expected_seqs = set(range(1, expected_count + 1))
        assert seqs == expected_seqs, f"Seqs are {sorted(seqs)}, expected {sorted(expected_seqs)}"


class TestJobStoreGetEventsSince:
    """Test get_job_events_since query and ordering."""

    def test_get_events_filters_by_seq(self, tmp_path):
        """Returns only events with seq > after_seq."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Append 5 events
        for i in range(5):
            event = ProgressEvent(
                run_id="unknown",
                step_name=f"step{i}",
                phase="start",
                message=f"Step {i}",
                percent=0.0,
                timestamp=datetime.now(timezone.utc),
            )
            store.append_job_event(job_id, event)

        # Fetch after seq=3
        events = store.get_job_events_since(job_id, after_seq=3)

        assert len(events) == 2  # seq 4 and 5
        assert events[0]["seq"] == 4
        assert events[1]["seq"] == 5

    def test_get_events_ordered_by_seq_asc(self, tmp_path):
        """Events returned in strict seq ASC order."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Append events
        for step in ["training", "etl", "eda"]:  # Intentionally out of order
            event = ProgressEvent(
                run_id="unknown",
                step_name=step,
                phase="start",
                message=f"Running {step}",
                percent=0.0,
                timestamp=datetime.now(timezone.utc),
            )
            store.append_job_event(job_id, event)

        events = store.get_job_events_since(job_id, after_seq=0)

        # Should be in seq order (insertion order here)
        assert events[0]["step_name"] == "training"
        assert events[1]["step_name"] == "etl"
        assert events[2]["step_name"] == "eda"

    def test_get_events_empty_for_new_job(self, tmp_path):
        """Returns empty list for job with no events."""
        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        events = store.get_job_events_since(job_id, after_seq=0)

        assert events == []

    def test_get_events_after_seq_zero_returns_all(self, tmp_path):
        """after_seq=0 returns all events for the job."""
        from datetime import datetime, timezone

        from energizados.api.progress import ProgressEvent

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="unknown",
            step_name="test",
            phase="complete",
            message="Done",
            percent=100.0,
            timestamp=datetime.now(timezone.utc),
        )
        store.append_job_event(job_id, event)

        events = store.get_job_events_since(job_id, after_seq=0)

        assert len(events) == 1
        assert events[0]["seq"] == 1


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


class TestJobStoreProjectPathMigration:
    """Test project_path column migration and filtering (Phase 1 multi-project)."""

    def test_fresh_db_has_project_path_in_schema(self, tmp_path):
        """Fresh DBs include project_path column in the CREATE TABLE literal."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(jobs)").fetchall()
            names = {c["name"] for c in columns}

        assert "project_path" in names

    def test_legacy_db_without_project_path_gets_migrated(self, tmp_path):
        """Existing DB without project_path column gets ALTERed on next open."""
        import sqlite3

        db_path = tmp_path / "legacy.db"
        # Build an old-schema jobs table WITHOUT project_path and insert a row
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE jobs (
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
                    retried_from TEXT
                )
                """)
            conn.execute(
                "INSERT INTO jobs (job_id, config, config_type, status, enqueued_at) "
                "VALUES (?, ?, ?, ?, ?)",
                ("job-legacy-1", '{"train": {}}', "train", "queued", "2024-01-01T00:00:00Z"),
            )
            conn.commit()

        # Open via JobStore — migration runs in _ensure_schema
        store = JobStore(db_path=str(db_path))

        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(jobs)").fetchall()
            names = {c["name"] for c in columns}

        assert "project_path" in names

        # Pre-existing row has project_path = NULL (the Global bucket)
        legacy_job = store.get_job("job-legacy-1")
        assert legacy_job is not None
        assert legacy_job.project_path is None

    def test_migration_idempotent_project_path(self, tmp_path):
        """Migration for project_path can run multiple times safely."""
        db_path = tmp_path / "test.db"

        JobStore(db_path=str(db_path))
        store = JobStore(db_path=str(db_path))

        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(jobs)").fetchall()
            project_cols = [c for c in columns if c["name"] == "project_path"]

        assert len(project_cols) == 1  # Exactly one column, not duplicated

    def test_create_job_with_project_path_roundtrip(self, tmp_path):
        """create_job accepts project_path and persists it."""
        store = JobStore(db_path=str(tmp_path / "test.db"))
        project = str(tmp_path / "myproj")

        job_id = store.create_job({"train": {}}, "train", project_path=project)

        job = store.get_job(job_id)
        assert job.project_path == project

    def test_create_job_without_project_path_defaults_null(self, tmp_path):
        """create_job without project_path stores NULL (Global)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job_id = store.create_job({"train": {}}, "train")

        job = store.get_job(job_id)
        assert job.project_path is None

    def test_list_jobs_filter_by_project_path(self, tmp_path):
        """list_jobs(project_path=...) filters to that project only."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        proj_a = str(tmp_path / "proj_a")
        proj_b = str(tmp_path / "proj_b")
        store.create_job({"train": {}}, "train", project_path=proj_a)
        store.create_job({"train": {}}, "train", project_path=proj_b)
        store.create_job({"train": {}}, "train")  # Global (NULL)

        a_jobs = store.list_jobs(project_path=proj_a)
        assert len(a_jobs) == 1
        assert a_jobs[0].project_path == proj_a

        b_jobs = store.list_jobs(project_path=proj_b)
        assert len(b_jobs) == 1
        assert b_jobs[0].project_path == proj_b

    def test_list_jobs_no_project_filter_returns_all(self, tmp_path):
        """list_jobs() with no project_path filter returns ALL jobs (Global view)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        proj = str(tmp_path / "proj")
        store.create_job({"train": {}}, "train", project_path=proj)
        store.create_job({"train": {}}, "train")  # NULL project

        all_jobs = store.list_jobs()
        assert len(all_jobs) == 2  # Both the project-scoped and the NULL job

    def test_db_path_env_override(self, tmp_path, monkeypatch):
        """JobStore() with no args reads ENERGIZADOS_JOBS_DB from env."""
        env_path = tmp_path / "env_override.db"
        monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(env_path))

        store = JobStore()  # No explicit db_path

        assert store.db_path == env_path
        assert env_path.exists()

    def test_explicit_db_path_wins_over_env(self, tmp_path, monkeypatch):
        """Explicit db_path arg takes priority over the env var."""
        env_path = tmp_path / "env.db"
        explicit_path = tmp_path / "explicit.db"
        monkeypatch.setenv("ENERGIZADOS_JOBS_DB", str(env_path))

        store = JobStore(db_path=str(explicit_path))

        assert store.db_path == explicit_path

    def test_project_path_index_created(self, tmp_path):
        """idx_jobs_project index is created for query performance."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        with store._get_connection() as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='jobs'"
            ).fetchall()
            index_names = {i["name"] for i in indexes}

        assert "idx_jobs_project" in index_names

    def test_retry_preserves_project_path(self, tmp_path):
        """Retrying a job preserves the original project_path."""
        store = JobStore(db_path=str(tmp_path / "test.db"))
        project = str(tmp_path / "myproj")

        original_id = store.create_job({"train": {}}, "train", project_path=project)
        store.update_status(original_id, JobStatus.RUNNING)
        store.update_status(original_id, JobStatus.FAILED, error={"error_code": "X"})

        new_id = store.retry_job(original_id)

        assert new_id is not None
        new_job = store.get_job(new_id)
        assert new_job.project_path == project
