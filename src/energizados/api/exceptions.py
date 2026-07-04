"""
Exception formatting API for Energizados.

This module provides format_error() helper for converting exceptions
to machine-readable dict format.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

__all__ = ["format_error"]


def format_error(exception: Exception) -> Dict[str, Any]:
    """Convert exception to machine-readable dict format.

    If the exception is an EnergizadosError, calls its to_dict() method.
    For generic exceptions, creates a dict with error_type and message.

    Args:
        exception: Exception to format

    Returns:
        Dict with error_code, message, and details (or error_type for generic exceptions)
    """
    from energizados.core.exceptions import EnergizadosError

    if isinstance(exception, EnergizadosError):
        # Use framework exception's to_dict() method (includes config_path for ConfigurationError)
        return exception.to_dict()
    else:
        # Generic exception - create basic dict
        return {
            "error_code": "GENERIC_ERROR",
            "error_type": type(exception).__name__,
            "message": str(exception),
            "details": {},
        }
