# Delta Specs: mejoras-3

Three production-hardening features for the Energizados ML pipeline.

---

## ADDED Requirements

### Requirement: Unlabeled Negatives Injection (F1)

The system MUST inject external unlabeled records as negative samples (`target=0`) into the training split when `split.unlabeled_negatives.enabled` is `true`.

The `SPLIT_SCHEMA` SHALL include a nested `unlabeled_negatives` object with keys: `enabled` (bool, default `false`), `source_path` (string, required when enabled), `max_per_cutoff` (int, default `1500`), `random_state` (int, default `42`), `date_column` (string or null), and `id_column` (string or null).

The system MUST execute injection AFTER the main split produces `train_df` but BEFORE `geo_stratify` and BEFORE saving splits.

For `time_series` splits, when `date_column` is provided, the system SHALL filter unlabeled records by the train period's date range, then sample up to `max_per_cutoff` records per cutoff. When `date_column` is null for time_series, the system MUST log a WARNING and apply no date filtering.

For non-time_series splits, the system SHALL sample up to `max_per_cutoff` records from the entire unlabeled pool in one pass.

The system MUST exclude unlabeled rows whose `id_column` value appears in the val or test splits, preventing data leakage.

The system SHALL assign `target=0` to all injected rows and concatenate them to `train_df`.

The system MUST log the number of rows added and the new fraud rate (positive class rate) in `train_df`.

The system SHOULD fill missing columns in the unlabeled dataset with `NaN` when the unlabeled dataset lacks columns present in the labeled dataset, logging a WARNING for each missing column.

The system MUST raise `FileNotFoundError` when `source_path` does not exist.

#### Scenario: Inject unlabeled negatives into non-time split

- GIVEN `split.unlabeled_negatives.enabled: true` and `split.method: "stratified"`
- AND `source_path` points to a valid parquet file with 5000 rows
- AND `max_per_cutoff: 1500` and `id_column: "contract_id"`
- WHEN the split step executes
- THEN up to 1500 rows are sampled from the unlabeled file (excluding IDs present in val/test)
- AND those rows have `target=0` and are concatenated to `train_df`
- AND the split log reports the count added and new fraud rate

#### Scenario: Inject unlabeled negatives with time-series split

- GIVEN `split.unlabeled_negatives.enabled: true` and `split.method: "time_series"`
- AND `date_column: "fecha_inspeccion"` and `max_per_cutoff: 500`
- WHEN the split step executes
- THEN unlabeled records are filtered to those within `train_period` date range
- AND up to 500 are sampled and concatenated to `train_df` with `target=0`

#### Scenario: Data leakage prevention via ID dedup

- GIVEN `split.unlabeled_negatives.enabled: true` and `id_column: "contract_id"`
- AND some unlabeled rows have `contract_id` values present in `val_df` or `test_df`
- WHEN injection runs
- THEN those rows are excluded before sampling
- AND the log reports how many were excluded

#### Scenario: Missing columns in unlabeled dataset

- GIVEN the unlabeled parquet lacks columns present in the labeled dataset
- WHEN injection runs
- THEN missing columns are filled with `NaN`
- AND a WARNING is logged listing the missing columns

#### Scenario: Source file does not exist

- GIVEN `source_path` points to a non-existent file
- WHEN the split step executes
- THEN a `FileNotFoundError` is raised with a clear message

#### Scenario: Feature disabled (backward compatibility)

- GIVEN `split.unlabeled_negatives.enabled: false` or the key is absent
- WHEN the split step executes
- THEN no unlabeled negatives are injected; behavior is identical to pre-change

---

### Requirement: Segment Thresholds Export (F2a)

The system MUST export a `segment_thresholds.json` file to the evaluation output directory when `segmented_metrics` are computed.

The JSON structure SHALL be:

```json
{
  "segment_column": "<column_name>",
  "threshold_mode": "<global|youden|f1_optimal|recall_target>",
  "default_threshold": 0.5,
  "segments": {
    "<segment_value>": {
      "threshold": 0.37,
      "threshold_mode": "youden",
      "auc": 0.82,
      "n_samples": 1500
    }
  }
}
```

`default_threshold` SHALL be the global threshold from evaluation config.

The system MUST write one JSON file per segment column or combination defined in `segmented_evaluation.by`.

#### Scenario: Export thresholds for a single segment column

- GIVEN evaluation runs with `segmented_evaluation.by: ["zona"]` and `threshold_mode: "youden"`
- WHEN `DefaultEvaluator.execute()` completes segmented metrics computation
- THEN a file `segment_thresholds_zona.json` is written to the evaluation output directory
- AND the file contains `segment_column: "zona"`, `threshold_mode: "youden"`, `default_threshold` equal to the global threshold, and a `segments` dict mapping each zona value to its optimal threshold and metrics

#### Scenario: Export thresholds for combined columns

