# Design: web-console Phase 5 — SSE Live Progress

## Executive Summary

Persist coarse-grained progress events from worker to SQLite (job_events table), stream them via Server-Sent Events (SSE) to the job detail UI, and replace the uncertainty of 2-second HTMX polling with real-time step timeline. Minimal MVP: step start/complete/error events only, no reconnect/TTL yet.

## Architecture Approach

**Pattern**: Persist + Tail (Option A from proposal)
- Worker writes events to `job_events` (SQLite, WAL mode)
- SSE endpoint tails events since last seq
- Browser renders step timeline via EventSource

**Rejected alternatives**:
- B (in-process): breaks async, no job isolation
- C (pub/sub): adds infra (Redis), not MVP

## Data Flow

```
┌─────────────────┐        ┌──────────────────┐        ┌─────────────┐
│ JobRunner child │        │  JobStore (SQLite)│        │   Web app   │
│  _run_job()     │        │   job_events      │        │             │
│                 │        │                  │        │             │
│ builder.run()   │───→    │  append_job_event│◄───┐   │ GET /jobs/  │
│  with callback  │        │  (write seq)     │    │   │ {id}/events │
│                 │        │                  │    │   │  (SSE)      │
│ progress_callback│───────→│  progress_event  │────┘   │             │
└─────────────────┘        └──────────────────┘        └──────┬──────┘
                                                                │
                                                                ▼
                                                       ┌─────────────────┐
                                                       │ job_detail.html │
                                                       │  EventSource    │
                                                       │  step timeline  │
                                                       └─────────────────┘
```

## Component Design

### 1. JobStore Additions (`src/energizados/web/store.py`)

**New methods**:

```python
def append_job_event(self, job_id: str, event: ProgressEvent) -> bool:
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
    try:
        with self._get_connection() as conn:
            # Get next seq for this job (transaction ensures monotonic)
            cursor = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM job_events WHERE job_id = ?",
                (job_id,)
            )
            next_seq = cursor.fetchone()[0] + 1

            # Insert event
            conn.execute("""
                INSERT INTO job_events (job_id, seq, phase, step_name, message, percent, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                next_seq,
                event.phase,
                event.step_name,
                event.message,
                event.percent,  # None for coarse events
                event.timestamp.isoformat()
            ))
            conn.commit()
            logger.debug(f"[{job_id}] Event {next_seq}: {event.step_name} - {event.phase}")
            return True
    except Exception as e:
        logger.error(f"Failed to write job event for {job_id}: {e}")
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
        rows = conn.execute("""
            SELECT seq, phase, step_name, message, percent, timestamp
            FROM job_events
            WHERE job_id = ? AND seq > ?
            ORDER BY seq ASC
        """, (job_id, after_seq)).fetchall()

    return [dict(row) for row in rows]
```

**Seq assignment**: Transaction-based MAX(seq)+1 per job ensures monotonic sequencing even under concurrent writes (single writer in practice, but WAL allows concurrent readers).

**Error handling**: Both methods swallow errors (log + return False/empty) because they're called from critical paths:
- `append_job_event`: callback in child process — must not crash pipeline
- `get_job_events_since`: SSE generator — must not raise and break stream

### 2. Schema Migration (`src/energizados/web/store.py::_ensure_schema`)

**Current schema** (line 75-87):
```sql
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    phase TEXT NOT NULL,
    step_name TEXT NOT NULL,
    message TEXT NOT NULL,
    percent INTEGER,  -- ← Needs to be REAL
    timestamp TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
)
```

**Migration approach**: Since `job_events` is currently empty (Phase 1 stub, never populated), drop and recreate is safe and simpler than SQLite's multi-step alter table dance:

```python
def _ensure_schema(self):
    """Create database schema if missing (idempotent)."""
    with self._get_connection() as conn:
        # ... existing jobs table ...

        # Migrate job_events: drop if percent is INTEGER (old schema)
        # Detect by checking column type (SQLite PRAGMA)
        existing_columns = conn.execute(
            "PRAGMA table_info(job_events)"
        ).fetchall()
        percent_col = [c for c in existing_columns if c[1] == "percent"]

        if percent_col and percent_col[2] == "INTEGER":
            logger.info("Migrating job_events.percent: INTEGER → REAL")
            conn.execute("DROP TABLE job_events")

        # Create with corrected schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                phase TEXT NOT NULL,
                step_name TEXT NOT NULL,
                message TEXT NOT NULL,
                percent REAL,  -- Fixed: REAL (nullable)
                timestamp TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)

        # ... existing indexes ...
```

**Coarse % storage**: MVP uses 0 (start), 100 (complete), or null (error/unknown). No fine-grained progress.

### 3. Worker Integration (`src/energizados/web/runner.py`)

**Stub replacement** (lines 50-52):

