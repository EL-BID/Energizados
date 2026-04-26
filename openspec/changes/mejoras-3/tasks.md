# Task Checklist: mejoras-3 — Threshold by Segment, Geo-Stratified Sampling, Unlabeled Negatives

## Overview

Four features, ordered by dependency and priority:
- **Schema** tasks must go first (they unblock all implementation)
- **F2a** (segment threshold export) is lowest effort, highest impact — done next
- **F2b** (segment threshold inference) depends on F2a schema
- **F3** (geo-stratify) and **F1** (unlabeled negatives) are independent of each other

---

## SCHEMA TASKS (unblock everything)

### T-S1 · SPLIT_SCHEMA — add `unlabeled_negatives` and `geo_stratify` ✅
- **Feature**: cross-cutting (F1, F3)
- **Description**: Extend the jsonschema dict `SPLIT_SCHEMA` in `src/energizados/core/schemas/schemas.py` with two new top-level keys:
  - `unlabeled_negatives`: object with `enabled` (bool), `source_path` (str), `max_per_cutoff` (int), `random_state` (int), `date_column` (str), `id_column` (str)
  - `geo_stratify`: object with `enabled` (bool), `column` (str), `strategy` (enum: proportional/equal/capped), `max_per_stratum` (int, optional), `random_state` (int)
- **Dependencies**: None
- **Test criteria**: Add two new test functions in `tests/test_config_schemas.py` validating that configs with these new keys pass jsonschema, and configs with invalid values (e.g., unknown strategy, missing required fields) fail with descriptive errors
- **Files**: `src/energizados/core/schemas/schemas.py`, `tests/test_config_schemas.py`
- **Status**: COMPLETED — 5 tests added, all passing

### T-S2 · INFERENCE_SCHEMA — add `segment_thresholds` ✅
- **Feature**: F2b
- **Description**: Extend `INFERENCE_SCHEMA` with a `segment_thresholds` object containing `enabled` (bool), `path` (str), `fallback_threshold` (number, optional)
- **Dependencies**: None (schema-only)
- **Test criteria**: New test in `tests/test_config_schemas.py` — valid config passes, config with missing `path` when enabled fails
- **Files**: `src/energizados/core/schemas/schemas.py`, `tests/test_config_schemas.py`
- **Status**: COMPLETED — 3 tests added, all passing

---

## F2a — Segment Thresholds Export (evaluator)

### T-F2a-1 · Test `_export_segment_thresholds` ✅
- **Feature**: F2a
- **Description**: Write tests in `tests/test_evaluator.py` for the export method. Use a mock `segmented_metrics` dict (e.g., `{"Norte": {"threshold": 0.37, "auc": 0.82, "n_samples": 1500, "threshold_mode": "youden"}}`). Verify:
  1. JSON file is written to output_dir
  2. JSON structure matches the schema in the design doc (segment_column, threshold_mode, default_threshold, segments dict)
  3. Multiple segment columns produce multiple JSON files
- **Dependencies**: T-S1 (schema unblocks this)
- **Test criteria**: `pytest tests/test_evaluator.py -k "segment_threshold"` passes
- **Files**: `tests/test_evaluator.py` (create), `src/energizados/evaluation/evaluator.py`
- **Status**: COMPLETED — 8 tests added, all passing

### T-F2a-2 · Implement `_export_segment_thresholds` ✅
- **Feature**: F2a
- **Description**: In `DefaultEvaluator`, add the method `_export_segment_thresholds(segmented_metrics, output_dir, global_threshold, segment_column, threshold_mode)`. It should:
  1. Build a flat dict with `segment_column`, `threshold_mode`, `default_threshold`, and a `segments` sub-dict
  2. Write `segment_thresholds_{column}.json` per segment column
  3. Return a `List[Path]` of written files
  4. Call this method at the end of `execute()` when `segmented_evaluation.enabled` is true, passing through the relevant `seg_by` columns and config
- **Dependencies**: T-S1, T-F2a-1
- **Test criteria**: `pytest tests/test_evaluator.py -k "segment_threshold"` passes; manual run of evaluation produces the JSON artifact
- **Files**: `src/energizados/evaluation/evaluator.py`
- **Status**: COMPLETED — Method implemented and integrated into execute(), returns List[Path], uses indent=2 for JSON

