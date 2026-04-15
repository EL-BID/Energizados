"""
Unit tests for DefaultFeatureEngineering.

Tests for the Feature Engineering that combines preprocessing
and feature selection with per-column configuration.
"""

import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from energizados.feature_engineering.default import (
    _build_global_transformers_pipeline,
    _build_transformer_from_config,
    get_preprocesor,
)
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    ExtraVars,
    TeEncoder,
    ToDummy,
    TsfelVars,
)


# Custom transformer for testing
class CustomTestTransformer:
    """Custom test transformer for testing purposes."""

    def __init__(self, multiplier=1.0):
        """Initialize the transformer.

        Args:
            multiplier: Value to multiply input by during transform.
        """
        self.multiplier = multiplier

    def fit(self, X, y=None):
        """Fit the transformer (no-op).

        Args:
            X: Input features.
            y: Target values (optional).

        Returns:
            self: Returns the instance.
        """
        self.n_features_in_ = X.shape[1] if hasattr(X, "shape") else 1
        return self

    def transform(self, X):
        """Transform the input by multiplying.

        Args:
            X: Input features.

        Returns:
            Transformed features.
        """
        return X * self.multiplier

    def fit_transform(self, X, y=None):
        """Fit and transform in one step.

        Args:
            X: Input features.
            y: Target values (optional).

        Returns:
            Transformed features.
        """
        self.fit(X, y)
        return self.transform(X)

    def get_feature_names_out(self, input_features=None):
        """Return feature names for output features.

        Args:
            input_features: Input feature names.

        Returns:
            Output feature names.
        """
        if input_features is None:
            input_features = [f"x{i}" for i in range(self.n_features_in_)]
        return input_features

    def set_output(self, transform="default"):
        """Set output container for sklearn compatibility.

        Args:
            transform: Transform type.

        Returns:
            self: Returns the instance.
        """
        return self


class TestBuildTransformerFromConfig:
    """Tests for _build_transformer_from_config."""

    def test_cardinality_reducer(self):
        """Verify the creation of CardinalityReducer."""
        transformer = _build_transformer_from_config(
            "cardinality_reducer", {"threshold": 0.01}, "test_col"
        )
        assert isinstance(transformer, CardinalityReducer)
        assert transformer.threshold == 0.01

    def test_cardinality_reducer_default_params(self):
        """Verify that CardinalityReducer uses default parameters."""
        transformer = _build_transformer_from_config("cardinality_reducer", None, "test_col")
        assert isinstance(transformer, CardinalityReducer)
        assert transformer.threshold == 0.001

    def test_to_dummy(self):
        """Verify the creation of ToDummy."""
        transformer = _build_transformer_from_config("to_dummy", {}, "test_col")
        assert isinstance(transformer, ToDummy)
        assert transformer.cols == ["test_col"]

    def test_target_encoding(self):
        """Verify the creation of TeEncoder."""
        transformer = _build_transformer_from_config("target_encoding", {"w": 15}, "test_col")
        assert isinstance(transformer, TeEncoder)
        assert transformer.w == 15
        assert transformer.cols == ["test_col"]

    def test_target_encoding_default_params(self):
        """Verify that TeEncoder uses default parameters."""
        transformer = _build_transformer_from_config("target_encoding", None, "test_col")
        assert isinstance(transformer, TeEncoder)
        assert transformer.w == 20

    def test_ordinal_encoding(self):
        """Verify the creation of OrdinalEncoder."""
        transformer = _build_transformer_from_config("ordinal_encoding", {}, "test_col")
        assert transformer.__class__.__name__ == "OrdinalEncoder"

    def test_unknown_transformer_raises_error(self):
        """Verify that an unknown transformer raises error."""
        with pytest.raises(ValueError, match="Unknown transformer"):
            _build_transformer_from_config("unknown_transformer", {}, "test_col")

    def test_tsfel_vars(self):
        """Verify the creation of TsfelVars."""
        transformer = _build_transformer_from_config("tsfel_vars", {"num_periodos": 6}, None)
        assert isinstance(transformer, TsfelVars)
        assert transformer.num_periodos == 6

    def test_tsfel_vars_default_params(self):
        """Verify that TsfelVars uses default parameters."""
        transformer = _build_transformer_from_config("tsfel_vars", None, None)
        assert isinstance(transformer, TsfelVars)
        assert transformer.num_periodos == 12

    def test_extra_vars(self):
        """Verify the creation of ExtraVars."""
        transformer = _build_transformer_from_config("extra_vars", {"num_periodos": 3}, None)
        assert isinstance(transformer, ExtraVars)
        assert transformer.num_periodos == 3

    def test_extra_vars_default_params(self):
        """Verify that ExtraVars uses default parameters."""
        transformer = _build_transformer_from_config("extra_vars", None, None)
        assert isinstance(transformer, ExtraVars)
        assert transformer.num_periodos == 3


