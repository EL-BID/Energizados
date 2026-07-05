# web-job-runner Specification

> Capability: `web-job-runner` — SQLite-backed async engine running `energizados`
> pipelines via `ConfigPipelineBuilder.run()` in a child process: FIFO queue,
> concurrency=1, durable lifecycle, zero new infra. Framework-agnostic. Phase 1
> reserves the `job_events` schema but does NOT populate it. SQLite state is the
> single source of truth (the framework lacks async execution today).

## Requirements

### Requirement: Jobs Table — Single Source of Truth

Persist all job state in a SQLite `jobs` table. Columns: `job_id` (server PK),
`config` (JSON), `config_type`, `status`, `enqueued_at`, `started_at`, `finished_at`,
`run_id` (null), `run_dir` (null), `error` (null JSON), `retried_from` (null self-FK).
No job state lives only in memory.

#### Scenario: row survives process kill

- GIVEN a `queued` job row
- WHEN the worker is killed and restarted
- THEN `SELECT * FROM jobs WHERE job_id=?` returns the row unchanged

### Requirement: Lifecycle States and Transitions

Exactly one state per job: `queued | running | success | failed | aborted`. Legal
transitions: `queued→running`; `running→success|failed|aborted`. Any other is rejected.

#### Scenario: illegal transition rejected

- GIVEN a job terminal in `success`
- WHEN asked to move it to `running`
- THEN the request is rejected and the row stays `success`

### Requirement: Concurrency=1 FIFO Ordering

Execute at most one job at a time, picking the oldest `queued` row
(`ORDER BY enqueued_at`).

#### Scenario: second job waits

- GIVEN job A is `running` and job B is INSERTed `queued`
- WHEN A reaches a terminal state
- THEN B is picked only after A is terminal

### Requirement: Enqueue Validates Before Insert

Call `energizados.api.validate_dict(config, config_type)`; never insert on validation
failure — return the errors instead.

#### Scenario: invalid config rejected

- GIVEN a config missing a required field
- WHEN enqueue is called
- THEN no row is inserted and `ValidationResult.errors` are returned

### Requirement: Execute via ConfigPipelineBuilder in a Child Process

Spawn a child process invoking `ConfigPipelineBuilder(config=<merged dict>).run()`. The
worker SHALL surface progress events from the running job AND persist
`run_metadata.json` (visible via `RunManager.get_run(run_id)`). Success → `success` with
`run_id`/`run_dir`; exception → `failed` with `error = format_error(exc)`.

#### Scenario: success writes metadata

- GIVEN a `queued` job with a valid stub config
- WHEN the worker executes it
- THEN `jobs.run_id` is set and `RunManager.get_run(run_id)` returns a `RunMetadata`

#### Scenario: framework exception → failed

- GIVEN a job whose child raises `ConfigurationError`
- WHEN the worker catches it
- THEN status is `failed`, `error` holds the `format_error` JSON, exception type preserved

### Requirement: Cancel Is Non-Destructive

Cancel of a `running` job terminates the child and sets `aborted`. The partial run dir
is preserved (deletion is a separate purge). Cancel of a non-running job is a no-op.

#### Scenario: partial output preserved

- GIVEN a `running` job with a partially written run dir
- WHEN cancel is invoked
- THEN the child is terminated, status is `aborted`, run dir still exists

### Requirement: Retry Creates a New Job

Create a NEW `job_id` (`queued`) with `retried_from = <original>`. The original row is
not mutated.

#### Scenario: child links to parent

- GIVEN a `failed` job P
- WHEN retry is invoked on P
- THEN a new `queued` row has `retried_from = P.job_id`, and P is unchanged

### Requirement: Worker Restart Reconciliation

On startup, atomically set every `running` job to `failed` with
`error = "worker restarted"`; leave `queued` rows untouched. Idempotent.

#### Scenario: orphaned running job reconciled

- GIVEN a job is `running` when the worker restarts
- WHEN the worker starts up
- THEN the row becomes `failed` ("worker restarted"); re-running is a no-op

### Requirement: Retention Purge

Delete terminal jobs whose `finished_at` is older than a cutoff. Idempotent.

#### Scenario: only old terminal jobs deleted

- GIVEN terminal jobs older than cutoff C and one newer terminal job
- WHEN `purge(C)` runs
- THEN only old rows are deleted; `purge(C)` again is a no-op

### Requirement: `custom_class` Prefix Security (Worker)

Before running any job, call `register_allowed_prefix()` for each configured workspace
prefix. Security-critical; complements (not replaces) the web submit check.

#### Scenario: prefix registered before import

- GIVEN a job config with `custom_class: "data.my.CustomETL"`
- WHEN the worker prepares to run it
- THEN `register_allowed_prefix("data")` was called before the child imports the class

### Requirement: `job_events` Schema Reserved (Phase 1)

Create a `job_events` table at schema creation: `id` (PK), `job_id` (FK→jobs), `seq`
(per-job monotonic), `phase` (`start|progress|complete|error`), `step_name`, `message`,
`percent`, `timestamp` (UTC ISO). Phase 1 MUST NOT populate it; population + SSE consumer
deferred to Phase 5.

#### Scenario: table exists but stays empty

- GIVEN a freshly created jobs database
- WHEN a job runs to terminal
- THEN `SELECT COUNT(*) FROM job_events WHERE job_id=?` returns `0`

### Requirement: Independent Worker Entrypoint

A worker entrypoint exists and is runnable independently of the web process (shape —
CLI vs `python -m` — is a design decision).

#### Scenario: worker runs with no web process

- GIVEN a `queued` job in the database
- WHEN the worker is started with no web process running
- THEN it executes the job to a terminal state

## Non-goals

Concurrency >1 · cooperative (intra-step) cancel · real-time SSE in Phase 1 ·
`job_events` population · Redis/extra infra · multi-tenant isolation.
