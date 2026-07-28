"""
FastAPI web application for Energizados web console.

Thin layer over energizados.api and JobStore. No business logic here.
Implements Phase 1 endpoints (tasks 5.9-5.18) with HTMX support.
Implements Phase 2 endpoints (runs list, detail, artifact serving) with security guards.
"""

import asyncio
import json
import logging
import os
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import energizados
from energizados.api import RunManager, format_error, merge_configs, validate_dict
from energizados.core.exceptions import ETLDependencyError
from energizados.core.pipeline import Pipeline
from energizados.web.models import JobStatus
from energizados.web.projects import ProjectService, default_project_service
from energizados.web.store import JobStore

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Energizados Web Console",
    description="Async job runner and web interface for Energizados ML framework",
    version="0.3.1",
)

# Create module-level Jinja2Templates instance
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _format_metric(value, best_run_id, current_run_id):
    """Render a metric value, marking the best run across compared runs with a star."""
    if value is None:
        return "N/A"
    try:
        formatted = f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)
    if best_run_id is not None and best_run_id == current_run_id:
        return f"{formatted} ★"
    return formatted


templates.env.globals["format_metric"] = _format_metric


# Add CORS middleware (for development; tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
try:
    static_dir.mkdir(exist_ok=True)
except (PermissionError, OSError):
    # Read-only install (PEP 668, system Python). The static dir must already
    # exist; if not, FastAPI will raise a clear error on first request.
    if not static_dir.is_dir():
        raise
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def _init_project_service() -> None:
    """Build the ProjectService from env/args and attach it to app.state.

    Workspace root resolution: ``ENERGIZADOS_WORKSPACE_ROOT`` env → default
    ``data/web/workspace``. The launcher's ``--workspace-root`` flag exports
    this env var so both the web and worker processes share it.
    """
    app.state.project_service = default_project_service()


def _project_service() -> ProjectService:
    """Return the app-level ProjectService (lazily built if missing)."""
    if not getattr(app.state, "project_service", None):
        app.state.project_service = default_project_service()
    return app.state.project_service


def _registered_projects() -> list:
    """Return registered workspace projects for the sidebar navigation.

    This is the FastAPI equivalent of a Flask context processor: registered as
    a Jinja global (see below) so ``base.html`` can render the sidebar without
    every route having to pass ``projects`` explicitly. Re-reads the registry
    on each render (cheap JSON read + path validation) so newly registered
    projects appear immediately.

    Wrapped + logged so a registry/IO failure can never break rendering of the
    app shell — the sidebar simply renders empty in that case.
    """
    try:
        return _project_service().list_projects()
    except Exception:  # noqa: BLE001 - never break the shell
        logger.exception("Failed to load registered projects for sidebar")
        return []


templates.env.globals["registered_projects"] = _registered_projects


def _run_manager_for(project_id: Optional[str], project_service: ProjectService) -> RunManager:
    """
    Build a RunManager scoped to a project's output dir, or the Global default.

    Args:
        project_id: Project slug from the URL (or None for the Global view).
        project_service: The ProjectService used to resolve project_id.

    Returns:
        ``RunManager(output_dir=<project>/output)`` for a registered project,
        or a plain ``RunManager()`` (cwd-relative ``output/``) for the Global
        view / unknown project_id.
    """
    if project_id:
        project = project_service.get_project(project_id)
        if project is not None:
            return RunManager(output_dir=str(Path(project.path) / "output"))
    return RunManager()


def _resolve_run_dir(manager: RunManager, run_id: str) -> Optional[Path]:
    """
    Resolve the on-disk run directory for a run_id, mirroring RunManager.get_run.

    ``RunManager.run_dir`` is a ``@property`` (the current run's dir, None on a
    fresh instance) — it is NOT a method taking a run_id. The old code called
    ``manager.run_dir(run_id)`` which is ``None(...)`` → TypeError → 500. This
    helper replaces all those call sites with the canonical pattern already used
    inside ``RunManager.get_run`` (``run_manager.py:441``): ``base / run_id``.

    Args:
        manager: A RunManager (its ``_output_dir`` selects the output base).
        run_id: Run identifier.

    Returns:
        The run directory Path if it exists on disk, else None.
    """
    base = getattr(manager, "_output_dir", None) or Path("output")
    run_dir = base / run_id
    return run_dir if run_dir.is_dir() else None


class _HtmxErrorResponse(Exception):
    """
    Short-circuit signal carrying a pre-built HTMX error fragment.

    Raised by ``_validate_request_config`` on HTMX validation errors so callers
    get a clean linear flow: every error path raises (JSON errors raise
    ``HTTPException``, HTMX errors raise this), and the helper only ever
    *returns* on success. The handler below unwraps and returns the fragment.
    """

    def __init__(self, response: Response):
        self.response = response


@app.exception_handler(_HtmxErrorResponse)
async def _htmx_error_response_handler(request: Request, exc: _HtmxErrorResponse) -> Response:
    """Unwrap an HTMX error fragment raised during request validation."""
    return exc.response


def _check_custom_class_prefixes(config: Dict[str, Any]) -> List[str]:
    """
    Extract all custom_class paths from config and verify against ALLOWED_PREFIXES.

    This is a security-critical function that validates all custom_class entries
    in the config to prevent arbitrary code execution. Only paths starting with
    entries in ALLOWED_PREFIXES (energizados.*, src.*) are allowed.

    Args:
        config: Configuration dictionary parsed from YAML

    Returns:
        List of invalid custom_class paths (empty if all valid)
    """
    from energizados.core.utils.import_utils import ALLOWED_PREFIXES

    invalid_paths = []

    def extract_custom_classes(obj: Any, path: str = "") -> List[str]:
        """Recursively extract all custom_class values from config."""
        custom_classes = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                if key == "custom_class" and isinstance(value, str):
                    custom_classes.append(value)
                else:
                    custom_classes.extend(extract_custom_classes(value, current_path))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                current_path = f"{path}[{i}]"
                custom_classes.extend(extract_custom_classes(item, current_path))

        return custom_classes

    # Extract all custom_class paths
    custom_class_paths = extract_custom_classes(config)

    # Validate each path against ALLOWED_PREFIXES
    for path in custom_class_paths:
        if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            invalid_paths.append(path)

    return invalid_paths


@dataclass
class _ValidatedConfig:
    """Successful result of request body parsing + validation + security check."""

    config: Dict[str, Any]
    config_type: str


def _raise_htmx_error(
    request: Request,
    template: str,
    *,
    errors: Optional[List[str]] = None,
    invalid_prefixes: Optional[List[str]] = None,
    allowed_prefixes: Optional[List[str]] = None,
    status_code: int = 400,
) -> None:
    """Build an HTMX validation-error fragment and raise it as ``_HtmxErrorResponse``."""
    response = templates.TemplateResponse(
        request,
        template,
        {
            "errors": errors,
            "invalid_prefixes": invalid_prefixes,
            "allowed_prefixes": allowed_prefixes,
        },
        status_code=status_code,
    )
    raise _HtmxErrorResponse(response)


async def _validate_request_config(request: Request, htmx_error_template: str) -> _ValidatedConfig:
    """
    Parse, validate, and security-check a request body config.

    Shared by ``POST /jobs`` and ``POST /plan``. The two callers differ only in
    which HTMX error fragment they render, passed as ``htmx_error_template``.

    Returns a ``_ValidatedConfig`` on success. On any validation error it raises:
    - ``HTTPException(400)`` for non-HTMX requests (FastAPI formats as ``{"detail": ...}``).
    - ``_HtmxErrorResponse`` for HTMX requests (the registered handler returns the fragment).
    Either way the caller never sees a value on the error path, so it can use the
    result directly with no success/error branching.
    """
    is_htmx = request.headers.get("HX-Request") == "true"
    content_type = request.headers.get("content-type", "")

    # Parse body
    body = await request.body()
    if not body:
        if is_htmx:
            _raise_htmx_error(request, htmx_error_template, errors=["Empty request body"])
        raise HTTPException(status_code=400, detail="Empty request body")

    try:
        if "application/yaml" in content_type:
            config = yaml.safe_load(body)
        elif "application/json" in content_type:
            config = json.loads(body)
        else:
            # Try YAML first, fallback to JSON
            try:
                config = yaml.safe_load(body)
            except yaml.YAMLError:
                config = json.loads(body)
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        msg = f"Invalid YAML or JSON: {str(e)}"
        if is_htmx:
            _raise_htmx_error(request, htmx_error_template, errors=[msg])
        raise HTTPException(status_code=400, detail=msg)

    if not isinstance(config, dict):
        if is_htmx:
            _raise_htmx_error(request, htmx_error_template, errors=["Config must be a dictionary"])
        raise HTTPException(status_code=400, detail="Config must be a dictionary")

    # config_type from query params
    config_type = request.query_params.get("config_type", "train")

    # Schema validation via energizados.api
    validation_result = validate_dict(config, config_type)
    if not validation_result.is_valid:
        errors = []
        for error in validation_result.errors or []:
            if hasattr(error, "__dict__"):
                errors.append(str(error))
            else:
                errors.append(error)
        if is_htmx:
            _raise_htmx_error(request, htmx_error_template, errors=errors)
        raise HTTPException(
            status_code=400, detail={"errors": errors, "message": "Configuration validation failed"}
        )

    # Security: disallow custom_class prefixes outside the allowlist
    invalid_prefixes = _check_custom_class_prefixes(config)
    if invalid_prefixes:
        allowed_prefixes = ["energizados.*", "src.*"]
        if is_htmx:
            _raise_htmx_error(
                request,
                htmx_error_template,
                invalid_prefixes=invalid_prefixes,
                allowed_prefixes=allowed_prefixes,
            )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "custom_class_prefix_validation",
                "message": f"Disallowed custom_class prefixes: {invalid_prefixes}",
                "invalid_prefixes": invalid_prefixes,
                "allowed_prefixes": allowed_prefixes,
            },
        )

    return _ValidatedConfig(config=config, config_type=config_type)


@app.get("/")
async def root(request: Request):
    """
    Entry point — redirect to the projects home.

    The projects home (``/projects``) is the v0.4 entry point. The legacy
    Global YAML editor that used to live here is kept reachable at ``/global``
    (project-agnostic job creation); each project's detail page
    (``/projects/{project_id}``) also hosts a project-scoped editor. The Global
    job list, runs, and dashboard remain reachable from the nav at ``/jobs``,
    ``/runs`` and ``/dashboard``.
    """
    return RedirectResponse(url="/projects", status_code=302)


