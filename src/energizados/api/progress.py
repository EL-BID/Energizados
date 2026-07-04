"""
Progress event API for Energizados.

This module provides ProgressEvent dataclass and console_progress callback
factory for pipeline execution observability.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["ProgressEvent", "console_progress"]


@dataclass
class ProgressEvent:
    """Progress event emitted during pipeline execution.

    Attributes:
        run_id: Run identifier
        step_name: Name of the pipeline step
        phase: Phase of the step ("start", "progress", "complete", "error")
        message: Human-readable message
        percent: Optional percentage (0.0 to 100.0)
        timestamp: Event timestamp (UTC)
    """

    run_id: str
    step_name: str
    phase: str  # "start", "progress", "complete", "error"
    message: str
    percent: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "run_id": self.run_id,
            "step_name": self.step_name,
            "phase": self.phase,
            "message": self.message,
            "percent": self.percent,
            "timestamp": self.timestamp.isoformat(),
        }


def console_progress() -> Callable[[ProgressEvent], None]:
    """Progress callback that renders to Rich console (CLI default).

    Returns a callback function that emits events to the active Rich console
    for CLI use. For programmatic use, provide your own callback.

    Returns:
        Callable[[ProgressEvent], None]: Callback function for progress events
    """

    def callback(event: ProgressEvent) -> None:
        """Handle progress event by rendering to console."""
        # Reuse existing Rich progress logic from cli/run.py
        # For now, just log the event (full Rich integration would be here)
        logger.debug(
            f"Progress: {event.step_name} - {event.phase} - {event.message}"
            + (f" ({event.percent}%)" if event.percent is not None else "")
        )

    return callback
