# Your First Project

A detailed walkthrough of creating and running your first Energizados project.

## Step 1: Create a Project

Start by creating a new project with a descriptive name:

```bash
energizados init electricity_fraud_detection
```

This command creates a complete project structure with everything you need to get started.

## Step 2: Understanding What Was Created

Let's explore the project structure:

### Configuration Files (`config/`)

- **`etl.yaml`**: Defines your data processing pipeline. The default includes a sample ETL that removes rows with NULL values from the sample dataset.

- **`train.yaml`**: Controls the entire training pipeline:
  - **Split**: How to split data into train/val/test sets
  - **Feature Engineering**: Preprocessing transformers and feature selection
  - **Models**: Model configuration (LightGBM, CatBoost, Neural Networks, LSTM)
  - **Ensemble**: Optional ensemble configuration (stacking or soft voting)
  - **Evaluation**: Metrics, reports, and threshold settings

- **`infer.yaml`**: Configuration for running inference on new data.

- **`eda.yaml`**: Settings for exploratory data analysis.

### Data Directories

- **`data/raw/`**: Contains `sample_dataset.parquet` with 42,500 records including:
  - 12 monthly consumption columns (`12_anterior` through `1_anterior`)
  - Categorical features: `actividad`, `tipo_tarifa`, `zona`, `nivel_tension`, `material_instalacion`
  - Binary target column: `target`

- **`data/processed/`**: Where ETL outputs and processed data will be saved.

- **`data/temp/splits/`**: Where train/val/test split files will be stored.

### Output Directory (`output/`)

Created automatically during training:
- **`index.html`**: Summary of all training runs
- **`train-YYYYMMDD_HHMM/`**: Per-run results including models, reports, and plots

### Source Code (`src/`)

Contains template files for custom components:
- **`data/custom_etl.py`**: Custom ETL implementation
- **`features/custom_selector.py`**: Custom feature selector
- **`models/custom_model.py`**: Custom model class
- **`inference/custom_inference.py`**: Custom inference logic
- **`utils/helpers.py`**: Shared utility functions
- **`run/`**: Python scripts for direct pipeline execution

## Step 3: Configure the Sample ETL

Open `config/etl.yaml`. The default configuration includes:

```yaml
etl:
  sample:
    enabled: true
    description: "Procesa dataset de ejemplo (elimina filas con NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"  # 'concat' (default) or 'merge'
    depends_on: []
```

This ETL:
- Uses `SourceETL` with `mode: "concat"` to process a single input file
- Outputs to `data/processed/sample_dataset.parquet`
- Has no dependencies (`depends_on: []`)

> 💡 **Tip:** To use your own data, replace the `input` path with your data file and adjust the `output` path accordingly.

## Step 4: Run the ETL

Execute the ETL to process the sample data:

```bash
energizados run etl
```

You should see output indicating that the ETL is running and completing successfully. The processed data will be saved to `data/processed/sample_dataset.parquet`.

## Step 5: Configure Training

Open `config/train.yaml`. The default configuration uses:

- **Split method**: Time series split
- **Feature engineering**: Preprocessing with categorical encodings
- **Model**: LightGBM with undersampling
- **Evaluation**: Multiple metrics with HTML reports

### Key Configuration Sections

**Split Configuration:**

```yaml
split:
  method: "time_series"
  date_column: "fecha_inspeccion"
  train_period: ["2010-01-01", "2017-08-01"]
  val_period: ["2017-09-01", "2017-12-31"]
  test_period: ["2018-01-01"]
  save_splits: true
  splits_dir: "data/temp/splits/"
```

**Feature Engineering:**

```yaml
feature_engineering:
  enabled: true
  preprocessing:
    enabled: true
    columns:
      actividad:
        - cardinality_reducer:
            threshold: 0.001
        - to_dummy: {}
      tipo_tarifa:
        - target_encoding:
            w: 20
      zona:
        - ordinal_encoding: {}
```

**Model Configuration:**

```yaml
models:
  - type: "lightgbm"
    sampling:
      method: "undersample"
      threshold: 0.5
    hyperparams:
      num_leaves: 31
      learning_rate: 0.05
      n_estimators: 1000
```

## Step 6: Run Training

Execute training pipeline:

```bash
energizados run train
```

This will:
1. Split the data into train/val/test sets
2. Apply feature engineering (preprocessing)
3. Train the LightGBM model
4. Evaluate on the validation and test sets
5. Generate reports and plots

## Step 7: View Training Results

After training completes, check the `output/` directory:

```bash
ls output/
```

You should see:
- `index.html`: Summary table of all runs
- `train-YYYYMMDD_HHMM/`: A directory for this specific run

### Viewing the Run Directory

```bash
ls output/train-*/
```

This contains:
- **`models/`**: Trained models and feature engineering pipeline
- **`reports/evaluation/`**: HTML report, JSON report, and plots
- **`config/`**: Copies of configuration files used

### Open the Evaluation Report

Open `output/train-YYYYMMDD_HHMM/reports/evaluation/report.html` in your browser to see:
- Model metrics (AUC, Precision, Recall, F1)
- Confusion matrix
- ROC curve
- Precision-Recall curve
- Feature importance

## Step 8: Run Inference (Optional)

Once you have a trained model, you can apply it to new data:

```bash
energizados run infer
```

Make sure `config/infer.yaml` is configured with:
- `input_path`: Path to your new data
- `output_path`: Where to save predictions
- `model_path`: Path to the trained model
- `feature_engineering_path`: Path to the feature engineering pipeline

## Next Steps

Now that you've completed your first project:

1. **Replace the sample data** with your own dataset
2. **Adjust the preprocessing** in `train.yaml` to match your features
3. **Experiment with different models** (CatBoost, Neural Networks, LSTM)
4. **Try ensemble methods** (stacking or soft voting)
5. **Use the EDA module** to explore your data:
   ```bash
   energizados run eda
   ```

---

← [Quick Start](quickstart.md) | [Project Structure](../user-guide/project-structure.md) →
