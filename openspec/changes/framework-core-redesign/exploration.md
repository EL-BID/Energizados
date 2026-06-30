# Exploration: Framework Core Architecture Redesign

> **Mode**: openspec (artifacts) + engram backup (`sdd/framework-core-redesign/explore`)
> **Phase**: sdd-explore
> **Status**: All 4 findings re-verified against CURRENT code (post surgical fixes). All hold.
> **Verdict**: This is NOT one change. Recommend **4 independent SDD changes**, sequenced.

---

## Current State (verified against `src/energizados/` today)

The framework is ~34,000 LOC across ~140 modules with 34 test files. It works, but its
core architecture has four confirmed structural defects. Recent surgical fixes (calibration,
split_builder, `BaseETL.__init__`, hierarchical FE, `_CalibratedWrapper`, removal of dead
`InferenceRegistry`) did NOT touch any of these four — they are still live.

### Finding 1 — `core` is a god-package with a circular dependency (VERIFIED)

- `core/__init__.py:20` → `from energizados.etl.base import BaseETL` (**core imports etl**).
- Every builder imports a **concrete** collaborator:
  - `eda_builder.py:11` → `DatasetExplorer`
  - `etl_builder.py:11` → `ETLOrchestrator`
  - `inference_builder.py:19` → `DefaultInference`
  - `evaluation_builder.py:12` → `DefaultEvaluator`
  - `training.py:17,18` → `DefaultFeatureEngineering`, `ModelRegistry`
- The reverse arrow is real too: `etl/orchestrator.py:17`, `etl/base.py:111`, `etl/pipeline.py:18`,
  `inference/base.py:8`, `inference/hierarchical.py:16`, `inference/default.py:14`,
  `modeling/ensemble.py:13`, `modeling/adapters.py:14`, `evaluation/evaluator.py:15` all
  import `energizados.core.{base,exceptions}`. **Dependency points both ways.**

### Finding 2 — Contract layer is decorative and fragmented (VERIFIED)

- `core/base.py` defines ONLY `BaseModel`, `BaseInference`, `PipelineStep`.
- **`BasePipeline` and `BaseEvaluator` do not exist** (documented but absent). `DefaultEvaluator`
  inherits `PipelineStep` directly (`evaluator/evaluator.py:24`).
- Base classes are scattered across **5 packages**: `etl/base.py:BaseETL`,
  `feature_engineering/base.py:BaseFeatureEngineering`, `feature_selection/base.py:BaseFeatureSelector`,
  `eda/base.py:BaseExplorer`, `core/base.py:{BaseModel,BaseInference,PipelineStep}`.
- **Contract violations**:
  - `HierarchicalInference.load_model -> HierarchicalModelContainer` (`hierarchical.py:91`) violates
    `BaseInference.load_model -> BaseModel` (`core/base.py:176`). `HierarchicalModelContainer` is a
    plain dict-wrapper, not a `BaseModel`.
  - `CleanFilesETL` is a `BaseETL` but its `extract/transform/load` all `raise NotImplementedError`
    (`etl/pipeline.py:1529/1532/1535`) — the abstract methods are part of the contract it breaks.
  - `FeatureSelectionPipeline` (`feature_selection/pipeline.py:115`) does **not** inherit
    `BaseFeatureSelector`.
- **save/load asymmetry**: `BaseFeatureEngineering` has `save()/load()`; `BaseModel`,
  `BaseFeatureSelector`, `BaseETL` have **none**.
- `BaseInference.load_model`/`save_predictions` are `raise NotImplementedError` stubs, not abstract.

### Finding 3 — Exception hierarchy is incoherent (VERIFIED)

- `core/exceptions.py` defines `EnergizadosError` → `{PipelineError, StepValidationError,
  ConfigurationError, ModelNotFittedError, ETLError, ETLDependencyError}`.
- **94 bare `raise ValueError/RuntimeError/TypeError/NotImplementedError` sites** across the source
  (grep-confirmed), e.g. split.py (11), preprocessing.py (8), feature_selection/methods.py (10),
  feature_engineering/default.py (5).
- **Same concept, different type**: `BaseModel.check_fitted` → `ModelNotFittedError`
  (`core/base.py:127`); `BaseFeatureEngineering.check_fitted` → bare `ValueError`
  (`feature_engineering/base.py:170`).
