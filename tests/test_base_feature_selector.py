"""
Unit tests for BaseFeatureSelector.

Tests for the Feature Selection base class that defines the interface
that all custom selectors must implement.
"""

import pandas as pd
import pytest

from energizados.core.exceptions import ModelNotFittedError
from energizados.feature_selection.base import BaseFeatureSelector


class TestBaseFeatureSelector:
    """Tests for the BaseFeatureSelector class."""

    @pytest.fixture
    def sample_data(self):
        """Returns sample data for testing.

        Returns:
            tuple: A tuple containing:
                - X (pd.DataFrame): Feature DataFrame with constant and variable features.
                - y (pd.Series): Target Series with binary labels.
        """
        X = pd.DataFrame(
            {
                "feature1": [1, 2, 3, 4, 5],
                "feature2": [2, 4, 6, 8, 10],
                "feature3": [1, 1, 1, 1, 1],  # Constant
                "feature4": [5, 4, 3, 2, 1],
            }
        )
        y = pd.Series([0, 0, 1, 1, 1])
        return X, y

    def test_base_selector_has_config(self):
        """Verify that BaseFeatureSelector accepts config."""

        # Create minimal concrete implementation to test config
        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector(config={"threshold": 0.5})
        assert selector.config == {"threshold": 0.5}

    def test_base_selector_default_config(self):
        """Verify that BaseFeatureSelector uses empty config by default."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()
        assert selector.config == {}

    def test_base_selector_initialized_with_selected_features(self):
        """Verify that selected_features_ is initialized as None."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()
        assert selector.selected_features_ is None

    def test_concrete_selector_must_implement_fit(self):
        """Verify that a selector must implement fit()."""

        class IncompleteSelector(BaseFeatureSelector):
            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X

        with pytest.raises(TypeError):
            IncompleteSelector()

    def test_concrete_selector_must_implement_transform(self):
        """Verify that a selector must implement transform()."""

        class IncompleteSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                return self

        with pytest.raises(TypeError):
            IncompleteSelector()

    def test_complete_selector_can_be_instantiated(self):
        """Verify that a complete selector can be instantiated."""

        class CompleteSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature2"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = CompleteSelector()
        assert selector is not None

    def test_fit_transform_method(self, sample_data):
        """Verify that fit_transform works correctly."""
        X, y = sample_data

        class TestSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature2"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = TestSelector()
        result = selector.fit_transform(X, y)

        expected = pd.DataFrame({"feature1": [1, 2, 3, 4, 5], "feature2": [2, 4, 6, 8, 10]})
        pd.testing.assert_frame_equal(result, expected)

    def test_get_selected_features_raises_error_if_not_fitted(self):
        """Verify that get_selected_features raises error if fit was not called."""

        class ConcreteSelector(BaseFeatureSelector):
            def fit(self, X, y):
                return self

            def transform(self, X):
                return X

        selector = ConcreteSelector()

        with pytest.raises(ModelNotFittedError):
            selector.get_selected_features()

    def test_get_selected_features_returns_features(self, sample_data):
        """Verify that get_selected_features returns the selected features."""
        X, y = sample_data

        class TestSelector(BaseFeatureSelector):
            def fit(self, X: pd.DataFrame, y: pd.Series):
                self.selected_features_ = ["feature1", "feature4"]
                return self

            def transform(self, X: pd.DataFrame) -> pd.DataFrame:
                return X[self.selected_features_]

        selector = TestSelector()
        selector.fit(X, y)

        features = selector.get_selected_features()
        assert features == ["feature1", "feature4"]