class TestGetPreprocesorColumnsConfig:
    """Tests for get_preprocesor with new 'columns' configuration."""

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing.

        Returns:
            dict: A sample preprocessing configuration.
        """
        return {
            "columns": {
                "zona": [{"ordinal_encoding": {}}],
                "actividad": [
                    {"cardinality_reducer": {"threshold": 0.001}},
                    {"to_dummy": {}},
                ],
            }
        }

    def test_returns_column_transformer(self, sample_config):
        """Verify that it returns a Pipeline with column_transformer."""
        preprocessor = get_preprocesor(sample_config)
        assert isinstance(preprocessor, Pipeline)
        # First step must be column_transformer
        assert preprocessor.steps[0][0] == "column_transformer"

    def test_single_column_single_transform(self):
        """Verify configuration with one column and one transformation."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Get ColumnTransformer from Pipeline
        ct = preprocessor.named_steps["column_transformer"]
        assert len(ct.transformers) == 1

    def test_multiple_columns(self):
        """Verify configuration with multiple columns."""
        config = {
            "columns": {
                "zona": [{"ordinal_encoding": {}}],
                "nivel_tension": [{"ordinal_encoding": {}}],
            }
        }
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        assert len(ct.transformers) == 2

    def test_pipeline_sequence_for_column(self):
        """Verify that a sequential Pipeline is created per column."""
        config = {
            "columns": {
                "actividad": [
                    {"cardinality_reducer": {"threshold": 0.001}},
                    {"to_dummy": {}},
                ]
            }
        }
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        transformer_name, transformer, cols = ct.transformers[0]
        assert transformer_name == "actividad_pipeline"
        assert cols == ["actividad"]
        # Verify that it's a Pipeline
        assert hasattr(transformer, "steps")
        assert len(transformer.steps) == 2

    def test_passthrough_for_unmentioned_columns(self):
        """Verify that unmentioned columns use passthrough."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        assert ct.remainder == "passthrough"

    def test_empty_columns_config_raises_error(self):
        """Verify that empty columns config raises error."""
        config = {"columns": {}}
        with pytest.raises(ValueError, match="The 'columns' config cannot be empty"):
            get_preprocesor(config)


class TestGetPreprocesorLegacy:
    """Tests to verify that legacy configs raise error (deprecated)."""

    def test_legacy_preprocessor_num_4_raises_error(self):
        """Verify that preprocessor_num=4 raises error (deprecated)."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="'columns' is required"):
            get_preprocesor(config)

    def test_legacy_with_categorical_features_raises_error(self):
        """Verify that legacy with categorical_features raises error (deprecated)."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "nivel_tension", "material_instalacion"],
        }
        with pytest.raises(ValueError, match="'columns' is required"):
            get_preprocesor(config)

    def test_legacy_default_preprocessor_num_raises_error(self):
        """Verify that without columns raises error (invalid config)."""
        config = {"categorical_features": ["zona"]}
        with pytest.raises(ValueError, match="'columns' is required"):
            get_preprocesor(config)


class TestGetPreprocesorPriority:
    """Tests to verify that 'columns' takes priority over legacy."""

    def test_columns_takes_priority_over_legacy(self):
        """Verify that 'columns' takes priority over preprocessor_num."""
        # If columns is present, it's used and legacy is ignored
        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "preprocessor_num": 4,
            "categorical_features": ["actividad", "tipo_tarifa"],
        }
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        # Should only have transformer for 'zona'
        assert len(ct.transformers) == 1
        _, _, cols = ct.transformers[0]
        assert cols == ["zona"]

    def test_legacy_params_alone_raise_error(self):
        """Verify that legacy params without columns raise error."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="'columns' is required"):
            get_preprocesor(config)


