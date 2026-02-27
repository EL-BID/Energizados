"""
Unit tests for DefaultFeatureEngineering.

Pruebas para el Feature Engineering que combina preprocessing
y feature selection con configuración por columna.
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


# Custom transformer para testing
class CustomTestTransformer:
    """Transformer custom de prueba para testing."""

    def __init__(self, multiplier=1.0):
        self.multiplier = multiplier

    def fit(self, X, y=None):
        self.n_features_in_ = X.shape[1] if hasattr(X, "shape") else 1
        return self

    def transform(self, X):
        return X * self.multiplier

    def fit_transform(self, X, y=None):
        self.fit(X, y)
        return self.transform(X)

    def get_feature_names_out(self, input_features=None):
        """Return feature names for output features."""
        if input_features is None:
            input_features = [f"x{i}" for i in range(self.n_features_in_)]
        return input_features

    def set_output(self, transform="default"):
        """Set output container for sklearn compatibility."""
        return self


class TestBuildTransformerFromConfig:
    """Tests para _build_transformer_from_config."""

    def test_cardinality_reducer(self):
        """Verifica la creación de CardinalityReducer."""
        transformer = _build_transformer_from_config("cardinality_reducer", {"threshold": 0.01}, "test_col")
        assert isinstance(transformer, CardinalityReducer)
        assert transformer.threshold == 0.01

    def test_cardinality_reducer_default_params(self):
        """Verifica que CardinalityReducer use parámetros por defecto."""
        transformer = _build_transformer_from_config("cardinality_reducer", None, "test_col")
        assert isinstance(transformer, CardinalityReducer)
        assert transformer.threshold == 0.001

    def test_to_dummy(self):
        """Verifica la creación de ToDummy."""
        transformer = _build_transformer_from_config("to_dummy", {}, "test_col")
        assert isinstance(transformer, ToDummy)
        assert transformer.cols == ["test_col"]

    def test_target_encoding(self):
        """Verifica la creación de TeEncoder."""
        transformer = _build_transformer_from_config("target_encoding", {"w": 15}, "test_col")
        assert isinstance(transformer, TeEncoder)
        assert transformer.w == 15
        assert transformer.cols == ["test_col"]

    def test_target_encoding_default_params(self):
        """Verifica que TeEncoder use parámetros por defecto."""
        transformer = _build_transformer_from_config("target_encoding", None, "test_col")
        assert isinstance(transformer, TeEncoder)
        assert transformer.w == 20

    def test_ordinal_encoding(self):
        """Verifica la creación de OrdinalEncoder."""
        transformer = _build_transformer_from_config("ordinal_encoding", {}, "test_col")
        assert transformer.__class__.__name__ == "OrdinalEncoder"

    def test_unknown_transformer_raises_error(self):
        """Verifica que un transformer desconocido lance error."""
        with pytest.raises(ValueError, match="Transformer desconocido"):
            _build_transformer_from_config("unknown_transformer", {}, "test_col")

    def test_tsfel_vars(self):
        """Verifica la creación de TsfelVars."""
        transformer = _build_transformer_from_config("tsfel_vars", {"num_periodos": 6}, None)
        assert isinstance(transformer, TsfelVars)
        assert transformer.num_periodos == 6

    def test_tsfel_vars_default_params(self):
        """Verifica que TsfelVars use parámetros por defecto."""
        transformer = _build_transformer_from_config("tsfel_vars", None, None)
        assert isinstance(transformer, TsfelVars)
        assert transformer.num_periodos == 12

    def test_extra_vars(self):
        """Verifica la creación de ExtraVars."""
        transformer = _build_transformer_from_config("extra_vars", {"num_periodos": 3}, None)
        assert isinstance(transformer, ExtraVars)
        assert transformer.num_periodos == 3

    def test_extra_vars_default_params(self):
        """Verifica que ExtraVars use parámetros por defecto."""
        transformer = _build_transformer_from_config("extra_vars", None, None)
        assert isinstance(transformer, ExtraVars)
        assert transformer.num_periodos == 3


class TestGetPreprocesorColumnsConfig:
    """Tests para get_preprocesor con nueva configuración 'columns'."""

    @pytest.fixture
    def sample_config(self):
        """Configuración de ejemplo."""
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
        """Verifica que retorne un Pipeline con column_transformer."""
        preprocessor = get_preprocesor(sample_config)
        assert isinstance(preprocessor, Pipeline)
        # El primer paso debe ser column_transformer
        assert preprocessor.steps[0][0] == "column_transformer"

    def test_single_column_single_transform(self):
        """Verifica configuración con una columna y una transformación."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Obtener el ColumnTransformer del Pipeline
        ct = preprocessor.named_steps["column_transformer"]
        assert len(ct.transformers) == 1

    def test_multiple_columns(self):
        """Verifica configuración con múltiples columnas."""
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
        """Verifica que se cree un Pipeline secuencial por columna."""
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
        # Verificar que es un Pipeline
        assert hasattr(transformer, "steps")
        assert len(transformer.steps) == 2

    def test_passthrough_for_unmentioned_columns(self):
        """Verifica que columnas no mencionadas usen passthrough."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        assert ct.remainder == "passthrough"

    def test_empty_columns_config_raises_error(self):
        """Verifica que configuración vacía de columns lance error."""
        config = {"columns": {}}
        with pytest.raises(ValueError, match="El config 'columns' no puede estar vacío"):
            get_preprocesor(config)


class TestGetPreprocesorLegacy:
    """Tests para verificar que configs legacy lanzan error (deprecados)."""

    def test_legacy_preprocessor_num_4_raises_error(self):
        """Verifica que preprocessor_num=4 lance error (deprecado)."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)

    def test_legacy_with_categorical_features_raises_error(self):
        """Verifica que legacy con categorical_features lance error (deprecado)."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "nivel_tension", "material_instalacion"],
        }
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)

    def test_legacy_default_preprocessor_num_raises_error(self):
        """Verifica que sin columns lance error (config inválida)."""
        config = {"categorical_features": ["zona"]}
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)


class TestGetPreprocesorPriority:
    """Tests para verificar que 'columns' tiene prioridad sobre legacy."""

    def test_columns_takes_priority_over_legacy(self):
        """Verifica que 'columns' tenga prioridad sobre preprocessor_num."""
        # Si columns está presente, se usa y se ignora legacy
        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "preprocessor_num": 4,
            "categorical_features": ["actividad", "tipo_tarifa"],
        }
        preprocessor = get_preprocesor(config)
        ct = preprocessor.named_steps["column_transformer"]
        # Solo debería tener transformer para 'zona'
        assert len(ct.transformers) == 1
        _, _, cols = ct.transformers[0]
        assert cols == ["zona"]

    def test_legacy_params_alone_raise_error(self):
        """Verifica que params legacy sin columns lancen error."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)


