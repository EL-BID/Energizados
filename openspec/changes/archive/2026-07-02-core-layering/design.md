# Design: Core Layering

> **Supersedes proposal/spec count**: The proposal and spec enumerated 4 cycle-forming edges. Gate review verified the full set is **6 edges**. This design covers all 6.
>
> **Scope correction**: Two edges in `core/steps/training.py` (lines 17-18) were omitted from the proposal/spec. They ARE cycle-forming and MUST be cut.

## Intent

Eliminate all module-level `core → concrete` import edges that close circular dependencies. The `core` package must be a true foundation with zero module-level imports to `etl`, `evaluation`, `inference`, `modeling`, or `feature_engineering`. Concrete packages may import `core`, but `core` must not import them at module load time.

## Architecture Decision

**ADR-001: Lazy imports over refactoring**

We cut the 6 cycle-forming edges via two mechanisms:

| Mechanism | Edges | Rationale |
|----------|-------|-----------|
| Import repoint | Edge 1 (`BaseETL`) | `BaseETL` now lives in `contracts` (a clean leaf). Repoint `core/__init__.py` from `etl.base` to `contracts`. Re-export keeps `from energizados.core import BaseETL` working. |
| Lazy import | Edges 2-6 | Move imports inside the method/function that uses each collaborator. Type hints use string annotations. |

**Rejected alternatives:**

1. **Move classes to `core`** — Would break pickle `__module__` attributes, invalidate persisted `.pkl` files, and mix concrete implementations into the foundational layer. Violates the principle that `core` is abstract contracts only.

2. **Add factory parameters for DI** — Valid testability improvement, but out of scope for this change. Lazy imports kill the cycle without adding new API surface. DI seams deferred to a follow-up change.

3. **`from __future__ import annotations` globally** — String annotations are sufficient and file-local. No need for a module-wide directive.

## Component Mapping

### Edge 1: Repoint `BaseETL` import (core/__init__.py)

**Current:**
```python
# src/energizados/core/__init__.py:20
from energizados.etl.base import BaseETL
```

**After:**
```python
from energizados.contracts import BaseETL
```

**Verification:**
- `from energizados.core import BaseETL` returns the same class (now sourced from `contracts`).
- `energizados.etl.base` is a shim that re-exports from `contracts`, so existing code continues working.

### Edge 2: Lazy import `ETLOrchestrator` (etl_builder.py)

**Current:**
```python
# src/energizados/core/builders/etl_builder.py:11
from energizados.etl.orchestrator import ETLOrchestrator
```

**After:**
```python
# Remove module-top import (line 11)

def build(self) -> Optional[PipelineStep]:
    # Lazy import
    from energizados.etl.orchestrator import ETLOrchestrator

    orchestrator = ETLOrchestrator(etl_configs)  # line 35
    # ... rest of method

    class ETLStep(PipelineStep):
        def __init__(self, orchestrator: "ETLOrchestrator", etl_names: List[str]):  # line 45
            # ...
```

**Verification:**
- `ETLOrchestrator` is instantiated only at line 35 (inside `build()`).
- Type hint at line 45 uses string annotation `"ETLOrchestrator"`.
- No module-level singleton or class-attribute uses it.

### Edge 3: Lazy import `DefaultEvaluator` (evaluation_builder.py)

**Current:**
```python
# src/energizados/core/builders/evaluation_builder.py:12
from energizados.evaluation import DefaultEvaluator
```

**After:**
```python
# Remove module-top import (line 12)

def build(self) -> Optional[PipelineStep]:
    # ... config parsing ...

    # Lazy import at line 66
    from energizados.evaluation import DefaultEvaluator

    return DefaultEvaluator(
        input_path=eval_config.get("input_path"),
        # ... kwargs
    )
```

**Verification:**
- `DefaultEvaluator` is instantiated only at line 66.
- No type hint uses this class.

### Edge 4: Lazy import `DefaultInference` (inference_builder.py)

**Current:**
```python
# src/energizados/core/builders/inference_builder.py:19
from energizados.inference.default import DefaultInference
```

