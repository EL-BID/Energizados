# Guía de Diseño de Prueba Piloto en Campo

Protocolo de campo controlado para validar el modelo de detección de fraude antes de su despliegue completo. Mide el **valor incremental (lift)** del modelo contra el **criterio actual de la empresa (BAU — Business As Usual)**, que es la pregunta de negocio real: *"¿Conviene migrar de lo que hacemos hoy al modelo?"*

El diseño canónico usa **200 inspecciones priorizadas por el modelo vs 200 inspecciones priorizadas por el criterio actual de la empresa**.

> **Nota sobre el control:** Esta guía usa BAU como control principal. Comparar contra aleatorio mide *"¿el modelo es mejor que no hacer nada inteligente?"*, lo cual infla el lift. Comparar contra BAU mide *"¿el modelo es mejor que lo que ya hacemos?"*, que es el número que defiende el ROI del cambio. El control aleatorio se mantiene como **tercer brazo opcional** (gold standard) en el Paso 4.

---

## Cuándo usar esta guía

- Antes de desplegar una nueva versión del modelo a producción.
- Cuando la distribuidora pregunta: *"¿Cuánto fraude adicional encuentra el modelo comparado con lo que hacemos hoy?"*
- Como evidencia para justificar el ROI y aprobar el reemplazo del criterio actual.

---

## Diseño experimental de un vistazo

| Elemento | Grupo tratamiento | Grupo control (BAU) |
|----------|-------------------|---------------------|
| Selección | Top-N clientes por score del modelo (descendente) | Top-N clientes por **criterio actual de la empresa** aplicado al mismo pool |
| Propósito | Medir precision@k del modelo | Establecer el baseline de la práctica actual |
| Cegamiento del inspector | Idéntico al control (doble ciego si es posible) | Idéntico al tratamiento |
| Ventana temporal | Misma que el control | Misma que el tratamiento |

> **Importante:** Este es un **cuasi-experimento**, no un RCT estricto. Ambos grupos se seleccionan por una regla (modelo vs BAU), así que mide *lift de un criterio sobre otro*. El análisis por deciles (Paso 7) es lo que valida el ranking interno del modelo de forma independiente.

---

## Paso 1 — Definir hipótesis y métrica primaria

**Objetivo:** decidir el éxito/fracaso con un criterio pre-registrado, no con interpretación post-hoc.

1. Escribí la **hipótesis primaria** en una frase medible. Ejemplo:
   > "Inspeccionar los top-200 clientes por score del modelo produce un hit rate de fraude ≥ 1.5× el hit rate de los top-200 por el criterio actual de la empresa, sobre la misma población y período."

2. Fijá la **métrica primaria**: `lift = hit_rate_modelo / hit_rate_BAU`.

3. Fijá **métricas secundarias**:
   - Hit rate absoluto por grupo (con IC 95%).
   - ROI estimado (escenarios bajo/medio/alto del valor del fraude).
   - Completion rate por grupo.
   - Distribución de hallazgos por segmento (`actividad`, `zona`, `nivel_tension`).

4. **Pre-registrar el umbral de decisión antes del trabajo de campo.** Contra BAU los lifts son más chicos (BAU ya tiene poder predictivo), así que los umbrales son distintos a los de un control aleatorio:

   | Resultado contra BAU | Decisión |
   |----------------------|----------|
   | Lift ≥ 1.5× con p < 0.05 | Desplegar el modelo (reemplazar BAU) |
   | Lift 1.1–1.5× | Marginal: decidir según costo operativo del cambio y ROI proyectado |
   | Lift < 1.1× | El modelo no supera a la práctica actual; iterar |

   > Ajustá el umbral de corte según el costo de cambiar el proceso operativo. Migrar de BAU al modelo tiene costo (capacitación, integración, riesgo), así que un lift de 1.1–1.3× puede no justificar el cambio aunque sea estadísticamente positivo.

**Entregable:** Documento de 1 página con hipótesis + métricas + umbral de decisión, fechado y firmado antes del trabajo de campo.

---

## Paso 2 — Definir la población elegible

**Objetivo:** garantizar que ambos grupos compitan en igualdad de condiciones (sin sesgo de selección).

