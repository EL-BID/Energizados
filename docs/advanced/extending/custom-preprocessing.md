# Custom Preprocessing Transformers

## Custom Column Transformers

### What They Are

Column transformers operate on individual columns or sets of columns during the preprocessing phase. They are applied to specific columns defined in the configuration.

### How to Create a Custom Column Transformer

Custom column transformers must follow the scikit-learn transformer API:

```python
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd
import numpy as np


class CustomColumnTransformer(BaseEstimator, TransformerMixin):
    """Custom transformer for specific columns."""

    def __init__(self, param1=default_value, param2=default_value):
        """Initialize transformer with parameters."""
        self.param1 = param1
        self.param2 = param2

    def fit(self, X, y=None):
        """Learn any parameters from the data."""
        # Store learned parameters
        self.learned_param_ = X.mean()
        return self

    def transform(self, X):
        """Apply transformation to the data."""
        # Return transformed DataFrame
        return X * self.param1
```

### Wire It in Configuration

```yaml
train:
  feature_engineering:
    preprocessing:
      columns:
        column_name:
          - custom_class: "preprocessing.CustomColumnTransformer"
            params:
              param1: value1
              param2: value2
```

## Custom Global Transformers

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

### Wire It in Configuration

```yaml
train:
  feature_engineering:
    preprocessing:
      columns:
        # ... column-level preprocessing

      global_transformers:
        - custom_class: "preprocessing.interaction_transformer.CustomInteractionTransformer"
          params:
            interactions:
              - ["consumption_mean", "consumption_std", "*"]
              - ["peak_hour", "off_peak_hour", "/"]
```

### Controlling the Execution Stage

By default, custom global transformers run **after** column encoding (`pipeline_stage = "post"`). If your transformer needs to see original categorical columns (e.g., to `groupby("actividad")` before it becomes `actividad_prob` after `target_encoding`), declare `pipeline_stage = "pre"` as a class attribute:

```python
class MyGroupTransformer(BaseEstimator, TransformerMixin):
    pipeline_stage = "pre"  # runs before column_transformer

    def fit(self, X, y=None):
        # X still has the original categorical "actividad" here
        self.stats_ = X.groupby("actividad")["1_anterior"].mean()
        return self

    def transform(self, X):
        df = X.copy()
        df["my_feature"] = df["actividad"].map(self.stats_)
        return df
```

The framework automatically splits `global_transformers` into two groups and assembles the pipeline as:

```
[pre-encoding transformers] → column_transformer → [post-encoding transformers]
```

No YAML changes are needed — the stage is entirely declared in Python.

## The Security Allowlist

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

The default allowlist was **narrowed for security** to the two framework-owned prefixes:

```python
# src/energizados/core/utils/import_utils.py
ALLOWED_PREFIXES = {
    "energizados.",      # Framework modules
    "src.",              # Generated project src/ directory
}
```

Previously broader prefixes (`data.`, `features.`, `models.`, `inference.`, `preprocessing.`, `etl.`, `tests.`) are **no longer allowed by default**. If your project uses custom module prefixes, register them explicitly as shown below.

### How to Add New Paths

Do **not** edit `import_utils.py`. Register custom prefixes at runtime with `register_allowed_prefix()`, before any framework usage (it is not thread-safe):

```python
from energizados.core.utils.import_utils import register_allowed_prefix

# Register each custom prefix you need (the trailing dot is added automatically)
register_allowed_prefix("data")          # → allows "data.CustomETL"
register_allowed_prefix("features")      # → allows "features.CustomSelector"
register_allowed_prefix("models")        # → allows "models.CustomModel"
register_allowed_prefix("ml_models")     # → any prefix you control
```

> **Migration note:** If you are upgrading from an older version where prefixes like `data.`, `features.`, or `models.` were allowed by default, add the matching `register_allowed_prefix(...)` calls during your project setup (before importing/using the framework) — the built-in allowlist now contains only `energizados.` and `src.`.

!!! warning "Security Warning"

    Only register module prefixes that you control or trust. Never add wildcards or overly broad prefixes.

### What Happens When a Class Is Not in the Allowlist

You'll get a `ConfigurationError` (an `EnergizadosError` subclass) with a clear message:

```
ConfigurationError: Class 'malicious.package.Attacker' is not in the allowed module prefixes. Allowed: ['energizados.', 'src.']
```

## Testing Custom Transformers

```python
# tests/test_custom_transformers.py
import pytest
import pandas as pd

from preprocessing.interaction_transformer import CustomInteractionTransformer


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    return pd.DataFrame({
        'col1': [1, 2, 3],
        'col2': [4, 5, 6],
        'col3': [7, 8, 9]
    })


def test_custom_interaction_transformer(sample_data):
    """Test CustomInteractionTransformer creates interaction features."""
    transformer = CustomInteractionTransformer(
        interactions=[("col1", "col2", "*"), ("col1", "col2", "+")]
    )

    result = transformer.fit_transform(sample_data)

    # Check that interaction columns were created
    assert 'col1_x_col2' in result.columns
    assert 'col1_plus_col2' in result.columns

    # Check values
    expected_product = sample_data['col1'] * sample_data['col2']
    pd.testing.assert_series_equal(result['col1_x_col2'], expected_product)
```

Run tests:
```bash
pytest tests/test_custom_transformers.py -v
```

## See Also

- [Custom Feature Engineering](custom-feature-engineering.md) - Full pipeline customization
- [Custom ETLs](custom-etl.md) - ETL implementations
- [Feature Engineering Guide](../../user-guide/configuration/train.md#feature-engineering) - Available transformations

---

← [Custom Feature Engineering](custom-feature-engineering.md) | [Custom Inference](custom-inference.md) →