@app.get("/global")
async def global_editor(request: Request):
    """
    Global YAML editor + job list (project-agnostic; creation deprecated).

    ADR-0002: Global job creation is blocked at ``POST /jobs``. The editor is
    kept visible for inspection but its submit is disabled; a banner points
    users at the project-scoped workflow. The job list below remains a
    read-only view of legacy Global rows.
    """
    return templates.TemplateResponse(
        request,
        "index.html",
        {"global_deprecated": True, "submit_disabled": True},
    )


@app.get("/ui")
async def style_guide(request: Request):
    """
    Living style guide for the web console design system.

    Renders ``ui.html`` — a self-documenting page that demonstrates the real
    design tokens and component classes defined in ``static/css/app.css``. Every
    swatch/sample is grounded in ``var(--app-*)`` tokens, so the whole page
    auto-adapts to the active light/dark theme via the global topbar toggle.
    """
    return templates.TemplateResponse(request, "ui.html", {})


@app.post("/jobs")
async def create_job(request: Request):
    """Reject Global job creation (ADR-0002).

    Global (project-agnostic) job creation is deprecated. This endpoint no
    longer parses, validates, or enqueues anything — it always returns 400.
    The canonical route is ``POST /projects/{project_id}/jobs``. Existing
    Global rows remain readable via ``GET /jobs`` (legacy read-only surface).

    Returns:
        400 with an ADR-0002 message — JSON ``{"detail": ...}`` for plain
        requests, or the ``job_validation.html`` fragment for HTMX requests
        (same helper the project-scoped route uses for validation errors).
    """
    message = (
        "Global job creation is deprecated (ADR-0002). "
        "Create jobs via POST /projects/{project_id}/jobs instead."
    )
    is_htmx = request.headers.get("HX-Request") == "true"
    if is_htmx:
        _raise_htmx_error(request, "job_validation.html", errors=[message])
    raise HTTPException(status_code=400, detail=message)


@app.get("/jobs")
async def list_jobs(request: Request, status: str = None):
    """
    List jobs with optional status filter (task 5.13).

    Returns HTMX fragment for auto-refresh (every 2s).

    Args:
        request: FastAPI request
        status: Optional status filter (queued|running|success|failed|aborted)

    Returns:
        HTMX fragment for auto-refresh polls (HX-Request); on direct navigation
        returns the full themed jobs page (jobs.html).
    """
    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            pass  # Invalid status, ignore filter

    # Get jobs from store
    store = JobStore()
    jobs = store.list_jobs(status_filter=status_filter, limit=100)

    # HTMX auto-refresh poll -> bare fragment; direct navigation -> full themed page.
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "job_list.html" if is_htmx else "jobs.html"
    return templates.TemplateResponse(
        request, template, {"jobs": jobs, "status_filter": status_filter}
    )


# SSE constants
SSE_POLL_INTERVAL_SECONDS = 1.0
SSE_MAX_POLL_ITERATIONS = (
    3600  # Safety cap: 1 hour at 1s interval (true backstop, not regular occurrence)
)
SSE_EVENT_CONNECTED = "connected"
SSE_EVENT_TERMINAL = "terminal"
SSE_EVENT_ERROR = "error"
# Client JS in job_detail.html must mirror these event names