- GIVEN `segmented_evaluation.by: ["zona+region"]`
- WHEN evaluation completes
- THEN a file `segment_thresholds_zona+region.json` is written
- AND `segment_column` is `"zona+region"` and segment keys are combined values like `"SP|Sudeste"`

#### Scenario: No segmented evaluation configured

- GIVEN `segmented_evaluation` is not configured or `enabled: false`
- WHEN evaluation runs
- THEN no `segment_thresholds.json` files are written

---

### Requirement: Segment Thresholds in Inference (F2b)

The system MUST apply per-segment thresholds during inference when `inference.segment_thresholds.enabled` is `true`.

The `INFERENCE_SCHEMA` SHALL include a nested `segment_thresholds` object with keys: `enabled` (bool, default `false`), `path` (string, required when enabled — path to `segment_thresholds.json`), and `fallback_threshold` (number or null, uses global threshold when null).

When enabled, the system SHALL load the JSON file, look up each row's segment value in the `segments` mapping, and apply the per-row threshold instead of the global threshold.

The system MUST raise a `ValueError` if the segment column referenced in the JSON is missing from the inference data.

For rows whose segment value is not found in the `segments` mapping, the system SHALL apply `fallback_threshold` if provided; otherwise, the global `threshold` from config.

The system MUST log a summary: total rows, rows matched to segment thresholds, rows using fallback, rows using global threshold.

#### Scenario: Apply per-segment thresholds

- GIVEN `inference.segment_thresholds.enabled: true` and `path: "output/train-20250401_1200/reports/evaluation/segment_thresholds_zona.json"`
- WHEN inference runs on data with a `zona` column
- THEN each row's prediction threshold is looked up from the segment mapping by its `zona` value
- AND `prediction` is 1 where `probability >= segment_threshold`, 0 otherwise

#### Scenario: Fallback for unknown segments

- GIVEN a row with `zona = "NEW_REGION"` not present in the JSON's `segments` dict
- AND `fallback_threshold: 0.6`
- WHEN inference runs
- THEN that row uses threshold `0.6` instead of the global threshold

#### Scenario: Fallback null uses global threshold

- GIVEN `fallback_threshold: null` and global `threshold: 0.5`
- AND a row's segment value is not in the JSON
- WHEN inference runs
- THEN that row uses threshold `0.5`

#### Scenario: Missing segment column raises error

- GIVEN the JSON references `segment_column: "zona"` but the inference data has no `zona` column
- WHEN inference runs
- THEN a `ValueError` is raised with a clear message indicating the missing column

#### Scenario: Feature disabled (backward compatibility)

- GIVEN `inference.segment_thresholds.enabled: false` or the key is absent
- WHEN inference runs
- THEN all rows use the global threshold; behavior is identical to pre-change

---

### Requirement: Geo-Stratified Sampling (F3)

The system MUST apply geographic stratified subsampling to `train_df` after the split and after unlabeled negatives injection, when `split.geo_stratify.enabled` is `true`.

The `SPLIT_SCHEMA` SHALL include a nested `geo_stratify` object with keys: `enabled` (bool, default `false`), `column` (string, required when enabled), `strategy` (string, one of `"proportional"`, `"equal"`, `"capped"`), `max_per_stratum` (integer or null, required when `strategy` is `"capped"`), and `random_state` (int, default `42`).

The system SHALL apply geo-stratification ONLY to `train_df`, never to `val_df` or `test_df`.

**Proportional strategy**: The system MUST subsample strata larger than the median stratum size down to the median. Strata at or below the median are left untouched.

**Equal strategy**: The system MUST subsample all strata down to the size of the smallest stratum. The system SHOULD log a WARNING if more than 50% of training data would be discarded.

**Capped strategy**: The system MUST subsample each stratum down to `max_per_stratum`, leaving smaller strata untouched.

The system MUST log before/after row counts per stratum and the overall training set size.

The system SHALL record geo-stratify metadata in the split metadata JSON, including: strategy, column, per-stratum counts before/after, total before/after.

#### Scenario: Proportional strategy reduces overrepresented strata

- GIVEN `geo_stratify.enabled: true`, `column: "geo_cluster"`, `strategy: "proportional"`
- AND `train_df` has strata sizes: `{A: 500, B: 200, C: 100}` (median = 200)
- WHEN geo-stratify runs
- THEN stratum A is reduced to 200 rows, B stays at 200, C stays at 100
- AND total `train_df` goes from 800 to 500

#### Scenario: Equal strategy undersamples to minimum

- GIVEN `strategy: "equal"` and strata sizes `{A: 500, B: 200, C: 100}`
- WHEN geo-stratify runs
- THEN all strata are reduced to 100 rows
- AND total `train_df` goes from 800 to 300

#### Scenario: Equal strategy warns about data loss

- GIVEN `strategy: "equal"` and more than 50% of training rows would be discarded
- WHEN geo-stratify runs
- THEN a WARNING is logged about data loss exceeding 50%

