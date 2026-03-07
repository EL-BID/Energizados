"""
Training Step for Energizados Framework.

Unified training step that combines feature engineering
and model training to prevent data leakage.
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
    Unified training step.

    Combines feature engineering and model training in a single step,
    ensuring no data leakage (fit only on train).

    Args:
        train_path: Path to training dataset
        val_path: Path to validation dataset
        test_path: Path to test dataset
        target_column: Name of target column
        feature_engineering_config: Feature engineering configuration
        model_config: Model configuration
        output_dir: Output directory

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
        output_dir: str = "output/models/",
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
        """Execute the full training."""
        # Use paths from context if not provided
        if context:
            self.train_path = self.train_path or context.get("train_path")
            self.val_path = self.val_path or context.get("val_path")
            self.test_path = self.test_path or context.get("test_path")

        if not self.train_path or not self.val_path:
            raise ValueError("train_path and val_path are required")

        # 1. Load data
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

        # Separate features and target
        X_train = train_df.drop(columns=[self.target_column])
        y_train = train_df[self.target_column]
        X_val = val_df.drop(columns=[self.target_column])
        y_val = val_df[self.target_column]

        X_test = None
        y_test = None
        if test_df is not None:
            X_test = test_df.drop(columns=[self.target_column])
            y_test = test_df[self.target_column]  # noqa: F841 - stored for later use

        # 2. Feature Engineering: FIT ONLY ON TRAIN
        logger.info("\n" + "=" * 50)
        logger.info("FEATURE ENGINEERING")
        logger.info("=" * 50)
        logger.info("Fitting feature engineering on TRAIN data only...")

        fe_enabled = self.feature_engineering_config.get("enabled", True)
        fe_config = self.feature_engineering_config.get("preprocessing", {})
        fs_config = self.feature_engineering_config.get("feature_selection", {})

        if not fe_enabled:
            fe_config = {"enabled": False}
            fs_config = {"enabled": False}

        feature_engineering = DefaultFeatureEngineering(
            preprocessing_config=fe_config,
            feature_selection_config=fs_config,
        )

        # FIT only on train
        feature_engineering.fit(X_train, y_train)

        # TRANSFORM on train, val, test
        logger.info("Transforming train, val, test...")
        X_train_transformed = feature_engineering.transform(X_train)
        X_val_transformed = feature_engineering.transform(X_val)
        X_test_transformed = feature_engineering.transform(X_test) if X_test is not None else None

        logger.info(f"Train transformed shape: {X_train_transformed.shape}")
        logger.info(f"Val transformed shape: {X_val_transformed.shape}")
        if X_test_transformed is not None:
            logger.info(f"Test transformed shape: {X_test_transformed.shape}")

        # Diagnostic: NaN counts in transformed data
        train_nan = X_train_transformed.isnull().sum().sum()
        val_nan = X_val_transformed.isnull().sum().sum()
        if train_nan > 0 or val_nan > 0:
            logger.warning(f"NaN values - Train: {train_nan}, Val: {val_nan}")
            nan_per_col = X_train_transformed.isnull().sum()
            nan_cols = nan_per_col[nan_per_col > 0]
            if len(nan_cols) > 0:
                logger.warning(f"Train NaN columns ({len(nan_cols)}): {nan_cols.nlargest(10).to_dict()}")

        # Save intermediate parquets if configured
        preprocessing_parquet = fe_config.get("output_parquet")
        if preprocessing_parquet and feature_engineering.preprocessor is not None:
            prep_path = Path(preprocessing_parquet)
            prep_path.parent.mkdir(parents=True, exist_ok=True)
            X_prep = feature_engineering.preprocessor.transform(X_train)
            X_prep.to_parquet(prep_path, index=False)
            logger.info(f"Preprocessing output saved to: {prep_path}")

        fs_parquet = fs_config.get("output_parquet")
        if fs_parquet:
            fs_path = Path(fs_parquet)
            fs_path.parent.mkdir(parents=True, exist_ok=True)
            X_train_transformed.to_parquet(fs_path, index=False)
            logger.info(f"Feature selection output saved to: {fs_path}")

        # Save feature engineering (use output_pkl from config if specified)
        output_pkl = self.feature_engineering_config.get("output_pkl")
        fe_path = Path(output_pkl) if output_pkl else self.output_dir / "feature_engineering.pkl"
        fe_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fe_path, "wb") as f:
            pickle.dump(feature_engineering, f)
        logger.info(f"Feature Engineering saved to: {fe_path}")

        # 3. Model Training
        logger.info("\n" + "=" * 50)
        logger.info("MODEL TRAINING")
        logger.info("=" * 50)

        model_type = self.model_config.get("type", "lightgbm")
        logger.info(f"Model type: {model_type}")

        # Create model using registry
        model_class = ModelRegistry.get(model_type)

        # Prepare config for the model
        model_params = self._prepare_model_params(model_type, X_train_transformed)

        model = model_class(**model_params)

        # Fit the model
        model.fit(X_train_transformed, y_train, X_val=X_val_transformed, y_val=y_val)

        # Save model
        model_path = self.output_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"Model saved to: {model_path}")

        # 4. Quick evaluation on val (for logs)
        val_proba = model.predict_proba(X_val_transformed)
        val_pred = (val_proba >= 0.5).astype(int)

        from sklearn.metrics import f1_score, roc_auc_score

        val_auc = roc_auc_score(y_val, val_proba)
        val_f1 = f1_score(y_val, val_pred)

        logger.info(f"\nValidation AUC: {val_auc:.4f}")
        logger.info(f"Validation F1:  {val_f1:.4f}")

        # Diagnostic: probability distribution
        import numpy as np

        logger.info(
            f"Val proba stats: min={val_proba.min():.4f}, max={val_proba.max():.4f}, "
            f"mean={val_proba.mean():.4f}, median={np.median(val_proba):.4f}, "
            f"pct>0.5={100*(val_proba >= 0.5).mean():.1f}%, "
            f"pct>0.3={100*(val_proba >= 0.3).mean():.1f}%, "
            f"pct>0.1={100*(val_proba >= 0.1).mean():.1f}%"
        )

        # Save val predictions for threshold calibration
        val_pred_dir = Path(self.val_path).parent if self.val_path else Path("data/splits")
        val_pred_path = val_pred_dir / "val_predictions.parquet"
        val_predictions = pd.DataFrame(
            {"y_true": y_val.values, "y_proba": val_proba},
            index=y_val.index,
        )
        val_predictions.to_parquet(val_pred_path)
        logger.info(f"Val predictions saved to: {val_pred_path}")

        return {
            **context,
            "model_path": str(model_path),
            "feature_engineering_path": str(fe_path),
            "val_predictions_path": str(val_pred_path),
            "val_auc": val_auc,
            "val_f1": val_f1,
            "model": model,
            "feature_engineering": feature_engineering,
        }

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate that required paths exist."""
        # Check that paths were provided or exist in context
        train_path = self.train_path or context.get("train_path")
        val_path = self.val_path or context.get("val_path")

        if not train_path or not val_path:
            return False

        return Path(train_path).exists() and Path(val_path).exists()

    def get_required_keys(self) -> list:
        """Return the required context keys."""
        # If paths not provided, they are required from context
        if not self.train_path or not self.val_path:
            return ["train_path", "val_path"]
        return []

    def get_output_keys(self) -> list:
        """Return the keys added to the context."""
        return ["model_path", "feature_engineering_path", "val_predictions_path", "val_auc", "val_f1", "model", "feature_engineering"]

    def _prepare_model_params(self, model_type: str, X_train: pd.DataFrame) -> Dict:
        """
        Prepare parameters for the model based on its type.

        Args:
            model_type: Model type
            X_train: Training DataFrame

        Returns:
            Dict: Parameters for the model
        """
        params = self.model_config.copy()

        # For models that need specific columns
        if model_type in ["lightgbm", "lgbm", "catboost", "cat"]:
            params["cols_for_model"] = X_train.columns.tolist()
            sampling_config = params.pop("sampling", {})
            params["sampling_method"] = sampling_config.get("method", "under")
            params["sampling_th"] = sampling_config.get("threshold", 0.5)
            params["hyperparams"] = params.pop("hyperparams", {})
            hyperparam_search = params.pop("hyperparam_search", {})
            params["search_hip"] = hyperparam_search.get("enabled", False)
            params["n_iter"] = hyperparam_search.get("n_iter", 60)
            params["cv"] = hyperparam_search.get("cv", 3)

        # For neural models
        elif model_type in ["neural_network", "nn", "lstm"]:
            # Identify consumption columns (12_anterior ... 1_anterior)
            consumption_cols = [c for c in X_train.columns if "_anterior" in c]
            feature_cols = [c for c in X_train.columns if c not in consumption_cols]

            params["features_names"] = feature_cols
            params["spents_names"] = consumption_cols
            sampling_config = params.pop("sampling", {})
            params["sampling_method"] = sampling_config.get("method", "under")
            params["sampling_th"] = sampling_config.get("threshold", 0.5)
            params["search_hip"] = params.pop("hyperparam_search", {}).get("enabled", False)

        # Remove 'type' key as it's used for model selection, not for the model constructor
        params.pop("type", None)

        return params
