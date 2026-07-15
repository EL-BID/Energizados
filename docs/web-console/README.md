# Energizados Web Console

The Energizados Web Console provides a browser-based interface for operating the ML framework without using the command line. It consists of two main components:

1. **Web Server** (FastAPI + HTMX) - Serves HTTP requests and UI
2. **Worker Process** - Executes async jobs via ConfigPipelineBuilder

## Quick Start

```bash
# Install dependencies
pip install -e ".[web]"

# Start both processes with the launcher
energizados-web --host 127.0.0.1 --port 8000 --db-path data/web/jobs.db

# Or start manually:
# Terminal 1: Web server
uvicorn energizados.web.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Worker
energizados-web-worker --db-path data/web/jobs.db --log-level INFO
```

Access the web console at http://localhost:8000

## Features

### 1. Job Management

The web console provides async job execution for ETL, training, and inference pipelines:

- **Submit Jobs**: Upload YAML configs via the web interface
- **Monitor Progress**: Real-time job status updates (QUEUED, RUNNING, SUCCESS, FAILED, ABORTED)
- **View Results**: Access job results and logs
- **Cancel Jobs**: Stop running jobs
- **Retry Failed Jobs**: Re-run failed jobs with one click

### 2. Runs Browsing (Phase 2)

Browse completed pipeline runs with comprehensive detail views:

#### List Runs (`GET /runs`)

View a paginated list of completed training runs with filtering options:

- **Status Filter**: Filter runs by status (success, partial, failed)
- **Limit Control**: Specify the maximum number of runs to display
- **Run Metadata**: View run_id, timestamp, duration, model types, validation metrics
- **Navigation**: Click through to detailed run views

**Example**:
```bash
curl http://localhost:8000/runs?status=success&limit=50
```

**Query Parameters**:
- `status` (optional): Filter by status - `success`, `partial`, `failed`
- `limit` (optional): Maximum runs to return (default: 100)

#### Run Detail (`GET /runs/{run_id}`)

Access comprehensive run metadata and artifacts:

- **Metrics Dashboard**: View evaluation metrics (AUC, F1, precision, recall)
- **Model Rankings**: For ensemble runs, see model comparison tables
- **Plot Gallery**: Access generated plots (ROC curves, confusion matrices, etc.)
- **Configuration**: View the exact YAML configs used in the run
- **Run Logs**: Inspect execution logs
- **EDA Reports**: Embed exploratory data analysis reports when available

**Example**:
```bash
curl http://localhost:8000/runs/train-20240101_120000
```

**Artifact Access**: All run artifacts are accessible via the artifact route:
```
GET /runs/{run_id}/artifacts/{path:path}
```

Examples:
- `GET /runs/train-20240101_120000/artifacts/reports/evaluation/roc_curve.png`
- `GET /runs/train-20240101_120000/artifacts/config/train.yaml`
- `GET /runs/train-20240101_120000/artifacts/run.log`

#### Job→Run Navigation

From job detail pages, navigate directly to corresponding run detail pages when `job.run_id` is populated. This provides a seamless workflow from job execution to run inspection.

### 3. Configuration Editor

Edit YAML configuration files directly in the browser with:

- **Syntax Highlighting**: Easy-to-read YAML formatting
- **Validation**: Real-time validation feedback before submission
- **File Upload**: Upload existing YAML files
- **Template Support**: Built-in config templates

### 4. Live Updates

The interface uses HTMX for dynamic updates without page refreshes:

- **Auto-refresh**: Job lists update every 2 seconds
- **Real-time Status**: See job progress as it happens
- **Smooth UX**: No jarring page reloads
- **Live progress via SSE**: per-job Server-Sent Events (`GET /jobs/{job_id}/progress` and the project-scoped equivalent) push step-by-step progress to the job detail page in real time

### 5. Multi-Project Workspace

The console is a multi-project workspace rather than a single-project runner:

- **Projects home page** (`GET /projects`): list, create, and register projects. Each project owns its own jobs and runs.
- **Project-scoped jobs**: create and manage jobs under `POST /projects/{project_id}/jobs`. Global job creation (`POST /jobs`) is deprecated and returns HTTP 400.
- **Project detail page** (`GET /projects/{project_id}`): shows that project's runs, dashboards, and lineage.
- **Project-scoped dashboards and comparisons**: `GET /projects/{project_id}/dashboard` and `GET /projects/{project_id}/runs/compare`.
- **Global cross-project surfaces** still exist: `GET /dashboard` and `GET /runs`.

