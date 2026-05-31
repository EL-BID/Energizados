---
name: version-deliverable
description: "Trigger: entregable de versión, version deliverable, release notes versión, generar entregable, crear entregable. Genera un documento Markdown de entregable por versión que resume experimentos, modelo ganador, resultados, y comparativa con la versión anterior."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- After running `experiment-results` and having `_results.md` already generated
- User says "entregable de versión", "generar entregable", "version deliverable", "release notes versión"
- User wants a version-level document that is readable for mixed audiences (business + technical)

## Prerequisites

- A version directory with completed experiments (at least one `_results.md` present)
- Each experiment must have `evaluation_report.json` in `reports/evaluation/`
- YAML config files for each experiment

## Hard Rules

1. **NEVER assume directory paths.** The user MUST provide the version directory path. Ask if not given.
2. **NEVER assume a previous version exists.** Ask the user which version to compare against. If v0 or no comparison is desired, skip that section.
3. **Always run AFTER `experiment-results`.** If `_results.md` does not exist, tell the user to run that skill first.
4. **Language: Spanish** — all prose in Spanish. Code, variable names, and technical identifiers remain in English.
5. **Two-layer structure**: executive summary first, technical appendix after. Mark sections with `<!-- SECCIÓN EJECUTIVA -->` and `<!-- SECCIÓN TÉCNICA -->`.
6. **Auto-classify experiments**: read all experiments, compute baseline AUC, classify each experiment as "mejoró", "empeoró", or "sin cambio significativo" relative to baseline (< 0.001 AUC diff = sin cambio).

## Input Discovery

1. **Locate version directory**: user-provided path (e.g., `.proyects/celesc/config/v0/` or `output/v0/exp/`)
2. **Locate `_results.md`**: same directory or parent — must exist before proceeding
3. **Read all `evaluation_report.json`**: from each experiment subdirectory
4. **Read YAML configs**: for split info, feature engineering details, and model hyperparams
5. **Locate previous version**: user provides path or confirms no comparison

### Required Data Sources

| Data | Source | Fallback |
|------|--------|----------|
| Metrics per experiment | `evaluation_report.json` | Error if missing |
| Split config (train/val/test periods) | YAML `training.split` | Warn and skip |
| Feature engineering pipeline | YAML `training.feature_engineering` | "No detallado" |
| Model type + hyperparams | YAML `training.models` + JSON `model_info` | Partial from JSON |
| Sampling strategy | YAML `training.models[].sampling` | "No especificado" |
| Winning experiment AUC | `_results.md` "Winning Pipeline" section | Compute from JSON |
| Phase classification | Experiment dir names `fase{N}_exp{M}_*` | Group by phase number |
| Previous version metrics | Previous version's `_results.md` + JSON | Skip section if unavailable |

## Classification Logic

### Experiment Classification (Section 1)

For each experiment with AUC test:

1. **Identify baseline**: first experiment in Phase 1 (fase1_exp1_*)
2. **Compare every experiment against the baseline AUC test**
3. Classify:
   - **Mejoró**: AUC test > baseline + 0.001
   - **Sin cambio significativo**: |AUC test - baseline| <= 0.001
   - **Empeororó**: AUC test < baseline - 0.001
4. **Identify key drivers**: group by phase, report which phase produced the biggest AUC jump vs. previous phase winner

### Phase Winner Tracking

Use the `_results.md` "Decisiones Acumuladas" table if available. Otherwise, compute:
- Group experiments by `fase{N}` phase number
- For each phase, the winner = max AUC test (including the carried-forward baseline)
- Delta = winner AUC - previous phase winner AUC

## Output Format

File: `_entregable_v{N}.md` in the same directory as `_experiments.md`.

See [assets/entregable-template.md](assets/entregable-template.md) for the complete structure.

### Section Order

```
# Entregable — {PROJECT} v{N}

> metadata (date, dataset, total experiments, metric guide)

<!-- SECCIÓN EJECUTIVA -->

## Resumen Ejecutivo (1 página)
### Resultado principal
### Comparativa vs versión anterior (if available)
### Recomendación operativa (2-3 bullets)

<!-- SECCIÓN TÉCNICA -->

## 1. Características del Experimento
### Qué se probó
### Qué resultó
### Qué no resultó
### Mayor driver de performance

## 2. Periodos de Datos
### Split configuration (train/val/test dates, method, sizes)

## 3. Características del Modelo Ganador
### Tipo de modelo y sampling
### Pipeline de feature engineering
### Hiperparámetros
### Features finales utilizadas

## 4. Resultados del Modelo Ganador
### Métricas principales (table: AUC val, AUC test, Precision, Recall, F1, Threshold)
### Matriz de confusión
### Curva de ganancia acumulada
### Calibración (if available)
### Métricas por segmento (if available)

## 5. Comparativa vs Versión Anterior (if previous version provided)
### Tabla comparativa (métricas, features, modelo)
### Delta AUC y análisis

## Anexo: Tabla Completa de Experimentos
### All experiments with all metrics (sortable by phase)
```

## Workflow

```
1. Gather inputs
   ├── Ask user for: version_dir, previous_version_dir (optional), project_name
   ├── Verify _results.md exists
   ├── Read all evaluation_report.json
   └── Read all YAML configs for winning experiment

2. Classify experiments
   ├── Identify baseline (fase1_exp1)
   ├── Classify each: mejoró / empeororó / sin cambio
   ├── Track phase winners and deltas
   └── Identify key driver (highest delta phase)

3. Extract winning experiment details
   ├── From evaluation_report.json: all metrics
   ├── From YAML config: split, feature engineering, model, sampling, evaluation
   └── From model_info: features, model class, params

4. Build comparison (if previous version provided)
   ├── Read previous _results.md for best AUC and config
   ├── Read previous winning evaluation_report.json
   └── Compute deltas

5. Generate _entregable_vN.md
   ├── Executive summary (1 page, plain Spanish)
   ├── Technical sections (detailed, all data)
   └── Full experiment table as appendix

6. Save and report location
```

## Code Examples

### Extract all experiment data

```bash
# Quick overview of all experiments in a version
python .claude/skills/experiment-results/scripts/extract_metrics.py {version_dir}/exp/ --format table

# JSON output for programmatic processing
python .claude/skills/experiment-results/scripts/extract_metrics.py {version_dir}/exp/ --format json
```

### Read YAML config for winning experiment

```python
import yaml
with open("{winning_yaml_path}") as f:
    config = yaml.safe_load(f)
    split = config["train"]["split"]
    fe = config["train"]["feature_engineering"]
    models = config["train"]["models"]
```

## Commands

```bash
# Verify _results.md exists
ls {version_dir}/_results.md

# List all experiment evaluation reports
find {version_dir}/exp -name "evaluation_report.json" | sort

# Extract baseline AUC (fase1_exp1)
python .claude/skills/experiment-results/scripts/extract_metrics.py {version_dir}/exp/ --format json | python3 -c "
import json, sys
data = json.load(sys.stdin)
baseline = [x for x in data if x['phase'] == 1]
if baseline:
    print(f'Baseline AUC: {baseline[0][\"auc\"]:.4f}')
"
```

## Resources

- **Template**: See [assets/entregable-template.md](assets/entregable-template.md) for the complete document structure with placeholders.
- **Metrics extraction**: Use the existing `experiment-results/scripts/extract_metrics.py` script.
- **Business explanations**: Follow the plain-language metric explanations from `experiment-results/assets/business_metrics_template.md`.