"""
FastAPI web application for Energizados web console.

Thin layer over energizados.api and JobStore. No business logic here.
Implements Phase 1 endpoints (tasks 5.9-5.18) with HTMX support.
Implements Phase 2 endpoints (runs list, detail, artifact serving) with security guards.
"""

import asyncio
import json
import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from energizados.api import RunManager, format_error, validate_dict
from energizados.core.exceptions import ETLDependencyError
from energizados.core.pipeline import Pipeline
from energizados.web.models import JobStatus
from energizados.web.store import JobStore

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Energizados Web Console",
    description="Async job runner and web interface for Energizados ML framework",
    version="0.3.0",
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
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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
    Main page - render index.html (task 5.10).

    Returns:
        HTML page with YAML editor and job list interface
    """
    return templates.TemplateResponse(request, "index.html", {})


@app.post("/jobs")
async def create_job(request: Request):
    """
    Create and enqueue a new job (tasks 5.11, 5.12, 5.20).

    Expects YAML body and config_type parameter. Validates config via
    validate_dict() and checks custom_class prefixes before enqueue.

    Returns:
        JSON with job_id and status, or 400 with validation errors
        HTML fragments if HX-Request header is present (PR3 content negotiation)
    """
    # Check if HTMX request for content negotiation (PR3 UX fix)
    is_htmx = request.headers.get("HX-Request") == "true"

    # Parse + validate + security-check the request config (shared with POST /plan).
    # Raises HTTPException (JSON) or _HtmxErrorResponse (HTMX) on any validation error.
    validated = await _validate_request_config(request, htmx_error_template="job_validation.html")
    config, config_type = validated.config, validated.config_type

    # Create job in JobStore
    store = JobStore()
    job_id = store.create_job(config, config_type)

    # Return HTML for HTMX, JSON otherwise (PR3 content negotiation)
    if is_htmx:
        return templates.TemplateResponse(
            request,
            "job_created.html",
            {"job_id": job_id, "status": "queued", "config_type": config_type},
            status_code=201,
        )
    return JSONResponse(
        status_code=201, content={"job_id": job_id, "status": "queued", "config_type": config_type}
    )


@app.get("/jobs")
async def list_jobs(request: Request, status: str = None):
    """
    List jobs with optional status filter (task 5.13).

    Returns HTMX fragment for auto-refresh (every 2s).

    Args:
        request: FastAPI request
        status: Optional status filter (queued|running|success|failed|aborted)

    Returns:
        HTML fragment with job list table
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

    return templates.TemplateResponse(
        request, "job_list.html", {"jobs": jobs, "status_filter": status_filter}
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

    return templates.TemplateResponse(request, "job_detail.html", {"job": job})


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
    run_dir = manager.run_dir(run_id)
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

    # Return HTML template
    return templates.TemplateResponse(
        request, "runs_list.html", {"runs": runs, "status_filter": status, "limit": limit}
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


def _resolve_evaluation_files(run_id: str):
    """
    Resolve the on-disk evaluation JSON paths for a run.

    Shared by ``_load_run_evaluation`` and ``_load_threshold_data`` so the
    run lookup + run_dir resolution + eval-dir layout lives in one place
    (avoids the duplication that would otherwise re-appear per consumer).

    Args:
        run_id: Run identifier

    Returns:
        ``(comparison_path, report_path)`` tuple, or ``None`` if the run or its
        directory cannot be resolved. Paths are returned even if the files do
        not exist — callers check ``.is_file()`` to decide which to read.
    """
    manager = RunManager()
    if not manager.get_run(run_id):
        return None
    run_dir = manager.run_dir(run_id)
    if not run_dir:
        return None
    eval_dir = run_dir / "reports" / "evaluation"
    return eval_dir / "comparison.json", eval_dir / "evaluation_report.json"


def _load_run_evaluation(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Load evaluation JSON for a run, handling both single-model and multi-model structures.

    Args:
        run_id: Run identifier

    Returns:
        Normalized dict with:
        - ranking (if multi-model): List[{name, metrics, info}]
        - metrics (if single-model): Dict of metric names
        - best_model (if multi-model): str
        - is_multi: bool
        - None if no evaluation found
    """
    resolved = _resolve_evaluation_files(run_id)
    if not resolved:
        return None
    comparison_path, report_path = resolved

    # Try multi-model first
    if comparison_path.is_file():
        try:
            data = json.loads(comparison_path.read_text())
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
            data = json.loads(report_path.read_text())
            return {
                "metrics": data.get("metrics", {}),
                "model_info": data.get("model_info", {}),
                "is_multi": False,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load {report_path} for run {run_id}: {e}")

    return None


def _list_run_configs(run) -> List[str]:
    """
    List config filenames in run directory.

    Args:
        run: RunMetadata object

    Returns:
        List of config filenames
    """
    manager = RunManager()
    run_dir = manager.run_dir(run.run_id)
    if not run_dir:
        return []

    config_dir = run_dir / "config"
    if not config_dir.is_dir():
        return []

    return [f.name for f in config_dir.iterdir() if f.is_file()]


def _has_run_log(run) -> bool:
    """
    Check if run.log exists.

    Args:
        run: RunMetadata object

    Returns:
        True if log exists, False otherwise
    """
    manager = RunManager()
    run_dir = manager.run_dir(run.run_id)
    if not run_dir:
        return False

    return (run_dir / "run.log").is_file()


def _read_run_log(run, max_lines: int = 1000) -> str:
    """
    Read last N lines from run.log.

    Args:
        run: RunMetadata object
        max_lines: Maximum number of lines to read (default 1000)

    Returns:
        Log file contents as string
    """
    manager = RunManager()
    run_dir = manager.run_dir(run.run_id)
    if not run_dir:
        return "Log not found"

    log_path = run_dir / "run.log"
    if not log_path.is_file():
        return "Log not found"

    try:
        # Tail efficiently: deque with maxlen discards earlier lines as it
        # reads, so we never hold the full file in memory (bounded read).
        with open(log_path, "r") as f:
            tail = deque(f, maxlen=max_lines)
        if len(tail) < max_lines:
            return "".join(tail)
        return f"... (showing last {max_lines} lines)\n" + "".join(tail)
    except IOError as e:
        return f"Error reading log: {e}"


def _get_artifact_relative_path(run, absolute_path: str) -> str:
    """
    Convert absolute artifact path to relative path for artifact route.

    Args:
        run: RunMetadata object
        absolute_path: Absolute path to artifact

    Returns:
        Relative path for artifact route

    Raises:
        ValueError: If path is not within run directory
    """
    manager = RunManager()
    run_dir = manager.run_dir(run.run_id)
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

    NOTE: Declared BEFORE /runs/{run_id} so FastAPI does not swallow the literal
    "compare" segment as a run_id path parameter (route matching is order-sensitive).
    """
    # Parse and validate run IDs
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)

    # Load evaluation data for all runs (tolerant to missing files)
    eval_data_dict = _load_run_evaluations_batch(run_ids)

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
            "runs": runs_data,
            "ids": ids,
            "best": best,
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

    # Extract data from RunMetadata, preserving None values for missing metrics
    timestamps = [run.timestamp.isoformat() if run.timestamp else None for run in runs]
    auc = [run.val_auc for run in runs]
    f1 = [run.val_f1 for run in runs]
    run_ids = [run.run_id for run in runs]

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

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "runs": runs,
            "limit": limit,
            "status": status,
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


def _load_threshold_data(run_id: str) -> Optional[Dict[str, Any]]:
    """
    Load threshold sweep and cumulative gains data directly from eval JSON.

    Bypasses _load_run_evaluation because it normalizes away threshold_metrics.
    Reads evaluation_report.json directly; returns null for ensemble runs
    (comparison.json does not contain threshold_metrics per current schema).

    Args:
        run_id: Run identifier

    Returns:
        Dictionary with:
            - threshold_metrics: {thresholds, precisions, recalls, f1s} or null
            - cumulative_gains: {deciles, cumulative_gain, cumulative_population} or null
            - current_threshold: float from metrics.threshold
            - available_models: list of model names if ensemble, null otherwise
            - is_multi: bool
        None if run not found or report missing
    """
    resolved = _resolve_evaluation_files(run_id)
    if not resolved:
        return None
    comparison_path, report_path = resolved

    # Check for multi-model first (ensemble detection)
    if comparison_path.is_file():
        try:
            data = json.loads(comparison_path.read_text())
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
            data = json.loads(report_path.read_text())
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
    """
    # Parse and validate run IDs
    run_ids = _parse_and_validate_run_ids(ids, max_count=10)

    # Load evaluation data for all runs (tolerant to missing files)
    eval_data_dict = _load_run_evaluations_batch(run_ids)

    # If all runs missing evaluation data, return 404
    if not eval_data_dict:
        raise HTTPException(
            status_code=404, detail="No evaluation data found for any of the specified runs"
        )

    # Build response with run metadata and evaluation data
    manager = RunManager()
    results = {}

    for run_id in run_ids:
        # Skip runs without evaluation data (already omitted from eval_data_dict)
        if run_id not in eval_data_dict:
            continue

        # Get run metadata
        run = manager.get_run(run_id)
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

    return {"runs": results}


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
