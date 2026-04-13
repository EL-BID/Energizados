---
name: experiment-results
description: >
  Genera un reporte completo de resultados de experimentos a partir de los outputs
  del pipeline de entrenamiento. Incluye tabla comparativa por fases, analisis de
  evolucion AUC, insights tecnicos, proximos pasos, y una seccion explicativa
  para negocio con simulador operativo.
  Trigger: Cuando el usuario dice "genera resultados", "experiment results",
  "crea el reporte de experimentos", "resultados de experimentos",
  "analysis de experimentos", "genera _results.md".
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Despues de ejecutar una serie de experimentos (energizados run train)
- Cuando el usuario pide un reporte o tabla de resultados
- Para cerrar un ciclo de experimentacion con analisis y recomendaciones

## Prerequisites

- Directorio de experimentos con outputs generados por el pipeline
- Cada experimento debe tener `reports/evaluation/evaluation_report.json`
- Un archivo `_experiments.md` con el roadmap de fases (opcional pero recomendado)

## Critical Patterns

### Input Discovery

1. **Localizar el directorio de experimentos**: Buscar en `{project}/.proyects/{name}/output/{version}/exp/`
2. **Localizar el roadmap**: Buscar `_experiments.md` en el mismo nivel de config
3. **Leer TODOS los `evaluation_report.json`** de cada subdirectorio de experimento

### Metricas a Extraer (de cada JSON)

```
metrics.auc            → AUC test
metrics.auc_val        → AUC validation
metrics.precision      → Precision @ threshold
metrics.recall         → Recall @ threshold
metrics.f1             → F1 @ threshold
metrics.threshold      → Threshold usado
metrics.auc_diff       → AUC val - AUC test (overfit indicator)
metrics.confusion_matrix → TP, FP, FN, TN
metrics.cumulative_gains → Deciles y cumulative gain (para simulador)
model_info.model_class → Tipo de modelo
model_info.inner_model → Modelo interno
calibration            → Info de calibracion (si existe)
```

### Workflow de Generacion

```
1. Descubrir experimentos
   ├── ls del directorio exp/
   ├── Para cada subdir, leer evaluation_report.json
   └── Extraer metricas clave

2. Agrupar por fase (usar naming convention: faseX_expN_*)
   ├── Parsear nombre del directorio
   └── Agrupar en tablas por fase

3. Identificar mejores
   ├── Mejor AUC test overall
   ├── Mejor AUC test por fase
   ├── Mejor F1
   └── Mejor modelo calibrado

4. Generar analisis
   ├── Evolucion del AUC (grafico ASCII)
   ├── Que funciono / que no / sorpresas
   ├── Proximos pasos priorizados
   └── Pipeline ganador

5. Generar seccion de negocio
   ├── Explicar metricas en lenguaje no-tecnico
   ├── Simulador de impacto operativo
   └── Recomendaciones accionables
```

### Formato del Output

El archivo de salida es `_results.md` en el mismo directorio que `_experiments.md`.

Estructura:
```
# Resultados de Experimentos — {PROJECT} {VERSION}
> metadata (fecha, metrica guia, dataset)

## Resumen Ejecutivo (tabla con mejores metricas)

## Tabla de Resultados Completa (por fase)
### FASE 1 — {nombre}
### FASE 2 — {nombre}
...

## Evolucion del AUC Test por Fase (grafico ASCII)

## Insights Principales
### Que funciono
### Que NO funciono
### Sorpresas

## Notas Tecnicas

## Proximos Pasos (tabla priorizada)

## Pipeline Ganador (YAML)

## Para Negocio: Que significan estos numeros
### Que mide el modelo (explicacion no-tecnica)
### Simulador de impacto operativo
### Recomendaciones

## Experimentos Faltantes
```

### Seccion de Negocio — Guia

La seccion de negocio DEBE incluir:

1. **Explicacion de metricas** sin jerga tecnica:
   - AUC → "de cada 100 pares (fraude/no-fraude), el modelo ranking correctamente X veces"
   - Precision → "de cada 100 que el modelo marca como fraude, X realmente lo son"
   - Recall → "de cada 100 fraudes reales, el modelo detecta X"
   - F1 → balance entre los dos
   - Cumulative Gains → "inspeccionando el X% de clientes con mayor riesgo, encontramos el Y% de los fraudes"

2. **Simulador operativo** usando cumulative_gains del mejor modelo:
   - Tabla: "Si inspeccionamos top 10%/20%/30%... de clientes, cuantos fraudes encontramos vs aleatorio"
   - Usar los deciles del evaluation_report.json
   - Estimar: inspecciones necesarias, fraudes detectados, falsos positivos

3. **Recomendaciones accionables**:
   - Threshold operativo sugerido
   - Estimacion de recursos necesarios
   - Riesgo de falsos positivos/negativos

## Code Examples

### Extraer metricas de todos los experimentos

```bash
for f in {exp_dir}/*/reports/evaluation/evaluation_report.json; do
  dir=$(basename $(dirname $(dirname $(dirname "$f"))))
  python3 -c "
import json
d = json.load(open('$f'))
m = d['metrics']
mi = d.get('model_info', {})
cal = d.get('calibration', {})
print(f'$dir|{mi.get(\"model_class\",\"\")}|{m[\"auc\"]:.4f}|{m.get(\"auc_val\",\"NaN\"):.4f}|{m[\"precision\"]:.4f}|{m[\"recall\"]:.4f}|{m[\"f1\"]:.4f}|{m[\"threshold\"]}|{m.get(\"auc_diff\",\"NaN\"):.4f}')
"
done
```

### Extraer cumulative gains para simulador de negocio

```bash
python3 -c "
import json
d = json.load(open('{best_exp}/reports/evaluation/evaluation_report.json'))
gains = d['metrics']['cumulative_gains']
for pop, gain in zip(gains['cumulative_population'], gains['cumulative_gain']):
    pct = int(pop * 100)
    fraud_pct = gain * 100
    print(f'Top {pct}% inspecciones → {fraud_pct:.1f}% fraudes detectados')
"
```

## Commands

```bash
# Listar experimentos disponibles
ls -1 {exp_dir}/

# Ver metricas rapidas de todos los experimentos
for f in {exp_dir}/*/reports/evaluation/evaluation_report.json; do
  dir=$(basename $(dirname $(dirname $(dirname "$f"))))
  python3 -c "import json; d=json.load(open('$f')); m=d['metrics']; print(f'{\"$dir\"}: AUC={m[\"auc\"]:.4f} F1={m[\"f1\"]:.4f}')"
done
```

## Resources

- **Templates**: See [assets/](assets/) for _results.md template structure
- **Scripts**: See [scripts/](scripts/) for metric extraction helpers