**After:**
```python
# Remove module-top import (line 19)

def build(self) -> Optional[PipelineStep]:
    # ... config parsing ...

    if custom_class:
        InferenceClass = import_class(custom_class)
    else:
        # Lazy import at line 51
        from energizados.inference.default import DefaultInference
        InferenceClass = DefaultInference
```

**Verification:**
- `DefaultInference` is only assigned to `InferenceClass` at line 51.
- No type hint uses this class.

### Edge 5: Lazy import `DefaultFeatureEngineering` (training.py)

**Current:**
```python
# src/energizados/core/steps/training.py:17
from energizados.feature_engineering import DefaultFeatureEngineering
```

**After:**
```python
# Remove module-top import (line 17)

def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
    # ... (lines 189-305: data loading, filtering, datetime handling) ...

    # Lazy import at line 306 (inside execute)
    from energizados.feature_engineering import DefaultFeatureEngineering

    feature_engineering = DefaultFeatureEngineering(
        preprocessing_config=fe_config,
        feature_selection_config=fs_config,
    )
```

**Verification:**
- `DefaultFeatureEngineering` is instantiated only at line 306 (inside `execute()`).
- No type hint uses this class.
- `execute()` is called at runtime by `Pipeline.run()`, not at module load.

### Edge 6: Lazy import `ModelRegistry` (training.py)

**Current:**
```python
# src/energizados/core/steps/training.py:18
from energizados.modeling.registry import ModelRegistry
```

**After:**
```python
# Remove module-top import (line 18)

def _train_single_model(self, ...):
    # ... (lines 572-591: prep work) ...

    # Lazy import at line 592 (inside _train_single_model)
    from energizados.modeling.registry import ModelRegistry

    model_class = ModelRegistry.get(model_type)
    params = self._prepare_model_params(cfg, X_train)

    # ... rest of method
```

**Verification:**
- `ModelRegistry` is used only at line 592 (`ModelRegistry.get(model_type)`).
- No type hint uses this class.
- `_train_single_model()` is called from `execute()` at runtime, not at module load.

## Data Flow

### Before (cycles present)

```
module load time:
  core/__init__.py → etl.base (cycle)
  core/builders/etl_builder.py → etl.orchestrator (cycle)
  core/builders/evaluation_builder.py → evaluation (cycle)
  core/builders/inference_builder.py → inference.default (cycle)
  core/steps/training.py → feature_engineering (cycle)
  core/steps/training.py → modeling.registry (cycle)

Each of these concrete packages also imports core → CYCLE.
```

### After (cycles eliminated)

```
module load time:
  core/__init__.py → contracts (safe: contracts is a leaf)
  core/builders/* → no concrete imports
  core/steps/* → no concrete imports

runtime (when build()/execute() is called):
  etl_builder.build() → lazy import ETLOrchestrator
  evaluation_builder.build() → lazy import DefaultEvaluator
  inference_builder.build() → lazy import DefaultInference
  training.execute() → lazy import DefaultFeatureEngineering
  training._train_single_model() → lazy import ModelRegistry
```

## Integration Points

### ConfigPipelineBuilder (unchanged)

- Builders are instantiated by `Director` from YAML at **runtime**.
- `build()` methods are called **after** `ConfigPipelineBuilder` assembles the steps.
- Lazy imports execute at the same time as before (during `build()`), just relocated from module-top to method-body.

### Pickle compatibility (unchanged)

- No class moves. Concretes keep their `__module__` attributes.
- `BaseETL` in `contracts.py` has `__module__ = "energizados.contracts"`.
- `SourceETL` in `etl/pipeline.py` still has `__module__ = "energizados.etl.pipeline"`.
- Legacy `.pkl` files load unchanged.

### Public paths (unchanged)

- `from energizados.core import BaseETL` → works (re-exported from `contracts`).
- `from energizados.etl.base import BaseETL` → works (shim re-exports from `contracts`).
- `from energizados.contracts import BaseETL` → works (canonical source).

## Cycle Verification Test

