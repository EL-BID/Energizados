# Plan: Notebook de Exploración de una Fuente de Datos Raw

## Objetivo

Crear un **notebook interactivo y reutilizable** que, dado un archivo raw (parquet/csv), produzca un análisis
exploratorio completo orientado a:

1. **Extraer conclusiones** sobre la calidad y naturaleza de los datos
2. **Generar preguntas** concretas para investigar con el equipo de negocio o de datos
3. **Documentar hallazgos** de forma que sirvan como referencia para decisiones de preprocesamiento

El notebook debe funcionar como una **herramienta de investigación**, no como un reporte automático. Cada sección
termina con celdas de conclusiones y preguntas abiertas que el analista completa.

---

## Filosofía

- **Un datasource a la vez**: el notebook analiza un único archivo. Para comparar fuentes se usa otro notebook.
- **Conclusiones primero**: cada bloque de análisis termina con una celda markdown donde el analista escribe hallazgos y
  preguntas.
- **Dependencias acotadas**: pandas, numpy, matplotlib, seaborn, scipy, plotly. Sin librerías de profiling automático.
- **Reproducible**: celda de configuración al inicio con todas las variables parametrizables.
- **Copiar y adaptar**: el notebook se copia por cada datasource nuevo y se rellena. Es una plantilla de trabajo, no un
  script que se ejecuta ciegamente.
- **Idioma**: todo el texto del notebook (títulos, conclusiones, preguntas, comentarios) en **español latinoamericano**.

---

## Estructura del Notebook

### Celda 0: Configuración

```python
# === CONFIGURACIÓN ===
FILE_PATH = "data/raw/sample_dataset.parquet"
FILE_SEPARATOR = ";"           # Separador CSV (None para autodetección)
FILE_ENCODING = "utf-8-sig"    # Encoding (utf-8-sig maneja BOM de Windows)
DECIMAL = ","                  # Separador decimal ("," para datos CELESC)
TARGET_COL = "target"          # None si no hay target
DATE_COL = "fecha_inspeccion"  # None si no hay fecha
ID_COL = "CLIENTE"             # Columna de ID/cliente (None si no hay)
LAT_COL = "LATITUDE"           # Columna de latitud (None si no hay)
LON_COL = "LONGITUDE"          # Columna de longitud (None si no hay)
PERIODS_SUFFIX = "_anterior"   # Sufijo de columnas de consumo
NUM_PERIODS = 12               # Cantidad de periodos de consumo
SAMPLE_SIZE = None             # None = todo el dataset
RANDOM_STATE = 42
OUTPUT_DIR = "output/exploration/"  # Donde guardar gráficos exportados

# === CONFIGURACIÓN DE VISUALIZACIÓN ===
PLOTLY_TEMPLATE = "plotly_white"  # Tema para gráficos Plotly
SEABORN_PALETTE = "muted"         # Paleta Seaborn
FIGSIZE_STANDARD = (12, 6)        # Figsize para gráficos simples
FIGSIZE_LARGE = (14, 8)           # Figsize para heatmaps/matrices
MAX_CATEGORIES_PLOT = 30          # Máximo de categorías a graficar
```

---

### Sección 1: Calidad de Carga

**Objetivo**: verificar que los datos se cargaron correctamente antes de analizar contenido. Los CSV de fuentes
latinoamericanas/europeas suelen tener problemas de encoding, separadores y formatos numéricos.

| Celda | Contenido                                                                                                       |
|-------|-------------------------------------------------------------------------------------------------------------------|
| 1.1   | Carga del archivo con manejo de errores: `on_bad_lines='warn'`, detección de encoding con `chardet` si falla    |
| 1.2   | Conteo de filas descartadas por `on_bad_lines` (comparar `wc -l` del CSV vs `len(df)`)                          |
| 1.3   | Verificación de BOM (Byte Order Mark): `\ufeff` en nombres de columnas                                         |
| 1.4   | Detección de formato numérico: columnas que se cargaron como `object` pero contienen números con coma decimal    |
| 1.5   | Conversión automática: `df[col].str.replace(',', '.').astype(float)` para columnas numéricas mal parseadas       |
| 1.6   | Whitespace en strings: `df[col].str.strip()` — detección de espacios trailing (ej. `MATERIAL_INSTALACION`)      |
| 1.7   | Resumen: tabla con columna, dtype original, dtype corregido, problemas detectados                                |

**Celda de conclusiones**:

```markdown
### Conclusiones - Calidad de Carga

- Encoding del archivo: ___
- Filas perdidas por parsing: ___
- Columnas con formato numérico incorrecto: ___
- Columnas con whitespace en valores: ___

### Preguntas

- [ ] ¿El archivo tiene problemas de encoding recurrentes o fue un error puntual?
- [ ] ¿Se pueden regenerar los CSV con formato estándar (UTF-8, punto decimal)?
```

---

### Sección 2: Primera Mirada

**Objetivo**: entender qué hay en el archivo sin asumir nada.