#### Scenario: Capped strategy clips large strata

- GIVEN `strategy: "capped"`, `max_per_stratum: 300`
- AND strata sizes `{A: 500, B: 200, C: 100}`
- WHEN geo-stratify runs
- THEN stratum A is reduced to 300, B stays at 200, C stays at 100
- AND total `train_df` goes from 800 to 600

#### Scenario: Missing geo column raises error

- GIVEN `geo_stratify.enabled: true` and `column: "geo_cluster"`
- AND `train_df` does not contain `geo_cluster`
- WHEN geo-stratify runs
- THEN a `ValueError` is raised indicating the column is missing

#### Scenario: Feature disabled (backward compatibility)

- GIVEN `geo_stratify.enabled: false` or the key is absent
- WHEN the split step executes
- THEN no geo-stratification is applied; behavior is identical to pre-change

---

### Requirement: Schema Additions for SPLIT_SCHEMA

The `SPLIT_SCHEMA` in `schemas.py` MUST add two optional nested objects:

1. `unlabeled_negatives`: object with properties `enabled` (bool, default false), `source_path` (string or null), `max_per_cutoff` (integer), `random_state` (integer), `date_column` (string or null), `id_column` (string or null).

2. `geo_stratify`: object with properties `enabled` (bool, default false), `column` (string or null), `strategy` (string, enum `["proportional", "equal", "capped"]`), `max_per_stratum` (integer or null), `random_state` (integer).

Both nested objects SHALL be optional. When absent, behavior is unchanged.

#### Scenario: Config validation passes with new keys

- GIVEN a `train.yaml` with `split.unlabeled_negatives.enabled: true` and `split.geo_stratify.enabled: true`
- WHEN `energizados validate train` is run
- THEN validation passes without errors

#### Scenario: Config validation passes without new keys

- GIVEN a `train.yaml` without `unlabeled_negatives` or `geo_stratify` keys
- WHEN `energizados validate train` is run
- THEN validation passes and behavior is identical to pre-change

---

### Requirement: Schema Additions for INFERENCE_SCHEMA

The `INFERENCE_SCHEMA` in `schemas.py` MUST add an optional nested object `segment_thresholds` with properties: `enabled` (bool, default false), `path` (string or null), `fallback_threshold` (number or null).

#### Scenario: Inference config validation with segment_thresholds

- GIVEN an `infer.yaml` with `segment_thresholds.enabled: true` and `path: "some/path.json"`
- WHEN `energizados validate infer` is run
- THEN validation passes without errors

---

## MODIFIED Requirements

### Requirement: SplitStep.execute() Processing Order

The `SplitStep.execute()` method SHALL process data in the following order: load dataset → split by method → inject unlabeled negatives (if enabled) → apply geo-stratify (if enabled) → save splits → return context.

(Previously: load dataset → split by method → save splits → return context)

#### Scenario: Full pipeline with all post-split features

- GIVEN `unlabeled_negatives.enabled: true` and `geo_stratify.enabled: true`
- WHEN `SplitStep.execute()` runs
- THEN unlabeled negatives are injected BEFORE geo-stratify is applied
- AND geo-stratify operates on the enlarged `train_df` (including injected rows)

#### Scenario: Split without post-split features (unchanged path)

- GIVEN `unlabeled_negatives` not configured and `geo_stratify` not configured
- WHEN `SplitStep.execute()` runs
- THEN the method produces identical results to the pre-change version

---

### Requirement: DefaultEvaluator.execute() Output Artifacts

The `DefaultEvaluator.execute()` method SHALL write `segment_thresholds_{column}.json` files to the evaluation output directory for each segment definition in `segmented_evaluation.by`, containing per-segment thresholds and metadata.

(Previously: the evaluator only wrote JSON/HTML reports; no standalone threshold JSON was produced)

#### Scenario: Segment thresholds JSON is written alongside evaluation report

- GIVEN `segmented_evaluation.enabled: true` and `segmented_evaluation.by: ["zona"]`
- WHEN `DefaultEvaluator.execute()` completes
- THEN `segment_thresholds_zona.json` exists in the evaluation output directory
- AND the file contains valid JSON with `segment_column`, `threshold_mode`, `default_threshold`, and `segments` keys

---

### Requirement: InferenceStep.execute() Threshold Application

The `InferenceStep.execute()` method SHALL support per-segment threshold application when `segment_thresholds.enabled` is `true`, using per-row threshold lookup from the loaded JSON.

(Previously: inference applied a single global `self.inference.threshold` to all rows)

#### Scenario: Per-segment thresholds produce different predictions than global

- GIVEN `segment_thresholds.enabled: true` and segment `"Norte"` has threshold `0.3` while segment `"Sul"` has `0.7`
- AND the global threshold is `0.5`
- WHEN a row in `"Norte"` has probability `0.4`
- THEN prediction is `1` (0.4 >= 0.3), not `0` (0.4 < 0.5)