class TestBuildGlobalTransformersPipeline:
    """Tests para _build_global_transformers_pipeline."""

    def test_returns_none_for_empty_config(self):
        """Verifica que retorne None para configuración vacía."""
        pipeline = _build_global_transformers_pipeline([])
        assert pipeline is None

    def test_returns_none_for_none_config(self):
        """Verifica que retorne None para configuración None."""
        pipeline = _build_global_transformers_pipeline(None)
        assert pipeline is None

    def test_builds_pipeline_with_single_transformer(self):
        """Verifica que construya un Pipeline con un transformer."""
        config = [{"tsfel_vars": {"num_periodos": 6}}]
        pipeline = _build_global_transformers_pipeline(config)
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0][0] == "global_tsfel_vars_0"

    def test_builds_pipeline_with_multiple_transformers(self):
        """Verifica que construya un Pipeline con múltiples transformers."""
        config = [
            {"tsfel_vars": {"num_periodos": 12}},
            {"extra_vars": {"num_periodos": 3}},
            {"extra_vars": {"num_periodos": 6}},
        ]
        pipeline = _build_global_transformers_pipeline(config)
        assert isinstance(pipeline, Pipeline)
        assert len(pipeline.steps) == 3

    def test_transformer_instances(self):
        """Verifica que las instancias de los transformers sean correctas."""
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
        """Verifica el uso de custom_class en global transformers."""
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
    """Tests para get_preprocesor con global_transformers."""

    def test_returns_pipeline_with_global_transformers(self):
        """Verifica que retorne un Pipeline con global_transformers."""
        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "global_transformers": [{"extra_vars": {"num_periodos": 3}}],
        }
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Verificar que tiene ambos pasos
        step_names = [name for name, _ in preprocessor.steps]
        assert "column_transformer" in step_names
        assert "global_transformers" in step_names

    def test_global_transformers_step_is_pipeline(self):
        """Verifica que el paso global_transformers sea un Pipeline."""
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
        """Verifica que funcione sin global_transformers."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, Pipeline)
        # Solo debe tener column_transformer
        assert len(preprocessor.steps) == 1
        assert preprocessor.steps[0][0] == "column_transformer"

    def test_fit_transform_with_global_transformers(self, sample_data):
        """Verifica fit_transform con global_transformers."""
        X, y = sample_data
        # Agregar columnas de consumo para que extra_vars funcione
        for i in range(12, 0, -1):
            X[f"{i}_anterior"] = X["consumo_1"]

        config = {
            "columns": {"zona": [{"ordinal_encoding": {}}]},
            "global_transformers": [{"extra_vars": {"num_periodos": 3}}],
        }
        preprocessor = get_preprocesor(config)
        X_transformed = preprocessor.fit_transform(X, y)
        assert X_transformed.shape[0] == X.shape[0]
        # ExtraVars agrega nuevas columnas
        assert X_transformed.shape[1] > X.shape[1]


class TestIntegrationWithSampleData:
    """Tests de integración con datos de ejemplo."""

    @pytest.fixture
    def sample_data(self):
        """Datos de ejemplo similares al dataset real."""
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


# Module-level fixture for use in multiple test classes
@pytest.fixture
def sample_data():
    """Datos de ejemplo similares al dataset real (module level)."""
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
        """Verifica fit_transform con nueva configuración."""
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
        assert X_transformed.shape[0] == X.shape[0]  # Mismo número de filas

    def test_fit_transform_with_legacy_config_raises_error(self, sample_data):
        """Verifica que configuración legacy lance error."""
        X, y = sample_data
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)


class TestCustomClassPerColumn:
    """Tests para custom_class por columna (formato plano)."""

    def test_build_transformer_with_custom_class(self):
        """Verifica la creación de transformer con custom_class."""
        # Usar el path completo del módulo de测试
        transformer = _build_transformer_from_config(
            "custom_class",
            {"multiplier": 2.0},
            "test_col",
            custom_class="tests.test_default_feature_engineering.CustomTestTransformer",
        )
        assert isinstance(transformer, CustomTestTransformer)
        assert transformer.multiplier == 2.0

    def test_custom_class_without_path_raises_error(self):
        """Verifica que custom_class sin path lance error."""
        with pytest.raises(ValueError, match="Se debe especificar 'custom_class'"):
            _build_transformer_from_config("custom_class", {}, "test_col")

    def test_get_preprocesor_with_custom_class_per_column(self):
        """Verifica get_preprocesor con custom_class por columna."""
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
        """Verifica mezcla de transformers built-in y custom en misma columna."""
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
        # Debe tener 2 pasos en el pipeline
        assert len(transformer.steps) == 2

    def test_custom_class_integration_with_fit_transform(self, sample_data):
        """Verifica integración de custom_class con fit_transform."""
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
    """Tests para el flag enabled en preprocessing."""

    @pytest.fixture
    def sample_data(self):
        """Datos de ejemplo."""
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
        """Verifica que preprocessing.enabled=true aplique preprocessing."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        config = {
            "preprocessing": {"enabled": True, "columns": {"zona": [{"ordinal_encoding": {}}]}},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        X_transformed = fe.transform(X)  # noqa: F841
        # Preprocessing debe haber modificado las columnas
        assert fe.preprocessor is not None

    def test_preprocessing_enabled_false_skips_preprocessing(self, sample_data):
        """Verifica que preprocessing.enabled=false salte preprocessing."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        config = {
            "preprocessing": {"enabled": False},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        X_transformed = fe.transform(X)
        # Preprocessor debe ser None cuando preprocessing está deshabilitado
        assert fe.preprocessor is None
        # Los datos deben ser iguales (sin transformación)
        pd.testing.assert_frame_equal(X_transformed, X)

    def test_preprocessing_default_is_enabled(self, sample_data):
        """Verifica que el default de enabled sea True."""
        from energizados.feature_engineering.default import DefaultFeatureEngineering

        X, y = sample_data
        # Sin especificar enabled (debe default a True)
        config = {
            "preprocessing": {"columns": {"zona": [{"ordinal_encoding": {}}]}},
            "feature_selection": {"enabled": False},
        }
        fe = DefaultFeatureEngineering(config=config)
        fe.fit(X, y)
        # Preprocessing debe haberse aplicado
        assert fe.preprocessor is not None