| Celda | Contenido                                                                                                              |
|-------|------------------------------------------------------------------------------------------------------------------------|
| 2.1   | `df.shape`, `df.dtypes`, `df.memory_usage(deep=True).sum()`                                                           |
| 2.2   | `df.head(10)` y `df.tail(5)` - inspección visual                                                                      |
| 2.3   | `df.dtypes.value_counts()` - resumen de tipos                                                                          |
| 2.4   | Clasificación automática de columnas en grupos: numéricas, categóricas, temporales, consumo (`*_anterior`), ID, target, geoespaciales |
| 2.5   | `df.describe(include='all').T` - estadísticos descriptivos completos                                                   |
| 2.6   | Tabla de cardinalidad: para cada columna, `nunique()`, `dtype`, `% nulos`, muestra de valores únicos                   |

**Celda de conclusiones**:

```markdown
### Conclusiones - Primera Mirada

- Dimensiones: ___
- Tipos detectados: ___
- Columnas con cardinalidad sospechosa (muy alta o muy baja): ___
- Observaciones iniciales: ___

### Preguntas

- [ ] ¿La granularidad es la esperada (1 fila = 1 cliente / 1 registro)?
- [ ] ¿Hay columnas que deberían tener otro tipo de dato?
```

---

### Sección 3: Valores Faltantes

**Objetivo**: entender qué falta, cuánto falta, y si hay patrones en lo que falta.

| Celda | Contenido                                                                                        |
|-------|--------------------------------------------------------------------------------------------------|
| 3.1   | Tabla de nulos por columna: count, %, ordenada descendente                                       |
| 3.2   | **Plotly**: barplot horizontal interactivo de % de nulos (hover con count absoluto)               |
| 3.3   | Heatmap de nulidad (muestra de N filas) - patrón de missingness                                  |
| 3.4   | Filas completas sin nulos vs filas con al menos un nulo (conteo y %)                             |
| 3.5   | Filas 100% nulas (si existen)                                                                    |
| 3.6   | Correlación de nulidad entre columnas (¿cuando falta A también falta B?)                         |
| 3.7   | Si hay target: % de nulos por clase target (¿los nulos son informativos?)                        |
| 3.8   | **Plotly**: funnel chart de pérdida de datos — total de filas → filas sin nulos en col A → sin nulos en A+B → ... → filas 100% completas |

**Celda de conclusiones**:

```markdown
### Conclusiones - Valores Faltantes

- Columnas con muchos nulos: ___
- Patrón de nulidad: aleatorio / sistemático / ___
- Nulidad correlacionada con target: sí / no
- Filas utilizables (sin nulos críticos): ___% del total

### Preguntas

- [ ] ¿Por qué falta ___? ¿Es un error de carga o dato inexistente?
- [ ] ¿Se puede imputar ___ o es mejor eliminar?
- [ ] ¿Los nulos representan "no aplica" (informativo) o "dato no recolectado"?
```

---

### Sección 4: Duplicados e Identidad

**Objetivo**: detectar filas duplicadas, entender la granularidad del dataset.

| Celda | Contenido                                                                             |
|-------|---------------------------------------------------------------------------------------|
| 4.1   | Filas 100% duplicadas: conteo y %                                                     |
| 4.2   | Si hay ID_COL: IDs duplicados (¿un cliente aparece más de una vez?)                   |
| 4.3   | Si hay ID_COL + DATE_COL: duplicados por combinación ID+fecha                         |
| 4.4   | Distribución de repeticiones por ID: histograma de `df.groupby(ID_COL).size()`        |
| 4.5   | Muestra de filas duplicadas (para inspección manual)                                  |
| 4.6   | Columnas con valores idénticos entre sí (columnas duplicadas)                         |
| 4.7   | Columnas constantes: una sola valor en toda la columna (varianza = 0)                 |

**Celda de conclusiones**:

```markdown
### Conclusiones - Duplicados

- Granularidad del dataset: un registro = ___
- Duplicados encontrados: ___ filas (___%)
- IDs con múltiples registros: ___ (___% de los IDs)

### Preguntas

- [ ] ¿Los duplicados son válidos o errores de carga?
- [ ] ¿Se debe deduplicar? ¿Con qué criterio (último registro, primero, agregar)?
- [ ] ¿Los IDs repetidos indican múltiples inspecciones del mismo cliente?
```

---

### Sección 5: Variable Target

**Objetivo**: entender la distribución del target y su viabilidad para modelar.

> Se omite si `TARGET_COL = None`.

