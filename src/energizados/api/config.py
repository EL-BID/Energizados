"""
Configuration utilities API for Energizados.

This module provides merge_configs() for deep-merging configuration dicts
and doctor() for system health checks.
"""

import logging
import platform
import sys
from typing import Any, Dict, List, Tuple

from energizados._version import get_version

logger = logging.getLogger(__name__)

__all__ = [
    "merge_configs",
    "doctor",
    "DoctorReport",
    "CheckResult",
    "REQUIRED_PACKAGES",
    "OPTIONAL_PACKAGES",
]

# Required packages checked by doctor(): {import_name: (pypi_name, min_version)}.
# import_name and pypi_name differ for some packages (e.g. sklearn vs scikit-learn);
# importing by pypi_name silently fails (the bug fixed in this commit), so the
# dict keeps them explicitly separated.
REQUIRED_PACKAGES: Dict[str, Tuple[str, str]] = {
    "pandas": ("pandas", "2.0.0"),
    "numpy": ("numpy", "1.20.0"),
    "sklearn": ("scikit-learn", "1.4.2"),
    "lightgbm": ("lightgbm", "4.6.0"),
    "yaml": ("pyyaml", "6.0"),
    "click": ("click", "8.0"),
}

# Optional packages (not in core dependencies). Same shape as REQUIRED_PACKAGES.
OPTIONAL_PACKAGES: Dict[str, Tuple[str, str]] = {
    "matplotlib": ("matplotlib", "3.5.0"),
    "seaborn": ("seaborn", "0.11.2"),
}


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


def get_system_info() -> Dict[str, str]:
    """Gather system information (platform, CPU, memory, disk, GPU).

    Uses psutil when available for hardware details; falls back to the
    ``os`` module with "Unknown (install psutil)" placeholders otherwise.

    Returns:
        Dictionary with system details.
    """
    import os

    info = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
    }

    try:
        import psutil  # type: ignore[import-not-found]

        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        info.update(
            {
                "cpu_physical_cores": (
                    str(cpu_count_physical) if cpu_count_physical else "Unknown"
                ),
                "cpu_logical_cores": str(cpu_count_logical) if cpu_count_logical else "Unknown",
                "cpu_freq_mhz": f"{cpu_freq.max:.0f} MHz" if cpu_freq else "Unknown",
                "cpu_usage": f"{cpu_percent}%",
            }
        )

        mem = psutil.virtual_memory()
        info.update(
            {
                "memory_total": f"{mem.total / (1024**3):.2f} GB",
                "memory_available": f"{mem.available / (1024**3):.2f} GB",
                "memory_percent": f"{mem.percent}%",
            }
        )

        # psutil.disk_usage("/") raises OSError (WinError 3) on Windows because
        # "/" is not a valid mount point. Use a portable root instead.
        root_path = os.path.abspath(os.sep)  # "/" on POSIX, "C:\\" on Windows
        try:
            disk = psutil.disk_usage(root_path)
            info.update(
                {
                    "disk_total": f"{disk.total / (1024**3):.2f} GB",
                    "disk_used": f"{disk.used / (1024**3):.2f} GB",
                    "disk_free": f"{disk.free / (1024**3):.2f} GB",
                    "disk_percent": f"{disk.percent}%",
                }
            )
        except OSError as e:
            logger.warning(f"Could not read disk usage for '{root_path}': {e}")
            info.update(
                {
                    "disk_total": "0.00 GB",
                    "disk_used": "0.00 GB",
                    "disk_free": "0.00 GB",
                    "disk_percent": "0.0%",
                }
            )

    except (ImportError, OSError):
        # Fallback to os module for basic info
        info.update(
            {
                "cpu_physical_cores": "Unknown (install psutil)",
                "cpu_logical_cores": (
                    str(os.cpu_count()) if hasattr(os, "cpu_count") else "Unknown"
                ),
                "cpu_freq_mhz": "Unknown (install psutil)",
                "cpu_usage": "Unknown (install psutil)",
                "memory_total": "Unknown (install psutil)",
                "memory_available": "Unknown (install psutil)",
                "memory_percent": "Unknown (install psutil)",
                "disk_total": "Unknown (install psutil)",
                "disk_used": "Unknown (install psutil)",
                "disk_free": "Unknown (install psutil)",
                "disk_percent": "Unknown (install psutil)",
            }
        )

    return info


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

    # Gather system info (platform + hardware via psutil when available)
    report.system_info = get_system_info()
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
    missing_packages = _find_missing_packages(REQUIRED_PACKAGES)

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
        missing_optional = _find_missing_packages(OPTIONAL_PACKAGES)

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


def _find_missing_packages(packages: Dict[str, Tuple[str, str]]) -> List[str]:
    """Return the pypi names of packages that cannot be imported.

    Args:
        packages: Mapping of ``{import_name: (pypi_name, min_version)}``.

    Returns:
        List of pypi names (suitable for ``pip install``) that failed to import.
    """
    missing: List[str] = []
    for import_name, (pypi_name, _min_version) in packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pypi_name)
    return missing
