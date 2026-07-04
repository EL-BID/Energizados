# Specification: framework-web-ready

## Purpose

Enable Energizados to function as a pure Python library with full programmatic API parity to the CLI, adding execution observability and hardening needed for a web service layer. This spec defines the core service API that the CLI delegates to, with structured outputs and no stdout coupling.

## ADDED Requirements

### Requirement: Config Validation API

The system SHALL provide a `validate_dict(config: dict, config_type: str) -> ValidationResult` function that validates configuration without file I/O.

#### Scenario: Validate valid ETL config

- GIVEN a valid ETL configuration dict
- WHEN `validate_dict(config, "etl")` is called
- THEN `ValidationResult(is_valid=True, errors=[], warnings=[])` is returned

#### Scenario: Validate invalid config with structural errors

- GIVEN an invalid configuration dict with missing required fields
- WHEN `validate_dict(config, "train")` is called
- THEN `ValidationResult(is_valid=False, errors=[ConfigError(...)], warnings=[])` is returned
- AND each error includes `field`, `message`, and `location` (path to the offending key)

#### Scenario: Validate config with warnings only

- GIVEN a configuration dict with deprecated but valid fields
- WHEN `validate_dict(config, "train")` is called
- THEN `ValidationResult(is_valid=True, errors=[], warnings=[ConfigWarning(...)])` is returned
- AND each warning includes `field`, `message`, and `deprecation_path` if applicable

#### Scenario: Invalid config_type parameter

- GIVEN a valid configuration dict
- WHEN `validate_dict(config, "unknown_type")` is called
- THEN `ConfigurationError` is raised with `error_code="CONFIG_UNKNOWN_TYPE"`

### Requirement: Pipeline Dict Config Support

The system SHALL accept `config: Union[str, Path, dict]` in `Pipeline.__init__` and provide `Pipeline.from_dict()` classmethod for dict configs.

#### Scenario: Initialize pipeline from dict config

- GIVEN a valid training configuration dict
- WHEN `Pipeline(config=dict_config)` is called
- THEN a `Pipeline` instance is created
- AND the instance config is equivalent to loading the same config from a file

#### Scenario: Initialize pipeline from file path (existing behavior)

- GIVEN a valid training configuration file path
- WHEN `Pipeline(config="/path/to/train.yaml")` is called
- THEN a `Pipeline` instance is created with config loaded from the file
- AND existing behavior is preserved (no breaking changes)

#### Scenario: Pipeline.from_dict classmethod

- GIVEN a valid training configuration dict
- WHEN `Pipeline.from_dict(config, context=None)` is called
- THEN a `Pipeline` instance is created
- AND behavior is equivalent to `Pipeline(config=dict_config)`

#### Scenario: Invalid dict config structure

- GIVEN an invalid configuration dict (missing required top-level keys)
- WHEN `Pipeline.from_dict(config)` is called
- THEN `ConfigurationError` is raised with `error_code="CONFIG_INVALID"`

### Requirement: Pipeline Planning API

The system SHALL provide `Pipeline.plan()` method that returns execution plan without running steps.

#### Scenario: Get execution plan for valid config

- GIVEN a valid training configuration dict
- WHEN `Pipeline.from_dict(config).plan()` is called
- THEN an `ExecutionPlan` object is returned
- AND the plan includes: `steps` (ordered list of step names), `dependencies` (DAG structure), `estimated_duration` (optional)

#### Scenario: Plan reveals dependency cycle

- GIVEN a configuration with circular ETL dependencies
- WHEN `Pipeline.from_dict(config).plan()` is called
- THEN `ETLDependencyError` is raised with `error_code="ETL_DEPENDENCY_CYCLE"`
- AND the error message includes the cycle path

#### Scenario: Plan includes disabled steps filtered out

- GIVEN a configuration where some ETLs have `enabled: false`
- WHEN `Pipeline.from_dict(config).plan()` is called
- THEN the returned plan excludes disabled steps
- AND dependencies are re-calculated accordingly

### Requirement: Structured Pipeline Run Results

The system SHALL provide `Pipeline.run(progress_callback=None) -> RunResult` that returns structured execution results.

#### Scenario: Successful run returns RunResult

- GIVEN a valid training configuration dict
- WHEN `Pipeline.from_dict(config).run()` is called
- THEN a `RunResult` object is returned with: `run_id` (UUID), `status` ("success"|"partial"|"failed"), `metrics` (dict), `start_time`, `end_time`, `output_paths` (dict of step → output file)

