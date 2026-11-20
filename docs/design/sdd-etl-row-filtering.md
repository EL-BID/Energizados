# SDD — Row-level filtering in the ETL step (`SourceETL`)

| | |
|---|---|
| **Status** | Approved — implementation in progress |
| **Date** | 2026-11-20 |
| **Scope** | `energizados.etl` (config surface + `SourceETL` semantics) |
| **Related** | `CONTEXT.md`, `AGENTS.md` (SourceETL section), `docs/user-guide/configuration/etl.md`, `src/energizados/core/utils/columns_filter.py` |

## 1. Problem statement

> "necesito agregarle al framework la posibilidad de que en el step de etl se pueda filtrar registros en base a condiciones. Evaluar si conviene implementar en el config yaml de etl algun campo donde se pueda escribir una condicion para cada fuente de datos."

The user needs to drop records at the ETL step based on conditions, and asks whether a per-source condition field in `config/etl.yaml` is the right place.

## 2. Goals

- **G1** — Filter records declaratively from `config/etl.yaml`.
- **G2** — Support an optional filter for each input, applied before combining inputs.
- **G3** — Support an optional ETL-level filter, applied after concat/merge.
- **G4** — Reuse the existing `columns_filter` grammar used by training and inference.
- **G5** — Support all three `SourceETL` modes: `concat`, `merge`, `incremental`.
- **G6** — Fail loudly on a misconfigured filter; a filter that silently does not apply would produce incorrect downstream datasets.
- **G7** — Preserve existing behavior when neither filter level is configured.

## 3. Non-goals

- Not a generic DAG-level transformation language (no aggregations or cross-ETL logic).
- No automatic filtering support for arbitrary custom ETL classes. The new filtering contract is guaranteed for `SourceETL`; custom classes may adopt it explicitly later.
- No behavior change for `columns_filter` in training/inference configs.
- No change to the abstract methods of the frozen `BaseETL` public API.
- No per-input expression sandbox beyond the trust model already accepted for `columns_filter._expr`.

## 4. Current state (evidence)

| Fact | Evidence |
|---|---|
| ETL entry `params` are passed to the ETL constructor (`etl_class(**params)`) | `src/energizados/etl/orchestrator.py:335-345` |
| The orchestrator resolves strings, globs, and `@etl_name` references into a flat `input_paths` list before instantiation | `src/energizados/etl/orchestrator.py:247-345` |
| Current input resolution assumes each input spec is a string; per-input metadata must be preserved during resolution | `src/energizados/etl/orchestrator.py:259-334` |
| `extract()` concatenates/merges all input files before `transform()` runs | `src/energizados/etl/pipeline.py:312-380` |
| `transform()` currently performs `.copy()`, `dropna(how="all")`, then optional `transform_fn` | `src/energizados/etl/pipeline.py:1153-1185` |
| `BaseETL.run()` currently returns early when the extracted DataFrame is empty, before `transform()` and `load()` | `src/energizados/contracts.py:443-478` |
| Incremental mode processes each file through `_read_single_file`, `_filter_by_incremental_key`, `transform()`, and partition load | `src/energizados/etl/pipeline.py:739-920` |
| The incremental high-water mark is computed from rows surviving the incremental-key cutoff, before `transform()` | `src/energizados/etl/pipeline.py:472-526` |
| A shared evaluator already exists: `apply_columns_filter(data, columns_filter)` | `src/energizados/core/utils/columns_filter.py:16-107` |
| ETL JSON schema currently accepts string input items and free-form `params` | `src/energizados/core/schemas/schemas.py:13-31` |
| Structural ETL validation exists in both the CLI validator and the service-layer config validator | `src/energizados/cli/validate.py:172-234`, `src/energizados/core/schemas/config_validator.py:155-179` |

Existing evaluator grammar (`core/utils/columns_filter.py`):

| Form | Meaning |
|---|---|
| `col: scalar` | equality (`col == value`) |
| `col: [v1, v2]` | membership (`isin`) |
| `col: {op: value, ...}` | comparison operators AND-chained |
| `_expr: "..."` | pandas query expression, applied first, ANDed with the rest |

Operators supported: `==`, `!=`, `>`, `>=`, `<`, `<=`, `like` (case-insensitive contains).

Known quirk: today the evaluator **warns and skips** on a missing column or unknown operator, and logs then continues on an invalid `_expr`. That behavior must remain the default for training/inference, but is unsafe for ETL filters.

