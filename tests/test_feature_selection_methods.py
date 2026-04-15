"""
Unit tests for feature selection methods.

Tests cover:
- CorrelationSelector
- ConstantSelector
- BorutaSelector
"""

import numpy as np
import pandas as pd
import pytest

from energizados.feature_selection.methods import (
    BorutaSelector,
    ConstantSelector,
    CorrelationSelector,
)


class TestCorrelationSelector:
    """Tests for CorrelationSelector class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data with correlated features.

        Returns:
            tuple: (X, y) where X has correlated features and y is binary target.
        """
        np.random.seed(42)
        n_samples = 100

        # Create features with correlation
        feature_0 = np.random.randn(n_samples)
        feature_1 = (
            feature_0 * 0.95 + np.random.randn(n_samples) * 0.1
        )  # Highly correlated with feature_0
        feature_2 = np.random.randn(n_samples)
        feature_3 = (
            feature_2 * 0.92 + np.random.randn(n_samples) * 0.15
        )  # Highly correlated with feature_2
        feature_4 = np.random.randn(n_samples)  # Independent feature
        feature_5 = np.random.randn(n_samples)  # Independent feature

        X = pd.DataFrame(
            {
                "feature_0": feature_0,
                "feature_1": feature_1,
                "feature_2": feature_2,
                "feature_3": feature_3,
                "feature_4": feature_4,
                "feature_5": feature_5,
            }
        )

        # Target correlates with feature_0 (should be kept over feature_1)
        y = pd.Series((feature_0 + np.random.randn(n_samples) * 0.2) > 0).astype(int)

        return X, y

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        selector = CorrelationSelector()
        assert selector.method == "pearson"
        assert selector.threshold == 0.9
        assert selector.vars_to_drop_ is None
        assert selector.selected_features_ is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        selector = CorrelationSelector(method="spearman", threshold=0.85)
        assert selector.method == "spearman"
        assert selector.threshold == 0.85

    def test_fit_returns_self(self, sample_data):
        """Test that fit() returns self."""
        X, y = sample_data
        selector = CorrelationSelector()
        result = selector.fit(X, y)
        assert result is selector

    def test_fit_sets_selected_features(self, sample_data):
        """Test that fit() sets selected_features_ attribute."""
        X, y = sample_data
        selector = CorrelationSelector(threshold=0.9)
        selector.fit(X, y)
        assert selector.selected_features_ is not None
        assert isinstance(selector.selected_features_, list)
        assert len(selector.selected_features_) < X.shape[1]  # Should drop some correlated features

    def test_fit_sets_vars_to_drop(self, sample_data):
        """Test that fit() sets vars_to_drop_ attribute."""
        X, y = sample_data
        selector = CorrelationSelector(threshold=0.9)
        selector.fit(X, y)
        assert selector.vars_to_drop_ is not None
        assert isinstance(selector.vars_to_drop_, list)

    def test_transform_filters_selected_features(self, sample_data):
        """Test that transform() returns DataFrame with only selected features."""
        X, y = sample_data
        selector = CorrelationSelector(threshold=0.9)
        selector.fit(X, y)
        X_transformed = selector.transform(X)

        assert X_transformed.shape[1] == len(selector.selected_features_)
        assert list(X_transformed.columns) == selector.selected_features_
        assert X_transformed.shape[1] < X.shape[1]  # Should have dropped features

    def test_transform_raises_when_not_fitted(self, sample_data):
        """Test that transform() raises ValueError when fit not called."""
        X, y = sample_data
        selector = CorrelationSelector()

        with pytest.raises(ValueError, match="Must call fit"):
            selector.transform(X)

    def test_fit_transform_single_call(self, sample_data):
        """Test that fit_transform() works correctly."""
        X, y = sample_data
        selector = CorrelationSelector(threshold=0.9)
        X_transformed = selector.fit_transform(X, y)

        assert X_transformed.shape[1] == len(selector.selected_features_)
        assert X_transformed.shape[1] < X.shape[1]

    def test_handles_non_numeric_columns(self):
        """Test that non-numeric columns are filtered out."""
        np.random.seed(42)
        X = pd.DataFrame(
            {
                "num1": np.random.randn(100),
                "num2": np.random.randn(100),
                "str_col": ["a"] * 50 + ["b"] * 50,
                "dt_col": pd.date_range("2020-01-01", periods=100),
            }
        )
        y = pd.Series(np.random.randint(0, 2, 100))

        selector = CorrelationSelector()
        selector.fit(X, y)

        # Should only select from numeric columns
        assert all(f in ["num1", "num2"] for f in selector.selected_features_)

    def test_threshold_zero_keeps_features(self, sample_data):
        """Test that threshold=0 behavior (keeps some correlated features)."""
        X, y = sample_data
        selector = CorrelationSelector(threshold=0.0)
        selector.fit(X, y)

        # With threshold 0, the algorithm still compares correlations
        # Features with higher correlation to target are kept over those with lower
        # So we should still have selected features (just fewer drops)
        assert len(selector.selected_features_) > 0
        assert selector.selected_features_ is not None

    def test_different_correlation_methods(self, sample_data):
        """Test that different correlation methods work."""
        X, y = sample_data

        for method in ["pearson", "spearman", "kendall"]:
            selector = CorrelationSelector(method=method)
            selector.fit(X, y)
            assert selector.selected_features_ is not None
            assert len(selector.selected_features_) <= X.shape[1]


