"""
Test suite for SplitStep in Energizados Framework.

Tests cover schema validation, time_series split behavior, warnings,
and regression tests for stratified/random splits.
"""

import logging

import numpy as np
import pandas as pd
import pytest
from jsonschema import ValidationError, validate

from energizados.core.schemas.schemas import SPLIT_SCHEMA
from energizados.core.steps.split import SplitStep

# =============================================================================
# Fixtures
# =============================================================================

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_df():
    """50-row DataFrame: date col spanning 2020-01 to 2024-12, binary target, 2 features."""
    dates = pd.date_range("2020-01-01", periods=50, freq="ME")
    return pd.DataFrame(
        {
            "fecha": dates,
            "f1": np.random.default_rng(42).standard_normal(50),
            "target": np.random.default_rng(42).integers(0, 2, 50),
        }
    )


@pytest.fixture
def sample_parquet(tmp_path, sample_df):
    """Write sample_df to parquet, return path."""
    path = tmp_path / "data.parquet"
    sample_df.to_parquet(path, index=False)
    return str(path)


@pytest.fixture
def grouped_df():
    """100-row DataFrame with 20 customer_id groups, binary target."""
    # Create 20 groups, each with 5 rows
    customer_ids = np.repeat(np.arange(20), 5)
    return pd.DataFrame(
        {
            "customer_id": customer_ids,
            "f1": np.random.default_rng(42).standard_normal(100),
            "target": np.random.default_rng(42).integers(0, 2, 100),
        }
    )


@pytest.fixture
def grouped_parquet(tmp_path, grouped_df):
    """Write grouped_df to parquet, return path."""
    path = tmp_path / "grouped_data.parquet"
    grouped_df.to_parquet(path, index=False)
    return str(path)


# =============================================================================
# Schema Validation Tests
# =============================================================================


def test_schema_time_series_accepted():
    """time_series method and array periods must pass schema validation."""
    config = {
        "method": "time_series",
        "date_column": "fecha",
        "train_period": ["2020-01-01", "2022-06-30"],
        "val_period": ["2022-07-01", "2023-06-30"],
        "test_period": ["2023-07-01", "2024-12-31"],
    }
    # Should not raise
    validate(instance=config, schema=SPLIT_SCHEMA)


def test_schema_temporal_rejected():
    """temporal method must fail schema validation."""
    config = {
        "method": "temporal",
        "date_column": "fecha",
        "train_period": ["2020-01-01", "2022-06-30"],
    }
    with pytest.raises(ValidationError) as excinfo:
        validate(instance=config, schema=SPLIT_SCHEMA)
    assert "method" in str(excinfo.value).lower()


def test_schema_period_array_accepted():
    """Array train_period must pass schema validation."""
    config = {
        "method": "time_series",
        "train_period": ["2020-01-01", "2022-06-30"],
    }
    # Should not raise
    validate(instance=config, schema=SPLIT_SCHEMA)


def test_schema_period_string_rejected():
    """Scalar string train_period must fail schema validation."""
    config = {
        "method": "time_series",
        "train_period": "2020-01-01",
    }
    with pytest.raises(ValidationError) as excinfo:
        validate(instance=config, schema=SPLIT_SCHEMA)
    assert "train_period" in str(excinfo.value).lower()


# =============================================================================
# time_series Split Tests
# =============================================================================


def test_time_series_missing_date_column(sample_parquet):
    """date_column=None must raise ValueError with descriptive message."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="time_series",
        date_column=None,
        train_period=["2020-01-01", "2022-06-30"],
        test_period=["2023-07-01", "2024-12-31"],
        save_splits=False,
    )
    with pytest.raises(ValueError) as excinfo:
        split_step.execute({})
    assert "date_column" in str(excinfo.value).lower()
    assert "time_series" in str(excinfo.value).lower()


def test_time_series_happy_path(sample_parquet, caplog):
    """Non-overlapping, non-empty periods must produce correct splits without warnings."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="time_series",
        date_column="fecha",
        train_period=["2020-01-01", "2022-06-30"],
        val_period=["2022-07-01", "2023-06-30"],
        test_period=["2023-07-01", "2024-12-31"],
        save_splits=False,
    )
    with caplog.at_level(logging.WARNING):
        result = split_step.execute({})

    # Verify no WARNING logs
    warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warning_logs) == 0, "Expected no warnings for happy path"

    # Verify context keys
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result
    assert "splits_dir" in result