**File:** `tests/test_core_layering.py`

**Implementation (AST-based):**

```python
"""Verify core has zero module-level imports to concrete packages."""

import ast
from pathlib import Path

import pytest


def test_core_has_no_module_level_imports_to_concrete_packages():
    """
    Scan ALL Python files under src/energizados/core/ (including steps/ and builders/)
    and verify ZERO module-level imports from core to concrete packages.

    Forbidden prefixes (cycle-forming):
      - energizados.etl
      - energizados.evaluation
      - energizados.inference
      - energizados.modeling
      - energizados.feature_engineering

    Allowed (not a cycle):
      - energizados.eda (eda does NOT import core at module level)
      - energizados.contracts (leaf package, no energizados imports)

    AST top-level-only scan automatically excludes in-method lazy imports.
    """
    core_root = Path("src/energizados/core")
    forbidden_prefixes = {
        "energizados.etl",
        "energizados.evaluation",
        "energizados.inference",
        "energizados.modeling",
        "energizados.feature_engineering",
    }

    violations = []

    for py_file in core_root.rglob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            # Only check top-level imports (not nested inside functions/classes)
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            # Check if node is at module level (parent is Module)
            if hasattr(tree, "body") and node not in tree.body:
                # If node is not in body, it's nested — skip
                # (AST walk doesn't expose parent directly; use line number heuristic)
                continue

            # More robust: check if node's line number matches a top-level node
            # For simplicity, we'll scan all and filter by prefix
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name.startswith(prefix) for prefix in forbidden_prefixes):
                        violations.append((py_file, alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module and any(
                    node.module.startswith(prefix) for prefix in forbidden_prefixes
                ):
                    violations.append((py_file, node.module, node.lineno))

    # Filter violations to only module-level imports (line number heuristic)
    # In practice, lazy imports inside methods have higher line numbers than
    # the last top-level import. This is a simplification; for exactness,
    # we rely on the fact that in-method imports are NOT at indentation level 0.
    actual_violations = []
    for file_path, module_name, lineno in violations:
        source = file_path.read_text()
        lines = source.split("\n")
        # Module-level imports are at indentation level 0 (or near it)
        # In-method imports are indented
        if lineno <= len(lines):
            line = lines[lineno - 1]
            # Strip leading whitespace to check indentation
            if line.lstrip().startswith(("from ", "import ")):
                # Check if it's at module level (no leading whitespace)
                if line == line.lstrip():
                    actual_violations.append((file_path, module_name, lineno))

    assert (
        len(actual_violations) == 0
    ), f"Found {len(actual_violations)} module-level imports to concrete packages: {actual_violations}"


def test_eda_import_remains_unchanged():
    """
    Verify that core/builders/eda_builder.py:11 still imports DatasetExplorer.
    This edge is intentionally NOT a cycle (eda does not import core).
    """
    eda_builder = Path("src/energizados/core/builders/eda_builder.py")
    source = eda_builder.read_text()

    assert "from energizados.eda.dataset_explorer import DatasetExplorer" in source, \
        "eda_builder.py should still import DatasetExplorer (not a cycle, leave as-is)"
```

**Test behavior after the change:**

- `test_core_has_no_module_level_imports_to_concrete_packages` → **PASS** (all 6 edges are lazy or repointed).
- `test_eda_import_remains_unchanged` → **PASS** (eda_builder line 11 untouched, explicitly allowed).

## Pickle/Public-Path Invariants

| Invariant | Before | After | Verification |
|-----------|--------|-------|--------------|
| `BaseETL.__module__` | `"energizados.etl.base"` | `"energizados.contracts"` | `from energizados.core import BaseETL; assert BaseETL.__module__ == "energizados.contracts"` |
| `SourceETL.__module__` | `"energizados.etl.pipeline"` | `"energizados.etl.pipeline"` | unchanged |
| `ETLOrchestrator.__module__` | `"energizados.etl.orchestrator"` | `"energizados.etl.orchestrator"` | unchanged |
| `DefaultEvaluator.__module__` | `"energizados.evaluation.evaluator"` | `"energizados.evaluation.evaluator"` | unchanged |
| `DefaultInference.__module__` | `"energizados.inference.default"` | `"energizados.inference.default"` | unchanged |
| `DefaultFeatureEngineering.__module__` | `"energizados.feature_engineering.default"` | `"energizados.feature_engineering.default"` | unchanged |
| `ModelRegistry.__module__` | `"energizados.modeling.registry"` | `"energizados.modeling.registry"` | unchanged |