1. Definí el **universo de clientes inspeccionables**:
   - Mismo período de referencia (ej. clientes activos con `12_anterior` a `1_anterior` completo).
   - Misma región geográfica.
   - Mismo tipo de cliente (o estratificar — ver Paso 3).
   - Excluir clientes ya inspeccionados en los últimos N meses.

2. Generá el **pool maestro** como `data/processed/pilot_pool.parquet` con:
   - `client_id`
   - `score_modelo` (probabilidad de fraude)
   - Variables necesarias para aplicar el criterio BAU (ej. consumo histórico, denuncias, antigüedad del medidor).
   - Variables de estratificación: `actividad`, `zona`, `nivel_tension`, `geo_region`.
   - `fecha_inspeccion_referencia` (control temporal).

3. Validá que el pool tenga **al menos 10× el tamaño de la muestra** (mínimo ~4.000 clientes) para que la selección BAU sea comparable y representativa.

**Entregable:** `pilot_pool.parquet` + criterios de elegibilidad escritos.

---

## Paso 3 — Calcular y validar el tamaño muestral

**Objetivo:** confirmar que el N por grupo alcanza para detectar el lift esperado con poder adecuado.

> **Consecuencia de usar BAU:** los lifts contra BAU son típicamente **1.3×–1.8×**, no 2×+. Detectar un lift más chico requiere **más muestra**. 200+200 puede ser suficiente para lifts ≥ 1.5× con prevalencia alta, pero **queda corto para detectar lifts de 1.2×–1.3×**. Si esperás un lift modesto, subí el N.

1. Estimá la **prevalencia base de fraude** esperada en el pool (tasa histórica de la distribuidora). Llamémosla `p0`.

2. Calculá el poder para el lift objetivo. Regla práctica (α=0.05, poder 0.8) para un control **con poder predictivo (BAU)**:

   | Prevalencia `p0` | Lift detectable con n=200/grupo | Lift detectable con n=400/grupo |
   |------------------|----------------------------------|----------------------------------|
   | 3% | ~2.0× | ~1.6× |
   | 5% | ~1.7× | ~1.4× |
   | 10% | ~1.5× | ~1.25× |
   | 15% | ~1.35× | ~1.2× |

   > Si tu objetivo es demostrar lift ~1.3× contra BAU, **necesitás n=400–600 por grupo**, no 200.

3. Si la prevalencia es **< 5%** o esperás un lift BAU modesto (< 1.4×), **subí a 400–600 por grupo** o aceptá que el piloto será **direccional** (no definitivo) y declaralo en las limitaciones.

4. Si la prevalencia es **> 10%** y esperás lift ≥ 1.5×, 200 + 200 alcanza.

**Entregable:** Nota técnica con el cálculo de poder, el lift objetivo y la justificación del N.

---

## Paso 4 — Formalizar el criterio BAU y asignar los grupos

**Objetivo:** producir dos grupos comparables definidos por reglas explícitas y reproducibles.

> **Gate obligatorio:** el criterio actual de la empresa tiene que poder **formalizarse y codificarse**. Si los criterios actuales son "el operador elige por intuición", **no tenés un control: tenés ruido**. En ese caso, o los formalizás con el equipo de campo, o volvés al control aleatorio (ver Paso 4.3).

### 4.1 Formalizar el criterio BAU

1. Con el equipo de pérdidas/fraude de la empresa, **escribí los criterios actuales** en lenguaje codificable. Ejemplos de criterios BAU formalizables:
   - *"Top-N clientes con mayor caída porcentual de consumo en los últimos 3 meses."*
   - *"Clientes denunciados por vecinos en el último trimestre."*
   - *"Clientes con consumo promedio > X y medidor con antigüedad > Y."*

2. **Requisitos del criterio formalizado:**
   - **Explícito:** escrito, no verbal.
   - **Reproducible:** podés aplicarlo al pool y obtener una lista determinística.
   - **Determinista o sembrado:** al recorrerlo da el mismo resultado (si usa aleatoriedad, fijar semilla).

3. Implementá el criterio como una función que rankea el pool y devuelve el **ranking BAU** (`rank_bau` por cliente).

**Entregable de 4.1:** Documento con el criterio BAU formalizado + script que lo aplica al pool.

### 4.2 Asignar los grupos

1. **Grupo tratamiento (modelo):** los **top-N** clientes del pool por `score_modelo` descendente.

