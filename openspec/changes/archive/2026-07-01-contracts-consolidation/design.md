# Design: Contracts Consolidation

> Change: `contracts-consolidation` (change #2 of 4 in `framework-core-redesign` program).
> Implements all 5 delta specs: contracts, inference, feature-selection, etl, serialization.
> Approach 2A (full consolidation) with 2-PR split.

## Technical Approach

Create a single home for all framework base classes in `src/energizados/contracts.py`, add the missing `BasePipeline` and `BaseEvaluator`, fix all documented contract violations, normalize save/load via `secure_pickle`, and maintain **100% backward compatibility** via shim re-exports. All concrete classes keep their `__module__` for pickle safety.

### 2-PR Split Strategy

**PR #1 (2A-i):** Add `contracts.py` + shims + missing bases (`BasePipeline`, `BaseEvaluator`) + proper abstract methods. Purely additive. No behavior changes, no violation fixes.

**PR #2 (2A-ii):** Fix violations (`FeatureSelectionPipeline`, `CleanFilesETL`, `HierarchicalInference`) + normalize save/load on `BaseModel` and `BaseFeatureSelector`.

## Architecture Decisions

### Decision 1: BasePipeline.run() Signature

**Choice** — `BasePipeline` is a **new, standalone base class**. The existing `Pipeline` class does **NOT** inherit from it. `BasePipeline.run(context: Dict) -> Dict` aligns with the `PipelineStep.execute` pattern but is purely additive.

**Rationale:**

1. **No breaking change to existing `Pipeline`** — `Pipeline.run()` (the orchestrator used by `ConfigPipelineBuilder`) has a different signature: `__init__(config_path, config)`, stores steps as a list, has callback attributes (`on_step_start`, etc.), and `run()` takes no arguments (returns `self.context`). Introducing inheritance would require refactoring `Pipeline` or making `BasePipeline` so generic it loses value.

2. **`BasePipeline` is for future extensibility** — provides a contract for user-defined pipelines that want the same `run(context)` pattern as `PipelineStep`. The existing `Pipeline` continues to work as-is.

3. **`BasePipeline` aligns with `PipelineStep`** — same context-based pattern: `run(context: Dict[str, Any]) -> Dict[str, Any]`. Optional `validate(context) -> bool` and `get_required_keys() -> list` methods complete the pattern.

**Signature:**

```python
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
```

**Alternatives considered:**

- Make `Pipeline` inherit `BasePipeline` (rejected: would require refactoring `Pipeline.__init__` and `run()` signatures, breaking the live orchestrator).
- Omit `BasePipeline` entirely (rejected: spec requires it; documented but missing base).

---

### Decision 2: BaseEvaluator.evaluate() Signature

**Choice** — `BaseEvaluator.evaluate()` is a **new abstract method**. `DefaultEvaluator` does **NOT** inherit `BaseEvaluator` in PR #1 (stays on `PipelineStep`). In PR #2, `DefaultEvaluator` inherits `BaseEvaluator` **instead of** `PipelineStep` (migration, not dual inheritance).

**Rationale:**

1. **Pin signature against current `DefaultEvaluator.run(context)` behavior** — `DefaultEvaluator.execute(context)` loads models/FE, computes metrics, generates plots/reports, and returns a context with `metrics`, `plots`, `reports`, `evaluation_dir`. `evaluate()` extracts the pure metrics computation.

2. **`evaluate()` is focused on metrics, not reports** — returns `Dict[str, float]` (e.g., `{'auc': 0.85, 'f1': 0.82}`). Report generation is a separate optional method `generate_reports(metrics, output_dir)`.

3. **`evaluate()` accepts the same inputs as `DefaultEvaluator.execute` uses** — `X`, `y`, `model`, plus optional kwargs for threshold, calibration, etc.

**Signature:**

```python
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
```

**Alternatives considered:**

- Return an `EvaluationResult` dataclass (rejected: adds complexity; dict is simpler and matches current `DefaultEvaluator` behavior).
- Include report generation in `evaluate()` (rejected: concerns; separate method keeps evaluation pure).
- Make `evaluate()` take `context` (rejected: couples to pipeline internals; X/y/model is the minimal interface).

---

### Decision 3: noop_load Mechanism on BaseETL

**Choice** — **Optional override hook** `noop_load()` that returns an empty `pd.DataFrame()`. Controlled by a **private flag** `_is_noop_load: bool = False` (default). `BaseETL.run()` checks the flag before dispatching to `extract/transform/load`.

**Rationale:**

1. **Minimal change to existing ETLs** — normal ETLs (`SourceETL`, `ClipOutliersETL`, `GeoFeaturesETL`) ignore the hook. `CleanFilesETL` overrides it and sets the flag.

2. **Flag-based dispatch is explicit and fast** — `BaseETL.run()` checks `if self._is_noop_load` once, not via method detection or exception catching.

3. **Preserves the orchestrator contract** — all ETLs return a DataFrame (empty for noop), so `ETLOrchestrator` continues to work without special cases.

**Implementation:**

```python
class BaseETL(ABC):
    """Base class for ETL processes.

    Supports normal ETLs (extract/transform/load) and noop ETLs
    (e.g., CleanFilesETL) via the _is_noop_load flag.
    """

    def __init__(self, name=None, input_paths=None, output_path=None, **params):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self._is_noop_load = False  # Subclasses override for noop behavior

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Extract data from source."""
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform data."""
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save transformed data."""
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
        if self._is_noop_load:
            return self.noop_load()

        # Normal flow: extract -> transform -> load
        df = self.extract()
        if len(df) == 0:
            return df
        df = self.transform(df)
        self.load(df, output_path)
        self._on_load_success()
        return df
```

**CleanFilesETL change (PR #2):**

```python
class CleanFilesETL(BaseETL):
    """ETL that deletes files. Does not produce a dataset."""

    def __init__(self, name, input_paths=None, output_path=None, missing_ok=True, **kwargs):
        self.name = name
        self.input_paths = input_paths or []
        self.output_path = output_path
        self.missing_ok = missing_ok
        self._is_noop_load = True  # Enable noop mode

    def noop_load(self) -> pd.DataFrame:
        """Delete files and return empty DataFrame."""
        # ... deletion logic ...
        return pd.DataFrame()

    # Remove NotImplementedError stubs — they're never called now
```

**Alternatives considered:**

- Method detection (`hasattr(extract, '__isabstractmethod__')`) — rejected: indirect, harder to understand.
- Separate `BaseFileETL` class — rejected: adds a base class; flag is simpler for a single exception.
- Keep `NotImplementedError` stubs — rejected: contract violation; tests fail.

---

### Decision 4: ModelContainer Protocol Shape

**Choice** — A `typing.Protocol` that requires `predict_proba` (for probability outputs) and `predict` (for binary decisions). Both `BaseModel` subclasses and `HierarchicalModelContainer` satisfy it.

**Rationale:**

1. **Duck-typing matches current behavior** — `HierarchicalModelContainer` is a plain dict-wrapper, not a `BaseModel`. A Protocol accepts both without inheritance changes.

2. **Protocol only validates shape, not behavior** — runtime duck-typing continues to work. Type checkers see the contract.

3. **Minimal protocol** — only the methods actually used by inference (`predict_proba`, `predict`). Not a full `BaseModel` replacement.

**Protocol definition:**

```python
from typing import Protocol, runtime_checkable

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
```

**BaseInference.load_model return type update:**

```python
class BaseInference(ABC):
    # ...

    @abstractmethod
    def load_model(self, model_path: str) -> ModelContainer:
        """Load a trained model.

        Args:
            model_path: Path to the model file.

        Returns:
            ModelContainer: Loaded model (satisfies predict/predict_proba).
        """
        pass
```

**HierarchicalModelContainer already satisfies it:**

```python
class HierarchicalModelContainer:
    """Lightweight container for hierarchical model state."""

    def __init__(self, models: Dict[str, Any], feature_engineerings: Dict[str, Any]):
        self.models = models
        self.feature_engineerings = feature_engineerings

    # Has predict_proba (used by HierarchicalInference.predict_proba)
    # Has predict (used by HierarchicalInference.predict)
    # Satisfies ModelContainer Protocol at runtime
```

**Alternatives considered:**

- Make `HierarchicalModelContainer` inherit `BaseModel` (rejected: changes inheritance; `HierarchicalModelContainer` is a sentinel, not a real model).
- Use `Any` return type (rejected: loses type information; Protocol is explicit about required methods).
- Require `get_raw_model` in Protocol (rejected: not used by inference).

---

### Decision 5: save()/load() Implementation on BaseModel and BaseFeatureSelector

**Choice** — **Direct methods** (not a mixin) using `secure_pickle` (`secure_dump`/`secure_load`). Check fitted state before save (`ModelNotFittedError`). Match `BaseFeatureEngineering.save/load` pattern.

**Rationale:**

1. **Mixin adds indirection without enough duplication** — only 3 bases need save/load (`BaseModel`, `BaseFeatureSelector`, `BaseFeatureEngineering`). Direct methods are clearer for readers.

2. **`BaseFeatureEngineering.save/load` already exists** — migrate it to the same pattern (no functional change, just consistency). Note: `BaseFeatureEngineering.save` already uses `secure_pickle` — this is alignment, not replacement.

3. **Pickle safety via `secure_pickle` is mandatory** — all saves use `secure_dump` (SHA-256 signature sidecar), all loads use `secure_load` (verifies signature).

**BaseModel implementation:**

```python
class BaseModel(ABC):
    # ...

    def save(self, path: str) -> None:
        """Save the fitted model to disk.

        Args:
            path: Destination path (.pkl extension recommended).

        Raises:
            ModelNotFittedError: If the model is not fitted.
        """
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError

            raise ModelNotFittedError(model_name=self.__class__.__name__)

        from energizados.core.utils.secure_pickle import secure_dump

        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        secure_dump(self, path)
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
        from energizados.core.utils.secure_pickle import secure_load

        model = secure_load(path)
        logger.info(f"Model loaded from: {path}")
        return model
```

**BaseFeatureSelector implementation:**

```python
class BaseFeatureSelector(ABC):
    # ...

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

        from energizados.core.utils.secure_pickle import secure_dump

        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        secure_dump(self, path)
        logger.info(f"Selector saved to: {path}")

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
        from energizados.core.utils.secure_pickle import secure_load

        selector = secure_load(path)
        logger.info(f"Selector loaded from: {path}")
        return selector
```

**BaseFeatureEngineering.save/load — no change needed:**

- Already uses `secure_dump`/`secure_load`.
- Already checks `is_fitted_` and raises `ModelNotFittedError`.
- Already creates parent directories.
- Pattern is identical to above (document alignment, no migration).

**Alternatives considered:**

- `SerializableMixin` — rejected: adds a class to the hierarchy for only 3 bases; direct methods are more explicit.
- Skip `BaseFeatureEngineering.save/load` migration — rejected: existing pattern is correct, just document alignment.
- Use plain `pickle` — rejected: `secure_pickle` is mandatory (SHA-256 verification, path traversal protection).

---

### Decision 6: Pickle Safety Strategy

**Choice** — **Concrete classes never move**. Only base classes move to `contracts.py`. Old modules become **shim re-exports** (`from energizados.contracts import BaseETL`). Pickle stores the concrete class (`LGBMModelAdapter.__module__ == 'energizados.modeling.adapters'`), which never changes. `BaseModel.__module__` changes, but pickle doesn't store it.

**Pickle round-trip test:**

Add a fixture at `tests/fixtures/pickles/` with legacy pickles created **before PR #1**:

```
tests/fixtures/pickles/
├── legacy_adapter.pkl              # LGBMModelAdapter from before base move
├── legacy_adapter.pkl.sig          # SHA-256 signature
├── legacy_feature_eng.pkl          # DefaultFeatureEngineering from before base move
└── legacy_feature_eng.pkl.sig      # SHA-256 signature
```

Test in `tests/test_contracts.py`:

```python
def test_legacy_pickle_roundtrip():
    """Legacy pickles load after base classes move to contracts."""
    from pathlib import Path
    from energizados.core.utils.secure_pickle import secure_load

    fixture_dir = Path(__file__).parent / "fixtures" / "pickles"

    # Load legacy model adapter
    model = secure_load(fixture_dir / "legacy_adapter.pkl")
    assert model.is_fitted_ is True
    assert model.__module__ == "energizados.modeling.adapters"  # Unchanged

    # Load legacy feature engineering
    fe = secure_load(fixture_dir / "legacy_feature_eng.pkl")
    assert fe.is_fitted_ is True
    assert fe.__module__ == "energizados.feature_engineering.default"  # Unchanged
```

**Rule:**

- **Concrete class `__module__` is immutable.** Only base classes move.
- **Shims re-export the same class object** (not a copy). `isinstance` checks continue to pass.
- **Old import paths resolve via shims.** User code and templates work unchanged.

**Alternatives considered:**

- Move concrete classes too — rejected: breaks all existing pickles; migration required.
- Use `sys.modules` alias for old paths — rejected: shims are clearer and explicitly versioned.
- Skip testing — rejected: pickle safety is a hard constraint; test confirms the invariant.

---

## File Changes

### PR #1 (2A-i): Add contracts + shims + missing bases

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/contracts.py` | Create | New home: `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`, `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`. |
| `src/energizados/core/base.py` | Modify | Becomes shim: `from energizados.contracts import BaseModel, BaseInference`. Keep `PipelineStep` (not in contracts). |
| `src/energizados/etl/base.py` | Modify | Becomes shim: `from energizados.contracts import BaseETL`. |
| `src/energizados/feature_engineering/base.py` | Modify | Becomes shim: `from energizados.contracts import BaseFeatureEngineering`. |
| `src/energizados/feature_selection/base.py` | Modify | Becomes shim: `from energizados.contracts import BaseFeatureSelector`. |
| `src/energizados/eda/base.py` | Modify | Becomes shim: `from energizados.contracts import BaseExplorer`. |
| `src/energizados/inference/base.py` | Modify | Already a shim; update to re-export from `contracts`. |
| `tests/test_contracts.py` | Create | Per-base abstract method enforcement, shim compatibility, `isinstance` tests. |
| `AGENTS.md` | Modify | Document `energizados.contracts` as the single home for base classes. |

### PR #2 (2A-ii): Fix violations + normalize save/load

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/contracts.py` | Modify | Add `save()`/`load()` to `BaseModel`, `BaseFeatureSelector`. |
| `src/energizados/etl/base.py` (via contracts) | Modify | Add `_is_noop_load` flag and `noop_load()` hook to `BaseETL`. |
| `src/energizados/feature_selection/pipeline.py` | Modify | `FeatureSelectionPipeline` now inherits `BaseFeatureSelector`. Remove direct `PipelineStep` inheritance. |
| `src/energizados/etl/pipeline.py` | Modify | `CleanFilesETL`: override `noop_load()`, set `_is_noop_load = True`, remove `NotImplementedError` stubs. |
| `src/energizados/inference/hierarchical.py` | Modify | `BaseInference.load_model` return type now `ModelContainer` (Protocol). `HierarchicalModelContainer` unchanged (already satisfies Protocol). |
| `src/energizados/evaluation/evaluator.py` | Modify | `DefaultEvaluator` now inherits `BaseEvaluator` (instead of `PipelineStep`). |
| `tests/test_contracts.py` | Modify | Add tests for save/load, noop_load, inheritance fixes, Protocol satisfaction. |
| `tests/fixtures/pickles/` | Create | Legacy pickle fixtures for round-trip test. |

---

## Data Flow

### PR #1 (contracts + shims)

```
User code imports:
  from energizados.etl.base import BaseETL
  from energizados.core.base import BaseModel
  from energizados.feature_selection.base import BaseFeatureSelector

      ↓

Old modules (shims):
  etl/base.py → from energizados.contracts import BaseETL
  core/base.py → from energizados.contracts import BaseModel, BaseInference
  feature_selection/base.py → from energizados.contracts import BaseFeatureSelector

      ↓

New contracts module:
  energizados.contracts.py → defines all 8 base classes
```

**Key invariant:** The shim re-exports the **same class object** (not a copy). `isinstance(obj, energizados.etl.base.BaseETL)` returns `True` because `energizados.etl.base.BaseETL is energizados.contracts.BaseETL`.

### PR #2 (violations fixed)

**FeatureSelectionPipeline inheritance:**

```
Before:
  FeatureSelectionPipeline → PipelineStep (direct)

After:
  FeatureSelectionPipeline → BaseFeatureSelector → (ABC)
```

**CleanFilesETL noop flow:**

```
ETLOrchestrator calls etl.run(output_path)
      ↓
BaseETL.run checks if self._is_noop_load
      ↓
True → CleanFilesETL.noop_load() deletes files, returns pd.DataFrame()
False → normal extract → transform → load flow
```

**save/load via secure_pickle:**

```
BaseModel.save(path)
      ↓
check is_fitted_ → raise ModelNotFittedError if False
      ↓
secure_dump(self, path) → joblib.dump + SHA-256.sig sidecar

BaseModel.load(path)
      ↓
secure_load(path) → verify .sig, joblib.load
```

---

## Interfaces / Contracts

### contracts.py Module Structure

```python
"""
Energizados Framework Contracts.

Single home for all abstract base classes. Public API.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, runtime_checkable
from pathlib import Path
import logging

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# Model & Inference Contracts
# ============================================================================

class BaseModel(ABC):
    """Base class for custom models."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.model_ = None
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series, X_val: Optional[pd.DataFrame] = None,
            y_val: Optional[pd.Series] = None) -> "BaseModel":
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        pass

    @abstractmethod
    def get_raw_model(self) -> Any:
        pass

    def check_fitted(self) -> None:
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)

    # save/load added in PR #2


@runtime_checkable
class ModelContainer(Protocol):
    """Protocol for objects with predict/predict_proba methods."""

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        ...


class BaseInference(ABC):
    """Base class for inference and prediction."""

    @abstractmethod
    def predict(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        pass

    @abstractmethod
    def predict_proba(self, model: BaseModel, data: pd.DataFrame) -> np.ndarray:
        pass

    @abstractmethod
    def load_model(self, model_path: str) -> ModelContainer:
        pass

    @abstractmethod
    def save_predictions(self, predictions: np.ndarray, output_path: str) -> None:
        pass


# ============================================================================
# Pipeline & Evaluation Contracts
# ============================================================================

class BasePipeline(ABC):
    """Base class for user-defined pipelines."""

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def validate(self, context: Dict[str, Any]) -> bool:
        return True

    def get_required_keys(self) -> list:
        return []


class BaseEvaluator(ABC):
    """Base class for model evaluation."""

    @abstractmethod
    def evaluate(self, X: pd.DataFrame, y: pd.Series, model: Any,
                 threshold: float = 0.5, **kwargs: Any) -> Dict[str, float]:
        pass

    def generate_reports(self, metrics: Dict[str, float], output_dir: str,
                        **kwargs: Any) -> None:
        pass


# ============================================================================
# ETL, Feature Engineering, Feature Selection, EDA Contracts
# ============================================================================

class BaseETL(ABC):
    """Base class for ETL processes."""

    def __init__(self, name=None, input_paths=None, output_path=None, **params):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self._is_noop_load = False  # Subclass sets True for noop

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        pass

    def noop_load(self) -> pd.DataFrame:
        return pd.DataFrame()

    def run(self, output_path: str) -> pd.DataFrame:
        if self._is_noop_load:
            return self.noop_load()
        df = self.extract()
        if len(df) == 0:
            return df
        df = self.transform(df)
        self.load(df, output_path)
        self._on_load_success()
        return df

    def _on_load_success(self) -> None:
        pass


class BaseFeatureEngineering(ABC):
    """Base class for feature engineering pipelines."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.is_fitted_ = False

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureEngineering":
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        return self.fit(X, y).transform(X)

    def save(self, path: str) -> None:
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)
        from energizados.core.utils.secure_pickle import secure_dump
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        secure_dump(self, path)
        logger.info(f"Feature engineering saved to: {path}")

    @classmethod
    def load(cls, path: str) -> "BaseFeatureEngineering":
        from energizados.core.utils.secure_pickle import secure_load
        pipeline = secure_load(path)
        logger.info(f"Feature engineering loaded from: {path}")
        return pipeline

    def get_feature_names_out(self) -> list:
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return self._get_feature_names_out()

    def _get_feature_names_out(self) -> list:
        return []

    def check_fitted(self) -> None:
        if not self.is_fitted_:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)


class BaseFeatureSelector(ABC):
    """Base class for feature selection."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.selected_features_ = None

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseFeatureSelector":
        pass

    @abstractmethod
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        pass

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        return self.fit(X, y).transform(X)

    # save/load added in PR #2

    def get_selected_features(self) -> list:
        if self.selected_features_ is None:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return self.selected_features_

    def get_audit_stats(self) -> Dict:
        if self.selected_features_ is None:
            from energizados.core.exceptions import ModelNotFittedError
            raise ModelNotFittedError(model_name=self.__class__.__name__)
        return {}


class BaseExplorer(ABC):
    """Base class for exploratory data analysis."""

    @abstractmethod
    def explore(self, data: pd.DataFrame, output_dir: str) -> None:
        pass
```

### Shim Module Examples

**`core/base.py` (after PR #1):**

```python
"""
Abstract Base Classes for the Energizados Framework.

This module now re-exports from energizados.contracts for backward compatibility.
"""

# Re-export from contracts
from energizados.contracts import BaseModel, BaseInference

# PipelineStep stays here (not in contracts)
from abc import ABC, abstractmethod
from typing import Any, Dict

class PipelineStep(ABC):
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_input(self, context: Dict[str, Any]) -> bool:
        pass

    def get_required_keys(self) -> list:
        return []

    def get_output_keys(self) -> list:
        return []

__all__ = ["BaseModel", "BaseInference", "PipelineStep"]
```

**`etl/base.py` (after PR #1):**

```python
"""ETL Base Module.

Re-exports BaseETL from energizados.contracts for backward compatibility.
"""

from energizados.contracts import BaseETL

__all__ = ["BaseETL"]
```

---

## Testing Strategy

### Unit Tests (tests/test_contracts.py)

| Test | Purpose |
|------|---------|
| `test_base_classes_exist` | All 8 bases exist in `contracts.py`. |
| `test_abstract_methods_enforced` | Instantiating a base without abstract methods raises `TypeError`. |
| `test_shim_reexports_same_class` | `energizados.etl.base.BaseETL is energizados.contracts.BaseETL`. |
| `test_isinstance_from_shim_passes` | `isinstance(SourceETL(), energizados.etl.base.BaseETL)` is `True`. |
| `test_base_pipeline_contract` | `BasePipeline.run(context)` is abstract; optional methods work. |
| `test_base_evaluator_contract` | `BaseEvaluator.evaluate(X, y, model)` is abstract; optional methods work. |
| `test_base_inference_abstract_methods` | `load_model` and `save_predictions` are `@abstractmethod`. |
| `test_model_container_protocol` | `ModelContainer` Protocol checks `predict_proba`/`predict`. |
| `test_hierarchical_model_container_satisfies_protocol` | `HierarchicalModelContainer` satisfies `ModelContainer` at runtime. |
| `test_noop_load_hook` | `BaseETL._is_noop_load = True` bypasses extract/transform/load. |
| `test_base_model_save_load` | `save()`/`load()` use `secure_pickle`, raise `ModelNotFittedError` if not fitted. |
| `test_base_feature_selector_save_load` | `save()`/`load()` use `secure_pickle`, raise `ModelNotFittedError` if no features. |
| `test_feature_selection_pipeline_inheritance` | `issubclass(FeatureSelectionPipeline, BaseFeatureSelector)` is `True`. |
| `test_default_evaluator_inherits_base_evaluator` | `issubclass(DefaultEvaluator, BaseEvaluator)` is `True`. |
| `test_legacy_pickle_roundtrip` | Legacy pickles load after base move. |

### Integration Tests

| Test | Purpose |
|------|---------|
| `test_pipeline_with_new_bases` | User-defined `BasePipeline` subclass works with context. |
| `test_evaluator_with_new_base` | User-defined `BaseEvaluator` subclass computes metrics. |
| `test_etl_orchestrator_with_clean_files` | `CleanFilesETL` runs via orchestrator without `NotImplementedError`. |
| `test_hierarchical_inference_load_model` | `HierarchicalInference.load_model()` returns `ModelContainer`-satisfying object. |
| `test_save_load_preserves_state` | `save()`/`load()` preserve fitted state and predictions. |

### Legacy Pickle Fixture Generation

Generate fixtures **before PR #1** lands:

```bash
# In a fresh virtual env with the current framework
python - << 'EOF'
import pickle
from pathlib import Path
from energizados.modeling.adapters import LGBMModelAdapter
from energizados.feature_engineering.default import DefaultFeatureEngineering
import numpy as np
import pandas as pd

# Create a simple model adapter
model = LGBMModelAdapter(config={"type": "lightgbm"})
model.is_fitted_ = True
model.model_ = None  # Dummy fitted state

# Create a simple feature engineering
fe = DefaultFeatureEngineering()
fe.is_fitted_ = True

# Save with regular pickle (not secure_dump, for legacy fixture)
fixture_dir = Path("tests/fixtures/pickles")
fixture_dir.mkdir(parents=True, exist_ok=True)

with open(fixture_dir / "legacy_adapter.pkl", "wb") as f:
    pickle.dump(model, f)

with open(fixture_dir / "legacy_feature_eng.pkl", "wb") as f:
    pickle.dump(fe, f)

print("Fixtures generated")
EOF
```

After PR #1 and #2, run the round-trip test to confirm backward compatibility.

---

## Migration / Rollout

### PR #1 Rollout

1. **Add `contracts.py`** with all 8 base classes.
2. **Convert old base modules** to shim re-exports.
3. **Add `tests/test_contracts.py`** with abstract method and shim tests.
4. **Run `pytest tests/`** — should be green (no behavior change).
5. **Update `AGENTS.md`** with contracts home documentation.

**Rollback:** Revert PR #1. Shims removed, `contracts.py` deleted. Concrete classes untouched → pickle-safe.

### PR #2 Rollout

1. **Add `save()`/`load()`** to `BaseModel`, `BaseFeatureSelector`.
2. **Add `_is_noop_load` flag** to `BaseETL`.
3. **Fix `FeatureSelectionPipeline`** inheritance.
4. **Fix `CleanFilesETL`** (override `noop_load`, set flag, remove stubs).
5. **Update `BaseInference.load_model`** return type to `ModelContainer`.
6. **Update `DefaultEvaluator`** to inherit `BaseEvaluator`.
7. **Run `pytest tests/`** — should be green.
8. **Generate legacy pickle fixtures** (if not already done).
9. **Run round-trip test** to confirm pickle safety.

**Rollback:** Revert PR #2. Inheritance reverts, save/load methods removed, noop hook removed. Existing user code continues to work (changes were additive).

### CHANGELOG Entry

```markdown
### Added
- `energizados.contracts` — single home for all 8 framework base classes.
  - `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`
  - `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`
- `BasePipeline` — new base class for user-defined pipelines with `run(context)` contract.
- `BaseEvaluator` — new base class for model evaluation with `evaluate(X, y, model)` contract.
- `BaseModel.save()`/`load()` — save/load fitted models via `secure_pickle`.
- `BaseFeatureSelector.save()`/`load()` — save/load fitted selectors via `secure_pickle`.
- `ModelContainer` Protocol — duck-typed contract for objects with `predict`/`predict_proba`.

### Changed
- Old base modules (`core/base.py`, `etl/base.py`, etc.) are now shim re-exports from `energizados.contracts`. All public import paths remain unchanged.
- `BaseInference.load_model` and `save_predictions` are now `@abstractmethod` (cannot be left unimplemented).
- `BaseInference.load_model` return type is now `ModelContainer` Protocol (accepts single models and `HierarchicalModelContainer`).
- `DefaultEvaluator` now inherits `BaseEvaluator` (instead of `PipelineStep` directly).
- `FeatureSelectionPipeline` now inherits `BaseFeatureSelector` (previously inherited `PipelineStep`).
- `CleanFilesETL` now uses the `noop_load` hook on `BaseETL` (no longer raises `NotImplementedError` in abstract methods).

### Fixed
- Contract violations: `FeatureSelectionPipeline` now correctly inherits `BaseFeatureSelector`.
- Contract violations: `CleanFilesETL` now respects the `BaseETL` contract via `noop_load` hook.
- Contract violations: `HierarchicalInference.load_model` return type now accommodates both single models and `HierarchicalModelContainer` via `ModelContainer` Protocol.

### Migration Notes
- **Pickle safety:** Existing `model.pkl` and `feature_engineering.pkl` files load unchanged. Concrete classes keep their `__module__`.
- **Public import paths:** All documented paths (`energizados.etl.base.BaseETL`, etc.) continue to work via shims.
- **User code:** No breaking changes. All modifications are additive (new methods, new bases) or fix violations (inheritance corrections).
```

---

## Changed-files Estimate & PR Shape

### PR #1 (2A-i)
~7 touched files + 1 new test ≈ **200–250 changed lines** (well under 400-line budget).

### PR #2 (2A-ii)
~6 touched files + 1 updated test + fixtures ≈ **150–200 changed lines** (well under 400-line budget).

**Total:** ~350–450 lines across 2 PRs.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Pickle format break (base class move) | Low | Concrete classes keep `__module__`. Test with legacy fixture. |
| Shim re-export breaks `isinstance` | Low | Re-exports the same class object. Add `test_isinstance_from_shim_passes`. |
| `FeatureSelectionPipeline` inheritance breaks subclassing | Low | `FeatureSelectionPipeline` is internal. Add migration note if external usage suspected. |
| `BaseInference.load_model` → `@abstractmethod` breaks custom inference | Low | Templates already implement it. Only incomplete user classes affected — they would fail at runtime anyway. |
| `noop_load` hook misused | Low | Document clearly in docstring. Test that normal ETLs unaffected. |
| `ModelContainer` Protocol too permissive | Low | Runtime duck-typing unchanged. Add type tests. |
| 400-line budget exceeded | Low | 2-PR split keeps each under budget. |
| Chained PR miscoordinated | Low | Document dependency explicitly. PR #2 cannot land until PR #1 merged. |

---

## Open Questions (All Resolved)

| Q | Resolution |
|---|------------|
| Q1: `BasePipeline.run()` signature | `run(context: Dict) -> Dict` aligned with `PipelineStep`. `Pipeline` class does NOT inherit it. |
| Q2: `BaseEvaluator.evaluate()` params | `evaluate(X, y, model, threshold=0.5, **kwargs) -> Dict[str, float]`. |
| Q3: `noop_load` mechanism | Flag-based (`_is_noop_load: bool`) with override hook. |
| Q4: `ModelContainer` Protocol shape | Requires `predict_proba(X)` and `predict(X)`. |
| Q5: `save()`/`load()` implementation | Direct methods using `secure_pickle`. `BaseFeatureEngineering` left as-is (already correct). |
| Q6: Pickle safety strategy | Concrete classes never move. Shims re-export. Legacy pickle test confirms. |
