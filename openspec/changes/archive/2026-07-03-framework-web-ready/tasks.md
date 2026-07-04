# Tasks: framework-web-ready

**Archive-Time Reconciliation**: Task checkboxes for phases 4-9 were marked complete at archive time per orchestrator authorization — completion proven by verify-report (PASS WITH WARNINGS, 1450 passed, 0 CRITICAL). All 11 spec requirements verified as implemented.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350 lines (api/ package: 150; core modifications: 130; CLI updates: 70) |
| 400-line budget risk | Low (additive only, within budget) |
| Chained PRs recommended | No (cohesive feature, single PR) |
| Suggested split | Single PR (all phases) |
| Delivery strategy | ask-on-risk |
| Chain strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: single-pr
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Exception hardening (error_code + to_dict()) | PR1 | Base: release/0.2.x; raise-site audit included |
| 2 | Import safety narrowing + register_allowed_prefix() | PR1 | Depends on Unit 1; migration guide |
| 3 | Pipeline.from_dict() + plan() methods | PR1 | Independent of Units 1-2 |
| 4 | RunManager query API + metadata extension | PR1 | Independent of Units 1-3 |
| 5 | MetricsDict wrapper + metrics unification | PR1 | Independent of Units 1-4 |
| 6 | api/ package (validate, pipeline, run_state, progress, exceptions, config) | PR1 | Depends on Units 1-5 for core changes |
| 7 | CLI delegation + --json flags (run, validate, doctor) | PR1 | Depends on Unit 6 (api layer) |
| 8 | Parity tests + regression + docs | PR1 | Final verification phase |

## Phase 1: Exception Hardening (Foundation)

### 1.1 Audit Exception Raise Sites (Compatibility Check)

