"""
Run Manager.

This module handles run directory creation, config copying, and post-run tasks.
"""

import json
import logging
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    ):
        """
        Initialize run manager.

        Args:
            config_paths: List of config file paths used for this run
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
        """
        self.config_paths: List[str] = config_paths or []
        self._run_dir: Optional[Path] = None
        self._run_name: Optional[str] = run_name
        self._overwrite: bool = overwrite
        self._start_time = time.time()

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