@app.get("/jobs/{job_id}/progress")
async def get_job_progress(job_id: str, request: Request):
    """
    SSE endpoint for live job progress (Task 5).

    Streams job events from SQLite in Server-Sent Events format.
    Returns 404 if job not found (before streaming).

    Args:
        job_id: Job identifier
        request: FastAPI request (for Last-Event-ID header)

    Returns:
        StreamingResponse with text/event-stream content-type
    """
    # Get job first - raise 404 BEFORE entering generator
    store = JobStore()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Read Last-Event-ID header for resume (default 0 if missing/invalid)
    last_event_id = request.headers.get("last-event-id")
    try:
        start_after_seq = int(last_event_id) if last_event_id else 0
    except ValueError:
        start_after_seq = 0

    async def event_stream(after_seq: int = 0):
        """Async generator for SSE events."""
        iteration = 0
        initial_sent = False

        try:
            while iteration < SSE_MAX_POLL_ITERATIONS:
                # Fetch new events
                try:
                    events = store.get_job_events_since(job_id, after_seq)
                except Exception as e:
                    logger.error(f"Error fetching events for job {job_id}: {e}")
                    events = []

                # Stream events with event-id for resume
                for event in events:
                    yield f"id: {event['seq']}\ndata: {json.dumps(event)}\n\n"
                    after_seq = max(after_seq, event["seq"])

                # Check job status (re-fetch to get latest state)
                current_job = store.get_job(job_id)

                # Send initial heartbeat for running jobs with no events
                if not initial_sent and not events and not current_job.is_terminal():
                    yield f"event: {SSE_EVENT_CONNECTED}\ndata: {json.dumps({'job_id': job_id, 'status': current_job.status.value})}\n\n"
                    initial_sent = True

                # Check if job is terminal
                if current_job.is_terminal():
                    # Emit terminal signal and close
                    terminal_event = {
                        "status": current_job.status.value,
                        "finished_at": current_job.finished_at,
                    }
                    yield f"event: {SSE_EVENT_TERMINAL}\ndata: {json.dumps(terminal_event)}\n\n"
                    logger.info(f"Job {job_id} terminal, closing SSE stream")
                    return

                # Job still running: wait before next poll. The loop only exits when
                # the job transitions to a terminal state or the safety cap is reached.
                await asyncio.sleep(SSE_POLL_INTERVAL_SECONDS)
                iteration += 1

            # Safety cap reached - close silently (client reconnects with Last-Event-ID)
            logger.warning(
                f"Job {job_id} SSE stream reached safety cap ({SSE_MAX_POLL_ITERATIONS} iterations)"
            )
            return

        except GeneratorExit:
            # Client disconnected
            logger.info(f"Job {job_id} SSE client disconnected")
        except Exception as e:
            # Unexpected error - log and close
            logger.error(f"Job {job_id} SSE stream error: {e}")
            yield f"event: {SSE_EVENT_ERROR}\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(after_seq=start_after_seq), media_type="text/event-stream"
    )


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    """
    Get job detail by ID (task 5.14).

    Returns HTML fragment or JSON based on Accept header.

    Args:
        job_id: Job identifier
        request: FastAPI request

    Returns:
        Job detail as HTML fragment or JSON
    """
    # Get job from store
    store = JobStore()
    job = store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Return JSON if requested
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return job.to_dict()

    # Resolve the owning project (None for Global jobs or unregistered paths).
    project_id = None
    project_name = None
    if job.project_path:
        project = _project_service().get_by_path(Path(job.project_path))
        if project is not None:
            project_id = project.project_id
            project_name = project.name

    return templates.TemplateResponse(
        request,
        "job_detail.html",
        {
            "job": job,
            "project_id": project_id,
            "project_name": project_name,
            "project_path": job.project_path,
        },
    )


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a running job (task 5.15).

    Args:
        job_id: Job identifier

    Returns:
        JSON with updated status
    """
    store = JobStore()

    # Check if job exists
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Attempt cancel
    cancelled = store.cancel_job(job_id)

    return {
        "job_id": job_id,
        "status": "aborted" if cancelled else job.status.value,
        "cancelled": cancelled,
    }


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """
    Retry a failed/aborted/successful job (task 5.16).

    Creates a new job with retried_from link to original.

    Args:
        job_id: Original job identifier

    Returns:
        JSON with new job_id and status
    """
    store = JobStore()

    # Check if original job exists
    original_job = store.get_job(job_id)
    if original_job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Attempt retry
    new_job_id = store.retry_job(job_id)

    if new_job_id is None:
        raise HTTPException(
            status_code=400, detail=f"Cannot retry job with status: {original_job.status.value}"
        )

    return JSONResponse(
        status_code=201, content={"job_id": new_job_id, "status": "queued", "retried_from": job_id}
    )


@app.get("/health")
async def health():
    """
    Health check endpoint (task 5.17).

    Returns:
        JSON with health status
    """
    return {"ok": True}


@app.get("/api/runs")
async def list_runs_api():
    """
    Proxy RunManager.list_runs() for Phase 2 preparation (task 5.18).

    Returns:
        JSON with list of run directories
    """
    try:
        runs = RunManager.list_runs()
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Error listing runs: {e}")
        return JSONResponse(status_code=500, content={"runs": [], "error": str(e)})


# ============================================================================
# Config templates API (config authoring — raw .tpl content, no substitution)
# ============================================================================

#: Strict filename guard for config-type identifiers served from a project's
#: ``config/`` dir. Rejects path separators (``/``, ``\``), traversal (``..``),
#: and any non-filename characters. ``^[A-Za-z0-9_]+$`` is intentionally narrow.
_CONFIG_TYPE_RE = re.compile(r"^[A-Za-z0-9_]+$")

#: Suffix of the shipped config templates (matches ``cli/init.py`` resolution).
_CONFIG_TEMPLATE_SUFFIX = ".yaml.tpl"


def _config_templates_dir() -> Path:
    """
    Resolve the shipped config-template directory.

    Mirrors ``cli/init.py``'s ``_get_template_path``: the ``.yaml.tpl`` files
    live under ``energizados/templates/config/`` inside the installed package.
    """
    return Path(energizados.__file__).resolve().parent / "templates" / "config"


def _available_config_template_names() -> List[str]:
    """
    Enumerate the stems of the shipped ``.yaml.tpl`` config templates.

    Returns the fixed set actually present on disk (e.g. ``["eda", "etl",
    "infer", "train"]``), sorted. This set is the allowlist for
    ``GET /api/templates/{name}`` — only these names are ever read, so the
    endpoint never reads an arbitrary path.
    """
    tpl_dir = _config_templates_dir()
    if not tpl_dir.is_dir():
        logger.warning(f"Config templates dir not found: {tpl_dir}")
        return []
    return sorted(
        p.name[: -len(_CONFIG_TEMPLATE_SUFFIX)]
        for p in tpl_dir.glob(f"*{_CONFIG_TEMPLATE_SUFFIX}")
        if p.is_file()
    )


@app.get("/api/templates")
async def list_config_templates() -> Dict[str, List[str]]:
    """
    List the available config-template names (stems of the shipped ``.yaml.tpl``).

    Returns:
        ``{"templates": ["eda", "etl", "infer", "train"]}`` (order may vary).
    """
    return {"templates": _available_config_template_names()}


@app.get("/api/templates/{name}")
async def get_config_template(name: str) -> Response:
    """
    Serve a single config template's raw ``.tpl`` content as ``text/yaml``.

    Security: ``name`` MUST be in the fixed set of shipped template stems
    (derived from the package's ``templates/config/`` dir). Anything else —
    including traversal like ``..`` or ``foo/bar`` — returns 404. No arbitrary
    file is ever read; only ``<templates_dir>/<name>.yaml.tpl`` for a known
    ``name``.

    The content is returned RAW (no ``{{project_name}}`` substitution) — config
    templates are plain YAML the user edits after loading.
    """
    valid_names = set(_available_config_template_names())
    if name not in valid_names:
        raise HTTPException(status_code=404, detail="Template not found")

    tpl_dir = _config_templates_dir().resolve()
    target = (tpl_dir / f"{name}{_CONFIG_TEMPLATE_SUFFIX}").resolve()
    # Defense-in-depth: the resolved path must live inside the templates dir
    # (guards against any future escape via the stem).
    try:
        target.relative_to(tpl_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="Template not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Template not found")

    return Response(content=target.read_text(encoding="utf-8"), media_type="text/yaml")


# ============================================================================
# PHASE 2: Runs List, Detail, and Artifact Serving (with security guards)
# ============================================================================


def _guess_media_type(path: Path) -> str:
    """
    Guess media type from file extension.

    Args:
        path: File path

    Returns:
        MIME type string
    """
    ext = path.suffix.lower()
    types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".html": "text/html",
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".log": "text/plain",
        ".txt": "text/plain",
    }
    return types.get(ext, "application/octet-stream")


def _is_cacheable(path: Path) -> bool:
    """
    Return True if file should be cached (plots, reports).

    Args:
        path: File path

    Returns:
        True if cacheable, False otherwise
    """
    ext = path.suffix.lower()
    return ext in {".png", ".jpg", ".jpeg", ".svg", ".html"}


@app.get("/runs/{run_id}/artifacts/{path:path}")
async def get_artifact(run_id: str, path: str):
    """
    Serve run artifacts with path-traversal guard (Phase 1, tasks 1.6-1.9).

    Security: Multi-layer guard against path traversal:
    1. Validate run_id via RunManager.get_run() (404 if unknown)
    2. Reject artifact_path containing .., absolute paths, backslashes
    3. Resolve both paths and assert artifact_path relative to run_dir
    4. Return 404 if file missing (no directory listings)

    Args:
        run_id: Run identifier (validated via RunManager)
        path: Relative path within run directory

    Returns:
        FileResponse with appropriate content-type and cache headers

    Raises:
        HTTPException: 404 if run/artifact not found, 403/400 on path traversal
    """
    manager = RunManager()

    # Step 1: Validate run_id via RunManager.get_run()
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Step 2: Resolve run directory
    run_dir = _resolve_run_dir(manager, run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run directory not found")

    # Step 3: Reject path traversal attempts
    if ".." in path or path.startswith("/") or "\\" in path:
        raise HTTPException(status_code=403, detail="Invalid path")

    # Step 4: Resolve artifact path
    try:
        artifact_path = (run_dir / path).resolve()
    except (OSError, ValueError) as e:
        logger.error(f"Error resolving artifact path: {e}")
        raise HTTPException(status_code=400, detail="Invalid artifact path")

    # Step 5: Double-check: must be within run_dir (defends against symlink escapes)
    try:
        artifact_path.relative_to(run_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal detected")

    # Step 6: Serve file if exists
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Step 7: Content-Type by extension
    media_type = _guess_media_type(artifact_path)

    # Step 8: Cache headers for plots/EDA (1 hour)
    cache_control = "public, max-age=3600" if _is_cacheable(artifact_path) else None

    return FileResponse(
        artifact_path,
        media_type=media_type,
        headers={"Cache-Control": cache_control} if cache_control else {},
    )


@app.get("/runs")
async def list_runs(request: Request, status: Optional[str] = None, limit: int = 100):
    """
    List runs with optional status filter (Phase 2, tasks 2.5).

    Args:
        request: FastAPI request
        status: Optional status filter (success|partial|failed)
        limit: Maximum number of runs to return (default 100)

    Returns:
        HTML template with runs table or JSON based on Accept header
    """
    manager = RunManager()

    # Build filter dict
    filter_dict = {"status": status} if status else None

    # Get runs from RunManager
    runs = manager.list_runs(filter=filter_dict, limit=limit)

    # Return JSON if requested
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"runs": [run.to_dict() for run in runs]}

    # ADR-0001: group runs by type for the HTML index (mirrors project_detail's
    # by-type tables). Legacy runs default to the "training" bucket.
    run_groups = {bucket: [] for bucket in _RUN_TYPE_BUCKETS}
    for run in runs:
        run_groups[_resolve_run_type(run)].append(run)
    run_outputs: Dict[str, str] = {}
    for run in runs:
        label = _primary_output_label(run)
        if label:
            run_outputs[run.run_id] = label

    # Return HTML template
    return templates.TemplateResponse(
        request,
        "runs_list.html",
        {
            "runs": runs,
            "run_groups": run_groups,
            "run_type_buckets": _RUN_TYPE_BUCKETS,
            "run_outputs": run_outputs,
            "status_filter": status,
            "limit": limit,
        },
    )


@app.post("/plan")
async def get_execution_plan(request: Request):
    """
    Return execution plan without running the pipeline.

    Expects YAML/JSON body and config_type query parameter.
    Validates config via validate_dict() and checks custom_class prefixes.

    Returns:
        - 200 with ExecutionPlan (JSON) or plan HTML fragment (HTMX)
        - 200 with {"available": false, "message": "..."} for non-ETL configs
        - 400 with validation errors (JSON) or error HTML fragment (HTMX)
        - 400 with cycle error (ETLDependencyError formatted via format_error)
    """
    # Check if HTMX request for content negotiation
    is_htmx = request.headers.get("HX-Request") == "true"

    # Parse + validate + security-check the request config (shared with POST /jobs).
    # Raises HTTPException (JSON) or _HtmxErrorResponse (HTMX) on any validation error.
    config = (
        await _validate_request_config(request, htmx_error_template="components/validation.html")
    ).config

    # Check if config has etl: section (plan preview only for ETL configs)
    if "etl" not in config:
        message = "Plan preview available for ETL configs only"
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "plan_preview.html",
                {"plan": None, "available": False, "message": message, "error": None},
                status_code=200,
            )
        return JSONResponse(status_code=200, content={"available": False, "message": message})

    # Build Pipeline and compute execution plan
    try:
        pipeline = Pipeline.from_dict(config)
        plan = pipeline.plan()
    except ETLDependencyError as e:
        # Circular dependency detected
        error_dict = format_error(e)
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "plan_preview.html",
                {"plan": None, "available": False, "message": None, "error": error_dict},
                status_code=400,
            )
        raise HTTPException(status_code=400, detail=error_dict)
    except Exception as e:
        # Only /plan constructs a Pipeline (POST /jobs never does), so this
        # handler is intentionally local to this endpoint. Pipeline.from_dict()
        # can fail in many ways on user-supplied config (e.g. ConfigurationError);
        # we log, format via format_error, and surface a structured 500 to the
        # operator instead of a bare FastAPI error page.
        logger.error(f"Error computing execution plan: {e}")
        error_dict = format_error(e)
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "plan_preview.html",
                {"plan": None, "available": False, "message": None, "error": error_dict},
                status_code=500,
            )
        raise HTTPException(status_code=500, detail=error_dict)

    # Return HTML for HTMX, JSON otherwise
    if is_htmx:
        return templates.TemplateResponse(
            request,
            "plan_preview.html",
            {"plan": plan, "available": True, "message": None, "error": None},
            status_code=200,
        )

    # JSON response
    return JSONResponse(
        status_code=200,
        content={
            "steps": plan.steps,
            "dependencies": plan.dependencies,
            "estimated_duration": plan.estimated_duration,
        },
    )


# ============================================================================
# PHASE 3: Template Helpers (Shared Infrastructure)
# ============================================================================


def _resolve_evaluation_files(run_id: str, manager: Optional[RunManager] = None):
    """
    Resolve the on-disk evaluation JSON paths for a run.

    Shared by ``_load_run_evaluation`` and ``_load_threshold_data`` so the
    run lookup + run_dir resolution + eval-dir layout lives in one place
    (avoids the duplication that would otherwise re-appear per consumer).

    Args:
        run_id: Run identifier
        manager: Optional RunManager (project-scoped). Defaults to a Global
            ``RunManager()``.

    Returns:
        ``(comparison_path, report_path)`` tuple, or ``None`` if the run or its
        directory cannot be resolved. Paths are returned even if the files do
        not exist — callers check ``.is_file()`` to decide which to read.
    """
    manager = manager or RunManager()
    if not manager.get_run(run_id):
        return None
    run_dir = _resolve_run_dir(manager, run_id)
    if not run_dir:
        return None
    eval_dir = run_dir / "reports" / "evaluation"
    return eval_dir / "comparison.json", eval_dir / "evaluation_report.json"


def _load_run_evaluation(
    run_id: str, manager: Optional[RunManager] = None
) -> Optional[Dict[str, Any]]:
    """
    Load evaluation JSON for a run, handling both single-model and multi-model structures.

    Args:
        run_id: Run identifier
        manager: Optional RunManager (project-scoped). Defaults to a Global one.
        run_id: Run identifier

    Returns:
        Normalized dict with:
        - ranking (if multi-model): List[{name, metrics, info}]
        - metrics (if single-model): Dict of metric names
        - best_model (if multi-model): str
        - is_multi: bool
        - None if no evaluation found
    """
    resolved = _resolve_evaluation_files(run_id, manager)
    if not resolved:
        return None
    comparison_path, report_path = resolved

    # Try multi-model first
    if comparison_path.is_file():
        try:
            data = json.loads(comparison_path.read_text(encoding="utf-8"))
            # Already in template-friendly format
            return {
                "ranking": data.get("ranking", []),
                "best_model": data.get("best_model"),
                "is_multi": True,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {comparison_path} for run {run_id}: {e}")

    # Try single-model
    if report_path.is_file():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return {
                "metrics": data.get("metrics", {}),
                "model_info": data.get("model_info", {}),
                "is_multi": False,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {report_path} for run {run_id}: {e}")

    return None


def _list_run_configs(run, manager: Optional[RunManager] = None) -> List[str]:
    """
    List config filenames in run directory.

    Args:
        run: RunMetadata object
        manager: Optional RunManager (project-scoped). Defaults to a Global one.

    Returns:
        List of config filenames
    """
    manager = manager or RunManager()
    run_dir = _resolve_run_dir(manager, run.run_id)
    if not run_dir:
        return []

    config_dir = run_dir / "config"
    if not config_dir.is_dir():
        return []

    return [f.name for f in config_dir.iterdir() if f.is_file()]


def _has_run_log(run, manager: Optional[RunManager] = None) -> bool:
    """
    Check if run.log exists.

    Args:
        run: RunMetadata object
        manager: Optional RunManager (project-scoped). Defaults to a Global one.

    Returns:
        True if log exists, False otherwise
    """
    manager = manager or RunManager()
    run_dir = _resolve_run_dir(manager, run.run_id)
    if not run_dir:
        return False

    return (run_dir / "run.log").is_file()


def _read_run_log(run, max_lines: int = 1000, manager: Optional[RunManager] = None) -> str:
    """
    Read last N lines from run.log.

    Args:
        run: RunMetadata object
        max_lines: Maximum number of lines to read (default 1000)
        manager: Optional RunManager (project-scoped). Defaults to a Global one.

    Returns:
        Log file contents as string
    """
    manager = manager or RunManager()
    run_dir = _resolve_run_dir(manager, run.run_id)
    if not run_dir:
        return "Log not found"

    log_path = run_dir / "run.log"
    if not log_path.is_file():
        return "Log not found"

    try:
        # Tail efficiently: deque with maxlen discards earlier lines as it
        # reads, so we never hold the full file in memory (bounded read).
        with open(log_path, "r", encoding="utf-8") as f:
            tail = deque(f, maxlen=max_lines)
        if len(tail) < max_lines:
            return "".join(tail)
        return f"... (showing last {max_lines} lines)\n" + "".join(tail)
    except IOError as e:
        return f"Error reading log: {e}"


def _get_artifact_relative_path(
    run, absolute_path: str, manager: Optional[RunManager] = None
) -> str:
    """
    Convert absolute artifact path to relative path for artifact route.

    Args:
        run: RunMetadata object
        absolute_path: Absolute path to artifact
        manager: Optional RunManager (project-scoped). Defaults to a Global one.

    Returns:
        Relative path for artifact route

    Raises:
        ValueError: If path is not within run directory
    """
    manager = manager or RunManager()
    run_dir = _resolve_run_dir(manager, run.run_id)
    if not run_dir:
        raise ValueError("Invalid run directory")

    try:
        return str(Path(absolute_path).relative_to(run_dir))
    except ValueError:
        raise ValueError(f"Path {absolute_path} not within run directory")


@app.get("/runs/compare")
async def compare_runs_page(request: Request, ids: str = ""):
    """
    Comparison HTML page for side-by-side run comparison.

    Renders comparison table with metrics, ensemble rankings, and best value highlighting.

    ADR-0001 (Phase 4): Compare is explicit about Run type. Only same-type Runs
    are comparable; cross-type sets render a typed empty-state banner (the JSON
    endpoint returns HTTP 409 for the same condition). Training runs keep the
    existing AUC/F1/precision/recall/threshold table; non-training homogeneous
    sets render a metadata table.

    NOTE: Declared BEFORE /runs/{run_id} so FastAPI does not swallow the literal
    "compare" segment as a run_id path parameter (route matching is order-sensitive).
    """
    # Parse and validate run IDs
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)

    # ADR-0001: resolve each requested Run's type BEFORE eval-data filtering so a
    # mixed-type set is rejected rather than silently narrowed to whatever
    # training runs happen to carry evaluation data.
    manager = RunManager()
    run_meta_by_id, run_types = _load_compare_run_types(run_ids, manager)

    # Cross-type set → typed empty-state banner (page surface). Not a 404: the
    # runs exist, they are simply not comparable.
    if len(set(run_types.values())) > 1:
        return templates.TemplateResponse(
            request,
            "compare_runs.html",
            {
                "mixed_types": True,
                "run_types": run_types,
                "runs": [],
                "meta_runs": [],
                "best": {"auc": None, "f1": None, "precision": None, "recall": None},
                "ids": ids,
                "run_type": None,
                "comparison_json": "[]",
            },
        )

    run_type = next(iter(set(run_types.values())))

    # Load evaluation data for all runs (tolerant to missing files).
    eval_data_dict = _load_run_evaluations_batch(run_ids)

    if run_type == "training":
        return _render_training_compare(request, ids, run_ids, eval_data_dict)

    # Homogeneous non-training compare: render a metadata table. These Runs do
    # not produce evaluation_report.json, so missing eval data is expected and
    # not a 404. Runs without metadata are skipped; if none resolve, 404.
    meta_runs = [
        {"run_id": run_id, "metadata": run_meta_by_id[run_id].to_dict()}
        for run_id in run_ids
        if run_meta_by_id.get(run_id) is not None
    ]
    if not meta_runs:
        raise HTTPException(status_code=404, detail="No valid runs found")

    return templates.TemplateResponse(
        request,
        "compare_runs.html",
        {
            "mixed_types": False,
            "run_types": run_types,
            "runs": [],
            "meta_runs": meta_runs,
            "best": {"auc": None, "f1": None, "precision": None, "recall": None},
            "ids": ids,
            "run_type": run_type,
            "comparison_json": "[]",
        },
    )


def _render_training_compare(
    request: Request,
    ids: str,
    run_ids: List[str],
    eval_data_dict: Dict[str, Dict],
):
    """Render the training-run comparison table (unchanged ADR-0001 pre-Phase-4 behavior).

    Factored out of compare_runs_page so the training path stays byte-for-byte
    identical while the page handler branches on Run type.
    """
    # If all runs missing evaluation data, return 404
    if not eval_data_dict:
        raise HTTPException(
            status_code=404, detail="No evaluation data found for any of the specified runs"
        )

    # Build comparison data directly from evaluation data
    runs_data = []

    for run_id in run_ids:
        # Skip runs without evaluation data (already omitted from eval_data_dict)
        if run_id not in eval_data_dict:
            continue

        # Get evaluation data
        eval_data = eval_data_dict[run_id]

        # Build run entry with minimal data needed for template
        runs_data.append(
            {
                "run_id": run_id,
                "evaluation": eval_data,
                "available_models": eval_data.get("ranking") if eval_data.get("is_multi") else None,
                "is_multi": eval_data.get("is_multi", False),
            }
        )

    if not runs_data:
        raise HTTPException(status_code=404, detail="No valid runs found")

    # Precompute best run per metric (single-model runs only) for ★ highlighting.
    best = {"auc": None, "f1": None, "precision": None, "recall": None}
    best_val = {k: float("-inf") for k in best}
    for entry in runs_data:
        if entry["is_multi"]:
            continue
        metrics = (entry["evaluation"] or {}).get("metrics") or {}
        for key in best:
            value = metrics.get(key)
            if isinstance(value, (int, float)) and value > best_val[key]:
                best_val[key] = value
                best[key] = entry["run_id"]

    return templates.TemplateResponse(
        request,
        "compare_runs.html",
        {
            "mixed_types": False,
            "run_types": {},
            "runs": runs_data,
            "meta_runs": [],
            "ids": ids,
            "best": best,
            "run_type": "training",
            # Embedded in a <script type="application/json"> data island via | safe.
            # json.dumps does not escape "</script>"; neutralize the closing-tag
            # sequence so a run_id/model name containing it cannot break out of the
            # script element (defense-in-depth XSS hardening).
            "comparison_json": json.dumps(runs_data)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e"),
        },
    )


@app.get("/runs/{run_id}")
async def get_run_detail(run_id: str, request: Request):
    """
    Get run detail page (Phase 4, tasks 4.8).

    Args:
        run_id: Run identifier
        request: FastAPI request

    Returns:
        HTML template with run detail or 404 if not found
    """
    manager = RunManager()
    run = manager.get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load evaluation JSON (try both structures)
    evaluation = _load_run_evaluation(run_id)

    # Determine threshold unavailability message
    threshold_unavailable_message = None
    threshold_data = _load_threshold_data(run_id)
    if threshold_data:
        if threshold_data.get("is_multi"):
            threshold_unavailable_message = (
                "Threshold exploration is not available for ensemble runs. "
                "comparison.json does not contain threshold sweep data. "
                "View individual model reports for detailed threshold analysis."
            )
        elif threshold_data.get("threshold_metrics") is None:
            threshold_unavailable_message = (
                "This run was created before threshold sweep data was added to evaluation reports. "
                "Re-run the evaluation to generate threshold exploration data."
            )

    # List config files
    config_files = _list_run_configs(run)

    # Check for run.log
    has_log = _has_run_log(run)

    # EDA relative path for iframe
    eda_relative_path = None
    if run.output_paths.get("eda_report"):
        try:
            eda_relative_path = _get_artifact_relative_path(run, run.output_paths["eda_report"])
        except ValueError:
            # Path not within run directory, skip EDA iframe
            pass

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run": run,
            "evaluation": evaluation,
            "config_files": config_files,
            "has_log": has_log,
            "log_content": _read_run_log(run) if has_log else None,
            "eda_relative_path": eda_relative_path,
            "threshold_unavailable_message": threshold_unavailable_message,
        },
    )


# ==================== Phase 4: Timeline Dashboard ====================


@app.get("/api/dashboard/timeline")
async def timeline_data(limit: int = 100, status: Optional[str] = None):
    """
    Timeline data API endpoint for dashboard charts.

    Returns JSON with timestamps, auc, f1, and run_ids arrays from RunMetadata.
    Supports optional status filter and limit parameter.
    """
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)

    # Apply client-side filtering for status (defensive in case RunManager doesn't respect filter)
    if status:
        runs = [run for run in runs if run.status == status]

    # Ensure we don't exceed the limit (defensive in case RunManager doesn't respect it)
    runs = runs[:limit] if len(runs) > limit else runs

    # ADR-0001: AUC/F1 are training-only metrics. Non-training runs carry None
    # and would pollute the timeline — scope to training runs. Reuses the
    # canonical _resolve_run_type helper; legacy runs default to "training".
    training_runs = [run for run in runs if _resolve_run_type(run) == "training"]
    # RunMetadata.timestamp is already a serialized ISO string — use it
    # verbatim (.isoformat() only works on a datetime and 500s on real runs).
    timestamps = [run.timestamp or None for run in training_runs]
    auc = [run.val_auc for run in training_runs]
    f1 = [run.val_f1 for run in training_runs]
    run_ids = [run.run_id for run in training_runs]

    return {
        "timestamps": timestamps,
        "auc": auc,
        "f1": f1,
        "run_ids": run_ids,
    }


@app.get("/dashboard")
async def dashboard_page(request: Request, limit: int = 20, status: Optional[str] = None):
    """
    Dashboard HTML page with timeline chart.

    Renders the main dashboard with timeline visualization.
    """
    manager = RunManager()
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)

    # Apply client-side filtering for status (defensive in case RunManager doesn't respect filter)
    if status:
        runs = [run for run in runs if run.status == status]

    # Ensure we don't exceed the limit
    runs = runs[:limit] if len(runs) > limit else runs

    # ADR-0001: per-type counts so the dashboard can show the run-type mix.
    # The timeline itself is training-only (AUC/F1), so the counts make the
    # scope of the chart legible at a glance.
    run_counts = {bucket: 0 for bucket in _RUN_TYPE_BUCKETS}
    for run in runs:
        run_counts[_resolve_run_type(run)] += 1

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "runs": runs,
            "limit": limit,
            "status": status,
            "run_counts": run_counts,
            "run_type_buckets": _RUN_TYPE_BUCKETS,
        },
    )


# ==================== Phase 4: Comparison View ====================


def _parse_and_validate_run_ids(ids_str: str, max_count: int = 10) -> List[str]:
    """
    Parse comma-separated run IDs with validation.

    Args:
        ids_str: Comma-separated run IDs string
        max_count: Maximum number of IDs allowed (default 10)

    Returns:
        List of validated run IDs

    Raises:
        HTTPException(400): If validation fails
    """
    if not ids_str:
        raise HTTPException(status_code=400, detail="ids parameter required")

    raw_ids = ids_str.split(",")
    if len(raw_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")
    if len(raw_ids) > max_count:
        raise HTTPException(status_code=400, detail=f"Maximum {max_count} run IDs allowed")

    validated = []
    for run_id in raw_ids:
        run_id = run_id.strip()
        if not run_id:
            continue
        # Defense in depth: block path traversal AND cap length (DoS hardening —
        # without a cap a single huge id could dominate memory/string work).
        if ".." in run_id or "/" in run_id or "\\" in run_id:
            raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id}")
        if len(run_id) > 256:
            raise HTTPException(status_code=400, detail="run_id too long (max 256 chars)")
        validated.append(run_id)

    if len(validated) < 2:
        raise HTTPException(status_code=400, detail="At least 2 valid run IDs required")

    return validated


def _load_run_evaluations_batch(run_ids: List[str]) -> Dict[str, Dict]:
    """
    Load evaluation data for multiple runs, tolerant to missing files.

    Args:
        run_ids: List of run IDs to load evaluation data for

    Returns:
        Dictionary mapping run_id to normalized evaluation data.
        Runs with missing evaluation data are omitted from the result.

    Uses _load_run_evaluation internally for consistency with single/multi-model normalization.
    """
    results = {}

    for run_id in run_ids:
        eval_data = _load_run_evaluation(run_id)
        if eval_data:  # Skip runs without evaluation data
            results[run_id] = eval_data

    return results


def _load_threshold_data(
    run_id: str, manager: Optional[RunManager] = None
) -> Optional[Dict[str, Any]]:
    """
    Load threshold sweep and cumulative gains data directly from eval JSON.

    Bypasses _load_run_evaluation because it normalizes away threshold_metrics.
    Reads evaluation_report.json directly; returns null for ensemble runs
    (comparison.json does not contain threshold_metrics per current schema).

    Args:
        run_id: Run identifier
        manager: Optional RunManager (project-scoped). Defaults to a Global one.

    Returns:
        Dictionary with:
            - threshold_metrics: {thresholds, precisions, recalls, f1s} or null
            - cumulative_gains: {deciles, cumulative_gain, cumulative_population} or null
            - current_threshold: float from metrics.threshold
            - available_models: list of model names if ensemble, null otherwise
            - is_multi: bool
        None if run not found or report missing
    """
    resolved = _resolve_evaluation_files(run_id, manager)
    if not resolved:
        return None
    comparison_path, report_path = resolved

    # Check for multi-model first (ensemble detection)
    if comparison_path.is_file():
        try:
            data = json.loads(comparison_path.read_text(encoding="utf-8"))
            # Extract available models from ranking
            ranking = data.get("ranking", [])
            available_models = [
                item.get("name") for item in ranking if isinstance(item, dict) and "name" in item
            ]
            return {
                "threshold_metrics": None,  # Not available in comparison.json
                "cumulative_gains": None,
                "current_threshold": None,
                "available_models": available_models,
                "is_multi": True,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {comparison_path} for run {run_id}: {e}")

    # Single-model: read evaluation_report.json directly
    if report_path.is_file():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            metrics = data.get("metrics", {})
            return {
                "threshold_metrics": data.get("threshold_metrics"),  # May be None for old runs
                "cumulative_gains": metrics.get("cumulative_gains"),  # May be None for old runs
                "current_threshold": metrics.get("threshold", 0.5),
                "available_models": None,
                "is_multi": False,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {report_path} for run {run_id}: {e}")

    return None


@app.get("/api/runs/compare")
async def compare_runs_json(ids: str = ""):
    """
    Comparison API endpoint for run comparison data.

    Returns JSON with evaluation data for multiple runs.
    Supports both single-model and multi-model runs.

    ADR-0001 (Phase 4): cross-type Run sets are rejected with HTTP 409 (the
    page surface renders a banner for the same condition). Homogeneous sets
    echo ``run_type`` at the top level so clients can branch like the template.
    """
    # Parse and validate run IDs
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)

    # ADR-0001: resolve each Run's type before eval-data filtering so mixed-type
    # sets are rejected rather than silently narrowed to training runs.
    manager = RunManager()
    run_meta_by_id, run_types = _load_compare_run_types(run_ids, manager)

    if len(set(run_types.values())) > 1:
        # Typed empty-state: runs exist but are not comparable. 409 (Conflict)
        # communicates "request well-formed, but this comparison is invalid."
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Runs are of different types and cannot be compared",
                "run_types": run_types,
            },
        )

    run_type = next(iter(set(run_types.values())))

    # Load evaluation data for all runs (tolerant to missing files)
    eval_data_dict = _load_run_evaluations_batch(run_ids)

    # If all runs missing evaluation data, return 404
    if not eval_data_dict:
        raise HTTPException(
            status_code=404, detail="No evaluation data found for any of the specified runs"
        )

    # Build response with run metadata and evaluation data
    results = {}

    for run_id in run_ids:
        # Skip runs without evaluation data (already omitted from eval_data_dict)
        if run_id not in eval_data_dict:
            continue

        # Get run metadata (already loaded during type resolution; avoids a
        # second get_run round-trip per run).
        run = run_meta_by_id.get(run_id)
        if not run:
            continue

        # Get evaluation data
        eval_data = eval_data_dict[run_id]

        # Build response entry
        results[run_id] = {
            "run_metadata": run.to_dict(),
            "evaluation": eval_data,
            "available_models": eval_data.get("ranking") if eval_data.get("is_multi") else None,
            "is_multi": eval_data.get("is_multi", False),
        }

    return {"runs": results, "run_type": run_type}


@app.get("/api/runs/{run_id}/thresholds")
async def get_threshold_sweep(run_id: str):
    """
    Threshold exploration data API endpoint.

    Returns threshold sweep and cumulative gains data for a run.
    Supports graceful degradation for ensemble runs and old runs lacking threshold data.

    Args:
        run_id: Run identifier

    Returns:
        JSON with threshold_metrics, cumulative_gains, current_threshold, available_models, is_multi
        404 if run not found or evaluation data missing
    """
    manager = RunManager()

    # Validate run exists
    run = manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Load threshold data
    threshold_data = _load_threshold_data(run_id)

    # Return 404 if no evaluation data found
    if not threshold_data:
        raise HTTPException(status_code=404, detail="Evaluation data not found")

    return threshold_data


# ============================================================================
# PHASE 1 (multi-project): Project registry + project-scoped routes
# ============================================================================
#
# The un-scoped routes above (/jobs, /runs, /dashboard) remain as the legacy
# "Global" view. The routes below scope jobs/runs to a specific registered
# project via /projects/{project_id}/... . project_id is ALWAYS resolved through
# ProjectService before any filesystem use — raw filesystem paths never appear
# in URLs.


def _require_project(project_id: str):
    """
    Resolve a project_id via ProjectService, 404 if unknown or path invalid.

    Args:
        project_id: URL-safe project slug.

    Returns:
        ``(project, project_service)``.

    Raises:
        HTTPException(404): If the project is not registered or its directory is
            no longer valid on disk.
    """
    ps = _project_service()
    project = ps.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project, ps


@app.get("/projects")
async def list_projects(request: Request):
    """
    List all registered projects (card grid home) with per-project stats.

    Each card shows: run count, the most recent run's status + val_auc, and the
    queue depth (QUEUED jobs) for that project's path.
    """
    ps = _project_service()
    projects = ps.list_projects()
    store = JobStore()

    projects_with_stats = []
    for project in projects:
        manager = _run_manager_for(project.project_id, ps)
        # list_runs() reads all run dirs from disk before applying the limit, so a
        # large limit gives an accurate count at no extra I/O cost. TODO(v0.5):
        # add a lightweight count() to RunManager to avoid per-project N+1 reads.
        runs = manager.list_runs(limit=1000)
        last_run = runs[0] if runs else None
        queued = store.list_jobs(status_filter=JobStatus.QUEUED, project_path=str(project.path))
        projects_with_stats.append(
            {
                "project": project,
                "run_count": len(runs),
                "last_run": last_run,
                "queue_depth": len(queued),
            }
        )

    return templates.TemplateResponse(
        request,
        "projects_list.html",
        {"projects": projects, "projects_with_stats": projects_with_stats},
    )


@app.post("/projects")
async def create_project_route(request: Request):
    """
    Create a new project under the workspace root.

    Form fields: ``name`` (required), ``template`` (optional, default "default").
    Returns an HTMX-friendly redirect/fragment.
    """
    from urllib.parse import urlencode

    ps = _project_service()
    form = await request.form()
    name = (form.get("name") or "").strip()
    template = (form.get("template") or "default").strip() or "default"

    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")

    try:
        project = ps.create_project(name=name, template=template)
    except (ValueError, FileExistsError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Redirect to the new project detail page
    return RedirectResponse(
        url=f"/projects/{project.project_id}?{urlencode({'created': '1'})}",
        status_code=303,
    )


@app.post("/projects/register")
async def register_project_route(request: Request):
    """
    Register an existing project directory by absolute path.

    Form fields: ``path`` (required), ``name`` (optional).
    """
    ps = _project_service()
    form = await request.form()
    raw_path = (form.get("path") or "").strip()
    name = (form.get("name") or "").strip() or None

    if not raw_path:
        raise HTTPException(status_code=400, detail="Path is required")

    try:
        project = ps.register_existing(Path(raw_path), name=name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RedirectResponse(url=f"/projects/{project.project_id}", status_code=303)


# Canonical Run-type buckets shown on the project hero page. The console groups
# Jobs and Runs by Run type (CONTEXT.md, Web Console). Since ADR-0001 Phase 2,
# RunMetadata carries a ``run_type`` discriminator and run dirs are typed
# (train-/etl-/eda-/inference-); the Job→Run ``config_type`` join remains as a
# fallback for legacy/CLI runs whose run_metadata.json predates run_type.
_RUN_TYPE_BUCKETS = ("etl", "eda", "inference", "training")


def _config_type_to_run_type(config_type: Optional[str]) -> str:
    """Map a Job ``config_type`` to a canonical Run-type bucket.

    ``config_type`` is a validation label (etl / train / eda / infer). Unknown
    values default to ``training`` — the dominant run type in practice and the
    from_dict default for RunMetadata.run_type.
    """
    mapping = {"etl": "etl", "eda": "eda", "infer": "inference", "train": "training"}
    ct = (config_type or "").strip().lower()
    return mapping.get(ct, "training")


def _resolve_run_type(run: Optional[Any], fallback: Optional[Dict[str, str]] = None) -> str:
    """Resolve a Run's type for Compare scoping (ADR-0001).

    Prefers ``RunMetadata.run_type`` (the canonical signal since Phase 2 — every
    finalized typed Run carries it, and RunMetadata.from_dict defaults legacy
    files to "training"). Falls back to the producing Job's ``config_type``
    joined via run_id for old/CLI runs whose run_metadata.json predates run_type.
    Defaults to "training" when neither signal is available, preserving the
    pre-Phase-4 UI where every compare was a training compare.
    """
    rt = getattr(run, "run_type", None)
    if isinstance(rt, str) and rt:
        return rt
    if run is not None and fallback:
        return _config_type_to_run_type(fallback.get(getattr(run, "run_id", None)))
    return "training"


def _primary_output_label(run: Any) -> Optional[str]:
    """Short label for the primary artifact a non-training Run produced.

    Used by the global ``/runs`` index to communicate what each etl/eda/
    inference run actually generated. Returns ``None`` for training runs and
    for non-training runs that recorded no output artifact. The label is a
    stable, human-readable summary (not the raw filesystem path).
    """
    op = getattr(run, "output_paths", {}) or {}
    rt = _resolve_run_type(run)
    if rt == "eda" and op.get("eda_report"):
        return "EDA report"
    if rt == "inference" and op.get("inference_predictions"):
        return "Predictions"
    if rt == "etl":
        etl_keys = [k for k in op if k.startswith("etl_")]
        if etl_keys:
            return f"ETL: {etl_keys[0][len('etl_') :]}"
    return None


def _run_type_fallback_map() -> Dict[str, str]:
    """Best-effort ``{run_id: config_type}`` from recent jobs (legacy type fallback).

    Only consulted when a Run lacks a canonical ``run_type``. Skipped when the
    jobs database does not yet exist so the global Compare read-path never
    creates a stray DB; the worker owns DB creation. Returns ``{}`` on any error
    so Compare degrades to the "training" default rather than failing.
    """
    db_path = Path(os.environ.get("ENERGIZADOS_JOBS_DB") or "data/web/jobs.db")
    if not db_path.exists():
        return {}
    try:
        jobs = JobStore().list_jobs(limit=500)
        return {j.run_id: j.config_type for j in jobs if j.run_id}
    except Exception:
        logger.warning("run-type fallback map unavailable; defaulting to training", exc_info=True)
        return {}


def _load_compare_run_types(run_ids: List[str], manager: "RunManager") -> tuple:
    """Resolve ``(run_metadata, run_type)`` for each requested Run (ADR-0001).

    Two-pass: read RunMetadata.run_type first and only build the job-join
    fallback map when some Run lacks a canonical type (avoids a DB read on the
    all-typed common path). Returns ``run_meta_by_id`` (run_id → RunMetadata or
    None) and ``run_types`` (run_id → resolved type string).
    """
    run_meta_by_id: Dict[str, Any] = {}
    raw: Dict[str, Optional[str]] = {}
    for run_id in run_ids:
        run = manager.get_run(run_id)
        run_meta_by_id[run_id] = run
        rt = getattr(run, "run_type", None)
        raw[run_id] = rt if isinstance(rt, str) and rt else None
    if any(v is None for v in raw.values()):
        fallback = _run_type_fallback_map()
        run_types: Dict[str, str] = {
            rid: (rt if rt is not None else _config_type_to_run_type(fallback.get(rid)))
            for rid, rt in raw.items()
        }
    else:
        run_types = {rid: rt for rid, rt in raw.items()}  # type: ignore[misc]
    return run_meta_by_id, run_types


@app.get("/projects/{project_id}")
async def project_detail(request: Request, project_id: str):
    """Project hero page: the at-a-glance landing for a Project.

    Sections: header with key counts, Jobs/Runs grouped by Run type, the latest
    training summary (metrics + model types), and a lineage placeholder. The
    YAML editor scoped to the project remains available further down the page.
    """
    project, ps = _require_project(project_id)
    store = JobStore()
    # Wider window than the old limit=20 so the type-grouped tables have enough
    # context; each table is capped in the template.
    jobs = store.list_jobs(project_path=str(project.path), limit=100)
    manager = _run_manager_for(project_id, ps)
    runs = manager.list_runs(limit=100)

    # Authoritative run-type signal (ADR-0001): prefer the type recorded in the
    # Run's own metadata; fall back to the producing Job's config_type joined via
    # run_id (for old/CLI runs whose run_metadata.json predates run_type). Old
    # training files load as run_type=="training" via RunMetadata.from_dict.
    run_type_by_run_id = {j.run_id: j.config_type for j in jobs if j.run_id}

    def _run_type(run) -> str:
        # RunMetadata.run_type is the canonical signal once a run is finalized
        # with the typed schema. "training" is the from_dict default, so legacy
        # runs without the key land in the training bucket (preserving old UI).
        if getattr(run, "run_type", None):
            return run.run_type
        return _config_type_to_run_type(run_type_by_run_id.get(run.run_id))

    job_groups = {bucket: [] for bucket in _RUN_TYPE_BUCKETS}
    for job in jobs:
        job_groups[_config_type_to_run_type(job.config_type)].append(job)

    run_groups = {bucket: [] for bucket in _RUN_TYPE_BUCKETS}
    for run in runs:
        run_groups[_run_type(run)].append(run)

    # Latest training run + its evaluation summary. Full metrics (incl. precision
    # and recall) live in the evaluation report loaded by _load_run_evaluation;
    # RunMetadata only carries val_auc / val_f1.
    latest_training = next((r for r in runs if _run_type(r) == "training"), None)
    latest_training_eval = (
        _load_run_evaluation(latest_training.run_id, manager)
        if latest_training is not None
        else None
    )
    latest_job = jobs[0] if jobs else None

    # ADR-0003 lineage: walk the latest training run's derived_from chain via
    # RunManager.get_run until a run has no parent. O(depth) — fine for typical
    # retrain depth. The chain is ordered root→leaf; lineage_available is True
    # only when at least one member has a derived_from link (a real retrain).
    # A purged ancestor (get_run returns None) ends the walk cleanly.
    lineage_chain: List[Any] = []
    if latest_training is not None:
        seen: set = set()
        current = latest_training
        while current is not None and current.run_id not in seen:
            seen.add(current.run_id)
            lineage_chain.append(current)
            parent_id = getattr(current, "derived_from", None)
            if not parent_id:
                break
            current = manager.get_run(parent_id)
        lineage_chain.reverse()  # root→leaf
    lineage_available = any(getattr(r, "derived_from", None) for r in lineage_chain)

    return templates.TemplateResponse(
        request,
        "project_detail.html",
        {
            "project": project,
            "project_id": project.project_id,
            # Preserved keys (backward-compat data contract):
            "jobs": jobs[:20],
            "runs": runs[:20],
            "submit_url": f"/projects/{project.project_id}/jobs",
            # Hero additions:
            "job_groups": job_groups,
            "run_groups": run_groups,
            "run_type_buckets": _RUN_TYPE_BUCKETS,
            "latest_training": latest_training,
            "latest_training_eval": latest_training_eval,
            "latest_job": latest_job,
            "jobs_total": len(jobs),
            "runs_total": len(runs),
            # ADR-0003 Run→Run retrain lineage (root→leaf); empty list when the
            # latest training run has no derived_from chain.
            "lineage_available": lineage_available,
            "lineage_chain": lineage_chain,
        },
    )


@app.get("/projects/{project_id}/config/{type}")
async def get_project_config(project_id: str, type: str):
    """
    Serve a project's real ``config/{type}.yaml`` as ``text/yaml``.

    Used by the editor's "Load from project config" control to prefill the YAML
    textarea with the project's actual config file.

    Security (layered):
        1. ``project_id`` resolved via ``_require_project`` (404 if unknown).
        2. ``type`` must match ``^[A-Za-z0-9_]+$`` — rejects ``/``, ``\\``,
           ``..``, dots, and any non-filename character (404 otherwise).
        3. The resolved path is anchored under the project's ``config/`` dir
           via ``relative_to`` (defense-in-depth against symlink escapes).
        4. 404 if the file does not exist (no directory listing).

    Args:
        project_id: URL-safe project slug.
        type: Config basename (without ``.yaml``), e.g. ``etl``, ``train``.

    Returns:
        ``FileResponse`` with ``media_type="text/yaml"``.
    """
    project, _ = _require_project(project_id)

    if not _CONFIG_TYPE_RE.match(type):
        raise HTTPException(status_code=404, detail="Invalid config type")

    config_dir = (Path(project.path) / "config").resolve()
    target = (config_dir / f"{type}.yaml").resolve()
    try:
        target.relative_to(config_dir)
    except ValueError:
        raise HTTPException(status_code=404, detail="Config not found")

    if not target.is_file():
        raise HTTPException(status_code=404, detail="Config not found")

    return FileResponse(target, media_type="text/yaml")


@app.get("/projects/{project_id}/jobs")
async def list_project_jobs(request: Request, project_id: str, status: str = None):
    """List jobs for a project (HTMX fragment, reuses job_list.html)."""
    project, _ = _require_project(project_id)
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            pass
    store = JobStore()
    jobs = store.list_jobs(status_filter=status_filter, project_path=str(project.path), limit=100)
    return templates.TemplateResponse(
        request, "job_list.html", {"jobs": jobs, "status_filter": status_filter}
    )


@app.post("/projects/{project_id}/jobs")
async def create_project_job(request: Request, project_id: str):
    """
    Create and enqueue a job scoped to a project.

    The job row stores ``project_path`` so the worker child ``os.chdir``s into
    the project directory before running.
    """
    project, _ = _require_project(project_id)
    is_htmx = request.headers.get("HX-Request") == "true"

    validated = await _validate_request_config(request, htmx_error_template="job_validation.html")
    config, config_type = validated.config, validated.config_type

    store = JobStore()
    job_id = store.create_job(config, config_type, project_path=str(project.path))

    if is_htmx:
        return templates.TemplateResponse(
            request,
            "job_created.html",
            {"job_id": job_id, "status": "queued", "config_type": config_type},
            status_code=201,
        )
    return JSONResponse(
        status_code=201,
        content={
            "job_id": job_id,
            "status": "queued",
            "config_type": config_type,
            "project_id": project.project_id,
        },
    )


@app.get("/projects/{project_id}/jobs/{job_id}")
async def get_project_job(project_id: str, job_id: str, request: Request):
    """Get job detail within a project."""
    project, _ = _require_project(project_id)
    store = JobStore()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return job.to_dict()
    return templates.TemplateResponse(request, "job_detail.html", {"job": job})


@app.post("/projects/{project_id}/jobs/{job_id}/cancel")
async def cancel_project_job(project_id: str, job_id: str):
    """Cancel a running job within a project."""
    _require_project(project_id)
    store = JobStore()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    cancelled = store.cancel_job(job_id)
    return {
        "job_id": job_id,
        "status": "aborted" if cancelled else job.status.value,
        "cancelled": cancelled,
    }


@app.post("/projects/{project_id}/jobs/{job_id}/retry")
async def retry_project_job(project_id: str, job_id: str):
    """Retry a terminal job within a project."""
    _require_project(project_id)
    store = JobStore()
    original_job = store.get_job(job_id)
    if original_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    new_job_id = store.retry_job(job_id)
    if new_job_id is None:
        raise HTTPException(
            status_code=400, detail=f"Cannot retry job with status: {original_job.status.value}"
        )
    return JSONResponse(
        status_code=201, content={"job_id": new_job_id, "status": "queued", "retried_from": job_id}
    )


@app.get("/projects/{project_id}/jobs/{job_id}/progress")
async def get_project_job_progress(project_id: str, job_id: str, request: Request):
    """SSE endpoint for live job progress (project-scoped). job_id is globally unique."""
    _require_project(project_id)
    # Delegate to the same SSE logic as the global route by reusing the handler.
    return await get_job_progress(job_id, request)


@app.get("/projects/{project_id}/runs")
async def list_project_runs(
    request: Request, project_id: str, status: Optional[str] = None, limit: int = 100
):
    """List runs for a project (scoped to <project>/output/)."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"runs": [run.to_dict() for run in runs]}
    return templates.TemplateResponse(
        request,
        "runs_list.html",
        {
            "runs": runs,
            "status_filter": status,
            "limit": limit,
            "project_id": project.project_id,
        },
    )


@app.get("/projects/{project_id}/runs/compare")
async def compare_project_runs_page(request: Request, project_id: str, ids: str = ""):
    """Comparison page for side-by-side run comparison (project-scoped)."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)
    eval_data_dict = _load_run_evaluations_batch_scoped(run_ids, manager)
    if not eval_data_dict:
        raise HTTPException(
            status_code=404, detail="No evaluation data found for any of the specified runs"
        )
    runs_data = []
    for run_id in run_ids:
        if run_id not in eval_data_dict:
            continue
        eval_data = eval_data_dict[run_id]
        runs_data.append(
            {
                "run_id": run_id,
                "evaluation": eval_data,
                "available_models": eval_data.get("ranking") if eval_data.get("is_multi") else None,
                "is_multi": eval_data.get("is_multi", False),
            }
        )
    if not runs_data:
        raise HTTPException(status_code=404, detail="No valid runs found")
    best = {"auc": None, "f1": None, "precision": None, "recall": None}
    best_val = {k: float("-inf") for k in best}
    for entry in runs_data:
        if entry["is_multi"]:
            continue
        metrics = (entry["evaluation"] or {}).get("metrics") or {}
        for key in best:
            value = metrics.get(key)
            if isinstance(value, (int, float)) and value > best_val[key]:
                best_val[key] = value
                best[key] = entry["run_id"]
    return templates.TemplateResponse(
        request,
        "compare_runs.html",
        {
            "runs": runs_data,
            "ids": ids,
            "best": best,
            "comparison_json": json.dumps(runs_data)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e"),
        },
    )


@app.get("/projects/{project_id}/runs/{run_id}/artifacts/{path:path}")
async def get_project_artifact(project_id: str, run_id: str, path: str):
    """
    Serve run artifacts scoped to a project's output dir, with traversal guards.

    Reuses the same layered guard as the global artifact route, but anchored on
    the project-scoped RunManager's output base.
    """
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)

    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _resolve_run_dir(manager, run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run directory not found")

    if ".." in path or path.startswith("/") or "\\" in path:
        raise HTTPException(status_code=403, detail="Invalid path")

    try:
        artifact_path = (run_dir / path).resolve()
    except (OSError, ValueError) as e:
        logger.error(f"Error resolving artifact path: {e}")
        raise HTTPException(status_code=400, detail="Invalid artifact path")

    try:
        artifact_path.relative_to(run_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal detected")

    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    media_type = _guess_media_type(artifact_path)
    cache_control = "public, max-age=3600" if _is_cacheable(artifact_path) else None
    return FileResponse(
        artifact_path,
        media_type=media_type,
        headers={"Cache-Control": cache_control} if cache_control else {},
    )


@app.get("/projects/{project_id}/runs/{run_id}")
async def get_project_run_detail(project_id: str, run_id: str, request: Request):
    """Run detail page scoped to a project (reuses run_detail.html)."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    evaluation = _load_run_evaluation(run_id, manager)
    threshold_unavailable_message = None
    threshold_data = _load_threshold_data(run_id, manager)
    if threshold_data:
        if threshold_data.get("is_multi"):
            threshold_unavailable_message = (
                "Threshold exploration is not available for ensemble runs."
            )
        elif threshold_data.get("threshold_metrics") is None:
            threshold_unavailable_message = (
                "This run predates threshold sweep data. Re-run evaluation to generate it."
            )

    config_files = _list_run_configs(run, manager)
    has_log = _has_run_log(run, manager)
    eda_relative_path = None
    if run.output_paths.get("eda_report"):
        try:
            eda_relative_path = _get_artifact_relative_path(
                run, run.output_paths["eda_report"], manager
            )
        except ValueError:
            pass

    pid = project.project_id
    runs_base = f"/projects/{pid}/runs"
    api_base = f"/projects/{pid}/api/runs"
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run": run,
            "evaluation": evaluation,
            "config_files": config_files,
            "has_log": has_log,
            "log_content": _read_run_log(run, manager=manager) if has_log else None,
            "eda_relative_path": eda_relative_path,
            "threshold_unavailable_message": threshold_unavailable_message,
            "project_id": pid,
            "runs_base": runs_base,
            "api_base": api_base,
        },
    )


