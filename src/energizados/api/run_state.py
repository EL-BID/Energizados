"""
Run state and result API for Energizados.

This module provides RunResult for structured access to pipeline results
and re-exports RunManager and RunMetadata from core.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# Re-export from core (placed here to avoid circular import between api and core layers)
# noqa: E402
from energizados.core.builders.run_manager import RunManager, RunMetadata

logger = logging.getLogger(__name__)

__all__ = ["RunManager", "RunMetadata", "RunResult", "from_dict"]


@dataclass
class RunResult:
    """Structured result from Pipeline.run().

    This is a VIEW over the pipeline context dict. The context is NOT copied;
    RunResult holds a reference. Modifications to context affect RunResult and vice versa.

    Attributes:
        run_id: Run identifier (may be None if run hasn't written metadata yet)
        status: Run status ("success", "partial", "failed")
        start_time: Run start time (optional)
        end_time: Run end time (optional)
        metrics: Metrics dict (empty for non-training runs)
        output_paths: Dict mapping step names to output file paths
        _context: Reference to full pipeline context (not a copy)
    """

    run_id: Optional[str]
    status: str
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

        Args:
            context: Pipeline context dict returned by Pipeline.run()

        Returns:
            RunResult with structured access to common fields
        """
        # Handle None context gracefully
        if context is None:
            context = {}

        # Extract metrics (may be None for non-training runs)
        metrics = context.get("metrics") or context.get("model_metrics") or {}

        return cls(
            run_id=context.get("run_id"),
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


# Alias for from_dict classmethod (already exists in RunMetadata)
from_dict = RunMetadata.from_dict
