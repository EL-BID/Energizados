# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| new experiments, nuevos experimentos, crear experimentos | new-experiments | /home/vvv/Develop/bid/energizados/.claude/skills/new-experiments/SKILL.md |
| generate results, experiment results, create experiment report | experiment-results | /home/vvv/Develop/bid/energizados/.claude/skills/experiment-results/SKILL.md |
| run experiment, kick off pipeline | run-experiment | /home/vvv/Develop/bid/energizados/.claude/skills/run-experiment/SKILL.md |
| new ETL, scaffold ETL | new-etl | /home/vvv/Develop/bid/energizados/.claude/skills/new-etl/SKILL.md |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### new-experiments
- Generate experiment roadmap (_experiments.md) + YAML configs following phased pattern
- Naming: fase{N}_exp{M}_{kebab-name}.yaml with 4-line header comments
- Phases: Baselines → Sampling → Feature Engineering → Encoding → Selection → Tuning → Calibration → Ensemble
- Winner selection by AUC test (not val), tiebreaker prefers simpler model
- geo_features is ETL-only (GeoFeaturesETL), never under global_transformers
- CatBoost uses auto_class_weights: "Balanced" in hyperparams (not class_weight)
- All YAMLs share same input_path, output_base_dir: "output/{version}/exp/"

### experiment-results
- Generate _results.md + _slides_negocio.md from evaluation_report.json files
- Extract: AUC test/val, Precision, Recall, F1, threshold, model_info, calibration
- Business section: explain metrics in plain language, operational impact simulator
- Slides: 10-12 slides max, neutral professional tone, no colloquialisms
- FAQ slide addressing "why low precision" and "wasted inspections"
- Cumulative gains table for top 10/20/30% inspection scenarios

### run-experiment
- Validate first: energizados validate etl,train — fail fast
- Run ETL: energizados run etl, then training: energizados run train -n {name}
- Surface metrics from evaluation_report.json (AUC, Precision, Recall, F1)
- Show threshold used, model type, path to HTML report

### new-etl
- Gather: name, mode (concat/merge/incremental), inputs, output, depends_on
- Validate: snake_case names, merge needs ≥2 inputs + merge_config, incremental needs incremental_key
- Output: directory for incremental, .parquet file for concat/merge
- State file for incremental mode should be in .cache/ (gitignored)

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| AGENTS.md | /home/vvv/Develop/bid/energizados/AGENTS.md | Index file — references all project conventions |
| CLAUDE.md | /home/vvv/Develop/bid/energizados/CLAUDE.md | Project overview and development commands |

Read the convention files listed above for project-specific patterns and rules.
