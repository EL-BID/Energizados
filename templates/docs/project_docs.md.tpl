# Documentación de {{project_name}}

## Overview

Describe brevemente el propósito y objetivos de este proyecto.

## Estructura del Proyecto

```
{{project_name}}/
├── config/                 # Configuraciones del pipeline (3 archivos)
│   ├── etls.yaml           # Configuración de ETLs
│   ├── training.yaml       # Configuración de entrenamiento (incluye feature_engineering)
│   └── inference.yaml      # Configuración de inferencia
├── data/
│   ├── raw/               # Datos crudos (inmutables)
│   ├── processed/         # Datos procesados
│   └── splits/            # Splits de train/val/test
├── docs/                   # Documentación del proyecto
├── models/
│   └── trained/           # Modelos entrenados (archivos)
├── notebooks/              # Notebooks de experimentación
├── reports/                # Reportes y resultados
├── src/
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
│   ├── utils/             # Funciones auxiliares compartidas
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── run/               # Scripts de ejecución
│       ├── 01_etl.py
│       ├── 02_training.py
│       ├── 03_evaluation.py
│       └── 04_inference.py
├── tests/                  # Suite de tests
│   ├── conftest.py
│   ├── test_data.py
│   ├── test_features.py
│   └── test_models.py
├── requirements.txt        # Dependencias
├── .gitignore
└── README.md
```

## Instalación

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## Uso

### Scripts de Ejecución

El proyecto incluye scripts en `src/run/` para ejecutar cada etapa del pipeline:

```bash
# Ejecutar ETLs
python src/run/01_etl.py

# Ejecutar entrenamiento
python src/run/02_training.py

# Ejecutar evaluación
python src/run/03_evaluation.py

# Ejecutar inferencia
python src/run/04_inference.py
```

### Ejecutar el pipeline completo con CLI

```bash
energizados run \
  --config config/etls.yaml \
  --config config/training.yaml
```

### Ejecutar solo un paso específico

```bash
# Ejecutar solo ETLs
energizados run --config config/etls.yaml --step etl

# Ejecutar solo Split
energizados run --config config/training.yaml --step split

# Ejecutar solo Training
energizados run --config config/training.yaml --step training
```

### Ejecutar una ETL específica

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
  --config config/training.yaml
```

### Tests

```bash
# Ejecutar todos los tests
pytest tests/

# Ejecutar con cobertura
pytest --cov=src tests/

# Ejecutar tests específicos
pytest tests/test_data.py -v
```

## Personalización

### 1. Configurar ETLs

Edita `config/etls.yaml` para definir tus ETLs. Consulta la documentación de Energizados para ejemplos.

### 2. Configurar Training

Edita `config/training.yaml` para:
- Definir la estrategia de split de datos (stratified, random, time_series)
- Configurar preprocessing (transformers por columna)
- Configurar feature selection
- Configurar el modelo y búsqueda de hiperparámetros
- Configurar evaluación

### 3. Personalizar ETL

Edita `src/data/custom_etl.py` para implementar tu lógica de extracción,
transformación y carga de datos.

### 4. Personalizar Feature Engineering

Edita `src/features/custom_selector.py` para implementar tu propio pipeline
de características.

### 5. Personalizar Modelo

Edita `src/models/custom_model.py` para implementar tu propio modelo
de ML, heredando de `BaseModel`.

### 6. Personalizar Inferencia

Edita `src/inference/custom_inference.py` para implementar tu lógica
de inferencia personalizada.

## Resultados

Documenta aquí los resultados obtenidos:
- Métricas de los modelos
- Comparaciones entre enfoques
- Insights del negocio

## Referencias

- Documentación de Energizados: https://github.com/yourusername/energizados
- Notebook de ejemplo: `notebooks/example_notebook.ipynb`
