"""
Split Step for Energizados Framework.

Divides the dataset into train/val/test reproducibly,
saving the splits for later use.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from energizados.core.base import PipelineStep

logger = logging.getLogger(__name__)


class SplitStep(PipelineStep):
    """
    Divide the dataset into train/val/test.

    Supports five split methods:
    - stratified: Maintains target proportion
    - random: Simple random split
    - time_series: Based on time periods
    - group_based: Groups rows by group_column, ensures no group leaks across splits
    - stratified_time: Time split within each cluster — guarantees temporal order
      per cluster while ensuring all clusters appear in train/val/test

    Args:
        input_path: Path to the full dataset
        target_column: Name of the target column
        test_size: Proportion for test (default: 0.2)
        val_size: Proportion for validation (default: 0.1)
        random_state: Random seed
        splits_dir: Directory to save the splits
        method: Split method ('stratified', 'random', 'time_series', 'group_based')
        group_column: Column to group by (for group_based method)
        date_column: Date column (for time_series)
        train_period: Training period [start, end]
        val_period: Validation period [start, end]
        test_period: Test period [start, end]

    Example:
        >>> split_step = SplitStep(
        ...     input_path="data/processed/dataset.parquet",
        ...     target_column="target",
        ...     splits_dir="data/splits/"
        ... )
        >>> result = split_step.run()
    """

    def __init__(
        self,
        input_path: str = "data/processed/sample_dataset.parquet",
        target_column: str = "target",
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42,
        splits_dir: str = "data/splits/",
        method: str = "stratified",
        group_column: Optional[str] = None,
        cluster_column: Optional[str] = None,
        date_column: Optional[str] = None,
        train_period: Optional[list] = None,
        val_period: Optional[list] = None,
        test_period: Optional[list] = None,
        save_splits: bool = True,
        **kwargs,
    ):
        self.input_path = input_path
        self.target_column = target_column
        self.test_size = test_size
        self.val_size = val_size
        self.random_state = random_state
        self.splits_dir = Path(splits_dir)
        self.method = method
        self.group_column = group_column
        self.cluster_column = cluster_column
        self.date_column = date_column
        self.train_period = train_period
        self.val_period = val_period
        self.test_period = test_period
        self.save_splits = save_splits

    def _validate_time_series_config(self) -> None:
        """Validate time_series-specific config. Raises ValueError if invalid."""
        if not self.date_column:
            raise ValueError(
                "SplitStep with method='time_series' requires 'date_column'. "
                "Add date_column to your split configuration."
            )

    def _validate_stratified_time_config(self, df: pd.DataFrame) -> None:
        """Validate stratified_time-specific config. Raises ValueError if invalid."""
        if not self.date_column:
            raise ValueError(
                "SplitStep with method='stratified_time' requires 'date_column'. "
                "Add date_column to your split configuration."
            )
        if not self.cluster_column:
            raise ValueError(
                "SplitStep with method='stratified_time' requires 'cluster_column'. "
                "Add cluster_column to your split configuration (e.g. 'geo_cluster')."
            )
        if self.cluster_column not in df.columns:
            raise ValueError(
                f"Cluster column '{self.cluster_column}' not found in dataset. "
                f"Run the geo_cluster global transformer first to generate this column."
            )

    def _validate_group_config(self, df: pd.DataFrame) -> None:
        """Validate group_based-specific config. Raises ValueError if invalid."""
        if self.group_column is None:
            raise ValueError(
                "SplitStep with method='group_based' requires 'group_column'. "
                "Add group_column to your split configuration."
            )
        if self.group_column not in df.columns:
            raise ValueError(
                f"Group column '{self.group_column}' not found in dataset columns. "
                f"Available columns: {list(df.columns)}"
            )

    def _check_class_imbalance(self, splits: Dict[str, pd.DataFrame], target_column: str) -> None:
        """Log WARNING if any split's positive rate <0.1 or >0.9."""
        for split_name, split_df in splits.items():
            if target_column in split_df.columns:
                positive_rate = (split_df[target_column] == 1).mean()
                if positive_rate < 0.1 or positive_rate > 0.9:
                    logger.warning(
                        f"Class imbalance detected in {split_name} split: "
                        f"{positive_rate * 100:.1f}% positive rate. "
                        f"Group-based splits cannot guarantee class balance."
                    )

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the split and save train/val/test datasets to disk.

        Loads the dataset from ``input_path`` (or the last ETL result in context),
        splits it using the configured method, and saves the resulting parquet files
        along with a JSON metadata file.

        Args:
            context: Pipeline context dict; used to resolve ``input_path`` when not
                set at construction time (falls back to ``etl_results``).

        Returns:
            Dict: Updated context with keys ``train_path``, ``val_path``,
                ``test_path``, and ``splits_dir``.

        Raises:
            ValueError: If the target column is missing or if ``time_series`` split
                is requested without a ``date_column``.
        """
        # Create directory
        self.splits_dir.mkdir(parents=True, exist_ok=True)

        # Determine input path from context if not provided
        input_path = self.input_path
        if not input_path and "etl_results" in context:
            # Use the last ETL result
            last_etl = list(context["etl_results"].keys())[-1]
            input_path = context["etl_results"][last_etl]

        # Validate path safety before reading
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(input_path, label="split input_path")

        # Load data
        df = pd.read_parquet(input_path)

        logger.info(f"Loading dataset from: {input_path}")
        logger.info(f"Dataset shape: {df.shape}")

        # Verify that target exists
        if self.target_column not in df.columns:
            raise ValueError(f"Target column '{self.target_column}' not found in dataset")

        # Split by time periods
        if self.method == "time_series":
            # Validate time_series configuration
            self._validate_time_series_config()

            # Convert date column to datetime if not already
            df[self.date_column] = pd.to_datetime(df[self.date_column])

            # Filter by periods
            train_mask = self._filter_by_period(df, self.train_period)
            val_mask = self._filter_by_period(df, self.val_period)
            test_mask = self._filter_by_period(df, self.test_period)

            train_df = df[train_mask].copy()
            val_df = df[val_mask].copy()
            test_df = df[test_mask].copy()

            # Check for overlapping periods
            for name_a, mask_a, name_b, mask_b in [
                ("train", train_mask, "val", val_mask),
                ("train", train_mask, "test", test_mask),
                ("val", val_mask, "test", test_mask),
            ]:
                overlap = (mask_a & mask_b).sum()
                if overlap > 0:
                    logger.warning(
                        "%s and %s periods overlap: %d rows in common", name_a, name_b, overlap
                    )

            # Check for empty splits
            for name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
                if len(split_df) == 0:
                    logger.warning(
                        "%s split is empty (0 rows). Check your %s_period configuration.",
                        name,
                        name,
                    )

        # Group-based split
        elif self.method == "group_based":
            # Validate group configuration
            self._validate_group_config(df)

            # Separate X, y, and groups
            y = df[self.target_column]
            X = df.drop(columns=[self.target_column])
            groups = df[self.group_column]

            # First split: all → train + temp (test_size = val_size + test_size)
            gss1 = GroupShuffleSplit(
                n_splits=1,
                test_size=(self.val_size + self.test_size),
                random_state=self.random_state,
            )
            train_idx, temp_idx = next(gss1.split(X, y, groups))

            # Second split: temp → val + test (test_size = test_size / (val+test))
            temp_test_size = self.test_size / (self.val_size + self.test_size)
            gss2 = GroupShuffleSplit(
                n_splits=1, test_size=temp_test_size, random_state=self.random_state
            )
            val_idx, test_idx = next(
                gss2.split(X.iloc[temp_idx], y.iloc[temp_idx], groups.iloc[temp_idx])
            )

            # Map temp indices back to original dataframe indices
            val_idx = temp_idx[val_idx]
            test_idx = temp_idx[test_idx]

            # Filter df rows by group membership
            train_df = df.iloc[train_idx].copy()
            val_df = df.iloc[val_idx].copy()
            test_df = df.iloc[test_idx].copy()

            # Check for group leaks
            train_groups = set(train_df[self.group_column])
            val_groups = set(val_df[self.group_column])
            test_groups = set(test_df[self.group_column])

            for name_a, groups_a, name_b, groups_b in [
                ("train", train_groups, "val", val_groups),
                ("train", train_groups, "test", test_groups),
                ("val", val_groups, "test", test_groups),
            ]:
                overlap = groups_a & groups_b
                if overlap:
                    logger.warning(
                        "Group leak detected: %d groups shared between %s and %s splits: %s",
                        len(overlap),
                        name_a,
                        name_b,
                        list(overlap)[:10],  # Show first 10
                    )

            # Check for class imbalance
            self._check_class_imbalance(
                {"train": train_df, "val": val_df, "test": test_df}, self.target_column
            )

        # Stratified time split: temporal split within each cluster
        elif self.method == "stratified_time":
            self._validate_stratified_time_config(df)
            df[self.date_column] = pd.to_datetime(df[self.date_column])
            train_parts, val_parts, test_parts = [], [], []

            for cluster_id, group in df.groupby(self.cluster_column):
                group = group.sort_values(self.date_column)
                n = len(group)
                n_test = max(1, int(n * self.test_size))
                n_val = max(1, int(n * self.val_size))

                if n < 10:
                    logger.warning(
                        "Cluster '%s' has only %d rows — val/test splits will be very small.",
                        cluster_id,
                        n,
                    )

                train_parts.append(group.iloc[: n - n_val - n_test])
                val_parts.append(group.iloc[n - n_val - n_test : n - n_test])
                test_parts.append(group.iloc[n - n_test :])

            train_df = pd.concat(train_parts).reset_index(drop=True)
            val_df = pd.concat(val_parts).reset_index(drop=True)
            test_df = pd.concat(test_parts).reset_index(drop=True)

        # Random/stratified split
        else:
            # Separate X and y
            y = df[self.target_column]
            X = df.drop(columns=[self.target_column])

            # Split: train + test
            if self.method == "stratified":
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=self.test_size, random_state=self.random_state, stratify=y
                )
            else:  # random
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=self.test_size, random_state=self.random_state
                )

            # Split: train → train + val
            val_size_adjusted = self.val_size / (1 - self.test_size)

            if self.method == "stratified":
                X_train, X_val, y_train, y_val = train_test_split(
                    X_train,
                    y_train,
                    test_size=val_size_adjusted,
                    random_state=self.random_state,
                    stratify=y_train,
                )
            else:  # random
                X_train, X_val, y_train, y_val = train_test_split(
                    X_train, y_train, test_size=val_size_adjusted, random_state=self.random_state
                )

            # Reconstruct DataFrames with target
            train_df = X_train.copy()
            train_df[self.target_column] = y_train.values

            val_df = X_val.copy()
            val_df[self.target_column] = y_val.values

            test_df = X_test.copy()
            test_df[self.target_column] = y_test.values

        # Save splits
        train_path = self.splits_dir / "train.parquet"
        val_path = self.splits_dir / "val.parquet"
        test_path = self.splits_dir / "test.parquet"

        if self.save_splits:
            train_df.to_parquet(train_path, index=False)
            val_df.to_parquet(val_path, index=False)
            test_df.to_parquet(test_path, index=False)

        # Save split metadata
        metadata = {
            "method": self.method,
            "n_samples": len(df),
            "n_train": len(train_df),
            "n_val": len(val_df),
            "n_test": len(test_df),
            "target_column": self.target_column,
        }

        if self.method == "time_series":
            metadata["date_column"] = self.date_column
            metadata["train_dates"] = self._get_date_range(train_df, self.date_column)
            metadata["val_dates"] = self._get_date_range(val_df, self.date_column)
            metadata["test_dates"] = self._get_date_range(test_df, self.date_column)
        elif self.method == "stratified_time":
            metadata["date_column"] = self.date_column
            metadata["cluster_column"] = self.cluster_column
            metadata["n_clusters"] = int(df[self.cluster_column].nunique())
            metadata["test_size"] = self.test_size
            metadata["val_size"] = self.val_size
        elif self.method == "group_based":
            metadata["group_column"] = self.group_column
            metadata["n_groups_total"] = df[self.group_column].nunique()
            metadata["n_groups_train"] = train_df[self.group_column].nunique()
            metadata["n_groups_val"] = val_df[self.group_column].nunique()
            metadata["n_groups_test"] = test_df[self.group_column].nunique()
            metadata["test_size"] = self.test_size
            metadata["val_size"] = self.val_size
            metadata["random_state"] = self.random_state
        else:
            metadata["test_size"] = self.test_size
            metadata["val_size"] = self.val_size
            metadata["random_state"] = self.random_state

        metadata["target_distribution"] = {
            "train": train_df[self.target_column].value_counts().to_dict(),
            "val": val_df[self.target_column].value_counts().to_dict(),
            "test": test_df[self.target_column].value_counts().to_dict(),
        }

        if self.save_splits:
            with open(self.splits_dir / "split_metadata.json", "w") as f:
                json.dump(metadata, f, indent=2, default=str)

        logger.info(f"\n{'=' * 50}")
        logger.info(f"DATA SPLIT ({self.method.upper()})")
        logger.info(f"{'=' * 50}")
        logger.info(f"Total:     {len(df):>6} samples")
        logger.info(f"Train:     {len(train_df):>6} samples ({len(train_df) / len(df) * 100:.1f}%)")
        logger.info(f"Val:       {len(val_df):>6} samples ({len(val_df) / len(df) * 100:.1f}%)")
        logger.info(f"Test:      {len(test_df):>6} samples ({len(test_df) / len(df) * 100:.1f}%)")

        # Show target distribution
        logger.info("\nTarget distribution:")
        for split_name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
            dist = split_df[self.target_column].value_counts()
            total = len(split_df)
            logger.info(f"{split_name}:")
            for label, count in dist.items():
                pct = count / total * 100
                logger.info(f"  {label}: {count:>6} ({pct:.1f}%)")

        if self.method == "time_series":
            logger.info("\nDate ranges:")
            logger.info(f"Train: {metadata['train_dates']}")
            logger.info(f"Val:   {metadata['val_dates']}")
            logger.info(f"Test:  {metadata['test_dates']}")

        if self.method == "group_based":
            logger.info(f"\nGroup distribution (by {self.group_column}):")
            logger.info(f"Total groups: {metadata['n_groups_total']}")
            logger.info(
                f"Train groups: {metadata['n_groups_train']} ({metadata['n_groups_train'] / metadata['n_groups_total'] * 100:.1f}%)"
            )
            logger.info(
                f"Val groups:   {metadata['n_groups_val']} ({metadata['n_groups_val'] / metadata['n_groups_total'] * 100:.1f}%)"
            )
            logger.info(
                f"Test groups:  {metadata['n_groups_test']} ({metadata['n_groups_test'] / metadata['n_groups_total'] * 100:.1f}%)"
            )

        logger.info(f"{'=' * 50}")
        if self.save_splits:
            logger.info(f"Splits saved to: {self.splits_dir}")

        # Return context with paths to splits
        return {
            **context,
            "train_path": str(train_path),
            "val_path": str(val_path),
            "test_path": str(test_path),
            "splits_dir": str(self.splits_dir),
        }

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate that the input dataset file exists.

        Args:
            context: Pipeline context dict.

        Returns:
            bool: True if ``input_path`` exists on disk or ``etl_results`` is
                present in context.

        Raises:
            StepValidationError: If ``input_path`` is set but the file does not exist.
        """
        if self.input_path:
            if not Path(self.input_path).exists():
                from energizados.core.exceptions import StepValidationError

                raise StepValidationError(
                    f"Input dataset not found: '{self.input_path}'\n\n"
                    "Run the ETL pipeline first to generate the dataset:\n\n"
                    "  energizados run etl",
                    step="SplitStep",
                )
            return True
        return "etl_results" in context

    def get_required_keys(self) -> list:
        """Return the required context keys.

        Returns:
            List[str]: ``["etl_results"]`` when no ``input_path`` is set;
                empty list otherwise.
        """
        if self.input_path:
            return []
        return ["etl_results"]

    def get_output_keys(self) -> list:
        """Return the context keys produced by this step.

        Returns:
            List[str]: Keys added to the pipeline context after splitting.
        """
        return ["train_path", "val_path", "test_path", "splits_dir"]

    def _filter_by_period(self, df: pd.DataFrame, period: Optional[list]) -> pd.Series:
        """Filter DataFrame by date period."""
        if period is None:
            return pd.Series([False] * len(df))

        start = pd.to_datetime(period[0])
        end = pd.to_datetime(period[1]) if len(period) > 1 else None

        mask = df[self.date_column] >= start
        if end is not None:
            mask = mask & (df[self.date_column] <= end)

        return mask

    def _get_date_range(self, df: pd.DataFrame, date_col: str) -> Optional[dict]:
        """Return the date range of a DataFrame."""
        if date_col not in df.columns:
            return None
        return {
            "min": str(df[date_col].min()),
            "max": str(df[date_col].max()),
        }
