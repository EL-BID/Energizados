"""
FastAPI web application for Energizados web console.

Thin layer over energizados.api and JobStore. No business logic here.
Implements Phase 1 endpoints (tasks 5.9-5.18) with HTMX support.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from energizados.api import RunManager, validate_dict
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
    """
    # Get content type
    content_type = request.headers.get("content-type", "")

    # Parse YAML body
    body = await request.body()
    if not body:
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
        raise HTTPException(status_code=400, detail=f"Invalid YAML or JSON: {str(e)}")

    if not isinstance(config, dict):
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

        raise HTTPException(
            status_code=400, detail={"errors": errors, "message": "Configuration validation failed"}
        )

    # Check custom_class prefixes for security
    invalid_prefixes = _check_custom_class_prefixes(config)
    if invalid_prefixes:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "custom_class_prefix_validation",
                "message": f"Disallowed custom_class prefixes: {invalid_prefixes}",
                "invalid_prefixes": invalid_prefixes,
                "allowed_prefixes": ["energizados.*", "src.*"],
            },
        )

    # Create job in JobStore
    store = JobStore()
    job_id = store.create_job(config, config_type)

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
async def list_runs():
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
