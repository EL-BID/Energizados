"""
Tests for IsolationForestScore transformer.

Comprehensive unit tests for the IsolationForestScore sklearn transformer.
All tests should FAIL initially (class doesn't exist), then PASS after implementation.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import NotFittedError

# These imports will fail until the class is implemented
from energizados.preprocessing.isolation_forest_score import IsolationForestScore


class TestConstructor:
    """Test constructor parameter handling."""

    def test_default_params(self):
        """Default parameters should be set correctly."""
        transformer = IsolationForestScore()
        params = transformer.get_params()

        assert params["columns"] is None
        assert params["n_estimators"] == 100
        assert params["max_samples"] == "auto"
        assert params["max_features"] == 1.0
        assert params["contamination"] == "auto"
        assert params["random_state"] is None
        assert params["contamination_from_target"] is False
        assert params["output_column"] == "if_score"
        assert params["periods_suffix"] == "_anterior"

    def test_custom_params(self):
        """Custom parameters should be set correctly."""
        transformer = IsolationForestScore(
            columns=["col1", "col2"],
            n_estimators=200,
            max_samples=256,
            max_features=0.8,
            contamination=0.1,
            random_state=42,
            contamination_from_target=True,
            output_column="anomaly_score",
            periods_suffix="_custom",
        )
        params = transformer.get_params()

        assert params["columns"] == ["col1", "col2"]
        assert params["n_estimators"] == 200
        assert params["max_samples"] == 256
        assert params["max_features"] == 0.8
        assert params["contamination"] == 0.1
        assert params["random_state"] == 42
        assert params["contamination_from_target"] is True
        assert params["output_column"] == "anomaly_score"
        assert params["periods_suffix"] == "_custom"


class TestAutoDetectColumns:
    """Test automatic column detection during fit."""

    def test_auto_detect_with_suffix(self):
        """Auto-detect columns ending with periods_suffix."""
        X = pd.DataFrame(
            {
                "1_anterior": [1.0, 2.0, 3.0],
                "12_anterior": [4.0, 5.0, 6.0],
                "other_col": ["a", "b", "c"],  # Not numeric
                "another": [7.0, 8.0, 9.0],  # Numeric but no suffix
            }
        )

        transformer = IsolationForestScore(periods_suffix="_anterior")
        transformer.fit(X)

        # Should select only numeric columns with the suffix
        assert set(transformer.selected_columns_) == {"1_anterior", "12_anterior"}

    def test_auto_detect_fallback_all_numeric(self):
        """Fallback to all numeric columns when no suffix match."""
        X = pd.DataFrame(
            {
                "col_a": [1.0, 2.0, 3.0],
                "col_b": [4.0, 5.0, 6.0],
                "category": ["a", "b", "c"],  # Not numeric
            }
        )

        transformer = IsolationForestScore(periods_suffix="_anterior")
        transformer.fit(X)

        # Should fallback to all numeric columns
        assert sorted(transformer.selected_columns_) == ["col_a", "col_b"]

    def test_explicit_columns_override(self):
        """Explicit columns should override auto-detection."""
        X = pd.DataFrame(
            {
                "1_anterior": [1.0, 2.0, 3.0],
                "12_anterior": [4.0, 5.0, 6.0],
                "other": [7.0, 8.0, 9.0],
            }
        )

        transformer = IsolationForestScore(
            columns=["1_anterior", "other"], periods_suffix="_anterior"
        )
        transformer.fit(X)

        # Should use explicit columns, ignoring suffix
        assert sorted(transformer.selected_columns_) == ["1_anterior", "other"]

    def test_missing_explicit_column_raises(self):
        """Explicit columns with missing column should raise ValueError."""
        X = pd.DataFrame(
            {
                "col1": [1.0, 2.0, 3.0],
                "col2": [4.0, 5.0, 6.0],
            }
        )

        transformer = IsolationForestScore(columns=["col1", "col_missing"])

        with pytest.raises(ValueError) as exc_info:
            transformer.fit(X)

        assert "col_missing" in str(exc_info.value)


class TestContaminationFromTarget:
    """Test contamination parameter derivation from target."""

    def test_contamination_from_y_mean(self):
        """Derive contamination from y.mean() when enabled."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        y = pd.Series([0, 0, 0, 1, 1])  # 40% positive

        transformer = IsolationForestScore(
            contamination_from_target=True,
            contamination="auto",  # Should be overridden
        )
        transformer.fit(X, y)

        # contamination_ should be set to y.mean()
        assert transformer.contamination_ == pytest.approx(0.4)

    def test_contamination_warns_when_y_none(self):
        """Warn when contamination_from_target=True but y is None."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )

        transformer = IsolationForestScore(
            contamination_from_target=True,
            contamination=0.1,
        )

        with pytest.warns(UserWarning, match="contamination_from_target"):
            transformer.fit(X, y=None)

        # Should fallback to constructor param
        assert transformer.contamination_ == 0.1

    def test_explicit_contamination(self):
        """Use explicit contamination when contamination_from_target=False."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )
        y = pd.Series([0, 0, 0, 1, 1])

        transformer = IsolationForestScore(
            contamination_from_target=False,
            contamination=0.15,
        )
        transformer.fit(X, y)

        # Should use constructor param, not y.mean()
        assert transformer.contamination_ == 0.15


