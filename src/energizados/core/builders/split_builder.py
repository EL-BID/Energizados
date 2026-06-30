"""
Split Step Builder.

This module constructs data splitting pipeline steps from configuration.
"""

from typing import Any, Dict, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.core.steps.split import SplitStep


class SplitBuilder(StepBuilder):
    """
    Builder for Split pipeline steps.

    Constructs a step that divides data into train/val/test sets
    based on the 'split' section of the training configuration.
    """

    def __init__(self, config: Dict[str, Any], global_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the builder with configuration.

        Args:
            config: The split configuration (from training.split or split key)
            global_config: The full configuration dict (needed for fallback logic)
        """
        super().__init__(config)
        self.global_config = global_config or {}

    def build(self) -> Optional[PipelineStep]:
        """
        Build the Split step from configuration.

        Returns:
            PipelineStep: The split step, or None if not configured
        """
        split_config = self.config

        if not split_config:
            return None

        # Determine input_path
        input_path = split_config.get("input_path")
        if not input_path:
            # Also look at training level (global)
            input_path = self.global_config.get("train", {}).get("input_path")
        if not input_path and "etl" in self.global_config:
            # Use the last ETL to EXECUTE (topological order) as the training
            # input source. Previously this used dict insertion order, which is
            # only correct when YAML happens to list ETLs in execution order.
            from energizados._version import SCHEMA_VERSION_KEY

            etl_configs = self.global_config.get("etl", {})
            etl_names = [k for k in etl_configs if k != SCHEMA_VERSION_KEY]
            last_etl = None
            if etl_names:
                try:
                    from energizados.etl.orchestrator import ETLOrchestrator

                    order = ETLOrchestrator(etl_configs).build_execution_order()
                    if order:
                        # Filter out ETLs with no output field (e.g. CleanFilesETL)
                        # These are side-effect ETLs that don't produce training data
                        etls_with_output = [
                            name for name in order if etl_configs.get(name, {}).get("output")
                        ]
                        last_etl = etls_with_output[-1] if etls_with_output else etl_names[-1]
                except Exception:
                    # Fall back to insertion order if the DAG cannot be resolved
                    # (e.g. cycle or missing dependency).
                    last_etl = etl_names[-1]
            if last_etl:
                # input_path will be @etl_name
                input_path = f"@{last_etl}"

        # Determine target_column - check multiple locations
        target_column = (
            split_config.get("target_column")
            or self.global_config.get("train", {}).get("target_column")
            or "target"
        )

        return SplitStep(
            input_path=input_path,
            target_column=target_column,
            test_size=split_config.get("test_size", 0.2),
            val_size=split_config.get("val_size", 0.1),
            random_state=split_config.get("random_state", 42),
            splits_dir=split_config.get("splits_dir", "data/temp/splits/"),
            method=split_config.get("method", "stratified"),
            group_column=split_config.get("group_column"),
            date_column=split_config.get("date_column"),
            train_period=split_config.get("train_period"),
            val_period=split_config.get("val_period"),
            test_period=split_config.get("test_period"),
            save_splits=split_config.get("save_splits", True),
            geo_stratify=split_config.get("geo_stratify"),
            unlabeled_negatives=split_config.get("unlabeled_negatives"),
        )

    def is_enabled(self) -> bool:
        """Check if Split step is enabled.

        Returns:
            bool: True if split config exists
        """
        return bool(self.config)
