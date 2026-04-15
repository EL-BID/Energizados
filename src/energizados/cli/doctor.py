"""
Doctor command implementation for Energizados CLI.

This module implements the 'doctor' command to check system information
and validate the environment (Python version, required libraries).
"""

import os
import platform
import shutil
import sys
from typing import Dict, List, Tuple

# Required packages from pyproject.toml
REQUIRED_PACKAGES = {
    "boruta": "0.4.3",
    "click": "8.0",
    "imblearn": "0.12.0",
    "joblib": "1.3.0",
    "lightgbm": "4.6.0",
    "numpy": "1.20.0",
    "pandas": "2.0.0",
    "plotly": "5.0.0",
    "pyarrow": "19.0.0",
    "yaml": "6.0",  # PyYAML imports as yaml
    "requests": "2.32.0",
    "rich": "13.0",
    "sklearn": "1.4.2",  # scikit-learn imports as sklearn
    "scipy": "1.9.0",
    "shap": "0.42.0",
    "tsfel": "0.1.9",
    "tqdm": "4.64.0",
    "unidecode": "1.4.0",
}

# Optional packages (not in core dependencies or require extras)
OPTIONAL_PACKAGES = {
    "catboost": "1.2.8",  # pip install energizados[catboost]
    "tensorflow": "2.17.0",  # pip install energizados[tensorflow]
    "xgboost": "2.0.0",  # pip install energizados[xgboost]
    "matplotlib": "3.5.0",
    "seaborn": "0.11.2",
    "psutil": "5.9.0",
    "GPUtil": "1.4.0",
}

# Minimum Python version
MIN_PYTHON_VERSION = (3, 10)
RECOMMENDED_PYTHON_VERSION = (3, 11)


class CheckResult:
    """Container for a single check result.

    Attributes:
        name: Name of the check.
        status: 'ok', 'warning', or 'error'.
        message: Descriptive message.
        solution: How to fix if status is not 'ok'.
    """

    def __init__(self, name: str, status: str, message: str, solution: str = "") -> None:
        self.name = name
        self.status = status
        self.message = message
        self.solution = solution


class DoctorReport:
    """Container for doctor command results.

    Attributes:
        system_info: Dictionary with system information.
        checks: List of CheckResult objects.
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


def get_system_info() -> Dict[str, str]:
    """Gather system information.

    Returns:
        Dictionary with system details.
    """
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

    # Try to get detailed system info using psutil
    try:
        import psutil

        # CPU info
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_percent = psutil.cpu_percent(interval=0.1)

        info.update(
            {
                "cpu_physical_cores": str(cpu_count_physical) if cpu_count_physical else "Unknown",
                "cpu_logical_cores": str(cpu_count_logical) if cpu_count_logical else "Unknown",
                "cpu_freq_mhz": f"{cpu_freq.max:.0f} MHz" if cpu_freq else "Unknown",
                "cpu_usage": f"{cpu_percent}%",
            }
        )

        # Memory info
        mem = psutil.virtual_memory()
        mem_total_gb = mem.total / (1024**3)
        mem_available_gb = mem.available / (1024**3)
        mem_percent = mem.percent

        info.update(
            {
                "memory_total": f"{mem_total_gb:.2f} GB",
                "memory_available": f"{mem_available_gb:.2f} GB",
                "memory_percent": f"{mem_percent}%",
            }
        )

        # Disk info
        disk = psutil.disk_usage("/")
        disk_total_gb = disk.total / (1024**3)
        disk_used_gb = disk.used / (1024**3)
        disk_free_gb = disk.free / (1024**3)
        disk_percent = disk.percent

        info.update(
            {
                "disk_total": f"{disk_total_gb:.2f} GB",
                "disk_used": f"{disk_used_gb:.2f} GB",
                "disk_free": f"{disk_free_gb:.2f} GB",
                "disk_percent": f"{disk_percent}%",
            }
        )

    except ImportError:
        # Fallback to os module for basic info
        info.update(
            {
                "cpu_physical_cores": "Unknown (install psutil)",
                "cpu_logical_cores": str(os.cpu_count()) if hasattr(os, "cpu_count") else "Unknown",
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

    # GPU info (optional)
    info["gpu"] = _get_gpu_info()

    return info


def _get_gpu_info() -> str:
    """Get GPU information if available.

    Returns:
        String with GPU info or "Not available".
    """
    try:
        import GPUtil

        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_info = []
            for gpu in gpus:
                gpu_info.append(
                    f"{gpu.name} ({gpu.memoryTotal:.0f}MB, "
                    f"{gpu.memoryUsed:.0f}MB used, {gpu.load * 100:.0f}% load)"
                )
            return ", ".join(gpu_info)
    except ImportError:
        pass

    # Try nvidia-smi as fallback
    try:
        result = shutil.which("nvidia-smi")
        if result:
            import subprocess  # nosec B404

            output = subprocess.check_output(  # nosec B603 B607
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,utilization.gpu"],
                text=True,
            )
            lines = output.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split(",")
                if len(parts) >= 4:
                    return f"{parts[0].strip()} ({parts[1].strip()}, {parts[3].strip()})"
    except Exception:  # nosec B110
        pass

    return "Not available"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse version string to tuple of integers.

    Args:
        version_str: Version string (e.g., "1.2.3").

    Returns:
        Tuple of version components.
    """
    # Remove non-numeric suffixes like "rc1", "a2", "dev"
    parts = []
    for part in version_str.split(".")[:3]:  # Only major.minor.patch
        # Extract leading digits
        digits = ""
        for char in part:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            parts.append(int(digits))
        else:
            parts.append(0)
    return tuple(parts) if parts else (0, 0, 0)


