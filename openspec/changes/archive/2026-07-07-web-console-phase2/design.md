# Design — web-console-phase2

> **SDD change**: `web-console-phase2` — Phase 2: runs list + detail views + artifact serving + EDA embed
> **Status**: design
> **Author**: SDD design phase
> **Date**: 2026-07-06

## Executive Summary

Thin **read-only FastAPI view layer** over existing `RunManager` APIs — no framework core modifications, no worker changes, no new infrastructure. Three new routes (`GET /runs`, `GET /runs/{run_id}`, `GET /runs/{run_id}/artifacts/{path:path})` serve Jinja2 templates and guarded file responses, enabling operators to browse historical runs, inspect evaluation metrics (single-model and multi-model), view plots, embed EDA reports via iframe, and read config files + logs. Artifact serving uses path-traversal guards validated by `RunManager.get_run()` before resolving files. All changes are contained to `src/energizados/web/app.py` + two new templates.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (HTMX)                             │
│  - View runs list (paginated, filterable)                           │
│  - Inspect run detail (metrics, plots, EDA, configs, log)            │
│  - Download artifacts (plots, reports)                               │
└──────────────────────────┬────────────────────────────────────────┘
                           │ HTTP / HTMX
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Web Process (EXISTING)                   │
│  (src/energizados/web/app.py)                                      │
│                                                                       │
│  ┌───────────────────────────────────────────────────┐             │
│  │           Existing Routes (Phase 1)               │             │
│  │  POST /jobs, GET /jobs, POST /jobs/{id}/cancel   │             │
│  └───────────────────────────────────────────────────┘             │
│                                                                       │
│  ┌───────────────────────────────────────────────────┐             │
│  │         NEW Routes (Phase 2 - this change)         │             │
│  │  GET /runs → list runs (template or JSON)          │             │
│  │  GET /runs/{run_id} → run detail page              │             │
│  │  GET /runs/{run_id}/artifacts/{path} → guarded File │             │
│  └───────────────┬───────────────────────────────────────┘             │
│                  │                                                    │
│                  ▼                                                    │
│  ┌───────────────────────────────────────────────────┐             │
│  │         energizados.api.RunManager (STABLE)       │             │
│  │  - list_runs(filter, limit) → List[RunMetadata]   │             │
│  │  - get_run(run_id) → Optional[RunMetadata]        │             │
│  └───────────────────────────────────────────────────┘             │
│                  │                                                    │
│                  ▼                                                    │
│  ┌───────────────────────────────────────────────────┐             │
│  │              output/<run_id>/ (PERSISTED)           │             │
│  │  - run_metadata.json                              │             │
│  │  - reports/evaluation/*.json, *.html, *.png        │             │
│  │  - config/*.yaml                                   │             │
│  │  - run.log                                         │             │
│  └───────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Read-only view layer** — no framework/worker changes | Phase 1 already handles execution; Phase 2 is pure presentation over persisted artifacts. |
| 2 | **Reuse RunManager APIs** — `list_runs()`, `get_run()` | Stable, tested, path-traversal guarded; no need to reimplement run discovery. |
| 3 | **Template branching for single vs multi-model** | JSON structures differ (`evaluation_report.json` vs `comparison.json`); UI detects and renders both. |
| 4 | **Guarded artifact route over StaticFiles mount** | Per-run scoping; traversal-safe; validates run_id before serving files. |
| 5 | **EDA embed via iframe** | `eda_report.html` is autocontained (plots as base64); isolation avoids CSS/JS conflicts. |
| 6 | **Direct JSON read vs RunResult.from_context** | Simpler; runs already persisted; avoids context reconstruction overhead. |

## Components

### 1. New Routes (FastAPI)

**Location**: `src/energizados/web/app.py` (additive only)

#### Route 1: `GET /runs` — List runs

**Purpose**: Paginated list of historical runs with status filter.

**Request**:
```http
GET /runs?status=success&limit=50
Accept: text/html | application/json
```

**Query params**:
- `status` (optional): Filter by `RunMetadata.status` ("success", "partial", "failed")
- `limit` (optional, default=100): Max runs to return

**Response (HTML)**: `TemplateResponse("runs_list.html", {runs, status_filter, limit})`

**Response (JSON)**: `{"runs": [RunMetadata.to_dict(), ...]}`

**Implementation**:
```python
@app.get("/runs")
async def list_runs(
    request: Request,
    status: Optional[str] = None,
    limit: int = 100
):
    """List runs with optional status filter."""
    filter_dict = {"status": status} if status else None
    runs = RunManager.list_runs(filter=filter_dict, limit=limit)
    
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return {"runs": [r.to_dict() for r in runs]}
    
    return templates.TemplateResponse(
        request, "runs_list.html",
        {"runs": runs, "status_filter": status, "limit": limit}
    )
```

**Integration points**:
- Calls `RunManager.list_runs(filter, limit)` (run_manager.py:455-494)
- Renders `runs_list.html` (new template, extends `base.html`)

---

#### Route 2: `GET /runs/{run_id}` — Run detail page

**Purpose**: Comprehensive single-page view of a run's metadata, metrics, plots, configs, and EDA.

**Request**:
```http
GET /runs/train-20240115_143022
```

**Response**: `TemplateResponse("run_detail.html", {run, evaluation, config_files, has_log, eda_relative_path})`

**Implementation**:
```python
@app.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    """Get run detail page."""
    run = RunManager().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Load evaluation JSON (try both structures)
    evaluation = _load_run_evaluation(run.run_id)
    
    # List config files
    config_files = _list_run_configs(run)
    
    # Check for run.log
    has_log = _has_run_log(run)
    
    # EDA relative path for iframe
    eda_relative_path = None
    if run.output_paths.get("eda_report"):
        eda_relative_path = _get_artifact_relative_path(run, run.output_paths["eda_report"])
    
    return templates.TemplateResponse(
        request, "run_detail.html",
        {
            "run": run,
            "evaluation": evaluation,
            "config_files": config_files,
            "has_log": has_log,
            "eda_relative_path": eda_relative_path,
        }
    )
```

**Integration points**:
- Validates `run_id` via `RunManager.get_run()` (run_manager.py:415-453) — **path-traversal guarded**
- Calls `_load_run_evaluation(run_dir)` helper (see Data Flow)
- Calls `_list_run_configs(run)` to enumerate `config/*.yaml`
- Calls `_has_run_log(run)` to check `run.log` presence
- Calls `_get_artifact_relative_path(run, absolute_path)` for iframe src

**Error handling**:
- 404 if `RunManager.get_run()` returns `None`
- 500 if evaluation JSON is corrupted (log, show error in template)

---

#### Route 3: `GET /runs/{run_id}/artifacts/{path:path}` — Guarded artifact serving

**Purpose**: Secure file serving for run artifacts (plots, reports, EDA, configs, logs).

**Request**:
```http
GET /runs/train-20240115_143022/artifacts/reports/evaluation/roc_curve.png
```

**Path params**:
- `run_id`: Run identifier (validated via `RunManager.get_run()`)
- `path`: Relative path within run directory (e.g., `reports/evaluation/roc_curve.png`)

**Response**: `FileResponse(path, media_type=..., headers={"Cache-Control": "public, max-age=3600"})`

**Security guard (CRITICAL)**:
```python
@app.get("/runs/{run_id}/artifacts/{path:path}")
async def get_artifact(run_id: str, path: str):
    """Serve run artifacts with path-traversal guard."""
    manager = RunManager()
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Resolve run directory
    run_dir = manager._resolve_run_dir(run_id)  # Uses _validate_run_name
    if run_dir is None:
        raise HTTPException(status_code=404, detail="Run directory not found")
    
    # Reject path traversal attempts
    if ".." in path or path.startswith("/") or "\\" in path:
        raise HTTPException(status_code=403, detail="Invalid path")
    
    # Resolve artifact path
    artifact_path = (run_dir / path).resolve()
    
    # Double-check: must be within run_dir (defends against symlink escapes)
    try:
        artifact_path.relative_to(run_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path traversal detected")
    
    # Serve file if exists
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # Content-Type by extension
    media_type = _guess_media_type(artifact_path)
    
    # Cache headers for plots/EDA (1 hour)
    cache_control = "public, max-age=3600" if _is_cacheable(artifact_path) else None
    
    return FileResponse(
        artifact_path,
        media_type=media_type,
        headers={"Cache-Control": cache_control} if cache_control else {}
    )
```

**Security contract**:
1. Validate `run_id` via `RunManager.get_run()` (already guards against `..`, `/`, `\`)
2. Reject artifact `path` containing `..`, absolute paths, or backslashes
3. Resolve both `run_dir` and `artifact_path` to absolute paths
4. Assert `artifact_path.relative_to(run_dir.resolve())` — blocks symlink escapes
5. Return 404 if file missing (no directory listings)

**Cache strategy**:
- Cacheable (1 hour): `*.png`, `*.jpg`, `*.svg`, `*.html` (plots, EDA, reports)
- No cache: `*.yaml`, `*.log` (configs, logs — may change)

**Precedent**: Mirrors `_validate_run_name` pattern from Phase 1 (run_manager.py:45-53).

---

### 2. Templates (Jinja2)

**Location**: `src/energizados/web/templates/`

#### Template 1: `runs_list.html`

**Purpose**: Paginated table of runs with key metrics.

**Structure**:
```html
{% extends "base.html" %}
{% from "components/status_badge.html" import status_badge %}

{% block title %}Runs — Energizados Web Console{% endblock %}

{% block content %}
<h2>📊 Runs History</h2>

<!-- Filter controls -->
<div class="mb-3">
    <a href="/runs?status=success" class="btn btn-sm btn-outline-success">✅ Success</a>
    <a href="/runs?status=failed" class="btn btn-sm btn-outline-danger">❌ Failed</a>
    <a href="/runs" class="btn btn-sm btn-outline-secondary">🔄 All</a>
</div>

<!-- Table -->
<table class="table table-hover">
    <thead>
        <tr>
            <th>Run ID</th>
            <th>Status</th>
            <th>Models</th>
            <th>AUC</th>
            <th>F1</th>
            <th>Duration</th>
            <th>Timestamp</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {% for run in runs %}
        <tr>
            <td><code class="small">{{ run.run_id }}</code></td>
            <td>{{ status_badge(run.status) }}</td>
            <td>{{ run.model_types|join(", ") }}</td>
            <td>{{ run.val_auc|round(3) if run.val_auc else "—" }}</td>
            <td>{{ run.val_f1|round(3) if run.val_f1 else "—" }}</td>
            <td>{{ run.duration_seconds|round(1) }}s</td>
            <td class="small">{{ run.timestamp[:19] }} UTC</td>
            <td>
                <a href="/runs/{{ run.run_id }}" class="btn btn-sm btn-primary">
                    👁️ View
                </a>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

{% if not runs %}
<div class="alert alert-info">ℹ️ No runs found.</div>
{% endif %}
{% endblock %}
```

**Reuses**: `base.html` layout, `status_badge` macro (with new run statuses: success, partial, failed).

---

#### Template 2: `run_detail.html`

**Purpose**: Comprehensive single-page view with sections for metadata, metrics, plots, configs, log, and EDA iframe.

**Structure**:
```html
{% extends "base.html" %}
{% from "components/status_badge.html" import status_badge %}

{% block title %}{{ run.run_id }} — Run Detail{% endblock %}

{% block content %}
<div class="run-detail">
    <!-- Header: Run ID + status badge -->
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>{{ run.run_id }}</h2>
        {{ status_badge(run.status) }}
    </div>

    <!-- Metadata section -->
    <section class="mb-4">
        <h5>📋 Metadata</h5>
        <table class="table table-sm">
            <tr><th>Timestamp</th><td>{{ run.timestamp[:19] }} UTC</td></tr>
            <tr><th>Duration</th><td>{{ run.duration_seconds|round(1) }}s</td></tr>
            <tr><th>Models</th><td>{{ run.model_types|join(", ") }}</td></tr>
            <tr><th>Features</th><td>{{ run.feature_count if run.feature_count else "—" }}</td></tr>
            <tr><th>Version</th><td>{{ run.energizados_version }}</td></tr>
        </table>
    </section>

    <!-- Metrics section (branches single vs multi) -->
    <section class="mb-4">
        <h5>📈 Metrics</h5>
        {% if evaluation %}
            {% if evaluation.ranking %}
                <!-- Multi-model: ranking table -->
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Rank</th><th>Model</th><th>AUC</th><th>F1</th><th>Precision</th><th>Recall</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for model in evaluation.ranking %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td>{{ model.name }}</td>
                            <td>{{ model.metrics.auc|round(3) }}</td>
                            <td>{{ model.metrics.f1|round(3) }}</td>
                            <td>{{ model.metrics.precision|round(3) }}</td>
                            <td>{{ model.metrics.recall|round(3) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <p class="text-muted">Best model: <strong>{{ evaluation.best_model }}</strong></p>
            {% else %}
                <!-- Single-model: metrics table -->
                <table class="table table-sm">
                    <tr><th>AUC</th><td>{{ evaluation.metrics.auc|round(3) }}</td></tr>
                    <tr><th>F1</th><td>{{ evaluation.metrics.f1|round(3) }}</td></tr>
                    <tr><th>Precision</th><td>{{ evaluation.metrics.precision|round(3) }}</td></tr>
                    <tr><th>Recall</th><td>{{ evaluation.metrics.recall|round(3) }}</td></tr>
                    <tr><th>Threshold</th><td>{{ evaluation.metrics.threshold }}</td></tr>
                </table>
            {% endif %}
        {% else %}
            <div class="alert alert-warning">⚠️ No evaluation report found.</div>
        {% endif %}
    </section>

    <!-- Plots gallery section -->
    <section class="mb-4">
        <h5>📊 Plots</h5>
        <div class="row">
            <!-- Detect and render available plots from reports/evaluation/*.png -->
            {% for plot_path in _list_plots(run) %}
            <div class="col-md-6 mb-3">
                <div class="card">
                    <img src="/runs/{{ run.run_id }}/artifacts/{{ plot_path }}" 
                         class="card-img-top" alt="{{ plot_path }}">
                    <div class="card-body text-center">
                        <small class="text-muted">{{ plot_path|basename }}</small>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </section>

    <!-- EDA embed section -->
    {% if eda_relative_path %}
    <section class="mb-4">
        <h5>🔍 EDA Report</h5>
        <iframe 
            src="/runs/{{ run.run_id }}/artifacts/{{ eda_relative_path }}" 
            width="100%" 
            height="800px"
            style="border: 1px solid #dee2e6; border-radius: 4px;"
        ></iframe>
    </section>
    {% endif %}

    <!-- Config files section -->
    <section class="mb-4">
        <h5>⚙️ Config Files</h5>
        <ul>
            {% for config_file in config_files %}
            <li>
                <a href="/runs/{{ run.run_id }}/artifacts/config/{{ config_file }}" 
                   target="_blank">
                    📄 {{ config_file }}
                </a>
            </li>
            {% endfor %}
        </ul>
    </section>

    <!-- Log section -->
    {% if has_log %}
    <section class="mb-4">
        <h5>📜 Run Log</h5>
        <pre class="bg-light p-3" style="max-height: 400px; overflow-y: auto;">{{ _read_run_log(run) }}</pre>
    </section>
    {% endif %}

    <!-- Navigation -->
    <div class="mt-4">
        <a href="/runs" class="btn btn-secondary">← Back to Runs</a>
    </div>
</div>
{% endblock %}
```

**Template helpers** (called from route, passed to template context):
- `_list_plots(run) -> List[str]` — glob `reports/evaluation/*.png`, return relative paths
- `_read_run_log(run) -> str` — read `run.log` if exists, tail last N lines
- `_get_artifact_relative_path(run, absolute_path) -> str` — convert absolute path to relative for artifact route

---

### 3. Data Flow — Evaluation JSON Helper

**Problem**: Two JSON structures exist:
- Single-model: `evaluation_report.json` → `{metrics: {...}, model_info: {...}}`
- Multi-model: `comparison.json` → `{ranking: [...], best_model: "...", metrics: {...}}`

**Solution**: Template helper that detects structure and normalizes for rendering.

**Implementation**:
```python
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
        - None if no evaluation found
    """
    manager = RunManager()
    run = manager.get_run(run_id)
    if not run:
        return None
    
    run_dir = manager._resolve_run_dir(run_id)
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
```

**Template usage**:
```jinja2
{% if evaluation.is_multi %}
    <!-- Render ranking table for multi-model -->
{% else %}
    <!-- Render metrics table for single-model -->
{% endif %}
```

---

### 4. Template Helper Functions

**Location**: `src/energizados/web/app.py` (private module-level functions)

#### `_list_run_configs(run: RunMetadata) -> List[str]`

```python
def _list_run_configs(run: RunMetadata) -> List[str]:
    """List config filenames in run directory."""
    manager = RunManager()
    run_dir = manager._resolve_run_dir(run.run_id)
    if not run_dir:
        return []
    
    config_dir = run_dir / "config"
    if not config_dir.is_dir():
        return []
    
    return [f.name for f in config_dir.iterdir() if f.is_file()]
```

#### `_has_run_log(run: RunMetadata) -> bool`

```python
def _has_run_log(run: RunMetadata) -> bool:
    """Check if run.log exists."""
    manager = RunManager()
    run_dir = manager._resolve_run_dir(run.run_id)
    if not run_dir:
        return False
    
    return (run_dir / "run.log").is_file()
```

#### `_read_run_log(run: RunMetadata, max_lines: int = 1000) -> str`

```python
def _read_run_log(run: RunMetadata, max_lines: int = 1000) -> str:
    """Read last N lines from run.log."""
    manager = RunManager()
    run_dir = manager._resolve_run_dir(run.run_id)
    if not run_dir:
        return "Log not found"
    
    log_path = run_dir / "run.log"
    if not log_path.is_file():
        return "Log not found"
    
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            return f"... (showing last {max_lines} of {len(lines)} lines)\n" + "".join(lines[-max_lines:])
        return "".join(lines)
    except IOError as e:
        return f"Error reading log: {e}"
```

#### `_get_artifact_relative_path(run: RunMetadata, absolute_path: str) -> str`

```python
def _get_artifact_relative_path(run: RunMetadata, absolute_path: str) -> str:
    """
    Convert absolute artifact path to relative path for artifact route.
    
    Example:
        absolute_path = "/output/train-20240115_143022/eda_report.html"
        returns "eda_report.html"
    """
    manager = RunManager()
    run_dir = manager._resolve_run_dir(run.run_id)
    if not run_dir:
        raise ValueError("Invalid run directory")
    
    try:
        return str(Path(absolute_path).relative_to(run_dir))
    except ValueError:
        raise ValueError(f"Path {absolute_path} not within run directory")
```

#### `_guess_media_type(path: Path) -> str`

```python
def _guess_media_type(path: Path) -> str:
    """Guess media type from file extension."""
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
```

#### `_is_cacheable(path: Path) -> bool`

```python
def _is_cacheable(path: Path) -> bool:
    """Return True if file should be cached (plots, reports)."""
    ext = path.suffix.lower()
    return ext in {".png", ".jpg", ".jpeg", ".svg", ".html"}
```

---

### 5. Navigation Integration

**Update**: `job_detail.html` (Phase 1 template) should link to run detail when `job.run_id` is present.

**Change**:
```html
<!-- In job_detail.html, after job status section -->
{% if job.run_id %}
<div class="mt-3">
    <a href="/runs/{{ job.run_id }}" class="btn btn-sm btn-primary">
        📊 View Run Results
    </a>
</div>
{% endif %}
```

---

## ADR: Architectural Decisions Record

### ADR-001: Direct JSON read vs RunResult.from_context

**Status**: Accepted

**Context**: Two approaches to load evaluation metrics for run detail:
1. Read persisted `evaluation_report.json` / `comparison.json` directly
2. Use `RunResult.from_context()` to reconstruct from context (not persisted)

**Decision**: **Read JSON directly** (implemented as `_load_run_evaluation`).

**Rationale**:
- Runs are already persisted; JSON exists on disk
- `RunResult.from_context()` requires reconstructing context (expensive, not needed)
- Direct read is simpler and faster (one file open vs. full context rebuild)
- Template only needs metrics, not full context state

**Consequences**:
- **Positive**: Simpler code, faster load, no framework changes
- **Negative**: Assumes JSON structure is stable (acceptable; format is documented)

**Alternatives considered**:
- **RunResult.from_context**: Rejected — overkill, requires context reconstruction that wasn't persisted

---

### ADR-002: Guarded artifact route vs StaticFiles mount

**Status**: Accepted

**Context**: Two approaches to serve run artifacts (plots, EDA, configs, logs):
1. Guarded route `GET /runs/{run_id}/artifacts/{path}` with run_id validation
2. `StaticFiles` mount per run directory (e.g., `/static/runs/{run_id}/`)

**Decision**: **Guarded artifact route with run_id validation**.

**Rationale**:
- **Security**: Validates `run_id` via `RunManager.get_run()` (already guards path traversal)
- **Per-run scoping**: Each request checks run exists before serving files
- **Traversal-safe**: Double-checks `resolved_path.relative_to(run_dir)` (symlink defense)
- **Cache control**: Can set cache headers per file type
- **No new mounts**: Avoids dynamic route registration per run

**Consequences**:
- **Positive**: Secure, no dynamic mounts, cacheable, follows Phase 1 pattern
- **Negative**: Slightly more code than StaticFiles (acceptable for security)

**Alternatives considered**:
- **StaticFiles mount per run**: Rejected — dynamic route registration complexity, harder to guard traversal, no per-run validation

---

### ADR-003: EDA embed via iframe vs inline HTML

**Status**: Accepted

**Context**: Two approaches to embed EDA report in run detail:
1. `<iframe src="/runs/{run_id}/artifacts/eda_report.html">` (isolation)
2. Inline HTML via template include or direct read

**Decision**: **iframe** (autocontained HTML served via artifact route).

**Rationale**:
- **Autocontained**: `eda_report.html` already includes plots as base64 (no external deps)
- **Isolation**: Avoids CSS/JS conflicts between EDA and run detail page
- **No escaping**: EDA HTML can be served directly without sanitization
- **Navigation**: EDA internal links work within iframe
- **Performance**: Browser caches iframe content separately

**Consequences**:
- **Positive**: Clean isolation, no conflicts, autocontained, cacheable
- **Negative**: iframe has fixed height (acceptable; set to 800px with scroll)

**Alternatives considered**:
- **Inline HTML**: Rejected — risk of CSS/JS conflicts, need to sanitize EDA HTML, harder to cache

---

## Cross-Cutting Concerns

### Security

| Concern | Mitigation |
|---------|-----------|
| **Path traversal in artifact serving** | Multi-layer guard: (1) `RunManager.get_run()` validates `run_id`, (2) Reject `..`, absolute paths, backslashes in `artifact_path`, (3) Resolve and assert `artifact_path.relative_to(run_dir)` |
| **Symlink escape from run_dir** | Double-check with `relative_to()` on resolved paths — blocks symlinks pointing outside run_dir |
| **Unauthenticated read access** | Documented risk (inherited from Phase 1); deploy behind network-isolated reverse proxy; auth deferred |
| **XSS from EDA HTML** | EDA is auto-contained (no external scripts); iframe isolation prevents script escape to parent page |
| **Directory traversal in run_id** | `RunManager.get_run()` already guards (run_manager.py:45-53) — rejects `/`, `\`, `..` |

**Security precedent**: Mirrors `_validate_run_name` from Phase 1 (run_manager.py:45-53).

---

### Performance

| Concern | Mitigation |
|---------|-----------|
| **Large plot/EDA file serving** | Cache headers (`Cache-Control: public, max-age=3600`) for images/HTML |
| **`list_runs()` reads many JSON files** | Default `limit=100`, pagination in UI (add offset in future if needed) |
| **run.log large file tailing** | `_read_run_log()` reads last N lines only (default 1000) |
| **EDA iframe slow load** | Browser caches iframe content; plots are base64 (no extra requests) |

---

### Error Handling

| Error case | Route handling | Template handling |
|------------|----------------|-------------------|
| **Run not found** | 404 via `RunManager.get_run()` → `None` | N/A |
| **Artifact not found** | 404 after path validation | Show "not available" message |
| **Evaluation JSON corrupted** | Log error, return `None` | Show "no evaluation report" alert |
| **run.log missing** | Return `False` from `_has_run_log()` | Skip log section |
| **Invalid path traversal attempt** | 403 with "Path traversal detected" | N/A |

---

### Cache Strategy

**Cacheable (1 hour)**:
- Plot images: `*.png`, `*.jpg`, `*.svg`
- Reports: `*.html` (EDA, evaluation reports)

**No cache**:
- Configs: `*.yaml`, `*.yml` (may change)
- Logs: `*.log` (may change)

**Implementation**:
```python
headers = {"Cache-Control": "public, max-age=3600"} if _is_cacheable(artifact_path) else {}
```

---

## Dependencies

### No new dependencies

- Uses existing `RunManager` APIs (stable)
- Uses existing `FastAPI` + `Jinja2` (Phase 1 dependencies)
- No new Python packages
- No new infrastructure

### Framework core changes

- **None** (Phase 2 is pure web layer)

---

## Testing Strategy

### Unit tests

**`tests/web/test_app.py` additions**:
```python
def test_list_runs_html(client):
    """Test GET /runs returns HTML with runs table."""
    response = client.get("/runs")
    assert response.status_code == 200
    assert b"Runs History" in response.data

def test_list_runs_json(client):
    """Test GET /runs with Accept: application/json."""
    response = client.get("/runs", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.json()
    assert "runs" in data

def test_get_run_detail(client, fake_run_dir):
    """Test GET /runs/{run_id} returns detail page."""
    response = client.get(f"/runs/{fake_run_dir.name}")
    assert response.status_code == 200
    assert b"Metadata" in response.data

def test_get_run_not_found(client):
    """Test GET /runs/{run_id} with invalid run_id returns 404."""
    response = client.get("/runs/invalid-run-id")
    assert response.status_code == 404

def test_get_artifact_plot(client, fake_run_dir):
    """Test GET /runs/{run_id}/artifacts/path serves plot."""
    response = client.get(f"/runs/{fake_run_dir.name}/artifacts/reports/evaluation/roc_curve.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

def test_get_artifact_path_traversal(client, fake_run_dir):
    """Test GET /runs/{run_id}/artifacts/../etc/passwd returns 403."""
    response = client.get(f"/runs/{fake_run_dir.name}/artifacts/../../etc/passwd")
    assert response.status_code == 403

def test_get_artifact_not_found(client, fake_run_dir):
    """Test GET /runs/{run_id}/artifacts/missing.png returns 404."""
    response = client.get(f"/runs/{fake_run_dir.name}/artifacts/missing.png")
    assert response.status_code == 404
```

**Template helpers tests** (`tests/web/test_helpers.py`):
```python
def test_load_evaluation_single_model(fake_run_dir):
    """Test _load_run_evaluation with single-model structure."""
    # Create evaluation_report.json
    evaluation = _load_run_evaluation(fake_run_dir.name)
    assert evaluation["is_multi"] is False
    assert "metrics" in evaluation

def test_load_evaluation_multi_model(fake_run_dir):
    """Test _load_run_evaluation with multi-model structure."""
    # Create comparison.json
    evaluation = _load_run_evaluation(fake_run_dir.name)
    assert evaluation["is_multi"] is True
    assert "ranking" in evaluation

def test_list_run_configs(fake_run_dir):
    """Test _list_run_configs returns config filenames."""
    configs = _list_run_configs(run_metadata)
    assert "train.yaml" in configs

def test_has_run_log(fake_run_dir):
    """Test _has_run_log detects log presence."""
    # Create run.log
    assert _has_run_log(run_metadata) is True
```

### Integration tests

**`tests/web/test_integration_runs.py`**:
```python
def test_runs_list_to_detail_flow(client, completed_run_dir):
    """Test user flow: list runs → click detail → view metrics/plots."""
    # List runs
    response = client.get("/runs")
    assert completed_run_dir.name in response.text
    
    # Get detail
    response = client.get(f"/runs/{completed_run_dir.name}")
    assert response.status_code == 200
    assert b"Metrics" in response.data
    
    # Get plot
    response = client.get(f"/runs/{completed_run_dir.name}/artifacts/reports/evaluation/roc_curve.png")
    assert response.status_code == 200
```

---

## Review Workload Forecast

### Changed lines estimate

- **`src/energizados/web/app.py`**: ~250 lines (3 routes + 6 helpers)
- **`src/energizados/web/templates/runs_list.html`**: ~60 lines
- **`src/energizados/web/templates/run_detail.html`**: ~120 lines
- **`tests/web/test_app.py` additions**: ~100 lines
- **Total**: ~530 lines

### Complexity assessment

- **Low complexity**: Pure read-only view layer, no framework changes
- **Well-bounded**: Only 3 routes, 2 templates, 6 helpers
- **Secure**: Reuses proven guard patterns from Phase 1
- **Testable**: All integration points have clear contracts

### Recommendation: **Single PR acceptable**

This is a small, well-bounded change that fits in a single PR. No framework core changes, no worker changes, additive web layer only.

---

## Rollback Plan

1. **Remove routes**: Delete 3 new route handlers from `app.py`
2. **Remove templates**: Delete `runs_list.html`, `run_detail.html`
3. **Remove navigation**: Revert `job_detail.html` link changes
4. **Remove tests**: Delete new test cases
5. **No migrations**: No database changes, no framework changes

**Impact**: Zero. This is pure additive web layer; rollback is file deletion.

---

## Traceability to Specs

### web-console-phase2 proposal coverage

| Proposal requirement | Design element |
|---------------------|-----------------|
| Runs list view (`GET /runs`) | Route 1 + runs_list.html template |
| Run detail view (`GET /runs/{run_id}`) | Route 2 + run_detail.html template |
| Safe artifact serving (`GET /runs/{run_id}/artifacts/{path}`) | Route 3 with security guard |
| Single-model evaluation rendering | Template branching + _load_run_evaluation |
| Multi-model evaluation rendering | Template branching + _load_run_evaluation |
| EDA embed via iframe | run_detail.html iframe section |
| Config files listing | _list_run_configs helper |
| Run log display | _read_run_log helper |
| Navigation from job to run | job_detail.html link update |
| Path-traversal security | Multi-layer guard in Route 3 |
| No framework/worker changes | Architecture: read-only view layer |

### PRD coverage (from `docs/web-console/PRD.md`)

| PRD requirement | Design element |
|----------------|-----------------|
| PRD #1: Runs list view | Route 1 + runs_list.html |
| PRD #2: Run detail view with metrics, plots, EDA, configs | Route 2 + run_detail.html |
| Security: path-traversal protection | Route 3 security guard |
| Autocontained EDA embed | iframe with artifact route |

---

## Next Steps

1. **Tasks phase**: Break down into actionable tasks (routes, templates, helpers, tests, navigation)
2. **Implementation order**: (1) Route 1 + runs_list.html → (2) Route 2 + run_detail.html → (3) Route 3 → (4) Template helpers → (5) Tests → (6) Navigation update
3. **Apply phase**: Implement following TDD discipline (test first, then code)
4. **Verify phase**: Run integration tests + manual browser smoke test

---

## Open Questions (deferred to implementation/tasks)

1. **Plot detection**: Exact glob pattern for `_list_plots()` — verify plot filenames in `reports/evaluation/` match expectation
2. **run.log encoding**: Confirm UTF-8 encoding assumption in `_read_run_log()`
3. **Cache duration**: Is 1 hour appropriate for plots? (acceptable default, can be tunable via ENV var)
4. **EDA iframe height**: 800px reasonable? (acceptable default, can be responsive)

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Evaluation JSON structure changes** | Low | Medium | Template branches on structure detection; missing fields handled gracefully |
| **Plot filenames differ from expectation** | Low | Low | Glob pattern is forgiving; missing plots → no gallery (not critical) |
| **run.log encoding issues** | Low | Low | UTF-8 is standard; encoding errors → show error message |
| **Large EDA HTML iframe slowness** | Medium | Low | EDA is autocontained (no external requests); browser caches iframe |
| **Path traversal bypass** | Low | High | Multi-layer guard + double-check relative_to() |
| **RunManager API changes** | Low | Medium | APIs are stable/public; if changed, update routes in same PR |

---

## Conclusion

Phase 2 is a **thin, read-only view layer** over existing `RunManager` APIs. No framework changes, no worker changes, no new infrastructure. Three new routes serve templates and guarded file responses. Template branching handles both single-model and multi-model evaluation structures. Artifact serving uses proven path-traversal guards from Phase 1. EDA embed uses iframe isolation. All changes are contained to `~530 lines` (web layer only). **Single PR acceptable**.