### 6. Run Grouping & Lineage

- **run_type grouping**: the runs list (`GET /runs`) and the project detail page bucket runs by type — `etl`, `eda`, `inference`, and `training` — so each pipeline stage is easy to find.
- **Retrain lineage**: when a run is produced by retrying or retraining from a previous run, the source run id is tracked (`derived_from_run_id`) and surfaced on the project detail page, making it easy to follow how a model evolved.

### 7. UI Style Guide

- **`GET /ui`**: a living style-guide page documenting the console's reusable UI components. It auto-adapts to the active light/dark theme via the global topbar toggle.

## Architecture

```
┌─────────────┐         HTMX/SSE         ┌──────────────────┐
│  Browser    │ ←───────────────────────→ │  FastAPI + Jinja2│
│  (HTMX)     │                            │  (capa fina)     │
└─────────────┘                            └────────┬─────────┘
                                                     │ energizados.api
                                                     ▼
                                            ┌──────────────────┐
                                            │  Job Runner      │  ← worker + cola
                                            │  (proceso aparte)│
                                            └────────┬─────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │  output/<run>/   │  ← run_metadata.json,
                                            │  (persistencia)  │     reports/, eda HTML
                                            └──────────────────┘
```

## API Endpoints

### Jobs

- `POST /projects/{project_id}/jobs` - Submit a new job scoped to a project (canonical route)
- `GET /projects/{project_id}/jobs` - List jobs for a project
- `GET /projects/{project_id}/jobs/{job_id}` - Project-scoped job detail
- `POST /projects/{project_id}/jobs/{job_id}/cancel` - Cancel a project job
- `POST /projects/{project_id}/jobs/{job_id}/retry` - Retry a failed project job
- `GET /projects/{project_id}/jobs/{job_id}/progress` - SSE stream of live progress for a project job
- `POST /jobs` - **Deprecated**. Global job creation is no longer supported and always returns HTTP 400. Use `POST /projects/{project_id}/jobs` instead. (Existing global jobs remain readable via the legacy `GET /jobs` endpoints below.)
- `GET /jobs` - List all jobs (legacy read-only surface across projects)
- `GET /jobs/{job_id}` - Get job detail
- `GET /jobs/{job_id}/progress` - SSE stream of live job progress events
- `POST /jobs/{job_id}/cancel` - Cancel a running job
- `POST /jobs/{job_id}/retry` - Retry a failed job

### Runs

- `GET /runs` - List completed runs (grouped by run_type: etl / eda / inference / training)
- `GET /runs/compare` - Side-by-side comparison page for multiple runs
- `GET /runs/{run_id}` - Get run detail with metrics and artifacts
- `GET /runs/{run_id}/artifacts/{path:path}` - Access run artifacts (plots, configs, logs)
- `GET /projects/{project_id}/runs` - List runs for a project (project detail page)
- `GET /projects/{project_id}/runs/compare` - Project-scoped run comparison page
- `GET /projects/{project_id}/runs/{run_id}` - Project-scoped run detail

### Projects & Navigation

- `GET /health` - Health check endpoint
- `GET /` - Main interface
- `GET /projects` - Projects home page (multi-project workspace)
- `GET /projects/{project_id}` - Project detail page (project-scoped runs, lineage, dashboard)
- `POST /projects` - Create a new project under the workspace
- `POST /projects/register` - Register an existing directory as a project
- `GET /dashboard` - Global metrics dashboard (timeline of recent runs across projects)
- `GET /projects/{project_id}/dashboard` - Project-scoped dashboard
- `GET /ui` - Living style-guide page (UI component reference)
- `GET /docs` - FastAPI auto-documentation

## Security Considerations

### Important: Phase 1 Authentication

The web console has **NO authentication or authorization** in Phase 1. All endpoints are publicly accessible. This is a documented security assumption.

**Required Security Measures for Production:**

