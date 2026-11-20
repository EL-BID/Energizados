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

- **T1** — S2, S6 — Inline: add strict reusable evaluation and ETL-level `SourceETL` filtering across concat/merge/incremental, with focused tests — commit: pending.
- **T2** — S2, S3, S4, S6 — Inline: add structured per-input filters, orchestrator metadata resolution, empty-output handling, and focused tests — commit: pending. Risk: item 3 (structured input and shared empty-extract behavior are consumed by existing ETLs/custom classes).
- **T3** — S1–S4, S6 — Inline: update JSON schema, both validators, dry-run compatibility, template, user docs, AGENTS.md, CHANGELOG.md, and SDD status, with validation tests — commit: pending.
- **T4** — S1–S6 — Inline + independent `gentle-ai-verify`: run focused/full checks, base-versus-change differential checks, review the complete SDD, and close evidence — commit: pending if task-document evidence changes.

## Log

- **L1** — Original request: "necesito agregarle al framework la posibilidad de que en el step de etl se pueda filtrar registros en base a condiciones. Evaluar si conviene implementar en el config yaml de etl algun campo donde se pueda escribir una condicion para cada fuente de datos.\nIniciemos un sdd"
- **L2** — User selected "Soportar ambos niveles" for filter placement and "Avanzar igual (recomendado)" for incremental watermarks.
- **L3** — User selected "Escribir salida vacía" for combined inputs emptied by filtering.
- **L4** — User approved the SDD with "aprovado". Implementation authorized on branch `feat/etl-row-filtering`.
- **L5** — No Engram/memory tools are registered; no mirror was created. Writer rule does not fire: the behavior units are dependent and will be implemented inline. Verification rule fires for T2 Risk item 3.
- **L6** — Environment incident: `.venv` has Python but no pytest/pandas/pyarrow/pip; system Python also lacks them. An isolated disposable test environment was prepared under `/tmp/energizados-etl-filter-tests`; the project environment was not modified. Initial test commands therefore did not produce a valid RED.
- **L7** — T1 RED: 13 failed, 1 passed (expected missing filter/strict behavior). GREEN: `tests/etl/test_source_etl_filter.py` 14 passed. Regression: `tests/test_source_etl.py` plus new filter tests, 104 passed, 5 pre-existing pandas FutureWarnings. Runner: isolated Python with `PYTHONPATH=src`, `-o addopts=''` because pytest-cov is not installed there.