```python
def progress_callback(event):
    """
    Write progress events to job_events table (Phase 5).

    Captures job_id from closure. Runs in child process.
    Must NOT raise — errors logged and swallowed.
    """
    from energizados.web.store import JobStore
    from energizados.api.progress import ProgressEvent

    try:
        store = JobStore()
        # Map ProgressEvent → job_event row
        # Note: event.run_id may be "unknown" early; job_id is the key
        store.append_job_event(job_id, event)
    except Exception as e:
        # Callback failure must not crash pipeline
        import logging
        logging = logging.getLogger(__name__)
        logging.error(f"Progress callback failed for job {job_id}: {e}")
```

**Integration point**: The callback is already wired to `builder.run(progress_callback=progress_callback)` at line 61. Just replace the stub.

**Process boundary**: Callback runs in child Process (spawned at line 133). Each JobStore instance creates its own SQLite connection via `_get_connection()`. WAL mode allows concurrent readers (web) + writers (worker child).

**Callback isolation**: The `safe_emit` pattern already ensures callback failures don't propagate (see core/pipeline.py if relevant). The additional try/catch here is defense-in-depth.

### 4. SSE Endpoint (`src/energizados/web/app.py`)

**New route**:

```python
from fastapi.responses import StreamingResponse
import asyncio

@app.get("/jobs/{job_id}/events")
async def get_job_events(job_id: str, request: Request):
    """
    SSE endpoint for live job progress events.

    Streams job_events as text/event-stream. Yields events as they arrive.
    Sends terminal event when job reaches success/failed/aborted.

    Args:
        job_id: Job identifier

    Returns:
        StreamingResponse with media_type="text/event-stream"

    Raises:
        HTTPException(404): If job not found
    """
    store = JobStore()
    job = store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        """Async generator yielding SSE events."""
        last_seq = 0
        poll_interval = 0.5  # 500ms

        while True:
            # Check client disconnect
            if await request.is_disconnected():
                logger.debug(f"SSE client disconnected for job {job_id}")
                break

            # Fetch new events
            events = store.get_job_events_since(job_id, last_seq)

            for event in events:
                last_seq = event["seq"]

                # Yield SSE formatted event
                yield f"data: {json.dumps(event)}\n\n"

            # Check if job is terminal
            job = store.get_job(job_id)
            if job and job.is_terminal():
                # Send terminal event and close
                terminal = {
                    "event": "terminal",
                    "data": {
                        "job_id": job.job_id,
                        "status": job.status.value,
                        "finished_at": job.finished_at
                    }
                }
                yield f"event: terminal\ndata: {json.dumps(terminal['data'])}\n\n"
                logger.debug(f"Job {job_id} terminal, closing SSE stream")
                break

            # Wait before next poll (async)
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

**Polling interval**: 500ms balances responsiveness (operator sees progress within 0.5s) vs load (2 queries/sec). Configurable via env var in future.

**Terminal detection**: Each loop re-fetches job status. When terminal, yields a special `event: terminal` message and breaks. Client closes EventSource on receipt.

**Client disconnect**: `await request.is_disconnected()` checks every loop to avoid orphaned generators.

**No heartbeat**: MVP skips heartbeat (comment every N seconds). Proxy timeout handling deferred.

**Backpressure**: Not capped for MVP. Single-worker deployment means max N concurrent SSE where N = users in deployment. Connection pooling via uvicorn defaults suffices.

### 5. UI Integration (`src/energizados/web/templates/job_detail.html`)

**Add section** (after Timeline, before Execution):

```html
{% if job.status.value == "running" or job.status.value == "queued" %}
<div class="mt-3">
    <h6 class="small text-uppercase text-muted mb-2">Live Progress</h6>
    <div id="progress-container" class="border rounded p-2" style="min-height: 100px; max-height: 300px; overflow-y: auto;">
        <div class="small text-muted">Waiting for events...</div>
    </div>
</div>
{% endif %}

