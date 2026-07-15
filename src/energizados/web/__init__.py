"""
Energizados Web Console Package.

This package provides async job execution and web interface capabilities:
- JobStore: SQLite-backed job persistence
- JobRunner: Worker execution engine
- WebApp: FastAPI + Jinja2 + HTMX web layer

Phase 1 (PR1) scope: JobStore + JobRunner + worker entrypoint only.
Web UI and integration tests deferred to PR2/PR3.
"""

__version__ = "0.3.1"  # Track with framework version