#### Scenario: Failed run returns RunResult with error details

- GIVEN a configuration that will fail during ETL execution
- WHEN `Pipeline.from_dict(config).run()` is called
- THEN `RunResult(status="failed", error=EnergizadosError, ...)` is returned
- AND the error includes `error_code` and `to_dict()` representation

#### Scenario: Partial run (some steps failed)

- GIVEN a configuration where one step fails but others succeed
- WHEN `Pipeline.from_dict(config).run()` is called
- THEN `RunResult(status="partial", completed_steps=[...], failed_steps=[...])` is returned
- AND metrics from completed steps are included

### Requirement: Progress Event Streaming

The system SHALL provide `ProgressEvent` dataclass and callback subscription model for execution observability.

#### Scenario: Subscribe to progress events during run

- GIVEN a valid training configuration dict and a callback function
- WHEN `Pipeline.from_dict(config).run(progress_callback=my_callback)` is called
- THEN the callback is invoked multiple times with `ProgressEvent` objects
- AND each event includes: `run_id` (str), `step_name` (str), `phase` ("start"|"progress"|"complete"|"error"), `message` (str), `percent` (Optional[float]), `timestamp` (datetime)

#### Scenario: Progress callback errors do not abort run

- GIVEN a progress callback that raises an exception
- WHEN `Pipeline.run(progress_callback=broken_callback)` is called
- THEN the exception is caught and logged
- AND the pipeline run continues without interruption
- AND subsequent callbacks are still invoked

#### Scenario: Run without progress callback (optional)

- GIVEN a valid training configuration dict
- WHEN `Pipeline.from_dict(config).run(progress_callback=None)` is called
- THEN the pipeline runs successfully
- AND no progress overhead is incurred (no default callback)

### Requirement: Run State Query API

The system SHALL provide `RunManager.get_run(run_id)`, `list_runs(filter=None)`, and `get_latest_run()` methods for querying execution metadata.

#### Scenario: Get specific run by ID

- GIVEN a completed pipeline run with known `run_id`
- WHEN `RunManager.get_run(run_id)` is called
- THEN a `RunMetadata` object is returned with: `run_id`, `config`, `status`, `metrics`, `start_time`, `end_time`, `output_paths`

#### Scenario: Get non-existent run returns None

- GIVEN a `run_id` that does not exist in the metadata store
- WHEN `RunManager.get_run(run_id)` is called
- THEN `None` is returned (not an exception)

#### Scenario: List all runs without filter

- GIVEN multiple pipeline runs have been executed
- WHEN `RunManager.list_runs()` is called
- THEN a list of `RunMetadata` objects is returned
- AND the list is ordered by `start_time` descending (most recent first)

#### Scenario: List runs with filter

- GIVEN multiple pipeline runs with different statuses
- WHEN `RunManager.list_runs(filter={"status": "success"})` is called
- THEN only successful runs are returned
- AND filter supports: `status`, `step_name`, `date_range` (start, end)

#### Scenario: Get latest run

- GIVEN multiple pipeline runs have been executed
- WHEN `RunManager.get_latest_run()` is called
- THEN the most recent run (by `start_time`) is returned
- AND if no runs exist, `None` is returned

### Requirement: Exception Machine-Readable Codes

All `EnergizadosError` subclasses SHALL expose `error_code: str` and `to_dict() -> dict` methods.

#### Scenario: ConfigurationError includes error_code

- GIVEN a `ConfigurationError` is raised
- WHEN `exception.error_code` is accessed
- THEN `"CONFIG_INVALID"` is returned
- AND `exception.to_dict()` returns `{"error_code": "CONFIG_INVALID", "message": str(exception), "details": {...}}`

#### Scenario: ETLError includes error_code

- GIVEN an `ETLError` is raised during ETL execution
- WHEN `exception.error_code` is accessed
- THEN `"ETL_EXECUTION_FAILED"` is returned
- AND `exception.to_dict()` includes the ETL name and phase (extract/transform/load)

#### Scenario: ModelNotFittedError includes error_code

- GIVEN a `ModelNotFittedError` is raised
- WHEN `exception.error_code` is accessed
- THEN `"MODEL_NOT_FITTED"` is returned
- AND `exception.to_dict()` includes the model class name

