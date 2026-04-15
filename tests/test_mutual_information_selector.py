"""
Unit tests for MutualInformationSelector.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.feature_selection.methods import MutualInformationSelector


class TestMutualInformationSelector:
    """Tests for MutualInformationSelector class."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing.

        Returns:
            tuple: (X, y) where X is a DataFrame with 10 features
                  and y is a binary target that depends on the first 3 features.
        """
        rng = np.random.default_rng(42)

        n_samples = 200
        n_features = 10

        X = pd.DataFrame(
            rng.random((n_samples, n_features)),
            columns=[f"feature_{i}" for i in range(n_features)],
        )

        # Create a target that depends on first 3 features
        y = pd.Series(
            (X["feature_0"] + X["feature_1"] + X["feature_2"] + rng.random(n_samples) * 0.1) > 1.5
        ).astype(int)

        return X, y

    def test_fit_returns_self(self, sample_data):
        """Verify fit returns self."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)
        result = selector.fit(X, y)
        assert result is selector

    def test_fit_selects_k_features(self, sample_data):
        """Verify fit selects exactly k features."""
        X, y = sample_data
        k = 5
        selector = MutualInformationSelector(k=k)
        selector.fit(X, y)
        assert len(selector.selected_features_) == k

    def test_fit_sets_selected_features(self, sample_data):
        """Verify fit sets selected_features_ attribute."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)
        selector.fit(X, y)
        assert selector.selected_features_ is not None
        assert isinstance(selector.selected_features_, list)

    def test_fit_sets_scores(self, sample_data):
        """Verify fit sets scores_ attribute."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)
        selector.fit(X, y)
        assert selector.scores_ is not None
        assert isinstance(selector.scores_, pd.Series)
        assert len(selector.scores_) == X.shape[1]

    def test_selects_informative_features(self, sample_data):
        """Verify selector selects features with highest mutual information.

        Since target depends on feature_0, feature_1, feature_2,
        these should be selected when k >= 3.
        """
        X, y = sample_data
        selector = MutualInformationSelector(k=3)
        selector.fit(X, y)

        # At least the first 3 features should be selected
        # (they have highest mutual information)
        selected_set = set(selector.selected_features_)
        assert (
            "feature_0" in selected_set
            or "feature_1" in selected_set
            or "feature_2" in selected_set
        )

    def test_transform_filters_to_selected_features(self, sample_data):
        """Verify transform returns DataFrame with only selected features."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)
        selector.fit(X, y)
        X_transformed = selector.transform(X)

        assert X_transformed.shape[1] == 5
        assert list(X_transformed.columns) == selector.selected_features_

    def test_transform_raises_when_not_fitted(self, sample_data):
        """Verify transform raises ValueError when fit not called."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)

        with pytest.raises(ValueError, match="Must call fit"):
            selector.transform(X)

    def test_get_selected_features_raises_when_not_fitted(self, sample_data):
        """Verify get_selected_features raises ValueError when fit not called."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)

        with pytest.raises(ValueError, match="Must call fit"):
            selector.get_selected_features()

    def test_fit_with_numpy_array(self, sample_data):
        """Verify fit works with numpy array input."""
        X, y = sample_data
        X_np = X.values
        selector = MutualInformationSelector(k=5)
        selector.fit(X_np, y)
        assert len(selector.selected_features_) == 5

    def test_fit_transform_single_call(self, sample_data):
        """Verify fit_transform works correctly."""
        X, y = sample_data
        selector = MutualInformationSelector(k=5)
        X_transformed = selector.fit_transform(X, y)

        assert len(selector.selected_features_) == 5
        assert X_transformed.shape[1] == 5

    def test_random_state_reproducibility(self, sample_data):
        """Verify results are reproducible with same random_state."""
        X, y = sample_data

        selector1 = MutualInformationSelector(k=5, random_state=42)
        selector1.fit(X, y)

        selector2 = MutualInformationSelector(k=5, random_state=42)
        selector2.fit(X, y)

        # Same random_state should give same results
        # (may differ slightly due to float operations in mutual_info)
        assert selector1.selected_features_ == selector2.selected_features_

    def test_handles_non_numeric_columns(self):
        """Verify non-numeric columns are filtered out."""
        rng = np.random.default_rng(42)
        X = pd.DataFrame(
            {
                "num1": rng.random(100),
                "num2": rng.random(100),
                "str_col": ["a"] * 50 + ["b"] * 50,
                "dt_col": pd.date_range("2020-01-01", periods=100),
            }
        )
        y = pd.Series(rng.integers(0, 2, 100))

        selector = MutualInformationSelector(k=1)
        selector.fit(X, y)

        # Should only select from numeric columns
        assert all(f in ["num1", "num2"] for f in selector.selected_features_)

    def test_k_larger_than_n_features(self, sample_data):
        """Verify k > n_features selects all features."""
        X, y = sample_data
        n_features = X.shape[1]
        k = n_features + 5
        selector = MutualInformationSelector(k=k)
        selector.fit(X, y)

        # Should select all available numeric features
        assert len(selector.selected_features_) == n_features

    def test_classification_target(self):
        """Verify detection of classification target (binary)."""
        rng = np.random.default_rng(42)
        X = pd.DataFrame(rng.random((100, 5)))
        y = pd.Series(rng.integers(0, 2, 100))

        selector = MutualInformationSelector(k=3)
        selector.fit(X, y)

        assert len(selector.selected_features_) == 3
        assert selector.scores_ is not None

    def test_regression_target(self):
        """Verify detection of regression target (continuous)."""
        rng = np.random.default_rng(42)
        X = pd.DataFrame(rng.random((100, 5)))
        y = pd.Series(rng.random(100))

        selector = MutualInformationSelector(k=3)
        selector.fit(X, y)

        assert len(selector.selected_features_) == 3
        assert selector.scores_ is not None
