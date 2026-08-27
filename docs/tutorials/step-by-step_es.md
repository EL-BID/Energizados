# Guía paso a paso: Energizados de cero a un modelo entrenado

Esta guía te lleva desde clonar el repositorio hasta crear y ejecutar el proyecto demo
(ETL + entrenamiento LightGBM sobre el dataset de ejemplo incluido), usando `uv` como
gestor de ambientes.

**Entorno objetivo de esta guía:** un VPS con **Linux SUSE Enterprise Server 15
(SLES 15)** cuya salida a internet es **mediante proxy**, y al que se accede
**siempre por SSH**. Todos los pasos están pensados para ese entorno headless
(sin navegador ni display en el servidor). Si trabajás en una máquina local sin
proxy, simplemente omití los pasos de configuración de proxy (Paso 2).

## Ruta rápida

```bash
# (VPS con proxy) configurar el proxy primero — ver Paso 2
git clone https://github.com/EL-BID/Energizados.git
cd Energizados
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .
energizados init sample && cd sample
energizados validate etl,train
energizados run etl,train
```

Al terminar: descargá `output/index.html` a tu máquina (ver Paso 3) para ver las
métricas del run en tu navegador.
Documentación local: `uv pip install -e ".[dev]"` en el repo y `mkdocs serve` + túnel SSH.

---

## Paso 1. Prerrequisitos (SLES 15)

| Requisito   | Detalle                                                                       |
| ----------- | ----------------------------------------------------------------------------- |
| SO          | SLES 15 (cualquier SP) u openSUSE Leap 15+ (glibc ≥ 2.26, requerido por duckdb/pyarrow) |
| Python      | **3.12** (esta guía la fija; el framework soporta &gt;= 3.10, &lt; 4.0)       |
| Git         | `sudo zypper install git` si no está                                          |
| curl o wget | `sudo zypper install curl` (o `wget`) para instalar uv                        |
| tmux        | `sudo zypper install tmux` — imprescindible con SSH (ver Paso 3)              |
| uv          | se instala en el Paso 4                                                       |
| Internet    | para clonar y descargar dependencias (numpy, lightgbm, geopandas, etc.)       |
| Salida      | solo vía proxy HTTP — se configura en el Paso 2                               |

> No necesitas instalar Python 3.12 con zypper: `uv` descarga un build standalone
> de Python 3.12 y todas las dependencias del framework tienen wheels
> `manylinux` para Linux x86_64 (verificado: duckdb usa `manylinux_2_26`,
> pyarrow `manylinux_2_17`, ambos satisfechos por el glibc de SLES 15), así que
> no se requieren paquetes de sistema adicionales ni compilador.

## Paso 2. Configurar el proxy (VPS — hacer esto ANTES de todo lo demás)

Todo el toolchain de esta guía (curl, git, uv, pip, y las descargas de datos del
framework) respeta las variables de entorno estándar de proxy. Agregá esto a
`~/.bashrc` (ajustando host y puerto a tu proxy):

```bash
export HTTP_PROXY="http://proxy.empresa.com:8080"
export HTTPS_PROXY="http://proxy.empresa.com:8080"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export NO_PROXY="localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
```

Luego `source ~/.bashrc`. Verificación rápida:

```bash
curl -sI https://pypi.org | head -1   # debe responder HTTP/... 200 o 301
```

Notas por componente:

| Componente | Detalle |
| ---------- | ------- |
| `git` | Respeta las variables de entorno. Alternativa persistente: `git config --global http.proxy http://proxy.empresa.com:8080` |
| `zypper` | Respeta las variables de entorno (usa libcurl). Si `sudo` las limpia, usá `sudo -E zypper install ...` o configurá el proxy del sistema en `/etc/sysconfig/proxy` |
| `uv` | Respeta las variables de entorno. Si el proxy intercepta TLS con CA corporativa: `export UV_NATIVE_TLS=1` |
| `pip` / `requests` | Con CA corporativa: `export PIP_CERT=/ruta/ca-empresa.pem` y `export REQUESTS_CA_BUNDLE=/ruta/ca-empresa.pem` |

