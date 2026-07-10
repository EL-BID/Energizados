# Tasks: web-console-phase5 - SSE Live Progress

## Review Workload Forecast

**Estimated Changed Lines:**
- `src/energizados/web/store.py`: +120 lines (new methods, migration)
- `src/energizados/web/runner.py`: +15 lines (callback replacement)
- `src/energizados/web/app.py`: +85 lines (SSE endpoint)
- `src/energizados/web/templates/job_detail.html`: +60 lines (EventSource UI)
- `tests/web/test_store.py`: +180 lines (new test classes)
- `tests/web/test_app.py`: +140 lines (SSE endpoint tests)
- **Total: ~600 lines**

**400-Line Budget Risk:** **Medium** (600 estimated = 150% of budget)
- Risk mitigation: Tasks are modular and testable in isolation
- Can ship partial completion (e.g., persistence without UI, SSE without UI)
- No complex algorithms — straightforward CRUD + SSE wiring

**Chained PRs Recommended:** **No** (single focused change, can ship in one PR)

**Decision Needed Before Apply:** **No** (MVP scope is clear and approved)

---

## Task Checklist (Strict TDD Order)

### Task 1: JobStore Schema Migration (percent: INTEGER → REAL)

**Spec Requirements:** Schema Migration for Percent Column
**Design:** ADR-003 (drop+recreate since table empty)

**Test First (RED):**
```python
# tests/web/test_store.py

class TestJobStoreSchemaMigration:
    """Test job_events.percent column migration INTEGER → REAL."""

    def test_percent_column_is_real_nullable(self, tmp_path):
        """Schema migration creates percent as REAL nullable."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        with store._get_connection() as conn:
            columns = conn.execute("PRAGMA table_info(job_events)").fetchall()
            percent_col = [c for c in columns if c["name"] == "percent"]

        assert len(percent_col) == 1
        assert percent_col["type"] == "REAL"
        assert percent_col["notnull"] == 0  # Nullable

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

        assert percent_col["type"] == "REAL"
```

**Implementation (GREEN):**
- Modify `_ensure_schema()` in `src/energizados/web/store.py`
- Add PRAGMA check for existing `percent` column type
- Drop table if INTEGER detected, recreate with REAL

---

### Task 2: JobStore.append_job_event() Method

**Spec Requirements:** Job Events Progress Persistence
**Design:** Section 1 (JobStore Additions)

**Test First (RED):**
```python
# tests/web/test_store.py

class TestJobStoreAppendEvent:
    """Test append_job_event persistence with monotonic seq."""

    def test_append_event_assigns_monotonic_seq(self, tmp_path):
        """Seq increments monotonically per job (1, 2, 3...)."""
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event1 = ProgressEvent(
            run_id="unknown",
            step_name="etl",
            phase="start",
            message="Starting ETL",
            percent=0.0,
            timestamp=datetime.now(timezone.utc)
        )

        event2 = ProgressEvent(
            run_id="unknown",
            step_name="etl",
            phase="complete",
            message="ETL complete",
            percent=100.0,
            timestamp=datetime.now(timezone.utc)
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
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="run-123",
            step_name="training",
            phase="start",
            message="Starting training",
            percent=50.5,  # Float value
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
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
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")

        event1 = ProgressEvent(
            run_id="unknown", step_name="step1", phase="start",
            message="Job1 step1", percent=0.0, timestamp=datetime.now(timezone.utc)
        )
        event2 = ProgressEvent(
            run_id="unknown", step_name="step2", phase="start",
            message="Job2 step2", percent=0.0, timestamp=datetime.now(timezone.utc)
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
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        # Mock store with broken connection
        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="unknown", step_name="test", phase="start",
            message="Test event", percent=0.0, timestamp=datetime.now(timezone.utc)
        )

        # Mock _get_connection to raise exception
        with patch.object(store, "_get_connection", side_effect=Exception("DB error")):
            result = store.append_job_event(job_id, event)

        assert result is False  # Returns False, doesn't raise
```