---

## F2b — Segment Thresholds Inference

### T-F2b-1 · Test F2b per-row threshold mapping ✅
- **Feature**: F2b
- **Description**: Write `tests/test_inference_segment_thresholds.py`. Create synthetic data with a known segment column (e.g., `zona`). Load a trained model (fixture or mock). Verify:
  1. Loading a valid `segment_thresholds.json` applies correct thresholds per row
  2. Rows with unknown segment values use `fallback_threshold`
  3. Missing segment column in data raises `ValueError` with descriptive message
  4. Output predictions shape matches input shape
- **Dependencies**: T-S2
- **Test criteria**: `pytest tests/test_inference_segment_thresholds.py -v` passes
- **Files**: `tests/test_inference_segment_thresholds.py` (create)
- **Status**: COMPLETED — 15 tests added covering utility function, builder methods, and integration tests

### T-F2b-2 · Implement segment threshold loading + application in InferenceBuilder ✅
- **Feature**: F2b
- **Description**: In the `InferenceStep` inner class inside `InferenceBuilder`, add:
  1. A helper method `_apply_segment_thresholds(probas, data, segment_thresholds_config)` that maps each row's segment value to its threshold, using `fallback_threshold` for unknown segments
  2. In `execute()`, after computing `predictions` and `probas`, check if `segment_thresholds.enabled`. If so, call `_apply_segment_thresholds` to re-binarize with per-row thresholds
  3. Add a `_load_segment_thresholds(path)` method that reads and validates the JSON (checks `segment_column` exists in data)
- **Dependencies**: T-S2, T-F2b-1
- **Test criteria**: `pytest tests/test_inference_segment_thresholds.py -v` passes
- **Files**: `src/energizados/core/builders/inference_builder.py`
- **Status**: COMPLETED — Added `_load_segment_thresholds()`, `_apply_segment_thresholds()` methods; modified `execute()` to use segment thresholds when enabled; falls back to global threshold when disabled or not configured

### T-F2b-3 · Add `apply_segment_thresholds` to DefaultInference (optional helper) ✅
- **Feature**: F2b
- **Description**: Add a static or module-level utility `apply_segment_thresholds(probas, segment_values, thresholds_dict, fallback_threshold)` to `inference/default.py`. This keeps threshold mapping logic testable/reusable independently of the builder. The InferenceBuilder then delegates to it.
- **Dependencies**: T-F2b-2
- **Test criteria**: Can be tested via T-F2b-1 tests if InferenceBuilder delegates to this utility
- **Files**: `src/energizados/inference/default.py`
- **Status**: COMPLETED — Added `apply_segment_thresholds()` module-level function with full docstring and examples; InferenceBuilder delegates to this function in `_apply_segment_thresholds()`

---

## F3 — Geo-Stratified Sampling

### T-F3-1 · Test `_apply_geo_stratify`
- **Feature**: F3
- **Description**: Write tests in `tests/test_split_step.py` for the geo-stratify logic. Create synthetic data with known stratum sizes (e.g., 3 zones with 100, 50, 200 rows). Verify:
  1. `proportional` strategy: largest stratum capped to median size (~100), smallest unchanged
  2. `equal` strategy: all strata reduced to smallest size (50)
  3. `capped` strategy with `max_per_stratum=80`: no stratum exceeds 80
  4. `data_loss` warning logged when >50% of rows are dropped
  5. ID column (if exists) is preserved after sampling
- **Dependencies**: T-S1
- **Test criteria**: `pytest tests/test_split_step.py -k "geo_stratify" -v` passes
- **Files**: `tests/test_split_step.py`

### T-F3-2 · Implement `_apply_geo_stratify` in SplitStep
- **Feature**: F3
- **Description**: In `SplitStep` (`src/energizados/core/steps/split.py`), add `_apply_geo_stratify(train_df)` method:
  - Group by `geo_stratify.column`
  - Apply strategy:
    - `proportional`: compute median stratum size, sample down strata larger than median
    - `equal`: sample all strata down to smallest stratum size
    - `capped`: clip each stratum at `max_per_stratum`
  - Log before/after counts per stratum
  - Log WARNING if overall data reduction > 50%
  - Return subsampled `train_df`