#### Scenario: EnergizadosError base class default code

- GIVEN an `EnergizadosError` (base class) is raised
- WHEN `exception.error_code` is accessed
- THEN `"ENERGIZADOS_ERROR"` is returned
- AND `exception.to_dict()` returns a valid dict structure

### Requirement: Import Safety with Extension Mechanism

The system SHALL narrow `ALLOWED_PREFIXES` to `{"src."}` and provide `register_allowed_prefix(prefix)` for extensibility.

#### Scenario: Default ALLOWED_PREFIXES is narrowed

- GIVEN the framework is imported fresh
- WHEN `import_utils.ALLOWED_PREFIXES` is inspected
- THEN only `{"src."}` is present (previous `{"data.", "features.", "src."}` is reduced)

#### Scenario: Register custom prefix for project

- GIVEN a project with custom classes under `ml_models.` prefix
- WHEN `register_allowed_prefix("ml_models.")` is called before importing custom classes
- THEN `import_class("ml_models.CustomModel")` succeeds
- AND `"ml_models."` is added to `ALLOWED_PREFIXES`

#### Scenario: Import class without allowed prefix fails safely

- GIVEN an attempt to import a class from `"dangerous."` prefix
- WHEN `import_class("dangerous.EvilClass")` is called
- THEN `ConfigurationError` is raised with `error_code="CONFIG_INVALID_CLASS_PREFIX"`
- AND the error message includes the blocked prefix and allowed prefixes

#### Scenario: Existing projects with old prefixes can extend

- GIVEN an existing project using classes from `"data."` or `"features."` prefixes
- WHEN the project calls `register_allowed_prefix("data.")` and `register_allowed_prefix("features.")` before framework usage
- THEN all existing custom classes continue to work
- AND no breaking changes occur for projects that opt-in to extension

### Requirement: CLI Delegation to Core API

All CLI commands SHALL become thin clients over the core API, preserving existing CLI behavior while enabling programmatic usage.

#### Scenario: CLI run command delegates to Pipeline

- GIVEN the `energizados run` command is executed
- WHEN the command handler runs
- THEN it calls `Pipeline.from_dict(config).run(progress_callback=console_progress)`
- AND CLI flags and output remain unchanged (behavior parity)

#### Scenario: CLI validate command delegates to validate_dict

- GIVEN the `energizados validate` command is executed
- WHEN the command handler runs
- THEN it calls `validate_dict(config, config_type)`
- AND validation errors/warnings are printed to stdout in the same format as before

#### Scenario: CLI doctor command exposed as API

- GIVEN the `energizados doctor` command is executed
- WHEN the command handler runs
- THEN it calls a new `api.doctor()` function
- AND `api.doctor()` returns structured health check results (not just prints to stdout)

#### Scenario: CLI init command remains primarily CLI

- GIVEN the `energizados init` command is executed
- WHEN the command handler runs
- THEN it calls the existing project scaffolding logic
- AND the underlying generator function is extractable so it CAN be called programmatically (but not via `api.create_project()` — filesystem scaffolding is a tooling concern)

#### Scenario: CLI merge_configs helper exposed as API

- GIVEN the framework needs to merge multiple config dicts internally
- WHEN `api.merge_configs(configs)` is called
- THEN it returns the merged dict following "last wins" semantics
- AND this helper is available for programmatic use

### Requirement: CLI JSON Output Mode

The system SHALL provide `--json` flag for structured output in all CLI commands.

#### Scenario: JSON output for run command

- GIVEN the `energizados run --json /path/to/config.yaml` command is executed
- WHEN the pipeline completes
- THEN the CLI outputs `RunResult.to_dict()` as JSON to stdout
- AND human-readable output is suppressed

#### Scenario: JSON output for validate command

- GIVEN the `energizados validate --json /path/to/config.yaml` command is executed
- WHEN validation completes
- THEN the CLI outputs `ValidationResult.to_dict()` as JSON to stdout
- AND the JSON includes `is_valid`, `errors`, `warnings` keys

#### Scenario: JSON output for doctor command

- GIVEN the `energizados doctor --json` command is executed
- WHEN health checks complete
- THEN the CLI outputs structured health results as JSON
- AND the JSON includes check name, status, and details for each check

### Requirement: CLI-Core API Parity

