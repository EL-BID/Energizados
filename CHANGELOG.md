# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Web: multi-project workspace foundation (v0.4 Phase 1)** — Project model with a registry bookmark (`data/web/projects.json`, re-validated against disk on every access); jobs and runs are now project-scoped (each belongs to exactly one project) and the worker `chdir`s into the project directory. The pre-multi-project Global scope is deprecated and surfaces read-only.
- **Web: config templates + project-aware YAML editor (v0.4 Phase 2)** — Per-project config authoring with templates and an editor scoped to the active project.
- **Web: retrain + inference UX (v0.4 Phase 3)** — Retrain-from-run and inference flows wired into the console.
- **Web: per-project dashboard + projects home (v0.4 Phase 4)** — Per-project dashboard wiring, projects-home stats, and a root redirect to the projects home.
- **Web: UI redesign — design system + app shell (Foundation)** — A token-driven design system (`--app-*` CSS custom properties; primary `#6366f1`; Inter + monospace) layered over Bootstrap 5.3, a persisted light/dark theme toggle with anti-flash, and an app shell with a Projects sidebar. Legacy Global routes are moved to a muted footer.
- **Web: UI redesign — project_detail showcase (Hero)** — `project_detail` redesigned into an at-a-glance page: Jobs/Runs grouped by run type (etl / eda / inference / training), a latest-training metric summary, and a lineage placeholder.
- **Web: UI redesign — system rollout + async states** — The design system applied across all remaining page templates (dark-safe, token-driven: `.app-card` panels, compact tables, status-badge consistency), plus async UX: HTMX-native loading indicators on action buttons, an out-of-band job-list refresh on job creation, and empty-state coverage.
- **Web: `/ui` style guide** — A living, self-documenting style-guide page demonstrating the tokens and components; swatches auto-adapt to the active theme (zero hardcoded colors).

### Fixed

- **Web: `/jobs` direct navigation** — `GET /jobs` returned a bare HTMX fragment (no shell, no dark mode) on direct navigation; now content-negotiated to render a full themed page (`jobs.html`) on direct nav while the 2s auto-refresh poll still receives the fragment.

### Documentation

- **Web: domain model** — Framework-core and web-console bounded contexts documented as ubiquitous-language glossaries (`src/energizados/CONTEXT.md`, `src/energizados/web/CONTEXT.md`) bound by a repo `CONTEXT-MAP.md`, plus three web-console ADRs (generalized run, deprecating the Global scope, run-level lineage).

## [0.3.0] - 2026-07-10

### Added

