# Delta for web-console — Phase 5

## ADDED Requirements

### Requirement: Job Events Progress Persistence

The system MUST persist each ProgressEvent from the pipeline to the job_events table via the worker's progress_callback. The callback MUST be integrated into JobRunner._run_job and capture job_id from the closure. Each event MUST include job_id, monotonically increasing seq number, phase, step_name, message, percent (nullable float), and timestamp. The callback MUST NOT abort the pipeline if event persistence fails — errors MUST be logged and isolated.

#### Scenario: worker writes step events

- GIVEN a running job executing a pipeline with multiple steps
- WHEN the pipeline emits ProgressEvent objects via the callback
- THEN each event is inserted into job_events with the correct job_id
- AND seq values increment monotonically (1, 2, 3, ...)
- AND phase, step_name, message, percent, timestamp match the ProgressEvent fields

#### Scenario: callback failure does not abort pipeline

- GIVEN a running job with progress_callback configured
- WHEN the job_events INSERT operation fails (database locked, I/O error)
- THEN the callback logs the error but does NOT raise
- AND the pipeline continues executing normally
- AND subsequent callbacks are still attempted

#### Scenario: callback captures job_id correctly

- GIVEN a worker process running multiple jobs sequentially
- WHEN progress_callback is invoked for a job
- THEN the callback uses the correct job_id from the closure
- AND events are written to the correct job_events row per job

### Requirement: SSE Endpoint for Live Progress

The system MUST expose GET /jobs/{job_id}/progress as a Server-Sent Events endpoint returning text/event-stream via StreamingResponse. The endpoint MUST accept an optional last_seq query parameter to resume from a specific sequence number. MUST stream events WHERE job_id = ? AND seq > ? ORDER BY seq ASC. MUST return 404 for unknown job_id. MUST send a terminal event and close the stream when job reaches success/failed/aborted status.

#### Scenario: stream events for running job

- GIVEN a job with status running and existing job_events records
- WHEN GET /jobs/{job_id}/progress is called with EventSource client
- THEN the endpoint returns text/event-stream content-type
- AND events are streamed as data: {json} lines with event: progress type
- AND each event includes id (seq), event (progress type), data (JSON with phase, step_name, message, percent, timestamp)
- AND the connection remains open waiting for new events

#### Scenario: job already finished at connect time

- GIVEN a job with status success and existing job_events records
- WHEN GET /jobs/{job_id}/progress is called
- THEN the endpoint replays all existing events in seq order
- AND sends a terminal event with event: complete type and data: {status: success}
- AND closes the stream (no keep-alive)
- AND the client receives complete job history immediately

#### Scenario: unknown job returns 404

- GIVEN a request with job_id that does not exist in the jobs table
- WHEN GET /jobs/{unknown_id}/progress is called
- THEN HTTP 404 is returned with error message
- AND no SSE stream is initiated

#### Scenario: last_seq parameter filters events

- GIVEN a job with 10 job_events records (seq 1-10)
- WHEN GET /jobs/{job_id}/progress?last_seq=5 is called
- THEN only events with seq > 5 are streamed (6, 7, 8, 9, 10)
- AND earlier events (1-5) are not sent

#### Scenario: terminal event sent on job completion

- GIVEN a job with status running and active SSE connection
- WHEN the job completes and status changes to success
- THEN a final event is sent with event: complete type
- AND the event data includes {status: success, final_message: "..."}
- AND the endpoint closes the stream (ends SSE response)

#### Scenario: terminal event sent on job failure

- GIVEN a job with status running and active SSE connection
- WHEN the job fails and status changes to failed
- THEN a final event is sent with event: error type
- AND the event data includes {status: failed, error_message: "..."}
- AND the endpoint closes the stream

### Requirement: UI Integration with EventSource

The system MUST integrate EventSource into job_detail.html to render live progress events. MUST open EventSource to /jobs/{job_id}/progress on page load. MUST append incoming progress events to a visible timeline or log area. MUST close EventSource on terminal event. MUST gracefully fallback if EventSource is unsupported.

#### Scenario: EventSource connects and renders events

