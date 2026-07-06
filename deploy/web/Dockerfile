# Energizados Web Console - Docker Image
# Single-stage build for simplicity and smaller size
# Cross-platform: works on both Windows (Docker Desktop) and Linux

ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim

# Build argument for extras installation (default: web only; can override with --build-arg INSTALL_EXTRAS=all)
ARG INSTALL_EXTRAS=web

# Set working directory
WORKDIR /app

# Install build dependencies for compiling Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install Energizados framework with specified extras
# Use 'web' by default for lightweight deployment (FastAPI + core framework)
# Override with: docker build --build-arg INSTALL_EXTRAS=all -t energizados .
RUN pip install --no-cache-dir -e ".[${INSTALL_EXTRAS}]"

# Create non-root user for security
RUN useradd -m -u 1000 energizados && \
    chown -R energizados:energizados /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/data/web /app/output && \
    chown -R energizados:energizados /app/data /app/output

# Switch to non-root user
USER energizados

# Set environment variables
ENV ENERGIZADOS_WEB_DB_PATH=/app/data/web/jobs.db \
    ENERGIZADOS_WEB_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Expose port for FastAPI
EXPOSE 8000

# Default command runs the worker (override in compose.yml for web service)
CMD ["python", "-m", "energizados.web.worker", "--db-path", "/app/data/web/jobs.db"]