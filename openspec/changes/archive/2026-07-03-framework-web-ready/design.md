# Design: framework-web-ready

## Technical Approach

**Single-PR additive change** that introduces a service API layer at `energizados.api`, hardens exceptions with machine-readable codes, narrows the import allowlist, and refactors CLI commands to thin clients over the core API. No frozen symbols are removed or renamed — all changes are backward-compatible.

## Architecture Overview

```
src/energizados/
├── api/                          # NEW: Service API layer
│   ├── __init__.py              # Public surface: validate_dict, from_dict, doctor
│   ├── validate.py              # validate_dict() -> ValidationResult
│   ├── pipeline.py              # Pipeline extensions (from_dict, plan)
│   ├── run_state.py             # RunManager query extensions
│   ├── progress.py              # ProgressEvent, console_progress callback
│   └── exceptions.py            # Helper to build error responses
├── core/
│   ├── exceptions.py            # MODIFIED: error_code + to_dict() added
│   ├── utils/
│   │   └── import_utils.py      # MODIFIED: narrowed ALLOWED_PREFIXES
│   ├── pipeline.py              # MODIFIED: plan() method, run() context unchanged
│   └── builders/
│       └── run_manager.py       # MODIFIED: get_run, list_runs, get_latest_run
├── cli/                         # MODIFIED: All commands delegate to api/
│   ├── run.py                   # Thin client over api
│   ├── validate.py              # Thin client over api.validate_dict
│   ├── doctor.py                # Thin client over api.doctor
│   └── init.py                  # Unchanged (primarily CLI)
└── contracts.py                 # UNCHANGED: Frozen public API
```

### Layering

```
┌─────────────────────────────────────────────────────────┐
│ CLI (Thin Clients)                                      │
│ - Human output formatting                                │
│ - --json flag delegation                                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ energizados.api (Service Layer)                         │
│ - validate_dict(), doctor(), merge_configs()             │
│ - Pipeline.from_dict(), plan(), progress events          │
│ - RunManager queries, RunResult.from_context()          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ energizados.core (Internal Implementation)              │
│ - Pipeline, ConfigPipelineBuilder, PipelineDirector      │
│ - RunManager, PipelineStep implementations               │
│ - Exception hierarchy with error_code + to_dict()        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ contracts.py (Frozen Public API)                         │
│ - BaseModel, BaseInference, BasePipeline, etc.          │
└─────────────────────────────────────────────────────────┘
```

## Architecture Decisions

### Decision 1: API Location — `energizados.api` (New Top-Level Package)

**Choice**: Create new top-level package `energizados.api` for the service layer. Do NOT use `energizados.core.api`.

**Alternatives considered**:
- **`energizados/core/api/`**: Would conflate user-facing service API with internal core implementation.
- **Add to `contracts.py`**: Contracts are frozen public API base classes — not the place for service functions.

**Rationale**:
- `contracts.py` is already at top level as the public surface — `api/` follows this pattern
- Service layer is user-facing, not internal — should not live in `core/`
- Future web service wrapper imports from `energizados.api`, not `energizados.core`
- Clear separation: `contracts.py` = frozen base classes, `api/` = service layer, `core/` = internal

**Public surface** (`api/__init__.py`):
```python
from energizados.api.validate import validate_dict, ValidationResult
from energizados.api.pipeline import Pipeline  # re-exports core Pipeline
from energizados.api.run_state import RunManager, RunResult, RunMetadata
from energizados.api.progress import ProgressEvent, console_progress
from energizados.api.exceptions import format_error
from energizados.api.config import merge_configs, doctor

__all__ = [
    "validate_dict",
    "ValidationResult",
    "Pipeline",
    "from_dict",  # Pipeline.from_dict
    "plan",
    "RunManager",
    "RunResult",
    "RunMetadata",
    "ProgressEvent",
    "console_progress",
    "format_error",
    "merge_configs",
    "doctor",
]
```

---

### Decision 2: `Pipeline` vs `ConfigPipelineBuilder` Relationship

**Choice**: `Pipeline` (core) gets `from_dict()` classmethod and dict-accepting `__init__`. `ConfigPipelineBuilder` unchanged. The `api` layer re-exports `Pipeline` without subclassing.

**Alternatives considered**:
- **Make `from_dict()` the primary and `__init__` delegate to it**: Would add unnecessary indirection for existing file-path callers.
- **Add dict support only to `ConfigPipelineBuilder`**: Breaks symmetry — `Pipeline` is the lower-level primitive that should support all input modes.
- **Create separate `api.Pipeline` subclass**: Would create confusion about which class to use.

**Rationale**:
- Current `Pipeline.__init__(config_path=None, config=None)` already accepts dict via `config` param
- Adding `from_dict()` as explicit classmethod satisfies spec requirement
- `ConfigPipelineBuilder` behavior unchanged — existing callers keep working
- `api/pipeline.py` simply re-exports the core `Pipeline` — no inheritance confusion

**Call graph**:
```
api/pipeline.py: from energizados.core.pipeline import Pipeline; __all__ = ["Pipeline", "from_dict"]
  └─> Re-exports core.Pipeline unchanged
  └─> core.Pipeline.from_dict() classmethod (new)

core.Pipeline.from_dict(config, context=None)
  └─> Pipeline(config=config, context=None)  # config is Dict
        └─> if config is dict: self.config = config
            └─> if config is str|Path: self.config = _load_config(config)

ConfigPipelineBuilder (unchanged)
  └─> PipelineDirector (unchanged)
        └─> Pipeline (unchanged for builder path)
```

