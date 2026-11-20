# ETL row filtering

Implement the approved `docs/design/sdd-etl-row-filtering.md` without changing legacy behavior when no filters are configured.
Engram mirror: unavailable in this session; this file is the continuity source of truth.

## Specs

- **S1** — User request: "necesito agregarle al framework la posibilidad de que en el step de etl se pueda filtrar registros en base a condiciones. Evaluar si conviene implementar en el config yaml de etl algun campo donde se pueda escribir una condicion para cada fuente de datos.\nIniciemos un sdd"
- **S2** — Filtering-level decision: "Soportar ambos niveles". Apply `input[].filter` before concat/merge and `params.filter` after combining, as specified in SDD §6.1–§6.3.
- **S3** — Incremental decision: "Avanzar igual (recomendado)". The watermark advances from rows after the incremental-key cutoff and before either row filter; filtered rows require `reprocess: true` to be revisited.
- **S4** — Empty-output decision: "Escribir salida vacía". Write a 0-row parquet with available schema and a WARNING when filtering empties concat/merge output.
- **S5** — Implementation approval: "aprovado".
- **S6** — SDD strictness and compatibility requirements: invalid ETL filters fail loudly; training/inference `columns_filter` behavior and no-filter ETL behavior remain unchanged (SDD §6.4, §8–§9).

## Tasks

- **T1** — S2, S6 — DONE: strict reusable evaluation and ETL-level `SourceETL` filtering across concat/merge/incremental, with focused tests — commit: `2d60d90`.
- **T2** — S2, S3, S4, S6 — DONE: structured per-input filters, orchestrator metadata resolution, empty-output handling, and focused tests — commit: `d16108e`. Risk: item 3 (structured input and shared empty-extract behavior are consumed by existing ETLs/custom classes).
- **T3** — S1–S4, S6 — DONE: JSON schema, CLI/service/API validators, dry-run compatibility, template, user docs, AGENTS.md/CLAUDE.md symlink, and CHANGELOG.md, with validation tests — commit: `faed56c`.
- **T4** — S1–S6 — DONE: independent `gentle-ai-verify` verdict PASS for S1–S6 and all 8 SDD acceptance criteria; full conda suite run; durable regression tests added — commit: pending this closing commit.

## Log

- **L1** — Original request: "necesito agregarle al framework la posibilidad de que en el step de etl se pueda filtrar registros en base a condiciones. Evaluar si conviene implementar en el config yaml de etl algun campo donde se pueda escribir una condicion para cada fuente de datos.\nIniciemos un sdd"
- **L2** — User selected "Soportar ambos niveles" for filter placement and "Avanzar igual (recomendado)" for incremental watermarks.
- **L3** — User selected "Escribir salida vacía" for combined inputs emptied by filtering.
- **L4** — User approved the SDD with "aprovado". Implementation authorized on branch `feat/etl-row-filtering`.
- **L5** — No Engram/memory tools are registered; no mirror was created. Writer rule does not fire: the behavior units are dependent and will be implemented inline. Verification rule fires for T2 Risk item 3.
- **L6** — Environment incident: `.venv` has Python but no pytest/pandas/pyarrow/pip; system Python also lacks them. An isolated disposable test environment was prepared under `/tmp/energizados-etl-filter-tests`; the project environment was not modified. Initial test commands therefore did not produce a valid RED.
- **L7** — T1 RED: 13 failed, 1 passed (expected missing filter/strict behavior). GREEN: `tests/etl/test_source_etl_filter.py` 14 passed. Regression: `tests/test_source_etl.py` plus new filter tests, 104 passed, 5 pre-existing pandas FutureWarnings. Runner: isolated Python with `PYTHONPATH=src`, `-o addopts=''` because pytest-cov is not installed there.
- **L8** — Commit evidence: SDD/tracking `e2db973`; T1 `2d60d90`. Git identity was configured locally as the user-approved previous author. Pre-commit passed after automatic isort/black formatting; tests were rerun and stayed at 104 passed. Review slice boundary: these two commits contain 639 authored insertions; no publishing or PR shape is authorized.
- **L9** — T2 RED: 10 failed, 2 passed before implementation (merge fixture then strengthened). Context backstop fired; one bounded worker completed direct incremental extraction and the empty-load hook within declared edit surfaces. Parent spot check and combined regression: 143 passed, 5 pre-existing pandas FutureWarnings. Base-vs-change differential by worker: no-filter empty/non-empty and custom BaseETL behavior byte-identical. Pre-commit passed after black formatting and tests were rerun. T2 commit: `d16108e` (Risk item 3 isolated). Review slice boundary recorded: `e2db973` → `2d60d90` → `d16108e`; publishing/PR shape remains undecided.
- **L10** — T3 first worker exhausted provider quota after partial edits; the human explicitly requested continuation. Parent confirmed no active child and observed 22 focused tests passing, then resumed with narrowed scope. A third service path (`api/validate.py`) was found and authorized as an additional worker edit surface. RED: 3 failed, 23 passed for malformed validate_dict cases; GREEN: 26 focused passed. Parent API/CLI/schema regression: 151 passed. A mixed-order `test_validate_cli_parity_with_api` failure reproduces on base and passes alone (global RichHandler WARNING contaminates JSON stdout); it is pre-existing and not fixed in this feature. Pre-commit found and parent fixed a missing ETLOrchestrator import plus unused test imports; final hooks passed. T3 commit: `faed56c`. Review slice boundary now `e2db973` → `2d60d90` → `d16108e` → `faed56c`.
- **L11** — Independent verifier verdict: PASS for S1–S6 and all 8 SDD acceptance criteria, with E2E CLI spec example, 13 legacy no-filter differential scenarios byte-identical against base `79e2fa1`, strict error/empty-output/watermark probes all passing, and three durable-test suggestions. Advisories (cosmetic only): double-wrapped input-filter error message in `extract()`; `_render_etl_plan` duplication of orchestrator plan rendering.
- **L12** — Human requested the full suite in conda env `bid-energ-py310-3` (Python 3.10.20). Full run including slow tests: 2148 passed, 2 failed, 5 skipped. Both failures diagnosed as not caused by this branch: (a) `test_validate_cli_parity_with_api` — order-dependent logging contamination, pre-existing (reproduced on base in mixed ordering; passes alone and in cli_main+parity subset on both branch and base); (b) `test_project_scoped_job_lands_under_project_output` — child-process SIGSEGV flake under full-suite load; passes in isolation on both branch (5.91s) and base (5.34s). Earlier /tmp env failures (geo/duckdb, business-rules backticks, web) were also base-reproducible environment issues, not regressions.
- **L13** — Added the verifier's 3 durable regression tests (second incremental run no-op after watermark; failed filtered run leaves previous output byte-identical; merge side emptied by input filter writes 0-row output). Focused suites after addition: 172 passed. SDD status updated to Implemented. Publishing/PR shape remains a user decision.