**Dominios que el proxy debe permitir** (pedilos al administrador si hay filtrado):

| Dominio | Para qué | Frecuencia |
| --- | --- | --- |
| `pypi.org` + `files.pythonhosted.org` | Instalación de dependencias (uv/pip) | Una vez |
| `astral.sh` | Instalador de uv | Una vez |
| `github.com` + `objects.githubusercontent.com` | `git clone` del repo; build standalone de Python 3.12 que descarga uv; datos geográficos de geobr | Una vez |
| `api.github.com` | Metadatos de geobr (features geográficas) — **con verificación TLS** | Una vez |
| `www.ipea.gov.br` | Fallback de datos geográficos | Una vez |
| `extensions.duckdb.org` | Extensiones duckdb (`spatial`, `httpfs`) para geobr | Una vez |
| `cdn.plot.ly` / `cdn.tailwindcss.com` | Solo los carga el **navegador que abre los reportes HTML** (tu máquina local, no el VPS). Evitalo con `self_contained: true` | Al ver reportes |

> Si el proxy hace inspección TLS (reemplaza certificados), las conexiones con
> verificación estricta fallan hasta que exportes el CA corporativo
> (`REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` / `UV_NATIVE_TLS=1`). La descarga de
> *datos* de geobr no se ve afectada, pero los *metadatos* (`api.github.com`) y la
> instalación de paquetes sí lo necesitan.

> Detalle completo del comportamiento offline/proxy del framework (en inglés) en
> [Offline & Proxied Environments](../user-guide/offline-and-proxy.md).

## Paso 3. Trabajo por SSH: tmux, túneles y descarga de artefactos

Todo lo que sigue ocurre en el VPS por SSH. Tres herramientas de trabajo:

**tmux — para que el trabajo sobreviva a cortes de SSH.** Un entrenamiento largo
muere si se corta la conexión SSH. Corré los pasos largos dentro de tmux:

```bash
tmux new -s energizados    # crear sesión
# ... ejecutar lo que quieras ...
# Ctrl+B y luego D        # despegarse (detach) — el proceso sigue corriendo
tmux attach -t energizados # re-pegarse más tarde (inclusive desde otra máquina)
```

**Túneles SSH — para servicios web del VPS.** MkDocs (Paso 14), Jupyter y la
consola web escuchan en `127.0.0.1` del VPS. Para usarlos desde tu navegador:

```bash
# Desde TU máquina local:
ssh -L 8000:127.0.0.1:8000 usuario@vps   # luego abre http://localhost:8000
```

**Descarga de artefactos — los reportes se ven en tu máquina, no en el VPS.** El
VPS no tiene navegador; traé los HTML/CSV generados con `scp` o `rsync`:

```bash
# Desde TU máquina local:
scp usuario@vps:~/projects/sample/output/index.html .
rsync -avz usuario@vps:~/projects/sample/output/train-*/reports/ ./reports/
```

> **Reportes sin internet:** los reportes HTML referencian CDN de Plotly/Tailwind
> por defecto (los carga el navegador que los abre). Si vas a verlos en una red
> sin salida a internet, activá `self_contained: true` en la sección `evaluation`
> de `config/train.yaml` (o `output.self_contained` en `eda.yaml`): los assets se
> incrustan en el HTML (+~3.5 MB por archivo) y se ven offline.

## Paso 4. Clonar el repositorio

```bash
git clone https://github.com/EL-BID/Energizados.git
cd Energizados
```

Verificación: `ls` debe mostrar `pyproject.toml`, `src/`, `tests/`, `README.md`.

## Paso 5. Instalar uv