@app.get("/projects/{project_id}/dashboard")
async def project_dashboard(
    request: Request, project_id: str, limit: int = 20, status: Optional[str] = None
):
    """Per-project dashboard (reuses dashboard.html with project-scoped runs)."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    if status:
        runs = [run for run in runs if run.status == status]
    runs = runs[:limit] if len(runs) > limit else runs
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"runs": runs, "limit": limit, "status": status, "project_id": project.project_id},
    )


@app.get("/projects/{project_id}/api/dashboard/timeline")
async def project_timeline_data(project_id: str, limit: int = 100, status: Optional[str] = None):
    """Timeline data API scoped to a project's runs."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    filter_dict = {"status": status} if status else None
    runs = manager.list_runs(filter=filter_dict, limit=limit)
    if status:
        runs = [run for run in runs if run.status == status]
    runs = runs[:limit] if len(runs) > limit else runs
    # ADR-0001: AUC/F1 are training-only metrics — scope to training runs so
    # non-training runs don't inject None points. Reuses _resolve_run_type.
    training_runs = [run for run in runs if _resolve_run_type(run) == "training"]
    # RunMetadata.timestamp is already a serialized ISO string — use it
    # verbatim (.isoformat() only works on a datetime and 500s on real runs).
    timestamps = [run.timestamp or None for run in training_runs]
    auc = [run.val_auc for run in training_runs]
    f1 = [run.val_f1 for run in training_runs]
    run_ids = [run.run_id for run in training_runs]
    return {"timestamps": timestamps, "auc": auc, "f1": f1, "run_ids": run_ids}