| Celda | Contenido                                                                                    |
|-------|----------------------------------------------------------------------------------------------|
| 5.1   | `df[TARGET_COL].value_counts(normalize=True)` - distribución                                 |
| 5.2   | **Plotly**: barplot de balance de clases con anotaciones de % y count                        |
| 5.3   | Ratio de desbalance (mayoritaria / minoritaria)                                              |
| 5.4   | Si hay DATE_COL: evolución del target rate en el tiempo (lineplot)                           |
| 5.5   | Target vs nulos: ¿las filas con nulos tienen diferente target rate?                          |
| 5.6   | **Plotly**: funnel chart de definición del target — total clientes → clientes inspeccionados → irregularidades encontradas → fraude confirmado |
| 5.7   | Análisis de sesgo de muestreo: ¿qué fracción de clientes fue inspeccionada? ¿cómo se seleccionaron? |

**Celda de conclusiones**:

```markdown
### Conclusiones - Target

- Balance: ___% positivo, ___% negativo
- Ratio de desbalance: ___:1
- Estabilidad temporal: estable / variable / ___
- Cobertura de inspección: ___% de clientes fueron inspeccionados

### Preguntas

- [ ] ¿El desbalance refleja la realidad o es un sesgo de muestreo?
- [ ] ¿Cómo se definió el target? ¿Inspección confirmada vs sospecha?
- [ ] ¿Los clientes no inspeccionados se asumen como "no fraude"? ¿Es válido?
- [ ] ¿Hay sesgo geográfico o temporal en las inspecciones realizadas?
- [ ] ¿Cuántos tipos de irregularidad existen y cuáles se consideran fraude?
```

---

### Sección 6: Análisis de Inspecciones

**Objetivo**: entender el proceso de inspección que genera el target. Específico para datos de fraude energético donde
existe un archivo de inspecciones separado.

> Se omite si no hay datos de inspecciones disponibles.

| Celda | Contenido                                                                                              |
|-------|--------------------------------------------------------------------------------------------------------|
| 6.1   | Distribución de `TIPO_SERVICO`: Fiscalización vs Corte vs Religação vs Denuncia                        |
| 6.2   | **Plotly**: sunburst/treemap de TIPO_SERVICO → ACAO → CATEGORIA_NOTA (jerarquía de acciones)           |
| 6.3   | **Plotly**: funnel de proceso de inspección: total inspecciones → fiscalizaciones → irregularidades → tipos de irregularidad |
| 6.4   | Distribución temporal de inspecciones: volumen por mes/año                                              |
| 6.5   | Tasa de hallazgo: % de fiscalizaciones que encuentran irregularidad                                     |
| 6.6   | Inspecciones por cliente: distribución de cuántas veces fue inspeccionado cada cliente                  |
| 6.7   | Clientes reincidentes: % de clientes con más de una inspección con irregularidad                       |
| 6.8   | Detección de smart meters: análisis de acciones con "Smart Meter" y su impacto en detección            |
| 6.9   | Acciones remotas vs presenciales: distribución y tasa de hallazgo por tipo                              |

**Celda de conclusiones**:

```markdown
### Conclusiones - Inspecciones

- Total inspecciones: ___
- Tipos de servicio: Fiscalización (___%), Corte (___%), Religação (___%), Denuncia (___%)
- Tasa de hallazgo en fiscalizaciones: ___% encuentran irregularidad
- Smart meters: ___% de acciones involucran medidores inteligentes
- Clientes reinspeccionados: ___% del total

### Preguntas

- [ ] ¿Qué criterio se usa para seleccionar clientes a fiscalizar?
- [ ] ¿Los cortes y religaciones aportan señal de fraude o son operativos?
- [ ] ¿"Procedimiento Irregular" incluye fraude confirmado y sospecha?
- [ ] ¿Los smart meters permiten detección automática? ¿Cambia la definición de target?
- [ ] ¿Las denuncias provienen de vecinos/terceros? ¿Qué tan confiables son?
```

---

### Sección 7: Variables Categóricas

**Objetivo**: entender cardinalidad, distribución y relación con el target.

| Celda | Contenido                                                                                    |
|-------|----------------------------------------------------------------------------------------------|
| 7.1   | Tabla resumen: columna, cardinalidad, top 3 categorías, % modal, % nulos, entropía de Shannon |
| 7.2   | Loop: **Plotly** barplot interactivo de top N categorías (hover con count y %)                |
| 7.3   | Categorías raras: para cada columna, % de categorías con frecuencia < 1%                     |
| 7.4   | **Plotly**: treemap de categorías para variables de alta cardinalidad (ej. ACTIVIDAD_ECONOMICA con 1000+ categorías) |
| 7.5   | Si hay target: loop con barplot de target rate por categoría (top N)                         |
| 7.6   | Si hay target: Cramér's V de cada categórica vs target                                       |
| 7.7   | Si hay target: Information Value (IV) y Weight of Evidence (WoE) por variable categórica     |
| 7.8   | Análisis de agrupabilidad: proponer agrupaciones para variables de alta cardinalidad          |

**Celda de conclusiones por variable** (una por cada categórica relevante):

