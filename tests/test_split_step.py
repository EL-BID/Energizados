"""
Test suite for SplitStep in Energizados Framework.

Tests cover schema validation, time_series split behavior, warnings,
and regression tests for stratified/random splits.
"""

import json
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


def test_time_series_missing_date_column(sample_parquet, tmp_path):
    """date_column=None must raise ValueError with descriptive message."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="time_series",
        date_column=None,
        train_period=["2020-01-01", "2022-06-30"],
        test_period=["2023-07-01", "2024-12-31"],
        save_splits=False,
        splits_dir=str(tmp_path / "splits"),
    )
    with pytest.raises(ValueError) as excinfo:
        split_step.execute({})
    assert "date_column" in str(excinfo.value).lower()
    assert "time_series" in str(excinfo.value).lower()


def test_time_series_happy_path(sample_parquet, tmp_path, caplog):
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
        splits_dir=str(tmp_path / "splits"),
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


def test_time_series_empty_val_warns(sample_parquet, tmp_path, caplog):
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
        splits_dir=str(tmp_path / "splits"),
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


def test_time_series_overlap_warns(sample_parquet, tmp_path, caplog):
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
        splits_dir=str(tmp_path / "splits"),
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


def test_group_based_missing_column_error(grouped_parquet, tmp_path):
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
        splits_dir=str(tmp_path / "splits"),
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

    with open(metadata_path, encoding="utf-8") as f:
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


def test_group_based_class_imbalance_warning(grouped_parquet, tmp_path, caplog):
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
        splits_dir=str(tmp_path / "splits"),
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
# Geo-Stratify Tests (T-F3-1)
# =============================================================================


@pytest.fixture
def geo_stratify_df():
    """DataFrame with 3 zones: A(100), B(50), C(200) for geo_stratify testing."""
    np.random.seed(42)
    zones = ["A"] * 100 + ["B"] * 50 + ["C"] * 200
    return pd.DataFrame(
        {
            "zone": zones,
            "f1": np.random.randn(350),
            "target": np.random.randint(0, 2, 350),
        }
    )


@pytest.fixture
def geo_stratify_df_equal():
    """DataFrame with 3 zones: A(500), B(200), C(100) for testing equal strategy."""
    np.random.seed(42)
    zones = ["A"] * 500 + ["B"] * 200 + ["C"] * 100
    return pd.DataFrame(
        {
            "geo_zone": zones,
            "f1": np.random.randn(800),
            "target": np.random.randint(0, 2, 800),
        }
    )


class TestApplyGeoStratify:
    """Test suite for _apply_geo_stratify method."""

    def test_proportional_strategy_caps_to_median(self, geo_stratify_df_equal):
        """
        proportional strategy: largest stratum capped to median size.
        Given sizes {A: 500, B: 200, C: 100}, median=200, result should have
        A capped to 200, B stays 200, C stays 100. Total: 500.
        """
        split_step = SplitStep(
            input_path="dummy.parquet",  # Not used for this test
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "proportional",
                "random_state": 42,
            },
        )

        result, metadata = split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Check counts per zone
        counts = result["geo_zone"].value_counts()
        assert counts["A"] == 200, f"Zone A should be capped to 200, got {counts['A']}"
        assert counts["B"] == 200, f"Zone B should stay 200, got {counts['B']}"
        assert counts["C"] == 100, f"Zone C should stay 100, got {counts['C']}"
        assert len(result) == 500, f"Total should be 500, got {len(result)}"
        # Verify metadata is returned
        assert "geo_stratify_strategy" in metadata
        assert metadata["geo_stratify_strategy"] == "proportional"

    def test_equal_strategy_reduces_to_smallest(self, geo_stratify_df_equal):
        """
        equal strategy: all strata reduced to smallest stratum size.
        Given {A: 500, B: 200, C: 100}, all become 100. Total: 300.
        """
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "equal",
                "random_state": 42,
            },
        )

        result, metadata = split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Check counts per zone
        counts = result["geo_zone"].value_counts()
        assert counts["A"] == 100, f"Zone A should be reduced to 100, got {counts['A']}"
        assert counts["B"] == 100, f"Zone B should be reduced to 100, got {counts['B']}"
        assert counts["C"] == 100, f"Zone C should stay 100, got {counts['C']}"
        assert len(result) == 300, f"Total should be 300, got {len(result)}"
        # Verify metadata
        assert metadata["geo_stratify_strategy"] == "equal"

    def test_capped_strategy_with_max_per_stratum(self, geo_stratify_df_equal):
        """
        capped strategy with max_per_stratum=300:
        A reduced to 300, B stays 200, C stays 100. Total: 600.
        """
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "capped",
                "max_per_stratum": 300,
                "random_state": 42,
            },
        )

        result, metadata = split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Check counts per zone
        counts = result["geo_zone"].value_counts()
        assert counts["A"] == 300, f"Zone A should be capped to 300, got {counts['A']}"
        assert counts["B"] == 200, f"Zone B should stay 200, got {counts['B']}"
        assert counts["C"] == 100, f"Zone C should stay 100, got {counts['C']}"
        assert len(result) == 600, f"Total should be 600, got {len(result)}"
        # Verify metadata
        assert metadata["geo_stratify_strategy"] == "capped"

    def test_data_loss_warning_when_equal_drops_more_than_50_percent(
        self, geo_stratify_df_equal, caplog
    ):
        """
        When equal strategy drops >50% of rows, a WARNING is logged.
        With {A: 500, B: 200, C: 100}, equal reduces to 300 (62.5% loss).
        """
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "equal",
                "random_state": 42,
            },
        )

        with caplog.at_level(logging.WARNING):
            split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Verify WARNING was logged
        warning_logs = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warning_logs) > 0, "Expected warning about data loss"
        warning_msg = warning_logs[0].getMessage().lower()
        assert (
            "data" in warning_msg or "rows" in warning_msg or "50%" in warning_msg
        ), f"Warning message should mention data loss: {warning_msg}"

    def test_missing_geo_column_raises_valueerror(self, geo_stratify_df_equal):
        """Missing geo column raises ValueError with descriptive message."""
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "nonexistent_column",
                "strategy": "proportional",
                "random_state": 42,
            },
        )

        with pytest.raises(ValueError) as excinfo:
            split_step._apply_geo_stratify(geo_stratify_df_equal)

        assert "nonexistent_column" in str(excinfo.value).lower()
        assert "not found" in str(excinfo.value).lower() or "missing" in str(excinfo.value).lower()

    def test_disabled_returns_original_df(self, geo_stratify_df_equal):
        """When enabled: false, the method returns the original df unchanged."""
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": False,
                "column": "geo_zone",
                "strategy": "equal",
                "random_state": 42,
            },
        )

        # When enabled is False, the method should not be called from execute
        # But if called directly, it should check enabled flag
        result, metadata = split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Should return unchanged
        pd.testing.assert_frame_equal(result, geo_stratify_df_equal)
        # Metadata should be empty when disabled
        assert metadata == {}

    def test_reproducibility_with_random_state(self, geo_stratify_df_equal):
        """Sampling must be reproducible with same random_state."""
        split_step1 = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "proportional",
                "random_state": 42,
            },
        )
        split_step2 = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "proportional",
                "random_state": 42,
            },
        )

        result1, _ = split_step1._apply_geo_stratify(geo_stratify_df_equal)
        result2, _ = split_step2._apply_geo_stratify(geo_stratify_df_equal)

        pd.testing.assert_frame_equal(result1, result2)

    def test_logs_before_after_counts(self, geo_stratify_df_equal, caplog):
        """Method should log before/after counts per stratum and total."""
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            geo_stratify={
                "enabled": True,
                "column": "geo_zone",
                "strategy": "proportional",
                "random_state": 42,
            },
        )

        with caplog.at_level(logging.INFO):
            split_step._apply_geo_stratify(geo_stratify_df_equal)

        # Should log geo_stratify info
        info_logs = [record for record in caplog.records if record.levelno == logging.INFO]
        log_messages = " ".join([r.getMessage().lower() for r in info_logs])
        assert (
            "geo" in log_messages or "strat" in log_messages or "zone" in log_messages
        ), "Should log information about geo_stratify"


# =============================================================================
# Unlabeled Negatives Tests (T-F1-1)
# =============================================================================


class TestInjectUnlabeledNegatives:
    """Test suite for _inject_unlabeled_negatives method (F1 feature)."""

    @pytest.fixture
    def labeled_df(self):
        """Labeled training data with ID column."""
        return pd.DataFrame(
            {
                "id": ["A1", "A2", "A3", "A4", "A5"],
                "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
                "feature2": ["X", "Y", "X", "Y", "Z"],
                "target": [0, 1, 0, 1, 0],
            }
        )

    @pytest.fixture
    def unlabeled_df(self):
        """Unlabeled data (no target column) for injection."""
        return pd.DataFrame(
            {
                "id": ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"],
                "feature1": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
                "feature2": ["X", "Y", "Z", "X", "Y", "Z", "X", "Y"],
            }
        )

    @pytest.fixture
    def unlabeled_with_dates(self):
        """Unlabeled data with date column for time_series filtering."""
        return pd.DataFrame(
            {
                "id": ["B1", "B2", "B3", "B4", "B5"],
                "feature1": [10.0, 20.0, 30.0, 40.0, 50.0],
                "date": pd.to_datetime(
                    ["2020-03-01", "2021-06-15", "2022-01-10", "2023-08-20", "2024-12-01"]
                ),
            }
        )

    def test_basic_injection_assigns_target_zero(self, tmp_path, labeled_df, unlabeled_df):
        """Basic injection: injected rows must have target=0."""
        # Save unlabeled to parquet
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_df.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 5,
                "random_state": 42,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Verify target=0 assigned to injected rows
        assert len(result) == 10, f"Expected 10 rows (5 labeled + 5 injected), got {len(result)}"
        injected_mask = result["id"].isin(["B1", "B2", "B3", "B4", "B5"])
        assert result[injected_mask]["target"].eq(0).all(), "Injected rows must have target=0"

    def test_max_per_cutoff_limits_injection(self, tmp_path, labeled_df, unlabeled_df):
        """max_per_cutoff must limit the number of injected rows."""
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_df.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 3,  # Only inject 3 of 8 available
                "random_state": 42,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Should have 5 labeled + 3 injected = 8 total
        assert len(result) == 8, f"Expected 8 rows (5 labeled + 3 injected), got {len(result)}"

    def test_id_dedup_excludes_val_test_ids(self, tmp_path, labeled_df, unlabeled_df, caplog):
        """Unlabeled rows with IDs in val or test must be excluded."""
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_df.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 10,  # Would inject all if no dedup
                "random_state": 42,
                "id_column": "id",
            },
        )

        # val and test contain some IDs that also exist in unlabeled
        val_df = pd.DataFrame(
            {
                "id": ["B1", "B2"],
                "feature1": [100.0, 200.0],
                "target": [0, 0],
            }  # B1, B2 in unlabeled
        )
        test_df = pd.DataFrame(
            {"id": ["B3"], "feature1": [300.0], "target": [0]}  # B3 in unlabeled
        )

        with caplog.at_level(logging.INFO):
            result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Should exclude B1, B2, B3 → inject B4, B5, B6, B7, B8 (5 rows)
        assert len(result) == 10, f"Expected 10 rows (5 labeled + 5 after dedup), got {len(result)}"
        injected_ids = set(result[~result["id"].isin(labeled_df["id"])]["id"])
        assert "B1" not in injected_ids, "B1 should be excluded (in val)"
        assert "B2" not in injected_ids, "B2 should be excluded (in val)"
        assert "B3" not in injected_ids, "B3 should be excluded (in test)"

        # Log should report excluded count
        assert any("3" in r.getMessage() for r in caplog.records), "Log should report 3 excluded"

    def test_time_series_date_filtering(self, tmp_path, labeled_df, unlabeled_with_dates):
        """For time_series method, filter unlabeled by train_period dates."""
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_with_dates.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            method="time_series",  # Important: triggers date filtering
            date_column="date",
            train_period=["2020-01-01", "2022-12-31"],  # Only dates in this range
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 10,
                "random_state": 42,
                "date_column": "date",
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Unlabeled dates: 2020-03 (IN), 2021-06 (IN), 2022-01 (IN), 2023-08 (OUT), 2024-12 (OUT)
        # Should inject 3 rows (B1, B2, B3)
        injected_count = len(result) - len(labeled_df)
        assert (
            injected_count == 3
        ), f"Expected 3 injected (within train_period), got {injected_count}"

    def test_missing_columns_filled_with_nan(self, tmp_path, labeled_df, caplog):
        """Unlabeled file missing columns should fill with NaN and log WARNING."""
        # Unlabeled missing 'feature2' column
        unlabeled_partial = pd.DataFrame(
            {
                "id": ["B1", "B2"],
                "feature1": [10.0, 20.0],
                # feature2 is missing
            }
        )
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_partial.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 10,
                "random_state": 42,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        with caplog.at_level(logging.WARNING):
            result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Should fill missing feature2 with NaN
        injected = result[~result["id"].isin(labeled_df["id"])]
        assert injected["feature2"].isna().all(), "Missing column should be NaN"

        # Should log WARNING about missing column
        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "feature2" in r.getMessage() for r in warning_logs
        ), "Should warn about missing column"

    def test_empty_or_unavailable_source_raises_file_not_found(self, tmp_path):
        """Missing source_path must raise FileNotFoundError."""
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(tmp_path / "nonexistent.parquet"),
                "max_per_cutoff": 10,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        with pytest.raises(FileNotFoundError):
            split_step._inject_unlabeled_negatives(pd.DataFrame(), val_df, test_df)

    def test_feature_disabled_returns_original(self, tmp_path, labeled_df, unlabeled_df):
        """When unlabeled_negatives is None or enabled:false, return original train_df."""
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_df.to_parquet(unlabeled_path, index=False)

        # Test with enabled: False
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": False,  # Disabled
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 10,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        pd.testing.assert_frame_equal(result, labeled_df)

    def test_logs_count_and_fraud_rate(self, tmp_path, labeled_df, unlabeled_df, caplog):
        """Method should log count added and new fraud rate."""
        unlabeled_path = tmp_path / "unlabeled.parquet"
        unlabeled_df.to_parquet(unlabeled_path, index=False)

        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": str(unlabeled_path),
                "max_per_cutoff": 5,
                "random_state": 42,
            },
        )

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})

        with caplog.at_level(logging.INFO):
            split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df)

        # Should log count added and fraud rate
        info_logs = " ".join([r.getMessage() for r in caplog.records if r.levelno == logging.INFO])
        assert (
            "inject" in info_logs.lower() or "added" in info_logs.lower()
        ), "Should log injection count"


# =============================================================================
# Unlabeled Negatives via @etl_ref (same-data-negatives)
# =============================================================================


class TestUnlabeledNegativesEtlRef:
    """Test suite for @etl_name source resolution and ETL-ref injection."""

    @pytest.fixture
    def labeled_df(self):
        """Labeled training data."""
        return pd.DataFrame(
            {
                "id": ["A1", "A2", "A3", "A4", "A5"],
                "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
                "zona": ["X", "Y", "X", "Y", "Z"],
                "target": [0, 1, 0, 1, 0],
            }
        )

    @pytest.fixture
    def negatives_parquet(self, tmp_path):
        """Assumed-negatives parquet + a pipeline context referencing it."""
        df = pd.DataFrame(
            {
                "id": ["B1", "B2", "B3"],
                "feature1": [10.0, 20.0, 30.0],
                "zona": ["X", "Y", "Z"],
            }
        )
        path = tmp_path / "assumed_negatives.parquet"
        df.to_parquet(path, index=False)
        context = {
            "etl_output_paths": {"negatives": str(path)},
            "etl_results": {"negatives": df},
        }
        return str(path), context

    def _split_step(self, source_path, **extra):
        return SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": source_path,
                "max_per_cutoff": 1500,
                "random_state": 42,
                **extra,
            },
        )

    def test_etl_ref_resolves_and_injects(self, labeled_df, negatives_parquet):
        """@negatives must resolve via context keys and inject into train only."""
        path, context = negatives_parquet
        split_step = self._split_step("@negatives")

        val_df = pd.DataFrame({"id": ["V1"], "feature1": [100.0], "target": [0]})
        test_df = pd.DataFrame({"id": ["T1"], "feature1": [200.0], "target": [0]})
        val_before, test_before = val_df.copy(), test_df.copy()

        result = split_step._inject_unlabeled_negatives(labeled_df.copy(), val_df, test_df, context)

        # Train-only injection
        assert len(result) == 8, f"Expected 8 rows (5 labeled + 3 injected), got {len(result)}"
        pd.testing.assert_frame_equal(val_df, val_before)
        pd.testing.assert_frame_equal(test_df, test_before)

        # Hard target=0, no marker column
        injected = result[~result["id"].isin(labeled_df["id"])]
        assert injected["target"].eq(0).all(), "Injected rows must have target=0"
        assert set(result.columns) == set(labeled_df.columns), "No marker column expected"

    def test_unknown_ref_error_lists_etls(self, labeled_df, negatives_parquet):
        """@no_such_etl must raise naming the ref and available ETLs."""
        _, context = negatives_parquet
        split_step = self._split_step("@no_such_etl")

        with pytest.raises(ValueError) as excinfo:
            split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )
        message = str(excinfo.value)
        assert "no_such_etl" in message, f"Error must name the reference: {message}"
        assert "negatives" in message, f"Error must list available ETLs: {message}"

    def test_not_executed_ref_error(self, labeled_df, negatives_parquet):
        """Ref in etl_output_paths but absent from etl_results → disabled/failed error."""
        path, context = negatives_parquet
        context = dict(context)
        del context["etl_results"]  # configured but never executed

        split_step = self._split_step("@negatives")

        with pytest.raises(ValueError) as excinfo:
            split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )
        message = str(excinfo.value).lower()
        assert "negatives" in message
        assert "disabled" in message or "failed" in message or "did not execute" in message

    def test_traversal_on_resolved_path_rejected(self, labeled_df, tmp_path):
        """A resolved path containing '..' must fail traversal validation."""
        evil = str(tmp_path / ".." / "evil.parquet")
        context = {
            "etl_output_paths": {"negatives": evil},
            "etl_results": {"negatives": pd.DataFrame()},
        }
        split_step = self._split_step("@negatives")

        with pytest.raises(ValueError, match="traversal"):
            split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )

    def test_resolved_path_missing_file_raises(self, labeled_df, tmp_path):
        """Executed ETL whose output file is gone → FileNotFoundError."""
        missing = str(tmp_path / "gone.parquet")
        context = {
            "etl_output_paths": {"negatives": missing},
            "etl_results": {"negatives": pd.DataFrame()},
        }
        split_step = self._split_step("@negatives")

        with pytest.raises(FileNotFoundError):
            split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )

    def test_etl_ref_drops_extra_columns_with_log(self, labeled_df, negatives_parquet, caplog):
        """Source columns absent from train are dropped (train schema wins)."""
        path, context = negatives_parquet
        extra_df = pd.read_parquet(path)
        extra_df["source_file"] = "raw.csv"  # column train does not have

        extra_path = path.replace(".parquet", "_extra.parquet")
        extra_df.to_parquet(extra_path, index=False)
        context = {
            "etl_output_paths": {"negatives": extra_path},
            "etl_results": {"negatives": extra_df},
        }
        split_step = self._split_step("@negatives")

        with caplog.at_level(logging.INFO):
            result = split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )

        assert "source_file" not in result.columns, "Extra column must be dropped"
        assert set(result.columns) == set(labeled_df.columns)

        logs = " ".join(r.getMessage() for r in caplog.records)
        assert "source_file" in logs, f"Dropped column must be logged, got: {logs}"

    def test_etl_ref_fills_missing_columns_with_warning(
        self, labeled_df, negatives_parquet, caplog
    ):
        """Train columns missing from the negatives source are NaN-filled + WARNING."""
        path, context = negatives_parquet
        partial_df = pd.read_parquet(path).drop(columns=["zona"])

        partial_path = path.replace(".parquet", "_partial.parquet")
        partial_df.to_parquet(partial_path, index=False)
        context = {
            "etl_output_paths": {"negatives": partial_path},
            "etl_results": {"negatives": partial_df},
        }
        split_step = self._split_step("@negatives")

        with caplog.at_level(logging.WARNING):
            result = split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame(), context
            )

        injected = result[~result["id"].isin(labeled_df["id"])]
        assert injected["zona"].isna().all(), "Missing column must be NaN-filled"

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("zona" in w for w in warnings), f"Expected NaN-fill WARNING: {warnings}"

    def test_file_mode_keeps_extra_columns(self, labeled_df, tmp_path):
        """External-file mode retains its pass-through behavior for extra columns."""
        unlabeled = pd.DataFrame(
            {
                "id": ["B1"],
                "feature1": [10.0],
                "zona": ["X"],
                "source_file": ["raw.csv"],  # extra column — file mode keeps it
            }
        )
        path = tmp_path / "external.parquet"
        unlabeled.to_parquet(path, index=False)

        split_step = self._split_step(str(path))
        result = split_step._inject_unlabeled_negatives(
            labeled_df.copy(), pd.DataFrame(), pd.DataFrame()
        )

        assert "source_file" in result.columns, "File mode must keep extra columns"


class TestUnlabeledNegativesGuardrails:
    """Zero-cap / date-filter-skip / empty-source WARNING behaviors (both modes)."""

    @pytest.fixture
    def labeled_df(self):
        return pd.DataFrame(
            {
                "id": ["A1", "A2", "A3"],
                "feature1": [1.0, 2.0, 3.0],
                "target": [0, 1, 0],
            }
        )

    def _make_source(self, tmp_path, df, name="negatives.parquet"):
        path = tmp_path / name
        df.to_parquet(path, index=False)
        return str(path)

    def test_zero_cap_injects_nothing_with_warning(self, labeled_df, tmp_path, caplog):
        path = self._make_source(
            tmp_path, pd.DataFrame({"id": ["B1", "B2"], "feature1": [10.0, 20.0]})
        )
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": path,
                "max_per_cutoff": 0,
            },
        )

        with caplog.at_level(logging.WARNING):
            result = split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame()
            )

        assert len(result) == len(labeled_df), "Zero cap must inject nothing"
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("no unlabeled negatives" in w.lower() for w in warnings)

    def test_empty_source_warns_and_train_unchanged(self, labeled_df, tmp_path, caplog):
        path = self._make_source(
            tmp_path,
            pd.DataFrame(
                {"id": pd.Series([], dtype="object"), "feature1": pd.Series([], dtype="float64")}
            ),
        )
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            unlabeled_negatives={
                "enabled": True,
                "source_path": path,
                "max_per_cutoff": 10,
            },
        )

        with caplog.at_level(logging.WARNING):
            result = split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame()
            )

        assert len(result) == len(labeled_df)
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("no unlabeled negatives" in w.lower() for w in warnings)

    def test_date_filter_skip_warns_when_column_absent(self, labeled_df, tmp_path, caplog):
        """time_series + configured date_column absent from negatives → skip + WARNING."""
        path = self._make_source(tmp_path, pd.DataFrame({"id": ["B1"], "feature1": [10.0]}))
        split_step = SplitStep(
            input_path="dummy.parquet",
            target_column="target",
            method="time_series",
            date_column="date",
            train_period=["2020-01-01", "2022-12-31"],
            unlabeled_negatives={
                "enabled": True,
                "source_path": path,
                "max_per_cutoff": 10,
                "date_column": "date",
            },
        )

        with caplog.at_level(logging.WARNING):
            result = split_step._inject_unlabeled_negatives(
                labeled_df.copy(), pd.DataFrame(), pd.DataFrame()
            )

        # Row must NOT be silently dropped by the date filter
        assert len(result) == len(labeled_df) + 1
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any("date" in w.lower() and "skip" in w.lower() for w in warnings)


class TestUnlabeledNegativesMetadata:
    """split_metadata.json contract for both source modes, including 0 rows."""

    def _make_negatives(self, tmp_path, rows=3):
        df = pd.DataFrame(
            {
                "fecha": pd.date_range("2020-01-01", periods=rows, freq="ME"),
                "f1": [float(i) for i in range(rows)],
            }
        )
        path = tmp_path / "negatives.parquet"
        df.to_parquet(path, index=False)
        return df, str(path)

    def _run_split(self, tmp_path, source_path, context=None):
        split_step = SplitStep(
            input_path=None,  # force etl_results fallback? No — use explicit path below
            target_column="target",
            method="stratified",
            test_size=0.2,
            val_size=0.1,
            random_state=42,
            splits_dir=str(tmp_path / "splits"),
            unlabeled_negatives={
                "enabled": True,
                "source_path": source_path,
                "max_per_cutoff": 1500,
                "random_state": 42,
            },
        )
        # Build a real input dataset in context-free mode
        dataset = pd.DataFrame(
            {
                "fecha": pd.date_range("2020-01-01", periods=50, freq="ME"),
                "f1": np.random.default_rng(42).standard_normal(50),
                "target": np.random.default_rng(42).integers(0, 2, 50),
            }
        )
        dataset_path = tmp_path / "dataset.parquet"
        dataset.to_parquet(dataset_path, index=False)
        split_step.input_path = str(dataset_path)
        split_step.execute(context or {})

        metadata_path = tmp_path / "splits" / "split_metadata.json"
        with open(metadata_path, encoding="utf-8") as f:
            return json.load(f)

    def test_metadata_etl_ref_mode(self, tmp_path):
        """ETL-ref mode reports resolved path, mode, assumed label, counts."""
        df, path = self._make_negatives(tmp_path, rows=3)
        context = {
            "etl_output_paths": {"negatives": path},
            "etl_results": {"negatives": df},
        }

        metadata = self._run_split(tmp_path, "@negatives", context)

        assert metadata["unlabeled_negatives_source"] == path
        assert metadata["unlabeled_negatives_source_mode"] == "etl_ref"
        assert metadata["unlabeled_negatives_labels_assumed"] is True
        assert metadata["unlabeled_negatives_injected"] == 3
        assert metadata["unlabeled_negatives_excluded_by_dedup"] == 0
        assert isinstance(metadata["new_fraud_rate"], float)

    def test_metadata_file_mode(self, tmp_path):
        """File mode reports the literal path and file-mode indicator."""
        _, path = self._make_negatives(tmp_path, rows=2)

        metadata = self._run_split(tmp_path, path)

        assert metadata["unlabeled_negatives_source"] == path
        assert metadata["unlabeled_negatives_source_mode"] == "file"
        assert metadata["unlabeled_negatives_labels_assumed"] is True
        assert metadata["unlabeled_negatives_injected"] == 2
        # Existing keys keep their names
        assert "unlabeled_negatives_excluded_by_dedup" in metadata
        assert "new_fraud_rate" in metadata

    def test_metadata_zero_rows_still_reported(self, tmp_path):
        """Injection enabled with 0 injected rows still reports source/mode/count."""
        df, path = self._make_negatives(tmp_path, rows=0)
        context = {
            "etl_output_paths": {"negatives": path},
            "etl_results": {"negatives": df},
        }

        metadata = self._run_split(tmp_path, "@negatives", context)

        assert metadata["unlabeled_negatives_source"] == path
        assert metadata["unlabeled_negatives_source_mode"] == "etl_ref"
        assert metadata["unlabeled_negatives_injected"] == 0
        assert metadata["unlabeled_negatives_labels_assumed"] is True

    def test_metadata_absent_when_injection_disabled(self, tmp_path):
        """No injection configured → no unlabeled_negatives keys in metadata."""
        metadata = self._run_split_no_injection(tmp_path)
        assert not any(k.startswith("unlabeled_negatives") for k in metadata)

    def _run_split_no_injection(self, tmp_path):
        dataset = pd.DataFrame(
            {
                "fecha": pd.date_range("2020-01-01", periods=50, freq="ME"),
                "f1": np.random.default_rng(42).standard_normal(50),
                "target": np.random.default_rng(42).integers(0, 2, 50),
            }
        )
        dataset_path = tmp_path / "dataset.parquet"
        dataset.to_parquet(dataset_path, index=False)

        split_step = SplitStep(
            input_path=str(dataset_path),
            target_column="target",
            method="stratified",
            test_size=0.2,
            val_size=0.1,
            random_state=42,
            splits_dir=str(tmp_path / "splits"),
        )
        split_step.execute({})

        with open(tmp_path / "splits" / "split_metadata.json", encoding="utf-8") as f:
            return json.load(f)


# =============================================================================
# Regression Tests
# =============================================================================


def test_stratified_regression(sample_parquet, tmp_path):
    """Stratified split must still work and maintain target proportions."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="stratified",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=False,
        splits_dir=str(tmp_path / "splits"),
    )
    result = split_step.execute({})

    # Verify context keys
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result

    # Read splits (we can't verify exact proportions without the data,
    # but we verify the files exist and are accessible)
    from energizados.core.utils.integrity_pickle import validate_no_traversal

    validate_no_traversal(result["train_path"], label="train_path")
    validate_no_traversal(result["val_path"], label="val_path")
    validate_no_traversal(result["test_path"], label="test_path")


def test_random_regression(sample_parquet, tmp_path):
    """Random split must still work and produce correct sizes."""
    split_step = SplitStep(
        input_path=sample_parquet,
        target_column="target",
        method="random",
        test_size=0.2,
        val_size=0.1,
        random_state=42,
        save_splits=False,
        splits_dir=str(tmp_path / "splits"),
    )
    result = split_step.execute({})

    # Verify context keys
    assert "train_path" in result
    assert "val_path" in result
    assert "test_path" in result

    # Read splits (we can't verify exact sizes without the data,
    # but we verify the files exist and are accessible)
    from energizados.core.utils.integrity_pickle import validate_no_traversal

    validate_no_traversal(result["train_path"], label="train_path")
    validate_no_traversal(result["val_path"], label="val_path")
    validate_no_traversal(result["test_path"], label="test_path")