@app.get("/projects/{project_id}/api/runs/{run_id}/thresholds")
async def get_project_threshold_sweep(project_id: str, run_id: str):
    """Threshold sweep data scoped to a project's run."""
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    run = manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    threshold_data = _load_threshold_data(run_id, manager)
    if not threshold_data:
        raise HTTPException(status_code=404, detail="Evaluation data not found")
    return threshold_data


# ---------------------------------------------------------------------------
# Phase 3 — Retrain + Inference UX (project-scoped)
# ---------------------------------------------------------------------------


def _eligible_inference_runs(manager: RunManager) -> List[Dict[str, str]]:
    """Runs that can provide a trained model for inference.

    A run is eligible when its metadata advertises ``output_paths.model`` and
    its run directory still exists on disk.

    Args:
        manager: A project-scoped RunManager.

    Returns:
        List of ``{"run_id", "label"}`` dicts (most-recent first, as returned
        by ``list_runs``).
    """
    eligible: List[Dict[str, str]] = []
    for run in manager.list_runs(limit=100):
        if not run.output_paths.get("model"):
            continue
        if not _resolve_run_dir(manager, run.run_id):
            continue
        model_types = getattr(run, "model_types", None) or []
        label = f"{run.run_id} ({', '.join(model_types)})" if model_types else run.run_id
        eligible.append({"run_id": run.run_id, "label": label})
    return eligible