def check_python_version() -> CheckResult:
    """Check Python version.

    Returns:
        CheckResult with version validation.
    """
    current = sys.version_info[:3]
    version_str = platform.python_version()

    if current >= MIN_PYTHON_VERSION:
        if current >= RECOMMENDED_PYTHON_VERSION:
            return CheckResult(
                name="Python Version",
                status="ok",
                message=f"Python {version_str} (recommended)",
            )
        return CheckResult(
            name="Python Version",
            status="ok",
            message=f"Python {version_str} (minimum met, consider upgrading to 3.11+)",
        )

    return CheckResult(
        name="Python Version",
        status="error",
        message=f"Python {version_str} (minimum required: 3.10)",
        solution=(
            "Upgrade Python:\n"
            f"  - Current: {version_str}\n"
            f"  - Required: {'.'.join(map(str, MIN_PYTHON_VERSION))}+\n"
            "  - Recommended: 3.11+\n"
            "  - Install from https://www.python.org/downloads/"
        ),
    )


def check_package(
    import_name: str, package_name: str, min_version: str, install_hint: str = ""
) -> CheckResult:
    """Check if a package is installed with minimum version.

    Args:
        import_name: Module name to import.
        package_name: Package name for display and pip install.
        min_version: Minimum required version.
        install_hint: Override the pip install command (e.g. for extras like
            'energizados[catboost]'). If empty, defaults to
            'pip install {package_name}>={min_version}'.

    Returns:
        CheckResult with package validation.
    """
    install_cmd = install_hint or f"'{package_name}>={min_version}'"

    try:
        module = __import__(import_name)
        installed = getattr(module, "__version__", "unknown")

        if installed == "unknown":
            # Try to get version from common attributes
            for attr in ["version", "VERSION", "__version_info__"]:
                ver = getattr(module, attr, None)
                if ver:
                    if isinstance(ver, tuple):
                        installed = ".".join(map(str, ver))
                    else:
                        installed = str(ver)
                    break

        installed_ver = parse_version(installed)
        required_ver = parse_version(min_version)

        if installed_ver >= required_ver:
            return CheckResult(
                name=f"Package: {package_name}",
                status="ok",
                message=f"Version {installed}",
            )
        else:
            return CheckResult(
                name=f"Package: {package_name}",
                status="error",
                message=f"Version {installed} (minimum required: {min_version})",
                solution=f"pip install --upgrade {install_cmd}",
            )

    except ImportError:
        return CheckResult(
            name=f"Package: {package_name}",
            status="error",
            message="Not installed",
            solution=f"pip install {install_cmd}",
        )


def run_checks(include_optional: bool = False) -> DoctorReport:
    """Run all environment checks.

    Args:
        include_optional: Whether to check optional packages.

    Returns:
        DoctorReport with all check results.
    """
    report = DoctorReport()
    report.system_info = get_system_info()

    # Check Python version
    report.add_check(check_python_version())

    # Map import name → pip package name (when they differ)
    PACKAGE_NAME_MAP = {
        "yaml": "pyyaml",
        "sklearn": "scikit-learn",
        "imblearn": "imbalanced-learn",
    }

    # Map import name → extras install hint (for optional framework extras)
    EXTRAS_MAP = {
        "catboost": "energizados[catboost]",
        "tensorflow": "energizados[tensorflow]",
        "xgboost": "energizados[xgboost]",
    }

    # Check required packages
    for import_name, min_version in REQUIRED_PACKAGES.items():
        package_name = PACKAGE_NAME_MAP.get(import_name, import_name)
        report.add_check(check_package(import_name, package_name, min_version))

    # Check optional packages if requested
    if include_optional:
        for import_name, min_version in OPTIONAL_PACKAGES.items():
            package_name = PACKAGE_NAME_MAP.get(import_name, import_name)
            install_hint = f"'energizados[{import_name}]'" if import_name in EXTRAS_MAP else ""
            report.add_check(
                check_package(import_name, package_name, min_version, install_hint=install_hint)
            )

    return report