**Implementation sketch** (`core/pipeline.py`):
```python
class Pipeline:
    def __init__(
        self,
        config_path: str = None,
        config: Dict = None,
    ):
        """
        Initialize the pipeline.

        Args:
            config_path: Path to the YAML configuration file
            config: Configuration dictionary (optional, takes precedence over config_path)
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = self._load_config(config_path)
        else:
            self.config = {}
        # ... rest unchanged (already works)

    @classmethod
    def from_dict(
        cls, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None
    ) -> "Pipeline":
        """Create Pipeline from dict config (explicit factory).

        This is the programmatic API entry point. Equivalent to:
            Pipeline(config=config_dict)

        Args:
            config: Configuration dictionary
            context: Optional initial context (not used in Pipeline, reserved for future)

        Returns:
            Configured Pipeline instance
        """
        return cls(config=config)

    def run(self) -> Dict[str, Any]:
        """
        Execute all pipeline steps.

        Returns:
            Dict: Final context with results (unchanged for backward compatibility)
        """
        # ... existing implementation unchanged
        return self.context  # Returns plain dict, NOT RunResult
```

**Key distinction**: `from_dict` is defined ONCE in `core.Pipeline`. The `api` layer re-exports it; there is NO duplicate definition.

---

### Decision 3: `RunResult` + `RunMetadata` — Separate Accessor, Zero Return Break

**Choice**: `Pipeline.run()` continues to return the existing context dict (ZERO break). `RunResult` is a separate dataclass with a `from_context()` classmethod that builds structured access from the raw dict. The API layer wraps the result.

**Alternatives considered**:
- **Make `Pipeline.run()` return `RunResult` with dict-like mixin**: Still breaks `dict(result)`, `result.items()`, `**result` unpacking, and `json.dumps(result)` without custom handling.
- **Make `RunResult` subclass `dict`**: Would work but is more invasive; keeping the return contract unchanged is safer.

**Rationale**:
- **Zero break**: Existing code doing `result = pipeline.run(); result["metrics"]` continues to work
- **Structured access**: New code can do `result = RunResult.from_context(pipeline.run()); result.run_id`
- **API layer wrapper**: `api.pipeline.run_pipeline()` or similar can return `RunResult` directly for web service use

**Data structures** (`api/run_state.py`):
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