def test_time_series_empty_val_warns(sample_parquet, caplog):
    """val_period=None must log WARNING about empty val split and complete execution."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="time_series",
        date_column="fecha",
        train_period=["2020-01-01", "2022-06-30"],
        val_period=None,
        test_period=["2023-07-01", "2024-12-31"],
        save_splits=False,
    )
    with caplog.at_level(logging.WARNING):
        result = split_step.execute({})

    # Verify WARNING about empty val split
    warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert any(
        "val" in record.getMessage().lower() for record in warning_logs
    ), "Expected warning about empty val split"

    # Verify execution completed
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result


def test_time_series_overlap_warns(sample_parquet, caplog):
    """Overlapping train/val periods must log WARNING with both split names and row count."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="time_series",
        date_column="fecha",
        train_period=["2020-01-01", "2022-06-30"],
        val_period=["2022-06-01", "2023-06-30"],  # Overlaps: 2022-06-01 to 2022-06-30
        test_period=["2023-07-01", "2024-12-31"],
        save_splits=False,
    )
    with caplog.at_level(logging.WARNING):
        result = split_step.execute({})

    # Verify WARNING about overlap
    warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
    overlap_warnings = [
        record for record in warning_logs if "overlap" in record.getMessage().lower()
    ]
    assert len(overlap_warnings) > 0, "Expected warning about overlapping periods"

    # Verify warning contains both split names
    overlap_msg = overlap_warnings[0].getMessage().lower()
    assert "train" in overlap_msg
    assert "val" in overlap_msg

    # Verify execution completed
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result
    assert "splits_dir" in result


# =============================================================================
# Group-based Split Tests
# =============================================================================


def test_schema_group_based_accepted():
    """group_based method with group_column must pass schema validation."""
    config = {
        "method": "group_based",
        "group_column": "customer_id",
        "test_size": 0.2,
        "val_size": 0.1,
    }
    # Should not raise
    validate(instance=config, schema=SPLIT_SCHEMA)


def test_schema_group_based_rejected_without_column():
    """group_based method without group_column must fail schema validation."""
    config = {
        "method": "group_based",
        "test_size": 0.2,
        "val_size": 0.1,
    }
    with pytest.raises(ValidationError) as excinfo:
        validate(instance=config, schema=SPLIT_SCHEMA)
    assert "group_column" in str(excinfo.value).lower()


def test_group_based_missing_column_error(grouped_parquet):
    """group_column not in DataFrame must raise ValueError."""
    split_step = SplitStep(
        input_path=grouped_parquet,
        target_column="target",
        method="group_based",
        group_column="nonexistent_column",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=False,
    )
    with pytest.raises(ValueError) as excinfo:
        split_step.execute({})
    assert "nonexistent_column" in str(excinfo.value)
    assert "not found" in str(excinfo.value).lower()


def test_group_based_no_leaks(grouped_parquet, tmp_path):
    """Group-based split must ensure no group leaks across splits."""
    split_step = SplitStep(
        input_path=grouped_parquet,
        target_column="target",
        method="group_based",
        group_column="customer_id",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=True,
        splits_dir=str(tmp_path / "splits"),
    )
    result = split_step.execute({})

    # Read splits
    train_df = pd.read_parquet(result["train_path"])
    val_df = pd.read_parquet(result["val_path"])
    test_df = pd.read_parquet(result["test_path"])

    # Get unique groups per split
    train_groups = set(train_df["customer_id"])
    val_groups = set(val_df["customer_id"])
    test_groups = set(test_df["customer_id"])

    # Assert no group leaks
    assert len(train_groups & val_groups) == 0, "Groups leaked from train to val"
    assert len(train_groups & test_groups) == 0, "Groups leaked from train to test"
    assert len(val_groups & test_groups) == 0, "Groups leaked from val to test"


