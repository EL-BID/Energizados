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
from sklearn.model_selection import train_test_split

from energizados.core.base import PipelineStep

logger = logging.getLogger(__name__)


class SplitStep(PipelineStep):
    """
    Divide the dataset into train/val/test.

    Supports three split methods:
    - stratified: Maintains target proportion
    - random: Simple random split
    - time_series: Based on time periods

    Args:
        input_path: Path to the full dataset
        target_column: Name of the target column
        test_size: Proportion for test (default: 0.2)
        val_size: Proportion for validation (default: 0.1)
        random_state: Random seed
        splits_dir: Directory to save the splits
        method: Split method ('stratified', 'random', 'time_series')
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
        date_column: Optional[str] = None,
        train_period: Optional[list] = None,
        val_period: Optional[list] = None,
        test_period: Optional[list] = None,
        **kwargs,
    ):
        self.input_path = input_path
        self.target_column = target_column
        self.test_size = test_size
        self.val_size = val_size
        self.random_state = random_state
        self.splits_dir = Path(splits_dir)
        self.method = method
        self.date_column = date_column
        self.train_period = train_period
        self.val_period = val_period
        self.test_period = test_period

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the split and save the datasets."""
        # Create directory
        self.splits_dir.mkdir(parents=True, exist_ok=True)

        # Determine input path from context if not provided
        input_path = self.input_path
        if not input_path and "etl_results" in context:
            # Use the last ETL result
            last_etl = list(context["etl_results"].keys())[-1]
            input_path = context["etl_results"][last_etl]

        # Load data
        df = pd.read_parquet(input_path)

        logger.info(f"Loading dataset from: {input_path}")
        logger.info(f"Dataset shape: {df.shape}")

        # Verify that target exists
        if self.target_column not in df.columns:
            raise ValueError(f"Target column '{self.target_column}' not found in dataset")

        # Split by time periods
        if self.method == "time_series":
            if not self.date_column:
                raise ValueError("For method='time_series' must specify date_column")

            # Convert date column to datetime if not already
            df[self.date_column] = pd.to_datetime(df[self.date_column])

            # Filter by periods
            train_mask = self._filter_by_period(df, self.train_period)
            val_mask = self._filter_by_period(df, self.val_period)
            test_mask = self._filter_by_period(df, self.test_period)

            train_df = df[train_mask].copy()
            val_df = df[val_mask].copy()
            test_df = df[test_mask].copy()

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
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=self.test_size, random_state=self.random_state)

            # Split: train → train + val
            val_size_adjusted = self.val_size / (1 - self.test_size)

            if self.method == "stratified":
                X_train, X_val, y_train, y_val = train_test_split(
                    X_train, y_train, test_size=val_size_adjusted, random_state=self.random_state, stratify=y_train
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
        else:
            metadata["test_size"] = self.test_size
            metadata["val_size"] = self.val_size
            metadata["random_state"] = self.random_state

        metadata["target_distribution"] = {
            "train": train_df[self.target_column].value_counts().to_dict(),
            "val": val_df[self.target_column].value_counts().to_dict(),
            "test": test_df[self.target_column].value_counts().to_dict(),
        }

        with open(self.splits_dir / "split_metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(f"\n{'='*50}")
        logger.info(f"DATA SPLIT ({self.method.upper()})")
        logger.info(f"{'='*50}")
        logger.info(f"Total:     {len(df):>6} samples")
        logger.info(f"Train:     {len(train_df):>6} samples ({len(train_df)/len(df)*100:.1f}%)")
        logger.info(f"Val:       {len(val_df):>6} samples ({len(val_df)/len(df)*100:.1f}%)")
        logger.info(f"Test:      {len(test_df):>6} samples ({len(test_df)/len(df)*100:.1f}%)")

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

        logger.info(f"{'='*50}")
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
        """Validate that the input exists."""
        if self.input_path:
            return Path(self.input_path).exists()
        return "etl_results" in context

    def get_required_keys(self) -> list:
        """Return the required context keys."""
        if self.input_path:
            return []
        return ["etl_results"]

    def get_output_keys(self) -> list:
        """Return the keys added to the context."""
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