## 5. Options considered

| # | Option | Pros | Cons | Verdict |
|---|---|---|---|---|
| O1 | `params.filter` on each `SourceETL` entry | Simple ETL-level condition; can reference any column after concat/merge; uniform `transform()` hook | By itself cannot reduce memory before concat | **Selected** |
| O2 | Standalone `RowFilterETL` DAG node | Composable over arbitrary upstream outputs; inspectable standalone artifact | Extra node and parquet write; does not provide pre-combine filtering | Follow-up only |
| O3 | Generic top-level `filter:` applied by the orchestrator after any ETL | Could work for custom classes | Conflicts with `stream_result`; adds a second transformation path; less explicit ownership | Rejected |
| O4 | Structured input items with `input[].filter` | Filters each source before concat/merge; reduces memory; supports source-specific rules | Requires preserving input metadata through orchestrator resolution and extending YAML validation | **Selected together with O1** |

**Design answer:** yes, conditions belong in `config/etl.yaml`, at two explicit levels:

- `input[].filter`: one condition per input, before combining data.
- `params.filter`: one condition for the whole `SourceETL`, after combining data.

The levels are unambiguous, optional, and composable. Supporting both was an explicit user decision.

## 6. Detailed design

### 6.1 Backward-compatible YAML surface

Existing string inputs remain valid and unchanged. A filtered input uses an object with exactly `path` and optional `filter`:

```yaml
etl:
  consumos:
    enabled: true
    input:
      # Legacy form: no per-input filter.
      - "data/raw/consumos_2022.csv"

      # Per-input filter, applied before concat.
      - path: "data/raw/consumos_2023.csv"
        filter:
          zona: ["NORTE", "SUL"]
          consumo_total: {">": 0, "<=": 50000}

      # Globs are valid; the filter applies to every expanded file.
      - path: "data/raw/consumos_2024_*.csv"
        filter:
          _expr: "tipo_servicio != 'CORTADO'"

      # @etl_name references are valid too; the filter applies to every
      # path produced by resolving the reference.
      - path: "@consumos_historicos"
        filter:
          estado: "ACTIVO"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"

      # ETL-level filter, applied after all inputs are concatenated.
      filter:
        consumo_total: {"<=": 100000}
        _expr: "(zona != 'EXTERIOR') & (consumo_total > 0)"
```

Rules:

- `input` keeps its current string-or-list shape. Within a list, each item may be a string or `{path: string, filter?: object}`.
- A single filtered input is written as a one-item list; a top-level mapping is not added in this increment.
- Input objects reject unknown keys and require a non-empty string `path`.
- Both filter levels use the complete `columns_filter` grammar.
- `params.filter` remains a free-form `params` entry for JSON-schema compatibility; structural validators give it a precise grammar.
- No `schema_version` bump: old configurations remain valid and the new fields are optional.

### 6.2 Input resolution and metadata preservation

The orchestrator must normalize and resolve each input spec without discarding its filter:

1. Normalize a legacy string to `{path: <string>, filter: None}`.
2. Resolve literals, sorted glob expansions, and `@etl_name` references exactly as today.
3. Broadcast the original input filter to every path produced by that spec.
4. Preserve input order and produce two aligned structures:
   - `input_paths`: the existing flat list of resolved paths.
   - `input_specs`: one `{path, filter}` record per resolved path.

`SourceETL` receives `input_specs` as an optional constructor argument and zips it positionally with `input_paths`. A path-to-filter dictionary is explicitly forbidden: the same path may occur more than once with different filters, and merge semantics are positional.

Direct `SourceETL` instantiation without `input_specs` remains supported and means no per-input filters. Legacy custom ETLs keep receiving the existing `input_paths`; the orchestrator must not inject a new unexpected kwarg into them. Structured filtered inputs are supported for `SourceETL`, and produce a clear configuration error for classes that do not advertise support.

### 6.3 Application order and per-mode semantics

The two filters are ANDed by their placement, but intentionally run at different times.

#### concat

```text
read each input
→ apply that input's filter
→ concatenate
→ dropna(how="all")
→ apply params.filter
→ transform_fn
→ partition/load
```

Per-input conditions can only reference columns from their own input. The ETL-level condition can reference any column in the combined frame.

#### merge

```text
read and filter each side independently
→ sequential merge in declared input order
→ dropna(how="all")
→ apply params.filter
→ transform_fn
→ load
```

