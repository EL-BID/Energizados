"""
Configuration utilities API for Energizados.

This module provides merge_configs() for deep-merging configuration dicts
and doctor() for system health checks.
"""

import logging
import platform
import sys
from typing import Any, Dict, List

from energizados._version import get_version

logger = logging.getLogger(__name__)

__all__ = ["merge_configs", "doctor", "DoctorReport", "CheckResult"]


def merge_configs(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple configuration dicts with deep merge.

    Uses deep merge so that dict-typed sections (e.g. 'etl:', 'train:')
    are merged key-by-key rather than replaced wholesale. Scalar and list
    values follow "last wins" semantics.

    Example: two configs each with an 'etl:' section will produce a combined
    'etl:' containing all ETL entries from both configs.

    Args:
        configs: List of configuration dictionaries to merge

    Returns:
        Dict: Combined configuration with deep-merged sections
    """
    merged_config: Dict[str, Any] = {}

    for config in configs:
        if not isinstance(config, dict):
            logger.warning(f"Skipping non-dict config: {type(config)}")
            continue
        merged_config = _deep_merge(merged_config, config)

    return merged_config


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dicts. Dict values are merged; all others use override."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Doctor functionality
class CheckResult:
    """Container for a single check result.

    Attributes:
        name: Name of the check
        status: 'ok', 'warning', or 'error'
        message: Descriptive message
        solution: How to fix if status is not 'ok'
    """

    def __init__(self, name: str, status: str, message: str, solution: str = "") -> None:
        self.name = name
        self.status = status
        self.message = message
        self.solution = solution


class DoctorReport:
    """Container for doctor command results.

    Attributes:
        system_info: Dictionary with system information
        checks: List of CheckResult objects
    """

    def __init__(self) -> None:
        self.system_info: Dict[str, str] = {}
        self.checks: List[CheckResult] = []

    def add_check(self, result: CheckResult) -> None:
        """Add a check result to the report."""
        self.checks.append(result)

    def is_healthy(self) -> bool:
        """Check if all critical checks passed."""
        return all(c.status != "error" for c in self.checks)

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return any(c.status == "warning" for c in self.checks)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization.

        Returns:
            Dict with system_info and checks (as dicts)
        """
        return {
            "system_info": self.system_info,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "message": check.message,
                    "solution": check.solution,
                }
                for check in self.checks
            ],
        }


def doctor(include_optional: bool = False) -> DoctorReport:
    """Run system health checks and return structured report.

    Performs checks for:
    - Python version compatibility
    - Platform information
    - Energizados version
    - Required package availability
    - Optional packages (if include_optional=True)

    Args:
        include_optional: If True, also check optional packages like matplotlib, seaborn

    Returns:
        DoctorReport with system_info and checks list
    """
    report = DoctorReport()

    # Gather system info
    report.system_info["python_version"] = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    report.system_info["platform"] = platform.platform()
    report.system_info["energizados_version"] = get_version()

    # Python version check
    min_version = (3, 10)
    current_version = (sys.version_info.major, sys.version_info.minor)
    if current_version < min_version:
        report.add_check(
            CheckResult(
                name="Python Version",
                status="error",
                message=f"Python {current_version[0]}.{current_version[1]} is below minimum {min_version[0]}.{min_version[1]}",
                solution="Upgrade Python to 3.10 or higher",
            )
        )
    else:
        report.add_check(
            CheckResult(
                name="Python Version",
                status="ok",
                message=f"Python {current_version[0]}.{current_version[1]} is compatible",
            )
        )

    # Platform check
    report.add_check(
        CheckResult(
            name="Platform",
            status="ok",
            message=f"Running on {platform.system()} ({platform.machine()})",
        )
    )

    # Energizados version check
    version = get_version()
    if version:
        report.add_check(
            CheckResult(
                name="Energizados Version", status="ok", message=f"Version {version} installed"
            )
        )
    else:
        report.add_check(
            CheckResult(
                name="Energizados Version",
                status="warning",
                message="Could not determine version",
                solution="Ensure energizados is properly installed",
            )
        )

    # Required packages check
    required_packages = {
        "pandas": "2.0.0",
        "numpy": "1.20.0",
        "scikit-learn": "1.4.2",
        "lightgbm": "4.6.0",
        "yaml": "6.0",
        "click": "8.0",
    }

    missing_packages = []
    for package, min_version in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)

    if missing_packages:
        report.add_check(
            CheckResult(
                name="Required Packages",
                status="error",
                message=f"Missing packages: {', '.join(missing_packages)}",
                solution=f"Install missing packages: pip install {' '.join(missing_packages)}",
            )
        )
    else:
        report.add_check(
            CheckResult(
                name="Required Packages", status="ok", message="All required packages installed"
            )
        )

    # Optional packages check (if requested)
    if include_optional:
        optional_packages = {
            "matplotlib": "3.5.0",
            "seaborn": "0.11.2",
        }

        missing_optional = []
        for package, min_version in optional_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing_optional.append(package)

        if missing_optional:
            report.add_check(
                CheckResult(
                    name="Optional Packages",
                    status="warning",
                    message=f"Missing optional packages: {', '.join(missing_optional)}",
                    solution=f"Install optional packages: pip install {' '.join(missing_optional)}",
                )
            )
        else:
            report.add_check(
                CheckResult(
                    name="Optional Packages", status="ok", message="All optional packages installed"
                )
            )

    return report
