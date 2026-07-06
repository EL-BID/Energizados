# Energizados Web Console

Async job runner and web interface for the Energizados ML framework.

## Overview

The web console provides a browser-based interface for submitting and monitoring Energizados pipeline runs. It consists of two separate processes:

- **Web Server**: FastAPI application with HTMX-powered UI
- **Worker**: Background process that executes jobs via `ConfigPipelineBuilder`

## Quick Start

### Installation

```bash
# Install with web dependencies
pip install -e ".[web]"
```

### Development Mode

```bash
# Terminal 1: Start web server
uvicorn energizados.web.app:app --reload

# Terminal 2: Start worker
energizados-web-worker --db-path data/web/jobs.db
```

Access the web console at http://localhost:8000

## Features

### Current Features (Phase 1)

- **Job Submission**: Submit ETL/train/EDA/inference configs via web interface
- **Job Monitoring**: Real-time status updates with auto-refresh
- **Job Management**: Cancel running jobs, retry failed jobs
- **Validation**: Real-time configuration validation with error feedback
- **Security**: Two-layer `custom_class` prefix validation

### Architecture

```
┌─────────────┐         ┌──────────────┐         ┌──────────────┐
│   Browser   │ ──────▶ │  Web Server  │ ──────▶ │  SQLite DB   │
│  (HTMX UI)  │         │  (FastAPI)   │         │  (jobs.db)   │
└─────────────┘         └──────────────┘         └──────────────┘
                                │                         ▲
                                │                         │
                                └─────────────────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   Worker     │
                              │  Process     │
                              └──────────────┘
```

## Usage

### Web Interface

1. Open http://localhost:8000
2. Paste YAML configuration or upload file
3. Click "Submit Job"
4. Monitor job status in real-time
5. Cancel/retry jobs as needed

### CLI Usage

#### Worker Process

```bash
# Start worker with default settings
energizados-web-worker

# Custom database path
energizados-web-worker --db-path /custom/path/jobs.db

# Set log level
energizados-web-worker --log-level DEBUG

# Using Python module
python -m energizados.web.worker --db-path data/web/jobs.db
```

#### Web Server

```bash
# Development with auto-reload
uvicorn energizados.web.app:app --reload

# Production
uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000

# With multiple workers
uvicorn energizados.web.app:app --workers 4
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENERGIZADOS_WEB_DB_PATH` | SQLite database path | `data/web/jobs.db` |
| `ENERGIZADOS_WEB_LOG_LEVEL` | Logging verbosity | `INFO` |

### Job States

Jobs progress through these states:

- `QUEUED` → `RUNNING` → `SUCCESS` | `FAILED` | `ABORTED`

## API Endpoints

### Web Endpoints

- `GET /` - Main web interface
- `POST /jobs` - Submit new job (YAML/JSON)
- `GET /jobs` - List all jobs (HTMX fragment)
- `GET /jobs/{id}` - Get job details
- `POST /jobs/{id}/cancel` - Cancel running job
- `POST /jobs/{id}/retry` - Retry failed/aborted job
- `GET /health` - Health check
- `GET /api/runs` - List historical runs

### API Documentation

Interactive API documentation available at http://localhost:8000/docs (Swagger UI)

## Templates

The web interface uses Jinja2 templates with HTMX for dynamic updates:

- `base.html` - Main layout with HTMX CDN
- `index.html` - Main page with YAML editor
- `job_list.html` - Job list table (HTMX fragment)
- `job_detail.html` - Job details (HTMX fragment)
- `components/` - Reusable components

## Security

### ⚠️ Important: No Authentication in Phase 1

The web console currently has **no authentication or authorization**. All endpoints are publicly accessible.

**Required security measures:**
- Deploy behind network firewall
- Use reverse proxy with authentication (Nginx basic auth, OAuth2)
- Require VPN for access
- Internal network only deployment

### Custom Class Validation

Two-layer security validation prevents arbitrary code execution:

1. **Web Layer**: Validates `custom_class` prefixes on submission
2. **Worker Layer**: Re-validates before import

**Allowed prefixes**: `energizados.*`, `src.*`

## Deployment

For production deployment, see the full deployment guide:

```bash
# View deployment documentation
cat docs/web-console/DEPLOYMENT.md
```

Key deployment options:
- **systemd** (recommended): Native service management
- **Docker Compose**: Containerized deployment
- **Supervisor**: Process management

## Troubleshooting

### Worker Not Processing Jobs

```bash
# Check worker status
ps aux | grep energizados-web-worker

# Check worker logs
journalctl -u energizados-worker -f  # if using systemd
tail -f /var/log/energizados-worker.log  # if using supervisor

# Verify database access
ls -la data/web/jobs.db
```

### Web UI Issues

```bash
# Check web server logs
journalctl -u energizados-web -f

# Verify port availability
netstat -tlnp | grep 8000

# Test web server
curl http://localhost:8000/health
```

### Database Issues

```bash
# Check database integrity
sqlite3 data/web/jobs.db "PRAGMA integrity_check;"

# Backup database
cp data/web/jobs.db data/web/jobs.db.backup

# View job queue
sqlite3 data/web/jobs.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```

## Development

### Running Tests

```bash
# Run all web tests
pytest tests/web/

# Run specific test file
pytest tests/web/test_app.py

# Run integration tests
pytest tests/web/test_integration.py

# Run slow tests (real pipeline execution)
pytest tests/web/ -m slow
```

### Code Structure

```
src/energizados/web/
├── app.py          # FastAPI web application
├── store.py        # JobStore (SQLite persistence)
├── runner.py       # JobRunner (worker execution engine)
├── worker.py       # Worker CLI entrypoint
├── models.py       # JobStatus enum, JobRow dataclass
├── templates/      # Jinja2 templates
└── static/         # Static assets
```

### Adding New Features

1. **New Route**: Add to `app.py`, write tests in `tests/web/test_app.py`
2. **Template**: Add to `templates/`, follow HTMX patterns
3. **Worker Feature**: Add to `runner.py` or `store.py`
4. **Tests**: Follow TDD approach (write failing test first)

## Air-Gapped Deployment

For environments without internet access, download HTMX manually:

```bash
# Download HTMX
curl -o src/energizados/web/static/htmx.min.js https://unpkg.com/htmx.org@1.9.10

# Update base.html template to use local file
# <script src="/static/htmx.min.js"></script>
```

## Performance

### Typical Resource Usage

- **Web Server**: 50-100 MB RAM, minimal CPU
- **Worker**: 100-500 MB RAM per job (varies by pipeline)
- **Database**: <10 MB for hundreds of jobs

### Scaling Notes

- **Single Worker**: FIFO queue with `concurrency=1`
- **Multiple Workers**: Not supported in Phase 1
- **Database**: SQLite efficient for thousands of jobs

## Future Enhancements

Planned for Phase 2+:

- **Authentication**: User accounts and RBAC
- **Real-time Updates**: SSE for live progress
- **Job Events**: Detailed progress tracking
- **Multi-Worker**: Redis-based job queue
- **Dashboards**: Analytics and reporting

## Support

- **Framework Docs**: See main project README.md
- **Design Docs**: `openspec/changes/web-console/design.md`
- **Issues**: Report via project issue tracker
- **API Docs**: http://localhost:8000/docs

## License

Part of the Energizados ML framework. See main project license file.