def _list_processed_input_files(project_path: Path) -> List[str]:
    """List non-recursive ``.parquet``/``.csv`` files under ``data/processed/``.

    The directory is built from the trusted project path (no user input), so
    there is no traversal risk in the listing itself; this returns
    project-relative paths (e.g. ``data/processed/foo.parquet``).

    Args:
        project_path: Absolute path to the project root.

    Returns:
        Sorted list of project-relative input file paths. Empty if the
        directory does not exist.
    """
    base = project_path / "data" / "processed"
    if not base.is_dir():
        return []
    proj_resolved = Path(project_path).resolve()
    files: List[str] = []
    for entry in sorted(base.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in (".parquet", ".csv"):
            continue
        try:
            rel = entry.resolve().relative_to(proj_resolved)
        except (ValueError, OSError):
            continue
        files.append(rel.as_posix())
    return files


def _validate_processed_input_path(
    project_path: Path, input_path: str, request: Request, is_htmx: bool
) -> str:
    """Validate that ``input_path`` is a file strictly under ``data/processed/``.

    Args:
        project_path: Absolute path to the project root.
        input_path: Project-relative path submitted by the user.
        request: The current request (for rendering an HTMX error fragment).
        is_htmx: Whether the request is an HTMX request.

    Returns:
        The validated project-relative input path.

    Raises:
        HTTPException(400): For non-HTMX requests on any violation.
        _HtmxErrorResponse: For HTMX requests (renders ``job_validation.html``).
    """

    def _fail(message: str) -> None:
        if is_htmx:
            _raise_htmx_error(request, "job_validation.html", errors=[message])
        raise HTTPException(status_code=400, detail=message)

    if not input_path:
        _fail("input_path is required")
    if ".." in input_path or input_path.startswith("/") or "\\" in input_path:
        _fail("Invalid input path")

    base = (project_path / "data" / "processed").resolve()
    try:
        target = (project_path / input_path).resolve()
    except (OSError, ValueError):
        _fail("Invalid input path")
        return ""  # pragma: no cover - _fail always raises
    try:
        target.relative_to(base)
    except ValueError:
        _fail("Invalid input path")
        return ""  # pragma: no cover - _fail always raises

    if not target.is_file():
        _fail("Input file not found")
    return input_path


@app.post("/projects/{project_id}/runs/{run_id}/retrain")
async def retrain_from_run(request: Request, project_id: str, run_id: str):
    """
    Re-enqueue a run from its saved configs.

    Reads every YAML file in ``<run_dir>/config/`` (typically ``etl.yaml`` +
    ``train.yaml``), deep-merges them, validates the merged config as ``train``,
    and enqueues a new job scoped to the project.

    Execution semantics (verified against ``PipelineDirector.build`` /
    ``ConfigPipelineBuilder``): ``config_type='train'`` is only a web-layer /
    schema-validation label. The worker builds the pipeline from the merged
    config DICT, and ``PipelineDirector.build`` adds a step for every ENABLED
    section it finds — including ``etl:``. So retrain re-runs the run's full
    effective merged config (ETL + split + train + evaluation), NOT training
    alone. Caveat: because ETL re-runs, the run's original source/input files
    must still be present; a run whose ETL used ``CleanFilesETL`` to delete its
    own inputs may not be retrainable.
    """
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    run_dir = _resolve_run_dir(manager, run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run directory not found")

    is_htmx = request.headers.get("HX-Request") == "true"

    config_dir = run_dir / "config"
    config_names = _list_run_configs(run, manager)
    if not config_names:
        msg = "Run has no saved configs to retrain from"
        if is_htmx:
            _raise_htmx_error(request, "job_validation.html", errors=[msg])
        raise HTTPException(status_code=400, detail=msg)

    configs: List[Dict[str, Any]] = []
    for name in config_names:
        try:
            with open(config_dir / name, encoding="utf-8") as f:
                parsed = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"[retrain run {run_id}] Failed to read config '{name}': {e}")
            msg = f"Failed to read config '{name}': {e}"
            if is_htmx:
                _raise_htmx_error(request, "job_validation.html", errors=[msg])
            raise HTTPException(status_code=400, detail=msg)
        if isinstance(parsed, dict):
            configs.append(parsed)

    if not configs:
        msg = "Run has no saved configs to retrain from"
        if is_htmx:
            _raise_htmx_error(request, "job_validation.html", errors=[msg])
        raise HTTPException(status_code=400, detail=msg)

    merged = merge_configs(configs)

    result = validate_dict(merged, "train")
    if not result.is_valid:
        errors = [e.message if hasattr(e, "message") else str(e) for e in result.errors]
        if is_htmx:
            _raise_htmx_error(request, "job_validation.html", errors=errors)
        raise HTTPException(status_code=400, detail="; ".join(errors))

    # Security: enforce the same custom_class trust boundary as POST /jobs.
    # The configs are disk-sourced (not user-typed), but the guard keeps the
    # retrain path consistent with /jobs and the documented allowlist policy.
    invalid_prefixes = _check_custom_class_prefixes(merged)
    if invalid_prefixes:
        allowed_prefixes = ["energizados.*", "src.*"]
        if is_htmx:
            _raise_htmx_error(
                request,
                "job_validation.html",
                invalid_prefixes=invalid_prefixes,
                allowed_prefixes=allowed_prefixes,
            )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "custom_class_prefix_validation",
                "message": f"Disallowed custom_class prefixes: {invalid_prefixes}",
                "invalid_prefixes": invalid_prefixes,
                "allowed_prefixes": allowed_prefixes,
            },
        )

    store = JobStore()
    # ADR-0003: stamp the SOURCE run_id (the URL path param) as the new job's
    # derived_from_run_id. The worker threads this to
    # ConfigPipelineBuilder(derived_from=...) so the re-run records its lineage
    # in run_metadata.json["derived_from"] at finalization (Phase 2 passthrough).
    job_id = store.create_job(
        merged, "train", project_path=str(project.path), derived_from_run_id=run_id
    )

    if is_htmx:
        return templates.TemplateResponse(
            request,
            "job_created.html",
            {"job_id": job_id, "status": "queued", "config_type": "train"},
            status_code=201,
        )
    return JSONResponse(
        status_code=201,
        content={
            "job_id": job_id,
            "status": "queued",
            "config_type": "train",
            "project_id": project.project_id,
        },
    )