class TestBuildGlobalTransformersPipeline:
    """Tests for _build_global_transformers_pipeline."""

    def test_returns_none_for_empty_config(self):
        """Verify that it returns None for empty config."""
        pipeline = _build_global_transformers_pipeline([])
        assert pipeline is None

    def test_returns_none_for_none_config(self):
        """Verify that it returns None for None config."""
        pipeline = _build_global_transformers_pipeline(None)
        assert pipeline is None

    def test_builds_pipeline_with_single_transformer(self):
        """Verify that it builds a Pipeline with one transformer."""
        config = [{"tsfel_vars": {"num_periodos": 6}}]
        pipeline = _build_global_transformers_pipeline(config)
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0][0] == "global_tsfel_vars_0"

    def test_builds_pipeline_with_multiple_transformers(self):
        """Verify that it builds a Pipeline with multiple transformers."""
        config = [
            {"tsfel_vars": {"num_periodos": 12}},
            {"extra_vars": {"num_periodos": 3}},
            {"extra_vars": {"num_periodos": 6}},
        ]
        pipeline = _build_global_transformers_pipeline(config)
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 3

    def test_transformer_instances(self):
        """Verify that transformer instances are correct."""
        config = [
            {"tsfel_vars": {"num_periodos": 12}},
            {"extra_vars": {"num_periodos": 3}},
        ]
        pipeline = _build_global_transformers_pipeline(config)
        _, tsfel_transformer = pipeline.steps[0]
        _, extra_transformer = pipeline.steps[1]
        assert isinstance(tsfel_transformer, TsfelVars)
        assert isinstance(extra_transformer, ExtraVars)
        assert tsfel_transformer.num_periodos == 12
        assert extra_transformer.num_periodos == 3

    def test_custom_class_global_transformer(self):
        """Verify the use of custom_class in global transformers."""
        config = [
            {
                "custom_class": "tests.test_default_feature_engineering.CustomTestTransformer",
                "params": {"multiplier": 2.0},
            }
        ]
        pipeline = _build_global_transformers_pipeline(config)
        _, transformer = pipeline.steps[0]
        assert isinstance(transformer, CustomTestTransformer)
        assert transformer.multiplier == 2.0


