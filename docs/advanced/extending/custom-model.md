# Custom Models

## What It Is

A custom model is any ML model that implements the `BaseModel` interface. This allows you to integrate models from any library (sklearn, xgboost, custom implementations) into the framework.

## BaseModel Contract

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

## Minimal Example: SklearnModelAdapter

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

## Advanced Example: CustomLightGBMModel

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

## Using Custom Models in Ensemble

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

## Testing Custom Models

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

Run tests:
```bash
pytest tests/test_custom_model.py -v
```

## Available Built-in Models

The framework includes several built-in model adapters:

| Model | Class | Description |
|-------|-------|-------------|
| LightGBM | `LGBMModel` | Gradient boosting with native categorical support |
| CatBoost | `CATModel` | Gradient boosting with automatic categorical handling |
| Neural Network | `NNModel` | Feedforward neural network (TensorFlow/Keras) |
| LSTM | `LSTMNNModel` | LSTM for sequential consumption data |
| Simple Trend | `SimpleTrendAdapter` | Rule-based model detecting dramatic consumption drops |
| Simple Constant | `SimpleConstantAdapter` | Rule-based model identifying constant consumption patterns |

## See Also

- [Custom ETLs](custom-etl.md) - Learn about ETL extensions
- [Custom Feature Engineering](custom-feature-engineering.md) - Feature pipeline customization
- [Custom Inference](custom-inference.md) - Inference implementations
- [Ensemble Models](../../user-guide/configuration/training.md#ensemble) - Using multiple models

---

← [Custom ETLs](custom-etl.md) | [Custom Feature Engineering](custom-feature-engineering.md) →