- **API: ConfigPipelineBuilder re-export** — `ConfigPipelineBuilder` is now re-exported from `energizados.api` for public API consumption, enabling worker processes to import from the public surface instead of internals.
- **API: RunManager EDA report metadata** — `RunManager._write_run_metadata` now populates `output_paths["eda_report"]` when `context["eda_results"]["report_path"]` is available, providing generic artifact path support.
- **Web: async job runner + web console (Phase 1)** — Complete async job execution system with FastAPI web interface, SQLite-backed job queue, HTMX-powered UI, and a separate worker process for pipeline execution (`Pipeline.run()` blocks for hours, so it runs out-of-process). Includes job submission, monitoring, cancellation, retry, and state management. Entry points: `energizados-web` (server) and `energizados-web-worker` (worker).
- **Web: HTMX content negotiation** — Web API supports both JSON and HTML responses based on `HX-Request` header, enabling seamless HTMX form validation feedback while maintaining programmatic JSON API compatibility.
- **Web: security validation** — Two-layer `custom_class` prefix validation (web submit check + worker import guard) prevents arbitrary code execution. Allowed prefixes: `energizados.*`, `src.*`.
- **Web: job lifecycle management** — FIFO queue with `concurrency=1`, legal state transitions (`QUEUED`→`RUNNING`→`SUCCESS|FAILED|ABORTED`), cancel/retry operations, and worker restart reconciliation.
- **Web: cross-platform deployment** — Docker Compose setup plus a launcher entry point (`energizados-web`) for running server and worker together on local/multi-platform environments.
- **Web: integration tests** — End-to-end tests covering submit→run→terminal flows, cancel semantics, retry links, worker reconciliation, and invalid config rejection.
- **Web: documentation** — Deployment guide with systemd/Docker/supervisor configs, security considerations, air-gapped setup instructions, and troubleshooting guide.
- **Web: Phase 2 runs browsing** — `GET /runs` paginated list (optional `status` filter and `limit`, default 100) and `GET /runs/{run_id}` detail view rendering metadata, single/multi-model metrics, plots gallery, EDA report iframe, config files, and a tailed `run.log`. Both routes return HTML or JSON via the `Accept` header.
- **Web: secure artifact serving** — `GET /runs/{run_id}/artifacts/{path}` serves run files with a multi-layer path-traversal guard (run_id validation, `..`/absolute/backslash rejection, resolved-path containment check against the run directory, no directory listings).
- **Web: job → run navigation** — The job detail view links to the corresponding run detail page when `job.run_id` is populated, closing the loop between async jobs and historical run inspection.
- **Web: Phase 3 execution plan preview** — `POST /plan` dry-run endpoint renders the ETL DAG (and validates config) before enqueuing a job, so operators can preview what will run without executing. Backed by `Pipeline.plan()`.
- **Web: Phase 4 metrics dashboard** — Three new views: a **timeline dashboard** (`/dashboard`, AUC/F1 evolution across the last N runs, `RunMetadata`-only), a **comparison view** (`/runs/compare`, server-rendered side-by-side table for up to 10 runs), and **threshold exploration** (`/api/runs/{run_id}/thresholds` + a Plotly precision/recall section on run detail).
- **Web: Phase 5 live progress (SSE)** — `GET /jobs/{job_id}/progress` streams `ProgressEvent`s as Server-Sent Events with native reconnect and `Last-Event-ID` resume. The worker persists events to a `job_events` table (SQLite), and the job-detail UI uses an `EventSource` block for non-terminal jobs — replacing 2-second HTMX polling with a real-time step timeline.

### Security

- **Dependencies: poetry.lock bumps** — Updated vulnerable dev/notebook transitive dependencies out of their vulnerable ranges (clears 21 Dependabot alerts; runtime framework dependencies are unaffected since CI installs via pip from `pyproject.toml`): mistune 3.2.0→3.3.3, tornado 6.5.5→6.5.7, bleach 6.3.0→6.4.0, jupyterlab 4.5.6→4.6.1, urllib3 2.6.3→2.7.0, idna 3.11→3.18, cryptography 46.0.5→49.0.0, jupyter-server 2.17.0→2.20.0, pymdown-extensions 10.21→11.0.1.

### Documentation

- **Field pilot design guide** — Controlled-field protocol to validate the fraud-detection model before full deployment, measuring incremental lift of the model vs the company's current (BAU) inspection criteria. Canonical design: 200 model-prioritized vs 200 BAU-prioritized inspections, with a random arm as optional gold-standard third arm.

### Notes

- **`result["model_metrics"]` deprecation** — The legacy `model_metrics` result-dict key is still present (emits a `DeprecationWarning`); the earlier note that it "will be removed in v0.3.0" is revised — removal is deferred. Use `result["metrics"]` (canonical).

## [0.2.9] - 2026-07-05

### Added

- **API: service layer package** — `energizados.api` provides programmatic framework usage with structured return values and no stdout coupling. Includes `validate_dict()`, `Pipeline.from_dict()`, `Pipeline.plan()`, `RunManager`, `RunResult.from_context()`, `ProgressEvent`, `console_progress()`, `merge_configs()`, `doctor()`, `format_error()`, and `register_allowed_prefix()`.
- **API: exception error codes** — All framework exceptions now include structured `error_code` attributes for programmatic error handling.
- **API: RunManager query interface** — Programmatic access to run metadata including `list_runs()`, `get_run()`, and `get_latest_run()`.
- **API: ProgressEvent streaming** — Event-based progress reporting for long-running operations with `console_progress()` helper.
- **API: Pipeline.from_dict() and plan()** — Create pipelines from dict configs and get execution plans without running.
- **API: doctor() function** — System health checks with optional package checks and `DoctorReport.to_dict()` serialization.
- **CLI: --json flags** — All CLI commands (`validate`, `doctor`, `run`) support `--json` output for structured machine-readable results.
- **Import safety: register_allowed_prefix()** — Extension function for projects with custom module prefixes beyond the secure defaults.

