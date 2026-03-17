# Extending Energizados Framework

This guide explains how to extend the Energizados framework with custom components without modifying the core package. It covers creating custom ETLs, feature selectors, models, feature engineering pipelines, global transformers, and inference implementations.

## 1. Overview

### What Can Be Extended

Energizados provides several extension points where you can plug in custom implementations:

- **Custom ETL**: Define your own extract-transform-load processes for data preparation
- **Custom Feature Selector**: Implement domain-specific feature selection logic
- **Custom Model**: Integrate any ML model that follows the `BaseModel` interface
- **Custom Feature Engineering Pipeline**: Replace the default preprocessing + feature selection with a custom implementation
- **Custom Global Transformers**: Add custom transformers that operate on the entire dataset after column-level preprocessing
- **Custom Inference**: Implement custom prediction logic with business rules, thresholding, or post-processing

### The `custom_class` Plugin System

The framework uses a dynamic import system that loads custom classes referenced in YAML configuration files. You specify the full class path (e.g., `"src.data.my_etl.CustomETL"`) and the framework instantiates it at runtime.

Example:
```yaml
etls:
  my_etl:
    custom_class: "src.data.my_etl.CustomETL"
    params:
      some_param: value
```

### The Security Allowlist

Dynamic class imports are powerful but pose security risks. Energizados uses an **allowlist** to restrict which modules can be dynamically imported. Only modules starting with specific prefixes are allowed (see [Section 9](#9-the-security-allowlist) for details).

## 2. Extension Points Summary

| Extension Point | Base Class | Config Key | Config File |
|----------------|-------------|-------------|-------------|
| Custom ETL | `BaseETL` | `etls[name].custom_class` | `etls.yaml` |
| Custom Feature Selector | `BaseFeatureSelector` | `feature_selection.steps[].method` (with custom implementation) | `training.yaml` |
| Custom Model | `BaseModel` | `models[].custom_class` | `training.yaml` |
| Custom Feature Engineering | `BaseFeatureEngineering` | `feature_engineering.custom_class` | `training.yaml` |
| Custom Global Transformer | `BaseEstimator, TransformerMixin` (sklearn API) | `preprocessing.global_transformers[].custom_class` | `training.yaml` |
| Custom Inference | `BaseInference` | `inference.custom_class` | `inference.yaml` |

## 3. Custom ETL

### What It Is

An ETL (Extract-Transform-Load) is a data processing step in the pipeline. ETLs can read data from various sources, transform it, and save it to a target format. ETLs can depend on other ETLs, forming a directed acyclic graph (DAG) that executes in topological order.

### BaseETL Contract

```python
from abc import ABC, abstractmethod
import pandas as pd

class BaseETL(ABC):
    """Base class for custom ETL."""

    def __init__(self):
        """Initialize ETL instance."""
        pass

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """
        Extracts data from the source.

        Returns:
            pd.DataFrame: Raw data

        Raises:
            ETLError: If an error occurs during extraction
        """
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms and cleans the data.

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
        """
        Saves transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If an error occurs during loading
        """
        pass

    def run(self, output_path: str) -> pd.DataFrame:
        """
        Executes the complete ETL pipeline.

        Can be overridden to add additional logic.

        Args:
            output_path: Path to save the transformed data

        Returns:
            pd.DataFrame: Transformed DataFrame
        """
        # Default implementation: extract() -> transform() -> load()
```

### Minimal Example: SimpleFilterETL

```python
# src/data/custom_etl.py
from energizados.etl.base import BaseETL
import pandas as pd


class SimpleFilterETL(BaseETL):
    """ETL that removes rows with nulls and saves to parquet."""

    def __init__(self, input_path=None, output_path=None, **kwargs):
        super().__init__(**kwargs)
        self.input_path = input_path
        self.output_path = output_path

    def extract(self) -> pd.DataFrame:
        """Read raw data from CSV."""
        return pd.read_csv(self.input_path)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows with any null values."""
        return df.dropna()

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save to parquet format."""
        df.to_parquet(path, index=False)
```

Wire it in `config/etls.yaml`:
```yaml
etls:
  filter_data:
    enabled: true
    description: "Removes rows with null values"
    input: "data/raw/data.csv"
    output: "data/processed/clean.parquet"
    custom_class: "src.data.custom_etl.SimpleFilterETL"
    params:
      input_path: "data/raw/data.csv"
      output_path: "data/processed/clean.parquet"
    depends_on: []
```

### Advanced Example: MultiSourceETL with Error Handling

```python
# src/data/multi_source_etl.py
from energizados.etl.base import BaseETL
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MultiSourceETL(BaseETL):
    """ETL that merges multiple sources with error handling."""

    def __init__(self, source_paths=None, merge_key=None, **kwargs):
        super().__init__(**kwargs)
        self.source_paths = source_paths or []
        self.merge_key = merge_key

    def extract(self) -> pd.DataFrame:
        """Extract and merge multiple data sources."""
        dfs = []
        for path in self.source_paths:
            try:
                if path.endswith('.csv'):
                    df = pd.read_csv(path)
                elif path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                else:
                    raise ValueError(f"Unsupported file format: {path}")
                dfs.append(df)
                logger.info(f"Loaded {len(df)} rows from {path}")
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")
                raise

        if not dfs:
            raise ValueError("No data sources loaded successfully")

        return dfs

    def transform(self, df_list: list) -> pd.DataFrame:
        """Merge all DataFrames on the specified key."""
        if len(df_list) == 1:
            return df_list[0]

        merged = df_list[0]
        for df in df_list[1:]:
            merged = pd.merge(
                merged,
                df,
                on=self.merge_key,
                how='left'
            )
            logger.info(f"Merged: {len(merged)} rows")

        return merged

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save to parquet with compression."""
        df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"Saved {len(df)} rows to {path}")
```

Wire it in `config/etls.yaml` with dependencies:
```yaml
etls:
  consumos:
    enabled: true
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  clientes:
    enabled: true
    input: "data/raw/clientes.csv"
    output: "data/processed/clientes.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  merge_all:
    enabled: true
    description: "Merges consumos and clientes by id_cliente"
    input:
      - "@consumos"
      - "@clientes"
    output: "data/processed/merged.parquet"
    custom_class: "src.data.multi_source_etl.MultiSourceETL"
    params:
      source_paths: ["@consumos", "@clientes"]
      merge_key: "id_cliente"
    depends_on: ["consumos", "clientes"]
```

### ETL Dependencies with @etl_name Syntax

Reference other ETL outputs using the `@etl_name` syntax in the `input` field:

```yaml
etls:
  step1:
    input: "data/raw/source.csv"
    output: "data/processed/step1.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"

  step2:
    input: "@step1"  # References step1's output
    output: "data/processed/step2.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: ["step1"]  # Explicit dependency
```

## 4. Custom Feature Selector

### What It Is

A feature selector reduces the feature space before training by selecting the most relevant features. This can improve model performance, reduce overfitting, and speed up training.

### BaseFeatureSelector Contract

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd

class BaseFeatureSelector(ABC):
    """Base class for custom feature selection."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the selector.

        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.selected_features_ = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureSelector":
        """
        Learn which features to select.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: The fitted instance.
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform X keeping only selected features.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: DataFrame with selected features.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Fit and transform in one step.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            pd.DataFrame: Transformed DataFrame.
        """
        return self.fit(X, y).transform(X)

    def get_selected_features(self) -> list:
        """
        Return the list of selected features.

        Returns:
            list: List of selected feature names.

        Raises:
            ValueError: If fit() has not been called previously.
        """
        if self.selected_features_ is None:
            raise ValueError("Must call fit() first")
        return self.selected_features_
```

### Minimal Example: VarianceThresholdSelector

```python
# src/features/variance_selector.py
from energizados.feature_selection.base import BaseFeatureSelector
import pandas as pd


class VarianceThresholdSelector(BaseFeatureSelector):
    """Selects features with variance above a threshold."""

    def __init__(self, threshold=0.01, config=None):
        super().__init__(config)
        self.threshold = threshold

    def fit(self, X, y):
        """Select features with variance above threshold."""
        variances = X.var()
        self.selected_features_ = variances[variances > self.threshold].index.tolist()
        return self

    def transform(self, X):
        """Return only selected features."""
        return X[self.selected_features_]
```

Wire it in `config/training.yaml`:
```yaml
training:
  feature_engineering:
    feature_selection:
      enabled: true
      steps:
        - name: variance_selector
          method: variance  # Use custom implementation
          custom_class: "src.features.variance_selector.VarianceThresholdSelector"
          params:
            threshold: 0.01
```

### Advanced Example: BusinessRuleSelector

```python
# src/features/business_rule_selector.py
from energizados.feature_selection.base import BaseFeatureSelector
import pandas as pd


class BusinessRuleSelector(BaseFeatureSelector):
    """Feature selector based on domain knowledge and business rules."""

    def __init__(self, mandatory_features=None, correlation_threshold=0.3, config=None):
        super().__init__(config)
        self.mandatory_features = mandatory_features or []
        self.correlation_threshold = correlation_threshold

    def fit(self, X, y):
        """Select features using business rules and correlation."""
        # Always include mandatory features
        selected = self.mandatory_features.copy()

        # Calculate correlation with target for optional features
        optional = [c for c in X.columns if c not in self.mandatory_features]

        for col in optional:
            corr = abs(X[col].corr(y))
            if corr >= self.correlation_threshold:
                selected.append(col)

        # Remove features highly correlated with each other (deduplication)
        selected = self._remove_highly_correlated(X[selected])

        self.selected_features_ = selected
        return self

    def _remove_highly_correlated(self, df, threshold=0.9):
        """Remove features with correlation > threshold."""
        corr_matrix = df.corr().abs()
        upper_tri = corr_matrix.where(
            pd.DataFrame(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        )
        to_drop = [col for col in upper_tri.columns if any(upper_tri[col] > threshold)]
        return [c for c in df.columns if c not in to_drop]

    def transform(self, X):
        """Return only selected features."""
        return X[self.selected_features_]
```

Wire it in `config/training.yaml`:
```yaml
training:
  feature_engineering:
    feature_selection:
      enabled: true
      steps:
        - name: business_selector
          custom_class: "src.features.business_rule_selector.BusinessRuleSelector"
          params:
            mandatory_features: ["id_cliente", "zona", "tarifa"]
            correlation_threshold: 0.3
```

## 5. Custom Model

### What It Is

A custom model is any ML model that implements the `BaseModel` interface. This allows you to integrate models from any library (sklearn, xgboost, custom implementations) into the framework.

### BaseModel Contract

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict
import numpy as np
import pandas as pd


class BaseModel(ABC):
    """Base class for custom models."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the model.

        Args:
            config: Optional configuration dictionary.
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
        """
        Train the model.

        Args:
            X: Training features
            y: Training target
            X_val: Validation features (optional)
            y_val: Validation target (optional)

        Returns:
            self: Returns trained instance
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)

        Raises:
            ModelNotFittedError: If model is not fitted
        """
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            X: Features for prediction

        Returns:
            np.ndarray: Probabilities of the positive class

        Raises:
            ModelNotFittedError: If model is not fitted
        """
        pass

    def check_fitted(self):
        """Check that model is fitted.

        Raises:
            ModelNotFittedError: If model is not fitted
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)
```

### Minimal Example: SklearnModelAdapter

```python
# src/models/sklearn_adapter.py
from energizados.core.base import BaseModel
from sklearn.linear_model import LogisticRegression
import numpy as np


class SklearnModelAdapter(BaseModel):
    """Adapter for any sklearn estimator."""

    def __init__(self, estimator_class=None, estimator_params=None, config=None):
        super().__init__(config)
        self.estimator_class = estimator_class or LogisticRegression
        self.estimator_params = estimator_params or {}

    def fit(self, X, y, X_val=None, y_val=None):
        """Fit the sklearn estimator."""
        self.model_ = self.estimator_class(**self.estimator_params)
        self.model_.fit(X, y)
        self.is_fitted_ = True
        return self

    def predict(self, X):
        """Return binary predictions."""
        self.check_fitted()
        return self.model_.predict(X)

    def predict_proba(self, X):
        """Return probability of positive class."""
        self.check_fitted()
        return self.model_.predict_proba(X)[:, 1]
```

Wire it in `config/training.yaml`:
```yaml
training:
  models:
    - type: "sklearn_adapter"
      custom_class: "src.models.sklearn_adapter.SklearnModelAdapter"
      params:
        estimator_class: "sklearn.ensemble.RandomForestClassifier"
        estimator_params:
          n_estimators: 100
          max_depth: 10
          random_state: 42
```

### Advanced Example: CustomLightGBMModel

```python
# src/models/custom_lightgbm.py
from energizados.core.base import BaseModel
import lightgbm as lgb
import numpy as np


class CustomLightGBMModel(BaseModel):
    """LightGBM model with custom objective and early stopping."""

    def __init__(self, n_estimators=1000, learning_rate=0.05, early_stopping_rounds=30, config=None):
        super().__init__(config)
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.early_stopping_rounds = early_stopping_rounds

    def _custom_objective(self, y_true, y_pred):
        """Custom focal loss objective."""
        gamma = 2.0
        grad = y_true * (1 - y_pred) ** gamma - (1 - y_true) * y_pred ** gamma
        hess = gamma * y_true * (1 - y_pred) ** (gamma - 1) + gamma * (1 - y_true) * y_pred ** (gamma - 1)
        return grad, hess

    def fit(self, X, y, X_val=None, y_val=None):
        """Fit LightGBM with custom objective."""
        train_data = lgb.Dataset(X, label=y)

        eval_sets = [(train_data, 'train')]
        if X_val is not None and y_val is not None:
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            eval_sets.append((val_data, 'val'))

        params = {
            'objective': 'binary',
            'metric': 'auc',
            'learning_rate': self.learning_rate,
            'verbosity': -1,
        }

        self.model_ = lgb.train(
            params,
            train_data,
            num_boost_round=self.n_estimators,
            valid_sets=eval_sets,
            callbacks=[lgb.early_stopping(stopping_rounds=self.early_stopping_rounds, verbose=False)]
        )

        self.is_fitted_ = True
        return self

    def predict(self, X):
        """Return binary predictions."""
        self.check_fitted()
        probas = self.model_.predict(X)
        return (probas >= 0.5).astype(int)

    def predict_proba(self, X):
        """Return probability predictions."""
        self.check_fitted()
        return self.model_.predict(X)
```

Wire it in `config/training.yaml`:
```yaml
training:
  models:
    - name: "custom_lgbm"
      custom_class: "src.models.custom_lightgbm.CustomLightGBMModel"
      params:
        n_estimators: 1000
        learning_rate: 0.05
        early_stopping_rounds: 30
```

### Using Custom Models in Ensemble

Custom models can be used as base models in ensembles:

```yaml
training:
  models:
    - name: "sklearn_rf"
      custom_class: "src.models.sklearn_adapter.SklearnModelAdapter"
      params:
        estimator_class: "sklearn.ensemble.RandomForestClassifier"
        estimator_params:
          n_estimators: 100

    - name: "custom_lgbm"
      custom_class: "src.models.custom_lightgbm.CustomLightGBMModel"
      params:
        n_estimators: 500

  ensemble:
    method: "stacking"
    meta_learner:
      type: "logistic_regression"
      params:
        C: 1.0
    use_val_as_oof: true
```

## 6. Custom Feature Engineering (Full Pipeline)

### When to Use This vs Individual Custom Transformers

Use a custom `BaseFeatureEngineering` implementation when you need to:
- Replace the entire preprocessing + feature selection pipeline with a completely custom approach
- Implement complex interactions between preprocessing and feature selection steps
- Optimize performance by fusing multiple operations

Use individual custom transformers (per-column or global) when you only need to add or replace a specific transformation within the default pipeline.

### BaseFeatureEngineering Contract

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional
import pandas as pd

class BaseFeatureEngineering(ABC):
    """Base class for custom feature engineering pipelines."""

    def __init__(self, config: Optional[Dict] = None):
        """Initializes the feature pipeline.

        Args:
            config: Optional configuration dictionary.
        """
        self.config = config or {}
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureEngineering":
        """Learns preprocessing and feature selection transformations.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            self: Returns trained instance.
        """
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Applies preprocessing and feature selection to data.

        Args:
            X: DataFrame to transform.

        Returns:
            pd.DataFrame: Transformed DataFrame.

        Raises:
            ValueError: If fit() was not called previously.
        """
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """Fit and transform in a single step.

        Args:
            X: Training features.
            y: Training target.

        Returns:
            pd.DataFrame: Transformed DataFrame.
        """
        return self.fit(X, y).transform(X)

    def save(self, path: str) -> None:
        """Saves the complete pipeline to disk.

        Args:
            path: Path where to save the pipeline (.pkl extension).

        Raises:
            ValueError: If fit() was not called previously.
        """
        if not self.is_fitted_:
            raise ValueError("You must call fit() before saving pipeline")

        from energizados.core.utils.secure_pickle import secure_dump
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        secure_dump(self, path)

    @classmethod
    def load(cls, path: str) -> "BaseFeatureEngineering":
        """Loads a saved pipeline from disk.

        Args:
            path: Path to the saved pipeline file.

        Returns:
            BaseFeatureEngineering: Loaded pipeline.
        """
        from energizados.core.utils.secure_pickle import secure_load
        return secure_load(path)

    def get_feature_names_out(self) -> list:
        """Returns feature names after transformations.

        Returns:
            list: List of output feature names.

        Raises:
            ValueError: If fit() was not called previously.
        """
        if not self.is_fitted_:
            raise ValueError("You must call fit() first")
        return self._get_feature_names_out()

    def _get_feature_names_out(self) -> list:
        """Internal method to get feature names.

        Can be overridden by subclasses.

        Returns:
            list: List of feature names.
        """
        return []
```

### Example: DomainSpecificFeatureEngineering

```python
# src/features/domain_feature_engineering.py
from energizados.feature_engineering.base import BaseFeatureEngineering
from sklearn.preprocessing import StandardScaler
import pandas as pd


class DomainSpecificFeatureEngineering(BaseFeatureEngineering):
    """Custom pipeline for electricity fraud detection features."""

    def __init__(self, config=None):
        super().__init__(config)
        self.scaler = StandardScaler()
        self.feature_cols = None

    def fit(self, X, y):
        """Learn feature engineering transformations."""
        # Select numeric columns for scaling
        numeric_cols = X.select_dtypes(include=['int64', 'float64']).columns
        self.feature_cols = numeric_cols.tolist()

        # Fit scaler on numeric features
        self.scaler.fit(X[self.feature_cols])

        self.is_fitted_ = True
        return self

    def transform(self, X):
        """Apply feature engineering."""
        # Make a copy to avoid modifying original
        X_transformed = X.copy()

        # Scale numeric features
        X_transformed[self.feature_cols] = self.scaler.transform(X[self.feature_cols])

        return X_transformed

    def _get_feature_names_out(self):
        """Return output feature names."""
        return self.feature_cols
```

Wire it in `config/training.yaml`:
```yaml
training:
  feature_engineering:
    enabled: true
    custom_class: "src.features.domain_feature_engineering.DomainSpecificFeatureEngineering"
    params:
      # Any parameters for your custom pipeline
```

## 7. Custom Global Transformers

### What They Are

Global transformers operate on the entire dataset after column-level preprocessing. They differ from column-level transformers in that:
- They access the full DataFrame (all columns)
- They can create new features that depend on multiple columns
- They execute AFTER per-column transformers in the preprocessing pipeline

### How They Differ from Column-Level Transformers

| Aspect | Column-Level Transformers | Global Transformers |
|---------|--------------------------|---------------------|
| Scope | Operate on individual columns | Operate on entire DataFrame |
| Order | Execute first | Execute after column transformers |
| Access | Only see their assigned column(s) | See all columns |
| Use Cases | Encoding, scaling per-column | Feature interactions, aggregations |

### Example: CustomInteractionTransformer

```python
# src/preprocessing/interaction_transformer.py
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd
import numpy as np


class CustomInteractionTransformer(BaseEstimator, TransformerMixin):
    """Creates interaction features between specified columns."""

    def __init__(self, interactions=None):
        """
        Initialize interaction transformer.

        Args:
            interactions: List of tuples, e.g., [("col1", "col2", "*"), ("col3", "col4", "/")]
        """
        self.interactions = interactions or []

    def fit(self, X, y=None):
        """No-op fit - stateless transformer."""
        return self

    def transform(self, X):
        """Create interaction features."""
        X_transformed = X.copy()

        for col1, col2, operation in self.interactions:
            if col1 not in X.columns or col2 not in X.columns:
                continue

            if operation == '*':
                X_transformed[f'{col1}_x_{col2}'] = X[col1] * X[col2]
            elif operation == '+':
                X_transformed[f'{col1}_plus_{col2}'] = X[col1] + X[col2]
            elif operation == '-':
                X_transformed[f'{col1}_minus_{col2}'] = X[col1] - X[col2]
            elif operation == '/':
                # Avoid division by zero
                with np.errstate(divide='ignore', invalid='ignore'):
                    X_transformed[f'{col1}_div_{col2}'] = np.where(
                        X[col2] != 0,
                        X[col1] / X[col2],
                        0
                    )

        return X_transformed
```

Wire it in `config/training.yaml`:
```yaml
training:
  feature_engineering:
    preprocessing:
      columns:
        # ... column-level preprocessing

      global_transformers:
        - custom_class: "src.preprocessing.interaction_transformer.CustomInteractionTransformer"
          params:
            interactions:
              - ["consumption_mean", "consumption_std", "*"]
              - ["peak_hour", "off_peak_hour", "/"]
```

## 8. Custom Inference

### What It Is

Custom inference implementations allow you to control how predictions are made on new data. You can:
- Apply custom thresholding strategies
- Add business rule post-processing
- Implement custom prediction workflows (e.g., batch processing, API calls)
- Handle edge cases and error scenarios

### BaseInference Contract

```python
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from energizados.core.base import BaseModel


class BaseInference(ABC):
    """Base class for inference and prediction."""

    @abstractmethod
    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make binary predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Binary predictions (0 or 1)
        """
        pass

    @abstractmethod
    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Make probability predictions.

        Args:
            model: Trained model
            data: Data for prediction

        Returns:
            np.ndarray: Probabilities of the positive class
        """
        pass

    def load_model(self, model_path: str) -> BaseModel:
        """
        Load a trained model from disk.

        Args:
            model_path: Path to model file

        Returns:
            BaseModel: Loaded model
        """
        raise NotImplementedError("Subclasses must implement load_model")

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """
        Save predictions to file.

        Args:
            predictions: Predictions to save
            output_path: Output path
        """
        raise NotImplementedError("Subclasses must implement save_predictions")
```

### Minimal Example: DefaultInference Wrapper

```python
# src/inference/custom_inference.py
from energizados.inference.base import BaseInference
from energizados.core.base import BaseModel
import pandas as pd
import numpy as np


class SimpleInference(BaseInference):
    """Basic inference wrapper using model's predict methods."""

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Use model's predict method directly."""
        return model.predict(data)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Use model's predict_proba method directly."""
        return model.predict_proba(data)
```

### Advanced Example: ThresholdedInference

```python
# src/inference/thresholded_inference.py
from energizados.inference.base import BaseInference
from energizados.core.base import BaseModel
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ThresholdedInference(BaseInference):
    """Inference with custom threshold and business rules."""

    def __init__(self, threshold=0.5, min_consumption=None, max_consumption=None):
        """
        Initialize thresholded inference.

        Args:
            threshold: Probability threshold for positive prediction
            min_consumption: Minimum consumption to flag as fraud (optional)
            max_consumption: Maximum consumption to flag as fraud (optional)
        """
        self.threshold = threshold
        self.min_consumption = min_consumption
        self.max_consumption = max_consumption

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """
        Apply threshold and business rules.

        Business rules:
        1. Apply probability threshold
        2. Override to 0 if consumption outside valid range
        """
        probas = model.predict_proba(data)

        # Apply threshold
        predictions = (probas >= self.threshold).astype(int)

        # Apply business rules if consumption column exists
        if self.min_consumption is not None and 'consumption_mean' in data.columns:
            invalid_consumption = (data['consumption_mean'] < self.min_consumption).values
            predictions[invalid_consumption] = 0

        if self.max_consumption is not None and 'consumption_mean' in data.columns:
            invalid_consumption = (data['consumption_mean'] > self.max_consumption).values
            predictions[invalid_consumption] = 0

        logger.info(f"Applied threshold {self.threshold}: {predictions.sum()} positives")
        return predictions

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Return raw probabilities from model."""
        return model.predict_proba(data)
```

Wire it in `config/inference.yaml`:
```yaml
inference:
  enabled: true
  input_path: "data/processed/new_data.parquet"
  output_path: "output/predictions.csv"
  custom_class: "src.inference.thresholded_inference.ThresholdedInference"
  params:
    threshold: 0.7
    min_consumption: 10.0
    max_consumption: 5000.0
```

## 9. The Security Allowlist

### Why It Exists

The `custom_class` plugin system uses Python's dynamic import capability to load classes from string references (e.g., `"src.models.custom.CustomModel"`). Without controls, this could allow arbitrary code execution from untrusted YAML configuration files.

The allowlist ensures that only classes from trusted module prefixes can be imported dynamically.

### How `import_utils.py` Works

The `import_class` function in `src/energizados/core/utils/import_utils.py`:

1. **Checks the allowlist**: Verifies the class path starts with an allowed prefix
2. **Raises ImportError** if not allowed: Shows which prefixes are permitted
3. **Attempts import**: Tries to import the module and class
4. **Adds project directories to sys.path temporarily**: Supports local projects not installed as packages

### What Paths Are Allowed by Default

```python
ALLOWED_PREFIXES = [
    "energizados.",      # Framework modules
    "src.",              # Generated project src/ directory
    "data.",             # Custom data modules
    "features.",          # Custom feature modules
    "models.",           # Custom model modules
    "inference.",         # Custom inference modules
    "preprocessing.",     # Custom preprocessing modules
    "etl.",              # Custom ETL modules
    "tests.",             # Test modules
]
```

### How to Add New Paths

If you need to add new module prefixes, edit `src/energizados/core/utils/import_utils.py`:

```python
ALLOWED_PREFIXES = [
    "energizados.",
    "src.",
    "data.",
    "features.",
    "models.",
    "inference.",
    "preprocessing.",
    "etl.",
    "tests.",
    "my_custom_prefix.",  # Add your custom prefix here
]
```

### What Happens When a Class Is Not in the Allowlist

You'll get an `ImportError` with a clear message:

```
ImportError: Class 'malicious.package.Attacker' is not in the allowed module prefixes.
Allowed prefixes: ['energizados.', 'src.', 'data.', 'features.', 'models.', 'inference.', 'preprocessing.', 'etl.', 'tests.']
```

## 10. Testing Your Extensions

### Pattern for Testing a Custom ETL

```python
# tests/test_custom_etl.py
import pytest
import pandas as pd
from pathlib import Path

from src.data.custom_etl import SimpleFilterETL


@pytest.fixture
def sample_data(temp_dir):
    """Create sample CSV data for testing."""
    data = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'value': [10, 20, None, 40, 50],
        'category': ['A', 'B', 'C', 'D', 'E']
    })
    csv_path = temp_dir / "test_data.csv"
    data.to_csv(csv_path, index=False)
    return csv_path


def test_simple_filter_etl(sample_data, temp_dir):
    """Test SimpleFilterETL removes rows with nulls."""
    output_path = temp_dir / "output.parquet"

    etl = SimpleFilterETL(
        input_path=str(sample_data),
        output_path=str(output_path)
    )

    df = etl.run(str(output_path))

    # Assert row with null is removed
    assert len(df) == 4
    assert df['value'].isnull().sum() == 0

    # Assert output file exists
    assert Path(output_path).exists()
```

### Pattern for Testing a Custom Model

```python
# tests/test_custom_model.py
import pytest
import numpy as np

from energizados.core.base import BaseModel
from src.models.sklearn_adapter import SklearnModelAdapter


def test_sklearn_adapter_fit_predict(synthetic_classification_data):
    """Test SklearnModelAdapter can fit and predict."""
    X, y = synthetic_classification_data

    model = SklearnModelAdapter(
        estimator_class="sklearn.ensemble.RandomForestClassifier",
        estimator_params={"n_estimators": 10}
    )

    # Fit the model
    model.fit(X, y)
    assert model.is_fitted_

    # Test predict
    predictions = model.predict(X)
    assert predictions.shape[0] == X.shape[0]
    assert set(predictions).issubset({0, 1})

    # Test predict_proba
    probas = model.predict_proba(X)
    assert probas.shape[0] == X.shape[0]
    assert all((0 <= probas) & (probas <= 1))


def test_custom_model_with_validation(synthetic_classification_data):
    """Test model with validation data."""
    X, y = synthetic_classification_data
    X_train, X_val = X[:80], X[80:]
    y_train, y_val = y[:80], y[80:]

    model = SklearnModelAdapter(
        estimator_class="sklearn.linear_model.LogisticRegression",
        estimator_params={"max_iter": 100}
    )

    # Fit with validation data
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
    assert model.is_fitted_

    # Predict on validation set
    predictions = model.predict(X_val)
    assert len(predictions) == len(X_val)
```

### Available Fixtures from `conftest.py`

| Fixture | Returns | Description |
|----------|----------|-------------|
| `synthetic_classification_data` | (X, y) | 100 samples, 10 features, binary target |
| `synthetic_classification_data_small` | (X, y) | 20 samples for quick tests |
| `mock_trained_model` | MagicMock | Mock with predict/predict_proba methods |
| `mock_trained_model_with_cols` | function | Returns mock for specific columns |
| `temp_dir` | Path | Auto-cleaned temporary directory |
| `sample_csv_file` | Path | CSV with synthetic data |
| `sample_parquet_file` | Path | Parquet with synthetic data |
| `nn_adapter_data` | (X, y, features, spents) | Data for NN/LSTM adapters |

### How to Run Only Your Extension's Tests

```bash
# Run specific test file
pytest tests/test_custom_etl.py -v

# Run specific test function
pytest tests/test_custom_model.py::test_sklearn_adapter_fit_predict -v

# Run all tests in a directory
pytest tests/test_my_extensions/ -v

# Run with coverage
pytest tests/test_custom_model.py --cov=src.models -v

# Run with verbose output and show print statements
pytest tests/test_custom_etl.py -v -s
```

### Test Structure Best Practices

1. **Use descriptive test names**: `test_<functionality>_<expected_behavior>`
2. **Leverage fixtures**: Use `synthetic_classification_data`, `temp_dir`, etc.
3. **Test both success and error cases**: Use `pytest.raises` for expected errors
4. **Keep tests isolated**: Each test should work independently
5. **Use markers**: Add `@pytest.mark.unit`, `@pytest.mark.slow` for categorization

```python
import pytest


@pytest.mark.unit
def test_etl_extract_success(sample_data, temp_dir):
    """Test extract method works correctly."""
    etl = SimpleFilterETL()
    df = etl.extract()
    assert len(df) == 5


@pytest.mark.unit
def test_etl_with_missing_file(temp_dir):
    """Test ETL raises error on missing file."""
    etl = SimpleFilterETL(input_path="nonexistent.csv")
    with pytest.raises(FileNotFoundError):
        etl.extract()


@pytest.mark.slow
def test_etl_large_dataset():
    """Test ETL performance with large dataset."""
    # Slow test that processes lots of data
    pass
```