This makes source-specific filters useful for reducing join inputs while retaining post-join conditions in `params.filter`. Standard pandas merge semantics apply if one side becomes empty; a WARNING is logged.

#### incremental

For each file:

```text
read file
→ apply incremental-key cutoff and compute new_max
→ apply that file's input filter
→ dropna(how="all")
→ apply params.filter
→ transform_fn
→ write partitions
→ mark file processed / persist state
```

The high-water mark is calculated from rows surviving the **incremental-key cutoff**, before either row-filter level. Therefore:

- Rows discarded by either filter do not hold back the watermark.
- Filtered rows are not revisited on later runs.
- Changing a filter requires `reprocess: true` to re-read historical rows.
- Both filters remain streaming-friendly and compatible with `stream_result`.

The direct `_extract_incremental()` path must apply the same per-input semantics even though normal incremental execution uses `SourceETL.run()`.

### 6.4 Strictness and errors

- Structural validation happens before reading data:
  - each filter must be a mapping;
  - `_expr` must be a string;
  - operator mappings may contain only `==, !=, >, >=, <, <=, like`;
  - input objects require `path` and reject unknown keys.
- `SourceETL.__init__` raises `ValueError` for structural violations, consistent with its existing constructor validation.
- `apply_columns_filter` gains `strict: bool = False`:
  - `strict=False`: current warn/log-and-continue behavior remains unchanged for training and inference;
  - `strict=True`: missing column, unknown operator, and invalid `_expr` raise.
- Both ETL filter levels call the evaluator with `strict=True`.
- Runtime failures are wrapped in `ETLError` and identify:
  - ETL name;
  - level (`input filter` or `ETL-level filter`);
  - input path for per-input failures;
  - offending column/operator/expression where available.

No operator evaluation is reimplemented in `SourceETL`.

### 6.5 Empty results, logging, and counts

Every filter application logs the level and count:

```text
• ETL '<name>' input filter '<path>': kept N of M records (removed K)
• ETL '<name>' ETL-level filter: kept N of M records (removed K)
```

Empty-output behavior is explicit:

- An input reduced to 0 rows remains an empty DataFrame with its schema and emits a WARNING.
- If concat/merge is empty after per-input filtering, the ETL still executes the remaining transform/load path and writes a **0-row output with the available schema**, with a WARNING.
- To achieve that without changing legacy ETL behavior, `BaseETL.run()` may gain an internal opt-in empty-load flag/hook. It defaults to the current early-return behavior and is enabled only for `SourceETL` instances with per-input filters. No abstract public method changes.
- If `params.filter` empties a previously non-empty frame, a 0-row output is written with a WARNING.
- In incremental mode, a file empty after either filter is marked processed, writes no partitions, logs a WARNING, and advances state as defined in §6.3.
- `stream_result` summaries report post-filter row counts.

### 6.6 Validation and planning UX

All existing entry points must understand structured inputs:

- `ETL_SCHEMA`: array items accept either strings or `{path, filter}` objects.
- `cli/validate.py::_validate_etl_section`: validates both input-level and ETL-level filter grammar.
- `core/schemas/config_validator.py::_validate_etl`: applies equivalent validation for service-layer callers such as `validate_dict`.
- Orchestrator resolution and `energizados run etl --dry-run`: display resolved paths without crashing on mapping inputs.
- Errors should be reported during `energizados validate etl` whenever they do not require data; missing DataFrame columns remain runtime errors.

## 7. Implementation plan

| File | Change |
|---|---|
| `src/energizados/core/utils/columns_filter.py` | Add opt-in `strict=False`; preserve default behavior |
| `src/energizados/etl/orchestrator.py` | Normalize structured inputs; resolve/broadcast filters; preserve positional `input_specs`; keep legacy custom-class calls unchanged |
| `src/energizados/etl/pipeline.py` | Add both filter levels, constructor validation, per-mode application, strict errors, and empty-result handling |
| `src/energizados/contracts.py` | If required by §6.5, add a backward-compatible internal opt-in for loading an empty extracted frame |
| `src/energizados/core/schemas/schemas.py` | Extend ETL input-item JSON schema |
| `src/energizados/cli/validate.py` | Validate both filter levels and structured input items |
| `src/energizados/core/schemas/config_validator.py` | Mirror validation for service-layer callers |
| `src/energizados/templates/config/etl.yaml.tpl` | Add commented per-input and ETL-level examples |
| `docs/user-guide/configuration/etl.md`, `AGENTS.md`, `CHANGELOG.md` | Document grammar, order, empty outputs, strict errors, and incremental watermark semantics |
| `tests/etl/test_source_etl_filter.py` (new) | Focused filter behavior tests |
| `tests/test_etl_orchestrator.py` | Structured input resolution, references/globs, order, duplicates, dry-run compatibility |

