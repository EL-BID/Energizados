# Documentation for {{project_name}}

## Overview

Briefly describe the purpose and objectives of this project.

## Project Structure

```
{{project_name}}/
├── config/                 # Pipeline configurations (3 files)
│   ├── etls.yaml           # ETL configuration
│   ├── training.yaml       # Training configuration (includes feature_engineering)
│   └── inference.yaml      # Inference configuration
├── data/
│   ├── raw/               # Raw data (immutable)
│   ├── processed/         # Processed data
│   └── temp/              # Temporary files
│       └── splits/        # Train/val/test splits
├── docs/                   # Project documentation
├── models/
│   └── trained/           # Trained model files
├── notebooks/              # Experimentation notebooks
├── reports/                # Reports and results
├── src/
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
│   ├── utils/             # Shared helper functions
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── run/               # Execution scripts
│       ├── 01_etl.py
│       ├── 02_training.py
│       ├── 03_evaluation.py
│       └── 04_inference.py
├── tests/                  # Test suite
│   ├── conftest.py
│   ├── test_data.py
│   ├── test_features.py
│   └── test_models.py
├── requirements.txt        # Dependencies
├── .gitignore
└── README.md
```

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Execution Scripts

The project includes scripts in `src/run/` to run each pipeline stage:

```bash
# Run ETLs
python src/run/01_etl.py

# Run training
python src/run/02_training.py

# Run evaluation
python src/run/03_evaluation.py

# Run inference
python src/run/04_inference.py
```

### Run the full pipeline with CLI

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

### Run a specific ETL

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

### Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific tests
pytest tests/test_data.py -v
```

## Customization

### 1. Configure ETLs

Edit `config/etls.yaml` to define your ETLs. See the Energizados documentation for examples.

### 2. Configure Training

Edit `config/training.yaml` to:
- Define the data split strategy (stratified, random, time_series)
- Configure preprocessing (per-column transformers)
- Configure feature selection
- Configure the model and hyperparameter search
- Configure evaluation

### 3. Customize ETL

Edit `src/data/custom_etl.py` to implement your extraction,
transformation and data loading logic.

### 4. Customize Feature Engineering

Edit `src/features/custom_selector.py` to implement your own
feature pipeline.

### 5. Customize Model

Edit `src/models/custom_model.py` to implement your own ML model,
inheriting from `BaseModel`.

### 6. Customize Inference

Edit `src/inference/custom_inference.py` to implement your
custom inference logic.

## Results

Document results here:
- Model metrics
- Comparisons between approaches
- Business insights

## References

- Energizados documentation: https://github.com/yourusername/energizados
- Example notebook: `notebooks/example_notebook.ipynb`
