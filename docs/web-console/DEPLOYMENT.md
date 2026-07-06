# Web Console Deployment Guide

This guide covers deployment options for the Energizados web console, which consists of two separate processes:

1. **Web Server** (FastAPI + HTMX) - Serves HTTP requests and UI
2. **Worker Process** - Executes async jobs via ConfigPipelineBuilder

## Architecture Overview

```
┌─────────────┐         ┌──────────────┐
│   Browser   │ ──────▶ │  Web Server  │
│  (HTMX UI)  │         │  (FastAPI)   │
└─────────────┘         └──────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │  SQLite DB    │
                        │ (jobs.db)     │
                        └───────────────┘
                                ▲
                                │
                        ┌───────────────┐
                        │   Worker      │
                        │  Process      │
                        └───────────────┘
```

## Development Setup

### Quick Start

```bash
# Install dependencies
pip install -e ".[web]"

# Terminal 1: Start web server
uvicorn energizados.web.app:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start worker
energizados-web-worker --db-path data/web/jobs.db --log-level INFO
```

Access the web console at http://localhost:8000

## Production Deployment

### Method 1: systemd (Recommended)

#### Web Server Service

Create `/etc/systemd/system/energizados-web.service`:

```ini
[Unit]
Description=Energizados Web Console
After=network.target

[Service]
Type=notify
NotifyAccess=all
User=energizados
Group=energizados
WorkingDirectory=/opt/energizados
Environment="PATH=/opt/energizados/venv/bin"
Environment="ENERGIZADOS_WEB_DB_PATH=/var/lib/energizados/jobs.db"
Environment="ENERGIZADOS_WEB_LOG_LEVEL=INFO"
ExecStart=/opt/energizados/venv/bin/uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Worker Service

Create `/etc/systemd/system/energizados-worker.service`:

```ini
[Unit]
Description=Energizados Job Worker
After=network.target

[Service]
Type=simple
User=energizados
Group=energizados
WorkingDirectory=/opt/energizados
Environment="PATH=/opt/energizados/venv/bin"
Environment="ENERGIZADOS_WEB_DB_PATH=/var/lib/energizados/jobs.db"
Environment="ENERGIZADOS_WEB_LOG_LEVEL=INFO"
ExecStart=/opt/energizados/venv/bin/energizados-web-worker --db-path /var/lib/energizados/jobs.db
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Enable and Start Services

```bash
# Create user and directories
sudo useradd -r -s /bin/false energizados
sudo mkdir -p /var/lib/energizados
sudo chown energizados:energizados /var/lib/energizados

# Enable services
sudo systemctl enable energizados-web energizados-worker

# Start services
sudo systemctl start energizados-web energizados-worker

# Check status
sudo systemctl status energizados-web energizados-worker
```

### Method 2: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  web:
    image: energizados:latest
    command: uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - ENERGIZADOS_WEB_DB_PATH=/app/data/web/jobs.db
      - ENERGIZADOS_WEB_LOG_LEVEL=INFO
    depends_on:
      - worker
    restart: unless-stopped

  worker:
    image: energizados:latest
    command: energizados-web-worker --db-path /app/data/web/jobs.db
    volumes:
      - ./data:/app/data
    environment:
      - ENERGIZADOS_WEB_DB_PATH=/app/data/web/jobs.db
      - ENERGIZADOS_WEB_LOG_LEVEL=INFO
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

### Method 3: Supervisor

Create `/etc/supervisor/conf.d/energizados-web.conf`:

```ini
[program:energizados-web]
command=/opt/energizados/venv/bin/uvicorn energizados.web.app:app --host 0.0.0.0 --port 8000
directory=/opt/energizados
user=energizados
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/energizados-web.log
environment=ENERGIZADOS_WEB_DB_PATH="/var/lib/energizados/jobs.db",ENERGIZADOS_WEB_LOG_LEVEL="INFO"
```

Create `/etc/supervisor/conf.d/energizados-worker.conf`:

```ini
[program:energizados-worker]
command=/opt/energizados/venv/bin/energizados-web-worker --db-path /var/lib/energizados/jobs.db
directory=/opt/energizados
user=energizados
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/energizados-worker.log
environment=ENERGIZADOS_WEB_DB_PATH="/var/lib/energizados/jobs.db",ENERGIZADOS_WEB_LOG_LEVEL="INFO"
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENERGIZADOS_WEB_DB_PATH` | Path to SQLite database | `data/web/jobs.db` |
| `ENERGIZADOS_WEB_LOG_LEVEL` | Logging verbosity | `INFO` |

## CLI Arguments

### Worker (`energizados-web-worker`)

| Argument | Description | Default |
|----------|-------------|---------|
| `--db-path` | Path to SQLite database | `data/web/jobs.db` |
| `--log-level` | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |

## Reverse Proxy Configuration

### Nginx Example

```nginx
server {
    listen 80;
    server_name energizados.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Apache Example

```apache
<VirtualHost *:80>
    ServerName energizados.example.com

    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    <Proxy *>
        Require all granted
    </Proxy>