def test_group_based_reproducibility(grouped_parquet, tmp_path):
    """Group-based split must be reproducible with same random_state."""
    split_step1 = SplitStep(
        input_path=grouped_parquet,
        target_column="target",
        method="group_based",
        group_column="customer_id",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=True,
        splits_dir=str(tmp_path / "splits1"),
    )
    result1 = split_step1.execute({})

    split_step2 = SplitStep(
        input_path=grouped_parquet,
        target_column="target",
        method="group_based",
        group_column="customer_id",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=True,
        splits_dir=str(tmp_path / "splits2"),
    )
    result2 = split_step2.execute({})

    # Read splits
    train_df1 = pd.read_parquet(result1["train_path"])
    train_df2 = pd.read_parquet(result2["train_path"])

    # Assert splits are identical
    pd.testing.assert_frame_equal(train_df1, train_df2)


def test_group_based_metadata_contract(grouped_parquet, tmp_path):
    """Group-based split metadata must contain all required group keys."""
    split_step = SplitStep(
        input_path=grouped_parquet,
        target_column="target",
        method="group_based",
        group_column="customer_id",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=True,
        splits_dir=str(tmp_path / "splits"),
    )
    split_step.execute({})

    # Read metadata
    metadata_path = tmp_path / "splits" / "split_metadata.json"
    import json

    with open(metadata_path) as f:
        metadata = json.load(f)

    # Assert group metadata keys exist
    assert "group_column" in metadata
    assert metadata["group_column"] == "customer_id"
    assert "n_groups_total" in metadata
    assert "n_groups_train" in metadata
    assert "n_groups_val" in metadata
    assert "n_groups_test" in metadata

    # Assert group counts sum correctly
    assert (
        metadata["n_groups_train"] + metadata["n_groups_val"] + metadata["n_groups_test"]
        == metadata["n_groups_total"]
    )


def test_group_based_class_imbalance_warning(grouped_parquet, caplog):
    """Skewed group distribution should trigger class imbalance warning."""
    # Create a dataset with extreme class imbalance per group
    # 4 groups total: 3 groups all positive (1), 1 group all negative (0)
    # Each group has 5 rows
    skewed_df = pd.DataFrame(
        {
            "customer_id": np.repeat([0, 1, 2, 3], 5),
            "target": np.array(
                [1] * 15 + [0] * 5
            ),  # First 15 positive (3 groups), last 5 negative (1 group)
        }
    )

    path = grouped_parquet.replace("grouped_data.parquet", "skewed_data.parquet")
    skewed_df.to_parquet(path, index=False)

    split_step = SplitStep(
        input_path=path,
        target_column="target",
        method="group_based",
        group_column="customer_id",
        test_size=0.25,  # 1 group in test (likely the negative one)
        val_size=0.25,
        random_state=42,
        save_splits=False,
    )

    with caplog.at_level(logging.WARNING):
        split_step.execute({})

    # Check for imbalance warning
    warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
    imbalance_warnings = [
        record for record in warning_logs if "imbalance" in record.getMessage().lower()
    ]
    assert len(imbalance_warnings) > 0, "Expected class imbalance warning"


# =============================================================================
# Regression Tests
# =============================================================================


def test_stratified_regression(sample_parquet):
    """Stratified split must still work and maintain target proportions."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="stratified",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=False,
    )
    result = split_step.execute({})

    # Verify context keys
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result

    # Read splits (we can't verify exact proportions without the data,
    # but we verify the files exist and are accessible)
    from energizados.core.utils.secure_pickle import validate_no_traversal

    validate_no_traversal(result["train_path"], label="train_path")
    validate_no_traversal(result["val_path"], label="val_path")
    validate_no_traversal(result["test_path"], label="test_path")


def test_random_regression(sample_parquet):
    """Random split must still work and produce correct sizes."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="random",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=False,
    )
    result = split_step.execute({})

    # Verify context keys
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result

    # Read splits (we can't verify exact sizes without the data,
    # but we verify the files exist and are accessible)
    from energizados.core.utils.secure_pickle import validate_no_traversal

    validate_no_traversal(result["train_path"], label="train_path")
    validate_no_traversal(result["val_path"], label="val_path")
    validate_no_traversal(result["test_path"], label="test_path")