### Changed

- **Import safety: ALLOWED_PREFIXES narrowed** — Default allowlist now contains only `{"energizados.", "src."}` for security. Projects using custom prefixes (e.g., `data.`, `features.`) must call `register_allowed_prefix()` before framework usage.
- **Metrics: unified result key** — Pipeline run results now expose `result["metrics"]` as the canonical key for both single-model and ensemble runs. Accessing the legacy `result["model_metrics"]` key still works but emits a `DeprecationWarning`; it will be removed in v0.3.0. (This deprecates the result-dict key, not a module.)
- **Test infrastructure: tests. prefix registration** — Test fixtures now dynamically register `tests.` prefix via `conftest.py` to support test-time class imports while keeping production defaults narrow.
- **Tests: slow tests deselected by default** — A plain `pytest` run now omits `@pytest.mark.slow` tests via `addopts -m "not slow"` in `pyproject.toml`. Run slow tests explicitly with `pytest -m slow`.

### Fixed

- **CLI: JSON output pollution** — Logging now disabled in `--json` mode to prevent log messages from corrupting JSON output.
- **Tests: import safety test reliability** — Import safety tests now verify source code defaults rather than runtime values affected by `conftest.py` modifications.
- **Templates: `custom_class` prefix** — Generated project templates now use the `src.*` prefix for `custom_class` references, compatible with the narrowed `ALLOWED_PREFIXES` allowlist.

### Documentation

- **Templates: `secure_load` usage** — Documented `secure_load` usage in the generated `03_inference.py.tpl`.

## [0.2.8] - 2026-07-02

### Added

- **Contracts: single home for base classes** — `energizados.contracts` is now the single source of truth for all 8 framework base classes (`BaseModel`, `BaseInference`, `BasePipeline`, `BaseEvaluator`, `BaseETL`, `BaseFeatureEngineering`, `BaseFeatureSelector`, `BaseExplorer`). Backward-compatible shims re-export them from their legacy paths (`energizados.core.base`, `energizados.etl.base`, `energizados.feature_engineering.base`, `energizados.feature_selection.base`, `energizados.eda.base`, `energizados.inference.base`). This is a frozen public API.
- **Contracts: `save()`/`load()` on `BaseModel` and `BaseFeatureSelector`** — persistence now part of the public base-class contract, aligned with `BaseFeatureEngineering`.
- **ETL: `CleanFilesETL` honors the `BaseETL` contract** — cleanup ETL integrates cleanly via a `noop_load` hook, so the orchestrator tracks it as a normal DAG node without writing a dataset.

### Changed

- **Core: unified `Registry` class** — extracted a single generic `Registry` and migrated `ModelRegistry` onto it. Model adapters now resolve config through a per-adapter `from_config` method instead of a central if/elif ladder, making new model registration additive.
- **Core: lazy imports in builders and steps** — `ETLOrchestrator`, `DefaultEvaluator`, `DefaultInference`, `DefaultFeatureEngineering`, and `ModelRegistry` are now imported lazily inside builders/steps, breaking circular-dependency cycles introduced by the contracts consolidation.
- **Inference/Evaluation/Feature-selection: type alignment to contracts** — `DefaultEvaluator`, `FeatureSelectionPipeline`, and `HierarchicalInference.load_model` now inherit/annotate against the consolidated base classes for consistency.

### Refactoring

- **`framework-core-redesign`** (core-layering + contracts-consolidation + unified-registry) completed and archived via SDD. No behavior changes for existing callers; import paths are preserved through shims.

## [0.2.7] - 2026-07-01

### Added

