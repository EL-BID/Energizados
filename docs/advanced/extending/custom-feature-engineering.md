# Custom Feature Engineering Pipeline

## When to Use This vs Individual Custom Transformers

Use a custom `BaseFeatureEngineering` implementation when you need to:

- Replace the entire preprocessing + feature selection pipeline with a completely custom approach
- Implement complex interactions between preprocessing and feature selection steps
- Optimize performance by fusing multiple operations

Use individual custom transformers (per-column or global) when you only need to add or replace a specific transformation within the default pipeline.

## BaseFeatureEngineering Contract

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

## Example: DomainSpecificFeatureEngineering

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

Wire it in `config/train.yaml`:

```yaml
train:
  feature_engineering:
    enabled: true
    custom_class: "features.domain_feature_engineering.DomainSpecificFeatureEngineering"
    params:
      # Any parameters for your custom pipeline
```

## Customizing Specific Steps

You can also customize specific steps within the feature engineering pipeline:

### Per-Column Custom Transformer

```yaml
train:
  feature_engineering:
    preprocessing:
      columns:
        actividad:
          - custom_class: "preprocessing.CustomCardinalityReducer"
            params:
              threshold: 0.001
          - to_dummy: {}
```

### Full Preprocessing Replacement

```yaml
train:
  feature_engineering:
    preprocessing:
      custom_class: "preprocessing.CustomPreprocessing"
      params:
        custom_param: value
```

### Custom Feature Selector

```yaml
train:
  feature_engineering:
    feature_selection:
      enabled: true
      steps:
        - name: custom_selector
          custom_class: "features.CustomFeatureSelector"
          params:
            param1: value1
```

## Available Preprocessing Transformations