@app.get("/projects/{project_id}/runs/{run_id}/inference")
async def inference_form(request: Request, project_id: str, run_id: str):
    """
    Render the inference form (HTMX fragment) or describe its data as JSON.

    Lists runs eligible to provide a model (those with ``output_paths.model``
    and an existing run dir) and the input files under the project's
    ``data/processed/`` directory. The context ``run_id`` (from the URL) is the
    default-selected model source when it is itself eligible.
    """
    project, ps = _require_project(project_id)
    manager = _run_manager_for(project_id, ps)
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    is_htmx = request.headers.get("HX-Request") == "true"

    eligible_runs = _eligible_inference_runs(manager)
    # Stable sort: bring the context run to the front if it is eligible.
    eligible_runs.sort(key=lambda item: item["run_id"] != run_id)

    input_files = _list_processed_input_files(project.path)

    if not is_htmx:
        return JSONResponse(
            status_code=200,
            content={
                "project_id": project.project_id,
                "context_run_id": run_id,
                "eligible_runs": eligible_runs,
                "input_files": input_files,
            },
        )

    return templates.TemplateResponse(
        request,
        "inference_form.html",
        {
            "project_id": project.project_id,
            "context_run_id": run_id,
            "eligible_runs": eligible_runs,
            "input_files": input_files,
            "threshold": 0.5,
        },
    )