@dataclass
class RunMetadata:
    """Metadata for a single run (stored in run_metadata.json)."""
    run_id: str
    timestamp: str  # ISO 8601
    duration_seconds: float
    energizados_version: str
    python_version: str
    git_commit: str
    model_types: List[str]
    status: str = "success"  # NEW: "success", "partial", "failed"
    val_auc: Optional[float] = None
    val_f1: Optional[float] = None
    feature_count: Optional[int] = None
    config_files: List[str] = field(default_factory=list)
    output_paths: Dict[str, str] = field(default_factory=dict)  # NEW

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunMetadata":
        """Tolerant loader for old runs (missing fields get defaults)."""
        return cls(
            run_id=data.get("run_id", ""),
            timestamp=data.get("timestamp", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            energizados_version=data.get("energizados_version", ""),
            python_version=data.get("python_version", ""),
            git_commit=data.get("git_commit", ""),
            model_types=data.get("model_types", []),
            status=data.get("status", "success"),  # Default for old runs
            val_auc=data.get("val_auc"),
            val_f1=data.get("val_f1"),
            feature_count=data.get("feature_count"),
            config_files=data.get("config_files", []),
            output_paths=data.get("output_paths", {}),  # Empty for old runs
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict representation."""
        return asdict(self)

@dataclass
class RunResult:
    """Structured result from Pipeline.run().

    This is a VIEW over the pipeline context dict. The context is NOT copied;
    RunResult holds a reference. Modifications to context affect RunResult and vice versa.
    """
    run_id: Optional[str]  # May be None if run hasn't written metadata yet
    status: str  # "success", "partial", "failed"
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    metrics: Dict[str, Any]
    output_paths: Dict[str, str]

    # Reference to full context (not a copy)
    _context: Dict[str, Any] = field(repr=False)

    @classmethod
    def from_context(cls, context: Dict[str, Any]) -> "RunResult":
        """Build RunResult from pipeline context dict.

        This is the bridge between the legacy dict return and the structured API.
        The context dict is passed by reference, not copied.
        """
        # Extract metrics (may be None for non-training runs)
        metrics = context.get("metrics") or context.get("model_metrics") or {}

        return cls(
            run_id=context.get("run_id"),  # Set by Pipeline during run
            status=context.get("status", "success"),
            start_time=context.get("start_time"),
            end_time=context.get("end_time"),
            metrics=metrics,
            output_paths=context.get("output_paths", {}),
            _context=context,
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict representation."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "metrics": self.metrics,
            "output_paths": self.output_paths,
        }
```

**Integration with `Pipeline.run()`**:
```python
# core/pipeline.py - Pipeline.run() UNCHANGED
def run(self) -> Dict[str, Any]:
    # ... existing implementation
    return self.context  # Returns plain dict, ZERO break

# api/pipeline.py - convenience wrapper
def run_pipeline(pipeline: Pipeline, progress_callback=None) -> RunResult:
    """Run pipeline and return structured result."""
    context = pipeline.run()
    return RunResult.from_context(context)
```

**Backward compatibility proof**:
- Existing code: `result = pipeline.run(); metrics = result["metrics"]` → continues to work (dict returned)
- New code: `result = RunResult.from_context(pipeline.run()); metrics = result.metrics` → structured access

---

### Decision 4: Progress Subscription Model — Callback with Error Isolation

**Choice**: `progress_callback: Callable[[ProgressEvent], None]` parameter on `Pipeline.run()`. Callback errors are caught, logged, and do NOT abort the run. Existing Rich console progress is refactored into a callback consumer.

**Alternatives considered**:
- **Async generator / queue**: Over-engineering for current use case — no async runtime in the framework.
- **Pub/sub with multiple subscribers**: Unnecessary complexity — single callback is sufficient.

**Rationale**:
- Callback is the simplest model that satisfies web service needs (stream events to HTTP response)
- Error isolation prevents a buggy UI callback from aborting the pipeline
- Rich console progress becomes a callback consumer — no hardcoded progress in core

**Implementation** (`api/progress.py`):
```python
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Any

@dataclass
class ProgressEvent:
    """Progress event emitted during pipeline execution."""
    run_id: str
    step_name: str
    phase: str  # "start", "progress", "complete", "error"
    message: str
    percent: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "step_name": self.step_name,
            "phase": self.phase,
            "message": self.message,
            "percent": self.percent,
            "timestamp": self.timestamp.isoformat(),
        }

def console_progress() -> Callable[[ProgressEvent], None]:
    """Progress callback that renders to Rich console (CLI default)."""
    def callback(event: ProgressEvent):
        # Reuse existing Rich progress logic from cli/run.py
        # Emit events to the active Progress instance
        pass
    return callback

# In Pipeline.run()
def run(self, progress_callback: Optional[Callable[[ProgressEvent], None]] = None) -> Dict[str, Any]:
    run_id = self._generate_run_id()
    for i, step in enumerate(self.steps):
        try:
            if progress_callback:
                try:
                    progress_callback(ProgressEvent(
                        run_id=run_id, step_name=step.__class__.__name__,
                        phase="start", message=f"Starting {step.__class__.__name__}"
                    ))
                except Exception as e:
                    logger.exception("Progress callback error (ignored)")
            # ... execute step
            if progress_callback:
                try:
                    progress_callback(ProgressEvent(
                        run_id=run_id, step_name=step.__class__.__name__,
                        phase="complete", message=f"Completed {step.__class__.__name__}"
                    ))
                except Exception as e:
                    logger.exception("Progress callback error (ignored)")
        except Exception as e:
            if progress_callback:
                try:
                    progress_callback(ProgressEvent(
                        run_id=run_id, step_name=step.__class__.__name__,
                        phase="error", message=str(e)
                    ))
                except Exception:
                    logger.exception("Progress callback error (ignored)")
            raise
    return self.context
```

**Internal dispatch**:
- Events emitted at step boundaries (start, complete, error)
- Phase events (`on_phase_update`) emitted from within steps (ETL sub-steps, training phases)
- Callback wrapped in `try/except` — errors logged but do not propagate

---

### Decision 5: Run-State Persistence — JSON Sidecar with Tolerant Loader

**Choice**: Extend existing `run_metadata.json` sidecar file. Add `RunMetadata.from_dict()` tolerant loader for old runs. `list_runs()` discovers all run types (train, eda, inference) by glob pattern.

**Alternatives considered**:
- **SQLite index**: Adds a dependency and complexity. Not needed for the scale (dozens to hundreds of runs).
- **Central index file**: Would need concurrent write safety. JSON sidecars are simpler.

**Rationale**:
- Existing `_write_run_metadata()` already writes `run_metadata.json` — extend, not replace
- No new dependencies (pure stdlib `json`)
- Simple to query for small scales (<1000 runs)
- Each run directory is self-contained (can archive/move without breaking queries)

**On-disk layout** (unchanged + extension):
```
output/
├── train-20240101_120000/
│   ├── run_metadata.json          # EXTENDED: add status, output_paths
│   ├── config/
│   ├── models/
│   └── reports/
├── eda-20240101_130000/           # EDA runs use eda- prefix
│   └── run_metadata.json
└── inference-20240101_140000/     # Inference runs use inference- prefix
    └── run_metadata.json
```

**Query implementation** (`api/run_state.py`):
```python
from pathlib import Path
import re

class RunManager:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        """Get metadata for a specific run by ID."""
        run_dir = self.output_dir / run_id
        if not run_dir.exists():
            return None
        return self._read_metadata(run_dir)

    def list_runs(
        self,
        filter: Optional[Dict[str, Any]] = None,
        limit: int = 100
    ) -> List[RunMetadata]:
        """List runs across all types (train, eda, inference)."""
        runs = []
        # Match all run types: train-*, eda-*, inference-*, or custom names
        for run_dir in sorted(self.output_dir.glob("*-*"), reverse=True):
            # Skip directories that don't look like run dirs
            if not run_dir.is_dir():
                continue
            metadata = self._read_metadata(run_dir)
            if metadata and self._matches_filter(metadata, filter):
                runs.append(metadata)
            if len(runs) >= limit:
                break
        return runs

    def get_latest_run(self) -> Optional[RunMetadata]:
        """Get the most recent run."""
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def _read_metadata(self, run_dir: Path) -> Optional[RunMetadata]:
        """Read run metadata with tolerant loader."""
        metadata_file = run_dir / "run_metadata.json"
        if not metadata_file.exists():
            return None
        import json
        with open(metadata_file) as f:
            data = json.load(f)
        return RunMetadata.from_dict(data)  # Tolerant loader

    def _matches_filter(self, metadata: RunMetadata, filter: Optional[Dict]) -> bool:
        if not filter:
            return True
        if "status" in filter and metadata.status != filter["status"]:
            return False
        # Add date_range filter if needed
        return True
```

**Extension to `_write_run_metadata`** (`core/builders/run_manager.py`):
```python
def _write_run_metadata(self, context: Dict[str, Any]) -> None:
    """Write run metadata JSON file to run directory."""
    # ... existing code unchanged ...

    # NEW: Add status and output_paths to metadata
    status = "success"
    if context.get("error"):
        status = "failed"
    elif context.get("comparison_mode"):
        status = "partial"  # Or determine based on step results

    output_paths = {}
    if "model_path" in context:
        output_paths["model"] = context["model_path"]
    if "feature_engineering_path" in context:
        output_paths["feature_engineering"] = context["feature_engineering_path"]

    metadata = {
        # ... existing fields ...
        "status": status,  # NEW
        "output_paths": output_paths,  # NEW
    }
    # Write to JSON file (existing code)
```

---

### Decision 6: Exception `error_code` + `to_dict()` — Base Class Method, Per-Instance Override Support

**Choice**: Add `error_code: str` as class attribute with default in `EnergizadosError`. Add `to_dict()` instance method to base class. Allow per-instance override by storing `error_code` as instance attribute when passed to `__init__`. All subclasses inherit both.

**Alternatives considered**:
- **Separate `ErrorInfo` class**: Unnecessary indirection.
- **Mixin class**: Overkill for two simple additions.
- **Only class-level codes**: Would not support the prefix-violation case needing specific code.

**Rationale**:
- Adding to base class means all subclasses automatically get `error_code` and `to_dict()`
- Class attribute provides default; instance attribute allows override for specific cases
- `to_dict()` method captures instance state (message, details)
- Stlib base inheritance (`ValueError`, `RuntimeError`) remains unchanged — `except ValueError` callers unaffected

**Implementation** (`core/exceptions.py`):
```python
from typing import Any, Dict

class EnergizadosError(Exception):
    """Base class for all Energizados exceptions."""
    error_code: str = "ENERGIZADOS_ERROR"

    def __init__(self, message: str, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            error_code: Optional per-instance error code override
            **details: Additional error context stored in details dict
        """
        super().__init__(message)
        # Store error_code as instance attribute if provided (shadows class attr)
        if error_code is not None:
            self.error_code = error_code
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        """Machine-readable error representation."""
        return {
            "error_code": self.error_code,
            "message": str(self),
            "details": self.details,
        }

# Subclass overrides error_code via class attribute
class ConfigurationError(EnergizadosError):
    error_code = "CONFIG_INVALID"

    def __init__(self, message: str, config_path: str = None, error_code: str = None, **details):
        """
        Initialize the exception.

        Args:
            message: Descriptive error message
            config_path: Path to the configuration file (optional)
            error_code: Optional per-instance error code override (e.g., for prefix violations)
            **details: Additional error context
        """
        # Forward error_code to base class for instance-level storage
        super().__init__(message, error_code=error_code, config_path=config_path, **details)
        self.config_path = config_path

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["config_path"] = self.config_path
        return d

# Subclass with stdlib base (unchanged inheritance)
class ModelNotFittedError(EnergizadosError, ValueError):
    error_code = "MODEL_NOT_FITTED"

    def __init__(self, model_name: str = None, error_code: str = None, **details):
        super().__init__(
            f"Model '{model_name or 'this'}' is not fitted. Call fit() first.",
            error_code=error_code,
            model_name=model_name,
            **details
        )

    # Inherits to_dict() from EnergizadosError
    # except ValueError continues to work (stdlib base unchanged)
```

**Proof of per-instance override**:
```python
# Class-level default
err = ConfigurationError("invalid config")
assert err.error_code == "CONFIG_INVALID"

# Instance-level override (for prefix violations)
err = ConfigurationError("bad prefix", error_code="CONFIG_INVALID_CLASS_PREFIX")
assert err.error_code == "CONFIG_INVALID_CLASS_PREFIX"  # Instance attr shadows class attr
```

**Proof of backward compat**:
```python
# Existing callers continue to work
try:
    model.predict(X)
except ValueError:  # Catches ModelNotFittedError (inherits ValueError)
    handle_unfitted()

# New callers can use error_code
try:
    model.predict(X)
except EnergizadosError as e:
    print(e.error_code)  # "MODEL_NOT_FITTED"
    print(e.to_dict())
```

**Error code assignments**:
- `EnergizadosError`: `ENERGIZADOS_ERROR`
- `PipelineError`: `PIPELINE_EXECUTION_FAILED`
- `StepValidationError`: `STEP_VALIDATION_FAILED`
- `ConfigurationError`: `CONFIG_INVALID` (or `CONFIG_INVALID_CLASS_PREFIX` for prefix violations)
- `ModelNotFittedError`: `MODEL_NOT_FITTED`
- `ETLError`: `ETL_EXECUTION_FAILED`
- `ETLDependencyError`: `ETL_DEPENDENCY_CYCLE`
- `TransformerError`: `TRANSFORM_FAILED`
- `FeatureSelectionError`: `FEATURE_SELECTION_FAILED`
- `InferenceError`: `INFERENCE_FAILED`
- `EvaluatorError`: `EVALUATION_FAILED`

---

### Decision 7: Import Allowlist Narrowing — `{"energizados.", "src."}` Default, Extension Function

**Choice**: Change `ALLOWED_PREFIXES` default to `{"energizados.", "src."}` (as a set for O(1) lookup). Add `register_allowed_prefix(prefix: str)` module-level function. Raise `ConfigurationError` with per-instance `error_code="CONFIG_INVALID_CLASS_PREFIX"` on blocked prefix.

**Alternatives considered**:
- **Keep broad prefixes**: Defeats the security goal.
- **Config file allowlist**: Over-engineering for project-level customization.

**Rationale**:
- `{"src."}` covers all generated project custom classes
- `{"energizados."}` covers framework internals
- Module-level function is simple and explicit
- Thread-safety caveat documented (not an issue for single-threaded CLI/workflow)

**Implementation** (`core/utils/import_utils.py`):
```python
from typing import Set

ALLOWED_PREFIXES: Set[str] = {
    "energizados.",
    "src.",
}
"""Default allowed prefixes for dynamic class imports.

This set is used to prevent arbitrary code execution when importing
classes dynamically from configuration files. Only classes from modules
starting with these prefixes can be imported.
"""

def register_allowed_prefix(prefix: str) -> None:
    """Register a custom allowed prefix for dynamic imports.

    Args:
        prefix: Module prefix to allow (e.g., "ml_models")

    Note:
        Not thread-safe. Call during initial setup before any framework usage.
        The trailing dot is added automatically if omitted.
    """
    if not prefix.endswith("."):
        prefix = prefix + "."
    ALLOWED_PREFIXES.add(prefix)

def import_class(class_path: str) -> type:
    """Import with validation."""
    # Check allowlist
    if not any(class_path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        from energizados.core.exceptions import ConfigurationError
        raise ConfigurationError(
            f"Class '{class_path}' is not in allowed module prefixes. "
            f"Allowed: {sorted(ALLOWED_PREFIXES)}",
            error_code="CONFIG_INVALID_CLASS_PREFIX",  # Per-instance override
        )
    # ... rest unchanged
```

**Migration guide** (release notes):
> If your project uses custom classes from `"data."` or `"features."` prefixes, call `register_allowed_prefix()` before framework usage:
> ```python
> from energizados.core.utils.import_utils import register_allowed_prefix
> register_allowed_prefix("data")
> register_allowed_prefix("features")
> ```

---

### Decision 8: CLI Delegation Pattern — Shared JSON Helper

**Choice**: Each CLI command delegates to `energizados.api`. `--json` flag uses shared helper `_output_json(result)` that calls `.to_dict()` + `json.dumps`. Human output unchanged.

**Alternatives considered**:
- **Separate JSON output path**: Duplicates logic.
- **Mixin base class**: Overkill for simple serialization.

**Rationale**:
- Shared helper ensures consistent JSON formatting across commands
- `to_dict()` on result types (ValidationResult, RunResult, DoctorReport) provides canonical serialization
- Human formatting preserved in CLI modules

**Implementation sketch** (`cli/main.py`):
```python
import json
from typing import Any

def _output_json(data: Any) -> None:
    """Output data as JSON to stdout."""
    if hasattr(data, "to_dict"):
        data = data.to_dict()
    click.echo(json.dumps(data, indent=2, default=str))

# cli/run.py
def run(config_paths, json_output=False, **kwargs):
    result = execute_pipeline(config_paths, **kwargs)
    if json_output:
        _output_json(result)
    else:
        _print_metrics_summary(result)

# cli/validate.py
def validate(config_paths, json_output=False, **kwargs):
    result = validate_config(config_paths, **kwargs)
    if json_output:
        _output_json(result)
    else:
        _print_validation_results(result)

# cli/doctor.py
def doctor(json_output=False, **kwargs):
    report = run_checks(**kwargs)
    if json_output:
        _output_json(report)
    else:
        for renderable in format_report(report):
            console.print(renderable)
```

**Per-command delegation**:
- `run`: Delegates to `Pipeline.from_dict().run(progress_callback=console_progress() if not json else None)`
- `validate`: Delegates to `api.validate_dict()`
- `doctor`: Delegates to `api.doctor()`
- `init`: Unchanged (primarily CLI, generator function extractable but not in `api/`)

---

### Decision 9: Metrics Unification — Alias Setting with Warning on Context Access

**Choice**: In `TrainingStep`, set BOTH `context["metrics"]` (canonical) AND `context["model_metrics"]` (deprecated alias). Use a custom dict wrapper `MetricsDict` that emits `DeprecationWarning` when `model_metrics` is accessed. `Pipeline.run()` returns this wrapped context.

**Alternatives considered**:
- **Property on RunResult**: Would require `result.model_metrics` instead of dict access — breaking change.
- **Post-processing step in TrainingStep**: More invasive than dict subclass.

**Rationale**:
- Setting both keys ensures existing code reading `model_metrics` continues to work
- Dict wrapper with deprecation warning guides migration
- `metrics` is canonical for both single and ensemble
- Minimal invasiveness — only affects context dict construction

**Implementation** (`core/steps/training.py`):
```python
import warnings
from typing import Any, Dict

class MetricsDict(dict):
    """Dict that emits deprecation warning on legacy model_metrics access."""

    def __getitem__(self, key: str) -> Any:
        if key == "model_metrics":
            warnings.warn(
                "'model_metrics' is deprecated; use 'metrics' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            # Return canonical metrics key (set below)
            return super().__getitem__("metrics")
        return super().__getitem__(key)

# In TrainingStep.execute() - after training completes
def _build_result(self, context: Dict[str, Any]) -> Dict[str, Any]:
    """Build result context with metrics unification."""
    # ... existing result building ...

    # Set canonical metrics key for both single and ensemble
    if not self.ensemble_config and len(self.models_configs) == 1:
        # Single model: metrics from val_auc/val_f1
        result["metrics"] = {"auc": val_auc, "f1": val_f1}
    else:
        # Ensemble or comparison mode: metrics from ensemble or per-model dict
        result["metrics"] = val_metrics or {"auc": val_auc, "f1": val_f1}

    # Wrap in MetricsDict for deprecation warning on model_metrics access
    # The wrapper sits at the CONTEXT level, not inside RunResult
    return MetricsDict(result)
```

**Key point**: `MetricsDict` wraps the context dict BEFORE `Pipeline.run()` returns it. This ensures:
- `result["metrics"]` → direct access (canonical)
- `result["model_metrics"]` → triggers `MetricsDict.__getitem__` → warning + returns metrics
- `RunResult.from_context(result)` → sees the wrapped dict, so both `result_context["model_metrics"]` and `run_result._context["model_metrics"]` hit the warning

**Access path trace**:
```
TrainingStep.execute()
  └─> return MetricsDict({**context, "metrics": {...}})  # Sets metrics, wrapper handles model_metrics

Pipeline.run()
  └─> self.context = step.execute(self.context)  # Context is now MetricsDict
  └─> return self.context  # Returns MetricsDict (subclass of dict)

Legacy code:
  result = pipeline.run()
  result["metrics"]      → Direct access (canonical, no warning)
  result["model_metrics"] → MetricsDict.__getitem__ → DeprecationWarning → returns metrics

New code:
  result = RunResult.from_context(pipeline.run())
  result.metrics         → Direct attribute access (canonical)
  result._context["metrics"]      → Direct access (canonical)
  result._context["model_metrics"] → MetricsDict.__getitem__ → DeprecationWarning → returns metrics
```

## Data Flow

### Validation Flow (CLI → API)

```
cli/validate.py:validate()
  └─> api.validate_dict(config, "etl")
        └─> ValidationResult(is_valid, errors, warnings)
  └─> if --json: _output_json(result.to_dict())
  └─> else: _print_validation_results(result)
```

### Pipeline Run Flow (Dict Config)

```
User code:
  pipeline = Pipeline.from_dict(config)
  result = pipeline.run(progress_callback=my_callback)  # Returns dict
  structured = RunResult.from_context(result)  # Optional: wrap for structured access

Pipeline.from_dict()
  └─> Pipeline.__init__(config=dict_config)

Pipeline.run()
  ├─> Generate run_id
  ├─> For each step:
  │   ├─> Emit ProgressEvent(step="start")
  │   ├─> Execute step (context may be wrapped in MetricsDict)
  │   └─> Emit ProgressEvent(step="complete")
  └─> Return self.context (plain dict or MetricsDict)
```

### CLI Delegation Flow

```
cli/run.py:execute_pipeline()
  └─> merge_configs(config_paths)  # cli/run.py helper
  └─> Pipeline.from_dict(merged_config)
        └─> ConfigPipelineBuilder (unchanged internal path)
  └─> pipeline.run(progress_callback=console_progress())
  └─> if --json: _output_json(RunResult.from_context(result).to_dict())
  └─> else: _print_metrics_summary(result)
```

### Exception Flow (Web Service Scenario)

```
Web service handler:
  try:
    result = Pipeline.from_dict(config).run()
  except EnergizadosError as e:
    return jsonify(e.to_dict()), 400

Exception hierarchy:
  EnergizadosError (base)
    ├─> error_code = "ENERGIZADOS_ERROR" (class attr, overridable per instance)
    ├─> to_dict() returns {error_code, message, details}
    └─> Subclasses override error_code, extend to_dict()

Per-instance override:
  ConfigurationError(..., error_code="CONFIG_INVALID_CLASS_PREFIX")
    └─> self.error_code = "CONFIG_INVALID_CLASS_PREFIX" (instance attr shadows class attr)
```

## Module Map

### New Modules

| Module | Purpose | Public API |
|--------|---------|------------|
| `api/__init__.py` | Public surface re-exports | `validate_dict`, `ValidationResult`, `Pipeline`, `RunManager`, `RunResult`, `RunMetadata`, `ProgressEvent`, `doctor`, `merge_configs` |
| `api/validate.py` | Config validation without file I/O | `validate_dict(config, config_type) -> ValidationResult` |
| `api/pipeline.py` | Pipeline re-exports | Re-exports `core.Pipeline`, `from_dict` classmethod (defined in core) |
| `api/run_state.py` | Run metadata queries and types | `RunManager.get_run`, `list_runs`, `get_latest_run`, `RunResult.from_context`, `RunMetadata.from_dict` |
| `api/progress.py` | Progress events and console callback | `ProgressEvent`, `console_progress` |
| `api/exceptions.py` | Error formatting helper | `format_error(exception) -> dict` |
| `api/config.py` | Config merging and doctor | `merge_configs(configs)`, `doctor() -> DoctorReport` |

### Modified Modules

| Module | Changes | Backward Compat? |
|--------|---------|------------------|
| `core/exceptions.py` | Add `error_code` class attr, `to_dict()` method, per-instance override support in `__init__` | Yes — stdlib base unchanged, `except ValueError` still works |
| `core/utils/import_utils.py` | Narrow `ALLOWED_PREFIXES` to set, add `register_allowed_prefix()`, raise `ConfigurationError` with per-instance code | No — opt-in via `register_allowed_prefix()` |
| `core/pipeline.py` | Add `from_dict()` classmethod, add `plan()` method | Yes — existing `config_path` param still works |
| `core/builders/run_manager.py` | Add `get_run`, `list_runs`, `get_latest_run` methods, extend `_write_run_metadata` with status/output_paths | Yes — additions only |
| `core/steps/training.py` | Add `MetricsDict` wrapper, set `metrics` key in result | Yes — adds `metrics` key, wraps context |
| `cli/run.py` | Delegate to `api`, add `--json` flag support | Yes — CLI flags unchanged, JSON output is additive |
| `cli/validate.py` | Delegate to `api.validate_dict`, add `--json` flag | Yes — same |
| `cli/doctor.py` | Delegate to `api.doctor`, add `--json` flag | Yes — same |
| `cli/init.py` | Unchanged | Yes |

### Unchanged Modules

- `contracts.py` — frozen, no changes
- `core/base.py` — unchanged
- `core/steps/*.py` — unchanged (except `training.py` for MetricsDict)
- `etl/` — unchanged
- `modeling/` — unchanged
- `evaluation/` — unchanged

## Interfaces / Contracts

### `ValidationResult` (api/validate.py)

```python
@dataclass
class ValidationResult:
    """Result of config validation."""
    is_valid: bool
    errors: List[ConfigError]
    warnings: List[ConfigWarning]
    info: List[ConfigInfo]

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "info": [i.to_dict() for i in self.info],
        }
```

### `ProgressEvent` (api/progress.py)

```python
@dataclass
class ProgressEvent:
    """Progress event emitted during pipeline execution."""
    run_id: str
    step_name: str
    phase: str  # "start", "progress", "complete", "error"
    message: str
    percent: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return asdict(self)
```

### `RunManager` Query API (api/run_state.py)

```python
class RunManager:
    """Query interface for run metadata."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        """Get metadata for specific run ID."""
        ...

    def list_runs(
        self, filter: Optional[Dict[str, Any]] = None, limit: int = 100
    ) -> List[RunMetadata]:
        """List runs with optional filter (status, date_range)."""
        ...

    def get_latest_run(self) -> Optional[RunMetadata]:
        """Get most recent run."""
        ...
```

### `Pipeline` Extensions (core/pipeline.py)

```python
class Pipeline:
    """ML workflow orchestrator."""

    def __init__(self, config_path: str = None, config: Dict = None):
        """Initialize from file path OR dict (unchanged signature)."""
        # ... existing implementation

    @classmethod
    def from_dict(cls, config: Dict, context: Optional[Dict] = None) -> "Pipeline":
        """Create Pipeline from dict config (explicit factory)."""
        return cls(config=config)

    def plan(self) -> ExecutionPlan:
        """Return execution plan without running."""
        # Validate config, build step list, check dependencies
        # Return ExecutionPlan(steps, dependencies, estimated_duration)
        ...

    def run(self) -> Dict[str, Any]:
        """Execute pipeline and return context dict (unchanged)."""
        # ... existing implementation
        return self.context
```

## Testing Strategy

### Unit Tests

| Component | Test Coverage | Approach |
|-----------|---------------|----------|
| `validate_dict()` | Valid/invalid configs, all config types | Fixture-driven, assert `ValidationResult` fields |
| `Pipeline.from_dict()` | Dict config creates valid Pipeline | Compare to file-path loaded Pipeline |
| `Pipeline.plan()` | Reveals cycles, filters disabled steps | Mock configs, assert `ExecutionPlan` |
| `RunResult.from_context()` | Builds from context, preserves metrics | Assert structured fields match context |
| `ProgressEvent` | `to_dict()`, all fields | Dataclass serialization tests |
| `RunManager` queries | `get_run`, `list_runs`, `get_latest_run` | Fake run directory, assert metadata |
| `Exception.to_dict()` | All exception types, error_code unique, per-instance override | Assert dict structure, unique codes, instance override works |
| `import_class()` | Blocked prefix, allowed prefix, register_allowed_prefix | Assert `ConfigurationError` raised, prefix registration works |
| `MetricsDict` | `context["metrics"]`, `context["model_metrics"]` | Assert deprecation warning, value equality |
| `RunMetadata.from_dict()` | Old runs (missing fields), new runs (all fields) | Assert tolerant loader supplies defaults |
| CLI `--json` | All commands | Capture stdout, assert JSON valid |

### Integration Tests

| Scenario | Verification |
|----------|--------------|
| CLI run with dict config | Same output as file-path config |
| CLI validate --json | JSON matches `ValidationResult.to_dict()` |
| CLI doctor --json | JSON matches `DoctorReport` structure |
| Progress callback receives events | Mock callback, assert all events received |
| Callback error doesn't abort run | Callback raises, run continues |
| Old run_metadata.json loads | `RunMetadata.from_dict()` supplies defaults for missing fields |

### Regression Tests

- All existing tests pass: `pytest tests/`
- Behavior preservation: CLI output unchanged (except `--json` mode)
- Pickle compatibility: Old `.pkl` files load unchanged
- `Pipeline.run()` return type still `Dict[str, Any]`

### TDD Ordering (Strict TDD Mode)

1. **Write RED tests** for:
   - `validate_dict()` with valid/invalid configs
   - `Pipeline.from_dict()` equivalence to file-path loading
   - `Exception.to_dict()` for all exception types
   - Exception per-instance `error_code` override
   - `MetricsDict` deprecation warning
   - `RunMetadata.from_dict()` tolerant loader
2. **Implement features**: Tests turn GREEN
3. **CLI `--json` tests**: Assert JSON output matches expected structure
4. **Integration tests**: Full pipeline run with progress callback
5. **Regression**: Verify all existing tests pass

## Migration / Rollout

### Single-PR Execution Order

1. **Add `api/` module**:
   - Create `api/__init__.py`, `validate.py`, `pipeline.py`, `run_state.py`, `progress.py`, `exceptions.py`, `config.py`
   - Write RED tests for all new API functions

2. **Modify `core/exceptions.py`**:
   - Add `error_code` class attribute to `EnergizadosError`
   - Add `__init__` with `error_code` parameter and `**details`
   - Add `to_dict()` method to `EnergizadosError`
   - Update subclasses to forward `error_code` in `__init__`
   - Override `error_code` in subclasses via class attribute
   - Tests turn GREEN

3. **Modify `core/utils/import_utils.py`**:
   - Change `ALLOWED_PREFIXES` to set with narrowed defaults
   - Add `register_allowed_prefix()` function
   - Update `import_class()` to raise `ConfigurationError` with per-instance `error_code`
   - Tests verify blocked prefix raises, prefix registration works

4. **Modify `core/pipeline.py`**:
   - Add `from_dict()` classmethod
   - Add `plan()` method
   - Tests verify equivalence, plan reveals cycles

5. **Modify `core/builders/run_manager.py`**:
   - Add `get_run`, `list_runs`, `get_latest_run` methods
   - Extend `_write_run_metadata()` with `status` and `output_paths`
   - Use `RunMetadata.from_dict()` in query methods
   - Tests verify query accuracy, old runs load

6. **Modify `core/steps/training.py`**:
   - Add `MetricsDict` subclass
   - Set `metrics` key in result (unified)
   - Wrap result context in `MetricsDict` before return
   - Test verifies deprecation warning on `model_metrics` access

7. **Modify CLI commands**:
   - `cli/run.py`: Add `--json` flag, use `_output_json()`
   - `cli/validate.py`: Delegate to `api.validate_dict()`, add `--json`
   - `cli/doctor.py`: Delegate to `api.doctor()`, add `--json`
   - Tests verify human output unchanged, JSON valid

8. **Add CLI tests**:
   - `--json` flag for run, validate, doctor
   - Assert JSON output matches expected structure

9. **Final regression**:
   - `pytest tests/` passes
   - Manual CLI smoke test

### Rollback Plan

- **Revert commit**: All changes in single PR — one revert
- **No data migration**: `RunMetadata.from_dict()` tolerant loader handles old runs
- **Pickle safe**: No class moves, no `__module__` changes
- **ALLOWED_PREFIXES**: Document rollback to broad prefixes in release notes if needed

## Open Questions

None. All 9 design decisions resolved.

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| **MetricsDict deprecation warning disrupts users** | Medium | Document clearly in release notes; warning only on `model_metrics` access |
| **ALLOWED_PREFIXES narrowing breaks existing projects** | Medium | Document `register_allowed_prefix()` migration; keep `src.` default |
| **Callback error isolation hides bugs** | Low | Log all callback errors at ERROR level; user-visible logs |
| **RunResult.from_context() confusion** | Low | Clear docstring; document that context is passed by reference |
| **JSON serialization edge cases (datetime, NaN)** | Low | Use `default=str` in `json.dumps`; `datetime.isoformat()` in `to_dict()` |
| **CLI `--json` output format drift** | Low | Shared `_output_json()` helper ensures consistency |
| **Progress callback overhead** | Low | Callback only invoked when provided; no default overhead |
| **Old run_metadata.json missing new fields** | Low | `RunMetadata.from_dict()` tolerant loader supplies defaults |

## Phase Split Recommendation

**Single PR is feasible** — estimated diff ~350 lines:
- `api/` module: ~150 lines (7 files)
- `core/exceptions.py`: ~40 lines (added `__init__`, `error_code`, `to_dict`)
- `core/utils/import_utils.py`: ~20 lines (narrowed prefixes, registration function)
- `core/pipeline.py`: ~30 lines (from_dict, plan methods)
- `core/builders/run_manager.py`: ~40 lines (query methods, metadata extension)
- `core/steps/training.py`: ~30 lines (MetricsDict, metrics unification)
- CLI modifications: ~80 lines (run, validate, doctor, shared helper)
- Tests: ~250 lines (not counted in diff budget)

**If split needed**, divide into:
1. **PR1: Core changes** (exceptions, import_utils, pipeline, run_manager, MetricsDict)
2. **PR2: API layer** (api/ module)
3. **PR3: CLI delegation** (--json flags, thin clients)

But single PR is recommended for cohesive feature delivery.

## Gate Fixes Applied

The following 6 gate failures from the previous draft have been corrected:

1. **RunResult backward compatibility** (CRITICAL): `Pipeline.run()` now continues to return the existing context dict unchanged. `RunResult` is a separate accessor with `from_context()` classmethod. Zero break to existing callers.

2. **MetricsDict + RunResult composition** (CRITICAL): `MetricsDict` wraps the context dict in `TrainingStep.execute()` BEFORE `Pipeline.run()` returns it. Both direct dict access (`result["model_metrics"]`) and `RunResult._context["model_metrics"]` hit the deprecation warning.

3. **Per-instance error_code** (CRITICAL): `EnergizadosError.__init__` now accepts `error_code` parameter and stores it as instance attribute (`self.error_code = error_code`), shadowing the class attribute. `ConfigurationError` forwards this parameter, enabling per-instance override for prefix violations.

4. **from_dict duplicate definition** (MAJOR): `from_dict` is defined ONCE in `core.Pipeline` as a classmethod. The `api` layer simply re-exports `Pipeline` without subclassing or redefining it.

5. **RunMetadata(**data) crashes on old runs** (MAJOR): Added `RunMetadata.from_dict()` classmethod with tolerant loading: missing fields get defaults, unknown keys are ignored. `get_run` and `list_runs` use this loader.

6. **list_runs only globs train-*** (MINOR): `list_runs` now uses `glob("*-*")` pattern to discover all run types (train, eda, inference, or custom names).

All fixes maintain backward compatibility and the "additive only" constraint.
