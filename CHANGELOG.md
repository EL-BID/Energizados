# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Config: `output_name` — name the run directory from config.** Every section (`train`/`infer`/`eda`/`etl`) accepts `output_name`, mirroring the CLI `-n`.
  - **Precedence:** CLI `-n` wins over config; absent → timestamped default (backward compatible).
- **Inference: `sort_by_probability` — predictions sorted by probability descending by default.** New `infer.sort_by_probability` (bool, default `true`) sorts the output most-suspicious-first, applied after `output_columns` selection. Set `false` to keep input order.
- **Evaluation: configurable `segment_thresholds_*.json` output dir.** `segmented_evaluation.thresholds_output_dir` overrides where the JSON is written.
  - **Migration:** default moved from `reports/evaluation/` to the trained model's `models/` dir (it's a deployment artifact read at predict time). See Notes.
- **Inference: `output_columns` is the self-sufficient output selector; `output_include_input` deprecated.** `output_columns` selects the final columns over the full frame `[input + prediction + probability + rule_*]`, in the order listed; input columns named in it are included automatically.
  - **Use it to:** keep only some input columns, or drop `prediction` by omitting it.
  - **Migration:** `output_include_input` is now a no-op (still warns). Default output (no `output_columns`) → see Changed.
  - **Details:** unknown columns are warned + skipped (not crashed); selection recorded in `.metadata.json`.
- **Dependencies: `geobr` declared in `pyproject.toml`.** `geo_features.py` / `GeoFeaturesETL` import `geobr` lazily but it was undeclared, so a clean install couldn't use geo features.
  - **Note:** `geobr` pulls the GeoPandas/Shapely/GDAL stack (heavier install).

### Changed

- **Inference: default output now includes ALL columns (behavior change).** With no `output_columns`, the predictions file contains all input + `prediction` + `probability` + `rule_*` (was only `[prediction, probability]`).
  - **Migration:** to restore the minimal 2-column output, set `output_columns: [prediction, probability]`.
- **Inference: `index.html` no longer regenerated for inference runs.** The run index lists training evaluation reports, so it's now skipped for non-training run types (`inference`/`eda`/`etl`). Only training runs update it.
- **Inference: logs the generated output columns.** Every predictions file now logs its final column list and count, alongside the existing "Predictions saved to" line.
- **Inference: `output_path` renamed to `output_predictions_path` (deprecated alias kept).** The predictions file is now configured via `output_predictions_path`.
  - **Migration:** `output_path` still works as a deprecated alias (warns). If both are set, `output_predictions_path` wins.
- **Inference: `segment_thresholds.fallback_threshold` removed; fallback is the global `threshold`.** Unknown segment values now unambiguously use the top-level `threshold` (it already did when `fallback_threshold` was omitted).
  - **Migration:** a config still carrying `fallback_threshold` gets a `WARNING` and the value is ignored (no crash). Set `threshold` instead.

### Fixed

- **Security: `secure_pickle` renamed to `integrity_pickle` to honestly describe its threat model.** The previous name implied pickle deserialization was made safe against untrusted input. It is not: `joblib.load` runs arbitrary code on deserialization, and the sidecar `.sig` is written by the same process that writes the `.pkl`, so an active attacker who can write the pickle can also forge a valid signature. The renamed module ships an explicit THREAT MODEL section documenting what is (corruption / tamper detection) and is not (active-attacker resistance, pickle RCE) protected.
  - **Migration (BREAKING):** rename all imports `from energizados.core.utils.secure_pickle import secure_dump, secure_load` → `from energizados.core.utils.integrity_pickle import dump, load`. `validate_no_traversal` keeps its name. The old module name is no longer importable; no alias is provided.
