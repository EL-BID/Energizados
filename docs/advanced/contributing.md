# Contributing

This guide covers code quality standards for contributing to the Energizados framework.

## Code Conventions

### Logging

**ALWAYS** use the `logging` module, **NEVER** `print`:

```python
# ❌ WRONG
print("Processing data...")

# ✅ CORRECT
import logging

logger = logging.getLogger(__name__)
logger.info("Processing data...")
logger.debug("Detailed info: %s", some_value)
logger.warning("Warning message")
logger.error("Error occurred: %s", e)
logger.critical("Critical failure")
```

### Code Formatting

Use **Black** with 100 character line length:

```bash
# Format automatically
black src/ tests/

# Check without modifying
black --check src/ tests/
```

Pre-commit hooks run black automatically on each commit.

**Example: Correct vs Incorrect formatting**

```python
# ❌ WRONG (exceeds 100 chars)
result = model.predict_proba(features, include_reshaped=True, use_batch_processing=True, verbose=True)

# ✅ CORRECT (within 100 chars)
result = model.predict_proba(
    features, include_reshaped=True, use_batch_processing=True, verbose=True
)
```

### Import Order

Import order (enforced by isort):

1. Stdlib imports
2. Third-party imports
3. Local imports
4. Within each group: alphabetical

```python
import os  # Stdlib
from pathlib import Path

import numpy as np  # Third-party
import pandas as pd
from sklearn.model_selection import train_test_split

from energizados.etl import BaseETL  # Local
from energizados.preprocessing import ToDummy
```

### Language

**Classes, methods, functions, variables**: English
**Domain feature names**: Spanish (e.g., `actividad`, `tipo_tarifa`, `zona`)

**Example:**

```python
class FraudDetector:
    """Detects electricity fraud using consumption patterns."""

    def __init__(self, actividad: str, zona: str):
        self.actividad = actividad
        self.zona = zona

    def predict(self, data: pd.DataFrame) -> np.ndarray:
        """Make predictions based on activity and zone."""
        features = self._extract_features(data)
        return self.model.predict(features)
```

### Type Hints

Use type hints in public functions and methods:

```python
from typing import Optional, List, Dict, Any
import pandas as pd

def process_data(
    df: pd.DataFrame,
    columns: List[str],
    params: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """Process DataFrame with specified columns."""
    if params is None:
        params = {}
    # ...
```

### Docstrings

Use Google-style docstrings for modules, classes, and public functions:

```python
class FeatureEngineer:
    """Handles feature engineering for ML models.

    This class provides methods for preprocessing, feature selection,
    and transformation of raw data into model-ready features.

    Attributes:
        transformers: List of transformers to apply.
        selector: Feature selector instance.

    Examples:
        >>> engineer = FeatureEngineer()
        >>> X_transformed = engineer.fit_transform(X, y)
    """

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> "FeatureEngineer":
        """Fit all transformers and feature selector.

        Args:
            X: Input features DataFrame.
            y: Target variable.

        Returns:
            self: Fitted instance.
        """
        # ...
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Common types:**

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting, no logical change |
| `refactor` | Code refactoring |
| `test` | Tests |
| `chore` | Maintenance, dependencies |

**Examples:**

```bash
feat(etl): add support for multiple input files with merge mode
fix(pipeline): correct date parsing in time series split
docs(readme): update installation instructions
style(preprocessing): apply black formatting
refactor(evaluation): extract metrics calculation to separate module
test(modeling): add unit tests for LGBMModelAdapter
chore(deps): upgrade lightgbm to 4.6.0
```

## Testing

### Running Tests

```bash
pytest                    # All tests with coverage
pytest -m unit           # Unit tests only
pytest -m integration     # Integration tests only
pytest -m "not slow"      # Exclude slow tests
pytest -m slow           # Slow tests only
pytest tests/test_X.py -v # Specific file
```

**View HTML coverage:**

```bash
# Mac/Linux:
open htmlcov/index.html