<script>
(function() {
    // Only inject EventSource if supported (fallback to HTMX auto-refresh)
    if (typeof EventSource === 'undefined') {
        console.warn('EventSource not supported, using HTMX fallback');
        return;
    }

    const job_id = '{{ job.job_id }}';
    const container = document.getElementById('progress-container');
    const eventSource = new EventSource(`/jobs/${job_id}/events`);

    eventSource.onmessage = function(e) {
        const event = JSON.parse(e.data);

        // Replace initial message
        if (container.querySelector('.text-muted')) {
            container.innerHTML = '';
        }

        // Append event row
        const row = document.createElement('div');
        row.className = 'small mb-1';

        // Phase-based icon/color
        let icon = '🔄';
        let color = 'text-primary';
        if (event.phase === 'complete') { icon = '✅'; color = 'text-success'; }
        if (event.phase === 'error') { icon = '❌'; color = 'text-danger'; }
        if (event.phase === 'start') { icon = '▶️'; color = 'text-info'; }

        row.innerHTML = `<span class="${color}">${icon}</span> ${event.step_name}: ${event.message}`;
        container.appendChild(row);
        container.scrollTop = container.scrollHeight;
    };

    eventSource.addEventListener('terminal', function(e) {
        const data = JSON.parse(e.data);
        eventSource.close();

        // Reload job detail to show final state
        setTimeout(() => {
            htmx.ajax('GET', `/jobs/${job_id}`, {target: '#job-detail', swap: 'outerHTML'});
        }, 1000);
    });

    eventSource.onerror = function(e) {
        console.error('SSE error:', e);
        eventSource.close();

        // Show fallback message
        container.innerHTML = '<div class="small text-warning">Live progress unavailable. Page will auto-refresh.</div>';
    };
})();
</script>
{% endif %}
```

**HTMX refresh on terminal**: After receiving terminal event, close EventSource and trigger HTMX reload to refresh the entire job card with final status/run_id.

**Graceful degradation**: If EventSource is undefined (old browsers), script returns early; existing HTMX auto-refresh continues working.

## ADR: Key Decisions

### ADR-001: Seq Assignment Strategy

**Decision**: Use `MAX(seq)+1` per-job within a transaction, not auto-increment.

**Rationale**:
- Auto-increment is global (shared across all jobs); per-job seq needs isolation
- Transaction ensures monotonic seq even if two callbacks race (unlikely in single-worker, but correct)
- Simpler than separate sequences table

**Rejected**: Global auto-increment would work but mixes events from different jobs; `seq` becomes global offset, not per-job index.

### ADR-002: Error Handling in Callback

**Decision**: Callback must NEVER raise. Log + swallow errors.

**Rationale**:
- Callback runs in child process during pipeline execution
- Unhandled exception would crash the entire job (worker sees exitcode != 0)
- Job loss is unacceptable; better to miss an event than lose the job

**Rejected**: Letting exceptions propagate would mark successful jobs as failed.

### ADR-003: Schema Migration Strategy

**Decision**: Drop+recreate `job_events` table since it's empty.

**Rationale**:
- SQLite `ALTER TABLE` can't change column type directly
- Requires: CREATE new, COPY data, DROP old, RENAME new
- Since table is empty (Phase 1 stub), drop+recreate is simpler and safe
- No production data at risk

**Rejected**: Multi-step migration is overkill for empty table.

### ADR-004: SSE Polling Interval

**Decision**: 500ms poll interval (2 queries/sec).

**Rationale**:
- Operator perceives sub-second updates as "real-time"
- SQLite WAL handles 2 QPS easily (single writer, multiple readers)
- Lower interval (100ms) increases load without UX gain (coarse steps)
- Higher interval (2s) defeats purpose vs HTMX

**Rejected**: 100ms would be 10 QPS, unnecessary for coarse step events.

### ADR-005: Use job_id Not run_id

**Decision**: Events keyed by `job_id`, not `run_id`.

**Rationale**:
- `run_id` is only available AFTER pipeline completes (written to context)
- Callback runs DURING pipeline execution — `run_id` unknown/meaningless
- `job_id` is available at callback time (closure var in `_run_job`)
- JobStore already has `job_id` foreign key on `job_events`

**Rejected**: Using `run_id` would require redesigning pipeline to emit run_id early, coupling job and run lifecycles.

## Open Questions & Resolutions

| Q | Resolution |
|---|------------|
| What if callback writes fail? | Log + continue (job succeeds, events partial). Acceptable for MVP. |
| SSE reconnect after network drop? | Manual page refresh (deferred: Last-Event-ID). |
| Event TTL/cleanup? | Documented debt (follow-up: worker cleanup task). |
| Concurrency limit on SSE connections? | Not capped (single-worker deployment; N = users). |
| Proxy timeout drops SSE? | X-Accel-Buffering header (nginx) — other proxies deferred. |

## Risks

| Risk | Mitigation |
|------|------------|
| **job_events unbounded growth** | Documented debt; cleanup in follow-up (DELETE WHERE timestamp < X). |
| **SSE connection drops on network hiccup** | Manual page refresh fallback; auto-reconnect deferred. |
| **Callback write failure partially loses events** | Log error; job still succeeds. Acceptable for MVP. |
| **SQLite lock contention under high write rate** | WAL mode, single writer (worker), concurrent readers (web). Mitigated. |
| **Child process SQLite connection leak** | Each JobStore call uses context manager (`with self._get_connection()`), connection closes on exit. |

## Validation Criteria

- Worker writes step start/complete/error events to `job_events`
- SSE endpoint streams new events as they arrive (sub-500ms latency)
- Job detail page shows real-time step timeline without page refresh
- Terminal event triggers HTMX refresh to show final state
- Existing HTMX fallback still works if SSE fails
- Schema migration succeeds on existing deployments (drop+recreate is safe)