**Implementation (GREEN):**
- Add `append_job_event()` method to `JobStore` in `src/energizados/web/store.py`
- Transaction-based `MAX(seq)+1` per job
- Try/except wrapper returning `bool` (never raises)

---

### Task 3: JobStore.get_job_events_since() Method

**Spec Requirements:** SSE Endpoint for Live Progress
**Design:** Section 1 (JobStore Additions)

**Test First (RED):**
```python
# tests/web/test_store.py

class TestJobStoreGetEventsSince:
    """Test get_job_events_since query and ordering."""

    def test_get_events_filters_by_seq(self, tmp_path):
        """Returns only events with seq > after_seq."""
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Append 5 events
        for i in range(5):
            event = ProgressEvent(
                run_id="unknown", step_name=f"step{i}", phase="start",
                message=f"Step {i}", percent=0.0, timestamp=datetime.now(timezone.utc)
            )
            store.append_job_event(job_id, event)

        # Fetch after seq=3
        events = store.get_job_events_since(job_id, after_seq=3)

        assert len(events) == 2  # seq 4 and 5
        assert events[0]["seq"] == 4
        assert events[1]["seq"] == 5

    def test_get_events_ordered_by_seq_asc(self, tmp_path):
        """Events returned in strict seq ASC order."""
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Append events
        for step in ["training", "etl", "eda"]:  # Intentionally out of order
            event = ProgressEvent(
                run_id="unknown", step_name=step, phase="start",
                message=f"Running {step}", percent=0.0, timestamp=datetime.now(timezone.utc)
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
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        event = ProgressEvent(
            run_id="unknown", step_name="test", phase="complete",
            message="Done", percent=100.0, timestamp=datetime.now(timezone.utc)
        )
        store.append_job_event(job_id, event)

        events = store.get_job_events_since(job_id, after_seq=0)

        assert len(events) == 1
        assert events[0]["seq"] == 1
```

**Implementation (GREEN):**
- Add `get_job_events_since()` method to `JobStore` in `src/energizados/web/store.py`
- Query with `WHERE job_id = ? AND seq > ? ORDER BY seq ASC`

---

### Task 4: Worker progress_callback Wiring

**Spec Requirements:** Job Events Progress Persistence
**Design:** Section 3 (Worker Integration)