- **Dependencies**: T-S1, T-F3-1
- **Test criteria**: `pytest tests/test_split_step.py -k "geo_stratify" -v` passes
- **Files**: `src/energizados/core/steps/split.py`

### T-F3-3 · Wire geo_stratify config in SplitBuilder
- **Feature**: F3
- **Description**: In `SplitBuilder.build()`, extract the `geo_stratify` dict from `split_config` and pass it to the `SplitStep` constructor. Add to `return SplitStep(...)` call.
- **Dependencies**: T-S1, T-F3-2
- **Test criteria**: Integration test with a YAML config containing `geo_stratify` section runs without error; `pytest tests/test_split_step.py -k "geo_stratify" -v` passes
- **Files**: `src/energizados/core/builders/split_builder.py`

---

## F1 — Unlabeled Negatives Injection

### T-F1-1 · Test `_inject_unlabeled_negatives`
- **Feature**: F1
- **Description**: Write tests in `tests/test_split_step.py`:
  1. Create a mock parquet with 3 labeled records (target=0/1) and 5 unlabeled records in a separate file
  2. Verify: injected records have `target=0`, NaN-filled missing columns, IDs not in val/test
  3. `max_per_cutoff` limits the count
  4. time_series date filtering: records outside train_period are excluded
  5. ID dedup against val/test works correctly
  6. Empty unlabeled file produces no change (graceful)
- **Dependencies**: T-S1
- **Test criteria**: `pytest tests/test_split_step.py -k "unlabeled" -v` passes
- **Files**: `tests/test_split_step.py`

### T-F1-2 · Implement `_inject_unlabeled_negatives` in SplitStep
- **Feature**: F1
- **Description**: In `SplitStep`, add `_inject_unlabeled_negatives(train_df, val_df, test_df)`:
  1. Load `unlabeled_negatives.source_path` parquet
  2. For time_series splits: filter unlabeled records by `train_period`
  3. Exclude IDs that appear in val_df or test_df (using `id_column`)
  4. Sample up to `max_per_cutoff` records (with `random_state`)
  5. Assign `target=0` to all injected records
  6. Fill columns present in `train_df` but missing in injected data with NaN
  7. Concatenate to `train_df` and return
- **Dependencies**: T-S1, T-F1-1
- **Test criteria**: `pytest tests/test_split_step.py -k "unlabeled" -v` passes
- **Files**: `src/energizados/core/steps/split.py`

### T-F1-3 · Wire unlabeled_negatives config in SplitBuilder + update `execute()` pipeline order
- **Feature**: F1
- **Description**: 
  1. In `SplitBuilder.build()`, extract `unlabeled_negatives` dict and pass to `SplitStep` constructor
  2. In `SplitStep.execute()`, insert F1 call AFTER initial split (step 2) and BEFORE F3 (step 4), following the `split → F1 → F3 → save` pipeline order from the design doc. Only execute when `unlabeled_negatives` config is present and `enabled: true`.
- **Dependencies**: T-S1, T-F1-2
- **Test criteria**: Full SplitStep execution with both F1 and F3 enabled produces valid train/val/test splits with correct shapes; ID dedup metadata is logged
- **Files**: `src/energizados/core/steps/split.py`, `src/energizados/core/builders/split_builder.py`

### T-F1-4 · Update metadata to record F1 injection
- **Feature**: F1
- **Description**: Extend the `split_metadata.json` with a new `unlabeled_negatives_injected` key showing count of injected records and source file. Update in `_inject_unlabeled_negatives`.
- **Dependencies**: T-F1-3
- **Test criteria**: Metadata JSON includes the new key after a run with F1 enabled
- **Files**: `src/energizados/core/steps/split.py`

---

## INTEGRATION / REGRESSION (run after all features)

### T-INT-1 · Regression: existing split methods unchanged
- **Feature**: cross-cutting
- **Description**: Run the full existing test suite (`pytest tests/test_split_step.py` excluding new tests) to ensure stratified/random/time_series/group_based/stratified_time splits produce identical results when F1 and F3 are disabled.
- **Dependencies**: All above
- **Test criteria**: `pytest tests/test_split_step.py -v` (existing tests only) — all pass

