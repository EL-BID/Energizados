# Slides Template — _slides_negocio.md

> This is a reference template for the `_slides_negocio.md` output.
> Replace all `{PLACEHOLDERS}` with values from the best experiment.
> Language should match the project (this example is in Spanish).

---

# Slides para Negocio — {PROJECT} {VERSION}

> **Modelo de detección de fraude eléctrico (non-technical losses)**
> Fecha: {DATE} | Versión: {VERSION}

---

## Slide 1: El Problema

- **Contexto**: {EMPRESA} enfrenta pérdidas no técnicas (fraude / desvío de energía) en su red de distribución.
- **Desafío**: El fraude representa aproximadamente el **{FRAUD_RATE}% de los clientes**, pero identificarlos manualmente consume recursos operativos significativos.
- **Costo de oportunidad**: Cada inspección tiene un costo operativo; cada fraude no detectado implica ingreso no facturado.
- **Objetivo**: Construir un modelo que **rankee** los casos de mayor riesgo para optimizar el despliegue de inspecciones.

---

## Slide 2: Qué Hicimos

- Se ejecutaron **{TOTAL_EXPERIMENTS} experimentos** en {TOTAL_PHASES} fases sistemáticas.
- Se evaluaron distintas estrategias de sampling, ingeniería de features, encoding, selección de variables, tuning de hiperparámetros y ensambles.
- **Split temporal realista**: entrenamiento con datos históricos y evaluación con un mes futuro (simula condiciones de producción).
- Métrica guía: **AUC** (capacidad de rankear correctamente fraudes versus clientes legítimos).

---

## Slide 3: Resultado Principal — Modelo Ganador

| Métrica | Valor | Interpretación |
|---------|-------|----------------|
| **AUC** | **{BEST_AUC}** | De cada 100 pares (fraude vs. no fraude), el modelo ordena correctamente ~{BEST_AUC_PCT}. Supera el azar (50%) y presenta margen de mejora. |
| **Recall** | **{BEST_RECALL}** | De cada 100 fraudes reales, el modelo detecta ~{BEST_RECALL_PCT}. Aproximadamente {BEST_FN_PCT} de cada 100 no son identificados. |
| **Precisión** | **{BEST_PRECISION}** | De cada 100 clientes marcados como sospechosos, ~{BEST_PRECISION_PCT} resultan ser fraudes reales. |
| **F1** | **{BEST_F1}** | Balance entre precisión y recall. El valor refleja el trade-off inherente al desbalance de clases. |

> **Arquitectura del modelo**: {MODEL_DESCRIPTION}.

---

## Slide 4: El Mayor Driver de Performance

- El **salto más significativo de performance** provino de {KEY_DRIVER_DESCRIPTION}.
- **+{AUC_DELTA} AUC** atribuible exclusivamente a {KEY_DRIVER_NAME}: se pasó de un modelo base aceptable a uno competitivo.
- **Conclusión técnica**: En este tipo de problemas, la representación de los datos tiene mayor impacto que la complejidad del algoritmo.

---

## Slide 5: Simulador de Impacto Operativo

> Escenario: **{SIM_TOTAL_CLIENTS} clientes** con ~{SIM_TOTAL_FRAUDS} fraudes reales.

| Estrategia | Inspecciones | Fraudes encontrados | Eficiencia vs. azar |
|------------|--------------|---------------------|---------------------|
| **Sin modelo** (aleatorio) | {SIM_INSPECTIONS} ({SIM_TOP_PCT}%) | ~{SIM_RANDOM_FRAUDS} | 1.0x (línea base) |
| **Con modelo** ({SIM_TOP_PCT}%) | {SIM_INSPECTIONS} ({SIM_TOP_PCT}%) | **~{SIM_MODEL_FRAUDS}** | **{SIM_EFFICIENCY}x** |

- **Ganancia**: **+{SIM_EXTRA_FRAUDS} fraudes detectados** con el **mismo volumen de inspecciones**.
- Equivalente a indicar que el modelo permite **evitar ~{SIM_SAVED_INSPECTIONS} inspecciones** si el objetivo es detectar los mismos ~{SIM_MODEL_FRAUDS} fraudes mediante selección aleatoria.

---

## Slide 6: Curva de Ganancia Acumulada

| Top % de clientes inspeccionados | % de fraudes detectados | Ventaja vs. azar |
|----------------------------------|-------------------------|------------------|
{GAINS_TABLE_ROWS}

> **Punto óptimo sugerido**: inspeccionar el **{SWEET_SPOT_PCT}%** permite capturar {SWEET_SPOT_FRAUD_PCT}% de todos los fraudes.

---

## Slide 7: Recomendaciones Operativas

1. **Utilizar threshold = {THRESHOLD}** (definido por análisis costo-beneficio: no detectar un fraude se estima ~{FN_COST_MULTIPLIER}x más costoso que una inspección sobre un cliente legítimo).
2. **Esperar una tasa de falsos positivos elevada**: aproximadamente {FP_RATIO} de cada {FP_DENOMINATOR} inspecciones dirigidas por el modelo corresponderán a clientes legítimos. Esto es esperable en problemas de detección de fraude con alta desproporción de clases.
3. **Priorizar el top {SWEET_SPOT_PCT}% del ranking**: representa el punto de máximo retorno de inversión operativa.
4. **Retraining periódico**: incorporar mensualmente los nuevos resultados de inspección para mantener la efectividad del modelo en el tiempo.
5. **Complementar con reglas de negocio**: aproximadamente el {FN_PCT}% de los fraudes no son detectados por el modelo. Se recomienda mantener reglas heurísticas para casos de borde.

---

## Slide 8: Qué Sigue — Roadmap

| Prioridad | Iniciativa | Impacto esperado | Esfuerzo |
|-----------|------------|------------------|----------|
{ROADMAP_ROWS}

---

## Slide 9: Preguntas Frecuentes

**"¿Por qué la precisión es baja ({BEST_PRECISION_PCT}%)?"**
> El fraude representa el {FRAUD_RATE}% de la base. Un modelo que detecte todos los fraudes sin errores tendría una precisión del {FRAUD_RATE}%. La precisión observada del {BEST_PRECISION_PCT}% indica que el modelo es **~{PRECISION_MULTIPLIER}x más eficiente** que la línea base.

**"¿Significa que la mayoría de las inspecciones no darán resultado?"**
> Sin un modelo de priorización, la inmensa mayoría de las inspecciones aleatorias recaerían sobre clientes legítimos, dado que solo el {FRAUD_RATE}% de la base es fraudulento. El modelo reduce significativamente ese desperdicio operativo.

**"¿Es superior a los métodos actuales?"**
> Si la selección de inspecciones se realiza por sorteo o reglas fijas, el modelo ofrece **{SIM_EFFICIENCY}x más detecciones** por unidad de recurso invertido en inspección.

---

## Slide 10: Próximos Pasos Inmediatos

1. **Validación piloto**: aplicar el modelo a un mes futuro y contrastar los resultados de inspección contra el ranking generado.
2. **Integración operativa**: exportar mensualmente la lista del top {SWEET_SPOT_PCT}% hacia el sistema de gestión de inspecciones.
3. **Feedback loop**: registrar el resultado de cada inspección (fraude confirmado / no confirmado) como insumo para reentrenamiento.
4. **Análisis geográfico**: incorporar la ubicación de los clientes para detectar concentraciones espaciales de fraude.

---

> **Gracias.**
> ¿Preguntas?