</VirtualHost>
```

## Security Considerations

### ⚠️ Critical: Phase 1 Authentication Risk

**The web console has NO authentication or authorization in Phase 1.** All endpoints are publicly accessible. This is a documented security assumption that must be addressed in production deployments.

#### Required Security Measures

1. **Network Isolation** - Deploy behind a firewall that restricts access to trusted networks only
2. **Reverse Proxy Auth** - Use authentication at the reverse proxy level (e.g., Nginx basic auth, OAuth2)
3. **VPN Requirement** - Require VPN connection for access
4. **Internal Network Only** - Deploy on internal network with no external access

#### Future Enhancement

Authentication and RBAC are planned for Phase 2+. See the design documentation for details.

### Database Security

- **File Permissions**: Ensure `jobs.db` has restrictive permissions (`chmod 600`)
- **Backup**: Regular backups of `jobs.db` for job history and audit trail
- **Location**: Store database in non-web-accessible directory

### Custom Class Validation

The framework includes two-layer security validation:

1. **Web Layer**: Validates `custom_class` prefixes against `ALLOWED_PREFIXES` during job submission
2. **Worker Layer**: Re-validates prefixes and calls `register_allowed_prefix()` before imports

**Allowed Prefixes**: `energizados.*`, `src.*`

Custom classes outside these prefixes will be rejected.

## Monitoring and Logging

### Log Locations

- **Web Server**: stdout/stderr (captured by systemd/supervisor/Docker)
- **Worker**: stdout/stderr (captured by systemd/supervisor/Docker)
- **Job Logs**: `output/<run_id>/run.log` (written by framework)

### Health Checks

```bash
# Check web server health
curl http://localhost:8000/health

# Check worker process
ps aux | grep energizados-web-worker

# Check job queue
sqlite3 data/web/jobs.db "SELECT status, COUNT(*) FROM jobs GROUP BY status;"
```

### Monitoring Metrics

Key metrics to monitor:
- Job queue depth (QUEUED jobs)
- Worker utilization (RUNNING jobs)
- Failed job rate (FAILED / Total)
- Average job duration
- Database size

## Air-Gapped Deployment

### HTMX CDN Fallback

The web console uses HTMX from CDN by default. For air-gapped deployments:

1. **Download HTMX**:
   ```bash
   curl -o /path/to/static/htmx.min.js https://unpkg.com/htmx.org@1.9.10
   ```

2. **Update Template**:
   Edit `src/energizados/web/templates/base.html`:
   ```html
   <!-- Replace CDN link -->
   <!-- <script src="https://unpkg.com/htmx.org@1.9.10"></script> -->
   
   <!-- With local reference -->
   <script src="/static/htmx.min.js"></script>
   ```

3. **Serve Static Files**:
   Ensure static files are mounted correctly (already configured in `app.py`).

## Troubleshooting

### Common Issues

1. **Worker not processing jobs**:
   - Check worker logs: `journalctl -u energizados-worker -f`
   - Verify database path and permissions
   - Ensure worker process is running: `ps aux | grep energizados-web-worker`

2. **Web UI not loading**:
   - Check web server logs: `journalctl -u energizados-web -f`
   - Verify port 8000 is not already in use
   - Check firewall rules

3. **Jobs stuck in QUEUED**:
   - Verify worker is running and can access database
   - Check for database locking issues
   - Review worker logs for errors

4. **Database corruption**:
   - Backup current database: `cp data/web/jobs.db data/web/jobs.db.backup`
   - Run SQLite integrity check: `sqlite3 data/web/jobs.db "PRAGMA integrity_check;"`
   - Restore from backup if needed

## Maintenance

### Database Maintenance

```bash
# Backup database
cp data/web/jobs.db data/web/jobs.db.$(date +%Y%m%d).bak

# Clean old terminal jobs (older than 30 days)
python -c "
from energizados.web.store import JobStore
from datetime import datetime, timedelta
store = JobStore()
cutoff = datetime.now() - timedelta(days=30)
store.purge_old_jobs(cutoff_days=30)
print('Old jobs purged successfully')
"
```

### Log Rotation

Configure logrotate for web and worker logs:

```
/var/log/energizados*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 energizados energizados
}
```

### Updates

```bash
# Pull latest changes
git pull

# Update dependencies
pip install -e ".[web]"

# Restart services
sudo systemctl restart energizados-web energizados-worker
```

## Performance Tuning

### Scaling Considerations

- **Single Worker**: Current design uses FIFO queue with `concurrency=1`
- **Multiple Workers**: Not supported in Phase 1 (would require Redis/RabbitMQ)
- **Database**: SQLite handles thousands of jobs efficiently; consider PostgreSQL for high-volume scenarios

### Resource Limits

Typical resource usage:
- **Web Server**: 50-100 MB RAM, minimal CPU
- **Worker**: 100-500 MB RAM per job, varies by pipeline complexity
- **Database**: <10 MB for hundreds of jobs

## Backup and Recovery

### Backup Script

```bash
#!/bin/bash
# backup_energizados.sh

BACKUP_DIR="/backup/energizados/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup database
cp /var/lib/energizados/jobs.db "$BACKUP_DIR/"

# Backup run outputs
cp -r /opt/energizados/output "$BACKUP_DIR/"

# Compress
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Recovery

```bash
# Stop services
sudo systemctl stop energizados-web energizados-worker

# Restore database
cp /backup/energizados/20240101/jobs.db /var/lib/energizados/jobs.db

# Start services
sudo systemctl start energizados-web energizados-worker
```

## Support and Documentation

- **Framework Documentation**: See main CLAUDE.md and README.md
- **Design Docs**: `openspec/changes/web-console/design.md`
- **Issues**: Report bugs via project issue tracker
- **API Documentation**: Run `uvicorn energizados.web.app:app --reload` and visit http://localhost:8000/docs
