# Custom Inference

## What It Is

Custom inference implementations allow you to control how predictions are made on new data. You can:
- Apply custom thresholding strategies
- Add business rule post-processing
- Implement custom prediction workflows (e.g., batch processing, API calls)
- Handle edge cases and error scenarios

## BaseInference Contract

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
```

## Minimal Example: DefaultInference Wrapper

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

## Advanced Example: ThresholdedInference

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

### Wire It in Configuration

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

## Loading Models and Saving Predictions

You can also implement custom model loading and prediction saving:

```python
# src/inference/batch_inference.py
from energizados.inference.base import BaseInference
from energizados.core.base import BaseModel
import pandas as pd
import numpy as np
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BatchInference(BaseInference):
    """Batch inference with model loading and prediction saving."""

    def __init__(self, batch_size=1000):
        """Initialize batch inference.

        Args:
            batch_size: Number of samples to process at once.
        """
        self.batch_size = batch_size

    def load_model(self, model_path: str) -> BaseModel:
        """Load model from pickle file."""
        from energizados.core.utils.secure_pickle import secure_load
        logger.info(f"Loading model from {model_path}")
        return secure_load(model_path)

    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        """Save predictions to CSV with index."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        df = pd.DataFrame({'prediction': predictions})
        df.to_csv(output_path, index=True)
        logger.info(f"Saved {len(predictions)} predictions to {output_path}")

    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Predict in batches for large datasets."""
        all_predictions = []

        for i in range(0, len(data), self.batch_size):
            batch = data.iloc[i:i+self.batch_size]
            batch_pred = model.predict(batch)
            all_predictions.append(batch_pred)
            logger.debug(f"Processed batch {i//self.batch_size + 1}")

        return np.concatenate(all_predictions)

    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        """Predict probabilities in batches."""
        all_probas = []

        for i in range(0, len(data), self.batch_size):
            batch = data.iloc[i:i+self.batch_size]
            batch_proba = model.predict_proba(batch)
            all_probas.append(batch_proba)
            logger.debug(f"Processed batch {i//self.batch_size + 1}")

        return np.concatenate(all_probas)
```

### Run Batch Inference

```python
# src/run/batch_inference_script.py
from src.inference.batch_inference import BatchInference
import pandas as pd

# Initialize custom inference
inference = BatchInference(batch_size=5000)

# Load data
data = pd.read_parquet("data/processed/new_data.parquet")

# Load model
model = inference.load_model("output/train-20240101_1200/models/model.pkl")

# Make predictions
predictions = inference.predict(model, data)
probas = inference.predict_proba(model, data)

# Save results
inference.save_predictions(predictions, "output/predictions.csv")
```

## Testing Custom Inference

```python
# tests/test_custom_inference.py
import pytest
import pandas as pd
import numpy as np

from src.inference.thresholded_inference import ThresholdedInference
from energizados.modeling.adapters import LGBMModelAdapter


@pytest.fixture
def trained_model(synthetic_classification_data):
    """Create a simple trained model for testing."""
    X, y = synthetic_classification_data
    model = LGBMModelAdapter(cols_for_model=X.columns.tolist(), hyperparams={"n_estimators": 10})
    model.fit(X, y)
    return model


def test_thresholded_inference_basic(trained_model, synthetic_classification_data):
    """Test thresholded inference with custom threshold."""
    X, y = synthetic_classification_data
    inference = ThresholdedInference(threshold=0.7)

    predictions = inference.predict(trained_model, X)
    probas = inference.predict_proba(trained_model, X)

    # Check shapes
    assert len(predictions) == len(X)
    assert len(probas) == len(X)

    # Check that predictions are binary
    assert set(predictions).issubset({0, 1})

    # Check that threshold is applied
    expected = (probas >= 0.7).astype(int)
    np.testing.assert_array_equal(predictions, expected)


def test_thresholded_inference_with_business_rules(trained_model):
    """Test inference with business rules."""
    # Create data with consumption column
    data = pd.DataFrame({
        'feature1': np.random.randn(100),
        'consumption_mean': np.concatenate([
            np.full(50, 5.0),   # Below minimum
            np.full(30, 6000.0), # Above maximum
            np.full(20, 100.0)   # Valid range
        ])
    })

    inference = ThresholdedInference(
        threshold=0.5,
        min_consumption=10.0,
        max_consumption=5000.0
    )

    predictions = inference.predict(trained_model, data)

    # First 50 should be overridden to 0 (below minimum)
    assert np.all(predictions[:50] == 0)

    # Next 30 should be overridden to 0 (above maximum)
    assert np.all(predictions[50:80] == 0)
```

Run tests:
```bash
pytest tests/test_custom_inference.py -v
```

## Available Built-in Inference

The framework includes a built-in inference implementation:

| Class | Description | Location |
|-------|-------------|----------|
| `DefaultInference` | Standard inference using model's predict methods | `src/energizados/inference/default.py` |

## See Also

- [Custom Models](custom-model.md) - Model implementations
- [Custom ETLs](custom-etl.md) - ETL extensions
- [Inference Guide](../../user-guide/configuration/inference.md) - Running inference

---

← [Custom Preprocessing](custom-preprocessing.md) | [Extending Framework](../extending/) →