2. **Grupo control (BAU):** los **top-N** clientes del pool por `rank_bau` (criterio actual).

   > **Atención — superposición:** los dos grupos pueden compartir clientes (un cliente puede estar en el top-N del modelo Y en el top-N del BAU). Esto es esperable y **no es un problema**: esos clientes compartidos simplemente no aportan información discriminante para el lift. Reportá cuántos clientes se superponen. Si la superposición es muy alta (> 50%), el modelo y BAU están de acuerdo en gran medida y el lift esperado será chico.

   Para evitar inspeccionar dos veces al mismo cliente, podés:
   - **Asignar cada cliente a un solo grupo** (quitar de un grupo los que están en el otro) y reportar la superposición, o
   - **Mantener la superposición** y aceptar que algunos clientes aportan a ambos brazos (análisis más simple, pero reduce el N efectivo del contraste).

3. Asigná un identificador de grupo a cada cliente: `grupo = "modelo" | "bau"`.

4. Guardá el archivo de asignación con **timestamp y semilla aleatoria** para reproducibilidad.

**Entregable de 4.2:** `pilot_assignments.parquet` con `client_id`, `grupo`, `score_modelo`, `rank_bau`, y conteo de superposición.

### 4.3 (Opcional) Tercer brazo aleatorio — gold standard

Si el presupuesto lo permite (N total = 600), agregar un **tercer grupo de N clientes aleatorios** del pool (estratificado por `zona` / `nivel_tension`). Esto da dos lifts complementarios:

- **Modelo vs BAU** → valor incremental de cambiar (defiende el ROI del reemplazo).
- **Modelo vs aleatorio** → valor absoluto del modelo (comparable con benchmarks externos y publicaciones).

Es la versión más defendible ante cualquier stakeholder.

---

## Paso 5 — Preparar el protocolo de campo

**Objetivo:** que las inspecciones sean comparables entre grupos y no introduzcan sesgo de medición.

1. **Doble ciego (ideal):** los inspectores **no deben saber** de qué grupo es cada inspección (ni si es "modelo" ni "BAU"). Si no es posible, al menos que no conozcan el criterio de origen.

2. **Protocolo de inspección idéntico** para ambos grupos:
   - Mismo checklist.
   - Mismo criterio de confirmación de fraude (manipulación de medidor, derivación clandestina, etc.).
   - Mismo formulario de captura.

3. Definir **categorías de resultado exhaustivas**:
   - `fraude_confirmado`
   - `sin_fraude`
   - `no_contactado` (cliente ausente)
   - `direccion_invalida`
   - `medidor_inaccesible`
   - `otro` (con descripción)

4. **Distribución temporal balanceada:** mezclá inspecciones modelo y BAU en las mismas jornadas/rutas. No mandes todos los BAU en un mes y los del modelo el siguiente.

5. **Capacitación breve** a inspectores (30 min): objetivo del piloto, importancia del cegamiento de grupo, cómo registrar resultados.

**Entregable:** Manual de procedimiento de campo + formulario de captura.

---

## Paso 6 — Ejecutar el trabajo de campo

**Objetivo:** recolectar datos limpios y completos.

1. Ejecutá las **inspecciones** dentro del período definido (idealmente ≤ 4–6 semanas para evitar deriva temporal).

2. **Seguimiento semanal** del completion rate por grupo:
   - Si un grupo tiene > 20% de `no_contactado`, programar **reintentos**.
   - Si la diferencia de completion rate entre grupos es > 10 puntos porcentuales, alerta de sesgo operativo.

3. **Auditoría de calidad:** revisar el 10% de las inspecciones para verificar consistencia del registro.

**Entregable:** Base de datos de resultados con una fila por inspección (`client_id`, `grupo`, `resultado`, `fecha_inspeccion`, `inspector_id`).

---

## Paso 7 — Análisis estadístico

**Objetivo:** estimar el lift con incertidumbre honesta.

1. **Limpieza:** separar las inspecciones válidas (completadas) de las no completadas. Reportar completion rate por grupo.

2. **Hit rate por grupo:**

   ```
   hit_rate_modelo = fraudes_confirmados_modelo / inspecciones_completadas_modelo
   hit_rate_bau    = fraudes_confirmados_bau    / inspecciones_completadas_bau
   ```

