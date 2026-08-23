# Guía paso a paso: Energizados de cero a un modelo entrenado

Esta guía te lleva desde clonar el repositorio hasta crear y ejecutar el proyecto demo
(ETL + entrenamiento LightGBM sobre el dataset de ejemplo incluido), usando `uv` como
gestor de ambientes.

## Ruta rápida

```bash
git clone https://github.com/EL-BID/Energizados.git
cd Energizados
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e .
energizados init sample && cd sample
energizados validate etl,train
energizados run etl,train
```

Al terminar: abre `output/index.html` para ver las métricas del run.
Documentación local: `uv pip install -e ".[dev]"` en el repo y `mkdocs serve`.

---

## Paso 1. Prerrequisitos (Linux SUSE)


| Requisito   | Detalle                                                                 |
| ----------- | ----------------------------------------------------------------------- |
| SO          | Linux SUSE / openSUSE (cualquier versión reciente)                      |
| Python      | **3.12** (esta guía la fija; el framework soporta &gt;= 3.10, &lt; 4.0) |
| Git         | `sudo zypper install git` si no está                                    |
| curl o wget | `sudo zypper install curl` (o `wget`) para instalar uv                  |
| uv          | se instala en el Paso 3                                                 |
| Internet    | para clonar y descargar dependencias (numpy, lightgbm, geopandas, etc.) |


> No necesitas instalar Python 3.12 con zypper: `uv` descarga un build standalone
> de Python 3.12 y todas las dependencias del framework tienen wheels para
> Linux x86_64, así que no se requieren paquetes de sistema adicionales.

## Paso 2. Clonar el repositorio

```bash
git clone https://github.com/EL-BID/Energizados.git
cd Energizados
```

Verificación: `ls` debe mostrar `pyproject.toml`, `src/`, `tests/`, `README.md`.

## Paso 3. Instalar uv

En SUSE / openSUSE (igual que cualquier Linux):

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

## Paso 4. Crear el ambiente e instalar el framework

Desde la raíz del repositorio clonado:

```bash
# Crea .venv con Python 3.12 (lo descarga automáticamente si no existe)
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

## Paso 5. Verificar el entorno

```bash
energizados doctor
```

Confirma versión de Python y que los paquetes requeridos están presentes. Salida
sana = todos los checks en verde (exit code 0).

## Paso 6. Crear el proyecto demo

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

## Paso 7. Validar la configuración

Siempre dentro de `sample/`:

```bash
energizados validate etl,train
```

Debe reportar validación exitosa sin errores. Para ver el plan sin ejecutar nada:

```bash
energizados run etl,train --dry-run
```

## Paso 8. Ejecutar el ETL

```bash
energizados run etl
```

Qué hace: lee `data/raw/sample_dataset.parquet`, elimina filas con NULL y escribe
`data/processed/sample_dataset.parquet` (ETL `sample` de `etl.yaml`).

Verificación: `ls data/processed` muestra `sample_dataset.parquet`.

## Paso 9. Ejecutar el EDA

```bash
energizados run eda
```

Qué hace: análisis exploratorio interactivo del dataset procesado
(`data/processed/sample_dataset.parquet`): estadísticas globales, análisis por
columna, variable objetivo, importancia de features (IV, KS, Cramér's V) y
segmentación. Genera un reporte HTML autocontenido.

Verificación: `output/eda-*/` contiene `eda_report.html` (ábrela en el navegador).

## Paso 10. Ejecutar el entrenamiento

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

## Paso 11. Revisar resultados

```
output/
├── index.html                    # Tabla resumen de todos los runs (ábrela en el navegador)
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

## Paso 12. Servir la documentación (MkDocs)

La documentación del framework está en el repo (carpeta `docs/` + `mkdocs.yml`) y se
sirve con MkDocs Material, incluido en los extras `dev`.

Desde la raíz del repositorio `Energizados/` (no dentro de `sample`), con el
entorno activado:

```bash
uv pip install -e ".[dev]"    # agrega mkdocs-material (ya lo tienes si instalaste [dev] en el Paso 4)
mkdocs serve
```

Abre [http://127.0.0.1:8000](http://127.0.0.1:8000) en el navegador. El servidor recarga automáticamente
al editar archivos de `docs/`. Detén con `Ctrl+C`.

> Si el puerto 8000 está ocupado: `mkdocs serve --dev-addr 127.0.0.1:8001`.

---

## Siguientes pasos


| Acción                             | Comando                                                                      |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| Inferencia con el modelo entrenado | `energizados run infer`                                                      |
| Scripts directos sin CLI           | `python src/run/00_etl.py`, `01_eda.py`, `02_training.py`, `03_inference.py` |
| Nombre custom de run               | `energizados run train -n mi-experimento`                                    |
| Perfil de memoria por step         | `energizados run etl,train -vv`                                              |
| Consola web (jobs async)           | `uv pip install -e ".[web]"` en el repo y luego `energizados-web`            |


## Problemas frecuentes


| Síntoma                                                | Causa / solución                                                                             |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `energizados: command not found`                       | El entorno no está activado (`source .venv/bin/activate`) o falló el `uv pip install -e .`   |
| `uv: command not found` tras instalarlo                | Abre terminal nueva o `source ~/.bashrc`; uv vive en `~/.local/bin`                          |
| Error de versión de Python                             | Usa `uv venv --python 3.12`; el framework requiere &gt;= 3.10, &lt; 4.0                      |
| `ModuleNotFoundError: catboost` (u xgboost/tensorflow) | Esos modelos son extras: `uv pip install -e ".[all]"` o el extra específico                  |
| `mkdocs: command not found`                            | MkDocs está en los extras dev: `uv pip install -e ".[dev]"`                                  |
| Aparece un `uv.lock` no deseado                        | Alguien corrió `uv sync`; bórralo y usa `uv pip install`                                     |
| ETL falla por archivo de entrada                       | Ejecuta `energizados run etl` antes de `train`, y verifica `data/raw/sample_dataset.parquet` |
| Validación bloquea por `schema_version`                | La config es más nueva que el framework: actualiza (`git pull` + reinstalar)                 |


