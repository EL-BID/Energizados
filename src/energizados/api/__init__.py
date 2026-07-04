"""
Energizados API - Service layer for programmatic framework usage.

This package provides the public API surface for using Energizados as a library,
with structured return values and no stdout coupling. All CLI commands delegate
to this API layer.

Public API:
- validate_dict(): Configuration validation without file I/O
- Pipeline: Core pipeline orchestrator (re-exported from core)
- RunManager: Query interface for run metadata
- RunResult: Structured access to pipeline results
- ProgressEvent: Progress streaming for observability
- format_error(): Exception formatting helper
- merge_configs(): Configuration merging utility
- doctor(): System health checks
"""

# Configuration utilities API
from energizados.api.config import CheckResult, DoctorReport, doctor, merge_configs

# Exception formatting API
from energizados.api.exceptions import format_error

# Pipeline API (re-export from core)
from energizados.api.pipeline import Pipeline

# Progress API
from energizados.api.progress import ProgressEvent, console_progress

# Run state API
from energizados.api.run_state import RunManager, RunMetadata, RunResult

# Validation API
from energizados.api.validate import (
    ConfigError,
    ConfigInfo,
    ConfigWarning,
    ValidationResult,
    validate_dict,
)

__all__ = [
    # Validation
    "validate_dict",
    "ValidationResult",
    "ConfigError",
    "ConfigWarning",
    "ConfigInfo",
    # Pipeline
    "Pipeline",
    # NOTE: from_dict removed from __all__ to avoid ambiguity
    # Users should call Pipeline.from_dict() or RunMetadata.from_dict() explicitly
    # Run state
    "RunManager",
    "RunResult",
    "RunMetadata",
    # Progress
    "ProgressEvent",
    "console_progress",
    # Exceptions
    "format_error",
    # Configuration utilities
    "merge_configs",
    "doctor",
    "DoctorReport",
    "CheckResult",
]

# Convenience aliases for classmethods (INTERNAL - not in __all__)
from_dict = Pipeline.from_dict
plan = Pipeline.plan
