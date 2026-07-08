# execution-plan-preview Specification

## Purpose

Provide dry-run execution plan capability via `Pipeline.plan()` showing steps and dependencies for ETL configs. Enables operators to validate dependency ordering and detect circular references before enqueuing jobs.

## Requirements

### Requirement: Execution Plan Structure

The system MUST provide `ExecutionPlan` data structure containing ordered steps list and dependencies mapping. The plan MUST be computed declaratively without loading data.

#### Scenario: plan shows execution order

- GIVEN an ETL config with dependencies: A depends on nothing, B depends on A, C depends on B
- WHEN `Pipeline.plan()` is called
- THEN the plan returns steps in order [A, B, C] respecting dependencies

#### Scenario: plan exposes dependency graph

- GIVEN an ETL config with multiple ETLs and dependencies
- WHEN `Pipeline.plan()` is called
- THEN the plan includes a dependency mapping {etl_name: [list_of_dependencies]}

#### Scenario: plan computation is declarative

- GIVEN an ETL config referencing large datasets
- WHEN `Pipeline.plan()` is called
- THEN the plan is computed without reading or loading the referenced data files

### Requirement: ETL-Only Scope

The system MUST restrict plan preview to ETL configs only. Configs without `etl:` section MUST NOT attempt plan computation. Non-ETL configs MUST return "not available" message without error.

#### Scenario: train config does not compute plan

- GIVEN a training config with `train:` section but no `etl:` section
- WHEN plan preview is requested
- THEN no plan computation is attempted and "not available" message is returned

#### Scenario: eda config does not compute plan

- GIVEN an EDA config with `eda:` section but no `etl:` section
- WHEN plan preview is requested
- THEN no plan computation is attempted and "not available" message is returned

#### Scenario: infer config does not compute plan

- GIVEN an inference config with `infer:` section but no `etl:` section
- WHEN plan preview is requested
- THEN no plan computation is attempted and "not available" message is returned

### Requirement: Circular Dependency Detection

The system MUST detect circular dependencies in the ETL DAG and raise `ETLDependencyError`. The error MUST identify the cycle detected to guide resolution.

#### Scenario: direct cycle detected

- GIVEN an ETL config where etl_a depends on etl_b and etl_b depends on etl_a
- WHEN `Pipeline.plan()` is called
- THEN `ETLDependencyError` is raised with cycle information

#### Scenario: indirect cycle detected

- GIVEN an ETL config where A→B→C→A forms a cycle through multiple steps
- WHEN `Pipeline.plan()` is called
- THEN `ETLDependencyError` is raised with the full cycle path

#### Scenario: self-dependency detected

- GIVEN an ETL config where an ETL lists itself in `depends_on:`
- WHEN `Pipeline.plan()` is called
- THEN `ETLDependencyError` is raised indicating self-dependency

### Requirement: No Duration Estimation

The system MUST NOT include execution time estimates in `ExecutionPlan`. The `estimated_duration` field MUST be `None` or omitted. Duration calculation is out of scope for this phase.

#### Scenario: plan excludes duration

- GIVEN any valid ETL config
- WHEN `Pipeline.plan()` is called
- THEN the returned `ExecutionPlan.estimated_duration` is `None` or absent

### Requirement: No Plan Caching

The system MUST re-validate and re-compute the plan on every `/plan` request. No caching mechanism is implemented in this phase.

#### Scenario: each request recomputes plan

- GIVEN the same ETL config submitted twice
- WHEN `POST /plan` is called for each submission
- THEN both calls trigger full validation and plan recomputation