- GIVEN a user viewing job detail page for a running job
- WHEN the page loads and EventSource connects
- AND progress events are received
- THEN each event is appended to a progress timeline visible on the page
- AND events render with step name, phase (start/complete/error), and message
- AND the timeline updates without full page refresh

#### Scenario: EventSource closes on terminal event

- GIVEN a user viewing job detail page with active EventSource
- WHEN a terminal event (complete/error) is received
- THEN the EventSource closes automatically
- AND a final status message is displayed
- AND no reconnection attempts are made

#### Scenario: EventSource unsupported falls back gracefully

- GIVEN a browser without EventSource support
- WHEN the job detail page loads
- THEN a fallback message is displayed
- AND no JavaScript errors occur
- AND existing HTMX auto-refresh continues working

#### Scenario: EventSource connection error handled

- GIVEN a user viewing job detail page
- WHEN the EventSource connection fails (network error, 500 error)
- THEN the error is logged to console
- AND a visible error message appears
- AND the page does not break or freeze

#### Scenario: progress timeline renders step phases

- GIVEN a running job emitting events for steps: etl, split, training
- WHEN events arrive via EventSource
- THEN the timeline renders phases in order: etl (start) → etl (complete) → split (start) → split (complete) → training (start) → training (complete)
- AND each phase shows status badge (queued/running/complete/error)
- AND step names are clickable or highlighted

### Requirement: Schema Migration for Percent Column

The system MUST modify job_events.percent column from INTEGER to REAL (nullable). Existing data must be preserved (empty table in production). The schema change MUST support storing float values from ProgressEvent.percent. Backward compatibility MUST be maintained for existing deployments.

#### Scenario: percent column stores float values

- GIVEN a ProgressEvent with percent: 75.5 (float)
- WHEN the event is persisted to job_events
- THEN the percent column stores 75.5 as REAL
- AND querying returns the exact float value (not truncated to integer)

#### Scenario: percent column stores null

- GIVEN a ProgressEvent with percent: None (not set)
- WHEN the event is persisted to job_events
- THEN the percent column stores NULL
- AND querying returns NULL (not 0)

#### Scenario: coarse progress stored as 0 or 100

- GIVEN a ProgressEvent for step start with percent: None
- WHEN the event is persisted for coarse-grained progress
- THEN percent is stored as NULL (not forced to 0)
- AND UI renders step as "in progress" (no percentage)

#### Scenario: schema migration preserves existing data

- GIVEN an existing deployment with job_events table (empty)
- WHEN the ALTER TABLE percent INTEGER → REAL runs
- THEN the schema change succeeds
- AND existing rows (none) are preserved
- AND the column accepts NULL values

### Requirement: SSE Event Format Contract

The SSE endpoint MUST emit events in a consistent JSON format. Each event MUST include id (seq), event (progress/complete/error), and data (JSON object with phase, step_name, message, percent, timestamp). Event names MUST distinguish between progress events and terminal events.

#### Scenario: SSE event format matches contract

- GIVEN a job_events record with seq=1, phase="start", step_name="etl", message="Processing ETL", percent=0.0, timestamp="2025-01-01T12:00:00Z"
- WHEN the SSE endpoint streams this event
- THEN the output format is: id: 1\nevent: progress\ndata: {"phase": "start", "step_name": "etl", "message": "Processing ETL", "percent": 0.0, "timestamp": "2025-01-01T12:00:00Z"}\n\n

#### Scenario: terminal event format matches contract

- GIVEN a job completing with status success
- WHEN the SSE endpoint sends the terminal event
- THEN the output format is: id: {final_seq}\nevent: complete\ndata: {"status": "success", "message": "..."}\n\n

#### Scenario: event names distinguish progress vs terminal

- GIVEN a client receiving mixed events from SSE stream
- WHEN events arrive
- THEN progress events have event: progress
- AND completion events have event: complete
- AND error events have event: error
- AND client can switch handling logic based on event name

### Requirement: Seq Ordering Guarantee

The system MUST guarantee that events are streamed in strict seq order (monotonically ascending). The SSE endpoint MUST query ORDER BY seq ASC and rely on the job_events table index (job_id, seq) for efficient retrieval. Clients MUST receive events in the same order they were generated.

#### Scenario: events streamed in seq order