- **Inference: `HierarchicalInference`** — generic routing to multiple models based on dataframe conditions (`column: value_or_list`). Supports first-match-wins, per-route FE (`feature_engineering_paths`), fallback model (`default_model_path`), and callable conditions. Native integration with `InferenceBuilder` (no `model_path` required when `routes` are configured)
- **Tests: `test_hierarchical_inference.py`** — 15 unit tests for `HierarchicalInference` (init, condition evaluation, routing, FE transform, builder integration)
- **Training: `columns_filter` in `feature_engineering.preprocessing`** — row-level filtering (equality, comparison operators, pandas `_expr`) now works in training, not just inference. The filter is applied to all splits (train/val/test) with `X` and `y` kept aligned by index. Useful for region-specific models without creating a separate ETL. Logic is shared with inference via `energizados.core.utils.columns_filter.apply_columns_filter`
- **GeoFeaturesETL: `include_cluster` parameter** — new `include_cluster: false` option to skip KMeans geographic clustering (`geo_cluster` column) while still generating IBGE hierarchy and distance features; useful when `stratified_time` split is not needed
- **Split: Unlabeled negatives injection** (`split.unlabeled_negatives`) — load external unlabeled contracts as `target=0` samples into train split; supports `time_series` date filtering, ID dedup against val/test, `max_per_cutoff` sampling, and NaN fill for missing columns
- **Split: Geo-stratified sampling** (`split.geo_stratify`) — balance geographic representation in train set with three strategies: `proportional` (cap to median), `equal` (reduce to min), `capped` (cap at `max_per_stratum`); logs WARNING if >50% data loss; metadata persisted in `split_metadata.json`
- **Evaluation: Segment thresholds export** — export per-segment optimal thresholds as `segment_thresholds_{column}.json` during evaluation (for each column in `segmented_evaluation.by`); JSON includes `threshold_mode`, `default_threshold`, and per-segment `threshold`/`auc`/`n_samples`
- **Inference: Per-segment thresholds** (`inference.segment_thresholds`) — load `segment_thresholds.json` and apply per-row thresholds based on segment column; `fallback_threshold` for unknown segments; `ValueError` raised if segment column missing from inference data
- **Evaluation: `threshold_mode="segment"` alias** — friendly alias for `"youden"` in segmented metrics; resolved before the loop to avoid parameter mutation
- **Skill: `version-deliverable`** — generate per-version deliverable documents with experiment summary and model comparison
- **Core: public exception types** — added `TransformerError`, `FeatureSelectionError`, `InferenceError`, `EvaluatorError`. `ModelNotFittedError` now also subclasses `ValueError` (additive — `except ValueError` still catches it). Fitted-state guards in `BaseFeatureEngineering`/`BaseFeatureSelector` and the `HierarchicalInference` "models not loaded" path now raise these typed errors.

### Changed

- **Core: `Pipeline.run` preserves framework exceptions** — `Pipeline.run` now re-raises `EnergizadosError` subclasses (e.g. `ConfigurationError`, `ETLDependencyError`) unchanged instead of wrapping them as `PipelineError`. Only unexpected (`Exception`) step errors are wrapped as `PipelineError` with the original preserved on `__cause__`. **Migration:** catch `except EnergizadosError` where you previously caught `except PipelineError` for inner framework errors (`except EnergizadosError` is an additive superset that still catches `PipelineError`).

### Fixed

- **Evaluation: `segment` alias mutation bug** — `threshold_mode="segment"` no longer mutates the parameter inside the loop, preventing incorrect "Unknown threshold_mode" warnings and wrong export values
- **Preprocessing: `GroupRelativeConsumption` dtype** — explicit `.astype(float)` before `.fillna(0.0)` prevents TypeError on mixed-type group columns
- **ETL: Upstream output validation** — orchestrator no longer raises "input file does not exist" for paths that are the declared output of an upstream ETL in the DAG

### Refactoring

- **Inference: `InferenceBuilder` support for `HierarchicalInference`** — passes `routes`, `default_model_path`, and `feature_engineering_paths` kwargs to the constructor; detects hierarchical inference to skip single-`model_path` auto-detection; `validate_input` and `execute` support loading multiple models internally
- **Inference: `columns_filter` extracted to shared utility** — moved the row-filtering logic from `inference_builder._apply_columns_filter` to a reusable `apply_columns_filter` function in `energizados.core.utils.columns_filter`; inference and training now share the same implementation
- Remove release automation components (commitlint, husky, git-cliff scripts, GitHub Actions workflow)

## [0.2.6] - 2026-04-25

### CI/CD

