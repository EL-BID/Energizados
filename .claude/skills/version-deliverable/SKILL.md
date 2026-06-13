---
name: version-deliverable
description: "Trigger: entregable de versión, version deliverable, release notes versión, generar entregable, crear entregable. Genera un documento Markdown de entregable multi-versión que resume iteraciones, modelo ganador, resultados, comparativa entre versiones, lecciones aprendidas y próximos pasos."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "2.0"
---

## When to Use

- After running `experiment-results` for each version and having `_results.md` already generated
- User says "entregable de versión", "generar entregable", "version deliverable", "release notes versión"
- User wants a multi-version deliverable document readable for mixed audiences (business + technical)

## Prerequisites

- One or more version directories with completed experiments (at least one `_results.md` per version)
- Each experiment must have `evaluation_report.json` in `reports/evaluation/`
- YAML config files for each version's winning experiment

## Hard Rules

1. **NEVER assume directory paths.** The user MUST provide version directory paths. Ask if not given.
2. **NEVER assume Empresa/Proyecto.** Ask the user for company and project names. These appear in the header.
3. **Always run AFTER `experiment-results`.** If `_results.md` does not exist for a version, tell the user to run that skill first.
4. **Language: Spanish** — all prose in Spanish. Code, variable names, and technical identifiers remain in English.
5. **Multi-version structure**: The deliverable covers ALL iterations (v0, v1, ..., vN) in a single document. Each version gets its own Iteración section.
6. **Auto-classify experiments**: read all experiments, compute baseline AUC, classify each experiment as "mejoró", "empeoró", or "sin cambio significativo" relative to baseline (< 0.001 AUC diff = sin cambio).
7. **Three-layer reading**: Executive layers (Objetivo → Iteraciones → Comparativa → Eficiencia Operativa → Lecciones) → Technical appendices (A, B, C, D) → Glossary.
8. **Objetivo section**: bullet-point list (3-5 items). Derive from experiment phases and user intent.
9. **Iteración sections**: each version gets a self-contained section with: summary, metrics table, phases table, key findings. Detailed phase-by-phase analysis goes to the corresponding appendix.
10. **Comparativa section**: always present when 2+ versions exist. Include: metrics evolution table, changes table, delta analysis (what drove the change, what didn't help, what got worse).
11. **Eficiencia Operativa section**: standalone section with cross-version cumulative gains comparison table, practical scenario (concrete numbers: TOP N%, inspections, frauds found, false positives, vs random), and operational recommendation.
12. **Lecciones aprendidas**: bullet points of key learnings across all versions.
13. **Próximos pasos**: actionable next steps.
14. **Apéndices etiquetados (A, B, C, D)**: one per version for detailed analysis, plus model configuration comparison and complete experiment tables.
15. **Glosario**: 4 categories — Términos generales, Modelos y algoritmos, Transformadores / Features, Abreviaturas y siglas. Include ALL technical terms used in the document.


## Input Discovery

1. **Ask user for**: company name, project name, list of version directories (ordered: v0 first), related documents URLs
2. **Locate `_results.md`** for each version directory
3. **Read all `evaluation_report.json`** from each version's experiment subdirectories
4. **Read YAML configs**: for split info, feature engineering details, and model hyperparams per version
5. **Locate previous version**: always the version before in the user-provided list

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
| Company name | User input | "—"
| Project name | User input | "Energizados" |
| Related documents | User input (URLs) | Skip section |
| Repository URL | User input | "—"

## Classification Logic

### Experiment Classification

For each experiment with AUC test:

1. **Identify baseline**: first experiment in Phase 1 (fase1_exp1_*)
2. **Compare every experiment against the baseline AUC test**
3. Classify:
   - **Mejoró**: AUC test > baseline + 0.001
   - **Sin cambio significativo**: |AUC test - baseline| <= 0.001
   - **Empeoró**: AUC test < baseline - 0.001
4. **Identify key drivers**: group by phase, report which phase produced the biggest AUC jump vs. previous phase winner

### Phase Winner Tracking

Use the `_results.md` "Decisiones Acumuladas" table if available. Otherwise, compute:
- Group experiments by `fase{N}` phase number
- For each phase, the winner = max AUC test (including the carried-forward baseline)
- Delta = winner AUC - previous phase winner AUC

## Output Format

File: `_entregable_v{N}.md` in the LATEST version directory (or user-specified location).
Where N = latest version number.

See [assets/entregable-template.md](assets/entregable-template.md) for the complete structure.

### Section Order

```
# Entregable {N}
> date

# Empresa
# Proyecto
# Objetivo

# Iteraciones
## Iteración v0 — {TITLE}
### Métricas principales
### Fases y experimentos ejecutados
### Hallazgos principales

## Iteración v1 — {TITLE}
### Métricas principales
### Fases y experimentos ejecutados
### El hallazgo central (if applicable)
### Modelos recomendados para producción
### Métricas por segmento (if available)
... (repeat for each version)

# Comparativa v0 vs v1 (vs vN if applicable)
## Evolución de métricas
## Cambios principales entre versiones
## Análisis del delta

# Eficiencia Operativa
## Curva de ganancia acumulada — Comparativa
## Escenario práctico
## Recomendación operativa

# Período de datos utilizados
## v0
## v1
... (per version)

# Lecciones aprendidas
# Documentos relacionados
# Repositorio de fuentes
# Próximos pasos

# APÉNDICE TÉCNICO A — Detalle de Experimentos v0
## A.1 Análisis fase por fase (v0)
### Fase 1 — {name} ({count} experimentos)
... (per phase: hypothesis, results table, conclusions)
## A.2 Matriz de confusión v0
## A.3 Calibración v0
## A.4 Features finales v0

# APÉNDICE TÉCNICO B — Detalle de Experimentos v1
## B.1 Análisis fase por fase (v1)
... (per phase)
## B.2 Matriz de confusión v1
## B.3 Calibración v1
## B.4 Gap AUC test/val — Análisis detallado (if applicable)
## B.5 Features finales v1
... (repeat APPENDIX per version: C, D, E...)

# APÉNDICE TÉCNICO {X} — Configuración de los Modelos
## {X}.1 Pipeline de feature engineering v0 — Preprocessing por columna
## {X}.2 Pipeline de feature engineering v1 — Preprocessing por columna
... (per version)
## {X}.N-1 Hiperparámetros v0
## {X}.N Hiperparámetros v1
... (per version)
## {X}.N+1 Diferencias clave en hiperparámetros v0 vs v1

# APÉNDICE TÉCNICO {Y} — Tablas Completas de Experimentos
## {Y}.1 Tabla completa v0 ({count} experimentos)
## {Y}.2 Tabla completa v1 ({count} experimentos)
... (per version)

# Glosario
## Términos generales
## Modelos y algoritmos
## Transformadores / Features
## Abreviaturas y siglas
```

## Workflow

```
1. Gather inputs
   ├── Ask user for: company_name, project_name, version_dirs[] (ordered), related_docs URLs, repo_url
   ├── Verify _results.md exists for each version
   ├── Read all evaluation_report.json for each version
   └── Read all YAML configs for each version's winning experiment

2. Classify experiments (per version)
   ├── Identify baseline (fase1_exp1)
   ├── Classify each: mejoró / empeoró / sin cambio
   ├── Track phase winners and deltas
   └── Identify key driver per version (highest delta phase)

3. Extract winning experiment details (per version)
   ├── From evaluation_report.json: all metrics
   ├── From YAML config: split, feature engineering, model, sampling, evaluation
   └── From model_info: features, model class, params

4. Build cross-version comparison
   ├── Metrics evolution table (AUC, precision, recall, F1, features count)
   ├── Changes table (model, features, sampling, FE, gap test/val)
   ├── Delta analysis (what drove the change, what didn't, what got worse)
   └── Cumulative gains comparison table

5. Build efficiency section
   ├── Cross-version cumulative gains table (% inspected → % frauds detected)
   ├── Practical scenario (TOP N% → inspections, frauds found, FP, vs random)
   └── Operational recommendation (threshold, retraining, projection caveat)

6. Build appendices
   ├── Per-version appendix (A=v0, B=v1, etc.):
   │   ├── Phase-by-phase analysis (hypothesis → table → conclusions per phase)
   │   ├── Confusion matrix
   │   ├── Calibration
   │   ├── Gap analysis (if applicable)
   │   └── Features finales
   ├── Configuration appendix: preprocessing columns, hyperparams, differences table
   └── Complete experiment tables per version

7. Build glossary
   ├── Scan entire document for technical terms
   ├── Group by 4 categories: Términos generales, Modelos y algoritmos, Transformadores/Features, Abreviaturas y siglas
   └── Keep definitions to 1-2 sentences, plain Spanish

8. Generate and save
   ├── Save as _entregable_v{N}.md
   └── Report location to user
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