```markdown
### Conclusiones - {nombre_columna}

- Cardinalidad: ___
- Dominada por: ___ (___%)
- Categorías raras (<1%): ___ de ___ categorías
- Categorías singleton (1 registro): ___
- Relación con target: fuerte / débil / ninguna (Cramér's V = ___, IV = ___)
- Agrupación sugerida: ___

### Preguntas

- [ ] ¿Qué significa la categoría "otros" / valores raros?
- [ ] ¿Se puede agrupar ___?
- [ ] ¿La alta cardinalidad (ej. 1091 actividades económicas) refleja diversidad real o ruido?
```

---

### Sección 8: Variables Numéricas (no consumo)

**Objetivo**: distribución, outliers, relación con target.

| Celda | Contenido                                                                                              |
|-------|--------------------------------------------------------------------------------------------------------|
| 8.1   | Tabla resumen: columna, mean, std, min, p5, p25, p50, p75, p95, max, skew, kurtosis, % ceros, % nulos |
| 8.2   | Loop: **Plotly** histograma + boxplot lado a lado por variable (subplots interactivos)                 |
| 8.3   | Detección de outliers por IQR: tabla con conteo y % por columna                                        |
| 8.4   | Si hay target: loop con violin plot / histograma superpuesto por clase                                 |
| 8.5   | Si hay target: test KS (Kolmogorov-Smirnov) entre clases por variable                                 |
| 8.6   | Si hay target: Information Value (IV) y WoE por bins (numéricas discretizadas)                         |
| 8.7   | Scatter matrix de las numéricas más relevantes (si son pocas)                                          |
| 8.8   | Análisis de PERDIDAS: distribución, % de ceros, relación con zona y tipo de tarifa                     |

**Celda de conclusiones**:

```markdown
### Conclusiones - Variables Numéricas

- Variables con distribución sesgada: ___
- Variables con muchos outliers: ___
- Variables discriminativas (KS significativo): ___
- Variables con alto IV (>0.3): ___

### Preguntas

- [ ] ¿Los outliers en ___ son errores o valores reales?
- [ ] ¿Se necesita transformar (log, sqrt) alguna variable?
- [ ] ¿PERDIDAS = 0 significa sin pérdidas o dato no medido?
- [ ] ¿Los valores extremos de consumo tienen explicación técnica (industria vs residencial)?
```

---

### Sección 9: Análisis Geoespacial

**Objetivo**: entender la distribución geográfica de los datos y su relación con el target. Específico para datasets
que incluyen coordenadas (latitud/longitud).

> Se omite si `LAT_COL = None` o `LON_COL = None`.

| Celda | Contenido                                                                                         |
|-------|---------------------------------------------------------------------------------------------------|
| 9.1   | Calidad de coordenadas: % de (0,0) o nulos, coordenadas fuera del rango esperado                 |
| 9.2   | **Plotly**: scattermapbox de todos los puntos (muestra si hay muchos), coloreado por ZONA          |
| 9.3   | Si hay target: **Plotly** scattermapbox con color por clase target                                |
| 9.4   | **Plotly**: mapa de calor (density_mapbox) de concentración de clientes                           |
| 9.5   | Si hay target: **Plotly** density_mapbox de tasa de fraude por zona geográfica                    |
| 9.6   | Distribución por zona (ZONA): conteo de clientes, target rate por zona                           |
| 9.7   | Distancia al centroide: análisis de clientes en zonas remotas vs urbanas                          |
| 9.8   | Clustering geográfico: K-Means o DBSCAN sobre coordenadas, comparación de target rate por cluster |

**Celda de conclusiones**:

```markdown
### Conclusiones - Análisis Geoespacial

- Cobertura geográfica: ___
- Calidad de coordenadas: ___% válidas, ___% en (0,0) o nulas
- Zonas con mayor concentración: ___
- Target rate por zona: rural ___%, urbano ___%, ___
- Clusters geográficos con alto fraude: ___

### Preguntas

- [ ] ¿Las coordenadas (0,0) representan datos faltantes o ubicaciones reales?
- [ ] ¿Hay zonas con más inspecciones que otras? ¿Sesgo de muestreo geográfico?
- [ ] ¿La tasa de fraude varía significativamente entre zonas? ¿Por qué?
- [ ] ¿Se puede usar la ubicación como feature o introduce sesgo de enforcement?
```

---

### Sección 10: Series de Consumo

**Objetivo**: análisis específico de las columnas `{N}_anterior` que representan el historial de consumo.

> Se omite si no se detectan columnas con el sufijo `PERIODS_SUFFIX`.