class TestNaNImputation:
    """Test NaN handling during fit and transform."""

    def test_nan_in_training_data(self):
        """NaN in training data should be imputed with medians."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, np.nan, 4.0, 5.0],  # median = 3.0
            }
        )

        transformer = IsolationForestScore()
        transformer.fit(X)

        # Should store median
        assert transformer.train_medians_["col"] == 3.0
        # Should be fitted
        assert transformer.is_fitted_ is True

    def test_nan_in_transform_data(self):
        """NaN in transform data should be imputed with stored medians."""
        X_train = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],  # median = 3.0
            }
        )
        X_new = pd.DataFrame(
            {
                "col": [10.0, np.nan, 30.0],  # NaN should become 3.0
            }
        )

        transformer = IsolationForestScore()
        transformer.fit(X_train)

        # Should not raise, should use stored median
        result = transformer.transform(X_new)
        assert "if_score" in result.columns

    def test_all_nan_column_raises_error(self):
        """All-NaN column should raise ValueError during fit."""
        X = pd.DataFrame(
            {
                "col": [np.nan, np.nan, np.nan],
            }
        )

        transformer = IsolationForestScore()
        # All-NaN columns cannot be used (sklearn requires valid data)
        with pytest.raises(ValueError, match="NaN"):
            transformer.fit(X)


class TestFitTransform:
    """Test end-to-end fit_transform pipeline."""

    def test_fit_transform_returns_dataframe_with_score(self):
        """fit_transform should return DataFrame with if_score column."""
        X = pd.DataFrame(
            {
                "1_anterior": [1.0, 2.0, 3.0, 4.0, 5.0],
                "2_anterior": [5.0, 4.0, 3.0, 2.0, 1.0],
            }
        )

        transformer = IsolationForestScore(random_state=42)
        result = transformer.fit_transform(X)

        # Should return DataFrame
        assert isinstance(result, pd.DataFrame)
        # Should have if_score column
        assert "if_score" in result.columns

    def test_fit_transform_preserves_original(self):
        """fit_transform should preserve original columns."""
        X = pd.DataFrame(
            {
                "1_anterior": [1.0, 2.0, 3.0, 4.0, 5.0],
                "2_anterior": [5.0, 4.0, 3.0, 2.0, 1.0],
                "other": ["a", "b", "c", "d", "e"],
            }
        )

        transformer = IsolationForestScore(random_state=42)
        result = transformer.fit_transform(X)

        # Original columns should be preserved
        assert "1_anterior" in result.columns
        assert "2_anterior" in result.columns
        assert "other" in result.columns
        # Score column should be added
        assert "if_score" in result.columns


class TestScoreSignInversion:
    """Test that scores are inverted (higher = more anomalous)."""

    def test_higher_score_more_anomalous(self):
        """Score should be inverted so higher = more anomalous."""
        # Create data where one point is clearly anomalous
        X = pd.DataFrame(
            {
                "col": [1.0, 1.1, 1.2, 1.1, 100.0],  # 100.0 is the anomaly
            }
        )

        transformer = IsolationForestScore(random_state=42)
        result = transformer.fit_transform(X)

        # The anomalous point (last one) should have the highest score
        assert result["if_score"].iloc[-1] == result["if_score"].max()


class TestOutputColumnNaming:
    """Test output column naming and collision handling."""

    def test_custom_output_column_name(self):
        """Custom output_column name should be used."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],
            }
        )

        transformer = IsolationForestScore(output_column="custom_score", random_state=42)
        result = transformer.fit_transform(X)

        assert "custom_score" in result.columns
        assert "if_score" not in result.columns

    def test_column_collision_warns(self):
        """Warn when output column already exists in X."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0, 4.0, 5.0],
                "if_score": [0.1, 0.2, 0.3, 0.4, 0.5],  # Already exists
            }
        )

        transformer = IsolationForestScore(random_state=42)
        transformer.fit(X)

        # Should warn about collision
        with pytest.warns(UserWarning, match="if_score"):
            transformer.transform(X)


class TestUnfittedError:
    """Test that transform raises error when not fitted."""

    def test_transform_before_fit_raises(self):
        """Transform before fit should raise NotFittedError."""
        X = pd.DataFrame(
            {
                "col": [1.0, 2.0, 3.0],
            }
        )

        transformer = IsolationForestScore()

        with pytest.raises(NotFittedError):
            transformer.transform(X)


class TestMissingColumnsError:
    """Test error handling for missing columns."""

    def test_explicit_missing_column(self):
        """Explicit columns with non-existent column should raise ValueError."""
        X = pd.DataFrame(
            {
                "col1": [1.0, 2.0, 3.0],
            }
        )

        transformer = IsolationForestScore(columns=["col1", "missing"])

        with pytest.raises(ValueError):
            transformer.fit(X)


class TestYAMLIntegration:
    """Test integration with YAML configuration system."""

    def test_build_transformer_from_config_if_score(self):
        """if_score should resolve through _build_transformer_from_config."""
        from energizados.feature_engineering.default import (
            _build_transformer_from_config,
        )

        transformer = _build_transformer_from_config("if_score", {"n_estimators": 200}, None)

        # Should return IsolationForestScore instance
        assert isinstance(transformer, IsolationForestScore)
        # Should have custom param applied
        assert transformer.get_params()["n_estimators"] == 200
        # Other params should be defaults
        assert transformer.get_params()["output_column"] == "if_score"

    def test_unknown_transformer_raises(self):
        """Unknown transformer name should raise ValueError."""
        from energizados.feature_engineering.default import (
            _build_transformer_from_config,
        )

        with pytest.raises(ValueError) as exc_info:
            _build_transformer_from_config("unknown_transformer", {}, None)

        # Should mention available options including if_score
        assert "if_score" in str(exc_info.value)