class TestConstantSelector:
    """Tests for ConstantSelector class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data with constant and near-constant features.

        Returns:
            tuple: (X, y) where X has constant features and y is binary target.
        """
        np.random.seed(42)
        n_samples = 100

        X = pd.DataFrame(
            {
                "feature_0": np.random.randn(n_samples),
                "feature_1": np.random.randn(n_samples),
                "constant_0": [5.0] * n_samples,  # Completely constant
                "constant_1": [3.0] * n_samples,  # Completely constant
                "feature_2": np.random.randn(n_samples),
            }
        )

        y = pd.Series(np.random.randint(0, 2, n_samples))

        return X, y

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        selector = ConstantSelector()
        assert selector.threshold == 0.99
        assert selector.vars_to_drop_ is None
        assert selector.selected_features_ is None

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        selector = ConstantSelector(threshold=0.95)
        assert selector.threshold == 0.95

    def test_fit_returns_self(self, sample_data):
        """Test that fit() returns self."""
        X, y = sample_data
        selector = ConstantSelector()
        result = selector.fit(X, y)
        assert result is selector

    def test_fit_removes_constant_features(self, sample_data):
        """Test that fit() removes constant features."""
        X, y = sample_data
        selector = ConstantSelector(threshold=0.99)
        selector.fit(X, y)

        # Should drop constant_0 and constant_1 (both are 100% constant)
        assert "constant_0" not in selector.selected_features_
        assert "constant_1" not in selector.selected_features_
        assert len(selector.selected_features_) < X.shape[1]

    def test_fit_sets_selected_features(self, sample_data):
        """Test that fit() sets selected_features_ attribute."""
        X, y = sample_data
        selector = ConstantSelector()
        selector.fit(X, y)
        assert selector.selected_features_ is not None
        assert isinstance(selector.selected_features_, list)

    def test_fit_sets_vars_to_drop(self, sample_data):
        """Test that fit() sets vars_to_drop_ attribute."""
        X, y = sample_data
        selector = ConstantSelector()
        selector.fit(X, y)
        assert selector.vars_to_drop_ is not None
        assert isinstance(selector.vars_to_drop_, list)
        assert len(selector.vars_to_drop_) > 0

    def test_transform_filters_selected_features(self, sample_data):
        """Test that transform() returns DataFrame with only selected features."""
        X, y = sample_data
        selector = ConstantSelector()
        selector.fit(X, y)
        X_transformed = selector.transform(X)

        assert X_transformed.shape[1] == len(selector.selected_features_)
        assert list(X_transformed.columns) == selector.selected_features_
        # Both constant_0 and constant_1 should be filtered out
        assert "constant_0" not in X_transformed.columns
        assert "constant_1" not in X_transformed.columns

    def test_transform_raises_when_not_fitted(self, sample_data):
        """Test that transform() raises ValueError when fit not called."""
        X, y = sample_data
        selector = ConstantSelector()

        with pytest.raises(ValueError, match="Must call fit"):
            selector.transform(X)

    def test_fit_transform_single_call(self, sample_data):
        """Test that fit_transform() works correctly."""
        X, y = sample_data
        selector = ConstantSelector()
        X_transformed = selector.fit_transform(X, y)

        assert X_transformed.shape[1] == len(selector.selected_features_)
        assert X_transformed.shape[1] < X.shape[1]

    def test_handles_non_numeric_columns(self):
        """Test that non-numeric columns are filtered out."""
        np.random.seed(42)
        X = pd.DataFrame(
            {
                "num1": np.random.randn(100),
                "num2": np.random.randn(100),
                "str_col": ["a"] * 50 + ["b"] * 50,
                "dt_col": pd.date_range("2020-01-01", periods=100),
            }
        )
        y = pd.Series(np.random.randint(0, 2, 100))

        selector = BorutaSelector(n_estimators=10, max_iter=2)
        selector.fit(X, y)

        # Should only select from numeric columns
        assert all(f in ["num1", "num2"] for f in selector.selected_features_)

    def test_transform_handles_missing_features(self):
        """Test that transform() handles features not in input DataFrame."""
        np.random.seed(42)
        X_train = pd.DataFrame(
            {
                "feature_0": np.random.randn(100),
                "feature_1": np.random.randn(100),
            }
        )
        y = pd.Series(np.random.randint(0, 2, 100))

        # Fit on training data
        selector = BorutaSelector(n_estimators=10, max_iter=2)
        selector.fit(X_train, y)

        # Transform with missing feature (should only return available features)
        X_test = pd.DataFrame(
            {
                "feature_0": np.random.randn(50),
                # feature_1 is missing
            }
        )
        X_transformed = selector.transform(X_test)

        # Should only return available features
        assert "feature_0" in X_transformed.columns
        assert X_transformed.shape[1] <= len(selector.selected_features_)

    def test_with_config(self):
        """Test initialization with config parameter."""
        config = {"output_dir": "output/test"}
        selector = BorutaSelector(config=config)

        assert selector.config == config

    def test_small_dataset(self):
        """Test behavior with very small dataset."""
        np.random.seed(42)
        X = pd.DataFrame(
            {
                "feature_0": np.random.randn(20),
                "feature_1": np.random.randn(20),
            }
        )
        y = pd.Series(np.random.randint(0, 2, 20))

        selector = BorutaSelector(n_estimators=5, max_iter=1)
        selector.fit(X, y)

        assert selector.selected_features_ is not None
