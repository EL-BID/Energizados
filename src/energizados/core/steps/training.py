"""
Training Step for Energizados Framework.

Unified training step that combines feature engineering
and model training to prevent data leakage.
"""

import logging
import pickle  # nosec B403: ML model serialization (local files only)
from pathlib import Path
from typing import Any, Dict, List, Optional

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

    Accepts a ``models_configs`` list (one entry per model). When the list
    contains a single model, behaviour is identical to the old single-model
    path. When multiple models are provided an ``EnsembleModel`` is built
    and saved as ``ensemble.pkl``; each base model is also saved under its
    own sub-directory for inspection.

    Args:
        train_path: Path to training dataset.
        val_path: Path to validation dataset.
        test_path: Path to test dataset.
        target_column: Name of target column.
        feature_engineering_config: Feature engineering configuration.
        models_configs: List of model configuration dicts (required).
        ensemble_config: Ensemble configuration dict (required when len > 1).
        output_dir: Output directory.

    Example:
        >>> step = TrainingStep(
        ...     models_configs=[{"type": "lightgbm", "hyperparams": {...}}],
        ... )
        >>> result = step.run(context)
    """

    def __init__(
        self,
        train_path: Optional[str] = None,
        val_path: Optional[str] = None,
        test_path: Optional[str] = None,
        target_column: str = "target",
        feature_engineering_config: Optional[Dict] = None,
        models_configs: Optional[List[Dict]] = None,
        ensemble_config: Optional[Dict] = None,
        output_dir: str = "output/models/",
        **kwargs,
    ):
        self.train_path = train_path
        self.val_path = val_path
        self.test_path = test_path
        self.target_column = target_column
        self.feature_engineering_config = feature_engineering_config or {}
        self.models_configs = models_configs or []
        self.ensemble_config = ensemble_config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the full training pipeline.

        Loads train/val/test splits from disk, fits DefaultFeatureEngineering on
        training data, transforms all splits, fits the model(s), and saves artifacts.
        A quick validation AUC/F1 is logged after training.

        Args:
            context: Pipeline context dict; may contain ``train_path``, ``val_path``,
                and ``test_path`` when paths were not provided at construction time.

        Returns:
            Dict: Updated context with keys: ``model_path``, ``feature_engineering_path``,
                ``val_predictions_path``, ``val_auc``, ``val_f1``, ``model``,
                ``feature_engineering``.

        Raises:
            ValueError: If ``train_path`` or ``val_path`` cannot be resolved.
        """
        # Use paths from context if not provided
        if context:
            self.train_path = self.train_path or context.get("train_path")
            self.val_path = self.val_path or context.get("val_path")
            self.test_path = self.test_path or context.get("test_path")

        if not self.train_path or not self.val_path:
            raise ValueError("train_path and val_path are required")

        # Phase A: Load data
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

        X_train = train_df.drop(columns=[self.target_column])
        y_train = train_df[self.target_column]
        X_val = val_df.drop(columns=[self.target_column])
        y_val = val_df[self.target_column]

        X_test = None
        y_test = None  # noqa: F841
        if test_df is not None:
            X_test = test_df.drop(columns=[self.target_column])
            y_test = test_df[self.target_column]  # noqa: F841

        # Phase B: Feature Engineering — fit ONCE on train
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

        feature_engineering.fit(X_train, y_train)

        logger.info("Transforming train, val, test...")
        X_train_transformed = feature_engineering.transform(X_train)
        X_val_transformed = feature_engineering.transform(X_val)
        X_test_transformed = feature_engineering.transform(X_test) if X_test is not None else None

        logger.info(f"Train transformed shape: {X_train_transformed.shape}")
        logger.info(f"Val transformed shape: {X_val_transformed.shape}")
        if X_test_transformed is not None:
            logger.info(f"Test transformed shape: {X_test_transformed.shape}")

        # Diagnostic: NaN counts
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

        # Save feature engineering
        output_pkl = self.feature_engineering_config.get("output_pkl")
        fe_path = Path(output_pkl) if output_pkl else self.output_dir / "feature_engineering.pkl"
        fe_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fe_path, "wb") as f:
            pickle.dump(feature_engineering, f)
        logger.info(f"Feature Engineering saved to: {fe_path}")

        # Phase C: Build and train model(s)
        logger.info("\n" + "=" * 50)
        logger.info("MODEL TRAINING")
        logger.info("=" * 50)

        names = self._resolve_model_names(self.models_configs)

        if len(self.models_configs) == 1:
            model, model_path = self._train_single_model(
                cfg=self.models_configs[0],
                name=names[0],
                X_train=X_train_transformed,
                y_train=y_train,
                X_val=X_val_transformed,
                y_val=y_val,
                save_path=self.output_dir / "model.pkl",
            )
        else:
            model, model_path = self._train_ensemble(
                names=names,
                X_train=X_train_transformed,
                y_train=y_train,
                X_val=X_val_transformed,
                y_val=y_val,
            )

        # Phase D: Quick val metrics
        val_proba = model.predict_proba(X_val_transformed)
        val_pred = (val_proba >= 0.5).astype(int)

        from sklearn.metrics import f1_score, roc_auc_score

        val_auc = roc_auc_score(y_val, val_proba)
        val_f1 = f1_score(y_val, val_pred)

        logger.info(f"\nValidation AUC: {val_auc:.4f}")
        logger.info(f"Validation F1:  {val_f1:.4f}")

        import numpy as np

        logger.info(
            f"Val proba stats: min={val_proba.min():.4f}, max={val_proba.max():.4f}, "
            f"mean={val_proba.mean():.4f}, median={np.median(val_proba):.4f}, "
            f"pct>0.5={100*(val_proba >= 0.5).mean():.1f}%, "
            f"pct>0.3={100*(val_proba >= 0.3).mean():.1f}%, "
            f"pct>0.1={100*(val_proba >= 0.1).mean():.1f}%"
        )

        # Save val predictions
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

    # ------------------------------------------------------------------
    # Single model helpers
    # ------------------------------------------------------------------

    def _train_single_model(
        self,
        cfg: Dict,
        name: str,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        save_path: Path,
    ):
        """Train one model, save it, and return (model, path)."""
        model_type = cfg.get("type", "lightgbm")
        logger.info(f"Training model '{name}' (type: {model_type})")

        model_class = ModelRegistry.get(model_type)
        params = self._prepare_model_params(cfg, X_train)
        model = model_class(**params)
        model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"Model '{name}' saved to: {save_path}")

        return model, save_path

    # ------------------------------------------------------------------
    # Ensemble helpers
    # ------------------------------------------------------------------

    def _train_ensemble(
        self,
        names: List[str],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ):
        """Train all base models, build and fit the ensemble, return (ensemble, path)."""
        from energizados.modeling.ensemble import EnsembleModel

        if not self.ensemble_config:
            raise ValueError("ensemble_config is required when more than one model is specified.")

        base_models = []
        model_types = []

        for cfg, name in zip(self.models_configs, names):
            model_type = cfg.get("type", "lightgbm")
            model_types.append(model_type)

            save_path = self.output_dir / name / "model.pkl"
            model, _ = self._train_single_model(
                cfg=cfg,
                name=name,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                save_path=save_path,
            )
            base_models.append(model)

        ensemble = EnsembleModel(
            base_models=base_models,
            model_types=model_types,
            model_names=names,
            method=self.ensemble_config.get("method", "soft_voting"),
            meta_learner_config=self.ensemble_config.get("meta_learner"),
            weights=self.ensemble_config.get("weights"),
            use_val_as_oof=self.ensemble_config.get("use_val_as_oof", True),
            cv=self.ensemble_config.get("cv", 5),
            skip_base_fit=True,  # base models already fitted above
        )

        logger.info(f"Building ensemble: method={self.ensemble_config.get('method', 'soft_voting')}")
        ensemble.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        ensemble_path = self.output_dir / "ensemble.pkl"
        with open(ensemble_path, "wb") as f:
            pickle.dump(ensemble, f)
        logger.info(f"Ensemble saved to: {ensemble_path}")

        return ensemble, ensemble_path

    # ------------------------------------------------------------------
    # Name resolution
    # ------------------------------------------------------------------

    def _resolve_model_names(self, models_configs: List[Dict]) -> List[str]:
        """
        Resolve a unique name for each model config.

        - If ``name`` key is present, use it.
        - If the type appears only once, use the type string.
        - If the type appears multiple times, use ``type_0``, ``type_1``, ...
        """
        type_counts: Dict[str, int] = {}
        for cfg in models_configs:
            t = cfg.get("type", "model")
            type_counts[t] = type_counts.get(t, 0) + 1

        type_indices: Dict[str, int] = {}
        names = []
        for cfg in models_configs:
            if "name" in cfg:
                names.append(cfg["name"])
                continue
            t = cfg.get("type", "model")
            if type_counts[t] == 1:
                names.append(t)
            else:
                idx = type_indices.get(t, 0)
                names.append(f"{t}_{idx}")
                type_indices[t] = idx + 1

        return names

    # ------------------------------------------------------------------
    # Model param preparation
    # ------------------------------------------------------------------

    def _prepare_model_params(self, model_config: Dict, X_train: pd.DataFrame) -> Dict:
        """
        Prepare constructor parameters for a model based on its type.

        Args:
            model_config: Single model config dict (with "type", "hyperparams", etc.).
            X_train: Transformed training DataFrame (used to derive column lists).

        Returns:
            Dict: Parameters for the model constructor.
        """
        params = model_config.copy()
        model_type = params.get("type", "lightgbm")

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

        elif model_type in ["neural_network", "nn", "lstm"]:
            consumption_cols = [c for c in X_train.columns if "_anterior" in c]
            feature_cols = [c for c in X_train.columns if c not in consumption_cols]
            params["features_names"] = feature_cols
            params["spents_names"] = consumption_cols
            sampling_config = params.pop("sampling", {})
            params["sampling_method"] = sampling_config.get("method", "under")
            params["sampling_th"] = sampling_config.get("threshold", 0.5)
            params["search_hip"] = params.pop("hyperparam_search", {}).get("enabled", False)

        # Store the type string in the config so evaluator can read it
        params["config"] = {"type": model_type}

        # Remove keys that are not model constructor arguments
        params.pop("type", None)
        params.pop("name", None)

        return params

    # ------------------------------------------------------------------
    # PipelineStep interface
    # ------------------------------------------------------------------

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate that both train and validation parquet files exist."""
        train_path = self.train_path or context.get("train_path")
        val_path = self.val_path or context.get("val_path")
        if not train_path or not val_path:
            return False
        return Path(train_path).exists() and Path(val_path).exists()

    def get_required_keys(self) -> list:
        """Return required context keys."""
        if not self.train_path or not self.val_path:
            return ["train_path", "val_path"]
        return []

    def get_output_keys(self) -> list:
        """Return context keys produced by this step."""
        return [
            "model_path",
            "feature_engineering_path",
            "val_predictions_path",
            "val_auc",
            "val_f1",
            "model",
            "feature_engineering",
        ]
