# {{project_name}}
{{origin_note}}
Proyecto de detección de fraude energético con Energizados Framework.

## Estructura del Proyecto

```
{{project_name}}/
├── config/                 # Configuraciones del pipeline
│   └── pipeline.yaml       # Configuración principal
├── data/                   # Datos del proyecto
│   ├── raw/               # Datos crudos (inmutables)
│   ├── processed/         # Datos procesados
│   └── external/          # Datos externos
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

### Ejecutar el pipeline completo

```bash
energizados run --config config/pipeline.yaml
```

### Ejecutar solo un paso específico

```bash
energizados run --config config/pipeline.yaml --step etl
energizados run --config config/pipeline.yaml --step training
```

### Ejecutar una ETL específica (con múltiples ETLs)

```bash
# Ejecutar una ETL y sus dependencias
energizados run --config config/pipeline.yaml --etl merge_etl

# Ver plan de ejecución sin ejecutar
energizados run --config config/pipeline.yaml --dry-run
```

### Validar configuración

```bash
energizados validate --config config/pipeline.yaml
```

### Ejecutar tests

```bash
pytest tests/
```

## Personalización

### 1. Personalizar ETL

Edita `src/data/custom_etl.py` para implementar tu lógica de extracción,
transformación y carga de datos.

**Soporta múltiples fuentes de datos:**
- Archivo único: `input: "data/file.csv"`
- Múltiples archivos: `input: ["file1.csv", "file2.csv"]`
- Glob pattern: `input: "data/raw/*.csv"`
- Referencia a otra ETL: `input: "@otra_etl"`

### 2. Configurar Múltiples ETLs

Edita `config/pipeline.yaml` y usa la sección `etls` en lugar de `etl`:

```yaml
etls:
  consumos:
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    depends_on: []

  merge:
    input:
      - "@consumos"
      - "data/raw/clientes.csv"
    output: "data/processed/merged.parquet"
    depends_on: ["consumos"]
```

### 3. Personalizar Feature Selection (opcional)

Edita `src/features/custom_selector.py` para implementar tu propia
lógica de selección de variables.

### 4. Personalizar Modelo

Edita `src/models/custom_model.py` para implementar tu propio modelo
de ML, heredando de `BaseModel`.

### 5. Agregar Utilidades

Edita `src/utils/helpers.py` para agregar funciones utilitarias
compartidas entre módulos.

## Documentación

Para más información sobre el framework Energizados, visita:
https://github.com/yourusername/energizados
