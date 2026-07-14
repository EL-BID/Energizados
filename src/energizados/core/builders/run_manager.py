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

from energizados.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def _validate_run_name(base: Path, run_name: Optional[str]) -> None:
    """Reject run_name values that escape base_output_dir.

    generate_run_dir() does shutil.rmtree() on the resolved run directory.
    If run_name is attacker-controlled (e.g. the web console), an absolute
    path or one containing traversal components would let it delete
    directories outside the output base. This guard refuses such names
    before any filesystem mutation happens.

    Args:
        base: Resolved base output directory.
        run_name: User-supplied run name. ``None`` is always allowed.

    Raises:
        ConfigurationError: If run_name is absolute or resolves outside base.
    """
    if run_name is None:
        return

    name = Path(run_name)
    if name.is_absolute():
        raise ConfigurationError(
            f"run_name must be a relative path inside the output dir, "
            f"got absolute path: {run_name!r}"
        )

    base_resolved = base.resolve()
    target = (base / name).resolve()
    try:
        target.relative_to(base_resolved)
    except ValueError:
        raise ConfigurationError(f"run_name must not escape the output directory: {run_name!r}")


@dataclass
class RunMetadata:
    """Metadata for a single run (stored in run_metadata.json).

    ADR-0001 — Runs are generalized and typed. ``run_type`` discriminates the
    kind of Run (``training``/``etl``/``eda``/``inference``) and controls which
    fields serialize: training-specific metrics (``val_auc``/``val_f1``/
    ``model_types``/``feature_count``) are omitted from ``to_dict`` for
    non-training runs. ``derived_from`` optionally records the source run_id of
    a retrain (ADR-0003 lineage).
    """

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
    # ADR-0001: type discriminator (training/etl/eda/inference). Old metadata
    # without this key loads as "training" (see from_dict).
    run_type: str = "training"
    # ADR-0003: run_id this Run was derived from (retrain lineage). None for
    # non-derived runs; omitted from serialization when None.
    derived_from: Optional[str] = None

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
            run_type=data.get("run_type", "training"),  # ADR-0001
            derived_from=data.get("derived_from"),  # ADR-0003
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable dict representation.

        Type-aware (ADR-0001): training-specific metrics are dropped for
        non-training runs so AUC/F1 no longer appear on every Run. ``derived_from``
        is omitted entirely when None to keep the payload clean.
        """
        data = asdict(self)
        if self.run_type != "training":
            for key in ("val_auc", "val_f1", "model_types", "feature_count"):
                data.pop(key, None)
        if self.derived_from is None:
            data.pop("derived_from", None)
        return data


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
        run_type: str = "training",
        derived_from: Optional[str] = None,
    ):
        """
        Initialize run manager.

        Args:
            config_paths: List of config file paths used for this run
            run_name: Optional custom run directory name
            overwrite: If True, overwrite existing run directory
            output_dir: Optional output directory path for query API (default: "output")
            run_type: ADR-0001 run-type discriminator (training/etl/eda/inference).
                Controls the run-dir prefix and which metadata fields serialize.
            derived_from: ADR-0003 source run_id for retrain lineage (None unless
                this Run was derived from another).
        """
        self.config_paths: List[str] = config_paths or []
        self._run_dir: Optional[Path] = None
        self._run_name: Optional[str] = run_name
        self._overwrite: bool = overwrite
        self._start_time = time.time()
        self._output_dir: Optional[Path] = Path(output_dir) if output_dir else None
        # ADR-0001 / ADR-0003
        self._run_type: str = run_type
        self._derived_from: Optional[str] = derived_from

    def set_derived_from(self, value: Optional[str]) -> None:
        """Set the derived_from lineage link (ADR-0003).

        Allows the director (or retrain flow) to set the source run_id after
        construction but before metadata finalization.
        """
        self._derived_from = value

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
            # Guard against path traversal / absolute paths before any
            # shutil.rmtree runs — run_name may be user-controlled (web console).
            _validate_run_name(base, run_name)
            # Use custom run name - delete existing directory if present
            run_dir = base / run_name
            if run_dir.exists():
                logger.info(f"Deleting existing run directory: {run_dir}")
                shutil.rmtree(run_dir)
            run_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use timestamp with collision handling.
            # ADR-0001: prefix by run_type — training keeps the config-derived
            # name (e.g. "train") for backward compat; other types use the
            # fixed run_type prefix so list_runs (*-*) auto-discovers them.
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            if self._run_type == "training":
                prefix = self._get_train_config_name() or "train"
            else:
                prefix = self._run_type
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

        # ADR-0001: training runs use models/ + reports/evaluation/ subdirs.
        # EDA/inference/ETL write their artifacts at the run-dir root, so those
        # subdirs are omitted (keeps failed-run cleanup honest — empty dirs no
        # longer make a non-training run look like it produced partial output).
        # config/ is always created so copy_configs_to_run_dir works for all types.
        if self._run_type == "training":
            (run_dir / "models").mkdir(parents=True, exist_ok=True)
            (run_dir / "reports" / "evaluation").mkdir(parents=True, exist_ok=True)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)

        logger.info(f"Run directory ({self._run_type}): {run_dir}")
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

        Type-aware (ADR-0001): training-specific fields (model_types, val_auc,
        val_f1, feature_count) are only populated for ``run_type == "training"``.
        Non-training runs populate ``output_paths`` from the relevant context
        keys (EDA report, inference predictions, ETL dataset paths).

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

        # Determine status (NEW for Phase 4)
        status = "success"
        if context.get("error"):
            status = "failed"
        elif context.get("comparison_mode"):
            status = "partial"  # Or determine based on step results

        # --- Build output_paths (training artifacts + generic typed outputs) ---
        output_paths: Dict[str, str] = {}
        if "model_path" in context and context["model_path"] is not None:
            output_paths["model"] = context["model_path"]
        if (
            "feature_engineering_path" in context
            and context["feature_engineering_path"] is not None
        ):
            output_paths["feature_engineering"] = context["feature_engineering_path"]

        # EDA report path (supported both as eda_results.report_path and the
        # explicit eda_report_path context key — ADR-0001).
        eda_results = context.get("eda_results")
        if isinstance(eda_results, dict) and eda_results.get("report_path"):
            output_paths["eda_report"] = eda_results["report_path"]
        if context.get("eda_report_path"):
            output_paths["eda_report"] = context["eda_report_path"]

        # Inference predictions path (ADR-0001).
        if context.get("inference_output_path"):
            output_paths["inference_predictions"] = context["inference_output_path"]

        # ETL dataset output paths (ADR-0001). Dataset stays at its configured
        # path; metadata references it.
        etl_output_paths = context.get("etl_output_paths")
        if isinstance(etl_output_paths, dict):
            for name, path in etl_output_paths.items():
                output_paths[f"etl_{name}"] = str(path)

        # Build metadata dict. Training-specific fields are only populated for
        # training runs (ADR-0001).
        metadata: Dict[str, Any] = {
            "run_id": run_id,
            "timestamp": timestamp,
            "duration_seconds": round(duration_seconds, 2),
            "energizados_version": energizados_version,
            "python_version": python_version,
            "git_commit": git_commit,
            "config_files": [Path(p).name for p in self.config_paths],
            "status": status,
            "output_paths": output_paths,
            "run_type": self._run_type,
        }
        if self._derived_from is not None:
            metadata["derived_from"] = self._derived_from

        if self._run_type == "training":
            # Extract model types from context
            model_types: List[str] = []
            if "model" in context and context["model"] is not None:
                model_types.append(type(context["model"]).__name__)
            elif "models" in context and context["models"] is not None:
                model_types = [type(m).__name__ for m in context["models"].values()]

            # Get feature count from context
            feature_count = None
            if "feature_engineering" in context and context["feature_engineering"] is not None:
                fe = context["feature_engineering"]
                if hasattr(fe, "selected_features_") and fe.selected_features_ is not None:
                    feature_count = len(fe.selected_features_)

            metadata["model_types"] = model_types
            metadata["val_auc"] = context.get("val_auc")
            metadata["val_f1"] = context.get("val_f1")
            metadata["feature_count"] = feature_count

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