### Test plan (test-first RED → GREEN)

1. Shared evaluator: every existing grammar form still works; default `strict=False` retains warn-and-skip behavior.
2. Strict evaluator: missing column, unknown operator, and invalid `_expr` raise.
3. Concat: different per-input filters apply to their own files before concat.
4. Concat: `params.filter` applies once to the combined frame.
5. Both levels: observable results prove per-input filter runs first and the surviving rows satisfy both levels.
6. Merge: per-input filters apply before the join; ETL-level filter can reference columns from both sides after the join.
7. Resolution: literal paths, globs, and `@etl_name` references broadcast filters correctly and preserve declared order.
8. Resolution: the same path appearing twice with different filters remains positional and is not collapsed into a map.
9. Incremental: filtered partitions are correct and `last_processed_value` advances from rows before either row-filter level.
10. Incremental: a file with 0 rows after filtering is marked processed, writes no partitions, and emits a WARNING.
11. Concat/merge: all rows removed by per-input filters still produce a 0-row output with schema and WARNING.
12. `params.filter` producing 0 rows writes a 0-row output with WARNING.
13. No filters: existing behavior, including the legacy empty-extract early return, remains unchanged; run the required base-versus-change differential check.
14. Errors: messages identify ETL name, filter level, input path where applicable, and offending condition.
15. `energizados validate etl` and `validate_dict` reject malformed input objects and filters before execution.
16. Dry-run accepts structured inputs and prints the resolved plan.
17. `stream_result` summaries reflect post-filter counts.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `_expr` executes pandas query expressions | Same project-owner trust model as existing train/infer `columns_filter`; documented, not sandboxed |
| Silent filter non-application | Strict ETL evaluation plus structural validation in both validators |
| Structured inputs break existing ETL configs or custom classes | Legacy strings normalize to the current path list; no new kwarg is injected into legacy custom classes; differential tests cover no-filter behavior |
| Watermark semantics surprise | Document and test that both filters run after watermark calculation; `reprocess: true` is the explicit recovery path |
| Empty extract historically skips load | Narrow internal opt-in only for filtered `SourceETL`; default BaseETL behavior and no-filter SourceETL behavior stay unchanged |
| Duplicate paths lose their distinct filters | Positional aligned `input_specs`; never key filter metadata by path |
| High memory on concat | Per-input filters run before concat; ETL-level filter intentionally remains post-combine |
| Custom classes silently ignore structured filters | Only `SourceETL` advertises the new contract; unsupported classes fail validation clearly |

## 9. Acceptance criteria

- Existing ETL YAML continues to run unchanged.
- Users can configure either filter level independently or both together.
- Per-input filters run before concat/merge; ETL-level filters run after.
- Incremental watermarks advance from rows before both row-filter levels.
- Invalid ETL filters never degrade into warn-and-skip behavior.
- Empty filtered concat/merge outputs are written as 0-row datasets with a WARNING.
- Training and inference filtering behavior remains unchanged.
- Validation, dry-run, documentation, templates, and tests cover the new YAML surface.

## 10. Follow-ups (not in scope)

- `RowFilterETL` if filtering arbitrary upstream/custom ETL outputs becomes a real need.
- Null-handling sugar such as `{"isna": true}`; currently expressible through `_expr: "col.isna()"`.
- Adoption of structured input filters by additional built-in or custom ETL classes.

## 11. Decision log

- **D1 — Filtering levels:** user selected **“Soportar ambos niveles”**: per-input before combining and ETL-level after combining.
- **D2 — Incremental watermark:** user selected **“Avanzar igual”**: rows discarded by filters are not revisited; changing filters requires `reprocess: true`.
- **D3 — Empty combined result:** user selected **“Escribir salida vacía”**: write a 0-row parquet with available schema and a WARNING.
- **D4 — Approval:** user wrote "aprovado"; implementation started on branch `feat/etl-row-filtering`.
