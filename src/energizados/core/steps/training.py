"""
Training Step for Energizados Framework.

Unified training step that combines feature engineering
and model training to prevent data leakage.
"""

import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from energizados.core.base import PipelineStep
from energizados.core.utils.secure_pickle import secure_dump

logger = logging.getLogger(__name__)


class MetricsDict(dict):
    """Dict that emits deprecation warning on legacy model_metrics access (Phase 5)."""

    def __getitem__(self, key: str) -> Any:
        if key == "model_metrics":
            warnings.warn(
                "'model_metrics' is deprecated; use 'metrics' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            # Return canonical metrics key (set below)
            return super().__getitem__("metrics")
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        """Override get() to emit deprecation warning for model_metrics key."""
        if key == "model_metrics":
            warnings.warn(
                "'model_metrics' is deprecated; use 'metrics' instead",
                DeprecationWarning,
                stacklevel=2,
            )
            # Return canonical metrics key
            return super().get("metrics", default)
        return super().get(key, default)


class _SklearnCalibWrapper:
    """Sklearn-compatible shim for CalibratedClassifierCV with cv='prefit'.

    CalibratedClassifierCV requires ``classes_``, a 2D ``predict_proba``, and
    ``_estimator_type = "classifier"`` (checked by sklearn's ``is_classifier()``).
    Our adapters expose 1D and lack these, so this wrapper bridges the gap.
    """

    _estimator_type = "classifier"

    def __init__(self, adapter) -> None:
        self._adapter = adapter
        self.classes_ = np.array([0, 1])

    def fit(self, X, y):
        # cv='prefit' never calls fit, but sklearn validates its presence.
        return self

    def predict_proba(self, X):
        p = self._adapter.predict_proba(X)
        return np.column_stack([1 - p, p])


class _CalibratedWrapper:
    """Post-calibration wrapper that restores the 1D predict_proba interface.

    After ``CalibratedClassifierCV.fit()``, ``predict_proba`` returns 2D (n, 2).
    This wrapper extracts the positive-class column so downstream code (evaluator,
    inference) continues to receive 1D arrays as expected.

    It also delegates the ``BaseModel`` contract (``get_raw_model``,
    ``check_fitted``, ``is_fitted_``, ``config``, ``cols_for_model``, ``_model``)
    to the wrapped adapter so downstream consumers (SHAP explainer, evaluator
    feature importance, report generation) work on calibrated models exactly as
    they do on the underlying adapter. Without this delegation the saved wrapper
    is ``secure_dump``ed as if it were a ``BaseModel`` but lacks the attributes
    those consumers read, silently degrading SHAP/feature-importance output.
    """

    def __init__(self, calibrated_clf, original_adapter) -> None:
        self._calibrated = calibrated_clf
        self._adapter = original_adapter

    def predict_proba(self, X):
        return self._calibrated.predict_proba(X)[:, 1]

    def predict(self, X):
        return self._adapter.predict(X)

    # ------------------------------------------------------------------
    # BaseModel contract delegation
    # ------------------------------------------------------------------
    def get_raw_model(self):
        """Return the raw underlying model (for SHAP / feature importance)."""
        return self._adapter.get_raw_model()

    def check_fitted(self):
        """Delegate fitted-state check to the wrapped adapter."""
        return self._adapter.check_fitted()

    @property
    def is_fitted_(self):
        return getattr(self._adapter, "is_fitted_", False)

    @property
    def config(self):
        return getattr(self._adapter, "config", {})

    @property
    def cols_for_model(self):
        return getattr(self._adapter, "cols_for_model", None)

    @property
    def _model(self):
        return getattr(self._adapter, "_model", None)


def _date_columns_needed_by_preprocessing(preprocessing_config: dict) -> set:
    """Return date_column values referenced by temporal_features in global_transformers."""
    needed = set()
    global_transformers = preprocessing_config.get("global_transformers") or []
    for entry in global_transformers:
        if isinstance(entry, dict) and "temporal_features" in entry:
            params = entry["temporal_features"]
            if isinstance(params, dict) and params.get("date_column"):
                needed.add(params["date_column"])
    return needed


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
        self._phase_callback = None

    # ------------------------------------------------------------------
    # Phase progress reporting
    # ------------------------------------------------------------------

    def _report_phase(self, context: Dict[str, Any], phase: str, pct: int):
        """Report phase progress if callback is available.

        Args:
            context: Pipeline context (may contain _on_phase_update callback)
            phase: Name of the current phase
            pct: Progress percentage (0-100)
        """
        if self._phase_callback is None:
            self._phase_callback = context.get("_on_phase_update")
        if self._phase_callback:
            try:
                self._phase_callback("TrainingStep", phase, pct)
            except Exception as e:  # nosec: callback errors should not abort training
                logger.debug("Phase callback error (ignored): %s", type(e).__name__)

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the full training pipeline.

        Loads train/val/test splits from disk, optionally applies
        ``columns_filter`` row-level filtering (from
        ``feature_engineering.preprocessing.columns_filter``), fits
        DefaultFeatureEngineering on training data, transforms all splits,
        fits the model(s), and saves artifacts.  A quick validation
        AUC/F1 is logged after training.

        Args:
            context: Pipeline context dict; may contain ``train_path``, ``val_path``,
                and ``test_path`` when paths were not provided at construction time.

        Returns:
            Dict: Updated context with keys: ``model_path``, ``feature_engineering_path``,
                ``val_predictions_path``, ``val_auc``, ``val_f1``, ``model``,
                ``feature_engineering``. In comparison mode (multiple models, no ensemble):
                ``model_paths``, ``models``, ``val_metrics``, ``comparison_mode=True``.

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

        self._report_phase(context, "loading", 0)

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

        # Apply columns_filter (row-level filtering) before any transformations
        columns_filter = self.feature_engineering_config.get("preprocessing", {}).get(
            "columns_filter"
        )
        if columns_filter:
            from energizados.core.utils.columns_filter import apply_columns_filter

            logger.info("Applying columns_filter to training data...")
            X_train, n_removed = apply_columns_filter(X_train, columns_filter)
            y_train = y_train.loc[X_train.index]
            if n_removed > 0:
                logger.info(f"  Train: removed {n_removed} rows")

            X_val, n_removed = apply_columns_filter(X_val, columns_filter)
            y_val = y_val.loc[X_val.index]
            if n_removed > 0:
                logger.info(f"  Val: removed {n_removed} rows")

            if X_test is not None:
                X_test, n_removed = apply_columns_filter(X_test, columns_filter)
                y_test = y_test.loc[X_test.index]  # noqa: F841
                if n_removed > 0:
                    logger.info(f"  Test: removed {n_removed} rows")

        datetime_cols = X_train.select_dtypes(include=["datetime64", "datetimetz"]).columns.tolist()
        if datetime_cols:
            needed_by_temporal = _date_columns_needed_by_preprocessing(
                self.feature_engineering_config.get("preprocessing", {})
            )
            cols_to_drop = [c for c in datetime_cols if c not in needed_by_temporal]
            if cols_to_drop:
                logger.info(f"Dropping datetime columns before feature engineering: {cols_to_drop}")
                X_train = X_train.drop(columns=cols_to_drop)
                X_val = X_val.drop(columns=cols_to_drop)
                if X_test is not None:
                    X_test = X_test.drop(columns=cols_to_drop)
            if needed_by_temporal & set(datetime_cols):
                logger.info(
                    f"Keeping datetime columns required by temporal_features: "
                    f"{sorted(needed_by_temporal & set(datetime_cols))}"
                )

        self._report_phase(context, "loading", 10)

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

        # Lazy import to avoid module-level cycle
        from energizados.feature_engineering import DefaultFeatureEngineering

        feature_engineering = DefaultFeatureEngineering(
            preprocessing_config=fe_config,
            feature_selection_config=fs_config,
        )

        feature_engineering.fit(X_train, y_train)

        # Save feature selection audit log if feature selection is enabled
        if (
            hasattr(feature_engineering, "selector_pipeline")
            and feature_engineering.selector_pipeline is not None
        ):
            # Check if selector pipeline has any steps
            if (
                hasattr(feature_engineering.selector_pipeline, "_step_selectors")
                and feature_engineering.selector_pipeline._step_selectors
            ):
                audit_log_path = self.output_dir / "reports" / "feature_selection_audit.json"
                feature_engineering.selector_pipeline.save_audit_log(audit_log_path)
                logger.info(f"Feature selection audit log saved to: {audit_log_path}")

        logger.info("Transforming train, val, test...")
        X_train_transformed = feature_engineering.transform(X_train)
        X_val_transformed = feature_engineering.transform(X_val)
        X_test_transformed = feature_engineering.transform(X_test) if X_test is not None else None

        # Drop any datetime columns that survived feature engineering (e.g. date columns used
        # by temporal_features with drop_date_column=False — models can't consume them).
        residual_dt_cols = X_train_transformed.select_dtypes(
            include=["datetime64", "datetimetz"]
        ).columns.tolist()
        if residual_dt_cols:
            logger.info(
                f"Dropping residual datetime columns after feature engineering: {residual_dt_cols}"
            )
            X_train_transformed = X_train_transformed.drop(columns=residual_dt_cols)
            X_val_transformed = X_val_transformed.drop(columns=residual_dt_cols)
            if X_test_transformed is not None:
                X_test_transformed = X_test_transformed.drop(columns=residual_dt_cols)

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
                logger.warning(
                    f"Train NaN columns ({len(nan_cols)}): {nan_cols.nlargest(10).to_dict()}"
                )

        # Save intermediate parquets if configured (for inspection — includes target column)
        preprocessing_parquet = fe_config.get("output_parquet")
        if preprocessing_parquet and feature_engineering.preprocessor is not None:
            prep_path = Path(preprocessing_parquet)
            prep_path.parent.mkdir(parents=True, exist_ok=True)
            X_prep = feature_engineering.preprocessor.transform(X_train)
            # Include target column for inspection purposes
            prep_df = X_prep.copy()
            prep_df[self.target_column] = y_train.values
            prep_df.to_parquet(prep_path, index=False)
            logger.info(f"Preprocessing output saved to: {prep_path}")

        fs_parquet = fs_config.get("output_parquet")
        if fs_parquet:
            fs_path = Path(fs_parquet)
            fs_path.parent.mkdir(parents=True, exist_ok=True)
            # Include target column for inspection purposes
            fs_df = X_train_transformed.copy()
            fs_df[self.target_column] = y_train.values
            fs_df.to_parquet(fs_path, index=False)
            logger.info(f"Feature selection output saved to: {fs_path}")

        # Save feature engineering
        output_pkl = self.feature_engineering_config.get("output_pkl")
        fe_path = Path(output_pkl) if output_pkl else self.output_dir / "feature_engineering.pkl"
        fe_path.parent.mkdir(parents=True, exist_ok=True)
        secure_dump(feature_engineering, fe_path)
        logger.info(f"Feature Engineering saved to: {fe_path}")

        self._report_phase(context, "feature_engineering", 50)

        # Phase C: Build and train model(s)
        logger.info("\n" + "=" * 50)
        logger.info("MODEL TRAINING")
        logger.info("=" * 50)

        names = self._resolve_model_names(self.models_configs)

        # Initialize variables for all modes
        model = None
        model_path = None
        models_dict = None
        model_paths_dict = None

        if len(self.models_configs) == 1:
            model, model_path = self._train_single_model(
                cfg=self.models_configs[0],
                name=names[0],
                X_train=X_train_transformed,
                y_train=y_train,
                X_val=X_val_transformed,
                y_val=y_val,
                X_train_raw=X_train,
                X_val_raw=X_val,
                save_path=self.output_dir / "model.pkl",
            )
        elif self.ensemble_config:
            model, model_path = self._train_ensemble(
                names=names,
                X_train=X_train_transformed,
                y_train=y_train,
                X_val=X_val_transformed,
                y_val=y_val,
            )
        else:
            models_dict, model_paths_dict = self._train_multi_model(
                names=names,
                X_train=X_train_transformed,
                y_train=y_train,
                X_val=X_val_transformed,
                y_val=y_val,
                X_train_raw=X_train,
                X_val_raw=X_val,
            )

        self._report_phase(context, "training", 90)

        # Phase D: Quick val metrics
        from sklearn.metrics import f1_score, roc_auc_score

        # Comparison mode: calculate metrics for each model
        if len(self.models_configs) > 1 and not self.ensemble_config:
            val_metrics = {}
            logger.info("\nComparison mode - validation metrics per model:")

            for name in names:
                model_type = None
                for cfg in self.models_configs:
                    if cfg.get("name") == name or (
                        cfg.get("type") == name and names.count(name) == 1
                    ):
                        model_type = cfg.get("type")
                        break
                if model_type is None:
                    model_type = name  # Fallback to name

                if model_type in ["simple_trend", "simple_constant"]:
                    X_val_for_pred = X_val
                else:
                    X_val_for_pred = X_val_transformed

                val_proba = models_dict[name].predict_proba(X_val_for_pred)
                val_pred = (val_proba >= 0.5).astype(int)

                val_auc = roc_auc_score(y_val, val_proba)
                val_f1 = f1_score(y_val, val_pred)

                val_metrics[name] = {"auc": val_auc, "f1": val_f1}
                logger.info(f"  {name:15s} AUC: {val_auc:.4f}, F1: {val_f1:.4f}")

            # Use first model's predictions for global stats (backward compatibility)
            first_name = names[0]
            model_type = None
            for cfg in self.models_configs:
                if cfg.get("name") == first_name or (
                    cfg.get("type") == first_name and names.count(first_name) == 1
                ):
                    model_type = cfg.get("type")
                    break
            if model_type is None:
                model_type = first_name

            if model_type in ["simple_trend", "simple_constant"]:
                X_val_for_pred = X_val
            else:
                X_val_for_pred = X_val_transformed

            val_proba = models_dict[first_name].predict_proba(X_val_for_pred)
            val_auc = None
            val_f1 = None
        else:
            # Single model or ensemble mode
            model_type = (
                self.models_configs[0].get("type", "lightgbm")
                if len(self.models_configs) == 1
                else None
            )
            if model_type in ["simple_trend", "simple_constant"]:
                X_val_for_pred = X_val
            else:
                X_val_for_pred = X_val_transformed

            val_proba = model.predict_proba(X_val_for_pred)
            val_pred = (val_proba >= 0.5).astype(int)

            val_auc = roc_auc_score(y_val, val_proba)
            val_f1 = f1_score(y_val, val_pred)
            val_metrics = None

            logger.info(f"\nValidation AUC: {val_auc:.4f}")
            logger.info(f"Validation F1:  {val_f1:.4f}")

        import numpy as np

        logger.info(
            f"Val proba stats (first model): min={val_proba.min():.4f}, max={val_proba.max():.4f}, "
            f"mean={val_proba.mean():.4f}, median={np.median(val_proba):.4f}, "
            f"pct>0.5={100 * (val_proba >= 0.5).mean():.1f}%, "
            f"pct>0.3={100 * (val_proba >= 0.3).mean():.1f}%, "
            f"pct>0.1={100 * (val_proba >= 0.1).mean():.1f}%"
        )

        # Save val predictions
        val_pred_dir = Path(self.val_path).parent if self.val_path else Path("data/temp/splits")
        val_pred_path = val_pred_dir / "val_predictions.parquet"
        val_predictions = pd.DataFrame(
            {"y_true": y_val.values, "y_proba": val_proba},
            index=y_val.index,
        )
        val_predictions.to_parquet(val_pred_path)
        logger.info(f"Val predictions saved to: {val_pred_path}")

        # Build return context
        result = {
            **context,
            "feature_engineering_path": str(fe_path),
            "val_predictions_path": str(val_pred_path),
            "feature_engineering": feature_engineering,
        }

        # Comparison mode: set model_paths and val_metrics
        if len(self.models_configs) > 1 and not self.ensemble_config:
            result["model_paths"] = {name: str(path) for name, path in model_paths_dict.items()}
            result["models"] = models_dict
            result["model_path"] = None
            result["model"] = None
            result["val_metrics"] = val_metrics
            result["val_auc"] = None
            result["val_f1"] = None
            result["comparison_mode"] = True
            # Set canonical metrics key for comparison mode (Phase 5)
            result["metrics"] = val_metrics if val_metrics else {}
        else:
            # Single model or ensemble mode
            result["model_path"] = str(model_path)
            result["model"] = model
            result["model_paths"] = None
            result["models"] = None
            result["val_metrics"] = None
            result["val_auc"] = val_auc
            result["val_f1"] = val_f1
            result["comparison_mode"] = False
            # Set canonical metrics key for single/ensemble mode (Phase 5)
            result["metrics"] = {"auc": val_auc, "f1": val_f1}

        self._report_phase(context, "evaluation", 100)

        # Wrap result in MetricsDict for deprecation warning (Phase 5)
        return MetricsDict(result)

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
        X_train_raw: pd.DataFrame = None,
        X_val_raw: pd.DataFrame = None,
        save_path: Path = None,
    ):
        """Train one model, save it, and return (model, path).

        For simple models (simple_trend, simple_constant), uses raw data (before feature engineering)
        since these rule-based models need the original consumption columns.
        """
        model_type = cfg.get("type", "lightgbm")
        logger.info(f"Training model '{name}' (type: {model_type})")

        # Lazy import to avoid module-level cycle
        from energizados.modeling.registry import ModelRegistry

        model_class = ModelRegistry.get(model_type)
        params = model_class.from_config(cfg, X_train)

        # For simple models, use raw data instead of transformed
        if model_type in ["simple_trend", "simple_constant"]:
            if X_train_raw is not None and X_val_raw is not None:
                X_train_for_model = X_train_raw
                X_val_for_model = X_val_raw
                logger.info("Using raw data for simple model (before feature engineering)")
            else:
                X_train_for_model = X_train
                X_val_for_model = X_val
        else:
            X_train_for_model = X_train
            X_val_for_model = X_val

        model = model_class(**params)
        model.fit(X_train_for_model, y_train, X_val=X_val_for_model, y_val=y_val)

        # Apply probability calibration if configured
        calibration_config = cfg.get("calibration", {})
        if calibration_config.get("enabled", False):
            model = self._apply_calibration(model, model_type, X_val, y_val, calibration_config)
            logger.info(f"Applied probability calibration to model '{name}'")

        save_path.parent.mkdir(parents=True, exist_ok=True)
        secure_dump(model, save_path)
        logger.info(f"Model '{name}' saved to: {save_path}")

        return model, save_path

    def _apply_calibration(
        self,
        model,
        model_type: str,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        calibration_config: Dict,
    ):
        """Apply CalibratedClassifierCV to a trained model.

        Args:
            model: Trained model (must support predict_proba).
            model_type: Type of the model (lightgbm, catboost, etc.).
            X_val: Validation features for fitting calibration.
            y_val: Validation target for fitting calibration.
            calibration_config: Calibration configuration dict.

        Returns:
            Calibrated model wrapped in CalibratedClassifierCV.
        """
        from sklearn.calibration import CalibratedClassifierCV

        method = calibration_config.get("method", "sigmoid")

        logger.info(f"Calibrating with method='{method}', cv=prefit")

        # CalibratedClassifierCV with cv='prefit' requires classes_ and 2D predict_proba.
        # _SklearnCalibWrapper bridges our 1D-adapter interface to what sklearn expects.
        wrapped = _SklearnCalibWrapper(model)
        calibrated_clf = CalibratedClassifierCV(estimator=wrapped, method=method, cv="prefit")
        calibrated_clf.fit(X_val, y_val)

        # _CalibratedWrapper restores the 1D predict_proba convention used by the evaluator.
        return _CalibratedWrapper(calibrated_clf, model)

    # ------------------------------------------------------------------
    # Multi-model helpers (comparison mode)
    # ------------------------------------------------------------------

    def _train_multi_model(
        self,
        names: List[str],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        X_train_raw: pd.DataFrame = None,
        X_val_raw: pd.DataFrame = None,
    ) -> tuple[dict[str, Any], dict[str, Path]]:
        """
        Train each model independently for comparison mode.

        Returns:
            Tuple of (models_dict, paths_dict) where:
            - models_dict: {name: fitted_model}
            - paths_dict: {name: Path to model.pkl}
        """
        models_dict = {}
        paths_dict = {}

        for cfg, name in zip(self.models_configs, names):
            save_path = self.output_dir / name / "model.pkl"
            model, _ = self._train_single_model(
                cfg=cfg,
                name=name,
                X_train=X_train,
                y_train=y_train,
                X_val=X_val,
                y_val=y_val,
                X_train_raw=X_train_raw,
                X_val_raw=X_val_raw,
                save_path=save_path,
            )
            models_dict[name] = model
            paths_dict[name] = save_path

        return models_dict, paths_dict

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

        logger.info(
            f"Building ensemble: method={self.ensemble_config.get('method', 'soft_voting')}"
        )
        ensemble.fit(X_train, y_train, X_val=X_val, y_val=y_val)

        ensemble_path = self.output_dir / "ensemble.pkl"
        secure_dump(ensemble, ensemble_path)
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
            "model_paths",
            "models",
            "val_metrics",
            "comparison_mode",
        ]
