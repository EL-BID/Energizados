"""
Run Manager.

This module handles run directory creation, config copying, and post-run tasks.
"""

import json
import logging
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RunMetadata:
    """Metadata for a single run (stored in run_metadata.json)."""

    run_id: str
    timestamp: str
    duration_seconds: float
    energizados_version: str
    python_version: str
    git_commit: str
    model_types: List[str]
    status: str = "success"  # "success", "partial", "failed"
    val_auc: Optional[float] = None
    val_f1: Optional[float] = None
    feature_count: Optional[int] = None
    config_files: List[str] = field(default_factory=list)
    output_paths: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunMetadata":
        """Tolerant loader for old runs (missing fields get defaults)."""
        # Handle None or invalid input gracefully
        if not isinstance(data, dict):
            return cls(
                run_id="",
                timestamp="",
                duration_seconds=0.0,
                energizados_version="",
                python_version="",
                git_commit="",
                model_types=[],
                status="success",
                val_auc=None,
                val_f1=None,
                feature_count=None,
                config_files=[],
                output_paths={},
            )

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


class RunManager:
    """
    Manages run directory creation and post-run tasks.

    Responsible for:
    - Creating timestamped run directories
    - Copying config files to run directory
    - Generating/updating the global run index HTML

    Attributes:
        config_paths: List of config file paths used for this run
    """

    def __init__(
        self,
        config_paths: Optional[List[str]] = None,
        run_name: Optional[str] = None,
        overwrite: bool = False,
        output_dir: Optional[str] = None,
    ):
        """
        Initialize run manager.

        Args:
            config_paths: List of config file paths used for this run
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
            output_dir: Optional output directory path for query API (default: "output")
        """
        self.config_paths: List[str] = config_paths or []
        self._run_dir: Optional[Path] = None
        self._run_name: Optional[str] = run_name
        self._overwrite: bool = overwrite
        self._start_time = time.time()
        self._output_dir: Optional[Path] = Path(output_dir) if output_dir else None

    @property
    def run_dir(self) -> Optional[Path]:
        """Get the current run directory path."""
        return self._run_dir

    def generate_run_dir(
        self,
        base_output_dir: str = "output",
        run_name: Optional[str] = None,
        overwrite: Optional[bool] = None,
    ) -> Path:
        """
        Creates a run directory inside the output base directory.

        If run_name is provided, uses that name directly (deleting existing dir if present).
        If run_name is None, uses a timestamp with suffix for collisions.
        If overwrite=True, deletes existing directory even with auto-generated names.

        Args:
            base_output_dir: Base output directory (default: "output")
            run_name: Optional custom run directory name
            overwrite: Override instance overwrite setting (optional)

        Returns:
            Path: Path to the created run directory
        """
        # Use instance default if not overridden
        use_overwrite = overwrite if overwrite is not None else self._overwrite

        base = Path(base_output_dir)

        if run_name is not None:
            # Use custom run name - delete existing directory if present
            run_dir = base / run_name
            if run_dir.exists():
                logger.info(f"Deleting existing run directory: {run_dir}")
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use timestamp with collision handling
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            prefix = self._get_train_config_name() or "train"
            auto_run_name = f"{prefix}-{timestamp}"
            run_dir = base / auto_run_name

            # Handle timestamp collisions and overwrite
            import os

            # If overwrite is True, delete existing directory first
            if use_overwrite and run_dir.exists():
                logger.info(f"Overwriting existing run directory: {run_dir}")
                shutil.rmtree(run_dir)

            suffix = 0
            while True:
                candidate = run_dir if suffix == 0 else base / f"{auto_run_name}_{suffix}"
                try:
                    os.makedirs(candidate)
                    run_dir = candidate
                    break
                except FileExistsError:
                    # If overwrite is True and directory exists, delete and retry
                    if use_overwrite:
                        logger.info(f"Overwriting existing run directory: {candidate}")
                        shutil.rmtree(candidate)
                        os.makedirs(candidate)
                        run_dir = candidate
                        break
                    suffix += 1

        (run_dir / "models").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "evaluation").mkdir(parents=True, exist_ok=True)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)

        logger.info(f"Training run directory: {run_dir}")
        self._run_dir = run_dir

        # Auto-attach file handler when verbose logging is active (-v/-vv/-vvv)
        import logging as _logging

        root = _logging.getLogger()
        if root.level < _logging.WARNING:
            run_log_path = run_dir / "run.log"
            file_handler = _logging.FileHandler(str(run_log_path), mode="w", encoding="utf-8")
            file_handler.setLevel(root.level)
            file_handler.setFormatter(
                _logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            root.addHandler(file_handler)
            logger.info(f"Run log: {run_log_path}")

        return run_dir

    def _get_train_config_name(self) -> Optional[str]:
        """Return the stem of the first non-etl/eda/infer config path, or None if not found."""
        skip_prefixes = ("etl", "eda", "infer")
        for path in self.config_paths:
            stem = Path(path).stem.lower()
            if not any(
                stem == p or stem.startswith(f"{p}_") or stem.startswith(f"{p}-")
                for p in skip_prefixes
            ):
                return Path(path).stem
        return None

    def copy_configs_to_run_dir(self):
        """Copies the config files used for this run into the run directory."""
        if self._run_dir is None:
            return
        config_target = self._run_dir / "config"
        for config_path in self.config_paths:
            src = Path(config_path)
            if src.exists():
                shutil.copy(src, config_target / src.name)
                logger.info(f"Config copied to run dir: {src.name}")

    def generate_index_html(self):
        """Regenerates output/index.html with all training runs."""
        if self._run_dir is None:
            return
        from energizados.evaluation.index import RunIndexGenerator

        output_dir = self._run_dir.parent
        generator = RunIndexGenerator()
        index_path = generator.generate_index_html(output_dir)
        if index_path:
            logger.info(f"Index HTML updated: {index_path}")

    def _write_run_metadata(self, context: Dict[str, Any]) -> None:
        """
        Write run metadata JSON file to run directory.

        Args:
            context: Context dict containing training results and configuration
        """
        if self._run_dir is None:
            return

        # Calculate duration
        duration_seconds = time.time() - self._start_time

        # Get run_id from directory name
        run_id = self._run_dir.name

        # Get timestamp
        timestamp = datetime.now().isoformat()

        # Get energizados version with fallback
        from energizados._version import get_version

        energizados_version = get_version()

        # Get Python version
        import sys

        python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )

        # Get git commit with fallback
        try:
            git_commit = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except Exception:
            git_commit = "unknown"

        # Extract model types from context
        model_types = []
        if "model" in context and context["model"] is not None:
            model_types.append(type(context["model"]).__name__)
        elif "models" in context and context["models"] is not None:
            model_types = [type(m).__name__ for m in context["models"].values()]

        # Get validation metrics from context
        val_auc = context.get("val_auc")
        val_f1 = context.get("val_f1")

        # Get feature count from context
        feature_count = None
        if "feature_engineering" in context and context["feature_engineering"] is not None:
            fe = context["feature_engineering"]
            if hasattr(fe, "selected_features_") and fe.selected_features_ is not None:
                feature_count = len(fe.selected_features_)

        # Determine status (NEW for Phase 4)
        status = "success"
        if context.get("error"):
            status = "failed"
        elif context.get("comparison_mode"):
            status = "partial"  # Or determine based on step results

        # Build output_paths dict (NEW for Phase 4)
        output_paths = {}
        if "model_path" in context and context["model_path"] is not None:
            output_paths["model"] = context["model_path"]
        if (
            "feature_engineering_path" in context
            and context["feature_engineering_path"] is not None
        ):
            output_paths["feature_engineering"] = context["feature_engineering_path"]

        # Build metadata dict
        metadata = {
            "run_id": run_id,
            "timestamp": timestamp,
            "duration_seconds": round(duration_seconds, 2),
            "energizados_version": energizados_version,
            "python_version": python_version,
            "git_commit": git_commit,
            "model_types": model_types,
            "val_auc": val_auc,
            "val_f1": val_f1,
            "feature_count": feature_count,
            "config_files": [Path(p).name for p in self.config_paths],
            "status": status,  # NEW
            "output_paths": output_paths,  # NEW
        }

        # Write to JSON file
        metadata_path = self._run_dir / "run_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Run metadata saved to: {metadata_path}")

    def finalize_run(self, context: Optional[Dict[str, Any]] = None):
        """
        Run post-build tasks.

        This should be called after a successful pipeline run:
        - Copy configs to run directory
        - Regenerate global index HTML
        - Write run metadata JSON if context is provided

        Args:
            context: Optional context dict containing training results (val metrics, model types, etc.)
        """
        if self._run_dir is not None:
            self.copy_configs_to_run_dir()
            self.generate_index_html()

            # Write run metadata if context is provided
            if context is not None:
                self._write_run_metadata(context)

    # ------------------------------------------------------------------
    # Query API methods (Phase 4)
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        """
        Get metadata for a specific run by ID.

        Args:
            run_id: Run directory name (e.g., "train-20240101_120000")

        Returns:
            RunMetadata if found, None otherwise (including invalid/path-traversal attempts)
        """
        # Reject None, empty, or invalid run_id (path traversal)
        if not run_id or not isinstance(run_id, str):
            return None

        # Path traversal protection
        if "/" in run_id or "\\" in run_id or ".." in run_id:
            return None

        # Use explicit output_dir if set, otherwise infer from run_dir or default
        if self._output_dir:
            base_dir = self._output_dir
        elif self._run_dir:
            base_dir = self._run_dir.parent
        else:
            base_dir = Path("output")

        run_dir = base_dir / run_id

        # Verify resolved path is within base_dir (defends against path traversal)
        try:
            resolved = run_dir.resolve()
            base_resolved = base_dir.resolve()
            # Check if resolved path is within base directory
            if not str(resolved).startswith(str(base_resolved)):
                return None
        except (OSError, RuntimeError):
            return None

        return self._read_metadata(run_dir)

    def list_runs(
        self, filter: Optional[Dict[str, Any]] = None, limit: int = 100
    ) -> List[RunMetadata]:
        """
        List runs across all types (train, eda, inference).

        Args:
            filter: Optional filter dict (e.g., {"status": "success"})
            limit: Maximum number of runs to return (default: 100)

        Returns:
            List of RunMetadata sorted by timestamp descending (most recent first)
        """
        # Use explicit output_dir if set, otherwise infer from run_dir or default
        if self._output_dir:
            base_dir = self._output_dir
        elif self._run_dir:
            base_dir = self._run_dir.parent
        else:
            base_dir = Path("output")

        if not base_dir.exists():
            return []

        runs = []
        # Match all run types: train-*, eda-*, inference-*, or custom names
        for run_dir in base_dir.glob("*-*"):
            # Skip directories that don't look like run dirs
            if not run_dir.is_dir():
                continue

            metadata = self._read_metadata(run_dir)
            if metadata and self._matches_filter(metadata, filter):
                runs.append(metadata)

        # Sort by timestamp descending (most recent first), then by run_id descending for stability
        runs.sort(key=lambda m: (m.timestamp, m.run_id), reverse=True)

        # Apply limit after sorting
        return runs[:limit]

    def get_latest_run(self) -> Optional[RunMetadata]:
        """
        Get the most recent run.

        Returns:
            RunMetadata if any runs exist, None otherwise
        """
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def _read_metadata(self, run_dir: Path) -> Optional[RunMetadata]:
        """
        Read run metadata with tolerant loader.

        Args:
            run_dir: Path to run directory

        Returns:
            RunMetadata if metadata file exists and loads successfully, None otherwise
        """
        metadata_file = run_dir / "run_metadata.json"
        if not metadata_file.exists():
            return None

        try:
            with open(metadata_file) as f:
                data = json.load(f)
            return RunMetadata.from_dict(data)  # Tolerant loader
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read metadata from {metadata_file}: {e}")
            return None

    def _matches_filter(self, metadata: RunMetadata, filter: Optional[Dict]) -> bool:
        """
        Check if metadata matches filter criteria.

        Args:
            metadata: RunMetadata to check
            filter: Optional filter dict

        Returns:
            True if no filter or if metadata matches all filter criteria
        """
        if not filter:
            return True

        if "status" in filter and metadata.status != filter["status"]:
            return False

        # Add date_range filter if needed in future

        return True
