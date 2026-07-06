# Energizados Web Console - Docker Deployment

This directory contains production-ready Docker configuration for the Energizados web console.

## Quick Start

### Without Authentication (Default)

```bash
cd deploy/web
docker compose up --build
```

Access the web console at http://localhost:8000

### With HTTP Basic Authentication

```bash
cd deploy/web

# Generate htpasswd file (requires apache2-utils or htpasswd tool)
# Linux: sudo apt-get install apache2-utils
# Windows: Download htpasswd.exe from Apache website
htpasswd -c htpasswd admin  # Prompts for password

# Start with proxy profile
docker compose --profile proxy up --build
```

Access the web console at http://localhost:8080 (nginx on port 8080)

## Files

- `Dockerfile` - Single-stage build for web console image
- `compose.yml` - Multi-service orchestration (web + worker + optional proxy)
- `nginx.conf` - Reverse proxy configuration with HTTP basic auth
- `README.md` - This file

## Volumes

Two named volumes are created for data persistence:

- `energizados-data` - SQLite database and job queue (`/app/data`)
- `energizados-output` - Training run outputs (`/app/output`)

Both volumes are shared between the web and worker services to enable job processing.

## Building with ML Dependencies

By default, the image installs only the web extras (FastAPI + core framework). To include catboost, xgboost, and tensorflow for training:

```bash
docker compose build --build-arg INSTALL_EXTRAS=all
```

## Service Health

The web service includes a healthcheck at `/health`. Monitor with:

```bash
docker compose ps
curl http://localhost:8000/health
```

## Production Considerations

⚠️ **Security**: The web console has no built-in authentication (Phase 1). Use the proxy profile or deploy behind a corporate firewall.

⚠️ **Persistence**: Use Docker volumes or bind mounts for production data persistence.

⚠️ **Scaling**: Current design uses SQLite + single worker. For high-volume scenarios, consider PostgreSQL and multiple workers.