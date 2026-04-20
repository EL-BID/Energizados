---
name: new-experiments
description: >
  Design and generate a complete set of ML training experiments for an Energizados project.
  Creates _experiments.md roadmap + all YAML config files following the phased experiment pattern
  (Baselines → Sampling → Feature Engineering → Encoding → Selection → Tuning → Calibration → Ensemble).
  Trigger: When the user says "new experiments", "create experiments", "nuevos experimentos",
  "crear experimentos", "experiment design", "experiment roadmap", "set up experiments".
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- User wants to create a set of experiments for a NEW version of an existing project (v0, v1, etc.)
- User says "new experiments", "nuevos experimentos", "crear experimentos"
- User wants an experiment roadmap with YAML configs following the phased pattern
- User has a processed dataset and wants to systematically explore model configurations

## Critical Patterns

### Directory Structure

```
.proyects/{project}/config/{version}/
├── _experiments.md                    # Roadmap + results table (DO NOT skip this)
├── etl.yaml                           # Already exists (DO NOT regenerate)
├── eda.yaml                           # Already exists (DO NOT regenerate)
├── infer.yaml                         # Already exists (DO NOT regenerate)
├── fase1_exp1_{name}.yaml             # One YAML per experiment
├── fase1_exp2_{name}.yaml
├── ...
└── faseN_expM_{name}.yaml
```

### Naming Convention

- Files: `fase{N}_exp{M}_{kebab-name}.yaml` — numbering restarts per phase
- YAML `description` field: hypothesis + what changes vs previous phase
- YAML comments: 4-line header (phase, hypothesis, run command, dependencies)
- Run names: `fase{N}-exp{M}-{kebab-name}`

### YAML Header Template

```yaml
# =============================================================================
# FASE {N} — exp{M}: {title}
# Hipótesis: {one-line hypothesis}
# Ejecución: energizados run train -n fase{N}-exp{M}-{kebab-name}
# Dependencia: {what this depends on from previous phase}
# =============================================================================
```

### Available Global Transformers (framework constraint)

**ONLY these transformers can be used under `global_transformers:` in preprocessing config:**

| Transformer | Purpose | Notes |
|-------------|---------|-------|
| `clip_outliers` | Clip extreme consumption values | Run FIRST — before if_score |
| `if_score` | Isolation Forest anomaly score | Appends `if_score` column |
| `extra_vars` | Statistical features per time window | Use with num_periodos: 3, 6, 12 |
| `consumption_patterns` | Domain fraud features | caídas abruptas, zero_ratio, etc. |
| `tsfel_vars` | Advanced temporal/frequency features | Slow — test last in kitchen-sink |
| `cast_dtype` | Column dtype conversion | Per-column use only |
| `cardinality_reducer` | Group infrequent categories | Per-column use only |
| `to_dummy` | One-hot encoding | Per-column use only |
| `target_encoding` | Target probability encoding | Per-column use only |
| `ordinal_encoding` | Ordinal integer encoding | Per-column use only |
| `minmax_scaler_row` | Row-wise MinMax scaling | Per-column use only |

**`geo_features` is NOT a global transformer** — it was moved to ETL.

### Class Imbalance per Model Type

Each model handles class imbalance differently — **do NOT use `class_weight: "balanced"` for CatBoost**:

| Model | Correct YAML |
|-------|-------------|
| `lightgbm` | `class_weight: "balanced"` at model level |
| `catboost` | `auto_class_weights: "Balanced"` inside `hyperparams` |
| `xgboost` | `class_weight: <float>` (scale_pos_weight) at model level |

`class_weight: "balanced"` is a scikit-learn convention that only LightGBM understands natively.
CatBoost receives it as `class_weights` (a list/None), so `"balanced"` causes a parse error.
Use `auto_class_weights: "Balanced"` in `hyperparams` for CatBoost — it's the native CatBoost param.
To use geographic features: add `GeoFeaturesETL` to `etl.yaml` FIRST, then the output dataset
will already contain `geo_cluster`, `geo_estado`, etc. as regular columns.
Never reference `geo_features` inside `global_transformers:`.