| Celda  | Contenido                                                                                        |
|--------|--------------------------------------------------------------------------------------------------|
| 10.1   | Estadísticos por período: tabla con mean, std, min, max, % ceros, % nulos por cada `N_anterior`  |
| 10.2   | **Plotly**: lineplot interactivo de consumo promedio por período (con banda de confianza)         |
| 10.3   | Boxplot por período (12 boxplots lado a lado)                                                    |
| 10.4   | **Plotly**: heatmap interactivo de consumo (muestra aleatoria de ~200 filas, columnas = períodos) |
| 10.5   | Distribución del consumo medio (media de los 12 períodos)                                        |
| 10.6   | Análisis de ceros: % de filas con al menos un cero, filas con todos ceros                        |
| 10.7   | Consumo constante: % de filas donde todos los períodos son iguales                               |
| 10.8   | Valores negativos: existencia, conteo, distribución                                              |
| 10.9   | Variación entre períodos consecutivos: distribución de `(t) - (t-1)`                             |
| 10.10  | Caídas abruptas: % de filas con caída > 50% entre períodos consecutivos                          |
| 10.11  | Si hay target: consumo promedio por clase (lineplot superpuesto)                                  |
| 10.12  | Si hay target: **Plotly** heatmap de muestra por clase (fraude vs no fraude), lado a lado         |
| 10.13  | Segmentación por nivel de consumo: bajo/medio/alto, con target rate por segmento                 |
| 10.14  | Detección de patrones anómalos: consumo que cae a 0 y vuelve, cambios bruscos de nivel           |

**Celda de conclusiones**:

```markdown
### Conclusiones - Series de Consumo

- Tendencia general: creciente / decreciente / estable
- Proporción de ceros: ___
- Consumo constante: ___% de filas
- Valores negativos: sí / no (___%)
- Diferencia visual entre clases: sí / no
- Patrones anómalos detectados: ___

### Preguntas

- [ ] ¿Un consumo de 0 significa medidor apagado, lectura fallida, o consumo real?
- [ ] ¿Los valores negativos son correcciones, devoluciones o errores?
- [ ] ¿Cuántos períodos históricos son realmente útiles para el modelo?
- [ ] ¿Un cambio brusco de nivel de consumo (sin llegar a 0) indica cambio de medidor o manipulación?
- [ ] ¿El consumo se mide en kWh? ¿Es directamente comparable entre tipos de tarifa?
```

---

### Sección 11: Formato Largo vs Ancho de Consumo

**Objetivo**: analizar el historial de consumo en su formato original (largo: PERIODO, CLIENTE, CONSUMO) antes
del pivoteo a formato ancho. Detectar problemas que se pierden al pivotar.

> Específico cuando el consumo viene en formato largo (ej. `Historial_consumo.csv`).

| Celda | Contenido                                                                                                    |
|-------|--------------------------------------------------------------------------------------------------------------|
| 11.1  | Dimensiones del formato largo: total registros, clientes únicos, períodos únicos                              |
| 11.2  | Cobertura temporal por cliente: distribución de cuántos períodos tiene cada cliente                           |
| 11.3  | **Plotly**: funnel de cobertura: total clientes → con ≥6 períodos → con ≥12 períodos → con todos los períodos |
| 11.4  | Períodos disponibles: tabla de períodos con conteo de clientes en cada uno                                    |
| 11.5  | Clientes con huecos: % de clientes con períodos faltantes (no consecutivos)                                  |
| 11.6  | Clientes con múltiples registros por período (duplicados de consumo)                                         |
| 11.7  | Consumo por período agregado: media, mediana, total por PERIODO                                              |
| 11.8  | **Plotly**: lineplot de consumo total/promedio por PERIODO (tendencia temporal real)                          |

**Celda de conclusiones**:

```markdown
### Conclusiones - Formato Largo de Consumo

- Total registros: ___, Clientes: ___, Períodos: ___
- Cobertura: ___% de clientes tienen los 12 períodos completos
- Clientes con huecos temporales: ___%
- Duplicados de consumo por (cliente, período): ___

### Preguntas

- [ ] ¿Qué hacer con clientes que tienen menos de 12 períodos? ¿Imputar con 0 o excluir?
- [ ] ¿Los huecos son por baja del servicio, cambio de medidor, o error de registro?
- [ ] ¿Los períodos representan meses calendario (YYYYMM) o ciclos de facturación?
- [ ] ¿Hay superposición de períodos? ¿El período más reciente es confiable (puede estar incompleto)?
```

---

### Sección 12: Correlaciones

**Objetivo**: detectar redundancias y relaciones lineales entre features.

| Celda | Contenido                                                                       |
|-------|---------------------------------------------------------------------------------|
| 12.1  | Matriz de correlación Pearson (**Plotly** heatmap interactivo) de todas las numéricas |
| 12.2  | Pares con `|corr| > 0.8`: tabla ordenada por correlación descendente            |
| 12.3  | Si hay target: correlación de cada numérica con el target (point-biserial)      |
| 12.4  | Correlación Spearman (para relaciones no lineales) - solo top pares             |
| 12.5  | Correlación entre períodos de consumo: ¿los períodos cercanos están más correlacionados? |
| 12.6  | **Plotly**: scatter interactivo de los pares más correlacionados (con hover de ID) |

**Celda de conclusiones**:

