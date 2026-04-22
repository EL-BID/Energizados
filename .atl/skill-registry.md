# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When the user says "generate results", "experiment results", "create experiment report", "results report", "experiment analysis", "generate _results.md" | experiment-results | /home/vvv/Develop/bid/energizados/.claude/skills/experiment-results/SKILL.md |
| When the user says "new experiments", "create experiments", "nuevos experimentos", "crear experimentos", "experiment design", "experiment roadmap", "set up experiments" | new-experiments | /home/vvv/Develop/bid/energizados/.claude/skills/new-experiments/SKILL.md |
| When you want to kick off a pipeline run and see results | run-experiment | /home/vvv/Develop/bid/energizados/.claude/skills/run-experiment/SKILL.md |
| When the user says "new etl", "agregar etl", "crear etl" | new-etl | /home/vvv/Develop/bid/energizados/.claude/skills/new-etl/SKILL.md |

## Compact Rules

### experiment-results
- Read evaluation_report.json from each experiment's reports/evaluation/ directory
- Use naming convention phaseX_expN_* to group by phase
- Extract: auc, auc_val, precision, recall, f1, threshold, confusion_matrix, cumulative_gains, model_info
- Best AUC test overall wins; report val for early stopping context
- Generate _results.md (technical) + _slides_negocio.md (business presentation, Spanish)
- Business section: explain AUC as "out of 100 pairs, X correct", use cumulative_gains deciles for operational simulator
- Slides: 10-12 slides, neutral Spanish, slide separator is `---`

### new-experiments
- Output: _experiments.md roadmap + YAML files per experiment in .proyects/{project}/config/{version}/
- Naming: fase{N}_exp{M}_{kebab-name}.yaml
- 4-line YAML header: phase, hypothesis, run command, dependency
- Only these global_transformers: clip_outliers, if_score, extra_vars, consumption_patterns, tsfel_vars, cast_dtype, cardinality_reducer, to_dummy, target_encoding, ordinal_encoding, minmax_scaler_row
- geo_features is NOT a global transformer (it's GeoFeaturesETL in etl.yaml)
- Class imbalance: LightGBM uses class_weight: "balanced", CatBoost uses auto_class_weights: "Balanced" in hyperparams (NOT class_weight)
- Phases: Baselines → Sampling → FE → Encoding → Selection → Tuning → Calibration → Ensemble
- Decision protocol: highest AUC test wins; tiebreaker < 0.001 → prefer simpler; carry winner forward unchanged

### run-experiment
- Always validate first: energizados validate etl,train
- Run ETL then training: energizados run etl && energizados run train
- After run: ls -t output/ | head -1 to find latest, read evaluation_report.json
- Show clean metrics table: AUC, Precision, Recall, F1 for val and test

### new-etl
- Modes: concat (stack vertically), merge (join horizontally), incremental (filter by key column)
- concat/merge: output ends in .parquet; incremental: output is a directory
- Incremental requires: incremental_key (datetime column), state_file, incremental_partition (default "%Y-%m")
- Use @etl_name to reference another ETL's output as input
- Validate with: energizados validate etl

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | /home/vvv/Develop/bid/energizados/AGENTS.md | Index — references full project documentation |