- **Error-type erasure at the boundary**: `Pipeline.run` (`pipeline.py:155`) wraps EVERY step
  exception in `PipelineError`, so a `ConfigurationError` or `ETLDependencyError` thrown inside a
  step is re-typed to `PipelineError` — callers cannot distinguish.
- **Missing**: no `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError`.

### Finding 4 — 4 parallel extension mechanisms (VERIFIED)

1. **`ModelRegistry`** (`modeling/registry.py`) — models only, a classmethod dict.
2. **`transformer_map`** — a hardcoded module-local dict in `feature_engineering/default.py:62`
   (names → `(class, default_params)`). Not a class, not extensible from outside without editing it.
3. **`_get_default_method_map()`** — another hardcoded dict in `feature_selection/pipeline.py:24`
   (method names → selector classes).
4. **`custom_class` + `import_class` allowlist** (`core/utils/import_utils.py`) — generic fallback
   for ETLs, transformers, evaluators, inference, feature engineering.

- **The model registry is bypassed for param prep**: `_prepare_model_params`
  (`training.py:812-855`) is a hardcoded if/elif ladder mapping `model_type` strings → constructor
  param shapes. Adding a model means editing BOTH the registry AND this ladder. `ModelRegistry.get`
  resolves the class (`training.py:592`), but the ladder decides its kwargs.
- **`_build_meta_learner` is broken for non-sklearn meta-learners** (`ensemble.py:199-213`): it does
  `ModelRegistry.get(meta_type)` which returns an adapter whose `predict_proba` returns **1D**, then
  calls `self._meta_learner.predict_proba(base_preds)[:, 1]` (`ensemble.py:232`) which expects **2D**.
  Only `logistic_regression` (built directly) works; any model-type meta-learner is broken.

---

## Affected Areas

- `src/energizados/core/__init__.py`, `core/base.py`, `core/exceptions.py`, `core/pipeline.py`
- `src/energizados/core/builders/{__init__,director,eda_builder,etl_builder,evaluation_builder,inference_builder,training_builder,base}.py`
- `src/energizados/core/steps/{training,split}.py`
- `src/energizados/core/utils/import_utils.py`
- `src/energizados/{etl,feature_engineering,feature_selection,modeling,inference,evaluation,eda}/base.py`
- `src/energizados/modeling/{registry,ensemble,adapters}.py`
- `src/energizados/inference/{default,hierarchical}.py`
- `src/energizados/feature_selection/pipeline.py`, `feature_engineering/default.py`
- `src/energizados/evaluation/evaluator.py`
- **`src/energizados/templates/**`** — generated projects import `SourceETL`, `BaseFeatureSelector`,
  `BaseInference`; etl.yaml.tpl documents `ClipOutliersETL`/`GeoFeaturesETL`/`CleanFilesETL` paths.
  These public paths MUST survive any move.

---

## Approaches

### Finding 1 — core layering

**1A. Dependency-injection seams in builders (recommended)**
- Builders stop importing concretes at module top; accept collaborator factories in `__init__`
  (default factory = the concrete class, so YAML behavior is unchanged). `core/__init__.py` stops
  re-exporting `BaseETL` (the literal cycle).
- Changes: 8 builder files, `core/__init__.py`, `director.py`. Move `BaseETL` import out of
  `core/__init__`.
- Pros: kills the cycle; tests can inject fakes; no public-path change; pickle-safe.
- Cons: introduces a factory/param on builders; must keep default behavior identical.
- Effort: **Medium** (~250-350 lines, 1-2 PRs).

**1B. Introduce `core/protocols.py` (typing Protocols) + builders depend on Protocols**
- Define `EvaluatorProtocol`, `InferenceProtocol`, `ETLOrchestratorProtocol`, `FeatureEngineeringProtocol`.
  Builders type-hint against protocols; concretes are imported lazily inside methods.
- Pros: structural typing, no inheritance coupling; fully pickle-safe (no class moves).
- Cons: Protocols add indirection; runtime still imports concretes (lazy) so cycle only deferred.
- Effort: **Medium-High** (~300-400 lines).

