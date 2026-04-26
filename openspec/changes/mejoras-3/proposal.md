# Proposal: mejoras-3 — Threshold by Segment, Geo-Stratified Sampling, Unlabeled Negatives

## Intent

Three production-hardening features for the Energizados ML pipeline:
1. **Threshold by segment** — export per-segment optimal thresholds from evaluation and apply them during inference, replacing the single global threshold.
2. **Geo-stratified sampling** — balance geographic representation in the training split after splitting, reducing selection bias.
3. **Unlabeled negatives injection** — load external unlabeled contracts as negative samples (`target=0`) into the training split.

## Scope

### In Scope
- **F2a**: Export `segment_thresholds.json` from `DefaultEvaluator` with per-segment optimal thresholds (threshold_mode, segment_column stored)
- **F2b**: Load `segment_thresholds.json` in `InferenceStep`, apply per-row thresholds based on segment column, with configurable fallback
- **F3**: Post-split geo-stratified subsampling in `SplitStep` (strategies: `proportional`, `equal`, `capped`)
- **F1**: Post-split unlabeled negatives injection in `SplitStep` with ID dedup against val/test, time-aware filtering for `time_series` splits
- Schema additions to `SPLIT_SCHEMA` and `INFERENCE_SCHEMA` (all optional, `enabled: false` default)
- Unit tests for all features

### Out of Scope
- UI/visualization for segment thresholds (already in HTML report via segmented_metrics)
- ETL-level geo-stratification (applied at split step only)
- Feature engineering changes
- Changes to saved `.pkl` model format
- Integration/E2E tests (separate task)

## Capabilities

### New Capabilities
- `segment-threshold-inference`: Load and apply per-segment thresholds during inference, with fallback to global threshold
- `geo-stratified-sampling`: Post-split geographic stratification of training data with configurable strategies
- `unlabeled-negatives-injection`: Inject external unlabeled records as negative samples into the training split

### Modified Capabilities
- None (no existing specs in `openspec/specs/` — all are new)

## Approach

**Execution order in SplitStep**: split → unlabeled_negatives (F1) → geo_stratify (F3) → save.

**F2a** — Add `_export_segment_thresholds()` to `DefaultEvaluator`. After computing `segmented_metrics`, write a flat JSON mapping `{segment_value: {threshold, threshold_mode, auc, n_samples}}` alongside the existing evaluation report.

**F2b** — Add `segment_thresholds` section to `INFERENCE_SCHEMA`. In `InferenceStep.execute()`, when enabled: load JSON → map each row's segment value to its threshold → apply per-row instead of global. Fallback threshold used for unseen segments.

**F3** — Add `geo_stratify` nested dict to `SPLIT_SCHEMA`. After `train_df` is computed, group by `geo_stratify.column`, apply chosen strategy (`proportional`/`equal`/`capped`), log before/after distribution.

**F1** — Add `unlabeled_negatives` nested dict to `SPLIT_SCHEMA`. After `train_df` is computed, load external file, exclude IDs present in val/test, sample up to configured limit, assign `target=0`, concat to train. For `time_series` splits: filter by date cutoffs per period.

**All features default to `enabled: false`** — backward compatible, no config migration needed.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/energizados/core/steps/split.py` | Modified | Add unlabeled_negatives + geo_stratify post-split logic |
| `src/energizados/core/schemas/schemas.py` | Modified | Add `unlabeled_negatives`, `geo_stratify` to SPLIT_SCHEMA; `segment_thresholds` to INFERENCE_SCHEMA |
| `src/energizados/core/builders/split_builder.py` | Modified | Extract and pass nested config dicts to SplitStep |
| `src/energizados/evaluation/evaluator.py` | Modified | Add `_export_segment_thresholds()` method |
| `src/energizados/inference/default.py` | Modified | Add segment-threshold-aware prediction logic |
| `src/energizados/core/builders/inference_builder.py` | Modified | Pass `segment_thresholds` config to InferenceStep |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| F1: Column mismatch between labeled and unlabeled datasets | Med | Validate column overlap at load time; log missing columns; fill with NaN |
| F1: Data leakage (unlabeled ID in val/test gets target=0) | Med | Dedup unlabeled IDs against val+test ID columns before concat |
| F2b: Segment column missing at inference time | Low | JSON artifact stores `segment_column` name; raise clear error if missing; `fallback_threshold` as safety net |
| F3: Aggressive "equal" strategy drops too much training data | Med | Log before/after row counts per stratum; warn if >50% data loss |
| All: Backward compatibility | Low | All features `enabled: false` by default; schema keys optional |

## Rollback Plan

- All features are gated behind `enabled: false` defaults — removing the config key or leaving disabled reverts behavior
- No changes to `.pkl` model format — existing saved models remain compatible
- If issues arise, delete the new config keys and the pipeline runs identically to pre-change
- `segment_thresholds.json` is a new artifact; removing it has no side effects

## Dependencies

- F2b depends on F2a (inference consumes evaluation's JSON output)
- F1 depends on external unlabeled dataset availability at configured path
- F3 requires a geographic column (e.g., `geo_cluster`) in the dataset

## Success Criteria

- [ ] `DefaultEvaluator` writes `segment_thresholds.json` with per-segment thresholds when evaluation runs
- [ ] `InferenceStep` applies per-segment thresholds when `segment_thresholds.enabled: true`, falls back to global when `false`
- [ ] `SplitStep` balances geographic strata when `geo_stratify.enabled: true`, unchanged when `false`
- [ ] `SplitStep` injects unlabeled negatives when `unlabeled_negatives.enabled: true`, unchanged when `false`
- [ ] All existing tests pass; new unit tests cover each feature
- [ ] `pre-commit run --all-files` passes
- [ ] Existing configs without new keys produce identical results (backward compat)
