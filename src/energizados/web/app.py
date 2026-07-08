"""
FastAPI web application for Energizados web console.

Thin layer over energizados.api and JobStore. No business logic here.
Implements Phase 1 endpoints (tasks 5.9-5.18) with HTMX support.
Implements Phase 2 endpoints (runs list, detail, artifact serving) with security guards.
"""

import json
import logging
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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

    # Get content type
    content_type = request.headers.get("content-type", "")

    # Parse YAML body
    body = await request.body()
    if not body:
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "job_validation.html",
                {
                    "errors": ["Empty request body"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
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
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "job_validation.html",
                {
                    "errors": [f"Invalid YAML or JSON: {str(e)}"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
        raise HTTPException(status_code=400, detail=f"Invalid YAML or JSON: {str(e)}")

    if not isinstance(config, dict):
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "job_validation.html",
                {
                    "errors": ["Config must be a dictionary"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="Config must be a dictionary")

    # Get config_type from query params
    config_type = request.query_params.get("config_type", "train")

    # Validate config via energizados.api
    validation_result = validate_dict(config, config_type)
    if not validation_result.is_valid:
        # Convert errors to JSON-serializable format
        errors = []
        for error in validation_result.errors or []:
            if hasattr(error, "__dict__"):
                errors.append(str(error))
            else:
                errors.append(error)

        if is_htmx:
            return templates.TemplateResponse(
                request,
                "job_validation.html",
                {"errors": errors, "invalid_prefixes": None, "allowed_prefixes": None},
                status_code=400,
            )
        raise HTTPException(
            status_code=400, detail={"errors": errors, "message": "Configuration validation failed"}
        )

    # Check custom_class prefixes for security
    invalid_prefixes = _check_custom_class_prefixes(config)
    if invalid_prefixes:
        allowed_prefixes = ["energizados.*", "src.*"]
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "job_validation.html",
                {
                    "errors": None,
                    "invalid_prefixes": invalid_prefixes,
                    "allowed_prefixes": allowed_prefixes,
                },
                status_code=400,
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

    # Get content type
    content_type = request.headers.get("content-type", "")

    # Parse YAML body
    body = await request.body()
    if not body:
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "components/validation.html",
                {
                    "errors": ["Empty request body"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
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
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "components/validation.html",
                {
                    "errors": [f"Invalid YAML or JSON: {str(e)}"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
        raise HTTPException(status_code=400, detail=f"Invalid YAML or JSON: {str(e)}")

    if not isinstance(config, dict):
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "components/validation.html",
                {
                    "errors": ["Config must be a dictionary"],
                    "invalid_prefixes": None,
                    "allowed_prefixes": None,
                },
                status_code=400,
            )
        raise HTTPException(status_code=400, detail="Config must be a dictionary")

    # Get config_type from query params
    config_type = request.query_params.get("config_type", "train")

    # Validate config via energizados.api
    validation_result = validate_dict(config, config_type)
    if not validation_result.is_valid:
        # Convert errors to JSON-serializable format
        errors = []
        for error in validation_result.errors or []:
            if hasattr(error, "__dict__"):
                errors.append(str(error))
            else:
                errors.append(error)

        if is_htmx:
            return templates.TemplateResponse(
                request,
                "components/validation.html",
                {"errors": errors, "invalid_prefixes": None, "allowed_prefixes": None},
                status_code=400,
            )
        raise HTTPException(
            status_code=400, detail={"errors": errors, "message": "Configuration validation failed"}
        )

    # Check custom_class prefixes for security
    invalid_prefixes = _check_custom_class_prefixes(config)
    if invalid_prefixes:
        allowed_prefixes = ["energizados.*", "src.*"]
        if is_htmx:
            return templates.TemplateResponse(
                request,
                "components/validation.html",
                {
                    "errors": None,
                    "invalid_prefixes": invalid_prefixes,
                    "allowed_prefixes": allowed_prefixes,
                },
                status_code=400,
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
        # Unexpected error
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
    manager = RunManager()
    run = manager.get_run(run_id)
    if not run:
        return None

    run_dir = manager.run_dir(run_id)
    if not run_dir:
        return None

    # Try multi-model first
    comparison_path = run_dir / "reports" / "evaluation" / "comparison.json"
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
            logger.error(f"Failed to load comparison.json: {e}")

    # Try single-model
    report_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"
    if report_path.is_file():
        try:
            data = json.loads(report_path.read_text())
            return {
                "metrics": data.get("metrics", {}),
                "model_info": data.get("model_info", {}),
                "is_multi": False,
            }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load evaluation_report.json: {e}")

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
        },
    )