- GIVEN a job with job_events records at seq=1, 2, 3, 4, 5
- WHEN GET /jobs/{job_id}/progress is called
- THEN events are streamed in order: seq 1 → 2 → 3 → 4 → 5
- AND no event is skipped or reordered

#### Scenario: concurrent writes do not affect ordering

- GIVEN a running job writing events via progress_callback
- AND a web client reading via SSE endpoint simultaneously
- WHEN new events are inserted during an active SSE stream
- THEN the reader sees events in seq order (1, 2, 3, ...)
- AND no race condition causes out-of-order delivery

### Requirement: Concurrent Read-Write Isolation

The system MUST support concurrent reads (web SSE endpoint) and writes (worker progress_callback) on the job_events table. SQLite WAL mode MUST be enabled to allow non-blocking reads. The single writer (worker) and multiple readers (web clients) MUST operate without locks or deadlocks.

#### Scenario: worker writes while web reads

- GIVEN a running job with active SSE connections from multiple web clients
- WHEN the worker inserts a new job_events record
- THEN all active SSE connections receive the new event
- AND no database lock or deadlock occurs
- AND reads do not block writes

#### Scenario: multiple SSE clients read concurrently

- GIVEN a running job with 3 web clients connected to SSE endpoint
- WHEN new events are inserted by the worker
- THEN all 3 clients receive events in seq order
- AND no client blocks another (concurrent reads supported)

### Requirement: Coarse Progress Only Contract

The system MUST emit progress events ONLY for step boundaries (start, complete, error). Fine-grained percentage progress (e.g., "training iteration 450 of 1000") is OUT OF SCOPE for Phase 5. Events MUST have percent=NULL or coarse values (0 for start, 100 for complete).

#### Scenario: step start event has no percentage

- GIVEN a pipeline step starting execution
- WHEN ProgressEvent is emitted for phase="start"
- THEN percent is NULL (not forced to 0)
- AND UI shows "Step started" without percentage bar

#### Scenario: step complete event has coarse percentage

- GIVEN a pipeline step completing execution
- WHEN ProgressEvent is emitted for phase="complete"
- THEN percent is 100.0 (or NULL)
- AND UI shows "Step complete" with success indication

#### Scenario: step error event has no percentage

- GIVEN a pipeline step failing with error
- WHEN ProgressEvent is emitted for phase="error"
- THEN percent is NULL (error state)
- AND UI shows "Step failed" with error message

### Requirement: No Event Retention/Cleanup in Phase 5

The system MUST NOT implement event retention or cleanup logic in Phase 5. The job_events table MAY grow unbounded. Cleanup strategy (DELETE old events) is deferred to follow-up work. This is documented as technical debt.

#### Scenario: job_events table grows unbounded

- GIVEN a system running 1000 jobs over time
- WHEN each job writes 20 events to job_events
- THEN the table accumulates 20,000 rows
- AND no automatic cleanup or TTL is performed
- AND disk space grows linearly with job count

#### Scenario: old events remain queryable

- GIVEN a job completed 6 months ago with job_events records
- WHEN GET /jobs/{old_job_id}/progress is called
- THEN old events are still returned
- AND no retention policy deletes or archives them

### Requirement: No SSE Reconnect in Phase 5

The system MUST NOT implement automatic SSE reconnection via Last-Event-ID in Phase 5. If the SSE connection drops, the user MUST manually refresh the page. Reconnection logic is deferred to follow-up work.

#### Scenario: connection drop requires manual refresh

- GIVEN a user viewing job detail page with active SSE connection
- WHEN the network connection drops temporarily
- THEN the EventSource closes (error event fired)
- AND no automatic reconnection is attempted
- AND the user must manually refresh the page to resume

#### Scenario: Last-Event-ID not honored

- GIVEN a client attempting to reconnect with Last-Event-ID header
- WHEN the reconnection request hits GET /jobs/{job_id}/progress
- THEN the Last-Event-ID header is ignored
- AND the endpoint starts from seq 0 (replays all events)

## Non-goals

Fine-grained % progress within steps · SSE auto-reconnect via Last-Event-ID · Event retention/cleanup TTL · Authentication/authorization for SSE · Multi-tenancy isolation · Progress history pagination