@app.post("/projects/{project_id}/inference")
async def create_inference_job(request: Request, project_id: str):
    """
    Enqueue an inference job from a chosen trained run + input file.

    Form fields: ``model_run_id`` (a run with a trained model), ``input_path``
    (a file under ``data/processed/``), and ``threshold`` (float in [0, 1],
    default 0.5). The ``model_path`` is built relative to the project cwd so the
    worker (which ``os.chdir``s into the project) resolves it correctly.
    ``feature_engineering_path`` is intentionally omitted: ``InferenceBuilder``
    auto-detects ``feature_engineering.pkl`` from the model's directory.
    """
    project, ps = _require_project(project_id)
    is_htmx = request.headers.get("HX-Request") == "true"

    form = await request.form()
    model_run_id = (form.get("model_run_id") or "").strip()
    input_path = (form.get("input_path") or "").strip()
    threshold_raw = (form.get("threshold") or "0.5").strip()

    manager = _run_manager_for(project_id, ps)

    def _fail(message: str) -> None:
        if is_htmx:
            _raise_htmx_error(request, "job_validation.html", errors=[message])
        raise HTTPException(status_code=400, detail=message)

    # Validate model_run_id: must reference a run with a trained model.
    run = manager.get_run(model_run_id) if model_run_id else None
    if run is None or not run.output_paths.get("model"):
        reason = "run not found" if run is None else "run has no trained model artifact"
        logger.warning(
            f"[inference project {project.project_id}] model_run_id "
            f"'{model_run_id}' ineligible: {reason}"
        )
        _fail("Selected run has no trained model")

    # Validate input_path: must resolve strictly under data/processed/ and exist.
    input_rel = _validate_processed_input_path(project.path, input_path, request, is_htmx)

    # Validate threshold: float in [0, 1].
    try:
        threshold = float(threshold_raw)
    except (TypeError, ValueError):
        threshold = None
    if threshold is None or threshold < 0.0 or threshold > 1.0:
        _fail(f"threshold must be a float in [0, 1], got {threshold_raw!r}")

    # Build the model path RELATIVE TO PROJECT CWD.
    run_dir = _resolve_run_dir(manager, model_run_id)
    if not run_dir:
        _fail("Selected run directory not found")
    model_abs = run_dir / run.output_paths["model"]
    try:
        model_rel = str(model_abs.relative_to(project.path))
    except ValueError:
        _fail("Model artifact is not located under the project directory")

    infer_config = {
        "infer": {
            "enabled": True,
            "model_path": model_rel,
            "input_path": input_rel,
            "threshold": threshold,
        }
    }

    result = validate_dict(infer_config, "infer")
    if not result.is_valid:
        errors = [e.message if hasattr(e, "message") else str(e) for e in result.errors]
        _fail("; ".join(errors))

    store = JobStore()
    job_id = store.create_job(infer_config, "infer", project_path=str(project.path))

    if is_htmx:
        return templates.TemplateResponse(
            request,
            "job_created.html",
            {"job_id": job_id, "status": "queued", "config_type": "infer"},
            status_code=201,
        )
    return JSONResponse(
        status_code=201,
        content={
            "job_id": job_id,
            "status": "queued",
            "config_type": "infer",
            "project_id": project.project_id,
        },
    )


def _load_run_evaluations_batch_scoped(run_ids: List[str], manager: RunManager) -> Dict[str, Dict]:
    """Load evaluation data for multiple runs using a specific (scoped) manager."""
    results = {}
    for run_id in run_ids:
        eval_data = _load_run_evaluation(run_id, manager)
        if eval_data:
            results[run_id] = eval_data
    return results