1. **Network Isolation** - Deploy behind a firewall restricting access to trusted networks
2. **Reverse Proxy Auth** - Use authentication at the reverse proxy level (Nginx basic auth, OAuth2)
3. **VPN Requirement** - Require VPN connection for access
4. **Internal Network Only** - Deploy on internal network with no external access

### Artifact Security

The artifact serving route includes comprehensive path-traversal guards:

- **Run Validation**: Validates run_id via RunManager before serving any files
- **Traversal Blocking**: Rejects paths with `..` segments, absolute paths, and backslashes
- **Double-Check Validation**: Resolved paths must be within the run directory
- **Symbolic Link Protection**: Guards against symlink escapes

### Custom Class Validation

The framework includes two-layer security validation:

1. **Web Layer**: Validates custom_class prefixes against ALLOWED_PREFIXES during job submission
2. **Worker Layer**: Re-validates prefixes before imports

**Allowed Prefixes**: `energizados.*`, `src.*`

## Deployment

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

Quick deployment options:

### Development
```bash
energizados-web --host 127.0.0.1 --port 8000 --db-path data/web/jobs.db
```

### Docker Compose
```bash
cd deploy/web
docker compose up --build
```

### systemd (Production)
```bash
sudo systemctl enable energizados-web energizados-worker
sudo systemctl start energizados-web energizados-worker
```

## Development

### Running Tests

```bash
# Run all web tests
pytest tests/web/

# Run specific test file
pytest tests/web/test_app.py -v

# Run with coverage
pytest tests/web/ --cov=src/energizados/web

# Run slow tests (integration tests with real processes)
pytest tests/web/ -m slow
```

### Code Quality

```bash
# Run pre-commit hooks
pre-commit run --all-files

# Manually run linters
isort src/energizados/web/
black src/energizados/web/
flake8 src/energizados/web/
bandit -r src/energizados/web/
```

### Project Structure

```
src/energizados/web/
├── app.py              # FastAPI application with all routes
├── store.py            # JobStore for SQLite persistence
├── runner.py           # JobRunner worker execution engine
├── worker.py           # Worker CLI entrypoint
├── models.py           # JobStatus enum and JobRow dataclass
├── templates/          # Jinja2 templates for UI
│   ├── base.html       # Base layout with HTMX CDN
│   ├── index.html      # Main page with YAML editor
│   ├── job_list.html   # HTMX fragment for job list
│   ├── job_detail.html # HTMX fragment for job details
│   ├── runs_list.html  # Runs list page (Phase 2)
│   ├── run_detail.html # Run detail page (Phase 2)
│   └── components/     # Reusable template components
└── static/             # Static assets (CSS, JS)

tests/web/
├── test_app.py         # Tests for all FastAPI routes
├── test_helpers.py     # Tests for template helper functions
├── test_integration_runs.py  # Integration tests for runs browsing
└── test_integration_flow.py # Integration tests for job execution
```

## Troubleshooting

### Common Issues

1. **Worker not processing jobs**: Check worker logs and verify database permissions
2. **Web UI not loading**: Ensure port 8000 is available and check firewall rules
3. **Jobs stuck in QUEUED**: Verify worker is running and can access database
4. **Database corruption**: Backup current database and run integrity check

### Logs Locations

- **Web Server**: stdout/stderr (captured by systemd/supervisor/Docker)
- **Worker**: stdout/stderr (captured by systemd/supervisor/Docker)
- **Job Logs**: `output/<run_id>/run.log`

### Health Checks

```bash
# Check web server health
curl http://localhost:8000/health

# Check worker process
ps aux | grep energizados-web-worker

# Check job queue
sqlite3 data/web/jobs.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```

## Additional Resources

- **Framework Documentation**: See main CLAUDE.md and README.md
- **Design Docs**: `openspec/changes/web-console/design.md`
- **Deployment Guide**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **API Documentation**: Run with `--reload` and visit http://localhost:8000/docs
- **Issue Tracker**: Report bugs via project issue tracker

## Version History

- **Phase 1**: Async job runner with SQLite persistence
- **Phase 2**: Runs browsing and artifact serving
- **Phase 3**: Multi-project workspace with project-scoped jobs, run_type grouping on `/runs`, retrain lineage (`derived_from_run_id`), global + project-scoped dashboards, run comparison pages, SSE live progress, and the `/ui` style guide (current)
- **Future**: Authentication, RBAC