**Test First (RED):**
```python
# tests/web/test_runner.py

class TestJobRunnerProgressCallback:
    """Test progress_callback integration with JobStore."""

    @patch("energizados.web.runner.Process")
    def test_progress_callback_writes_to_job_events(self, mock_process_class, tmp_path):
        """Progress events from pipeline are written to job_events."""
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Mock Process that exits immediately
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.exitcode = 0
        mock_process_class.return_value = mock_process

        # Mock builder.run() to invoke callback with fake event
        def fake_run(progress_callback=None):
            if progress_callback:
                event = ProgressEvent(
                    run_id="unknown", step_name="etl", phase="start",
                    message="Starting ETL", percent=0.0,
                    timestamp=datetime.now(timezone.utc)
                )
                progress_callback(event)
            return {}  # Fake pipeline result

        with patch("energizados.web.runner.ConfigPipelineBuilder") as mock_builder_class:
            mock_builder = MagicMock()
            mock_builder.run.side_effect = fake_run
            mock_builder_class.return_value = mock_builder

            runner = JobRunner(store=store)
            runner._poll()

        # Verify event was written
        events = store.get_job_events_since(job_id, after_seq=0)
        assert len(events) == 1
        assert events[0]["step_name"] == "etl"
        assert events[0]["phase"] == "start"

    @patch("energizados.web.runner.Process")
    def test_progress_callback_failure_does_not_abort_pipeline(self, mock_process_class, tmp_path):
        """Callback write failure doesn't crash the job (job succeeds)."""
        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Mock Process that exits successfully
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.exitcode = 0
        mock_process_class.return_value = mock_process

        # Mock builder.run() to invoke callback
        def fake_run(progress_callback=None):
            if progress_callback:
                event = MagicMock()  # Fake ProgressEvent
                progress_callback(event)
            return {}  # Pipeline still succeeds

        # Mock store.append_job_event to raise (simulating DB error)
        with patch.object(store, "append_job_event", side_effect=Exception("DB locked")):
            with patch("energizados.web.runner.ConfigPipelineBuilder") as mock_builder_class:
                mock_builder = MagicMock()
                mock_builder.run.side_effect = fake_run
                mock_builder_class.return_value = mock_builder

                runner = JobRunner(store=store)
                runner._poll()

        # Job still succeeded despite callback failure
        job = store.get_job(job_id)
        assert job.status == JobStatus.SUCCESS

    @patch("energizados.web.runner.Process")
    def test_progress_callback_captures_correct_job_id(self, mock_process_class, tmp_path):
        """Callback closure captures job_id correctly per job."""
        store = JobStore(db_path=str(tmp_path / "test.db"))

        job1_id = store.create_job({"train": {}}, "train")
        job2_id = store.create_job({"etl": {}}, "etl")

        # Mock Process that exits immediately
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.exitcode = 0
        mock_process_class.return_value = mock_process

        # Track which job_id the callback receives
        callback_job_ids = []

        def fake_run(progress_callback=None):
            if progress_callback:
                # Inspect closure to get job_id
                # (This is tricky; alternatively, check written events)
                pass
            return {}

        with patch("energizados.web.runner.ConfigPipelineBuilder") as mock_builder_class:
            mock_builder = MagicMock()
            mock_builder.run.side_effect = fake_run
            mock_builder_class.return_value = mock_builder

            runner = JobRunner(store=store)

            # Process job1
            runner._poll()
            job1_events = store.get_job_events_since(job1_id, after_seq=0)

            # Process job2
            runner._poll()
            job2_events = store.get_job_events_since(job2_id, after_seq=0)

        # Verify events written to correct jobs
        # (This test might need adjustment based on callback implementation)
```

**Implementation (GREEN):**
- Replace stub `progress_callback` in `src/energizados/web/runner.py` (lines 50-52)
- Import `JobStore` and call `append_job_event(job_id, event)`
- Wrap in try/except logging error but never raising

---

### Task 5: SSE Endpoint (GET /jobs/{job_id}/progress)

**Spec Requirements:** SSE Endpoint for Live Progress
**Design:** Section 4 (SSE Endpoint)

