# Documentación de {{project_name}}

## Overview

Describe brevemente el propósito y objetivos de este proyecto.

## Estructura del Proyecto

```
src/
├── data/          # ETL, preprocessing y carga de datos
├── features/      # Feature engineering y selección
├── models/        # Definiciones y entrenamiento de modelos
├── inference/     # Inferencia y predicciones
└── utils/         # Funciones auxiliares compartidas

tests/             # Suite de tests
config/            # Configuración de pipelines
data/              # Almacenamiento de datos
models/            # Modelos entrenados (archivos)
docs/              # Documentación adicional
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

### Entrenamiento

```bash
energizados run --config config/pipeline.yaml
```

### Inferencia

```bash
python -m src.inference.custom_inference --model models/trained/model.pkl --input data/processed/test.parquet
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

## Resultados

Documenta aquí los resultados obtenidos:
- Métricas de los modelos
- Comparaciones entre enfoques
- Insights del negocio

## Referencias

- Documentación de Energizados: https://github.com/yourusername/energizados
- Notebook de ejemplo: `notebooks/example_notebook.ipynb`