For any configuration, CLI execution and core API execution SHALL produce equivalent results.

#### Scenario: Run command parity

- GIVEN a valid training configuration file
- WHEN `energizados run config.yaml` is executed via CLI
- AND `Pipeline.from_dict(config).run()` is called programmatically
- THEN both produce equivalent `RunResult` objects (same run_id, metrics, output paths)
- AND the only difference is output format (human-readable vs structured)

#### Scenario: Validate command parity

- GIVEN a configuration file with errors
- WHEN `energizados validate config.yaml` is executed via CLI
- AND `validate_dict(config, "train")` is called programmatically
- THEN both report the same validation errors and warnings
- AND the `ValidationResult` from the API matches what the CLI prints

#### Scenario: EDA command parity

- GIVEN a valid EDA configuration
- WHEN `energizados run eda --config config.yaml` is executed via CLI
- AND the equivalent core API call is made
- THEN both produce the same HTML report and analysis results

## MODIFIED Requirements

### Requirement: Metrics Format Unification

The system SHALL use `result["metrics"]` as the canonical key for both single-model and ensemble results, with deprecation support for `result["model_metrics"]`.

#### Scenario: Single model returns metrics key

- GIVEN a single-model training run completes successfully
- WHEN `RunResult.metrics` is accessed
- THEN it contains the model's performance metrics (AUC, precision, recall, etc.)
- AND `result["metrics"]` is the primary key

#### Scenario: Ensemble returns metrics key (unified)

- GIVEN an ensemble training run completes successfully
- WHEN `RunResult.metrics` is accessed
- THEN it contains the ensemble's performance metrics (not `model_metrics`)
- AND `result["metrics"]` is the canonical key for both single and ensemble

#### Scenario: Legacy model_metrics key still works with deprecation warning

- GIVEN an ensemble training run completes successfully
- WHEN `result["model_metrics"]` is accessed
- THEN a `DeprecationWarning` is emitted: "'model_metrics' is deprecated; use 'metrics' instead"
- AND the value is returned (for backward compatibility)

#### Scenario: Code reads metrics key only

- GIVEN existing code reads only `result["metrics"]`
- WHEN the code runs with either single-model or ensemble results
- THEN it works correctly in both cases without changes

## REMOVED Requirements

None — all changes are additive or backward-compatible modifications.

## RENAMED Requirements

None — no requirements are renamed, only modified behavior is specified.

## Suspect Item Decisions

### doctor Command → Core API Exposed

**Decision**: Expose as `api.doctor()` (core API).  
**Rationale**: Health checks are valuable for services to pre-flight environment validation before accepting work. Cheap to expose, high library value.  
**Migration**: CLI doctor command becomes thin client over `api.doctor()`.

### init/create-project → Primarily CLI, Generator Extractable

**Decision**: Keep primarily CLI, but extract underlying generator function so it CAN be called programmatically.  
**Rationale**: Filesystem scaffolding is fundamentally a tooling concern, not a library API. Projects typically scaffold once via CLI. However, extracting the generator enables programmatic use without committing to a public `api.create_project()` surface.  
**Migration**: No migration needed — `api.create_project()` is NOT added as a public API. The generator function is internal-only.

### merge_configs → Core API Exposed

**Decision**: Expose as `api.merge_configs(configs)`.  
**Rationale**: Config merging is a generic operation useful for programmatic pipeline construction. Cheap to expose, enables dynamic config assembly.  
**Migration**: Internal refactoring to move logic to `api/merge_configs.py` with CLI as thin client.

## Implementation Notes

- **Exception error codes**: Each `EnergizadosError` subclass requires a stable, documented `error_code`. Codes SHALL use UPPER_SNAKE_CASE and be scoped to the error domain (e.g., `CONFIG_*`, `ETL_*`, `MODEL_*`).
- **ProgressEvent overhead**: Callback-based design is optional — only invoked when a consumer subscribes. No default overhead when `progress_callback=None`.
- **Import safety**: Projects that need the old broad prefixes (`data.`, `features.`) must call `register_allowed_prefix()` before framework usage. This is an opt-in migration path.
- **CLI behavior preservation**: All CLI commands must pass behavior-preservation tests comparing old CLI output to new delegated CLI output.
- **Metrics format**: The deprecation warning for `model_metrics` should be implemented using `warnings.warn()` with category `DeprecationWarning`.