- Opt into Node.js 24 for GitHub Actions (#10)
- **workflows:** Upgrade actions/checkout and actions/setup-python to v6 (#11)

## [0.2.2] - 2026-04-15

### Fixed

- `doctor` command now uses `importlib.metadata` for reliable package version detection instead of unreliable module-level attributes
- Added `jsonschema` dependency for config validation

## [0.2.1] - 2026-04-15

### Changed

- Updated license to new IDB template with AI_BID disclaimer

## [0.2.0] - 2026-04-15

### Core

- Full redesign: Builder pattern, Pydantic validation, modular pipeline steps
- CLI: `init`, `run`, `validate`, `eda` commands with wildcard support and custom run naming (`-n`)
- Config files: `etl.yaml`, `train.yaml`, `infer.yaml`, `eda.yaml` — three separate files, each evolving independently
- Schema versioning: each config section carries `schema_version`; the CLI blocks execution if the project schema is newer than the installed framework
- Run scripts in `src/run/` for direct execution without CLI (`ConfigPipelineBuilder` API)

### ETL

- Multi-ETL orchestration with DAG dependency resolution (topological sort)

### Feature Engineering

- Column transformers: cardinality reducer, dummies, target/ordinal encoding, MinMax scaler, cast dtype
- Global transformers: `tsfel_vars`, `extra_vars`, `consumption_patterns`, `clip_outliers`, `geo_features`
- Feature selection: Boruta, Correlation, Constant
- `feature_engineering` moved inside `train.yaml` (no separate `feature_pipeline.yaml`)

### Modeling

- Models: LightGBM, CatBoost, **XGBoost** (optional dep: `pip install energizados[xgboost]`), Neural Networks, LSTM
- Unsupervised: **IsolationForest** (trains without labels; uses `contamination` param)
- Rule-based baselines: `simple_trend` (ChangeTrend), `simple_constant` (ConstantConsumption)
- Ensemble: stacking (OOF or blending) and soft voting via `EnsembleModel`
- Sampling: `undersample`, `oversample`, `none` per-model
- Hyperparameter search: `RandomizedSearchCV` with configurable `n_iter` and `cv`

### Splits

- `time_series`, `stratified`, `random`, `group_based`, `stratified_time` (requires `geo_cluster` from GeoFeaturesETL)

### EDA

- 7-phase interactive HTML report (Plotly + Matplotlib)
- Phase 5: IV, KS, Cramér's V feature importance ranking
- Phase 6: population segmentation and drift analysis
- Phase 7: configurable hierarchical column relationships (`RelatedColumnsAnalyzer`)

### Evaluation

- Metrics: AUC, Precision, Recall, F1, confusion matrix, cumulative gains
- HTML + JSON reports per training run
- Per-run index (`output/index.html`) for multi-experiment comparison
- Threshold calibration
-

### Inference

- Configurable pipeline with auto-loading of feature engineering + model artifacts
- `columns_filter` with comparison operators for record-level filtering
- Enriched output with original columns alongside predictions

### Quality

- Comprehensive test suite: `test_source_etl.py`, `test_etl_orchestrator.py`, `test_cli_init.py`, `test_default_inference.py`
- Pre-commit hooks (black, flake8, mypy, bandit)
- Secure pickle: SHA-256 verified load/save for model artifacts

## [0.1.0] - 2024-01-01

Initial notebook-based research framework published by the IDB ([EL-BID/Energizados](https://github.com/EL-BID/Energizados)).

### Added

- Jupyter notebooks for local and Google Colab execution
- Rule-based models: consumption drop detection (`ChangeTrend`), constant consumption detection (`ConstantConsumption`)
- Supervised models: LightGBM, feedforward Neural Network, LSTM+Dense hybrid
- Preprocessing: TSFEL time-series feature extraction, statistical vars, categorical encoding (dummy, cardinality reducer, target encoding), row-wise MinMax scaling
- Feature selection: constant removal, correlation-based, Boruta
- Imbalanced-class handling: random oversampling and undersampling
- Hyperparameter optimization via Random Search
- Evaluation: AUC-ROC metric
- Anonymized sample dataset (42,500 records, 19 columns, 5.8 % fraud rate)