**Public path compatibility:**

- `from energizados.core import BaseETL` → works (re-exported).
- `from energizados.etl.base import BaseETL` → works (shim re-exports).
- `from energizados.contracts import BaseETL` → works (canonical).

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Lazy import timing edge case** | Low | Lazy imports execute in `build()` or `execute()`, which are called at runtime by `ConfigPipelineBuilder` from YAML. No module-level singleton or class-attribute references. Verified per edge. |
| **Type hint consumers break** | Low | String annotations (`"ETLOrchestrator"`) are sufficient. No runtime annotation resolution consumers in the codebase (no `typing.get_type_hints()` calls on these classes). |
| **Pickle break from BaseETL repoint** | None | No class move. `BaseETL` now lives in `contracts`, but that's where `etl.base` already re-exported from. Pickled `SourceETL` still references `etl.pipeline` (unchanged). |
| **Edge 5/6 mistakenly omitted** | Low | This design explicitly lists all 6 edges. Test covers all of `core/**`. Gate review will verify the count. |
| **DI seams expected but missing** | Medium | This change does NOT add fake-injection capability. Documented as out of scope. DI-seams work deferred to follow-up. |

## Dependencies

- **Soft-depends on change #2 (`contracts-consolidation`)**: Edge 1 repoints to `energizados.contracts`, which was created in change #2. Assumption: change #2 has landed and `contracts.py` exists.
- **No other dependencies**: Independent of Findings 3 and 4.

## Success Criteria

- [ ] `core/__init__.py:20` imports `BaseETL` from `energizados.contracts`.
- [ ] `etl_builder.py` has no module-top import of `ETLOrchestrator` (import inside `build()`).
- [ ] `evaluation_builder.py` has no module-top import of `DefaultEvaluator` (import inside `build()`).
- [ ] `inference_builder.py` has no module-top import of `DefaultInference` (import inside `build()`).
- [ ] `training.py` has no module-top imports of `DefaultFeatureEngineering` or `ModelRegistry` (import inside `execute()` and `_train_single_model()`).
- [ ] Type hints use string annotations (no runtime import).
- [ ] `pytest tests/test_core_layering.py::test_core_has_no_module_level_imports_to_concrete_packages` passes.
- [ ] `pytest tests/` green (all existing tests pass).
- [ ] `from energizados.core import BaseETL` resolves and `BaseETL.__module__` is `"energizados.contracts"`.
- [ ] After `import energizados.core`, `energizados.etl|evaluation|inference|modeling|feature_engineering` are NOT in `sys.modules` (unless explicitly imported elsewhere).

## Open Questions

None. The 6-edge scope is verified and well-defined.

## Edges Covered (6)

| # | File:line | Mechanism | Instantiation Line |
|---|-----------|-----------|-------------------|
| 1 | `core/__init__.py:20` | Repoint to `contracts` | N/A (re-export) |
| 2 | `core/builders/etl_builder.py:11` | Lazy import in `build()` | Line 35: `ETLOrchestrator(etl_configs)` |
| 3 | `core/builders/evaluation_builder.py:12` | Lazy import in `build()` | Line 66: `DefaultEvaluator(...)` |
| 4 | `core/builders/inference_builder.py:19` | Lazy import in `build()` | Line 51: `InferenceClass = DefaultInference` |
| 5 | `core/steps/training.py:17` | Lazy import in `execute()` | Line 306: `DefaultFeatureEngineering(...)` |
| 6 | `core/steps/training.py:18` | Lazy import in `_train_single_model()` | Line 592: `ModelRegistry.get(model_type)` |