**1C. Extract a thin `energizados.contracts` package that neither imports nor is imported by core**
- Base classes + protocols live in `contracts`; `core` imports `contracts`; packages import
  `contracts`. Core no longer imports etl.
- Pros: cleanest layering; natural home for Finding 2's consolidation.
- Cons: bigger blast radius; couples directly to Finding 2.
- Effort: **High** (~400-600 lines) — overlaps Finding 2.

**Recommendation: 1A** as the standalone `core-layering` change. It is the smallest move that
actually removes the `core↔etl` import cycle, is fully pickle-safe (no class moves), and leaves
door open for 1C later. Do NOT bundle 1C with contracts consolidation — keep them reviewable.

---

### Finding 2 — contract consolidation

**2A. Create `energizados.contracts` (or `core/contracts.py`) + add the missing bases, keep old paths as re-export aliases (recommended)**
- New home for `BaseModel, BaseInference, BasePipeline, BaseEvaluator, BaseETL,
  BaseFeatureEngineering, BaseFeatureSelector, BaseExplorer`. Existing modules
  (`etl/base.py`, etc.) become **shim re-exports** (`from energizados.contracts import BaseETL`).
- Add the missing `BasePipeline`, `BaseEvaluator`; make `BaseInference.load_model`/`save_predictions`
  `@abstractmethod`.
- Fix violations: `FeatureSelectionPipeline(BaseFeatureSelector)`; `CleanFilesETL` either gets a
  `noop_load` hook on `BaseETL` or a separate `BaseFileETL`; `HierarchicalInference` typed against
  a `ModelContainer` protocol (update `BaseInference.load_model` return type to a Protocol).
- Normalize save/load: add `save()/load()` to `BaseModel`, `BaseFeatureSelector` (or factor a
  `SerializableMixin`).
- **Pickle safety**: concrete classes (`LGBMModelAdapter`, `DefaultFeatureEngineering`, etc.) keep
  their `__module__` — only base classes move, and pickle stores the concrete class. So existing
  `model.pkl` / `feature_engineering.pkl` load unchanged. Old import paths survive via shims.
- Pros: single source of truth; fixes all violations; zero pickle risk; backward-compatible imports.
- Cons: largest single change; many small touches.
- Effort: **Medium-High** (~350-500 lines) — likely needs 2 chained PRs (2A-i add contracts+shims;
  2A-ii fix violations + save/load normalization).

**2B. In-place fixes only (no consolidation)**
- Leave base classes where they are; just fix the violations (FeatureSelectionPipeline inheritance,
  CleanFilesETL, HierarchicalInference typing, add BaseEvaluator, normalize save/load).
- Pros: tiny blast radius; no move at all.
- Cons: fragmentation remains; does not address the "scattered across 5 packages" problem.
- Effort: **Low-Medium** (~150-250 lines).

**Recommendation: 2B-first, 2A-later.** Do the cheap violation fixes inside the
`contracts-consolidation` change as PR #1, then the contracts extraction as PR #2. This keeps each
PR under the 400-line budget and de-risks pickle compatibility (shims are added before anything is
moved in earnest).

---

### Finding 3 — exception hierarchy

**3A. Add the missing exception types + a catch-and-preserve rule (recommended)**
- Add `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError` (all subclass
  `EnergizadosError`). Keep existing types.
- Normalize "not fitted": introduce a single `NotFittedError(EnergizadosError)` (or reuse
  `ModelNotFittedError` renamed/aliased) used by `check_fitted` everywhere.
- **Fix the erasure**: in `Pipeline.run`, re-raise `EnergizadosError` subclasses **as-is**, only
  wrapping truly unexpected `Exception` into `PipelineError`. Preserve the original via `from e`.