### Key YAML Sections That Change Per Phase

| Phase | What Changes | Fixed Sections |
|-------|-------------|----------------|
| 1 (Baselines) | model type, encoding strategy | split, sampling=none, FE=none |
| 2 (Sampling) | sampling.method, class_weight | model from F1 winner, FE=none |
| 3 (FE) | global_transformers | model + sampling from F2 winner |
| 4 (Encoding) | columns preprocessing | model + sampling + FE from F3 winner |
| 5 (Selection) | feature_selection steps | full pipeline from F4 winner |
| 6 (Tuning) | model type + hyperparam_search | full pipeline from F5 winner |
| 7 (Calibration) | evaluation.calibration | TOP model from F6 |
| 8 (Ensemble) | models list + ensemble section | TOP models from F6 |

### What Carries Forward

Each phase builds on the **best configuration** from the previous phase. Apply this protocol to every phase and record the winner in the "Decisiones Acumuladas" table.

**Standard Decision Protocol (apply to every phase)**:

1. **Run**: execute experiments as specified (parallel when independent, sequential when dependent).
2. **Baseline**: compare each experiment vs. the **winner of the previous phase** on **AUC test** — not vs. other experiments in the same phase.
3. **Winner**: experiment with highest AUC test **including the baseline**. If no experiment beats the baseline → carry the **baseline forward unchanged** (never force a change).
4. **Tiebreaker** (AUC difference < 0.001):
   - Phases 1–5: prefer **fewer features / simpler model** (less overfitting risk).
   - Tuning phase: prefer **manual/explicit regularization** over search-tuned results.
   - Calibration/Ensemble: prefer best **F1** or business metric (Recall when cost of FN >> FP).
5. **Record**: write winner + rationale in "Decisiones Acumuladas" — all subsequent phases inherit this config exactly.

**Why AUC test and not val?**
Val is used for early stopping and hyperparameter tuning — it already informed training decisions, so selecting by val would reward models that overfit to val, not models that generalize. Test is the only set the model never saw.

**Selection bias caveat**: When comparing many experiments on the same test set, the winner may have won by chance (the more experiments, the higher the risk). Two mitigations:
- The tiebreaker threshold (< 0.001) treats small differences as noise — prefer simpler.
- If the dataset is large enough, reserve a **final holdout** (e.g. last 3–6 months) that is NEVER used until the final model of the last phase. All phase-by-phase selection happens on val/test; the holdout gives an unbiased estimate of real-world performance at the end only.

### Path Conventions

All YAMLs in a version share:
- `input_path`: points to the processed dataset from ETL
- `output_base_dir`: `"output/{version}/exp/"`
- `splits_dir`: `"output/{version}/exp/temp/splits/"`
- `output_parquet` (preprocessing): `"output/{version}/exp/temp/prep/fase{N}_exp{M}_prep.parquet"`

## Templates

### Full (8 phases, ~30-35 experiments)

Best for: production projects requiring systematic optimization.

Phases: Baselines → Sampling → Feature Engineering → Encoding → Selection → Model Tuning → Calibration → Ensemble

See [assets/experiment-template-full.md](assets/experiment-template-full.md) for detailed phase/experiment breakdown.

### Standard (4-5 phases, ~12-15 experiments)

Best for: quick iterations when some decisions are already known.

Phases: Baselines → Feature Engineering → Model Tuning → Ensemble (+ optional Sampling)

See [assets/experiment-template-standard.md](assets/experiment-template-standard.md).

### Quick (3 phases, ~6-8 experiments)

Best for: rapid prototyping, proof of concept.

Phases: Baselines → Feature Engineering → Model Tuning

See [assets/experiment-template-quick.md](assets/experiment-template-quick.md).