- **Fixed: `doctor` no longer reports scikit-learn as missing (false-negative).** `api.config.doctor()` imported required packages by their PyPI name (`scikit-learn`) instead of their Python import name (`sklearn`); same for `pyyaml` (imports as `yaml`). `__import__("scikit-learn")` always raised `ImportError`, so the doctor always reported scikit-learn — the framework's most important dependency — as missing. Required and optional packages now live in module-level `REQUIRED_PACKAGES` / `OPTIONAL_PACKAGES` mappings of `{import_name: (pypi_name, min_version)}`, separating the two names explicitly. CI no longer masks the doctor smoke step with `continue-on-error: true`.
  - **Migration:** callers importing `REQUIRED_PACKAGES` from `energizados.api.config` see the new `{import_name: (pypi_name, min_version)}` shape (was `{name: min_version}`).
- **Fixed: Windows CLI no longer crashes on non-ASCII glyphs (⚡ ✓ ✗ ⚠ →).** Windows consoles default to cp1252 (`'charmap'` codec), which can't encode those glyphs; on a non-TTY stdout (CI log capture) this raised `UnicodeEncodeError: 'charmap' codec can't encode character '\u26a1'`. The CLI now forces UTF-8 stdio at startup (`_ensure_utf8_stdio`), and CI sets `PYTHONUTF8=1` (PEP 540 UTF-8 mode) — harmless on Linux.
- **Fixed: `output_include_input` no longer pads filtered-out rows with NaN.** When `columns_filter` removed rows, the enriched output gained one NaN-padded row per filtered-out input row (e.g. a 3.4M-row output with only 804k real predictions). Input capture now happens after filtering, so output is 1:1 with predicted rows.
- **Fixed (tests): mock model helper returns exactly `len(X)` probabilities.** The test helper over-returned when the proba list length didn't divide `n`, inflating arrays and masking the padding bug above.

## [0.3.3] - 2026-07-27

### Added

- **ETL: `output_base_dir` for pure-ETL run-dir placement** — The `etl:` config section now accepts a top-level `output_base_dir` scalar (like `schema_version`), so `energizados run etl` writes its run-dir (`run.log` + `config/` copy) under a custom base instead of the default `output/`, matching the existing `train`/`infer`/`eda` behavior. `PipelineDirector._resolve_base_output_dir` now checks `etl` after `train`/`infer`/`eda` (priority `train > infer > eda > etl`; default `output`). `ETL_SCHEMA` declares the key in `properties` so jsonschema does not treat it as an ETL entry requiring `input`, and `ETLOrchestrator` filters it (alongside `schema_version`) so it is not registered as a bogus DAG node. ETL parquet outputs are unaffected — they keep going to their literal `output:` paths; only run metadata relocates.
- **Training: no-holdout mode (`split.method="none"`)** — Train on the full dataset without a validation/test split, intended for production model training after offline evaluation is complete. New `split.method="none"` option writes only `train.parquet`; `val_path`/`test_path` are `None`. `TrainingStep` makes `val_path` optional, keeps an internal 10% split for early stopping only, and reports honest `None` metrics (no fake numbers). `holdout_mode` is exposed in the context (`"none"` vs `"standard"`). Probability calibration is skipped with a warning (it needs val data). Ensemble blending (`use_val_as_oof=true`) raises `ConfigurationError` with three actionable alternatives (provide val / K-fold OOF / `soft_voting`). The director auto-skips the evaluation step with a `WARNING` when `split.method="none"`, and `DefaultEvaluator` defensively returns `skipped=True` instead of crashing on a missing `test_path`. Soft-voting ensembles and K-fold OOF stacking work without val data. Backward-compatible: every existing `split.method` (`stratified`, `random`, `time_series`, `group_based`, `stratified_time`) is byte-identical.

### Changed (internal)

- **GeoFeatures: transformer owns geographic clustering (ADR-0001)** — KMeans clustering (`geo_cluster`) and the train/infer `geo_model.pkl` hand-off move from `GeoFeaturesETL` (file-I/O layer) into the `GeoFeatures` transformer (`preprocessing/`), matching `CONTEXT.md`'s definition of a Transformer. `GeoFeatures` now exposes pure scikit-learn semantics (`fit`/`transform`/`save`/`load`) plus `include_cluster` (default `false`, preserving existing `global_transformers` usage). `GeoFeaturesETL` becomes a thin wrapper that delegates to the transformer while keeping its full param surface and `ETLError` contract. Decision recorded in `src/energizados/docs/adr/0001-geo-features-as-transformer.md` (first framework-core ADR). No public-API changes; internal refactor only.

## [0.3.2] - 2026-07-24

### Added

- **CLI: memory profiling under `-vv`** — `energizados run ... -vv` now samples process RSS around every ETL and pipeline step and reports, live in the progress bar, `Δ<retained> peak <max>` per step (with a `⚠` marker when a step retains more than 1 GB), followed by a `Memory profile` table sorted by peak. Uses `psutil` RSS (correct for pandas/numpy C-level memory, which `tracemalloc` cannot see); zero overhead without `-vv`. Backward-compatible: `ETLOrchestrator`/`Pipeline` gained an opt-in `profile_memory` flag and the `on_etl_complete`/`on_step_complete` callbacks gained an optional `metrics=None` kwarg. New public helper `energizados.core.utils.memory_sampler.MemorySampler` (context manager) and `format_bytes`.
- **GeoFeaturesETL: persist `scaler+kmeans` via `geo_model_path`** — New `geo_model_path` constructor parameter. On first fit, the ETL writes the fitted `StandardScaler` and `KMeans` (plus `n_clusters`) to that path using `secure_pickle`; on later runs (including inference) it reloads them and enters PREDICT mode, where the saved `n_clusters` takes precedence over the config. This keeps cluster IDs consistent between training and serving, so a row's `geo_cluster` means the same thing in both contexts. Loading is best-effort: a missing or unreadable file falls back to FIT mode with an INFO log.

### Fixed

- **Inference: standalone `run infer` with model auto-detection** — `InferenceStep.validate_input` now honors the auto-detected `_resolved_model_path`, so `energizados run infer` no longer aborts with `Missing keys: ['model']` when no `model_path` is set in `infer.yaml`. Validation and execution now resolve the model the same way.
- **CLI: pipeline errors now reach `run.log`** — The `run` command's exception handlers (validation, missing files, unexpected errors) now emit `logger.error(...)` in addition to the terminal panel, so failures appear in the run's `run.log` and not only on screen. The misleading hardcoded panel title "Dataset not found" is replaced with "Validation failed".
- **EDA: report relocation into the run dir** — For typed `energizados run eda` runs, the report and artifacts now reliably land inside the timestamped run directory, overriding `output.output_dir` from the YAML; the caller's config dict is no longer mutated.

### Changed

- **Templates: `infer.yaml` runnable end-to-end out of the box** — Generated `infer.yaml` now points `input_path` at the sample ETL output (`data/processed/sample_dataset.parquet`) and writes predictions inside the inference run directory by default (`output/inference-<TIMESTAMP>/predictions.csv`), so the `etl → train → infer` pipeline runs without manual edits.
- **GeoFeaturesETL: object→category cast** — Object columns (`actividad`, `tipo_tarifa`, `cliente`, ...) are cast to `category` before the internal `X.copy()` so the geo transform's DataFrame copy uses ~4x less memory (object ~1.4 GB → category ~0.4 GB on the sample dataset). Safe because `OrdinalEncoder` and `TeEncoder` handle `category` transparently.
- **GeoFeatures: chunked geocoding** — `_IBGEGeocoder.geocode` now processes points in chunks of 500k (configurable via `chunk_size`) and concatenates the per-chunk spatial-join results. Output is identical to the unchunked version (same per-point dedup, same polygon-border handling), but peak memory is bounded — scales to 3.4M+ inference points without OOM.

## [0.3.1] - 2026-07-15

### Added

- **Web: multi-project workspace foundation (Phase 1)** — Project model with a registry bookmark (`data/web/projects.json`, re-validated against disk on every access); jobs and runs are now project-scoped (each belongs to exactly one project) and the worker `chdir`s into the project directory. The pre-multi-project Global scope is deprecated and surfaces read-only.
- **Web: config templates + project-aware YAML editor (Phase 2)** — Per-project config authoring with templates and an editor scoped to the active project.
- **Web: retrain + inference UX (Phase 3)** — Retrain-from-run and inference flows wired into the console.
- **Web: per-project dashboard + projects home (Phase 4)** — Per-project dashboard wiring, projects-home stats, and a root redirect to the projects home.
- **Web: UI redesign — design system + app shell (Foundation)** — A token-driven design system (`--app-*` CSS custom properties; primary `#6366f1`; Inter + monospace) layered over Bootstrap 5.3, a persisted light/dark theme toggle with anti-flash, and an app shell with a Projects sidebar. Legacy Global routes are moved to a muted footer.
- **Web: UI redesign — project_detail showcase (Hero)** — `project_detail` redesigned into an at-a-glance page: Jobs/Runs grouped by run type (etl / eda / inference / training), a latest-training metric summary, and a lineage placeholder.
- **Web: UI redesign — system rollout + async states** — The design system applied across all remaining page templates (dark-safe, token-driven: `.app-card` panels, compact tables, status-badge consistency), plus async UX: HTMX-native loading indicators on action buttons, an out-of-band job-list refresh on job creation, and empty-state coverage.
- **Web: `/ui` style guide** — A living, self-documenting style-guide page demonstrating the tokens and components; swatches auto-adapt to the active theme (zero hardcoded colors).
- **Core,Web: generalized typed Runs (ADR-0001)** — `RunMetadata` gains a `run_type` discriminator (training / etl / eda / inference) with type-aware serialization (AUC/F1/model_types omitted for non-training runs); the director now emits a typed run dir for any enabled section (priority training > inference > eda > etl), so pure ETL/EDA/inference configs produce browsable `output/<type>-<ts>/` runs. EDA reports and inference predictions relocate into their run dirs; ETL datasets stay at their configured path, referenced from metadata. Old `run_metadata.json` stays loadable as "training".
- **Web: type-scoped Run comparison (ADR-0001)** — `Compare` resolves each run's type before loading evaluation data: mixed-type sets return a typed empty-state (HTTP 409 JSON with `run_types`, or a warning banner on the page) instead of silently 404ing; homogeneous non-training sets render a metadata table; training comparison is unchanged.
- **Web: Global scope deprecated in code (ADR-0002)** — `POST /jobs` no longer creates Global (project-less) jobs (always 400, pointing at `POST /projects/{id}/jobs`); the `/global` editor shows a deprecation banner with a disabled submit. Legacy Global jobs/runs stay readable via the global routes (read-only, no migration).
- **Web: Run→Run retrain lineage (ADR-0003)** — Retrain records the source Run via `derived_from`, persisted both as a `jobs.derived_from_run_id` column and in `run_metadata.json` (mirroring how `run_id` is stored), threaded through the worker to the run manager. `project_detail` renders the lineage chain (Run A → Run B → Run C). Retry stays Job→Job (`retried_from`) and preserves any `derived_from` from the original job (a retried retrain is still derived from its source); the two links remain separate (ADR-0003 non-collapse).

### Fixed

- **Web: `/jobs` direct navigation** — `GET /jobs` returned a bare HTMX fragment (no shell, no dark mode) on direct navigation; now content-negotiated to render a full themed page (`jobs.html`) on direct nav while the 2s auto-refresh poll still receives the fragment.

### Documentation

- **Web: domain model** — Framework-core and web-console bounded contexts documented as ubiquitous-language glossaries with a context map, unified in the repo-root `CONTEXT.md`, plus three web-console ADRs (generalized run, deprecating the Global scope, run-level lineage).

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