class TestGetPreprocesorWithGlobalTransformers:
    """Tests for get_preprocesor with global_transformers."""

    def test_returns_pipeline_with_global_transformers(self):
        """Verify that it returns a Pipeline with global_transformers."""
        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "global_transformers": [{"extra_vars": {"num_periodos": 3}}],
        }
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Verify that it has both steps
        step_names = [name for name, _ in preprocessor.steps]
        assert "column_transformer" in step_names
        assert "global_transformers" in step_names

    def test_global_transformers_step_is_pipeline(self):
        """Verify that the global_transformers step is a Pipeline."""
        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "global_transformers": [
                {"tsfel_vars": {"num_periodos": 12}},
                {"extra_vars": {"num_periodos": 3}},
            ],
        }
        preprocessor = get_preprocesor(config)
        global_transformers = preprocessor.named_steps["global_transformers"]
        assert isinstance(global_transformers, Pipeline)
        assert len(global_transformers.steps) == 2

    def test_without_global_transformers(self):
        """Verify that it works without global_transformers."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Should only have column_transformer
        assert len(preprocessor.steps) == 1
        assert preprocessor.steps[0][0] == "column_transformer"

    def test_fit_transform_with_global_transformers(self, sample_data):
        """Verify fit_transform with global_transformers."""
        X, y = sample_data
        # Add consumption columns so extra_vars works
        for i in range(12, 0, -1):
            X[f"{i}_anterior"] = X["consumo_1"]

        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "global_transformers": [{"extra_vars": {"num_periodos": 3}}],
        }
        preprocessor = get_preprocesor(config)
        X_transformed = preprocessor.fit_transform(X, y)
        assert X_transformed.shape[0] == X.shape[0]
        # ExtraVars adds new columns
        assert X_transformed.shape[1] > X.shape[1]


class TestIntegrationWithSampleData:
    """Integration tests with sample data."""

    @pytest.fixture
    def sample_data(self):
        """Sample data similar to the real dataset.

        Returns:
            tuple: A tuple containing:
                - X (pd.DataFrame): Feature DataFrame.
                - y (pd.Series): Target Series.
        """
        X = pd.DataFrame(
            {
                "zona": ["Norte", "Sur", "Norte", "Este", "Oeste"] * 4,
                "actividad": ["Comercio", "Industria", "Residencial", "Comercio", "Industria"] * 4,
                "consumo_1": [100, 150, 80, 120, 200] * 4,
                "consumo_2": [110, 160, 85, 125, 210] * 4,
            }
        )
        y = pd.Series([0, 1, 0, 1, 1] * 4)
        return X, y

    def test_fit_transform_with_columns_config(self, sample_data):
        """Verify fit_transform with new configuration."""
        X, y = sample_data
        config = {
            "columns": {
                "zona": [{"ordinal_encoding": {}}],
                "actividad": [
                    {"cardinality_reducer": {"threshold": 0.1}},
                    {"to_dummy": {}},
                ],
            }
        }
        preprocessor = get_preprocesor(config)
        X_transformed = preprocessor.fit_transform(X, y)
        assert X_transformed.shape[0] == X.shape[0]  # Same number of rows

    def test_fit_transform_with_legacy_config_raises_error(self, sample_data):
        """Verify that legacy config raises error."""
        X, y = sample_data
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="'columns' is required"):
            get_preprocesor(config)


# Module-level fixture for use in multiple test classes
@pytest.fixture
def sample_data():
    """Sample data similar to the real dataset (module level).

    Returns:
        tuple: A tuple containing:
            - X (pd.DataFrame): Feature DataFrame.
            - y (pd.Series): Target Series.
    """
    X = pd.DataFrame(
        {
            "zona": ["Norte", "Sur", "Norte", "Este", "Oeste"] * 4,
            "actividad": ["Comercio", "Industria", "Residencial", "Comercio", "Industria"] * 4,
            "consumo_1": [100, 150, 80, 120, 200] * 4,
            "consumo_2": [110, 160, 85, 125, 210] * 4,
        }
    )
    y = pd.Series([0, 1, 0, 1, 1] * 4)
    return X, y


class TestCustomClassPerColumn:
    """Tests for custom_class per column (flat format)."""

    def test_build_transformer_with_custom_class(self):
        """Verify the creation of transformer with custom_class."""
        # Use the full module path of the test
        transformer = _build_transformer_from_config(
            "custom_class",
            {"multiplier": 2.0},
            "test_col",
            custom_class="tests.test_default_feature_engineering.CustomTestTransformer",
        )
        assert isinstance(transformer, CustomTestTransformer)
        assert transformer.multiplier == 2.0

    def test_custom_class_without_path_raises_error(self):
        """Verify that custom_class without path raises error."""
        with pytest.raises(ValueError, match="Must specify 'custom_class'"):
            _build_transformer_from_config("custom_class", {}, "test_col")

    def test_get_preprocesor_with_custom_class_per_column(self):
        """Verify get_preprocesor with custom_class per column."""
        config = {
            "columns": {
                "zona": [
                    {
                        "custom_class": "tests.test_default_feature_engineering.CustomTestTransformer",
                        "params": {"multiplier": 1.5},
                    }
                ]
            }
        }
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        ct = preprocessor.named_steps["column_transformer"]
        assert len(ct.transformers) == 1

    def test_mix_builtin_and_custom_in_same_column(self):
        """Verify mixing built-in and custom transformers in same column."""
        config = {
            "columns": {
                "actividad": [
                    {"cardinality_reducer": {"threshold": 0.1}},
                    {
                        "custom_class": "tests.test_default_feature_engineering.CustomTestTransformer",
                        "params": {"multiplier": 1.0},
                    },
                ]
            }
        }
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        transformer_name, transformer, cols = ct.transformers[0]
        assert transformer_name == "actividad_pipeline"
        assert cols == ["actividad"]
        # Must have 2 steps in the pipeline
        assert len(transformer.steps) == 2

    def test_custom_class_integration_with_fit_transform(self, sample_data):
        """Verify integration of custom_class with fit_transform."""
        X, y = sample_data
        config = {
            "columns": {
                "zona": [{"ordinal_encoding": {}}],
                "consumo_1": [
                    {
                        "custom_class": "tests.test_default_feature_engineering.CustomTestTransformer",
                        "params": {"multiplier": 2.0},
                    }
                ],
            }
        }
        preprocessor = get_preprocesor(config)
        X_transformed = preprocessor.fit_transform(X, y)
        assert X_transformed.shape[0] == X.shape[0]


class TestPreprocessingEnabledFlag:
    """Tests for the enabled flag in preprocessing."""

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing.

        Returns:
            tuple: A tuple containing:
                - X (pd.DataFrame): Feature DataFrame.
                - y (pd.Series): Target Series.
        """
        X = pd.DataFrame(
            {
                "zona": ["Norte", "Sur", "Norte", "Este", "Oeste"] * 4,
                "actividad": ["Comercio", "Industria", "Residencial", "Comercio", "Industria"] * 4,
                "consumo_1": [100, 150, 80, 120, 200] * 4,
                "consumo_2": [110, 160, 85, 125, 210] * 4,
            }
        )
        y = pd.Series([0, 1, 0, 1, 1] * 4)
        return X, y

    def test_preprocessing_enabled_true_applies_preprocessing(self, sample_data):
        """Verify that preprocessing.enabled=true applies preprocessing."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        config = {
            "preprocessing": {"enabled": True, "columns": {"zona": [{"ordinal_encoding": {}}]}},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        X_transformed = fe.transform(X)  # noqa: F841
        # Preprocessing must have modified columns
        assert fe.preprocessor is not None

    def test_preprocessing_enabled_false_skips_preprocessing(self, sample_data):
        """Verify that preprocessing.enabled=false skips preprocessing."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        config = {
            "preprocessing": {"enabled": False},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        X_transformed = fe.transform(X)
        # Preprocessor must be None when preprocessing is disabled
        assert fe.preprocessor is None
        # Data must be equal (no transformation)
        pd.testing.assert_frame_equal(X_transformed, X)

    def test_preprocessing_default_is_enabled(self, sample_data):
        """Verify that the default for enabled is True."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        # Without specifying enabled (must default to True)
        config = {
            "preprocessing": {"columns": {"zona": [{"ordinal_encoding": {}}]}},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        # Preprocessing must have been applied
        assert fe.preprocessor is not None