- [x] 1.1.1 Run `colgrep "raise EnergizadosError"` -k 20` to enumerate all raise sites of base exception
- [x] 1.1.2 Run `colgrep "raise ConfigurationError"` -k 20` to enumerate ConfigurationError raise sites
- [x] 1.1.3 Run `colgrep "raise ModelNotFittedError"` -k 20` to enumerate ModelNotFittedError raise sites
- [x] 1.1.4 Document each raise site with file:line and calling pattern (positional args vs kwargs)
- [x] 1.1.5 Verify no existing caller uses positional-only args that would break with new `**details` parameter

### 1.2 Add error_code and to_dict() to Base Exception (TDD)

- [x] 1.2.1 [TEST] Write RED test `test_energizados_error_error_code_default` asserting `EnergizadosError().error_code == "ENERGIZADOS_ERROR"`
- [x] 1.2.2 [TEST] Write RED test `test_energizados_error_to_dict_structure` asserting `EnergizadosError("msg").to_dict() == {"error_code": "ENERGIZADOS_ERROR", "message": "msg", "details": {}}`
- [x] 1.2.3 [TEST] Write RED test `test_energizados_error_per_instance_error_code_override` asserting `EnergizadosError("msg", error_code="CUSTOM").error_code == "CUSTOM"`
- [x] 1.2.4 [IMPL] Add `error_code: str = "ENERGIZADOS_ERROR"` class attribute to `EnergizadosError` (`core/exceptions.py:9`)
- [x] 1.2.5 [IMPL] Add `__init__(self, message: str, error_code: str = None, **details)` to `EnergizadosError`, storing `error_code` as instance attr if provided
- [x] 1.2.6 [IMPL] Add `to_dict(self) -> Dict[str, Any]` method returning `{"error_code": self.error_code, "message": str(self), "details": self.details}`
- [x] 1.2.7 [TEST] Verify Phase 1.2 tests turn GREEN

### 1.3 Update Subclasses with Specific error_codes (TDD)

- [x] 1.3.1 [TEST] Write RED test `test_configuration_error_error_code` asserting `ConfigurationError().error_code == "CONFIG_INVALID"`
- [x] 1.3.2 [TEST] Write RED test `test_configuration_error_to_dict_extended` asserting `to_dict()` includes `config_path` field
- [x] 1.3.3 [TEST] Write RED test `test_model_not_fitted_error_code` asserting `ModelNotFittedError().error_code == "MODEL_NOT_FITTED"`
- [x] 1.3.4 [IMPL] Add `error_code = "CONFIG_INVALID"` class attribute to `ConfigurationError` (`core/exceptions.py:68`)
- [x] 1.3.5 [IMPL] Update `ConfigurationError.__init__` to forward `error_code` parameter to base class
- [x] 1.3.6 [IMPL] Override `ConfigurationError.to_dict()` to include `config_path` field
- [x] 1.3.7 [IMPL] Add `error_code = "MODEL_NOT_FITTED"` to `ModelNotFittedError` (`core/exceptions.py:92`)
- [x] 1.3.8 [IMPL] Update `ModelNotFittedError.__init__` to forward `error_code` parameter to base class
- [x] 1.3.9 [IMPL] Add `error_code` class attributes to remaining exceptions: `PipelineError` (PIPELINE_EXECUTION_FAILED), `StepValidationError` (STEP_VALIDATION_FAILED), `ETLError` (ETL_EXECUTION_FAILED), `ETLDependencyError` (ETL_DEPENDENCY_CYCLE), `TransformerError` (TRANSFORM_FAILED), `FeatureSelectionError` (FEATURE_SELECTION_FAILED), `InferenceError` (INFERENCE_FAILED), `EvaluatorError` (EVALUATION_FAILED)
- [x] 1.3.10 [TEST] Verify Phase 1.3 tests turn GREEN

### 1.4 Verify Raise-Site Compatibility

- [x] 1.4.1 Run `pytest tests/` to confirm no existing raise sites break from signature changes
- [x] 1.4.2 Manually verify each raise site documented in Phase 1.1 still works with new signatures

## Phase 2: Import Safety Hardening

### 2.1 Narrow ALLOWED_PREFIXES and Add Extension Function (TDD)

- [x] 2.1.1 [TEST] Write RED test `test_import_class_blocked_prefix` asserting `import_class("dangerous.EvilClass")` raises `ConfigurationError` with `error_code="CONFIG_INVALID_CLASS_PREFIX"`
- [x] 2.1.2 [TEST] Write RED test `test_register_allowed_prefix` asserting `register_allowed_prefix("custom")` adds `"custom."` to `ALLOWED_PREFIXES`
- [x] 2.1.3 [TEST] Write RED test `test_register_allowed_prefix_existing_works` asserting after `register_allowed_prefix("data")`, `import_class("data.CustomClass")` succeeds
- [x] 2.1.4 [IMPL] Change `ALLOWED_PREFIXES` from list to set: `{"energizados.", "src."}` (`core/utils/import_utils.py:13-23`)
- [x] 2.1.5 [IMPL] Add `def register_allowed_prefix(prefix: str) -> None` function that adds trailing dot and inserts into set
- [x] 2.1.6 [IMPL] Update `import_class()` to raise `ConfigurationError` with per-instance `error_code="CONFIG_INVALID_CLASS_PREFIX"` instead of generic `ImportError`
- [x] 2.1.7 [IMPL] Update error message to list allowed prefixes when blocking import
- [x] 2.1.8 [TEST] Verify Phase 2.1 tests turn GREEN

### 2.2 Migration Guide for Existing Projects

- [x] 2.2.1 Add docstring to `register_allowed_prefix()` documenting thread-safety caveat (not thread-safe, call during setup)
- [x] 2.2.2 Add inline comment in `ALLOWED_PREFIXES` documenting narrowing from `["data.", "features.", "src."]` to `{"energizados.", "src."}`
- [x] 2.2.3 Prepare release notes snippet: "If your project uses custom classes from 'data.' or 'features.' prefixes, call `register_allowed_prefix()` before framework usage"

## Phase 3: Pipeline Dict Config Support

### 3.1 Add from_dict() Classmethod to Pipeline (TDD)

- [x] 3.1.1 [TEST] Write RED test `test_pipeline_from_dict_equivalence` asserting `Pipeline.from_dict(config)` and `Pipeline(config_path="/file.yaml")` produce equivalent pipelines when config dicts match
- [x] 3.1.2 [TEST] Write RED test `test_pipeline_from_dict_invalid_config` asserting `Pipeline.from_dict({"invalid": True})` still processes (doesn't raise — validation happens at run time)
- [x] 3.1.3 [IMPL] Add `@classmethod def from_dict(cls, config: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> "Pipeline"` to `Pipeline` class (`core/pipeline.py:31`)
- [x] 3.1.4 [IMPL] Implement `from_dict()` to return `cls(config=config)` (existing `__init__` already accepts dict)
- [x] 3.1.5 [TEST] Verify Phase 3.1 tests turn GREEN

### 3.2 Add plan() Method to Pipeline (TDD)

- [x] 3.2.1 [TEST] Write RED test `test_pipeline_plan_returns_steps` asserting `plan()` returns object with `steps` (list) and `dependencies` (dict) fields
- [x] 3.2.2 [TEST] Write RED test `test_pipeline_plan_reveals_dependency_cycle` asserting circular ETL dependencies raise `ETLDependencyError` with `error_code="ETL_DEPENDENCY_CYCLE"`
- [x] 3.2.3 [TEST] Write RED test `test_pipeline_plan_filters_disabled_steps` asserting plan excludes ETLs with `enabled: false`
- [x] 3.2.4 [IMPL] Add `def plan(self) -> ExecutionPlan` method to `Pipeline` class
- [x] 3.2.5 [IMPL] Implement `plan()` to build step list from config and validate ETL dependencies using existing `ETLOrchestrator` cycle detection
- [x] 3.2.6 [IMPL] Create `ExecutionPlan` dataclass in `core/pipeline.py` with `steps: List[str]`, `dependencies: Dict[str, List[str]]`, `estimated_duration: Optional[float]`
- [x] 3.2.7 [TEST] Verify Phase 3.2 tests turn GREEN

## Phase 4: RunState Query API

### 4.1 Extend RunMetadata and Add Query Methods (TDD)

- [x] 4.1.1 [TEST] Write RED test `test_run_metadata_from_dict_tolerant_loader` asserting `RunMetadata.from_dict({"run_id": "test"})` supplies defaults for missing fields
- [x] 4.1.2 [TEST] Write RED test `test_run_manager_get_run` asserting `RunManager().get_run(existing_id)` returns `RunMetadata`, `get_run("nonexistent")` returns `None`
- [x] 4.1.3 [TEST] Write RED test `test_run_manager_list_runs` asserting `list_runs()` returns list sorted by `start_time` descending
- [x] 4.1.4 [TEST] Write RED test `test_run_manager_get_latest_run` asserting `get_latest_run()` returns most recent run or `None`
- [x] 4.1.5 [IMPL] Extend `_write_run_metadata()` in `RunManager` to add `status` ("success"/"partial"/"failed") and `output_paths` (dict) to metadata JSON (`core/builders/run_manager.py:183`)
- [x] 4.1.6 [IMPL] Create `RunMetadata` dataclass in `core/builders/run_manager.py` with fields matching design plus `from_dict()` classmethod with tolerant loading
- [x] 4.1.7 [IMPL] Add `def get_run(self, run_id: str) -> Optional[RunMetadata]` method to `RunManager` class
- [x] 4.1.8 [IMPL] Add `def list_runs(self, filter: Optional[Dict] = None, limit: int = 100) -> List[RunMetadata]` method using `glob("*-*")` to discover all run types (train, eda, inference)
- [x] 4.1.9 [IMPL] Add `def get_latest_run(self) -> Optional[RunMetadata]` method calling `list_runs(limit=1)[0] if runs else None`
- [x] 4.1.10 [TEST] Verify Phase 4.1 tests turn GREEN

## Phase 5: Metrics Unification

### 5.1 Add MetricsDict Wrapper and Canonical metrics Key (TDD)

- [x] 5.1.1 [TEST] Write RED test `test_metrics_dict_metrics_access` asserting `result["metrics"]` returns metrics dict for both single and ensemble models
- [x] 5.1.2 [TEST] Write RED test `test_metrics_dict_model_metrics_deprecation_warning` asserting `result["model_metrics"]` emits `DeprecationWarning` and returns same value as `result["metrics"]`
- [x] 5.1.3 [IMPL] Add `MetricsDict` subclass of `dict` in `core/steps/training.py` with `__getitem__` that emits warning on `"model_metrics"` access
- [x] 5.1.4 [IMPL] Update `TrainingStep.execute()` to set `result["metrics"]` as canonical key for both single and ensemble modes
- [x] 5.1.5 [IMPL] Wrap final result context in `MetricsDict` before returning from `TrainingStep.execute()`
- [x] 5.1.6 [TEST] Verify Phase 5.1 tests turn GREEN

### 5.2 Regression Test for Pipeline.run() Return Contract

- [x] 5.2.1 [TEST] Write RED test `test_pipeline_run_returns_dict` asserting `isinstance(pipeline.run(), dict)` and `pipeline.run()["metrics"]` works
- [x] 5.2.2 [TEST] Verify Phase 5.2.1 turns GREEN (confirms zero break to existing dict return)

## Phase 6: Core API Layer (api/ Package)

### 6.1 Create api Package Structure

- [x] 6.1.1 Create `src/energizados/api/__init__.py` with public surface re-exports (validate_dict, ValidationResult, Pipeline, RunManager, RunResult, RunMetadata, ProgressEvent, console_progress, format_error, merge_configs, doctor)
- [x] 6.1.2 Create `src/energizados/api/validate.py` with `validate_dict()` function and `ValidationResult` dataclass (ported from `cli/validate.py` but with structured return)
- [x] 6.1.3 Create `src/energizados/api/pipeline.py` that re-exports `core.Pipeline` and documents `from_dict()` availability
- [x] 6.1.4 Create `src/energizados/api/run_state.py` with `RunManager`, `RunResult`, `RunMetadata` dataclasses and `RunResult.from_context()` classmethod
- [x] 6.1.5 Create `src/energizados/api/progress.py` with `ProgressEvent` dataclass and `console_progress()` callback factory
- [x] 6.1.6 Create `src/energizados/api/exceptions.py` with `format_error(exception)` helper
- [x] 6.1.7 Create `src/energizados/api/config.py` with `merge_configs()` and `doctor()` functions (ported from CLI)

### 6.2 API Module Tests (TDD)

- [x] 6.2.1 [TEST] Write RED test `test_validate_dict_valid_config` asserting `validate_dict(config, "etl")` returns `ValidationResult(is_valid=True, errors=[], warnings=[])`
- [x] 6.2.2 [TEST] Write RED test `test_validate_dict_invalid_config` asserting errors populate `ValidationResult.errors` with field/message/location
- [x] 6.2.3 [TEST] Write RED test `test_run_result_from_context` asserting `RunResult.from_context(context)` extracts metrics, run_id, status correctly
- [x] 6.2.4 [TEST] Write RED test `test_progress_event_to_dict` asserting `ProgressEvent(...).to_dict()` returns JSON-serializable dict
- [x] 6.2.5 [IMPL] Implement API modules (6.1.1-6.1.7) with real logic
- [x] 6.2.6 [TEST] Verify Phase 6.2 tests turn GREEN

## Phase 7: CLI Delegation and JSON Output

### 7.1 Add Shared JSON Helper and Update run Command (TDD)

- [x] 7.1.1 [TEST] Write RED test `test_run_json_output` asserting `energizados run --json config.yaml` outputs valid JSON matching `RunResult.to_dict()` structure
- [x] 7.1.2 [IMPL] Add `_output_json(data)` helper in `cli/main.py` that calls `.to_dict()` if available and outputs JSON
- [x] 7.1.3 [IMPL] Add `--json` flag to `cli/run.py` run command, delegating to `api.pipeline.run_pipeline()` or wrapping result in `RunResult.from_context()`
- [x] 7.1.4 [IMPL] Update human-readable output path to skip when `--json` is True
- [x] 7.1.5 [TEST] Verify Phase 7.1 tests turn GREEN

### 7.2 Update validate and doctor Commands (TDD)

- [x] 7.2.1 [TEST] Write RED test `test_validate_json_output` asserting `energizados validate --json config.yaml` outputs JSON matching `ValidationResult.to_dict()`
- [x] 7.2.2 [TEST] Write RED test `test_doctor_json_output` asserting `energizados doctor --json` outputs JSON with system_info and checks
- [x] 7.2.3 [IMPL] Update `cli/validate.py` to delegate to `api.validate_dict()` and add `--json` flag using `_output_json()`
- [x] 7.2.4 [IMPL] Update `cli/doctor.py` to delegate to `api.doctor()` and add `--json` flag using `_output_json()`
- [x] 7.2.5 [TEST] Verify Phase 7.2 tests turn GREEN

## Phase 8: Parity Tests and Regression

### 8.1 CLI-Core API Parity Tests

- [x] 8.1.1 [TEST] Write test `test_run_cli_parity_with_api` asserting `energizados run config.yaml` (CLI) and `Pipeline.from_dict(config).run()` (API) produce equivalent metrics and output paths
- [x] 8.1.2 [TEST] Write test `test_validate_cli_parity_with_api` asserting CLI validate and `api.validate_dict()` report same errors/warnings
- [x] 8.1.3 [TEST] Verify parity tests pass

### 8.2 Full Regression Suite

- [x] 8.2.1 Run `pytest tests/` — all existing tests pass (confirms no breaking changes)
- [x] 8.2.2 Run pre-commit hooks: `isort`, `black`, `bandit`, `flake8` — all pass
- [x] 8.2.3 Manual smoke test: `energizados init test_project && cd test_project && energizados run etl,train` — succeeds
- [x] 8.2.4 Verify pickle compatibility: load existing `.pkl` file from before change, confirms no deserialization errors

## Phase 9: Documentation and Rollout

### 9.1 Update CLAUDE.md Public API Section

- [x] 9.1.1 Add `energizados.api` section to `CLAUDE.md` documenting new service layer
- [x] 9.1.2 Document `validate_dict()`, `Pipeline.from_dict()`, `RunManager` query methods, `ProgressEvent` callback
- [x] 9.1.3 Document `error_code` and `to_dict()` additions to exception hierarchy

### 9.2 CHANGELOG Entry

- [x] 9.2.1 Add `[Unreleased]` section to `CHANGELOG.md`
- [x] 9.2.2 Add **Added** entry for `energizados.api` package with service layer functions
- [x] 9.2.3 Add **Added** entry for `error_code` and `to_dict()` on all `EnergizadosError` subclasses
- [x] 9.2.4 Add **Changed** entry for `ALLOWED_PREFIXES` narrowing with migration note
- [x] 9.2.5 Add **Added** entry for `Pipeline.from_dict()` and `plan()` methods
- [x] 9.2.6 Add **Added** entry for `RunManager` query API and extended metadata
- [x] 9.2.7 Add **Changed** entry for metrics format unification (deprecation warning for `model_metrics`)
- [x] 9.2.8 Add **Added** entry for `--json` flags on run/validate/doctor commands

## Rollback Boundaries

- **Exception hardening**: Revert `error_code` and `to_dict()` additions to `core/exceptions.py`
- **Import safety**: Revert `ALLOWED_PREFIXES` set change and `register_allowed_prefix()` addition
- **Pipeline changes**: Revert `from_dict()` and `plan()` methods from `core/pipeline.py`
- **RunManager**: Revert query methods and metadata extension from `core/builders/run_manager.py`
- **Metrics**: Revert `MetricsDict` wrapper and canonical `metrics` key from `core/steps/training.py`
- **API layer**: Delete `src/energizados/api/` directory entirely (new package, no existing deps)
- **CLI changes**: Revert `--json` flag additions and delegation changes in `cli/` modules
- **Pickle safety**: All changes preserve existing `.pkl` compatibility (no `__module__` changes)

## Dependencies

- **Spec requirement mapping**: Phase 1 satisfies "Exception Machine-Readable Codes"; Phase 2 satisfies "Import Safety with Extension Mechanism"; Phase 3 satisfies "Pipeline Dict Config Support" and "Pipeline Planning API"; Phase 4 satisfies "Run State Query API"; Phase 5 satisfies "Metrics Format Unification"; Phase 6 satisfies "Core API Service Layer"; Phase 7 satisfies "CLI Delegation to Core API" and "CLI JSON Output Mode"
- **Design decision mapping**: Phase 1 implements Decision 6 (exception hardening); Phase 2 implements Decision 7 (import narrowing); Phase 3 implements Decision 2 (Pipeline.from_dict relationship); Phase 4 implements Decision 5 (run-state persistence); Phase 5 implements Decision 9 (metrics unification); Phase 6 implements Decision 1 (API location) and data structures; Phase 7 implements Decision 8 (CLI delegation)
- **Sequential vs parallel**: Phase 1-2 (foundation) MUST be sequential. Phase 3-5 (core extensions) can run in parallel but are grouped in single PR for coherence. Phase 6 (API layer) depends on Phase 3-5. Phase 7 (CLI) depends on Phase 6. Phase 8-9 (verification/docs) run after implementation.
