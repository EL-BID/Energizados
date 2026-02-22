# {{project_name}}
{{origin_note}}
Proyecto de detección de fraude energético con Energizados Framework.

## Estructura del Proyecto

```
{{project_name}}/
├── config/                 # Configuraciones del pipeline (4 archivos)
│   ├── etls.yaml           # Configuración de ETLs
│   ├── feature_pipeline.yaml # Preprocessing + Feature Selection
│   ├── training.yaml       # Configuración de entrenamiento
│   └── inference.yaml      # Configuración de inferencia
├── data/                   # Datos del proyecto
│   ├── raw/               # Datos crudos (inmutables)
│   └── processed/         # Datos procesados
├── docs/                   # Documentación del proyecto
│   └── project_docs.md    # Documentación específica
├── models/                 # Modelos entrenados (archivos)
│   └── trained/           # Modelos guardados
├── notebooks/              # Notebooks de experimentación
│   └── example_notebook.ipynb
├── reports/                # Reportes y resultados
├── src/                    # Código fuente
│   ├── data/              # ETL y preprocessing
│   │   ├── __init__.py
│   │   └── custom_etl.py
│   ├── features/          # Feature engineering
│   │   ├── __init__.py
│   │   └── custom_selector.py
│   ├── models/            # Definiciones de modelos
│   │   ├── __init__.py
│   │   └── custom_model.py
│   ├── inference/         # Inferencia
│   │   ├── __init__.py
│   │   └── custom_inference.py
│   └── utils/             # Utilidades compartidas
│       ├── __init__.py
│       └── helpers.py
├── tests/                  # Tests
│   ├── conftest.py        # Configuración pytest
│   ├── test_data.py       # Tests de ETL
│   ├── test_features.py   # Tests de features
│   └── test_models.py     # Tests de modelos
├── requirements.txt        # Dependencias
├── .gitignore
└── README.md
```

## Uso

> **Nota:** Este proyecto incluye un dataset de ejemplo en `data/raw/sample_dataset.parquet`
> que puedes usar para probar el pipeline inmediatamente.

### Ejecutar el pipeline completo

```bash
energizados run \
  --config config/etls.yaml \
  --config config/feature_pipeline.yaml \
  --config config/training.yaml
```

### Ejecutar solo un paso específico

```bash
# Ejecutar solo ETLs
energizados run --config config/etls.yaml --step etl

# Ejecutar solo Feature Pipeline
energizados run --config config/feature_pipeline.yaml --step feature_pipeline

# Ejecutar solo Training
energizados run --config config/training.yaml --step training
```

### Ejecutar una ETL específica (con múltiples ETLs)

```bash
# Ejecutar una ETL y sus dependencias
energizados run --config config/etls.yaml --etl sample

# Ver plan de ejecución sin ejecutar
energizados run --config config/etls.yaml --dry-run
```

### Validar configuración

```bash
# Validar un solo archivo
energizados validate --config config/etls.yaml

# Validar múltiples archivos
energizados validate \
  --config config/etls.yaml \
  --config config/feature_pipeline.yaml
```

### Ejecutar tests

```bash
pytest tests/
```

## Personalización

### 1. Configurar ETLs

Edita `config/etls.yaml` para definir tus ETLs:

```yaml
etls:
  consumos:
    enabled: true
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: []

  merge:
    enabled: true
    input:
      - "@consumos"  # Referencia al output de consumos
      - "data/raw/clientes.csv"
    output: "data/processed/merged.parquet"
    custom_class: "energizados.etl.pipeline.MultiSourceETL"
    depends_on: ["consumos"]
```

### 2. Configurar Feature Pipeline

Edita `config/feature_pipeline.yaml`:

```yaml
feature_pipeline:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  output_pkl: "data/processed/feature_pipeline.pkl"
  output_parquet: "data/processed/feature_pipeline.parquet"

  preprocessing:
    columns:
      actividad:
        - cardinality_reducer:
            threshold: 0.001
        - to_dummy: {}
      tipo_tarifa:
        - cardinality_reducer:
            threshold: 0.001
        - target_encoding:
            w: 20
      nivel_tension:
        - ordinal_encoding: {}
      zona:
        - ordinal_encoding: {}

  feature_selection:
    enabled: true
    method: "boruta"
    params:
      n_estimators: 100
```

### 3. Personalizar ETL

Edita `src/data/custom_etl.py` para implementar tu lógica de extracción,
transformación y carga de datos.

### 4. Personalizar Feature Pipeline (opcional)

Crea `src/feature_pipeline/custom_pipeline.py` para implementar tu propio
pipeline de características, heredando de `BaseFeaturePipeline`.

### 5. Personalizar Modelo

Edita `src/models/custom_model.py` para implementar tu propio modelo
de ML, heredando de `BaseModel`.

### 6. Agregar Utilidades

Edita `src/utils/helpers.py` para agregar funciones utilitarias
compartidas entre módulos.

## Documentación

Para más información sobre el framework Energizados, visita:
https://github.com/yourusername/energizados
