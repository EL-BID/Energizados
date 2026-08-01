"""
Energizados Framework Contracts.

Single home for all abstract base classes. Public API.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# Model & Inference Contracts
# ============================================================================


class BaseModel(ABC):
    """Base class for custom models.

    Users inherit and implement abstract methods to define
    their own ML model.

    Example:
        >>> from energizados.contracts import BaseModel
        >>> import numpy as np
        >>> class MyModel(BaseModel):
        ...     def fit(self, X, y, X_val=None, y_val=None):
        ...         self.model_ = SomeClassifier()
        ...         self.model_.fit(X, y)
        ...         self.is_fitted_ = True
        ...         return self
        ...     def predict(self, X):
        ...         return self.model_.predict(X)
        ...     def predict_proba(self, X):
        ...         return self.model_.predict_proba(X)[:, 1]
        ...     def get_raw_model(self):
        ...         return self.model_
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the model.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.model_ = None
        self.is_fitted_ = False

    @abstractmethod
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> "BaseModel":
        """Train the model.

        Args:
            X: Training features
            y: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)

        Returns:
            self: Returns the trained instance
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Probabilities of the positive class

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        pass

    @abstractmethod
    def get_raw_model(self) -> Any:
        """Extract the underlying fitted model from the adapter's trained pipeline.

        Adapters wrap sklearn/lightgbm/catboost/keras models inside pipelines
        (e.g., sklearn Pipeline). This method returns the raw fitted model
        suitable for tools like SHAP that need direct access to the model object.

        Returns:
            The raw fitted model instance (e.g., LGBMClassifier, Sequential).

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        pass

    def check_fitted(self):
        """Check that the model is fitted.

        Raises:
            ModelNotFittedError: If the model is not fitted
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)

    def save(self, path: str) -> None:
        """Save the fitted model to disk.

        Args:
            path: Destination path (.pkl extension recommended).

        Raises:
            ModelNotFittedError: If the model is not fitted.
        """
        self.check_fitted()

        from energizados.core.utils.integrity_pickle import dump

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        dump(self, path)
        logger.info(f"Model saved to: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseModel":
        """Load a fitted model from disk.

        Args:
            path: Path to the saved model file.

        Returns:
            BaseModel: Loaded model.

        Raises:
            FileNotFoundError: If the .sig file is missing.
            ValueError: If integrity check fails or path contains '..'.
        """
        from energizados.core.utils.integrity_pickle import load

        model = load(path)
        logger.info(f"Model loaded from: {path}")
        return model


@runtime_checkable
class ModelContainer(Protocol):
    """Protocol for objects that can make predictions.

    Satisfied by BaseModel subclasses and HierarchicalModelContainer.
    """

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probabilities of the positive class.

        Args:
            X: Feature DataFrame.

        Returns:
            np.ndarray: Probabilities (shape: [n_samples]).
        """
        ...

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return binary predictions (0 or 1).

        Args:
            X: Feature DataFrame.

        Returns:
            np.ndarray: Binary predictions (shape: [n_samples]).
        """
        ...


class BaseInference(ABC):
    """Base class for inference and prediction.

    Users can inherit and implement abstract methods
    to define their own inference logic.

    Example:
        >>> from energizados.contracts import BaseInference, BaseModel
        >>> class MyInference(BaseInference):
        ...     def predict(self, model, data):
        ...         return model.predict(data)
        ...     def predict_proba(self, model, data):
        ...         return model.predict_proba(data)
        ...     def load_model(self, model_path):
        ...         return load_model(model_path)
        ...     def save_predictions(self, predictions, output_path):
        ...         np.save(output_path, predictions)
    """

    @abstractmethod
    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Make binary predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)
        """
        pass

    @abstractmethod
    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Make probability predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Probabilities of the positive class
        """
        pass

    @abstractmethod
    def load_model(self, model_path: str) -> ModelContainer:
        """Load a trained model from disk.

        Args:
            model_path: Path to the model file

        Returns:
            ModelContainer: Loaded model (satisfies predict/predict_proba)
        """
        pass

    @abstractmethod
    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """Save predictions to file.

        Args:
            predictions: Predictions to save
            output_path: Output path
        """
        pass


# ============================================================================
# Pipeline & Evaluation Contracts
# ============================================================================


class BasePipeline(ABC):
    """Base class for user-defined pipelines.

    Provides the same context-based execution pattern as PipelineStep.
    The framework's built-in Pipeline orchestrator does NOT inherit this
    — it remains on PipelineStep for backward compatibility.
    """

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the pipeline and return the updated context.

        Args:
            context: Dictionary with pipeline data.

        Returns:
            Dict: Updated context with pipeline results.

        Raises:
            PipelineError: If an error occurs during execution.
        """
        pass

    def validate(self, context: Dict[str, Any]) -> bool:
        """Validate that the context has necessary data.

        Args:
            context: Dictionary with pipeline data.

        Returns:
            bool: True if validation succeeds.
        """
        return True

    def get_required_keys(self) -> list:
        """Return list of required context keys.

        Returns:
            list: Required key names.
        """
        return []


