# Exploration: core-layering (re-scoped against current code)

> Change #3 of the `framework-core-redesign` program. Finding 1.
> **Re-investigation** — the program-level `exploration.md` (Finding 1 + Approach 1A) is STALE: it
> predates change #2 (`contracts-consolidation`), which moved the 8 base classes into
> `energizados.contracts` and turned the old base modules into shim re-exports. Every claim below is
> verified against the source on `release/0.2.x` @ `e7135c4` (post change #2).

## What change #2 already did for Finding 1

- `BaseETL`, `BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`, `BaseFeatureEngineering`,
  `BaseFeatureSelector`, `BaseExplorer` now live in `src/energizados/contracts.py`.
- `src/energizados/contracts.py` imports **nothing** from `energizados` at module level — it is a
  **clean leaf** in the dependency graph. (`check_fitted` imports `core.exceptions` lazily inside the
  method, which does not create a module-level edge.)
- The old `*/base.py` modules are shim re-exports (`from energizados.contracts import BaseETL`).

This is most of the original Approach **1C** (extract `energizados.contracts` as a peer package). What
remains is the actual **import-edge cleanup** so `core` no longer reaches into `etl` (and the other
concrete packages) at module load time.

## Current dependency graph (verified)

### Module-level edges FROM `core` TO concrete packages (the problem direction)

| # | Edge | File:line | Target type | Forms a cycle? |
|---|------|-----------|-------------|----------------|
| 1 | `core → etl` | `core/__init__.py:20` `from energizados.etl.base import BaseETL` | **base class** (now a shim → contracts) | Yes |
| 2 | `core → etl` | `core/builders/etl_builder.py:11` `from energizados.etl.orchestrator import ETLOrchestrator` | **concrete** | Yes |
| 3 | `core → evaluation` | `core/builders/evaluation_builder.py:12` `from energizados.evaluation import DefaultEvaluator` | **concrete** | Yes |
| 4 | `core → inference` | `core/builders/inference_builder.py:19` `from energizados.inference.default import DefaultInference` | **concrete** | Yes |
| 5 | `core → eda` | `core/builders/eda_builder.py:11` `from energizados.eda.dataset_explorer import DatasetExplorer` | **concrete** | **No** (eda does not import core) |

(Lazy, in-method imports are NOT module-level edges and are fine: `core/builders/split_builder.py:61`
imports `ETLOrchestrator` inside a method. Leave as-is.)

`training` was not flagged at module-top in `core/builders/`; the original exploration referenced
`core/steps/training.py:17,18` — verify separately during spec/design if relevant.

### The reverse direction (etl/inference/evaluation/modeling → core) — CORRECT, keep

- `etl/orchestrator.py:17-18` → `core.exceptions`, `core.utils`
- `inference/default.py`, `inference/hierarchical.py` → `core`
- `evaluation/evaluator.py` → `core`
- `modeling/adapters.py`, `modeling/ensemble.py` → `core`
- `feature_engineering/default.py` → `core`

This direction is architecturally correct (concrete packages depend on the core foundation). It is NOT
the problem. The problem is edges 1–4 going the wrong way (core depending on concretes), which close
the cycle.

### Cycle membership

- Edge 1 (`core → etl.base`): closes the cycle because `etl.base` → `contracts` (clean) BUT the edge
  still points core→etl. Repointing to `contracts` removes it entirely.
- Edges 2, 3, 4 (`core/builders → concrete → core`): each closes a cycle because the concrete's package
  imports `core`. These are the "builders import concretes" half of Finding 1.
- Edge 5 (`core/builders → eda`): NOT a cycle (eda does not import core). Pure one-way coupling.

## How `ETLOrchestrator` is used in `etl_builder.py` (edge 2 feasibility)

```
11: from energizados.etl.orchestrator import ETLOrchestrator
35:     orchestrator = ETLOrchestrator(etl_configs)        # instantiated once, in a method
45:         def __init__(self, orchestrator: ETLOrchestrator, etl_names: List[str]):  # type hint
```

Instantiated once inside a method (line 35); used as a type hint (line 45). A **lazy import** (move
line 11 into the method, use a string/`from __future__ import annotations` for the hint) is feasible
with no behavior change. Same pattern likely applies to edges 3 and 4 (DefaultEvaluator,
DefaultInference) — confirm in spec.

## Scope options (honest re-assessment)

The cycle is NOT a 1-line fix (the first explore attempt was wrong). There are **4 cycle-closing
edges** to cut (1 + 2 + 3 + 4). Edge 5 is optional coupling.

### (a') SMALL — "kill-cycle" only
- Edge 1: repoint `core/__init__.py:20` → `from energizados.contracts import BaseETL`.
- Edges 2/3/4: move each concrete import from module-top into the method that uses it (lazy import),
  with string annotations for any type hints.
- Effort: ~4 files, ~tens of lines, **1 PR**.
- Outcome: **all core↔concrete cycles eliminated**; `core` becomes a true foundation.
- Trade-off: lazy imports kill the cycle but do **NOT** enable fake injection for builder unit tests
  (the collaborator is still hardcoded, just imported lazily).

### (b) FULL 1A — "kill-cycle + DI seams"
- Everything in (a') PLUS replace each builder's hardcoded concrete with a **factory parameter**
  injected via `__init__` (default factory = the concrete, so YAML behavior is unchanged).
- Adds the ability to inject fakes in tests (the original 1A testability goal).
- Effort: ~8 files (5 builders + director + `core/__init__` + tests), ~250–350 lines, **1–2 PRs**.

### (c) SPLIT (recommended)
- This change = **(a') kill-cycle** (small, high architectural value, low risk).
- Separate follow-up change = **builder DI seams** (the testability/fake-injection work), done when
  there's a concrete testing need driving it.
- Keeps each PR small, reviewable, and under the 400-line budget.

**Recommendation: (c).** The cycle is the architectural defect; killing it is cheap and unblocks
treating `core` as a foundation. The DI-seams work is a legitimate but separate testability
improvement with no current forcing function — defer it to its own change rather than bundling.

## Risks

- **Pickle safety**: no class moves here (only import repoints + lazy moves). Concretes keep
  `__module__`. Zero pickle risk.
- **Public-path compat**: `from energizados.core import BaseETL` keeps working (re-exported, just
  sourced from `contracts` now). No public API change.
- **Behavior preservation**: lazy imports must reproduce identical instantiation timing. Verify per
  builder in spec/design (especially any module-level singleton use).
- **Testability**: (a') does not add fake-injection capability; only (b) does. Make the trade-off
  consciously.

## Next

`next_recommended: propose` — formalize the chosen scope (recommend (c)/(a')) into a proposal.