```markdown
### Conclusiones - Correlaciones

- Pares altamente correlacionados: ___
- Variables más correlacionadas con target: ___
- Estructura de correlación del consumo: ___

### Preguntas

- [ ] ¿Se puede eliminar alguna variable redundante?
- [ ] ¿La correlación entre períodos consecutivos sugiere usar diferencias en vez de valores absolutos?
```

---

### Sección 13: Análisis Temporal

**Objetivo**: entender la distribución temporal de los datos.

> Se omite si `DATE_COL = None`.

| Celda | Contenido                                                                                 |
|-------|-------------------------------------------------------------------------------------------|
| 13.1  | Rango temporal: fecha min, fecha max, span                                                |
| 13.2  | **Plotly**: distribución por año y por mes (barplots interactivos)                        |
| 13.3  | Target rate por período temporal (si hay target)                                          |
| 13.4  | Volumen de registros por período (¿hay períodos sin datos?)                               |
| 13.5  | Estacionalidad: ¿el target rate varía por mes del año?                                    |
| 13.6  | **Plotly**: timeline de inspecciones (si aplica) — scatter con fecha vs tipo de resultado |
| 13.7  | Distribución por día de la semana: ¿las inspecciones se concentran en ciertos días?       |

**Celda de conclusiones**:

```markdown
### Conclusiones - Análisis Temporal

- Rango: ___ a ___
- Períodos sin datos: ___
- Estacionalidad del target: sí / no
- Días/meses con más actividad: ___

### Preguntas

- [ ] ¿Por qué hay menos datos en ___?
- [ ] ¿El período de test debe respetar la temporalidad?
- [ ] ¿Hay cambios de política o metodología que afecten la comparabilidad temporal?
- [ ] ¿El volumen de inspecciones está limitado por capacidad operativa?
```

---

### Sección 14: Análisis de Join entre Fuentes

**Objetivo**: cuando el dataset final se construye a partir de múltiples fuentes (maestro + consumo + inspecciones),
analizar la calidad del cruce y qué se pierde en cada join.

> Se omite si el análisis es sobre un único archivo ya unificado.

| Celda | Contenido                                                                                                 |
|-------|-----------------------------------------------------------------------------------------------------------|
| 14.1  | Cobertura de IDs: Venn diagram (o tabla) de IDs presentes en cada fuente                                  |
| 14.2  | **Plotly**: funnel de join — clientes en maestro → con historial de consumo → con inspección → con target definido |
| 14.3  | Clientes huérfanos: IDs en consumo/inspecciones que no existen en el maestro                              |
| 14.4  | Clientes sin consumo: IDs en maestro que no tienen historial de consumo                                   |
| 14.5  | Clientes sin inspección: IDs en maestro que nunca fueron inspeccionados (mayoría)                         |
| 14.6  | Perfil de clientes excluidos: ¿los que se pierden en el join son diferentes a los que quedan?             |
| 14.7  | **Plotly**: barplot comparativo de distribución de categóricas entre clientes incluidos vs excluidos       |
| 14.8  | Impacto del join en el balance del target: ¿cambia el ratio de fraude después del cruce?                  |

**Celda de conclusiones**:

```markdown
### Conclusiones - Join entre Fuentes

- Clientes en maestro: ___
- Clientes con consumo: ___ (___% del maestro)
- Clientes con inspección: ___ (___% del maestro)
- Dataset final (join completo): ___ registros
- Pérdida por join: ___% de clientes descartados

### Preguntas

- [ ] ¿Los clientes sin historial de consumo son nuevos o tienen datos en otro sistema?
- [ ] ¿Los clientes no inspeccionados se deben incluir como clase negativa o excluir del dataset?
- [ ] ¿El perfil de clientes excluidos introduce sesgo en el modelo?
- [ ] ¿El join debe ser inner (solo completos) o left (conservar todos del maestro)?
```

---

### Sección 15: Poder Predictivo de Features

**Objetivo**: ranking cuantitativo de qué variables tienen mayor poder para discriminar entre clases del target.

> Se omite si `TARGET_COL = None`.

| Celda | Contenido                                                                                       |
|-------|-------------------------------------------------------------------------------------------------|
| 15.1  | Information Value (IV) por variable: tabla ordenada descendente                                  |
| 15.2  | **Plotly**: barplot horizontal de IV con umbrales de referencia (< 0.02 inútil, 0.02-0.1 débil, 0.1-0.3 medio, > 0.3 fuerte) |
| 15.3  | Weight of Evidence (WoE) por bins para las top 10 variables numéricas                           |
| 15.4  | **Plotly**: WoE plots interactivos por variable                                                  |
| 15.5  | Chi-squared test para todas las categóricas vs target: tabla con estadístico y p-value          |
| 15.6  | KS test para todas las numéricas vs target: tabla con estadístico y p-value                     |
| 15.7  | Ranking combinado: tabla con IV, KS/Chi2, Cramér's V, correlación point-biserial por variable   |
| 15.8  | Feature importance rápida: entrenar LightGBM sin tunear y extraer importances (gain + split)    |

**Celda de conclusiones**:

