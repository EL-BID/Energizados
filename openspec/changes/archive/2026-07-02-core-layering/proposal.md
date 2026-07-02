# Proposal: Core Layering

## Intent

The `energizados.core` package has **module-level import edges into concrete implementation packages** (`etl`, `evaluation`, `inference`) that close circular dependencies. This violates architectural layering: the foundation (`core`) should not depend on the packages built atop it. The cycles complicate reasoning, make the module graph harder to understand, and block treating `core` as a stable foundation.

This change cuts the 4 cycle-closing edges using the smallest viable mechanism (import repoint + lazy imports), with **zero behavior change**. DI seams (factory params for fake injection) are explicitly deferred to a follow-up change.

## Scope

### In Scope

**Scope (a'): "kill-cycle" only — the 4 cycle-closing edges**

| # | Edge | File:line | Action |
|---|------|-----------|--------|
| 1 | `core/__init__.py:20` `from energizados.etl.base import BaseETL` | **Repoint** to `from energizados.contracts import BaseETL`. The re-export in `core/__init__.py` keeps `from energizados.core import BaseETL` working. |
| 2 | `core/builders/etl_builder.py:11` `from energizados.etl.orchestrator import ETLOrchestrator` | **Lazy import**: move the import inside `build()` method (line 35, where `ETLOrchestrator(etl_configs)` is called). Handle the type hint on line 45 via string annotation (no module-level import). |
| 3 | `core/builders/evaluation_builder.py:12` `from energizados.evaluation import DefaultEvaluator` | **Lazy import**: move inside `build()` method (line 66, where `DefaultEvaluator(...)` is called). No type hint uses this class. |
| 4 | `core/builders/inference_builder.py:19` `from energizados.inference.default import DefaultInference` | **Lazy import**: move inside `build()` method (line 51, where `InferenceClass = DefaultInference` is assigned). No type hint uses this class. |

**Cycle verification test:**
- Add a test that asserts `core` has **ZERO module-level imports** of `etl`/`evaluation`/`inference`/`modeling`/`feature_engineering`/`eda`. Implement as a grep-based or AST-based check in `tests/`.

**Success criterion:**
- After the change, `import energizados.core` does NOT cause `energizados.etl`/`evaluation`/`inference` to appear in `sys.modules` (or the equivalent static check).
- All existing tests pass (`pytest tests/`).
- `from energizados.core import BaseETL` still resolves (re-exported from `contracts`).

### Out of Scope

**Edge 5 — NOT a cycle (explicitly deferred):**
- `core/builders/eda_builder.py:11` `from energizados.eda.dataset_explorer import DatasetExplorer`
- Rationale: `eda` does NOT import `core` at module level. This is one-way coupling, not a cycle. Leave as-is.

**`training.py` edges — NOT cycles (explicitly deferred):**
- `core/steps/training.py:17` `from energizados.feature_engineering import DefaultFeatureEngineering`
- `core/steps/training.py:18` `from energizados.modeling.registry import ModelRegistry`
- Rationale: `feature_engineering` and `modeling.registry` do NOT import `core` at module level. These are one-way couplings, not cycles. Leave as-is.

**DI seams — EXPLICITLY deferred to a separate follow-up change:**
- Factory parameters on builders for fake injection (the original Approach 1A testability goal).
- This change does NOT add the ability to inject fakes in tests. Lazy imports kill the cycle but keep the collaborator hardcoded.
- Rationale: keeps this PR small and focused on the architectural defect (the cycle). DI-seams work is a legitimate testability improvement but has no current forcing function — defer until there's a concrete testing need.

**Other Findings from framework-core-redesign (out of scope for this change):**
- Finding 2 (contracts consolidation) — already completed in change #2.
- Finding 3 (exception hierarchy) — already completed in change #1.
- Finding 4 (unified registry) — deferred to change #4.

## Capabilities

### New Capabilities

- **`core-layering`**: `core` becomes a true foundation with zero module-level edges into concrete packages. The dependency graph is now a DAG (concrete packages can import `core`, but `core` does not import them at module load time).

### Modified Capabilities

- **`core`** (behavior unchanged):
  - `BaseETL` import path via `energizados.core.BaseETL` still works (re-exported from `contracts`).
  - Builders (`ETLBuilder`, `EvaluationBuilder`, `InferenceBuilder`) behavior unchanged — lazy imports reproduce identical instantiation timing.

## Approach

**Scope (a') with the 4 edges**

### Edge 1: Repoint `core/__init__.py:20`

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
- `energizados.etl.base` is a shim that also re-exports from `contracts`, so existing code using `from energizados.etl.base import BaseETL` continues to work unchanged.

### Edge 2: Lazy import in `etl_builder.py`

**Current (module-level import):**
```python
# src/energizados/core/builders/etl_builder.py:11
from energizados.etl.orchestrator import ETLOrchestrator
```

**After (lazy import inside `build()` method):**
```python
# Remove module-top import (line 11)

def build(self) -> Optional[PipelineStep]:
    # Import inside the method
    from energizados.etl.orchestrator import ETLOrchestrator

    orchestrator = ETLOrchestrator(etl_configs)
    # ... rest of method
```

**Type hint handling (line 45):**
```python
# Current:
def __init__(self, orchestrator: ETLOrchestrator, etl_names: List[str]):

# After (string annotation OR from __future__ import annotations):
def __init__(self, orchestrator: "ETLOrchestrator", etl_names: List[str]):
```

**Verification:** `ETLOrchestrator` is instantiated only at line 35, inside `build()`. No module-level singleton or class-attribute uses it.

### Edge 3: Lazy import in `evaluation_builder.py`

**Current (module-level import):**
```python
# src/energizados/core/builders/evaluation_builder.py:12
from energizados.evaluation import DefaultEvaluator
```

**After (lazy import inside `build()` method):**
```python
# Remove module-top import (line 12)

def build(self) -> Optional[PipelineStep]:
    # Import inside the method
    from energizados.evaluation import DefaultEvaluator

    # ... (config parsing)

    return DefaultEvaluator(
        input_path=eval_config.get("input_path"),
        # ... kwargs
    )
```

**Verification:** `DefaultEvaluator` is instantiated only at line 66. No type hint uses this class. No module-level use.

### Edge 4: Lazy import in `inference_builder.py`

**Current (module-level import):**
```python
# src/energizados/core/builders/inference_builder.py:19
from energizados.inference.default import DefaultInference
```

**After (lazy import inside `build()` method):**
```python
# Remove module-top import (line 19)

def build(self) -> Optional[PipelineStep]:
    # ... (config parsing)

    # Import inside the method
    if custom_class:
        InferenceClass = import_class(custom_class)
    else:
        from energizados.inference.default import DefaultInference
        InferenceClass = DefaultInference
```

**Verification:** `DefaultInference` is only assigned to `InferenceClass` at line 51. No type hint uses this class. No module-level use.

### Cycle verification test

Add `tests/test_core_layering.py` (or extend an existing test):
```python
def test_core_has_no_module_level_imports_to_concrete_packages():
    """Verify core has zero module-level imports to concrete packages."""
    import ast
    import sys

    core_module = sys.modules.get("energizados.core")
    assert core_module is not None, "energizados.core should be importable"

    # Get the source file paths for core package
    import importlib.util
    spec = importlib.util.find_spec("energizados.core")
    core_path = spec.origin

    # Parse all .py files under src/energizados/core/
    concrete_imports = []
    for py_file in Path("src/energizados/core").rglob("*.py"):
        source = py_file.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("energizados.etl") \
                        or alias.name.startswith("energizados.evaluation") \
                        or alias.name.startswith("energizados.inference") \
                        or alias.name.startswith("energizados.modeling") \
                        or alias.name.startswith("energizados.feature_engineering") \
                        or alias.name.startswith("energizados.eda"):
                        concrete_imports.append((py_file, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module and (
                    node.module.startswith("energizados.etl")
                    or node.module.startswith("energizados.evaluation")
                    or node.module.startswith("energizados.inference")
                    or node.module.startswith("energizados.modeling")
                    or node.module.startswith("energizados.feature_engineering")
                    or node.module.startswith("energizados.eda")
                ):
                    concrete_imports.append((py_file, node.module))

    assert len(concrete_imports) == 0, \
        f"Found {len(concrete_imports)} module-level imports to concrete packages: {concrete_imports}"
```

**Alternative implementation (simpler, grep-based):**
```python
def test_core_has_no_module_level_imports_to_concrete_packages_grep():
    """Verify core has zero module-level imports to concrete packages (grep version)."""
    import subprocess
    result = subprocess.run(
        ["grep", "-r", "^from energizados.etl\\|^from energizados.evaluation\\|^from energizados.inference\\|^from energizados.modeling\\|^from energizados.feature_engineering\\|^from energizados.eda",
         "src/energizados/core/"],
        capture_output=True,
        text=True
    )
    assert result.returncode != 0, "grep should find no matches (return code non-zero)"
    assert result.stdout == "", f"Found module-level imports: {result.stdout}"
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/core/__init__.py` | Modified | Repoint `BaseETL` import from `etl.base` to `contracts`. Re-export keeps public path working. |
| `src/energizados/core/builders/etl_builder.py` | Modified | Move `ETLOrchestrator` import from module-top into `build()` method. Type hint becomes string annotation. |
| `src/energizados/core/builders/evaluation_builder.py` | Modified | Move `DefaultEvaluator` import from module-top into `build()` method. |
| `src/energizados/core/builders/inference_builder.py` | Modified | Move `DefaultInference` import from module-top into `build()` method. |
| `tests/test_core_layering.py` (or equivalent) | New | Test asserting absence of module-level imports from `core` to concrete packages. |
| `AGENTS.md` | Modified | Document the `core` layering guarantee (no cycles). |

**Impact on existing experiments/models:** none. No class moves, no behavior change. Old `model.pkl`/`feature_engineering.pkl` files load unchanged.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Pickle format break** | None | No class moves. Only import repoints + lazy moves. Concretes keep `__module__`. Zero pickle risk. |
| **Public-path compat break** | None | `from energizados.core import BaseETL` still works (re-exported from `contracts`). Add test to verify. |
| **Behavior change from lazy imports** | Low | Lazy imports must reproduce identical instantiation timing. Verify per builder that the concrete is not used at module load time (no module-level singleton/class-attribute referencing it). All verified: `ETLOrchestrator` instantiated only at line 35; `DefaultEvaluator` at line 66; `DefaultInference` at line 51. |
| **Type hint breakage** | Low | Use string annotations (`"ETLOrchestrator"`) OR add `from __future__ import annotations` at module top (PEP 563). Verify with `mypy` or equivalent. |
| **Edge 5 / training.py edges mistakenly included** | Low | Explicitly document them as out of scope. Verify in spec/design that they are NOT touched. |
| **DI seams expected but missing** | Medium | This change does NOT add fake-injection capability. Make the trade-off conscious and explicit. Document that DI-seams work is deferred to a follow-up change. |
| **Lazy import timing edge case** | Low | If a builder's `build()` method is called at module load time (e.g., in a class-attribute default), the lazy import would still execute early. Verify builders are only instantiated via `ConfigPipelineBuilder` (runtime, not module load). Current code: builders are instantiated by `Director` from YAML, which is runtime. |

## Rollback Plan

**Pure revert.** No persisted artifacts affected. All changes are import statement relocations within `core` package. Concretes untouched → pickle-safe.

If `from energizados.core import BaseETL` appears broken after revert, verify that `core/__init__.py` was restored to `from energizados.etl.base import BaseETL`.

## Dependencies

**Soft-depends on change #2 (`contracts-consolidation`):**
- Edge 1 repoints to `energizados.contracts`, which was created in change #2.
- If change #2 is not yet merged, this change cannot land as-is (would need to repoint to `etl.base` instead, which defeats the purpose).
- **Assumption:** change #2 (`contracts-consolidation`) has landed and `energizados.contracts` exists.

**No other dependencies:** Independent of Findings 3 and 4.

## Success Criteria

**Code changes:**
- [ ] `core/__init__.py:20` imports `BaseETL` from `energizados.contracts` (not `etl.base`).
- [ ] `etl_builder.py` has no module-top import of `ETLOrchestrator` (import inside `build()`).
- [ ] `evaluation_builder.py` has no module-top import of `DefaultEvaluator` (import inside `build()`).
- [ ] `inference_builder.py` has no module-top import of `DefaultInference` (import inside `build()`).
- [ ] Type hints handled via string annotations OR `from __future__ import annotations`.

**Tests:**
- [ ] `pytest tests/` green (all existing tests pass).
- [ ] New test `test_core_has_no_module_level_imports_to_concrete_packages` passes (grep or AST-based).
- [ ] Public-path test: `from energizados.core import BaseETL` resolves and `issubclass(SourceETL, BaseETL)` passes.

**Cycle verification:**
- [ ] After `import energizados.core`, the modules `energizados.etl`, `energizados.evaluation`, `energizados.inference` are NOT in `sys.modules` (unless explicitly imported elsewhere).
- [ ] Grep/AST check confirms zero module-level imports from `core` to concrete packages.

**Budget:**
- [ ] Diff ≤ ~100 lines (well under 400-line budget).

## Open Questions

None. The scope is narrow and well-defined.

## Next Recommended

`spec` — elaborate the 4 edge changes with concrete before/after code snippets, verify each builder's instantiation timing, and specify the cycle-verification test implementation.