## Workflow

### Step 1: Gather Project Context

Ask the user for (or read from existing files):

| Question | Source | Why |
|----------|--------|-----|
| Project name | `.proyects/` directory list | Determines output path |
| Version | Existing versions or user input | e.g. v0, v1 |
| Processed dataset path | `etl.yaml` output or user | `input_path` in all YAMLs |
| Target column | User or dataset inspection | `target_column` |
| Categorical columns + types | Dataset inspection or user | `columns` preprocessing section |
| Imbalance ratio | Dataset inspection | Determines sampling needs |
| Split config | User or existing train.yaml | `split` section |
| Metric guide | User (default: AUC) | North star metric |
| Template choice | User | full / standard / quick |

### Step 2: Generate _experiments.md

Create the roadmap file with:
1. Header (objective, metric, dataset stats, date, naming convention)
2. Mermaid dependency diagram
3. Execution rules
4. "Decisiones Acumuladas" table (empty, to fill as experiments run)
5. One section per phase with experiment table
6. Empty results table (all columns, no values)
7. Missing experiments / opportunities section
8. Execution commands block

### Step 3: Generate All YAML Files

For each experiment in the roadmap:
1. Start from the YAML skeleton (see [assets/yaml-skeleton.yaml](assets/yaml-skeleton.yaml))
2. Set the 4-line header comment
3. Fill `description` with hypothesis
4. Copy shared sections (input_path, output_base_dir, split, evaluation)
5. Vary only what the phase requires (see table above)
6. Each experiment gets its own `output_parquet` path

### Step 4: Verify Consistency

Before finishing, verify:
- All filenames match `fase{N}_exp{M}_{name}.yaml` convention
- All `input_path` values point to the same dataset
- All `split` sections are identical within a phase
- Dependencies in mermaid match actual phase progression
- No duplicate experiment names
- Run commands match actual filenames
- **No `geo_features` under `global_transformers`** — it's ETL-only (`GeoFeaturesETL`)
- All `global_transformers` entries are in the Available Transformers table above

## Code Examples

### Reading Project Context from Dataset

```python
import pandas as pd

df = pd.read_parquet("data/processed/v0/dataset.parquet")

# Get imbalance ratio
imbalance = df["target"].value_counts(normalize=True)
print(f"Imbalance: {imbalance.to_dict()}")

# Get categorical columns
cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
print(f"Categorical: {cat_cols}")

# Get consumption columns (ending in periods_suffix)
consumption_cols = [c for c in df.columns if c.endswith("_anterior")]
print(f"Consumption periods: {len(consumption_cols)}")
```

### Generating a YAML from Template

When generating YAMLs, follow this pattern:
1. Start with the 4-line comment header
2. Use YAML anchors for repeated values (`&period_suffix`)
3. Keep `description` as multiline string with hypothesis
4. Vary ONLY the phase-specific sections
5. All other sections copy verbatim from the base config

## Commands

```bash
# Run a single experiment
energizados run train -n fase{N}-exp{M}-{name}

# Run with verbose output
energizados run train -n fase{N}-exp{M}-{name} -v

# Validate before running
energizados validate train

# Run all experiments in a phase (parallel example)
energizados run train -n fase1-exp1-lgbm-vanilla -v &
energizados run train -n fase1-exp2-catboost-vanilla -v &
wait
```

## Resources

- **Full template**: See [assets/experiment-template-full.md](assets/experiment-template-full.md) for 8-phase breakdown
- **Standard template**: See [assets/experiment-template-standard.md](assets/experiment-template-standard.md) for 4-5 phases
- **Quick template**: See [assets/experiment-template-quick.md](assets/experiment-template-quick.md) for 3 phases
- **YAML skeleton**: See [assets/yaml-skeleton.yaml](assets/yaml-skeleton.yaml) for base config structure
- **Reference experiment set**: `.proyects/celesc/config/v0/` — complete working example