3. **Lift con intervalo de confianza:**
   - Usar test de proporciones (Z-test o Fisher exact) para el p-valor.
   - Reportar el IC 95% del lift, no solo el puntual.

4. **Análisis por deciles del score del modelo (obligatorio):**
   - Dividir todos los clientes inspeccionados en deciles según `score_modelo`.
   - Graficar hit rate por decil.
   - Un modelo bien comportado muestra hit rate **monótonamente decreciente** del decil 10 al decil 1. Esto valida el ranking interno **de forma independiente del BAU**.
   - Opcional: marcar en el gráfico qué decil cae cada inspección BAU para ver dónde se concentra el criterio actual.

5. **ROI** con escenarios bajo/medio/alto del valor medio del fraude. La base del cálculo es el **excedente del modelo sobre BAU**:

   ```
   fraudes_extra = fraudes_modelo - fraudes_bau
   ROI = fraudes_extra × valor_medio_fraude - costo_diferencial_inspecciones
   ```

6. **Análisis segmentado:** lift por `zona`, `actividad`, `nivel_tension`. ¿El modelo supera a BAU en todos los segmentos o hay nichos donde BAU sigue siendo mejor? Esto guía un despliegue híbrido (modelo en algunos segmentos, BAU en otros).

**Entregable:** Reporte de análisis con tablas, IC, gráfico de deciles, superposición modelo/BAU y ROI.

---

## Paso 8 — Reporte y decisión

**Objetivo:** cerrar el piloto con una decisión clara y accionable.

1. Comparar el resultado contra el **umbral pre-registrado** del Paso 1.

2. Redactar el reporte final con:
   - Diseño del piloto (población, criterio BAU formalizado, asignación, N).
   - Resultados primarios: lift modelo-vs-BAU + IC + p-valor.
   - Resultados secundarios: deciles, segmentos, ROI, superposición.
   - Limitaciones (ver lista abajo — incluye leakage).
   - **Recomendación explícita:** desplegar / despliegue híbrido / iterar / descartar.

3. **Presentación a stakeholders** con foco en:
   - "¿Cuánto fraude adicional encontramos con el modelo respecto a lo que hacemos hoy?" (lift absoluto contra BAU).
   - "¿Cuál es el ROI esperado al escalar?" (proyección a 1.000 / 5.000 inspecciones).

**Entregable:** Reporte ejecutivo + decisión documentada.

---

## Paso 9 — Lecciones para iteración

**Objetivo:** que el piloto alimente la próxima versión del modelo.

1. **Falsos positivos del modelo** (top-N del modelo sin fraude) son oro: analizar qué features los empujaron hacia arriba en el ranking. ¿Hay un patrón? ¿Falta alguna feature?

2. **Casos donde BAU ganó** (fraude encontrado por BAU que el modelo rankeó bajo): ¿qué tenían en común? ¿Qué sabe el criterio actual que el modelo no capturó? Estas observaciones pueden convertirse en features nuevas.

3. Registrar todo en `docs/pilot_learnings.md` para alimentar el próximo ciclo de entrenamiento.

**Entregable:** Documento de lecciones + backlog de mejoras del modelo.

---

## Estimación del valor medio del fraude (cuando la distribuidora no lo provee)

El cálculo de ROI necesita el valor monetario promedio de un caso de fraude confirmado. Si la distribuidora no lo suministra, estimarlo en este orden de confianza:

### 1. Estimación por componentes (vos podés armarla)

```
valor_fraude = energia_no_facturada + multa + regularizacion
```

- **Energía no facturada:** `consumo_promedio_mensual × meses_fraude × tarifa`.
  - `meses_fraude`: 6 meses (conservador, ventana típica de recuperación).
  - `tarifa`: del dataset o promedio residencial regional.
  - `consumo_promedio_mensual`: mediana de `1_anterior` para clientes no fraudulentos, o percentil 25 de la población (conservador).
- **Multa:** típicamente 2×–3× la energía no facturada, según regulación local.
- **Regularizacion:** R$ 200–500 por caso (medidor + reconexión).

### 2. Rangos típicos del sector (solo referencia)