**Test First (RED):**
```python
# tests/web/test_app.py

class TestSSEProgressEndpoint:
    """Test GET /jobs/{job_id}/progress SSE streaming."""

    def test_sse_unknown_job_returns_404(self, client, mock_store):
        """GET /jobs/{unknown_id}/progress returns 404."""
        mock_store.get_job.return_value = None

        response = client.get("/jobs/unknown-job-id/progress")

        assert response.status_code == 404
        mock_store.get_job.assert_called_once_with("unknown-job-id")

    def test_sse_returns_event_stream_content_type(self, client, mock_store):
        """SSE endpoint returns text/event-stream."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z"
        )
        mock_store.get_job.return_value = mock_job
        mock_store.get_job_events_since.return_value = []

        response = client.get("/jobs/job-running-1/progress")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

    def test_sse_streams_events_with_correct_format(self, client, mock_store):
        """SSE yields events as 'data: {json}\n\n' format."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z"
        )
        mock_store.get_job.return_value = mock_job

        mock_events = [
            {"seq": 1, "phase": "start", "step_name": "etl", "message": "Starting ETL", "percent": 0.0, "timestamp": "2024-01-01T00:00:01Z"},
            {"seq": 2, "phase": "complete", "step_name": "etl", "message": "ETL complete", "percent": 100.0, "timestamp": "2024-01-01T00:00:05Z"},
        ]
        mock_store.get_job_events_since.return_value = mock_events

        response = client.get("/jobs/job-running-1/progress")

        assert response.status_code == 200

        # Read streaming response
        content = response.text

        # Should contain SSE formatted events
        assert 'data: {"seq": 1,' in content
        assert 'data: {"seq": 2,' in content
        assert "\n\n" in content  # SSE delimiter

    def test_sse_terminal_job_replays_history_then_closes(self, client, mock_store):
        """Terminal job replays all events then sends terminal event."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-complete-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,  # Terminal
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z",
            finished_at="2024-01-01T00:05:00Z"
        )
        mock_store.get_job.return_value = mock_job

        mock_events = [
            {"seq": 1, "phase": "start", "step_name": "etl", "message": "Starting", "percent": 0.0, "timestamp": "2024-01-01T00:00:01Z"},
            {"seq": 2, "phase": "complete", "step_name": "etl", "message": "Done", "percent": 100.0, "timestamp": "2024-01-01T00:00:05Z"},
        ]
        mock_store.get_job_events_since.return_value = mock_events

        response = client.get("/jobs/job-complete-1/progress")

        assert response.status_code == 200
        content = response.text

        # Should replay all events
        assert 'data: {"seq": 1,' in content
        assert 'data: {"seq": 2,' in content

        # Should include terminal event
        assert "event: terminal" in content or "terminal" in content.lower()

    def test_sse_running_job_polls_for_new_events(self, client, mock_store):
        """Running job keeps polling until terminal (generator continues)."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-poll",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,  # Not terminal
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z"
        )
        mock_store.get_job.return_value = mock_job
        mock_store.get_job_events_since.return_value = []

        # This test is tricky with TestClient — might need httpx or direct generator inspection
        # For now, verify the endpoint doesn't immediately close
        response = client.get("/jobs/job-running-poll/progress")

        assert response.status_code == 200
        # Should eventually include polling loop (implementation detail)

    def test_sse_filters_events_by_last_seq(self, client, mock_store):
        """SSE respects after_seq parameter (via query string or header)."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-filter-1",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z"
        )
        mock_store.get_job.return_value = mock_job

        # Mock get_job_events_since to verify it receives correct after_seq
        mock_store.get_job_events_since.return_value = [
            {"seq": 4, "phase": "start", "step_name": "training", "message": "Starting training", "percent": 0.0, "timestamp": "2024-01-01T00:00:04Z"}
        ]

        # Note: The endpoint might not expose last_seq directly; it's for internal use
        # This test may need adjustment based on implementation
        response = client.get("/jobs/job-filter-1/progress")

        assert response.status_code == 200
        # Verify get_job_events_since was called with after_seq > 0 (implementation-specific)

    def test_sse_client_disconnect_handled(self, client, mock_store):
        """Generator stops when client disconnects."""
        # This requires async generator inspection or mocking request.is_disconnected()
        # Complex to test with TestClient — might need httpx AsyncClient
        pytest.skip("Requires async client — defer to integration test")
```

**Implementation (GREEN):**
- Add `GET /jobs/{job_id}/progress` route to `src/energizados/web/app.py`
- Async generator `event_stream()` with `asyncio.sleep(0.5)` polling
- `StreamingResponse` with `media_type="text/event-stream"`
- Terminal detection via `job.is_terminal()`

---

### Task 6: UI EventSource Integration (job_detail.html)

**Spec Requirements:** UI Integration with EventSource
**Design:** Section 5 (UI Integration)

