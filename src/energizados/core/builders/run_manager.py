"""
Run Manager.

This module handles run directory creation, config copying, and post-run tasks.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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

    def __init__(self, config_paths: Optional[List[str]] = None):
        """
        Initialize the run manager.

        Args:
            config_paths: List of config file paths used for this run
        """
        self.config_paths: List[str] = config_paths or []
        self._run_dir: Optional[Path] = None

    @property
    def run_dir(self) -> Optional[Path]:
        """Get the current run directory path."""
        return self._run_dir

    def generate_run_dir(self, base_output_dir: str = "output") -> Path:
        """
        Creates a timestamped run directory inside the output base directory.

        Args:
            base_output_dir: Base output directory (default: "output")

        Returns:
            Path: Path to the created run directory
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        run_name = f"train-{timestamp}"
        base = Path(base_output_dir)
        run_dir = base / run_name

        # Handle timestamp collisions atomically (avoid TOCTOU race)
        import os

        suffix = 0
        while True:
            candidate = run_dir if suffix == 0 else base / f"{run_name}_{suffix}"
            try:
                os.makedirs(candidate)
                run_dir = candidate
                break
            except FileExistsError:
                suffix += 1

        (run_dir / "models").mkdir(parents=True, exist_ok=True)
        (run_dir / "reports" / "evaluation").mkdir(parents=True, exist_ok=True)
        (run_dir / "config").mkdir(parents=True, exist_ok=True)

        logger.info(f"Training run directory: {run_dir}")
        self._run_dir = run_dir
        return run_dir

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

    def finalize_run(self):
        """
        Run post-build tasks.

        This should be called after a successful pipeline run:
        - Copy configs to run directory
        - Regenerate global index HTML
        """
        if self._run_dir is not None:
            self.copy_configs_to_run_dir()
            self.generate_index_html()