```markdown
### Conclusiones - Poder Predictivo

- Top 5 variables por IV: ___
- Variables con IV < 0.02 (candidatas a eliminar): ___
- Coincidencia entre métodos (IV vs KS vs LGBM importance): ___

### Preguntas

- [ ] ¿Las variables con alto IV pero bajo en LGBM importance tienen interacción con otras?
- [ ] ¿Las variables de consumo agregadas son más predictivas que los períodos individuales?
- [ ] ¿Hay variables con alto poder predictivo que podrían causar data leakage?
```

---

### Sección 16: Análisis de Segmentos

**Objetivo**: entender si existen subpoblaciones con comportamiento muy diferente que justifiquen modelos separados
o tratamiento especial.

| Celda | Contenido                                                                                                  |
|-------|------------------------------------------------------------------------------------------------------------|
| 16.1  | Segmentación por TIPO_CLIENTE: métricas clave (consumo medio, target rate, n) por segmento                 |
| 16.2  | Segmentación por TIPO_TARIFA (agrupada): residencial vs comercial vs industrial vs rural                    |
| 16.3  | **Plotly**: barplot agrupado de target rate por segmento con intervalos de confianza                        |
| 16.4  | Segmentación por nivel de consumo: cuartiles de consumo promedio × target rate                              |
| 16.5  | **Plotly**: funnel por segmento: clientes → inspeccionados → con irregularidad (para comparar tasas)       |
| 16.6  | Cruces: TIPO_CLIENTE × ZONA × target rate (tabla pivote con heatmap)                                       |
| 16.7  | Análisis de smart meters vs electromecánicos: distribución de MATERIAL, target rate por tipo de medidor    |

**Celda de conclusiones**:

```markdown
### Conclusiones - Segmentos

- Segmentos con mayor tasa de fraude: ___
- Segmentos con menor cobertura de inspección: ___
- Diferencia entre smart meters y electromecánicos: ___
- Segmentos que podrían requerir modelo separado: ___

### Preguntas

- [ ] ¿Se debe entrenar un modelo por tipo de cliente o un modelo único?
- [ ] ¿Los segmentos con poca representación tienen suficientes datos para entrenar?
- [ ] ¿Los smart meters cambian la dinámica de detección de fraude?
- [ ] ¿Hay segmentos donde la inspección es más costosa/difícil?
```

---

### Sección 17: Resumen y Próximos Pasos

Celda final de síntesis que el analista completa después de recorrer todo el notebook.

```markdown
## Resumen de Hallazgos

### Calidad de datos

- Problemas de carga: ___
- Valores faltantes críticos: ___
- Duplicados: ___
- Coordenadas inválidas: ___

### Variables más relevantes

- Por IV: ___
- Por KS/Chi2: ___
- Por análisis visual: ___

### Problemas detectados

- Data leakage potencial: ___
- Sesgo de muestreo: ___
- Variables redundantes: ___

### Insights de dominio

- Patrones de consumo en fraude: ___
- Segmentos de riesgo: ___
- Relación geográfica: ___

## Preguntas Pendientes (para negocio/datos)

1. ...
2. ...
3. ...

## Decisiones de Preprocesamiento Sugeridas

- Imputación: ...
- Encoding: ...
- Eliminación: ...
- Transformaciones: ...
- Agrupaciones de categorías: ...
- Tratamiento de coordenadas inválidas: ...

## Próximos Pasos

- [ ] Confirmar definición de target con el equipo de negocio
- [ ] Decidir estrategia de join (inner vs left)
- [ ] Definir ventana temporal para train/val/test
- [ ] Decidir si se entrena modelo único o por segmento
- [ ] ...
```

---

## Convenciones del Notebook

### Estructura de cada sección

```
[Markdown] Título + explicación de qué se analiza y por qué
[Code]     Análisis (tablas, cálculos)
[Code]     Gráfico(s)
[Markdown] **Conclusiones** + **Preguntas** (plantilla para que el analista llene)
```

### Funciones helper

El notebook incluye al inicio un bloque de funciones utilitarias para evitar repetición:

```python
def classify_columns(df, target_col, date_col, periods_suffix, lat_col, lon_col):
    """Clasifica columnas en: numeric, categorical, temporal, consumption, target, id, geo."""
    ...


def missing_summary(df):
    """Retorna DataFrame con count_null, pct_null por columna."""
    ...


def plot_hist_box(series, title):
    """Histograma + boxplot lado a lado (matplotlib)."""
    ...


def plotly_hist_box(series, title):
    """Histograma + boxplot interactivo (plotly)."""
    ...


def plot_target_rate(df, col, target_col, top_n=20):
    """Barplot de target rate por categoría (plotly)."""
    ...


def plotly_funnel(labels, values, title):
    """Funnel chart con Plotly."""
    ...


def plotly_map(df, lat_col, lon_col, color_col=None, title=""):
    """Scattermapbox con Plotly (usa OpenStreetMap, sin API key)."""
    ...


def plotly_treemap(df, path_cols, values_col=None, title=""):
    """Treemap jerárquico con Plotly."""
    ...


def cramers_v(x, y):
    """Calcula Cramér's V entre dos variables categóricas."""
    ...


def information_value(df, col, target_col, bins=10):
    """Calcula IV y retorna tabla de WoE por bin."""
    ...


def ks_test_by_target(df, col, target_col):
    """KS test de una numérica entre clases del target."""
    ...


def consumption_cols(df, num_periods, suffix):
    """Retorna lista de columnas de consumo ordenadas."""
    ...
```

