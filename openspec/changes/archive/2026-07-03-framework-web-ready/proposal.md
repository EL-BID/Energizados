# Proposal: framework-web-ready

## Intent

Enable Energizados to function as a **pure Python library** with full programmatic API parity to the CLI, and add the execution observability and hardening needed for a web service layer. The framework currently exposes critical functionality only via CLI subprocess invocation — validation, dry-run, run-state queries, and progress events are all CLI-only or print-based. This change introduces a **core service API** that the CLI delegates to, with structured outputs and no stdout coupling.

## Scope

### In Scope

**Library/CLI parity (confirmed gaps):**
- Core API `validate_dict(config: dict) -> ValidationResult` — currently CLI-only in `cli/validate.py`
- `Pipeline.__init__` / `ConfigPipelineBuilder` accept `config: dict` as primary input — currently require file path only
- Dry-run as programmatic API: `Pipeline.validate_only()` or `Pipeline.plan()` — currently CLI-only `--dry-run` flag
- Structured return values from run operations (validate, run, metrics) — currently print to stdout

**Execution observability (confirmed gaps):**
- Run-state persistence/query: `RunManager.get_run(run_id)`, `list_runs()`, `get_latest_run()` — currently writes metadata but exposes no query API
- `ProgressEvent` stream for cancellation/timeout support — currently coupled to Rich console with no structured event surface
- `Pipeline.run()` execution metadata returned as structured object — currently blocking with no progress hooks

**Hardening (confirmed gaps):**
- Exception `error_code` + `to_dict()` for web responses — currently defined in `core/exceptions.py` but missing machine-readable codes
- Import allowlist narrowing + documented extension mechanism — `core/utils/import_utils.py` `ALLOWED_PREFIXES` too broad (`data.`, `features.`, `src.`)

### Out of Scope

**Web service/UI (explicitly non-goal):**
- The web service layer, API endpoints, authentication, and UI implementation are a **separate future change**
- This change only prepares the framework as a library that a service could wrap

**Async/concurrency (likely out of scope):**
- Full async runtime, task cancellation primitives, or checkpoint/restart
- Mark as non-goal unless trivially achievable within API surface changes

**Storage backends (out of scope):**
- S3 or other remote storage for models/data
- Focus on local file operations only (existing behavior)

**Suspect items (need triage in spec/design):**
- `doctor` command (CLI-only or core API?)
- `init`/`create-project` (CLI-only or core API?)
- `merge_configs` helper (CLI-only or core API?)
- Metrics format inconsistency (single model `result["metrics"]` vs ensemble `result["model_metrics"]`)

**Explicitly deferred:**
- Full web-server scaffolding (FastAPI, Flask, etc.)
- Authentication/authorization
- Multi-tenancy or isolation features

## Capabilities

### New Capabilities

- **`api.validate`**: `validate_dict(config: dict) -> ValidationResult` with structured errors/warnings
- **`api.from_dict`**: `Pipeline.from_dict(config: dict, context: Optional[PipelineContext])` or `ConfigPipelineBuilder.from_dict()`
- **`api.dry_run`**: `Pipeline.plan()` returns execution plan without running steps
- **`api.run_state`**: `RunManager` query API: `get_run(run_id)`, `list_runs(filter)`, `get_latest_run()`
- **`api.progress`**: `ProgressEvent` dataclass (step, phase, message, percent) + subscription callback or async generator
- **`api.exceptions`**: All `EnergizadosError` subclasses expose `error_code: str` and `to_dict() -> dict`
- **`api.import_safety`**: Documented `ALLOWED_PREFIXES` + extension mechanism (whitelist entry function)

### Modified Capabilities

- **`Pipeline`**: Constructor accepts `config: dict | str | Path` (union type); `run()` returns structured `RunResult` with metrics
- **`ConfigPipelineBuilder`**: `from_dict()` classmethod; builds `Pipeline` from dict config
- **`RunManager`**: Exposes query methods; persists state with run-id indexing
- **CLI commands**: Become thin clients over core API (e.g. `energizados run` calls `Pipeline.from_dict().run()`)
- **`import_utils.ALLOWED_PREFIXES`**: Narrowed to `src.`, documented extension function

## Approach

### Phase 1: Core API Service Layer (`energizados.api` or `energizados.core.api`)