class BaseEvaluator(ABC):
    """Base class for model evaluation.

    Defines the contract for computing metrics and optional report generation.
    """

    @abstractmethod
    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model: Any,
        threshold: float = 0.5,
        **kwargs: Any,
    ) -> Dict[str, float]:
        """Compute evaluation metrics.

        Args:
            X: Feature DataFrame.
            y: True target values.
            model: Trained model (must have predict_proba).
            threshold: Decision threshold for binary predictions.
            **kwargs: Additional evaluator-specific parameters.

        Returns:
            Dict[str, float]: Metric name -> value (e.g., {'auc': 0.85, 'f1': 0.82}).

        Raises:
            ValueError: If inputs are invalid.
            ModelNotFittedError: If model is not fitted.
        """
        pass

    def generate_reports(
        self,
        metrics: Dict[str, float],
        output_dir: str,
        **kwargs: Any,
    ) -> None:
        """Generate evaluation reports (optional override).

        Args:
            metrics: Computed metrics from evaluate().
            output_dir: Directory to write reports.
            **kwargs: Additional report-specific parameters.
        """
        pass


# ============================================================================
# ETL, Feature Engineering, Feature Selection, EDA Contracts
# ============================================================================


class BaseETL(ABC):
    """Base class for ETL processes.

    Supports normal ETLs (extract/transform/load) and noop ETLs
    (e.g., CleanFilesETL) via the _is_noop_load flag.
    """

    # Class-level default so concrete ETLs whose __init__ does not call
    # super().__init__() still resolve the flag. CleanFilesETL sets True in PR#2.
    _is_noop_load: bool = False

    def __init__(self, name=None, input_paths=None, output_path=None, **params):
        """Initialize the ETL instance.

        Args:
            name: ETL name (stored as self.name).
            input_paths: Resolved input file paths (stored as self.input_paths).
            output_path: Output path (stored as self.output_path).
            **params: Additional orchestrator params (ignored by the base).
        """
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self._is_noop_load = False  # Subclass sets True for noop

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Extracts data from the source.

        Returns:
            pd.DataFrame: Raw data

        Raises:
            ETLError: If an error occurs during extraction
        """
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms and cleans the data.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Clean DataFrame with expected schema

        Raises:
            ETLError: If an error occurs during transformation
        """
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        """Saves the transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If an error occurs during loading
        """
        pass

    def noop_load(self) -> pd.DataFrame:
        """Override for ETLs that don't produce a dataset (e.g., CleanFilesETL).

        Returns:
            pd.DataFrame: Empty DataFrame (orchestrator compatibility).
        """
        return pd.DataFrame()

    def run(self, output_path: str) -> pd.DataFrame:
        """Execute the ETL pipeline.

        Args:
            output_path: Where to save the output (ignored for noop ETLs).

        Returns:
            pd.DataFrame: Transformed data (empty for noop ETLs).
        """
        import logging

        from energizados.core.exceptions import ETLError

        logger = logging.getLogger(__name__)

        if self._is_noop_load:
            return self.noop_load()

        try:
            df = self.extract()

            if len(df) == 0:
                return df

            # Apply sampling if 'sample' parameter was provided
            sample = getattr(self, "sample", None)
            if sample is not None:
                original_len = len(df)
                df = df.sample(n=min(sample, len(df)), random_state=42)
                logger.info(f"  • Sampled {len(df)} records (was {original_len})")

            df = self.transform(df)
            self.load(df, output_path)
            self._on_load_success()
            return df
        except ETLError:
            raise
        except Exception as e:
            raise ETLError(f"Error running ETL: {str(e)}") from e

    def _on_load_success(self) -> None:
        """Hook called after load() completes successfully. Override to persist state."""
        pass