| Segmento | Valor medio del fraude |
|----------|------------------------|
| Residencial | R$ 1.500 – R$ 5.000 |
| Comercial | R$ 5.000 – R$ 20.000 |
| Industrial | R$ 20.000 – R$ 100.000+ |

Para una muestra mixta, un promedio ponderado razonable de primer piso es **R$ 3.000 – R$ 8.000**.

### 3. Más confiable: pedirlo a la distribuidora

Pedirle al equipo de pérdidas/fraude los **casos de fraude regularizados de los últimos 1–2 años** con su valuación final. Con 20–30 casos históricos ya se obtiene una media creíble.

### 4. Mientras tanto: análisis de sensibilidad

Siempre correr el ROI con tres escenarios para que la decisión no dependa de un solo supuesto:

```
ROI_bajo  = fraudes_extra × R$ 1.500  - costo_diferencial_inspecciones
ROI_medio = fraudes_extra × R$ 5.000  - costo_diferencial_inspecciones
ROI_alto  = fraudes_extra × R$ 15.000 - costo_diferencial_inspecciones
```

> El valor medio del fraude **varía mucho por tipo de cliente**. Reportar el ROI **segmentado** (residencial / comercial / industrial) o al menos por `nivel_tension` / `actividad` — una media única puede ser engañosa en una muestra mixta.

---

## Limitaciones específicas del diseño BAU (declarar en el reporte)

- **Leakage potencial:** si el modelo fue entrenado con labels generados por inspecciones que surgieron de los criterios actuales, el modelo aprendió parcialmente a *replicar* lo que ya hace la empresa. El lift modelo-vs-BAU puede entonces medir en parte *"cuánto el modelo recuerda el criterio actual"* en lugar de *"cuánto lo supera"*. No invalida el piloto, pero hay que declararlo.
- **Superposición de grupos:** parte del top-N del modelo puede coincidir con el top-N de BAU. Reportar el % de superposición; reduce el N efectivo del contraste.
- **Criterio BAU estático:** el control mide contra el criterio actual *en el momento del piloto*. Si la empresa mejora su criterio durante o después, el lift puede cambiar.
- **Poder estadístico:** con N=200+200, el piloto puede ser solo direccional si el lift esperado es < 1.4×. Declarar si este es el caso.

---

## Checklist de entregables

| Paso | Entregable | Tiempo estimado |
|------|------------|-----------------|
| 1 | Hipótesis + métricas + umbral | 1 día |
| 2 | Pool maestro | 1–2 días |
| 3 | Cálculo de poder | 0.5 día |
| 4.1 | Criterio BAU formalizado + script | 1–2 días |
| 4.2 | Asignación de grupos + superposición | 0.5 día |
| 5 | Protocolo de campo | 2–3 días |
| 6 | Trabajo de campo | 4–6 semanas |
| 7 | Análisis | 3–5 días |
| 8 | Reporte + decisión | 2 días |
| 9 | Lecciones | 2 días |

---

## Pitfalls comunes

- **Comparar contra aleatorio cuando el objetivo es reemplazar BAU.** Infla el lift artificialmente. Usar BAU como control principal.
- **Criterio BAU no formalizable.** "Intuición del operador" no es un control reproducible. Gate del Paso 4.1.
- **Ignorar la superposición de grupos.** Reportar siempre el % de clientes compartidos entre top-N modelo y top-N BAU.
- **No ajustar el umbral de decisión.** Los umbrales de control aleatorio (~2×) no aplican a BAU. Usar 1.1–1.5× según Paso 1.
- **Subestimar el N necesario.** Lifts contra BAU son más chicos → se necesita más muestra para detectarlos. Si el lift es modesto, 200+200 no alcanza.
- **Olvidar el leakage.** Declarar si el modelo se entrenó con labels de inspecciones BAU.
- **Metric shopping post-hoc.** Siempre comparar contra el umbral pre-registrado.
- **Completion rate desbalanceado.** Una diferencia >10 puntos porcentuales entre grupos señaliza sesgo operativo, no performance del modelo.
- **Omitir el análisis por deciles.** Un buen top-N no prueba que el ranking esté bien ordenado en todo el rango de scores.
- **Confounding temporal/geográfico.** Ambos grupos deben compartir el mismo período y región.
- **Efecto Hawthorne del inspector.** Cegar el grupo siempre que sea posible.