**New module structure:**
```
src/energizados/
├── api/
│   ├── __init__.py          # Public API surface
│   ├── validate.py           # validate_dict(config) -> ValidationResult
│   ├── pipeline.py           # from_dict(), plan(), dry_run
│   ├── run_state.py          # RunManager query API
│   ├── progress.py           # ProgressEvent dataclass, subscription
│   └── exceptions.py         # error_code, to_dict() extensions (or move to core/exceptions.py)
└── core/
    └── utils/
        └── import_utils.py   # ALLOWED_PREFIXES + documented extension
```

**API signatures (sketch):**
```python
# api/validate.py
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ConfigError]
    warnings: List[ConfigWarning]

def validate_dict(config: dict, config_type: str) -> ValidationResult:
    """Validate a config dict without file I/O."""
    ...

# api/pipeline.py
class Pipeline:
    def __init__(self, config: Union[str, Path, dict], context: Optional[PipelineContext] = None):
        """Accept file path (existing) OR dict (new)."""
        if isinstance(config, (str, Path)):
            config = load_yaml(config)
        self.config = config
        ...

    @classmethod
    def from_dict(cls, config: dict, context: Optional[PipelineContext] = None) -> "Pipeline":
        """Factory for dict configs (equiv to __init__ with dict)."""
        ...

    def plan(self) -> ExecutionPlan:
        """Return execution plan without running (dry-run as API)."""
        ...

    def run(self, progress_callback: Optional[Callable[[ProgressEvent], None]] = None) -> RunResult:
        """Execute pipeline; return structured result. Optional progress callback."""
        ...

# api/run_state.py
class RunManager:
    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        ...

    def list_runs(self, filter: Optional[RunFilter] = None) -> List[RunMetadata]:
        ...

    def get_latest_run(self) -> Optional[RunMetadata]:
        ...

# api/progress.py
@dataclass
class ProgressEvent:
    run_id: str
    step_name: str
    phase: str  # "start", "progress", "complete", "error"
    message: str
    percent: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

# api/exceptions.py (or core/exceptions.py extension)
class EnergizadosError(Exception):
    error_code: str  # e.g. "CONFIG_INVALID", "ETL_DEPENDENCY_CYCLE"
    def to_dict(self) -> dict: ...
```

### Phase 2: CLI Delegation

**CLI becomes thin client:**
```python
# cli/run.py (simplified)
def run(config_path: str, ...):
    config = load_yaml(config_path)
    pipeline = Pipeline.from_dict(config)
    result = pipeline.run(progress_callback=console_progress)

    # Structured output (optional JSON)
    if output_json:
        click.echo(json.dumps(result.to_dict()))
    else:
        click.echo(f"Run completed: {result.run_id}")
```

### Phase 3: Exception Hardening

**Add to all exception classes:**
```python
# core/exceptions.py
class EnergizadosError(Exception):
    error_code: str = "ENERGIZADOS_ERROR"

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.details = details

    def to_dict(self) -> dict:
        return {"error_code": self.error_code, "message": str(self), "details": self.details}

class ConfigurationError(EnergizadosError):
    error_code = "CONFIG_INVALID"
    ...

# And so on for all subclasses
```

### Phase 4: Import Safety

**Narrow `ALLOWED_PREFIXES` + documented extension:**
```python
# core/utils/import_utils.py
ALLOWED_PREFIXES = {
    "src.",  # Generated project src/ directory
    # REMOVED: "data.", "features.", "src." was too broad
}

def register_allowed_prefix(prefix: str) -> None:
    """Register a custom allowed prefix (extensibility)."""
    ALLOWED_PREFIXES.add(prefix)

def import_class(class_path: str) -> type:
    """Import a class from a string path with safety checks."""
    # Validate prefix, check not __import__, etc.
    ...
```

### Phase 5: Suspect Item Triage

