"""
Integration tests for web worker.

Following strict TDD: tests written first (RED), then implementation (GREEN).
Tests worker startup, shutdown, and basic job processing.
"""

from datetime import datetime, timezone
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from energizados.api.progress import ProgressEvent
from energizados.web.models import JobStatus
from energizados.web.store import JobStore
from energizados.web.store import JobStore as _RealJobStore
from energizados.web.worker import main, parse_args


class TestWorkerEntrypoint:
    """Test worker entrypoint and argument parsing."""

    def test_parse_args_defaults(self):
        """Test default argument values."""
        import sys

        # Mock sys.argv for testing
        original_argv = sys.argv
        sys.argv = ["worker"]  # Minimal argv

        try:
            args = parse_args()
            assert args.db_path == "data/web/jobs.db"
            assert args.log_level == "INFO"
        finally:
            sys.argv = original_argv

    def test_parse_args_custom_values(self):
        """Test custom argument values."""
        import sys

        # Mock sys.argv for testing
        original_argv = sys.argv
        sys.argv = ["worker", "--db-path", "test_worker.db", "--log-level", "DEBUG"]

        try:
            args = parse_args()
            assert args.db_path == "test_worker.db"
            assert args.log_level == "DEBUG"
        finally:
            sys.argv = original_argv

    @patch("energizados.web.worker.JobRunner")
    @patch("energizados.web.worker.JobStore")
    def test_main_initializes_components(self, mock_store_class, mock_runner_class, tmp_path):
        """Test main() initializes JobStore and JobRunner."""
        import sys

        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        mock_runner = MagicMock()
        mock_runner_class.return_value = mock_runner

        # Mock run() to set shutdown flag immediately (no infinite loop)
        def immediate_run():
            mock_runner._shutdown = True

        mock_runner.run = immediate_run

        # Mock sys.argv
        original_argv = sys.argv
        sys.argv = ["worker", "--db-path", str(tmp_path / "test.db")]

        try:
            main()

            # Verify components were initialized
            mock_store_class.assert_called_once()
            mock_runner_class.assert_called_once()
            # Verify run was called (via our immediate_run function)
            assert mock_runner._shutdown is True
        finally:
            sys.argv = original_argv


class TestWorkerIntegration:
    """Integration tests for worker with real JobStore and JobRunner."""

    def test_worker_startup_reconciliation(self, tmp_path):
        """Test worker performs startup reconciliation."""
        from energizados.web.models import JobStatus

        db_path = tmp_path / "jobs.db"
        store = JobStore(db_path=str(db_path))

        # Create an orphaned running job
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        # Mock _poll to return immediately (no real processing)
        with patch("energizados.web.runner.JobRunner._poll", return_value=False):
            # Import and create runner directly
            from energizados.web.runner import JobRunner

            runner = JobRunner(store=store)
            runner._shutdown = True  # Exit immediately after startup
            runner.run()

        # Verify orphaned job was reconciled
        job = store.get_job(job_id)
        assert job.status == JobStatus.FAILED
        assert job.error is not None
        assert job.error["error_code"] == "WORKER_RESTARTED"

    def test_worker_processes_queued_job(self, tmp_path):
        """Test worker processes queued job (with mocked child process)."""
        from energizados.web.models import JobStatus

        db_path = tmp_path / "jobs.db"
        store = JobStore(db_path=str(db_path))

        # Create a queued job
        job_id = store.create_job({"train": {"enabled": True}}, "train")

        # Mock Process to avoid real pipeline execution
        with patch("energizados.web.runner.Process") as mock_process_class:
            mock_process = MagicMock()
            mock_process.is_alive.return_value = False  # Exits immediately
            mock_process.exitcode = 0  # Success
            mock_process_class.return_value = mock_process

            # Import and run worker
            from energizados.web.runner import JobRunner

            runner = JobRunner(store=store)
            runner._poll()

        # Verify job was processed successfully
        job = store.get_job(job_id)
        assert job.status == JobStatus.SUCCESS

    def test_worker_shutdown_on_empty_queue(self, tmp_path):
        """Test worker exits when queue is empty and shutdown flag is set."""
        db_path = tmp_path / "jobs.db"
        store = JobStore(db_path=str(db_path))

        # No jobs in queue

        # Import and run worker
        from energizados.web.runner import JobRunner

        runner = JobRunner(store=store)
        runner._shutdown = True  # Simulate immediate shutdown
        runner.run()

        # Verify worker exited gracefully (no exception raised)
        assert True  # If we got here, shutdown worked

    def test_worker_continues_after_exception(self, tmp_path):
        """Test worker handles exceptions gracefully without crashing."""

        db_path = tmp_path / "jobs.db"
        store = JobStore(db_path=str(db_path))

        # Create a queued job
        store.create_job({"train": {}}, "train")

        # Import and create runner
        from energizados.web.runner import JobRunner

        runner = JobRunner(store=store)

        # _poll raises once (simulating a transient failure), then signals
        # shutdown so the run() loop exits. The loop must swallow the exception
        # and continue rather than crashing the worker.
        call_count = {"n": 0}

        def flaky_poll():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Test error during poll")
            runner._shutdown = True
            return False

        with patch.object(runner, "_poll", side_effect=flaky_poll):
            runner.run()

        # Loop survived the exception and exited cleanly
        assert call_count["n"] >= 1
        assert runner.store is store


