"""
Unit tests for DefaultFeaturePipeline.

Pruebas para el Feature Pipeline que combina preprocessing
y feature selection con configuración por columna.
"""

import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer

from energizados.feature_engineering.default import (
    _build_transformer_from_config,
    get_preprocesor,
)
from energizados.preprocessing.preprocessing import (
    CardinalityReducer,
    TeEncoder,
    ToDummy,
)


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
        """Verifica que retorne un ColumnTransformer."""
        preprocessor = get_preprocesor(sample_config)
        assert isinstance(preprocessor, ColumnTransformer)

    def test_single_column_single_transform(self):
        """Verifica configuración con una columna y una transformación."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert isinstance(preprocessor, ColumnTransformer)
        assert len(preprocessor.transformers) == 1

    def test_multiple_columns(self):
        """Verifica configuración con múltiples columnas."""
        config = {
            "columns": {
                "zona": [{"ordinal_encoding": {}}],
                "nivel_tension": [{"ordinal_encoding": {}}],
            }
        }
        preprocessor = get_preprocesor(config)
        assert len(preprocessor.transformers) == 2

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
        transformer_name, transformer, cols = preprocessor.transformers[0]
        assert transformer_name == "actividad_pipeline"
        assert cols == ["actividad"]
        # Verificar que es un Pipeline
        assert hasattr(transformer, "steps")
        assert len(transformer.steps) == 2

    def test_passthrough_for_unmentioned_columns(self):
        """Verifica que columnas no mencionadas usen passthrough."""
        config = {"columns": {"zona": [{"ordinal_encoding": {}}]}}
        preprocessor = get_preprocesor(config)
        assert preprocessor.remainder == "passthrough"

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
        # Solo debería tener transformer para 'zona'
        assert len(preprocessor.transformers) == 1
        _, _, cols = preprocessor.transformers[0]
        assert cols == ["zona"]

    def test_legacy_params_alone_raise_error(self):
        """Verifica que params legacy sin columns lancen error."""
        config = {
            "preprocessor_num": 4,
            "categorical_features": ["zona", "actividad"],
        }
        with pytest.raises(ValueError, match="Se requiere 'columns'"):
            get_preprocesor(config)


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