**Decide in spec/design:**
- Should `doctor` be a library API or remain CLI-only?
- Should `init`/`create-project` be callable from Python or remain CLI?
- Should `merge_configs` be exposed as `api.merge_configs()`?
- Unify metrics format: `result["metrics"]` for all models (single or ensemble)

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/api/` | New | Core service API layer (validate, pipeline, run_state, progress) |
| `src/energizados/core/exceptions.py` | Modified | Add `error_code` and `to_dict()` to all exception classes |
| `src/energizados/core/utils/import_utils.py` | Modified | Narrow `ALLOWED_PREFIXES`, add `register_allowed_prefix()` |
| `src/energizados/core/pipeline.py` | Modified | Accept `config: dict`, add `plan()` method, return `RunResult` |
| `src/energizados/core/builders/run_manager.py` | Modified | Add query methods (`get_run`, `list_runs`, `get_latest_run`) |
| `src/energizados/cli/` | Modified | All commands delegate to core API (thin clients) |
| `tests/` | Modified | Add tests for core API, exception codes, import safety |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Breaking frozen public API** | Low | Proposal is ADDITIVE only. No changes to 8 base classes in `contracts`. New API is separate module. |
| **CLI behavior change from delegation** | Low | CLI commands keep same flags/outputs; delegation preserves existing behavior. Add behavior-preservation tests. |
| **Pickle break from class moves** | None | No class moves to `api/`. All existing classes keep `__module__`. Old `.pkl` files load unchanged. |
| **Metrics format unification breaks consumers** | Medium | Decision needed in spec: unify to `result["metrics"]` with deprecation path for `result["model_metrics"]`. Add version marker. |
| **`ALLOWED_PREFIXES` narrowing breaks custom classes** | Medium | Document extension mechanism; add migration guide. Keep `src.` allowed. |
| **ProgressEvent overhead** | Low | Callback-based design is optional; only invoked when consumer subscribes. No default overhead. |
| **Run-state persistence format change** | Low | Extend existing metadata format; add query layer only. No migration needed for old runs. |
| **Parity testing burden** | High | Every CLI command needs coverage via core API. Prioritize high-value commands (run, validate, eda). Document parity gaps. |

## Rollback Plan

**Pure revert + deprecation warnings:**
- All new `api/` module can be deleted without affecting existing code (it's a new import path)
- CLI delegation can be reverted to old implementation (git history preserves pre-delegation code)
- Exception additions (`error_code`, `to_dict()`) are backward-compatible (new attributes don't break existing `except` clauses)
- `ALLOWED_PREFIXES` narrowing may require re-adding `data.`/`features.` if custom projects break — document in release notes

## Dependencies

**Soft-depends on prior changes:**
- Change #1 (exception-hierarchy): DONE — provides `EnergizadosError` base for `error_code` extension
- Change #2 (contracts-consolidation): DONE — frozen public API surface
- Change #3 (core-layering): DONE — clean `core` foundation
- Change #4 (unified-registry): DONE — registry pattern for potential use in `api`

**No external dependencies:** New API uses only existing stdlib and project dependencies.

## Success Criteria

**API surface:**
- [ ] `energizados.api` module exists and is importable
- [ ] `validate_dict()` accepts dict and returns `ValidationResult`
- [ ] `Pipeline.from_dict()` builds pipeline from dict config
- [ ] `Pipeline.plan()` returns execution plan without running
- [ ] `Pipeline.run(progress_callback=...)` executes and returns `RunResult`
- [ ] `RunManager.get_run()`, `list_runs()`, `get_latest_run()` return metadata
- [ ] All `EnergizadosError` subclasses have `error_code` and `to_dict()`
- [ ] `import_utils.register_allowed_prefix()` allows custom prefixes

**CLI delegation:**
- [ ] All CLI commands (run, validate, eda, doctor, init) delegate to core API
- [ ] CLI behavior unchanged (same flags, same output for normal mode)
- [ ] JSON output mode available for structured consumption

**Testing:**
- [ ] `pytest tests/` green (all existing tests pass)
- [ ] New tests for core API (validate_dict, from_dict, plan, run_state)
- [ ] New tests for exception `error_code` and `to_dict()`
- [ ] New tests for import safety (ALLOWED_PREFIXES, register_allowed_prefix)
- [ ] Parity tests: CLI output matches core API output for same config

**Non-goals verified:**
- [ ] No web server scaffolding (FastAPI, Flask) added
- [ ] No async runtime primitives (unless trivially achievable)
- [ ] No S3 or remote storage support

**Budget:**
- [ ] Diff within 400-line budget per phase (may split into multiple PRs)

## Open Questions

**Suspect items triage:**
1. Should `doctor` command be exposed as `api.doctor()` or remain CLI-only?
2. Should `init`/`create-project` be callable from Python or remain CLI-only?
3. Should `merge_configs` be exposed as `api.merge_configs()`?
4. How to unify metrics format (`result["metrics"]` vs `result["model_metrics"]`) with deprecation path?

**API design decisions:**
1. Core API module name: `energizados.api` or `energizados.core.api`?
2. `ProgressEvent` subscription model: callback vs async generator vs queue?
3. `RunResult` serialization format: JSON-compatible dict or dataclass?
4. Run-state storage format: JSON file, SQLite, or keep existing ad-hoc files?

## Next Recommended

`spec` — elaborate API signatures, define `ValidationResult`/`RunResult`/`ProgressEvent` structures, specify CLI delegation approach, and triage suspect items with decision rationale.
