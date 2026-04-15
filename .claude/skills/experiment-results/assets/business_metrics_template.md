# Business Metrics Template — For _results.md generation

## Section: Para Negocio: Que significan estos numeros

### Generation Rules

1. Use the BEST model's metrics (highest AUC test)
2. Use cumulative_gains from that model's report
3. Use confusion_matrix for absolute numbers
4. ALL text must be in the project's language (Spanish if input is Spanish)
5. NO technical jargon — write for a manager, not an engineer

### Required Subsections

#### 1. Que hace el modelo (2-3 paragraphs)

Explain:
- The model ranks clients by fraud probability
- It does NOT automatically detect fraud — it PRIORITIZES inspections
- Higher rank = higher risk = inspect first

#### 2. Metricas explicadas

For each metric, provide a "que significa" with a concrete example:

- **AUC {value}**: "De cada 100 veces que comparemos un cliente fraudulento con uno que no lo es, el modelo identificara correctamente al fraudulento en {auc*100:.0f} ocasiones. Un modelo aleatorio acierta 50 veces de 100."
- **Precision {value}** (at threshold): "De cada 100 clientes que el modelo marque como sospechosos, {prec*100:.0f} realmente cometieron fraude. Los otros {100-prec*100:.0f} son falsos alarmas."
- **Recall {value}** (at threshold): "De cada 100 fraudes reales que ocurrieron, el modelo detecta {recall*100:.0f}. Se escapan {100-recall*100:.0f} sin detectar."
- **Threshold**: "El modelo usa un punto de corte de {threshold}. Clientes con probabilidad mayor a {threshold*100:.0f}% se marcan como sospechosos."

#### 3. Simulador de impacto operativo

Generate a table from cumulative_gains:

| % Clientes inspeccionados | % Fraudes detectados | Ventaja vs aleatorio | Inspecciones estimadas* | Fraudes encontrados* |
|---------------------------|---------------------|---------------------|------------------------|---------------------|
| 10%                       | XX%                 | +XX%                | NNN                    | NNN                 |
| 20%                       | XX%                 | +XX%                | NNN                    | NNN                 |
| ...                       | ...                 | ...                 | ...                    | ...                 |

*Estimated using total test set size and fraud rate.

Formula:
- fraudes_en_test = TP + FN from confusion_matrix
- total_test = TP + FP + FN + TN
- fraud_rate = fraudes_en_test / total_test
- For decile N (top N*10%):
  - inspecciones = total_test * N * 0.1
  - fraudes_encontrados = fraudes_en_test * cumulative_gain[N-1]

Add "aleatorio" row for comparison:
- aleatorio: N*10% inspecciones → N*10% de fraudes (linear)

#### 4. Recomendacion operativa

Based on the cost_benefit calibration (if available) or the cumulative gains curve:

- "Inspeccionando el top 20% de clientes (los de mayor riesgo), se detectan ~XX% de los fraudes. Esto es XX veces mejor que inspeccionar al azar."
- Suggest a threshold based on the cost_benefit analysis if available.
- Estimate resource savings: "En vez de inspeccionar 100% de los clientes, con el mismo recurso pueden enfocarse en el 20% de mayor riesgo y capturar XX% de los fraudes."

### Template Variables

When generating, replace:
- `{BEST_AUC}` → best AUC test value
- `{BEST_PREC}` → precision at operational threshold
- `{BEST_RECALL}` → recall at operational threshold
- `{BEST_F1}` → F1 at operational threshold
- `{BEST_THRESHOLD}` → operational threshold
- `{FRAUD_RATE}` → dataset fraud rate (percentage)
- `{TOTAL_TEST}` → total test set size
- `{TOTAL_FRAUDS}` → total frauds in test set
- `{MODEL_NAME}` → model class name
- `{GAINS_TABLE}` → generated cumulative gains table
