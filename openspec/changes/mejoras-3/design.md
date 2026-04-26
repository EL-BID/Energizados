# Design: mejoras-3 — Threshold by Segment, Geo-Stratified Sampling, Unlabeled Negatives

## Technical Approach

Implement three production-hardening features as post-split transformations in `SplitStep` and threshold-aware prediction in `InferenceStep`:

1. **F1 (unlabeled_negatives)**: Inject external unlabeled records as `target=0` samples into train split only, with ID deduplication against val/test and time-aware filtering for time_series splits.

2. **F2a (segment_thresholds export)**: Extend `DefaultEvaluator` to export per-segment optimal thresholds as JSON artifacts alongside evaluation reports.

3. **F2b (segment_thresholds inference)**: Extend `InferenceStep` to load segment thresholds JSON and apply per-row thresholds based on segment column values.

4. **F3 (geo_stratify)**: Post-split geographic stratification of train data using proportional, equal, or capped sampling strategies.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution order | split → F1 → F3 → save | Unlabeled injection before geo-stratify allows stratification to balance both labeled and injected samples. Geo-stratify always last before save to ensure final train distribution is controlled. |
| Config nesting | Nested dicts under split/inference | Keeps related config together; matches existing pattern (e.g., `split.method`, `segmented_evaluation.enabled`). |
| Default values | All `enabled: false` | Zero breaking changes; existing configs work without modification. |
| Threshold JSON format | Flat structure with metadata | Easy to inspect, diff, and version control; includes segment_column name for validation at inference time. |
| Geo-stratify strategies | proportional, equal, capped | Covers common production needs: reduce overrepresentation (proportional), force balance (equal), cap outliers (capped). |
| Missing segment handling | fallback_threshold → global_threshold | Allows graceful degradation when new segments appear at inference time. |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        SplitStep.execute()                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Load dataset                                                │
│        │                                                         │
│        ▼                                                         │
│  2. Split by method (stratified/random/time_series/group_based) │
│        │                                                         │
│        ├──► train_df                                             │
│        ├──► val_df                                               │
│        └──► test_df                                              │
│               │                                                  │
│               ▼                                                  │
│  3. F1: _inject_unlabeled_negatives()                           │
│        │  (if unlabeled_negatives.enabled)                      │
│        │  • Load external parquet                               │
│        │  • Filter by date (time_series only)                   │
│        │  • Exclude IDs in val/test                             │
│        │  • Sample up to max_per_cutoff                         │
│        │  • Assign target=0, fill missing columns with NaN      │
│        │  • Concatenate to train_df                             │
│        ▼                                                         │
│  4. F3: _apply_geo_stratify()                                   │
│        │  (if geo_stratify.enabled)                             │
│        │  • Group train_df by geo_stratify.column               │
│        │  • Apply strategy (proportional/equal/capped)          │
│        │  • Log before/after counts                             │
│        ▼                                                         │
│  5. Save splits + metadata                                      │
│        │                                                         │
│        └──► Context with train_path, val_path, test_path        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    DefaultEvaluator.execute()                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ... existing evaluation logic ...                              │
│        │                                                         │
│        ├──► Compute segmented_metrics                           │
│        │                                                         │
│        ▼                                                         │
│  F2a: _export_segment_thresholds()                              │
│        │  (if segmented_evaluation.enabled)                     │
│        │  • Build JSON per segment column                       │
│        │  • Write segment_thresholds_{column}.json              │
│        ▼                                                         │
│  Return context                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     InferenceStep.execute()                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ... existing inference logic ...                               │
│        │                                                         │
│        ├──► Get predictions (probabilities)                     │
│        │                                                         │
│        ▼                                                         │
│  F2b: Apply per-segment thresholds                              │
│        │  (if segment_thresholds.enabled)                       │
│        │  • Load segment_thresholds.json                        │
│        │  • Validate segment_column exists in data               │
│        │  • Map each row's segment value to threshold            │
│        │  • Apply fallback/global for unknown segments           │
│        ▼                                                         │
│  Save predictions                                                │
└─────────────────────────────────────────────────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/energizados/core/steps/split.py` | Modify | Add `_inject_unlabeled_negatives()` and `_apply_geo_stratify()` methods; update `execute()` with new pipeline order |
| `src/energizados/core/schemas/schemas.py` | Modify | Add `unlabeled_negatives` and `geo_stratify` to SPLIT_SCHEMA; add `segment_thresholds` to INFERENCE_SCHEMA |
| `src/energizados/core/builders/split_builder.py` | Modify | Extract and pass new nested config dicts to SplitStep constructor |
| `src/energizados/evaluation/evaluator.py` | Modify | Add `_export_segment_thresholds()` method; call after segmented metrics computation |
| `src/energizados/inference/default.py` | Modify | Add `predict_with_segment_thresholds()` method for per-row threshold application |
| `src/energizados/core/builders/inference_builder.py` | Modify | Add segment threshold loading and per-row threshold application logic in InferenceStep |
| `tests/test_split_step.py` | Modify | Add unit tests for F1 and F3 features |
| `tests/test_evaluator.py` | Create | Add unit tests for F2a segment thresholds export |
| `tests/test_inference_segment_thresholds.py` | Create | Add unit tests for F2b inference with segment thresholds |

## Interfaces / Contracts

### SplitStep Constructor Changes

```python
def __init__(
    self,
    # ... existing params ...
    unlabeled_negatives: Optional[Dict] = None,  # NEW
    geo_stratify: Optional[Dict] = None,         # NEW
    **kwargs,
):
```

### New SplitStep Methods

```python
def _inject_unlabeled_negatives(
    self,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Inject unlabeled negative samples into training data.
    
    Args:
        train_df: Current training DataFrame
        val_df: Validation DataFrame (for ID dedup)
        test_df: Test DataFrame (for ID dedup)
    
    Returns:
        Augmented train_df with injected negatives (target=0)
    """

def _apply_geo_stratify(
    self,
    train_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply geographic stratified sampling to training data.
    
    Args:
        train_df: Current training DataFrame
    
    Returns:
        Subsampled train_df with balanced geographic representation
    """
```

### New DefaultEvaluator Method

```python
def _export_segment_thresholds(
    self,
    segmented_metrics: Dict[str, Dict],  # From metrics_calculator.segment_metrics()
    output_dir: Path,
    global_threshold: float,
) -> List[Path]:
    """
    Export segment thresholds to JSON files.
    
    Args:
        segmented_metrics: Dict mapping segment_name -> segment_results
        output_dir: Directory to write JSON files
        global_threshold: Default threshold from config
    
    Returns:
        List of paths to written JSON files
    """
```

### New InferenceStep Behavior

```python
def _apply_segment_thresholds(
    self,
    probas: np.ndarray,
    data: pd.DataFrame,
    segment_thresholds_config: Dict,
) -> np.ndarray:
    """
    Apply per-segment thresholds to predictions.
    
    Args:
        probas: Probability predictions from model
        data: Original input DataFrame (contains segment column)
        segment_thresholds_config: Config with path, fallback_threshold
    
    Returns:
        Binary predictions using per-segment thresholds
    """
```

### Segment Thresholds JSON Schema

```json
{
  "segment_column": "zona",
  "threshold_mode": "youden",
  "default_threshold": 0.5,
  "segments": {
    "Norte": {
      "threshold": 0.37,
      "threshold_mode": "youden",
      "auc": 0.82,
      "n_samples": 1500
    },
    "Sul": {
      "threshold": 0.63,
      "threshold_mode": "youden",
      "auc": 0.79,
      "n_samples": 1200
    }
  }
}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | F1 unlabeled injection | Mock parquet data, verify ID dedup, date filtering, target assignment, column filling |
| Unit | F1 data leakage prevention | Create overlapping IDs between unlabeled and val/test, verify exclusion |
| Unit | F3 geo-stratify strategies | Create synthetic data with known stratum sizes, verify proportional/equal/capped math |
| Unit | F3 data loss warning | Create scenario where equal strategy drops >50% data, verify WARNING logged |
| Unit | F2a JSON export | Mock segmented_metrics input, verify JSON structure and file written |
| Unit | F2b per-row threshold mapping | Create test data with known segments, verify correct threshold applied per row |
| Unit | F2b fallback handling | Test with unknown segments, verify fallback_threshold used |
| Unit | F2b missing column error | Remove segment column, verify ValueError raised |
| Integration | Full pipeline with F1+F3 | Run SplitStep with both features enabled, verify output shapes and metadata |
| Integration | End-to-end F2a→F2b | Run evaluation, then inference using exported JSON, verify consistent thresholds |
| Regression | Existing splits unchanged | Verify stratified/random/time_series splits produce identical results when F1/F3 disabled |
| Schema | Config validation | Test valid configs pass, invalid configs fail with clear errors |

## Configuration Examples

### Example 1: F1 (unlabeled_negatives) with time_series split

```yaml
train:
  split:
    method: "time_series"
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]
    
    # F1: Inject unlabeled negatives
    unlabeled_negatives:
      enabled: true
      source_path: "data/external/unlabeled_contracts.parquet"
      max_per_cutoff: 1500
      random_state: 42
      date_column: "fecha_inspeccion"  # For time filtering
      id_column: "contract_id"         # For dedup against val/test
```

### Example 2: F3 (geo_stratify) proportional strategy

```yaml
train:
  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    
    # F3: Geo-stratified sampling
    geo_stratify:
      enabled: true
      column: "geo_cluster"
      strategy: "proportional"  # Reduces large strata to median size
      random_state: 42
```

### Example 3: F3 (geo_stratify) capped strategy

```yaml
train:
  split:
    method: "stratified"
    
    geo_stratify:
      enabled: true
      column: "geo_cluster"
      strategy: "capped"
      max_per_stratum: 1000  # Required when strategy=capped
      random_state: 42
```

### Example 4: Combined F1 + F3

```yaml
train:
  split:
    method: "time_series"
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]
    
    # First: inject unlabeled negatives
    unlabeled_negatives:
      enabled: true
      source_path: "data/external/unlabeled.parquet"
      max_per_cutoff: 1000
      date_column: "fecha_inspeccion"
      id_column: "contract_id"
    
    # Then: stratify the combined dataset
    geo_stratify:
      enabled: true
      column: "geo_cluster"
      strategy: "equal"
      random_state: 42
```

### Example 5: F2a (segment thresholds export)

```yaml
train:
  evaluation:
    enabled: true
    threshold: 0.5
    
    # Enable segmented evaluation to trigger threshold export
    segmented_evaluation:
      enabled: true
      by: ["zona", "actividad", "zona+region"]  # Columns to segment by
      threshold_mode: "youden"  # optimal threshold method per segment
      min_samples: 30
```

Output: `segment_thresholds_zona.json`, `segment_thresholds_actividad.json`, `segment_thresholds_zona+region.json`

### Example 6: F2b (segment thresholds inference)

```yaml
infer:
  enabled: true
  input_path: "data/new_contracts.parquet"
  output_path: "output/predictions.csv"
  model_path: "output/train-20250401_1200/models/model.pkl"
  threshold: 0.5  # Global fallback threshold
  
  # F2b: Apply per-segment thresholds
  segment_thresholds:
    enabled: true
    path: "output/train-20250401_1200/reports/evaluation/segment_thresholds_zona.json"
    fallback_threshold: 0.6  # Optional: for unknown segments (null = use global)
```

### Example 7: Backward compatible (no changes)

```yaml
train:
  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1
    # No unlabeled_negatives or geo_stratify keys = disabled

infer:
  enabled: true
  threshold: 0.5
  # No segment_thresholds key = disabled, uses global threshold
```

## Migration / Rollout

**No migration required.** All features default to `enabled: false`. Existing configurations continue to work without modification.

**Rollout steps:**
1. Deploy code changes (features disabled by default)
2. Validate existing pipelines still produce identical results
3. Enable features incrementally per project:
   - Start with F2a (threshold export) — read-only, no behavior change
   - Add F2b (threshold inference) — compare outputs with/without
   - Add F3 (geo_stratify) — monitor data loss warnings
   - Add F1 (unlabeled negatives) — requires external dataset availability

## Open Questions

- [ ] Should F1 support multiple source files (list) or single file only? (Spec says single, but production may need multiple)
- [ ] Should F3 strategies be extensible (plugin architecture) or hardcoded enum? (Starting with hardcoded for simplicity)
- [ ] Should segment thresholds JSON include feature importance per segment? (Deferred to future enhancement)