- Sweep: replace the highest-value bare raises (check_fitted paths, config validation, public API
  entry points) — NOT a mechanical 94-site rewrite (that's noisy and review-hostile).
- Changes: `core/exceptions.py`, `core/pipeline.py`, `core/base.py`,
  `feature_engineering/base.py`, `feature_selection/base.py` (+ selective call sites).
- Pros: fully backward-compatible (new types subclass the base; `except EnergizadosError` still
  catches); no class moves → pickle-safe; high value-per-line.
- Cons: must choose the sweep scope carefully to stay in budget.
- Effort: **Low-Medium** (~150-250 lines).

**3B. Full 94-site migration to typed exceptions**
- Pros: complete consistency.
- Cons: huge, noisy diff; review-hostile; many raises are internal preconditions where `ValueError`
  is arguably fine.
- Effort: **High** (~600-900 lines).

**Recommendation: 3A.** Do this FIRST. It is the most independent (no dependency on 1/2/4), lowest
pickle risk (exceptions are rarely pickled; subclassing keeps `except` clauses working), and
delivers the boundary-erasure fix which has real runtime value.

---

### Finding 4 — unified registry

**4A. Single `Registry` abstraction with per-domain instances + adapter-param adapters (recommended)**
- Generalize `ModelRegistry` into a reusable `Registry` (in `core/registry.py` or `contracts`).
  Create `model_registry`, `transformer_registry`, `selector_registry` instances. `transformer_map`
  and `_get_default_method_map` register into it; built-ins self-register via a decorator.
- Replace the `_prepare_model_params` if/elif ladder with a **param-adapter** per model family
  (each adapter knows how to translate YAML config → constructor kwargs). `ModelRegistry` stores
  `(class, param_adapter)`. Adding a model = one registration entry, not two edits.
- Fix `_build_meta_learner`: require meta-learner candidates to expose a 2D `predict_proba`, or wrap
  adapter meta-learners in the existing `_SklearnCalibWrapper` shim (the 1D→2D bridge already
  exists in `training.py`). Reject unsupported meta types with a clear error.
- Keep `custom_class`/`import_class` as the escape hatch — but register imported classes too.
- Pros: one mechanism; kills the ladder; fixes meta-learner; extensible without core edits.
- Cons: touches the most files; highest review surface; must preserve YAML semantics exactly.
- Effort: **High** (~450-650 lines) — needs 2-3 chained PRs.

**4B. Minimal: kill the ladder only, keep parallel maps**
- Move `_prepare_model_params` logic into per-adapter classes (adapters carry their own
  `from_config(cfg, X) -> kwargs`); leave `transformer_map` and selector map as-is.
- Pros: smaller; fixes the most-irksome part (ladder + meta-learner).
- Cons: still 3 mechanisms; doesn't unify.
- Effort: **Medium** (~250-350 lines).

**4C. Full unification including transformers/selectors**
- Pros: one story for the whole framework.
- Cons: largest blast radius; transformers/selectors have different default-param semantics.
- Effort: **High** (~500-700 lines).

**Recommendation: 4A, done LAST, split into chained PRs:** (i) introduce `Registry` abstraction +
migrate model registry + kill ladder via per-adapter `from_config`; (ii) fix `_build_meta_learner`;
(iii) migrate transformer_map + selector map into registries. Do this after 1/2/3 land so it builds
on the cleaned layering and contracts.

---

## Recommended SCOPE / SPLIT

**Do NOT attempt this as one change.** A single change would be ~1,500-2,500 lines — 4-6× the
400-line review budget. Split into **4 independent SDD changes**, sequenced by dependency and risk:

| # | Change name | Finding | Est. lines | PRs | Depends on | Pickle risk |
|---|-------------|---------|-----------|-----|------------|-------------|
| 1 | `exception-hierarchy` | 3 | 150-250 | 1 | none | **None** |
| 2 | `contracts-consolidation` | 2 | 350-500 | 2 (chained) | ideally 1, can run parallel | Low (shims) |
| 3 | `core-layering` | 1 | 250-350 | 1-2 | ideally 2 | None |
| 4 | `unified-registry` | 4 | 450-650 | 2-3 (chained) | 1, 2, 3 | Low (no class moves) |

**Sequencing rationale:**
- **`exception-hierarchy` first** — zero coupling to the others, zero pickle risk (new types
  subclass the base; `except` clauses keep working), fixes the boundary erasure which has immediate
  runtime value. Quick win that builds momentum.
- **`contracts-consolidation` second** — adds the contracts home + fixes violations. Soft-depends
  on nothing hard, but benefits from having the exception types available (e.g. `NotFittedError`).
  Split: PR-i = add contracts + shims (additive, safe); PR-ii = violation fixes + save/load.
- **`core-layering` third** — breaks the cycle via DI seams (1A). Builds cleanly on the contracts
  layer (builders can now type-hint against the consolidated bases).
- **`unified-registry` last** — biggest and most invasive; should land on the cleaned layering.
  Chained: ladder-kill + meta-learner fix first, registry unification second.

**Cross-dependency note:** Only hard dependency is "core-layering benefits from
contracts-consolidation." Everything else is independent enough to reorder if priorities shift.

---

## Risks

### Pickle / model compatibility (CRITICAL)
- `secure_pickle` (`core/utils/secure_pickle.py`) uses **joblib** with a SHA-256 `.sig` sidecar.
  joblib pickles store each object's `(module, qualname)`.
- **Good news**: pickle stores the **concrete** class (`LGBMModelAdapter`,
  `DefaultFeatureEngineering`), not the base class. Moving **base** classes is therefore
  pickle-safe AS LONG AS concrete classes keep their `__module__`. Existing `model.pkl` /
  `feature_engineering.pkl` from past experiments (CELESC v3/v4, etc.) continue to load.
- **Hard rule for every change**: concrete classes (`*Adapter`, `Default*`, `SourceETL`,
  `ClipOutliersETL`, `GeoFeaturesETL`, `CleanFilesETL`) MUST NOT change their import path. If any
  must move, add a backward-compat alias (`sys.modules` registration or a shim module that
  re-exports the class under its old path) AND a one-time migration test that round-trips a legacy
  pickle.
- **Mitigation**: add a test fixture with a "frozen" legacy pickle + its `.sig` and assert it loads
  after each change.

### Public extension-point compatibility (CRITICAL)
- Generated projects and user configs reference, via `custom_class` / imports:
  `energizados.etl.pipeline.{SourceETL,ClipOutliersETL,GeoFeaturesETL,CleanFilesETL}`,
  `energizados.feature_selection.base.BaseFeatureSelector`,
  `energizados.inference.base.BaseInference`, `energizados.etl.base.BaseETL`.
- **Hard rule**: every one of these import paths MUST keep resolving. Use shim re-exports, never
  bare moves. Add a compatibility test that imports each documented public path.

### 400-line review budget
- No single change above fits comfortably in one PR except `exception-hierarchy`.
- `contracts-consolidation` and `unified-registry` are explicitly planned as **chained PRs**.
- Delivery strategy is `ask-always` → orchestrator must confirm chaining before each apply.

### Test surface
- 34 test files. `strict_tdd: true` (RED-GREEN-REFACTOR). Each change must add/adjust tests;
  `pytest tests/` is the gate. Largest risk is in `contracts-consolidation` (touches inheritance)
  and `unified-registry` (touches model construction).

### The `_anterior` / 12-month domain leak (5th finding — OUT OF SCOPE)
- Not part of this redesign. **Interaction note**: `_prepare_model_params` (finding 4 ladder) and
  several transformers hardcode `"_anterior"` / `num_periodos=12`. When the unified-registry change
  refactors the ladder, avoid entangling the domain-leak fix — keep them separate concerns so the
  (future) `_anterior` generalization is a clean follow-up.

---

## Ready for Proposal

**Yes — but as a PROGRAM, not a single proposal.** Recommended next step:

1. Create **one** proposal per change in the sequence above, starting with
   `exception-hierarchy`. Each proposal should state: scope, approach (from this exploration),
   rollback plan (shim/alias strategy), and impact on existing experiments/models.
2. Do NOT open a single umbrella proposal — it would exceed the budget and blur review.

**What the orchestrator should tell the user:** "The 4 confirmed findings are verified still-live.
A single redesign would blow the 400-line budget ~5×. I recommend 4 sequenced SDD changes
(exception-hierarchy → contracts-consolidation → core-layering → unified-registry), the first of
which is low-risk and pickle-safe. Confirm the split and I'll start the `exception-hierarchy`
proposal."

---

## Skill Resolution
paths-injected — orchestrator forwarded the skill-load instruction; I read `.atl/skill-registry.md`
then loaded `sdd-explore/SKILL.md` and `_shared/{sdd-phase-common,openspec-convention}.md` before
investigating.
