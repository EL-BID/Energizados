"""
Training Step for Energizados Framework.

Paso de entrenamiento unificado que combina feature engineering
y model training para prevenir data leakage.
"""

import logging
import pickle  # nosec B403: ML model serialization (local files only)
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from energizados.core.base import PipelineStep
from energizados.feature_engineering import DefaultFeatureEngineering
from energizados.modeling.registry import ModelRegistry

logger = logging.getLogger(__name__)


class TrainingStep(PipelineStep):
    """
    Paso de entrenamiento unificado.

    Combina feature engineering y model training en un solo paso,
    asegurando que no haya data leakage (fit solo en train).

    Args:
        train_path: Ruta al dataset de train
        val_path: Ruta al dataset de validación
        test_path: Ruta al dataset de test
        target_column: Nombre de la columna target
        feature_engineering_config: Configuración del feature engineering
        model_config: Configuración del modelo
        output_dir: Directorio de salida

    Example:
        >>> training_step = TrainingStep(
        ...     feature_engineering_config={...},
        ...     model_config={...}
        ... )
        >>> result = training_step.run(context)
    """

    def __init__(
        self,
        train_path: Optional[str] = None,
        val_path: Optional[str] = None,
        test_path: Optional[str] = None,
        target_column: str = "target",
        feature_engineering_config: Optional[Dict] = None,
        model_config: Optional[Dict] = None,
        output_dir: str = "models/trained/",
        **kwargs,
    ):
        self.train_path = train_path
        self.val_path = val_path
        self.test_path = test_path
        self.target_column = target_column
        self.feature_engineering_config = feature_engineering_config or {}
        self.model_config = model_config or {}
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el entrenamiento completo."""
        # Usar paths del contexto si no se proporcionaron
        if context:
            self.train_path = self.train_path or context.get("train_path")
            self.val_path = self.val_path or context.get("val_path")
            self.test_path = self.test_path or context.get("test_path")

        if not self.train_path or not self.val_path:
            raise ValueError("Se requieren train_path y val_path")

        # 1. Cargar datos
        logger.info("\n" + "=" * 50)
        logger.info("TRAINING STEP")
        logger.info("=" * 50)

        train_df = pd.read_parquet(self.train_path)
        val_df = pd.read_parquet(self.val_path)
        test_df = pd.read_parquet(self.test_path) if self.test_path else None

        logger.info(f"Train shape: {train_df.shape}")
        logger.info(f"Val shape: {val_df.shape}")
        if test_df is not None:
            logger.info(f"Test shape: {test_df.shape}")

        # Separar features y target
        X_train = train_df.drop(columns=[self.target_column])
        y_train = train_df[self.target_column]
        X_val = val_df.drop(columns=[self.target_column])
        y_val = val_df[self.target_column]

        X_test = None
        y_test = None
        if test_df is not None:
            X_test = test_df.drop(columns=[self.target_column])
            y_test = test_df[self.target_column]  # noqa: F841 - stored for later use

        # 2. Feature Engineering: FIT SOLO EN TRAIN
        logger.info("\n" + "=" * 50)
        logger.info("FEATURE ENGINEERING")
        logger.info("=" * 50)
        logger.info("Fitting feature engineering on TRAIN data only...")

        fe_config = self.feature_engineering_config.get("preprocessing", {})
        fs_config = self.feature_engineering_config.get("feature_selection", {})

        feature_engineering = DefaultFeatureEngineering(
            preprocessing_config=fe_config,
            feature_selection_config=fs_config,
        )

        # FIT solo en train
        feature_engineering.fit(X_train, y_train)

        # TRANSFORM en train, val, test
        logger.info("Transforming train, val, test...")
        X_train_transformed = feature_engineering.transform(X_train)
        X_val_transformed = feature_engineering.transform(X_val)
        X_test_transformed = feature_engineering.transform(X_test) if X_test is not None else None

        logger.info(f"Train transformed shape: {X_train_transformed.shape}")
        logger.info(f"Val transformed shape: {X_val_transformed.shape}")
        if X_test_transformed is not None:
            logger.info(f"Test transformed shape: {X_test_transformed.shape}")

        # Guardar feature engineering
        fe_path = self.output_dir / "feature_engineering.pkl"
        with open(fe_path, "wb") as f:
            pickle.dump(feature_engineering, f)
        logger.info(f"Feature Engineering saved to: {fe_path}")

        # 3. Model Training
        logger.info("\n" + "=" * 50)
        logger.info("MODEL TRAINING")
        logger.info("=" * 50)

        model_type = self.model_config.get("type", "lightgbm")
        logger.info(f"Model type: {model_type}")

        # Crear modelo usando el registry
        model_class = ModelRegistry.get(model_type)

        # Preparar config para el modelo
        model_params = self._prepare_model_params(model_type, X_train_transformed)

        model = model_class(**model_params)

        # Fit del modelo
        model.fit(X_train_transformed, y_train, X_val=X_val_transformed, y_val=y_val)

        # Guardar modelo
        model_path = self.output_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"Model saved to: {model_path}")

        # 4. Evaluación rápida en val (para logs)
        val_proba = model.predict_proba(X_val_transformed)
        val_pred = (val_proba >= 0.5).astype(int)

        from sklearn.metrics import f1_score, roc_auc_score

        val_auc = roc_auc_score(y_val, val_proba)
        val_f1 = f1_score(y_val, val_pred)

        logger.info(f"\nValidation AUC: {val_auc:.4f}")
        logger.info(f"Validation F1:  {val_f1:.4f}")

        return {
            **context,
            "model_path": str(model_path),
            "feature_engineering_path": str(fe_path),
            "val_auc": val_auc,
            "val_f1": val_f1,
            "model": model,
            "feature_engineering": feature_engineering,
        }

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Valida que existan los paths necesarios."""
        # Verificar que se proporcionaron los paths o existen en el contexto
        train_path = self.train_path or context.get("train_path")
        val_path = self.val_path or context.get("val_path")

        if not train_path or not val_path:
            return False

        return Path(train_path).exists() and Path(val_path).exists()

    def get_required_keys(self) -> list:
        """Retorna las claves requeridas del contexto."""
        # Si no se proporcionan paths, se requieren del contexto
        if not self.train_path or not self.val_path:
            return ["train_path", "val_path"]
        return []

    def get_output_keys(self) -> list:
        """Retorna las claves que agrega al contexto."""
        return ["model_path", "feature_engineering_path", "val_auc", "val_f1", "model", "feature_engineering"]

    def _prepare_model_params(self, model_type: str, X_train: pd.DataFrame) -> Dict:
        """
        Prepara los parámetros para el modelo según su tipo.

        Args:
            model_type: Tipo de modelo
            X_train: DataFrame de entrenamiento

        Returns:
            Dict: Parámetros para el modelo
        """
        params = self.model_config.copy()

        # Para modelos que necesitan columnas específicas
        if model_type in ["lightgbm", "lgbm", "catboost", "cat"]:
            params["cols_for_model"] = X_train.columns.tolist()
            params["sampling_method"] = params.pop("sampling", {}).get("method", "under")
            params["sampling_th"] = params.pop("sampling", {}).get("threshold", 0.5)
            params["hyperparams"] = params.pop("hyperparams", {})
            params["search_hip"] = params.pop("hyperparam_search", {}).get("enabled", False)

        # Para modelos neuronales
        elif model_type in ["neural_network", "nn", "lstm"]:
            # Identificar columnas de consumo (12_anterior ... 1_anterior)
            consumption_cols = [c for c in X_train.columns if "_anterior" in c]
            feature_cols = [c for c in X_train.columns if c not in consumption_cols]

            params["features_names"] = feature_cols
            params["spents_names"] = consumption_cols
            params["sampling_method"] = params.pop("sampling", {}).get("method", "under")
            params["sampling_th"] = params.pop("sampling", {}).get("threshold", 0.5)
            params["search_hip"] = params.pop("hyperparam_search", {}).get("enabled", False)

        return params