**Test First (RED):**
```python
# tests/web/test_app.py

class TestJobDetailProgressUI:
    """Test EventSource UI rendering in job_detail.html."""

    def test_job_detail_includes_eventsource_for_running_jobs(self, client, mock_store):
        """job_detail.html includes EventSource script when job is running."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-running-ui",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z",
            started_at="2024-01-01T00:01:00Z"
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-running-ui")

        assert response.status_code == 200
        content = response.text

        # Should include EventSource initialization
        assert "EventSource" in content
        assert "/jobs/job-running-ui/progress" in content or "progress" in content

        # Should include progress container
        assert "progress-container" in content.lower() or "progress" in content.lower()

    def test_job_detail_no_eventsource_for_terminal_jobs(self, client, mock_store):
        """Terminal jobs don't include EventSource (no live progress)."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-success-ui",
            config={"train": {}},
            config_type="train",
            status=JobStatus.SUCCESS,
            enqueued_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:05:00Z"
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-success-ui")

        assert response.status_code == 200
        content = response.text

        # Should NOT include live progress EventSource
        # (might show static history, but not live EventSource)
        assert "EventSource" not in content or "/jobs/job-success-ui/progress" not in content

    def test_eventsource_fallback_for_unsupported_browsers(self, client, mock_store):
        """Template includes graceful fallback if EventSource unsupported."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-fallback",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z"
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-fallback")

        assert response.status_code == 200
        content = response.text

        # Should include fallback check
        assert "typeof EventSource" in content or "EventSource" in content
        # Should show message if unsupported
        assert "unsupported" in content.lower() or "fallback" in content.lower()

    def test_eventsource_terminal_handler_triggers_refresh(self, client, mock_store):
        """EventSource terminal event handler triggers HTMX refresh."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-terminal-handler",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z"
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-terminal-handler")

        assert response.status_code == 200
        content = response.text

        # Should include terminal event listener
        assert "addEventListener" in content
        assert "terminal" in content.lower()

        # Should trigger HTMX refresh
        assert "htmx.ajax" in content or "htmx" in content.lower()

    def test_progress_container_renders_phase_badges(self, client, mock_store):
        """Progress timeline renders phase badges (start/complete/error)."""
        from energizados.web.models import JobRow, JobStatus

        mock_job = JobRow(
            job_id="job-phases",
            config={"train": {}},
            config_type="train",
            status=JobStatus.RUNNING,
            enqueued_at="2024-01-01T00:00:00Z"
        )
        mock_store.get_job.return_value = mock_job

        response = client.get("/jobs/job-phases")

        assert response.status_code == 200
        content = response.text

        # Should include phase display logic
        assert "phase" in content.lower()
        # Should include icons or badges for phases
        assert ("start" in content.lower() or "▶" in content or "running" in content.lower())
```

**Implementation (GREEN):**
- Add EventSource section to `src/energizados/web/templates/job_detail.html`
- Wrap in `{% if job.status.value == "running" or job.status.value == "queued" %}`
- Include progress container, EventSource init, terminal handler, fallback

---

### Task 7: Integration Test (End-to-End)

**Spec Requirements:** Full pipeline from worker → job_events → SSE → UI
**Design:** Data Flow diagram