En SLES 15 (con el proxy del Paso 2 ya exportado — curl lo respeta):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# o si prefieres wget:
# wget -qO- https://astral.sh/uv/install.sh | sh
```

Alternativa si ya tienes Python 3.12: `pip install uv` (o `pipx install uv`).

Verificación:

```bash
uv --version
```

> El instalador deja uv en `~/.local/bin`. Si `uv: command not found`, abre una
> terminal nueva o ejecuta `source ~/.bashrc` (o el rc de tu shell).

## Paso 6. Crear el ambiente e instalar el framework

Desde la raíz del repositorio clonado:

```bash
# Crea .venv con Python 3.12 (lo descarga automáticamente si no existe;
# el build standalone llega desde github.com — ya está en la allowlist)
uv venv --python 3.12

# Activa el entorno
source .venv/bin/activate

# Instala el framework en modo editable
uv pip install -e .
```

Variantes según tu uso:

| Objetivo                                          | Comando                      |
| ------------------------------------------------- | ---------------------------- |
| Solo ejecutar el demo                             | `uv pip install -e .`        |
| Contribuir / correr tests                         | `uv pip install -e ".[dev]"` |
| Todos los modelos (catboost, xgboost, tensorflow) | `uv pip install -e ".[all]"` |
| Consola web                                       | `uv pip install -e ".[web]"` |

> **Importante:** usa `uv pip install`, no `uv sync`. Este proyecto mantiene su lockfile
> con Poetry (`poetry.lock`); `uv sync` crearía un `uv.lock` no deseado.

Verificación:

```bash
energizados --help
```

## Paso 7. Verificar el entorno

```bash
energizados doctor
```

Confirma versión de Python y que los paquetes requeridos están presentes. Salida
sana = todos los checks en verde (exit code 0). No requiere red.

## Paso 8. Crear el proyecto demo

Primero crea un directorio dedicado para agrupar todos tus proyectos (fuera del
repo del framework, con el entorno activado):

```bash
mkdir ~/projects && cd ~/projects
energizados init sample
cd sample
```

Esto genera la estructura completa:

```
sample/
├── config/          # etl.yaml, train.yaml, infer.yaml, eda.yaml
├── data/raw/        # sample_dataset.parquet (dataset demo incluido)
├── src/             # ETL, modelo e inferencia personalizables + scripts run/
├── notebooks/
├── output/          # aquí aparecen los runs de entrenamiento
└── tests/
```

Verificación: `ls config` muestra los 4 YAML.

## Paso 9. Validar la configuración

Siempre dentro de `sample/`:

```bash
energizados validate etl,train
```

Debe reportar validación exitosa sin errores. Para ver el plan sin ejecutar nada:

```bash
energizados run etl,train --dry-run
```

## Paso 10. Ejecutar el ETL

```bash
energizados run etl
```

Qué hace: lee `data/raw/sample_dataset.parquet`, elimina filas con NULL y escribe
`data/processed/sample_dataset.parquet` (ETL `sample` de `etl.yaml`).

Verificación: `ls data/processed` muestra `sample_dataset.parquet`.

## Paso 10b. Features geográficas a través del proxy (opcional, recomendado)

Si vas a usar `GeoFeaturesETL` (jerarquía IBGE `geo_estado`/`geo_municipio`/
`geo_regiao`, distancias, clustering — requerido para el split
`stratified_time`), el framework descarga shapefiles del IBGE **una única vez**
vía `geobr`. Después de eso, todo queda cacheado en disco y no se vuelve a
tocar la red.

**1. Pre-calienta los caches una sola vez** (con el proxy activo, en el entorno
del proyecto):

```bash
# Datos geobr (municipios + estados) → ~/.cache/geobr/
python -c "import geobr; print(geobr.read_state(year=2020).shape)"