# Windows:
start htmlcov/index.html
```

### Test Fixtures

The `tests/conftest.py` file provides common fixtures:

| Fixture | Purpose |
|---------|-----------|
| `synthetic_classification_data` | Synthetic binary classification data (100 samples) |
| `synthetic_classification_data_small` | Small data for quick tests (20 samples) |
| `mock_trained_model` | Mock trained model with `predict()` and `predict_proba()` |
| `mock_trained_model_with_cols` | Mock with handling of specific column names |
| `temp_dir` | Temporary directory (auto-cleaned) |
| `sample_csv_file` | CSV file with synthetic data |
| `sample_parquet_file` | Parquet file with synthetic data |
| `nn_adapter_data` | Data for NN/LSTM adapters (features + consumption) |

**Usage example:**

```python
def test_my_model(synthetic_classification_data):
    X, y = synthetic_classification_data
    # Your asserts here
    assert len(X) == 100
    assert len(y) == 100
```

### Test Conventions

**Markers:**

- `@pytest.mark.unit`: Fast unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Tests that take > 5 seconds

**Example:**

```python
import pytest

@pytest.mark.unit
def test_cardinality_reducer_basic(synthetic_classification_data):
    """Test CardinalityReducer with basic configuration."""
    X, y = synthetic_classification_data
    # ...

@pytest.mark.slow
@pytest.mark.integration
def test_full_pipeline_with_lgbm(temp_dir):
    """Test complete pipeline with LightGBM model."""
    # ...
```

## Package Architecture

### Source Tree

```
src/energizados/
├── cli/                   # Command-line interface
│   ├── main.py           # Main CLI (entry point: energizados)
│   ├── init.py           # Subcommand: energizados init
│   ├── run.py            # Subcommand: energizados run
│   └── validate.py       # Subcommand: energizados validate
│
├── core/                  # Core framework components
│   ├── pipeline.py       # ConfigPipelineBuilder: DEPRECATED wrapper - use PipelineDirector from core/builders/
│   ├── builders/         # Pipeline step builders (current architecture)
│   │   ├── director.py   # PipelineDirector: orchestrates pipeline construction
│   │   ├── base.py       # StepBuilder: abstract base class for builders
│   │   ├── run_manager.py # RunManager: manages run directories and post-run tasks
│   │   ├── etl_builder.py  # ETLBuilder: constructs ETL steps
│   │   ├── split_builder.py # SplitBuilder: constructs split steps
│   │   ├── training_builder.py # TrainingBuilder: constructs training steps
│   │   ├── evaluation_builder.py # EvaluationBuilder: constructs evaluation steps
│   │   ├── inference_builder.py # InferenceBuilder: constructs inference steps
│   │   └── eda_builder.py   # EDABuilder: constructs EDA steps
│   ├── base.py           # Base classes: Pipeline, Model, Inference
│   ├── steps/            # Pipeline step implementations
│   │   ├── split.py      # SplitStep: train/val/test splits
│   │   └── training.py   # TrainingStep: model training
│   ├── plots/            # Shared plot utilities
│   │   └── utils.py
│   └── utils/            # Internal utilities
│       ├── import_utils.py   # Dynamic import with allowlist
│       └── secure_pickle.py  # Pickle with SHA-256 verification
│
├── eda/                   # Exploratory Data Analysis
│   ├── base.py                # BaseExplorer: abstract class
│   ├── dataset_explorer.py    # DatasetExplorer: main orchestrator
│   ├── column_explorer.py     # Per-column analysis (Phase 2)
│   ├── target_explorer.py     # Target variable analysis (Phase 3)
│   ├── geo_analyzer.py       # Geospatial analysis (Phase 4)
│   ├── feature_importance.py  # IV/KS/Cramér's V ranking (Phase 5)
│   ├── segmentation_analyzer.py # Segment drift analysis (Phase 6)
│   ├── related_columns_analyzer.py # Hierarchical column relationships (Phase 7)
│   ├── plots.py               # Static Matplotlib/Seaborn charts
│   ├── plots_interactive.py   # Interactive Plotly charts (HTML strings)
│   ├── report.py              # HTML report generator
│   └── utils.py               # IV, WoE, KS, Cramér's V utilities
│
├── etl/                   # ETL framework with dependencies
│   ├── base.py            # BaseETL: abstract class for ETLs
│   ├── pipeline.py        # SourceETL: concat (vertical) or merge (horizontal)
│   └── orchestrator.py    # ETLOrchestrator: dependency management
│
├── evaluation/            # Model evaluation
│   ├── evaluator.py       # DefaultEvaluator: runs full evaluation
│   ├── metrics.py         # Metrics calculation (AUC, F1, etc.)
│   ├── plots.py           # PlotGenerator: ROC, precision-recall, etc.
│   ├── report.py          # ReportGenerator: HTML + JSON
│   └── index.py           # index.html: summary table of all runs
│
├── feature_engineering/   # Feature engineering (preprocessing + selection)
│   ├── base.py            # BaseFeatureEngineering: abstract class
│   └── default.py         # DefaultFeatureEngineering implementation
│
├── feature_selection/     # Feature selection methods
│   ├── base.py            # BaseFeatureSelector: abstract class
│   └── methods.py         # BorutaSelector, CorrelationSelector, ConstantSelector
│
├── inference/             # Inference implementations
│   ├── base.py            # BaseInference: abstract class
│   └── default.py         # DefaultInference implementation
│
├── modeling/              # ML models
│   ├── supervised_models.py  # LGBMModel, CATModel, NNModel, LSTMNNModel
│   ├── adapters.py          # LGBMModelAdapter, CATModelAdapter, etc.
│   ├── ensemble.py          # EnsembleModel: soft voting or stacking
│   └── simple_models.py     # Baseline: simple rule-based models
│
└── preprocessing/         # Data transformers
    ├── preprocessing.py     # ToDummy, TeEncoder, CardinalityReducer, etc.
    ├── base.py              # BaseTransformer: abstract class
    └── transformers/        # Specific transformers (if structured separately)
