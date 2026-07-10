# Proposal: web-console Phase 5 — Live Progress via SSE

## Intent

Add Server-Sent Events (SSE) live progress to the web console so operators can watch a running job's pipeline progress in real-time instead of waiting for HTMX auto-refresh every 2 seconds. Eliminate the "is it stuck?" uncertainty for long-running training jobs.

## Scope

### In Scope (MVP-minimal)
- **Worker event persistence**: Implement `progress_callback` in `JobRunner` to write `ProgressEvent` records to `job_events` table (SQLite, WAL mode)
- **SSE endpoint**: `GET /jobs/{job_id}/events` returns `text/event-stream` via `StreamingResponse`, tails `job_events WHERE seq > last_seq`
- **UI integration**: Add `EventSource` to `job_detail.html` that renders step timeline with real-time status badges
- **Schema fix**: Change `job_events.percent` from `INTEGER` to `REAL` (nullable) — store coarse 0/100 or null
- **Use job_id**: Callback captures `job_id` from `_run_job` closure (available at callback time, unlike `run_id`)

### Out of Scope
- SSE reconnect via `Last-Event-ID` (Phase 5+)
- Event retention/cleanup strategy (documented as debt)
- Fine-grained `%` within steps (coarse step start/complete/error only)
- Authentication/authorization (still trusted deployment)

## Capabilities

### New Capabilities
None (extends existing `web-console` capability)

### Modified Capabilities
- `web-console`: Add SSE live progress events to job detail view

## Approach

**Option A — Persist + Tail (recommended)**:
1. Worker's `progress_callback` inserts into `job_events` (already exists, schema: `id, job_id, seq, phase, step_name, message, percent, timestamp`)
2. Web app SSE endpoint queries `WHERE job_id = ? AND seq > ? ORDER BY seq` (indexed via `idx_job_events_job_seq`)
3. UI opens `EventSource` on job detail, renders step timeline with status badges (queued→running→complete/failed)

**Why Option A**: SQLite WAL allows concurrent reads (web) + single writer (worker). No new deps. Minimal code. Works across process boundary.

**Rejected options**: B (in-process execution breaks async), C (pub/sub adds infra complexity).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/web/runner.py` | Modified | Implement `progress_callback` to insert into `job_events` |
| `src/energizados/web/store.py` | Modified | Add `insert_event()`, `get_events_since(job_id, seq)` methods |
| `src/energizados/web/app.py` | Modified | Add `GET /jobs/{job_id}/events` SSE endpoint |
| `src/energizados/web/templates/job_detail.html` | Modified | Add `EventSource` client + step timeline rendering |
| `job_events` schema | Modified | Change `percent INTEGER` → `percent REAL` (nullable) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `job_events` unbounded growth | High | Punt as documented debt; cleanup in follow-up |
| SSE connection drops on network | Medium | Manual page refresh fallback; auto-reconnect in Phase 5+ |
| Percent type mismatch (float vs int) | Low | Schema fix to REAL, store 0/100 coarse or null |
| SQLite write contention | Low | WAL mode, single writer (worker), reads (web) are concurrent |

## Rollback Plan

If SSE breaks:
1. Revert `progress_callback` to no-op (`pass`)
2. Remove SSE endpoint
3. Revert `job_detail.html` to HTMX auto-refresh only
4. `job_events` table stays empty (harmless)

## Dependencies

- None (Starlette `StreamingResponse` already available via FastAPI)

## Success Criteria

- Worker writes step start/complete/error events to `job_events`
- SSE endpoint streams new events as they arrive
- Job detail page shows real-time step timeline without page refresh
- Existing HTMX fallback still works if SSE fails

## Known Issues — Resolutions

1. **run_id unknown at callback time**: Use `job_id` instead (available in `_run_job` closure). `job_events` already keyed by `job_id`.

2. **percent type mismatch**: Change schema to `REAL` (nullable). Store coarse 0/100 or null for MVP. Fine-grained % deferred.

3. **Event retention**: Punt as documented debt. No TTL in Phase 5. Follow-up will add `DELETE FROM job_events WHERE created_at < ?` via worker cleanup task.

4. **Fine-grained %**: Coarse step progress only (start/complete/error). Phase 5+ can wire `TrainingStep` iteration progress if needed.