# Extensiones duckdb (spatial + httpfs) → ~/.duckdb/extensions/
python -c "import duckdb; c = duckdb.connect(); c.execute('LOAD spatial'); c.execute('LOAD httpfs'); print('extensiones OK')"
```

Si ambos comandos responden, el proxy está dejando pasar todo lo necesario
(`api.github.com`, `github.com`/`objects.githubusercontent.com`,
`extensions.duckdb.org`; ver tabla del Paso 2). Si el primero falla con
`ConnectionError: Failed to download v2 metadata`, es falta de permiso del proxy
en `api.github.com`.

**2. Configura siempre `cache_dir` en el ETL geográfico** (`config/etl.yaml`):

```yaml
  geo_features:
    enabled: true
    description: "Features geográficas (IBGE + cluster + distancias)"
    input: "@dataset"
    output: "data/processed/dataset_geo.parquet"
    custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
    params:
      lat_col: "latitud"
      lon_col: "longitud"
      cache_dir: ".cache/ibge"   # → .cache/ibge/ibge_municipios_2020.parquet + ibge_states_2020.parquet
```

**3. VPS sin salida posterior / clonar la instalación:** los caches son
directorios plain-files; copiándolos a otro VPS, las features geográficas
corren **sin tocar internet**:

```bash
# Qué respaldar/copiar:
~/.cache/geobr/            # datos geobr
~/.duckdb/extensions/      # extensiones duckdb
<proyecto>/.cache/ibge/    # caches del proyecto (si usaste cache_dir)
```

## Paso 11. Ejecutar el EDA

```bash
energizados run eda
```

Qué hace: análisis exploratorio interactivo del dataset procesado
(`data/processed/sample_dataset.parquet`): estadísticas globales, análisis por
columna, variable objetivo, importancia de features (IV, KS, Cramér's V) y
segmentación. Genera un reporte HTML autocontenido.

Verificación: `output/eda-*/` contiene `eda_report.html`. Descargalo y ábrelo en
tu navegador (ver Paso 3):

```bash
# desde tu máquina local:
scp usuario@vps:~/projects/sample/output/eda-*/eda_report.html .
```

## Paso 12. Ejecutar el entrenamiento

> Al ser un paso largo, corrélo dentro de tmux (Paso 3) para que sobreviva a
> cortes de SSH: `tmux new -s train` → ejecutar → `Ctrl+B D`.

```bash
energizados run train
```

Qué hace:

1. **Split**: partición temporal train/val/test (guarda splits en `data/temp/splits/`).
2. **Feature engineering + entrenamiento**: modelo LightGBM con búsqueda de
   hiperparámetros (`n_iter: 60`).
3. **Evaluación**: reporte HTML/JSON con métricas (AUC, precision, recall, F1...).

> **Duración:** la búsqueda de hiperparámetros (60 iteraciones) puede tardar varios
> minutos. Para un primer smoke test rápido, edita `config/train.yaml` y pon
> `hyperparam_search: { enabled: false }` antes de ejecutar.

Ejecución paso a paso (opcional):

```bash
energizados run train --step split
energizados run train --step train
```

## Paso 13. Revisar resultados

```
output/
├── index.html                    # Tabla resumen de todos los runs
└── train-YYYYMMDD_HHMM/          # Un directorio por ejecución
    ├── models/                   # feature_engineering.pkl + model.pkl
    ├── reports/evaluation/       # reporte HTML + JSON + gráficos
    ├── config/                   # copia de los YAML usados
    └── run_metadata.json         # métricas, versión, duración