```

### Extension Points

The framework provides several base classes for extending functionality:

| Base Class | Location | Purpose |
|------------|----------|---------|
| `BaseETL` | `src/energizados/etl/base.py` | Create custom ETLs |
| `BaseFeatureEngineering` | `src/energizados/feature_engineering/base.py` | Custom feature engineering pipelines |
| `BaseFeatureSelector` | `src/energizados/feature_selection/base.py` | Custom feature selection methods |
| `BaseInference` | `src/energizados/inference/base.py` | Custom inference logic |
| `BaseExplorer` | `src/energizados/eda/base.py` | Custom EDA phases |

## Continuous Integration

### GitHub Actions Workflow

Example CI pipeline configuration:

```yaml
# .github/workflows/test.yml
name: Test Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install --with dev --extras all

      - name: Run pre-commit
        run: |
          poetry run pre-commit run --all-files

      - name: Run tests
        run: |
          poetry run pytest --cov=energizados --cov-report=term-missing

      - name: Validate configs
        run: |
          poetry run energizados validate --config config/etl.yaml
          poetry run energizados validate --config config/train.yaml

      - name: Dry run pipeline
        run: |
          poetry run energizados run etl --dry-run
```

**What the CI Pipeline Runs:**

1. **Linting**: Pre-commit hooks (isort, black, bandit, flake8, prettier)
2. **Testing**: Full test suite with coverage
3. **Validation**: YAML configuration files are validated
4. **Dry run**: Pipeline execution plan is verified without running

## Pull Request Process

1. **Fork the repository** and create a feature branch
2. **Make your changes** following the code conventions above
3. **Run tests** and ensure all pass
4. **Run pre-commit hooks** and fix any issues
5. **Commit your changes** using conventional commit format
6. **Push to your fork** and create a pull request
7. **Wait for CI** to pass and address any review comments

## Publishing (Maintainers Only)

### 1. Bump Version

Edit `pyproject.toml`:

```toml
[project]
version = "0.1.2"  # Update semantic version
```

Use `0.1.3.dev0` for development, `0.1.3` for release.

### 2. Build Package

```bash
# With Poetry
poetry build

# Or with setuptools directly
python -m build
```

This generates `dist/energizados-<version>-py3-none-any.whl` and `.tar.gz`.

### 3. Upload to PyPI

```bash
# First, verify with TestPyPI
twine upload --repository testpypi dist/*

# If everything looks good, upload to PyPI
twine upload dist/*
```

### 4. Create Git Tag (Optional but Recommended)

```bash
git tag v0.1.2
git push origin v0.1.2
```

**References:**

- [`PyPI Publishing`](pypi-publishing.md) — Complete first-time PyPI setup guide
- `pyproject.toml` — Project configuration

## Additional Resources

- **[Development Setup](development-setup.md)** — Setting up your dev environment
- **[Extending Framework](extending/)** — Creating custom components
- **[User Guide](../user-guide/)** — End-user documentation
- **`AGENTS.md`** — Rules for AI agents

---

← [Development Setup](development-setup.md) | [Advanced Topics](../advanced/) →
