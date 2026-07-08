# Delta for web-console

## ADDED Requirements

### Requirement: Plan Preview Endpoint

The system MUST expose `POST /plan` endpoint to receive YAML/JSON config, validate schema via `validate_dict()`, check custom_class prefixes via `_check_custom_class_prefixes()`, and return `ExecutionPlan` via `Pipeline.plan()`. The endpoint MUST validate the config structure and dependencies before returning the plan.

#### Scenario: successful plan preview

- GIVEN a valid ETL config with multiple steps and dependencies
- WHEN `POST /plan` is called with the config body
- THEN an `ExecutionPlan` is returned with steps in execution order and dependency graph

#### Scenario: config with custom classes passes security check

- GIVEN an ETL config with `custom_class: "energizados.etl.pipeline.SourceETL"`
- WHEN `POST /plan` is called
- THEN the plan is returned successfully without error

#### Scenario: invalid schema returns structured error

- GIVEN a config with invalid YAML syntax or missing required fields
- WHEN `POST /plan` is called
- THEN a 400 status code is returned with validation error details

### Requirement: HTMX Content Negotiation

The system MUST support content negotiation on `POST /plan`. If the `HX-Request` header is present, the system MUST return an HTML fragment from `components/plan_preview.html`. Otherwise, the system MUST return JSON response.

#### Scenario: HTMX request returns HTML fragment

- GIVEN a valid ETL config
- WHEN `POST /plan` is called with `HX-Request: true` header
- THEN an HTML fragment is returned rendering the plan inline

#### Scenario: JSON request returns JSON response

- GIVEN a valid ETL config
- WHEN `POST /plan` is called without `HX-Request` header
- THEN a JSON response is returned with `ExecutionPlan` structure

### Requirement: Unsupported Config Type Handling

The system MUST return HTTP 200 with `{"available": false, "message": "Plan preview available for ETL configs only"}` when config has no `etl:` section or config_type != `etl`. This MUST NOT be treated as an error (no 400 status code).

#### Scenario: train config returns unavailable message

- GIVEN a training config (`train.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

#### Scenario: eda config returns unavailable message

- GIVEN an EDA config (`eda.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

#### Scenario: infer config returns unavailable message

- GIVEN an inference config (`infer.yaml`) with no `etl:` section
- WHEN `POST /plan` is called
- THEN HTTP 200 is returned with `available: false` and informative message

### Requirement: Circular Dependency Error Handling

The system MUST catch `ETLDependencyError` exceptions (indicating circular dependencies in the ETL DAG) and return HTTP 400 with structured error message via `format_error()`. The error MUST clearly indicate the cycle detected.

#### Scenario: circular dependency returns 400

- GIVEN an ETL config with circular dependencies (e.g., A depends on B, B depends on A)
- WHEN `POST /plan` is called
- THEN HTTP 400 is returned with structured error showing the cycle

#### Scenario: self-dependency returns 400

- GIVEN an ETL config where an ETL depends on itself
- WHEN `POST /plan` is called
- THEN HTTP 400 is returned with structured error indicating the self-dependency

### Requirement: Plan Preview UI Integration

The system MUST include a "Preview Plan" button in `templates/components/editor.html`. The button MUST submit to `/plan` with `hx-post="/plan"` and `hx-target="#validation-output"` to display the plan inline in the validation zone.

#### Scenario: preview plan button triggers HTMX request

- GIVEN a user viewing the YAML editor with a valid ETL config
- WHEN the "Preview Plan" button is clicked
- THEN an HTMX POST request is sent to `/plan` targeting `#validation-output`

#### Scenario: plan renders inline in validation zone

- GIVEN a user clicks "Preview Plan" with a valid ETL config
- WHEN the HTML fragment response is received
- THEN the execution plan is displayed inline in the `#validation-output` zone

#### Scenario: unsupported config shows message inline

- GIVEN a user clicks "Preview Plan" with a training config (no `etl:` section)
- WHEN the HTML fragment response is received
- THEN the "not available for this config type" message is displayed inline

#### Scenario: circular dependency error shows inline

- GIVEN a user clicks "Preview Plan" with an ETL config containing circular dependencies
- WHEN the error response is received
- THEN the structured error message is displayed inline in the validation zone