```

Checklist de éxito:

- [ ] `data/processed/sample_dataset.parquet` existe
- [ ] `output/train-*/reports/evaluation/` contiene el reporte HTML
- [ ] `output/index.html` lista el run con métricas (val_auc, val_f1)

Para ver los HTML en tu máquina (Paso 3):

```bash
scp usuario@vps:~/projects/sample/output/index.html .
scp -r usuario@vps:~/projects/sample/output/train-*/reports/evaluation/ ./evaluation/
```

## Paso 14. Servir la documentación (MkDocs)

La documentación del framework está en el repo (carpeta `docs/` + `mkdocs.yml`) y se
sirve con MkDocs Material, incluido en los extras `dev`.

Desde la raíz del repositorio `Energizados/` (no dentro de `sample`), con el
entorno activado:

```bash
uv pip install -e ".[dev]"    # agrega mkdocs-material (ya lo tienes si instalaste [dev] en el Paso 6)
mkdocs serve
```

El servidor escucha en `127.0.0.1:8000` **del VPS**. Para verlo desde tu
navegador, abre un túnel SSH en otra terminal (tu máquina local):

```bash
ssh -L 8000:127.0.0.1:8000 usuario@vps
# luego abre http://localhost:8000
```

El servidor recarga automáticamente al editar archivos de `docs/`. Detén con `Ctrl+C`.

> Si el puerto 8000 está ocupado: `mkdocs serve --dev-addr 127.0.0.1:8001`
> (y tunela ese puerto). Importante: `NO_PROXY=localhost,127.0.0.1` (Paso 2)
> evita que el tráfico local se mande al proxy.

## Paso 15. Ejecutar la inferencia

Con el proyecto `sample` y al menos un run de entrenamiento terminado:

```bash
cd ~/projects/sample
energizados run infer
```

Qué hace: busca el run de entrenamiento más reciente en `output/` (o el que
indiques con `model_path` en `config/infer.yaml`), aplica el feature engineering
entrenado y puntúa el dataset de `input_path`.

Estructura generada:

```
output/
└── inference-YYYYMMDD_HHMM/
    ├── predictions.csv                      # columna probability (+ prediction si no la excluís)
    ├── predictions.csv.metadata.json        # modelo, threshold, feature engineering usados
    └── run.log