> **Note:** Global transformers (listed below) are documented in full detail in the [Training Configuration → Global Transformers](../../user-guide/configuration/train.md#global-transformers) section, including the pre/post encoding stage distinction.

| Transformation | Description | Parameters |
|----------------|-------------|------------|
| `cardinality_reducer` | Groups infrequent categories into "otros" | `threshold` (float, class default=0.1; YAML template default=0.001) |
| `to_dummy` | One-hot encoding | None |
| `target_encoding` | Replaces category with target probability (requires y) | `w` (int, default=20) |
| `ordinal_encoding` | Ordinal encoding (0, 1, 2, ...) | sklearn OrdinalEncoder params |
| `minmax_scaler_row` | Row-wise MinMax scaling | `feature_range` (tuple, default=[0,1]) |
| `cast_dtype` | Converts column to a pandas dtype | `dtype` (str, default=`"float32"`) |
| `tsfel_vars` | Time series feature extraction using tsfel | `num_periodos` (int, default=12), `features` (dict, default=None — inline `{domain: [names]}` selection; if null uses all domains and logs the list), `periods_suffix` (str, default="_anterior"), `n_jobs` (int, default=1), `chunk_size` (int, default=500), `cache_dir` (str, default=None) |
| `extra_vars` | Statistical features for different time windows | `num_periodos` (int, default=3), `periods_suffix` (str, default="_anterior"), `count_nulls` (bool, default=False) |
| `group_relative_consumption` | **[pre-encoding]** Consumption relative to group statistics (e.g. actividad, tarifa, zona). Generates `prop_cons_{window}_{metric}_{group_column}` | `group_column` (str, default="actividad"), `windows` (list[int], default=[3,6,12]), `metrics` (list[str], default=["mean","max"]), `periods_suffix` (str, default="_anterior") |
| `seasonal_anomaly` | **[pre-encoding]** Seasonal z-score for each month vs group mean/std for that calendar month. Generates `seasonal_anomaly_{i}_anterior` | `group_column` (str, default="actividad"), `date_column` (str, required), `periods_suffix` (str, default="_anterior") |
| `clip_outliers` | Clips extreme values in consumption columns (run first among post-encoding transformers) | `threshold` (float, default=100000), `columns` (list, default=null), `periods_suffix` (str, default="_anterior") |
| `consumption_patterns` | Domain-specific fraud detection features (diff ratios, zero ratio, z-score, slope, consistency, drastic changes, autocorrelation, seasonal ratio) | `num_periodos` (int, default=12), `periods_suffix` (str, default="_anterior"), plus enable flags (see train.md) |
| `if_score` | Isolation Forest anomaly score (inverted; higher = more anomalous) | `n_estimators` (int, default=100), `contamination` (float/str, default="auto"), `contamination_from_target` (bool, default=false), plus other params (see train.md) |
| `temporal_features` | Calendar features from a date column with flat (`month=7`) and/or cyclic (`month_sin/cos`) encoding. Cyclic encoding preserves calendar circularity (Dec & Jan are neighbors) | `date_column` (str, required), `features` (list, default=["month","quarter","week","dayofweek"]), `encoding` (str, default="both" — "flat"/"cyclic"/"both"), `drop_date_column` (bool, default=false) |
| `geo_features` | Not a built-in key. The `GeoFeatures` transformer provides clustering (`geo_cluster`), IBGE hierarchy, and distances — use it via `GeoFeaturesETL` in `etl.yaml` (recommended; handles file I/O), or directly via `custom_class` here with `include_cluster: true`. | `custom_class` path + `GeoFeatures` params (`include_cluster`, `n_clusters`, `regions_file`, `geo_model_path`, …) |

## Global Transformers

Global transformers operate on the entire dataset after column-level preprocessing. They can create features that depend on multiple columns.

```yaml
train:
  feature_engineering:
    preprocessing:
      columns:
        # ... column-based preprocessing

      global_transformers:
        # Time series feature extraction
        - tsfel_vars:
            num_periodos: 12
            features:
              statistical:
                - Mean
                - Standard deviation
                - Max
                - Min
              temporal:
                - Slope
                - Zero crossing rate
            periods_suffix: "_anterior"

        # Statistical features for different time windows
        - extra_vars:
            num_periodos: 3
        - extra_vars:
            num_periodos: 6
        - extra_vars:
            num_periodos: 12

        # Consumption relative to peer group (e.g. actividad, tarifa, zona)
        - group_relative_consumption:
            group_column: "actividad"
            windows: [3, 6, 12]
            metrics: ["mean", "max"]
            periods_suffix: "_anterior"

        # Seasonal anomaly: z-score vs group mean/std for each calendar month
        - seasonal_anomaly:
            group_column: "actividad"
            date_column: "fecha_inspeccion"
            periods_suffix: "_anterior"

        # Custom global transformer
        - custom_class: "preprocessing.CustomGlobalTransformer"
          params:
            custom_param: value
```

See [Custom Preprocessing](custom-preprocessing.md) for more details on global transformers.

## Testing Custom Feature Engineering

```python
# tests/test_custom_feature_engineering.py
import pytest
import pandas as pd

from features.domain_feature_engineering import DomainSpecificFeatureEngineering


def test_custom_feature_engineering_fit_transform(synthetic_classification_data):
    """Test custom feature engineering pipeline."""
    X, y = synthetic_classification_data

    # Initialize and fit
    fe = DomainSpecificFeatureEngineering()
    fe.fit(X, y)

    # Transform data
    X_transformed = fe.transform(X)

    # Assert shape preserved
    assert X_transformed.shape[0] == X.shape[0]

    # Assert feature names available
    feature_names = fe.get_feature_names_out()
    assert len(feature_names) > 0

    # Test save/load
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
        fe.save(f.name)
        fe_loaded = DomainSpecificFeatureEngineering.load(f.name)

        X_loaded = fe_loaded.transform(X)
        pd.testing.assert_frame_equal(X_transformed, X_loaded)
```

Run tests:

```bash
pytest tests/test_custom_feature_engineering.py -v
```

## See Also

- [Custom Preprocessing](custom-preprocessing.md) - Custom column and global transformers
- [Custom Models](custom-model.md) - Model implementations
- [Feature Engineering Guide](../../user-guide/configuration/train.md#feature-engineering) - Available transformations and usage

---

← [Custom Models](custom-model.md) | [Custom Preprocessing](custom-preprocessing.md) →