### T-INT-2 · Integration: end-to-end F2a → F2b
- **Feature**: F2a + F2b
- **Description**: Run evaluation with `segmented_evaluation.enabled`, then run inference with `segment_thresholds.enabled` pointing to the exported JSON. Verify predictions are consistent with the exported per-segment thresholds.
- **Dependencies**: T-F2a-2, T-F2b-2
- **Test criteria**: Predictions with per-segment thresholds differ from global-threshold predictions (when segments have different optimal thresholds); unknown segments gracefully fall back

### T-INT-3 · Integration: full pipeline with F1 + F3 combined
- **Feature**: F1 + F3
- **Description**: Run `energizados run train` with both `unlabeled_negatives` and `geo_stratify` enabled in config. Verify output shapes, metadata completeness, and that both features applied in the correct order.
- **Dependencies**: T-F1-4, T-F3-3
- **Test criteria**: Pipeline completes without error; split_metadata.json reflects both features

---

## Task Summary Table

| Task ID | Title | Feature | Effort | Dependencies |
|--------|-------|---------|--------|--------------|
| T-S1 | SPLIT_SCHEMA — add unlabeled_negatives + geo_stratify | cross-cutting | LOW | — |
| T-S2 | INFERENCE_SCHEMA — add segment_thresholds | F2b | LOW | — |
| T-F2a-1 | Test _export_segment_thresholds | F2a | LOW | T-S1 |
| T-F2a-2 | Implement _export_segment_thresholds in DefaultEvaluator | F2a | LOW | T-S1, T-F2a-1 |
| T-F2b-1 | Test F2b per-row threshold mapping | F2b | LOW | T-S2 |
| T-F2b-2 | Implement segment threshold loading + application in InferenceBuilder | F2b | MEDIUM | T-S2, T-F2b-1 |
| T-F2b-3 | Add apply_segment_thresholds utility to DefaultInference | F2b | LOW | T-F2b-2 |
| T-F3-1 | Test _apply_geo_stratify | F3 | LOW | T-S1 |
| T-F3-2 | Implement _apply_geo_stratify in SplitStep | F3 | LOW | T-S1, T-F3-1 |
| T-F3-3 | Wire geo_stratify config in SplitBuilder | F3 | LOW | T-S1, T-F3-2 |
| T-F1-1 | Test _inject_unlabeled_negatives | F1 | MEDIUM | T-S1 |
| T-F1-2 | Implement _inject_unlabeled_negatives in SplitStep | F1 | MEDIUM | T-S1, T-F1-1 |
| T-F1-3 | Wire unlabeled_negatives config + pipeline order in SplitStep | F1 | MEDIUM | T-S1, T-F1-2 |
| T-F1-4 | Update metadata for F1 injection | F1 | LOW | T-F1-3 |
| T-INT-1 | Regression: existing split methods unchanged | cross-cutting | LOW | All above |
| T-INT-2 | Integration: end-to-end F2a → F2b | F2a+F2b | MEDIUM | T-F2a-2, T-F2b-2 |
| T-INT-3 | Integration: full pipeline with F1 + F3 | F1+F3 | MEDIUM | T-F1-4, T-F3-3 |

---

## Priority Order for Execution

1. **T-S1, T-S2** — Schema first (unblocks all)
2. **T-F2a-1, T-F2a-2** — F2a export (LOW effort, HIGH impact)
3. **T-F2b-1, T-F2b-2, T-F2b-3** — F2b inference (depends on T-S2)
4. **T-F3-1, T-F3-2, T-F3-3** — F3 geo-stratify (LOW effort, independent of F1/F2)
5. **T-F1-1, T-F1-2, T-F1-3, T-F1-4** — F1 unlabeled negatives (MEDIUM effort, independent)
6. **T-INT-1, T-INT-2, T-INT-3** — Integration tests

---

## Strict TDD Reminder

For each implementation task:
1. **Write the test FIRST** — run it, watch it fail with the expected error
2. **Write the implementation** — minimal code to pass the test
3. **Run pytest** — verify all tests pass
4. **Refactor if needed** — no behavior changes, only code cleanup

Do not proceed to the next task until the current task's tests pass.
