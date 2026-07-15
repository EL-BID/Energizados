# {{project_name}}
{{origin_note}}
Energy fraud detection project with Energizados Framework.

## Project Structure

```
{{project_name}}/
├── config/                 # Pipeline configurations
│   ├── etl.yaml            # ETL configuration
│   ├── train.yaml          # Training configuration (includes feature_engineering)
│   └── infer.yaml          # Inference configuration (ETL + model scoring)
├── data/                   # Project data
│   ├── raw/               # Raw data (immutable)
│   ├── processed/         # Processed data
│   └── temp/              # Temporary files (splits, cache)
├── docs/                   # Project documentation
│   └── project_docs.md    # Project-specific documentation
├── output/                 # Training run outputs (auto-created per run)
├── notebooks/              # Experimentation notebooks
│   └── example_notebook.ipynb
├── src/run/                # Execution scripts
│   ├── 00_etl.py          # Runs ETLs
│   ├── 01_eda.py          # Runs EDA
│   ├── 02_training.py     # Runs training
│   └── 03_inference.py    # Runs inference
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
python src/run/00_etl.py          # ETLs
python src/run/01_eda.py          # EDA
python src/run/02_training.py     # Training
python src/run/03_inference.py    # Inference
```

### Run the full pipeline

```bash
energizados run etl     # ETL
energizados run train   # Training
energizados run infer   # Inference (ETL + predictions)
```

### Run a specific step only

```bash
energizados run etl --step etl
energizados run train --step split
energizados run train --step training
energizados run infer --step etl    # inference dataset only
energizados run infer --step infer  # predictions only
```

### Run a specific ETL

```bash
energizados run etl --etl sample
energizados run etl --dry-run
```

### Validate configuration

```bash
energizados validate etl,train
```

### Run tests

```bash
pytest tests/
```

## Customization

### 1. Configure ETLs

Edit `config/etl.yaml` to define your ETLs:

```yaml
etl:
  schema_version: 1

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
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "left"
        on: "id_cliente"
    depends_on: ["consumos"]
```

### 2. Configure Training (includes Feature Engineering)

Edit `config/train.yaml`:

```yaml
training:
  enabled: true
  target_column: "target"
  test_size: 0.2
  val_size: 0.1

  split:
    method: "stratified"  # stratified | random | time_series | group_based | stratified_time
    test_size: 0.2
    val_size: 0.1
    # Optional: inject unlabeled negatives as target=0 (reduces selection bias)
    # unlabeled_negatives:
    #   enabled: true
    #   source_path: "data/external/unlabeled.parquet"
    #   max_per_cutoff: 1500
    # Optional: balance geographic representation in train set
    # geo_stratify:
    #   enabled: true
    #   column: "geo_region"
    #   strategy: "proportional"  # proportional | equal | capped

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

### 3. Configure Inference

Edit `config/infer.yaml`:

```yaml
infer:
  enabled: true
  input_path: "data/processed/dataset_infer.parquet"
  output_path: "output/predictions.csv"
  threshold: 0.5
  # Optional: apply per-segment thresholds from evaluation
  # segment_thresholds:
  #   enabled: true
  #   path: "output/train-YYYYMMDD_HHMM/reports/evaluation/segment_thresholds_zona.json"
  #   fallback_threshold: 0.5
```

### 4. Customize ETL

Edit `src/data/custom_etl.py` to implement your extraction,
transformation and data loading logic.

### 5. Customize Feature Engineering (optional)

Edit the `feature_engineering` section in `config/training.yaml` or create
`src/features/custom_selector.py` to implement your own feature pipeline.

### 6. Customize Model

Edit `src/models/custom_model.py` to implement your own ML model,
inheriting from `BaseModel`.

### 7. Add Utilities

Edit `src/utils/helpers.py` to add utility functions
shared between modules.

## Documentation

For more information about the Energizados framework, visit:
https://github.com/yourusername/energizados