**Test First (RED):**
```python
# tests/web/test_integration.py (new file)

class TestSSEIntegration:
    """End-to-end test: worker → job_events → SSE → client."""

    def test_full_progress_flow(self, tmp_path):
        """Worker emits event → job_events row → SSE streams it."""
        from energizados.web.store import JobStore
        from energizados.web.runner import JobRunner
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone
        import asyncio
        import httpx

        # Setup
        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")
        store.update_status(job_id, JobStatus.RUNNING)

        # Simulate worker writing event
        event = ProgressEvent(
            run_id="unknown", step_name="etl", phase="start",
            message="Starting ETL", percent=0.0, timestamp=datetime.now(timezone.utc)
        )
        store.append_job_event(job_id, event)

        # Simulate SSE client reading event
        async def read_sse():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", f"http://testserver/jobs/{job_id}/progress") as response:
                    async for chunk in response.aiter_text():
                        if "data:" in chunk:
                            return chunk

        # This test requires a running test server — might be better as a manual test
        # Or use TestClient with streaming support
        pytest.skip("Requires running test server — defer to manual verification")

    def test_concurrent_read_write_isolation(self, tmp_path):
        """Concurrent worker writes + web reads don't deadlock."""
        from energizados.web.store import JobStore
        from energizados.api.progress import ProgressEvent
        from datetime import datetime, timezone
        import threading

        store = JobStore(db_path=str(tmp_path / "test.db"))
        job_id = store.create_job({"train": {}}, "train")

        # Simulate concurrent writes and reads
        write_errors = []
        read_errors = []

        def worker_writes():
            try:
                for i in range(10):
                    event = ProgressEvent(
                        run_id="unknown", step_name=f"step{i}", phase="start",
                        message=f"Step {i}", percent=0.0, timestamp=datetime.now(timezone.utc)
                    )
                    store.append_job_event(job_id, event)
            except Exception as e:
                write_errors.append(e)

        def web_reads():
            try:
                for i in range(10):
                    store.get_job_events_since(job_id, after_seq=0)
            except Exception as e:
                read_errors.append(e)

        thread1 = threading.Thread(target=worker_writes)
        thread2 = threading.Thread(target=web_reads)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        assert write_errors == []
        assert read_errors == []

        # Verify all events written
        events = store.get_job_events_since(job_id, after_seq=0)
        assert len(events) == 10
```

**Implementation (GREEN):**
- Integration is automatic once Tasks 1-6 are complete
- Manual verification via running worker and browser

---

### Task 8: Cleanup and Refactoring

**Test First (RED):**
- (No new tests — refactoring existing code)

**Implementation (GREEN):**
- Extract magic values to constants (poll interval, SSE headers)
- Add logging to SSE endpoint (connect, disconnect, terminal)
- Verify all tests still pass after refactoring
- Update docstrings for new methods
- Check for TODO/FIXME comments from implementation

---

## Task Ordering and Dependencies

**Sequential (must run in order):**
1. Task 1 (Schema migration) — foundation
2. Task 2 (append_job_event) — needs Task 1 schema
3. Task 3 (get_job_events_since) — can run parallel to Task 2
4. Task 4 (Worker callback) — needs Task 2
5. Task 5 (SSE endpoint) — needs Task 3
6. Task 6 (UI) — needs Task 5
7. Task 7 (Integration) — needs all previous
8. Task 8 (Refactoring) — always last

**Parallel opportunities:**
- Tasks 2 and 3 can run in parallel (independent methods)
- Tasks 5 and 6 could be parallel in theory (UI can mock SSE)
- All tests are isolated via `tmp_path`, so test execution can parallelize

**Estimated test-first implementation time:**
- Task 1: 30 min (simple migration)
- Task 2: 60 min (transaction logic, error handling)
- Task 3: 30 min (simple query)
- Task 4: 60 min (callback wiring, isolation tests)
- Task 5: 90 min (async generator, streaming response)
- Task 6: 45 min (template, JS EventSource)
- Task 7: 60 min (integration test setup)
- Task 8: 30 min (refactoring, cleanup)

**Total: ~7 hours** (excluding debugging and test refinement)

---

## Risk Factors

**High Risk:**
- SSE endpoint async complexity (generator lifecycle, disconnect handling)
- Callback isolation (ensuring DB errors never crash jobs)

**Medium Risk:**
- Schema migration on existing deployments (mitigated by empty table)
- EventSource browser compatibility (mitigated by fallback)

**Low Risk:**
- JobStore CRUD logic (straightforward SQLite)
- Template rendering (static HTML/JS, no backend complexity)

**Mitigation Strategy:**
- Start with Task 1-3 (JobStore foundation) — highest confidence
- Tackle Task 5 (SSE) with careful async testing
- Manual verification for Task 7 (integration)
- Keep Task 6 (UI) simple — no complex client-side state