class TestSseIntegration:
    """Integration tests for SSE live progress with real JobStore."""

    @pytest.fixture
    def real_store_app(self, tmp_path, monkeypatch):
        """FastAPI TestClient wired to a REAL JobStore on a tmp DB (no mocks)."""
        db_path = str(tmp_path / "integration.db")
        # Make app.JobStore() return a real store pointing at the tmp DB.
        monkeypatch.setattr(
            "energizados.web.app.JobStore",
            lambda *a, **kw: _RealJobStore(db_path=db_path),
        )
        # IMPORTANT: poll instantly so the running-job loop does not sleep 1s per iteration.
        monkeypatch.setattr("energizados.web.app.SSE_POLL_INTERVAL_SECONDS", 0.0)
        from fastapi.testclient import TestClient

        from energizados.web.app import app

        return TestClient(app), _RealJobStore(db_path=db_path)

    def test_sse_streams_real_events_then_closes_on_terminal(self, real_store_app):
        """End-to-end: real store writes events, SSE streams them, then closes when terminal."""
        client, store = real_store_app

        # Create job and events
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)
        store.append_job_event(
            job_id,
            ProgressEvent(
                run_id="unknown",
                step_name="etl",
                phase="start",
                message="Starting ETL",
                percent=0.0,
                timestamp=datetime.now(timezone.utc),
            ),
        )
        store.append_job_event(
            job_id,
            ProgressEvent(
                run_id="unknown",
                step_name="etl",
                phase="complete",
                message="ETL done",
                percent=100.0,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        # Mark terminal BEFORE requesting SSE stream for deterministic close
        store.update_status(job_id, JobStatus.SUCCESS)

        response = client.get(f"/jobs/{job_id}/progress")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        text = response.text
        assert 'data: {"seq": 1' in text
        assert 'data: {"seq": 2' in text
        assert "event: terminal" in text
        assert '"status": "success"' in text


class TestJobStoreConcurrency:
    """Integration tests for JobStore thread-safety under concurrent load."""

    def test_concurrent_read_write_isolation(self, tmp_path):
        """Thread-safety of JobStore under concurrent worker writes + web reads."""
        db_path = str(tmp_path / "concurrent.db")
        store = _RealJobStore(db_path=db_path)
        write_errors = []
        read_errors = []

        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        def writer():
            for i in range(50):
                try:
                    store.append_job_event(
                        job_id,
                        ProgressEvent(
                            run_id="unknown",
                            step_name="step",
                            phase="progress",
                            message=f"Event {i}",
                            percent=float(i),
                            timestamp=datetime.now(timezone.utc),
                        ),
                    )
                except Exception as e:
                    write_errors.append(e)

        def reader():
            for _ in range(50):
                try:
                    store.get_job_events_since(job_id, after_seq=0)
                except Exception as e:
                    read_errors.append(e)

        w = Thread(target=writer)
        r = Thread(target=reader)
        w.start()
        r.start()
        w.join()
        r.join()

        assert write_errors == []
        assert read_errors == []
        events = store.get_job_events_since(job_id, after_seq=0)
        assert len(events) == 50
        assert [e["seq"] for e in events] == list(range(1, 51))
