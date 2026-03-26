# {{project_name}}
{{origin_note}}
Energy fraud detection project with Energizados Framework.

## Project Structure

```
{{project_name}}/
├── config/                 # Pipeline configurations (3 files)
│   ├── etls.yaml           # ETL configuration
│   ├── training.yaml       # Training configuration (includes feature_engineering)
│   └── inference.yaml      # Inference configuration
├── data/                   # Project data
│   ├── raw/               # Raw data (immutable)
│   ├── processed/         # Processed data
│   └── splits/            # Train/val/test splits
├── docs/                   # Project documentation
│   └── project_docs.md    # Project-specific documentation
├── models/                 # Trained model files
│   └── trained/           # Saved models
├── notebooks/              # Experimentation notebooks
│   └── example_notebook.ipynb
├── reports/                # Reports and results
├── src/run/                # Execution scripts
│   ├── 01_etl.py          # Runs ETLs
│   ├── 02_training.py     # Runs training
│   ├── 03_evaluation.py   # Runs evaluation
│   └── 04_inference.py    # Runs inference
├── src/                    # Source code
│   ├── data/              # ETL and preprocessing
│   │   ├── __init__.py
│   │   └── custom_etl.py
│   ├── features/          # Feature engineering
│   │   ├── __init__.py
│   │   └── custom_selector.py
│   ├── models/            # Model definitions
│   │   ├── __init__.py
│   │   └── custom_model.py
│   ├── inference/         # Inference
│   │   ├── __init__.py
│   │   └── custom_inference.py
│   └── utils/             # Shared utilities
│       ├── __init__.py
│       └── helpers.py
├── tests/                  # Tests
│   ├── conftest.py        # pytest configuration
│   ├── test_data.py       # ETL tests
│   ├── test_features.py   # Feature tests
│   └── test_models.py     # Model tests
├── requirements.txt        # Dependencies
├── .gitignore
└── README.md
```

## Usage

> **Note:** This project includes a sample dataset at `data/raw/sample_dataset.parquet`
> that you can use to test the pipeline immediately.

### Run Scripts

The project includes scripts in the `src/run/` directory to run each stage:

```bash
# Run a specific stage
python src/run/01_etl.py          # ETLs
python src/run/02_training.py     # Training
python src/run/03_evaluation.py   # Evaluation
python src/run/04_inference.py    # Inference
```

### Run the full pipeline

```bash
energizados run \
  --config config/etls.yaml \
  --config config/training.yaml
```

### Run a specific step only

```bash
# Run ETLs only
energizados run --config config/etls.yaml --step etl

# Run Split only
energizados run --config config/training.yaml --step split

# Run Training only
energizados run --config config/training.yaml --step training
```

### Run a specific ETL (with multiple ETLs)

```bash
# Run an ETL and its dependencies
energizados run --config config/etls.yaml --etl sample

# View execution plan without running
energizados run --config config/etls.yaml --dry-run
```

### Validate configuration

```bash
# Validate a single file
energizados validate --config config/etls.yaml

# Validate multiple files
energizados validate \
  --config config/etls.yaml \
  --config config/training.yaml
```

### Run tests

```bash
pytest tests/
```

## Customization

### 1. Configure ETLs

Edit `config/etls.yaml` to define your ETLs:

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
      - "@consumos"  # Reference to consumos output
      - "data/raw/clientes.csv"
    output: "data/processed/merged.parquet"
    custom_class: "energizados.etl.pipeline.MultiSourceETL"
    depends_on: ["consumos"]
```

### 2. Configure Training (includes Feature Engineering)

Edit `config/training.yaml`:

```yaml
training:
  enabled: true
  target_column: "target"
  test_size: 0.2
  val_size: 0.1

  feature_engineering:
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

  model:
    model_type: "lightgbm"
    params:
      n_estimators: 100
```

### 3. Customize ETL

Edit `src/data/custom_etl.py` to implement your extraction,
transformation and data loading logic.

### 4. Customize Feature Engineering (optional)

Edit the `feature_engineering` section in `config/training.yaml` or create
`src/features/custom_selector.py` to implement your own feature pipeline.

### 5. Customize Model

Edit `src/models/custom_model.py` to implement your own ML model,
inheriting from `BaseModel`.

### 6. Add Utilities

Edit `src/utils/helpers.py` to add utility functions
shared between modules.

## Documentation

For more information about the Energizados framework, visit:
https://github.com/yourusername/energizados