### Estilo visual

**Matplotlib/Seaborn** (para gráficos estáticos de alta calidad):
- Paleta consistente: usar `sns.set_palette("muted")` o similar
- Figsize estándar: `(12, 6)` para gráficos simples, `(14, 8)` para heatmaps
- Títulos descriptivos en cada gráfico (en español)
- `plt.tight_layout()` siempre
- Tablas con `df.style.background_gradient()` cuando aporten claridad

**Plotly** (para gráficos interactivos):
- Usar `plotly_white` como template base
- Funnels: `plotly.express.funnel` o `plotly.graph_objects.Funnel`
- Mapas: `plotly.express.scatter_mapbox` con `mapbox_style="open-street-map"` (sin API key)
- Treemaps: `plotly.express.treemap` para jerarquías categóricas
- Sunbursts: `plotly.express.sunburst` para TIPO_SERVICO → ACAO
- Heatmaps interactivos: `plotly.express.imshow` con hover
- Todos los gráficos Plotly con hover informativo y títulos en español

### Dependencias

```python
# Estándar
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Interactivos
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
```

---

## Ubicación

```
notebooks/exploration_template.ipynb     # Template limpio (se copia por datasource)
notebooks/exploration_sample.ipynb       # Ejemplo ejecutado con sample_dataset.parquet
```

Cada vez que se analiza una fuente nueva:

```bash
cp notebooks/exploration_template.ipynb notebooks/exploration_{nombre_fuente}.ipynb
```

---

## Resumen de secciones agregadas respecto al plan original

| # | Sección                       | Razón de inclusión                                                                                |
|---|-------------------------------|---------------------------------------------------------------------------------------------------|
| 1 | Calidad de Carga              | Los CSV de CELESC tienen BOM, decimal con coma, EOF errors, whitespace en valores                 |
| 6 | Análisis de Inspecciones      | El target proviene de inspecciones; entender el proceso es fundamental para definir bien el target |
| 9 | Análisis Geoespacial          | Datos_maestro incluye LATITUDE/LONGITUDE — potencial para mapas y clustering geográfico           |
| 11| Formato Largo vs Ancho        | Historial_consumo viene en formato largo (PERIODO, CLIENTE, CONSUMO) — hay que analizar cobertura |
| 14| Join entre Fuentes            | Son 3 CSVs que se cruzan por CLIENTE — el join pierde registros y puede introducir sesgo          |
| 15| Poder Predictivo              | IV, WoE, feature importance rápida para priorizar features antes de entrenar                      |
| 16| Segmentos                     | TIPO_CLIENTE × TIPO_TARIFA × ZONA × MATERIAL crean subpoblaciones con dinámica diferente          |

### Gráficos Plotly agregados

| Tipo          | Dónde se usa                                                                         |
|---------------|--------------------------------------------------------------------------------------|
| Funnel        | Pérdida de datos por nulos (§3), definición de target (§5), cobertura de consumo (§11), join entre fuentes (§14), segmentos (§16) |
| Scattermapbox | Distribución geográfica de clientes y target rate (§9)                                |
| Density map   | Concentración geográfica y zonas de alto fraude (§9)                                  |
| Treemap       | Variables de alta cardinalidad como ACTIVIDAD_ECONOMICA (§7)                          |
| Sunburst      | Jerarquía TIPO_SERVICO → ACAO → CATEGORIA_NOTA de inspecciones (§6)                  |
| Heatmap       | Consumo por período (§10), correlaciones (§12)                                        |
| Bar + hover   | Categóricas (§7), IV ranking (§15), segmentos (§16)                                   |

---

## Diferencia con FEATURE-EDA.md

| Aspecto       | FEATURE-EDA.md (módulo)             | Este notebook                                      |
|---------------|-------------------------------------|----------------------------------------------------|
| Tipo          | Módulo del framework (automatizado) | Notebook interactivo (manual)                      |
| Output        | Reporte HTML generado               | Notebook con conclusiones escritas por el analista |
| Uso           | Pipeline / CLI                      | Jupyter Lab, exploración ad-hoc                    |
| Foco          | Métricas exhaustivas                | Conclusiones y preguntas de investigación          |
| Reutilización | Se ejecuta igual siempre            | Se copia y adapta por datasource                   |
| Interactividad| Estático (matplotlib)               | Interactivo (plotly + matplotlib)                  |