def format_report(report: DoctorReport, verbose: bool = False) -> list:
    """Format the doctor report as a list of Rich renderables.

    Args:
        report: DoctorReport to format.
        verbose: Whether to show detailed system info.

    Returns:
        List of Rich renderables (Table, Panel) to be printed directly.
    """
    from rich.panel import Panel
    from rich.table import Table

    renderables = []

    # System info section - always show summary
    info = report.system_info
    if verbose:
        # Full detailed table
        info_table = Table(title="[bold]System Information[/]", show_header=False, box=None)
        info_table.add_column("Property", style="cyan", width=25)
        info_table.add_column("Value", style="white")

        sections = {
            "OS & Platform": ["platform", "system", "release", "machine", "hostname"],
            "CPU": [
                "processor",
                "cpu_physical_cores",
                "cpu_logical_cores",
                "cpu_freq_mhz",
                "cpu_usage",
            ],
            "Memory": ["memory_total", "memory_available", "memory_percent"],
            "Disk": ["disk_total", "disk_used", "disk_free", "disk_percent"],
            "Python": ["python_version", "python_implementation", "python_executable"],
            "GPU": ["gpu"],
        }

        for section, keys in sections.items():
            info_table.add_row("", "")
            info_table.add_row(f"[bold]{section}[/]", "")
            for key in keys:
                if key in info:
                    label = key.replace("_", " ").title()
                    value = info[key]
                    # Style unknown values dim
                    if "Unknown" in value or "install psutil" in value:
                        value = f"[dim]{value}[/]"
                    info_table.add_row(f"  {label}", value)

        renderables.append(info_table)

    # Compact summary - always shown
    summary_lines = [f"[cyan]Platform:[/] {info.get('platform', 'Unknown')}"]

    # CPU line (skip if all unknown)
    cpu_cores = info.get("cpu_logical_cores", "")
    cpu_freq = info.get("cpu_freq_mhz", "")
    cpu_usage = info.get("cpu_usage", "")
    if "Unknown" not in cpu_cores or "Unknown" not in cpu_freq:
        summary_lines.append(f"[cyan]CPU:[/] {cpu_cores} cores @ {cpu_freq} ({cpu_usage} usage)")

    # Memory line (skip if unknown)
    mem_avail = info.get("memory_available", "")
    mem_total = info.get("memory_total", "")
    mem_percent = info.get("memory_percent", "")
    if "Unknown" not in mem_avail:
        summary_lines.append(f"[cyan]Memory:[/] {mem_avail} / {mem_total} ({mem_percent} used)")

    # Disk line (skip if unknown)
    disk_free = info.get("disk_free", "")
    disk_total = info.get("disk_total", "")
    disk_percent = info.get("disk_percent", "")
    if "Unknown" not in disk_free:
        summary_lines.append(
            f"[cyan]Disk:[/] {disk_free} free / {disk_total} total ({disk_percent} used)"
        )

    # Python line
    summary_lines.append(
        f"[cyan]Python:[/] {info.get('python_version', 'Unknown')} "
        f"({info.get('python_implementation', 'Unknown')})"
    )

    # GPU line (only if available)
    if info.get("gpu", "Not available") != "Not available":
        summary_lines.append(f"[cyan]GPU:[/] {info['gpu']}")

    summary = "\n".join(summary_lines)
    panel = Panel(
        summary,
        title="[bold]System Summary[/]",
        border_style="cyan",
        padding=(0, 1),
    )
    renderables.append(panel)

    # Checks section
    checks_table = Table(title="Environment Checks", show_header=True)
    checks_table.add_column("Status", style="", width=8)
    checks_table.add_column("Check", style="cyan", width=30)
    checks_table.add_column("Details", style="white")
    checks_table.add_column("Solution", style="yellow", width=40)

    for check in report.checks:
        status_symbol = {
            "ok": "[green]✓[/green]",
            "warning": "[yellow]⚠[/yellow]",
            "error": "[red]✗[/red]",
        }.get(check.status, "?")

        checks_table.add_row(
            status_symbol,
            check.name,
            check.message,
            check.solution,
        )

    renderables.append(checks_table)

    # Summary
    status = "[green]✓ All checks passed![/green]"
    if report.has_warnings():
        status = "[yellow]⚠ Some warnings detected[/yellow]"
    if not report.is_healthy():
        status = "[red]✗ Some checks failed[/red]"

    panel = Panel(
        status,
        title="Summary",
        border_style="green" if report.is_healthy() else "red",
    )
    renderables.append(panel)

    return renderables