class BaseFeatureEngineering(ABC):
    """Base class for feature engineering pipelines."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the feature engineering pipeline.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureEngineering":
        """Fit the feature engineering pipeline.

        Args:
            X: Feature DataFrame
            y: Target series

        Returns:
            self: Returns the fitted instance
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform features using the fitted pipeline.

        Args:
            X: Feature DataFrame

        Returns:
            pd.DataFrame: Transformed features

        Raises:
            ModelNotFittedError: If the pipeline is not fitted
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Fit and transform in one step.

        Args:
            X: Feature DataFrame
            y: Target series

        Returns:
            pd.DataFrame: Transformed features
        """
        return self.fit(X, y).transform(X)

    def save(self, path: str) -> None:
        """Save the fitted pipeline to disk.

        Args:
            path: Destination path (.pkl extension recommended).

        Raises:
            ModelNotFittedError: If the pipeline is not fitted.
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)

        from energizados.core.utils.integrity_pickle import dump

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        dump(self, path)
        logger.info(f"Feature engineering saved to: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseFeatureEngineering":
        """Load a fitted pipeline from disk.

        Args:
            path: Path to the saved pipeline file.

        Returns:
            BaseFeatureEngineering: Loaded pipeline.

        Raises:
            FileNotFoundError: If the .sig file is missing.
            ValueError: If integrity check fails or path contains '..'.
        """
        from energizados.core.utils.integrity_pickle import load

        pipeline = load(path)
        logger.info(f"Feature engineering loaded from: {path}")
        return pipeline

    def get_feature_names_out(self) -> list:
        """Get the names of the output features.

        Returns:
            list: Output feature names

        Raises:
            ModelNotFittedError: If the pipeline is not fitted
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return self._get_feature_names_out()

    def _get_feature_names_out(self) -> list:
        """Internal method to get output feature names.

        Returns:
            list: Output feature names
        """
        return []

    def check_fitted(self) -> None:
        """Check that the pipeline is fitted.

        Raises:
            ModelNotFittedError: If the pipeline is not fitted
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)


class BaseFeatureSelector(ABC):
    """Base class for feature selection."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the feature selector.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.selected_features_ = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureSelector":
        """Fit the feature selector.

        Args:
            X: Feature DataFrame
            y: Target series

        Returns:
            self: Returns the fitted instance
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform features by selecting the best ones.

        Args:
            X: Feature DataFrame

        Returns:
            pd.DataFrame: DataFrame with selected features

        Raises:
            ModelNotFittedError: If the selector is not fitted
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Fit and transform in one step.

        Args:
            X: Feature DataFrame
            y: Target series

        Returns:
            pd.DataFrame: DataFrame with selected features
        """
        return self.fit(X, y).transform(X)

    def get_selected_features(self) -> list:
        """Get the names of the selected features.

        Returns:
            list: Selected feature names

        Raises:
            ModelNotFittedError: If the selector is not fitted
        """
        if self.selected_features_ is None:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return self.selected_features_

    def get_audit_stats(self) -> Dict:
        """Get audit statistics about the selection process.

        Returns:
            Dict: Audit statistics

        Raises:
            ModelNotFittedError: If the selector is not fitted
        """
        if self.selected_features_ is None:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return {}

    def save(self, path: str) -> None:
        """Save the fitted selector to disk.

        Args:
            path: Destination path (.pkl extension recommended).

        Raises:
            ModelNotFittedError: If the selector is not fitted.
        """
        if self.selected_features_ is None:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)

        from energizados.core.utils.integrity_pickle import dump

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        dump(self, path)
        logger.info(f"Feature selector saved to: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseFeatureSelector":
        """Load a fitted selector from disk.

        Args:
            path: Path to the saved selector file.

        Returns:
            BaseFeatureSelector: Loaded selector.

        Raises:
            FileNotFoundError: If the .sig file is missing.
            ValueError: If integrity check fails or path contains '..'.
        """
        from energizados.core.utils.integrity_pickle import load

        selector = load(path)
        logger.info(f"Feature selector loaded from: {path}")
        return selector


class BaseExplorer(ABC):
    """Base class for exploratory data analysis.

    Note: This is adapted from the original EDA module's BaseExplorer
    to maintain backward compatibility. The original API uses analyze()
    and get_alerts() methods.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the explorer.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.alerts: List[Dict] = []
        self.results: Dict = {}

    @abstractmethod
    def analyze(self, df: pd.DataFrame, target_col: Optional[str] = None, **kwargs) -> Dict:
        """Analyze the DataFrame and return results.

        Args:
            df: Input DataFrame to analyze
            target_col: Name of target column (optional)
            **kwargs: Additional arguments specific to each implementation

        Returns:
            dict: Analysis results
        """
        pass

    @abstractmethod
    def get_alerts(self) -> List[Dict]:
        """Return list of alerts generated during analysis.

        Returns:
            list: List of alert dicts with keys: code, message, severity, details
        """
        pass

    def _add_alert(
        self,
        code: str,
        message: str,
        severity: str = "WARNING",
        details: Optional[Dict] = None,
    ) -> None:
        """Add an alert to the alerts list.

        Args:
            code: Alert code (e.g. 'HIGH_MISSING', 'CLASS_IMBALANCE')
            message: Human-readable alert message
            severity: Alert severity - 'ERROR', 'WARNING', or 'INFO'
            details: Optional dictionary with additional details
        """
        if severity not in ("ERROR", "WARNING", "INFO"):
            severity = "WARNING"

        self.alerts.append(
            {
                "code": code,
                "message": message,
                "severity": severity,
                "details": details or {},
            }
        )