```

Ejecución por fases (opcional, si tu `infer.yaml` tiene sección `etl:`):

```bash
energizados run infer --step etl     # solo construye el dataset de inferencia
energizados run infer --step infer   # solo puntúa (el dataset debe existir)
```

> En el demo, `input_path` apunta al mismo dataset de entrenamiento: es un smoke
> test, no una evaluación real. Para inferencia real usá un dataset sin target
> (sección `etl:` de `config/infer.yaml`).

Verificación: `ls output/inference-*/` muestra `predictions.csv` y su
`.metadata.json`.

## Paso 16. Analizar las predicciones con `07_inference_analysis.ipynb`

El notebook `notebooks/07_inference_analysis.ipynb` del repo del framework analiza
la salida de una inferencia: distribución de probabilidades, curvas de threshold,
estratificación por deciles, top clientes sospechosos, patrones de consumo vs
probabilidad, zona gris (0.4–0.6) y exporta CSVs accionables. Solo usa
pandas/numpy/matplotlib/seaborn, que ya vienen con el framework.

Copiá el notebook al proyecto y apuntalo a tu inferencia:

```bash
cp ~/Energizados/notebooks/07_inference_analysis.ipynb ~/projects/sample/notebooks/
```

Abrí el notebook y editá **solo la primera celda de código (celda
"CONFIGURACIÓN")**. Las variables a ajustar:

```python
PROJECT_PATH        = Path('/home/usuario/projects/sample')  # tu proyecto
OUTPUT_PATH         = PROJECT_PATH / 'output'
VERSION             = '.'                       # demo: los runs van directo a output/
INFERENCE_DIR_NAME  = 'inference-YYYYMMDD_HHMM'  # el dir que generó el Paso 15
SEGMENT_THRESHOLDS_PATH = OUTPUT_PATH / VERSION / 'segment_thresholds_geo_region.json'
```

> Convención de paths del notebook: `INFERENCE_DIR = output/<VERSION>/<INFERENCE_DIR_NAME>`.
> En el demo los runs van directo a `output/inference-...`, por eso `VERSION = '.'`
> (pathlib colapsa el punto). Si tu proyecto organiza por versiones
> (`output/v5/inference-...`), usá `VERSION = 'v5'`. La celda también espera
> `predictions.csv.metadata.json` junto al CSV (lo genera el Paso 15) y, si lo
> configuraste, el JSON de umbrales por segmento.

Verificá el nombre exacto del run: `ls ~/projects/sample/output/ | grep inference`

Al ejecutarlo (por ejemplo en JupyterLab, accesible desde tu máquina con el
túnel SSH del Paso 3), la celda final de export genera:

```
output/<VERSION>/<INFERENCE_DIR_NAME>/analysis/
├── top_1000_suspicious.csv     # top 1000 clientes más sospechosos
├── decile_summary.csv          # resumen por decil de riesgo
└── predictions_enriched.csv    # predicciones + decil + bucket + meses en cero
```

---

## Siguientes pasos

| Acción                             | Comando                                                                      |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| Inferencia con el modelo entrenado | `energizados run infer` (Paso 15)                                            |
| Análisis post-inferencia           | Notebook `07_inference_analysis.ipynb` (Paso 16)                             |
| Scripts directos sin CLI           | `python src/run/00_etl.py`, `01_eda.py`, `02_training.py`, `03_inference.py` |
| Nombre custom de run               | `energizados run train -n mi-experimento`                                    |
| Perfil de memoria por step         | `energizados run etl,train -vv`                                              |
| Consola web (jobs async)           | `uv pip install -e ".[web]"` en el repo y luego `energizados-web` + túnel SSH (Paso 3) |
| Notebooks 01–08 del framework      | `notebooks/` del repo (data check, outliers, calibración, segmentos, SHAP, piloto) |

## Problemas frecuentes

| Síntoma                                                | Causa / solución                                                                                          |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `energizados: command not found`                       | El entorno no está activado (`source .venv/bin/activate`) o falló el `uv pip install -e .`                |
| `uv: command not found` tras instalarlo                | Abre terminal nueva o `source ~/.bashrc`; uv vive en `~/.local/bin`                                       |
| Error de versión de Python                             | Usa `uv venv --python 3.12`; el framework requiere &gt;= 3.10, &lt; 4.0                                   |
| `ModuleNotFoundError: catboost` (u xgboost/tensorflow) | Esos modelos son extras: `uv pip install -e ".[all]"` o el extra específico                               |
| `mkdocs: command not found`                            | MkDocs está en los extras dev: `uv pip install -e ".[dev]"`                                               |
| Aparece un `uv.lock` no deseado                        | Alguien corrió `uv sync`; bórralo y usa `uv pip install`                                                  |
| ETL falla por archivo de entrada                       | Ejecuta `energizados run etl` antes de `train`, y verifica `data/raw/sample_dataset.parquet`             |
| Validación bloquea por `schema_version`                | La config es más nueva que el framework: actualiza (`git pull` + reinstalar)                              |
| `curl`/`git`/`uv` no conectan en el VPS                | Proxy sin exportar: revisá el Paso 2 (`HTTP_PROXY`/`HTTPS_PROXY` en mayúsculas y minúsculas)              |
| Instalación falla con error SSL/TLS                    | El proxy intercepta TLS: `export UV_NATIVE_TLS=1`, `PIP_CERT` y `REQUESTS_CA_BUNDLE` con el CA empresa   |
| `zypper` no llega a los repos                          | Proxy limpiado por `sudo`: usá `sudo -E zypper ...` o configurá `/etc/sysconfig/proxy`                    |
| geobr: `ConnectionError: Failed to download v2 metadata`| El proxy bloquea `api.github.com` (verificado: geobr baja metadatos de ahí con TLS verificado). Pedí el desbloqueo o pre-semeá `~/.cache/geobr/` desde otro equipo |
| geobr: `Load spatial` / `httpfs` falla                  | El proxy bloquea `extensions.duckdb.org`. Semeá `~/.duckdb/extensions/` o pedí el desbloqueo (Paso 10b)  |
| Entrenamiento muere al cortarse SSH                    | Corré los pasos largos en tmux (Paso 3)                                                                   |
| No puedo abrir los reportes HTML del VPS               | El VPS no tiene navegador: descargalos con `scp`/`rsync` (Paso 3) o usá `self_contained: true`           |
| `localhost:8000` no carga con túnel SSH                | Falta `NO_PROXY=localhost,127.0.0.1` (Paso 2): el navegador local está mandando el localhost al proxy     |
