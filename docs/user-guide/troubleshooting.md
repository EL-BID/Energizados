# Troubleshooting

Common issues and solutions for Energizados.

## `energizados` not found in PATH

### Symptom

```bash
bash: energizados: command not found
```

### Solutions by Operating System

#### macOS / Linux

1. Verify the virtual environment is activated:

```bash
which energizados  # Should show path inside venv
```

2. If not in PATH, verify installation:

```bash
pip show energizados  # Should show package location
```

3. Reinstall if necessary:

```bash
pip uninstall energizados
pip install energizados
```

#### Windows

1. Verify the virtual environment is activated:

```cmd
where energizados  # Should show path inside venv
```

2. If not in PATH, verify installation:

```cmd
pip show energizados
```

3. Reinstall if necessary:

```cmd
pip uninstall energizados
pip install energizados
```

4. If persistent, ensure the `Scripts` folder of your venv is in the Windows PATH.

---

## Python Version Conflicts

### Symptom

Installation error indicating package requires Python >= 3.10

### Solutions

1. Check your Python version:

```bash
python --version
```

2. If you have multiple Python versions, use the correct one explicitly:

- **macOS / Linux**: `python3.11 --version`, `python3.11 -m pip install energizados`
- **Windows**: `py -3.11 --version`, `py -3.11 -m pip install energizados`

3. Consider using a Python version manager:

- **pyenv** (macOS/Linux): `pyenv install 3.11.0 && pyenv global 3.11.0`
- **pyenv-win** (Windows): Install from [pyenv-win](https://github.com/pyenv-win/pyenv-win)

---

## CatBoost Installation Errors

### Symptom

Error installing `energizados[catboost]`

### Solutions by Operating System

#### macOS

CatBoost may require compilation. Ensure you have development tools:

```bash
xcode-select --install
```

#### Linux

Install compilation dependencies if needed:

```bash
# Ubuntu/Debian
sudo apt install build-essential

# Fedora
sudo dnf install gcc-c++ make
```

#### Windows

CatBoost has precompiled binaries for Windows. If errors occur:

- Ensure Visual C++ Redistributable is installed
- Try installing catboost directly:

```cmd
pip install catboost==1.2.8
```

---

## TensorFlow Installation Errors

### Symptom

Error installing `energizados[tensorflow]`

### Solutions by Operating System

#### macOS (M1/M2/M3 Apple Silicon)

TensorFlow for macOS ARM requires a specific version:

```bash
pip install tensorflow-macos
```

#### Linux

TensorFlow requires CUDA for GPU support. For CPU only:

```bash
pip install tensorflow-cpu>=2.10.0
```

#### Windows

TensorFlow has limited Windows support. Use CPU version:

```cmd
pip install tensorflow-cpu>=2.10.0
```

---

## ETL Execution Errors

### Symptom

ETL fails to execute

### Solutions

1. Check input file paths:

```bash
ls -la data/raw/  # Verify input files exist
```

2. Validate configuration:

```bash
energizados validate config/etl.yaml -v
```

3. Run with verbose output:

```bash
energizados run etl -vv
```

4. Check for circular dependencies in `depends_on`:

```yaml
# ❌ This causes a circular dependency
etl:
  a:
    depends_on: ["b"]
  b:
    depends_on: ["a"]
```

---

## Training Errors

### Symptom

Training fails during execution

### Solutions

1. Verify input data exists:

```bash
ls -la data/processed/  # Check ETL output
```

2. Validate training configuration:

```bash
energizados validate train -v
```

3. Check target column exists:

```python
import pandas as pd
df = pd.read_parquet("data/processed/dataset.parquet")
print(df.columns)  # Verify target_column is present
```

4. Run with debug logging:

```bash
energizados run train -vvv
```

### Common Training Issues

**Issue:** `ValueError: Target column not found`

**Solution:** Ensure `target_column` in `train.yaml` matches the exact column name in your data (case-sensitive).

**Issue:** `KeyError: Column not found` during preprocessing

**Solution:** Remove or rename columns that don't exist from `feature_engineering.preprocessing.columns`.

**Issue:** Out of memory during training

**Solution:** Reduce `hyperparams.n_estimators` or decrease dataset size.

---

## Evaluation Errors

### Symptom

Evaluation fails or produces unexpected results

### Solutions

1. Ensure model was trained successfully:

```bash
ls -la output/train-*/models/  # Check model files exist
```

2. Check metrics list is valid:

```yaml
evaluation:
  metrics: [auc, precision, recall, f1]  # Valid metrics only
```

3. Verify threshold calibration parameters:

```yaml
calibration:
  enabled: true
  method: "cost_benefit"  # Must be: cost_benefit, operational, precision_recall
  params:
    cost_fp: 1  # Required for cost_benefit
    cost_fn: 10
```

---

## Inference Errors

### Symptom

Inference fails to produce predictions

### Solutions

1. Verify model path is correct:

```bash
# Single model
ls -la output/train-*/models/model.pkl

# Ensemble
ls -la output/train-*/models/ensemble.pkl
```

2. Check feature engineering pipeline exists:

```bash
ls -la output/train-*/models/feature_engineering.pkl
```

3. Ensure input data has correct schema:

```python
import pandas as pd
df = pd.read_parquet("data/new_data.parquet")
print(df.columns.tolist())  # Should match training data columns
```

4. Verify threshold is between 0 and 1:

```yaml
infer:
  threshold: 0.5  # Must be 0.0 to 1.0
```

---

## General Troubleshooting Tips

### 1. Check the Environment

```bash
energizados doctor
```

This checks:
- Python version
- Installed packages
- Optional dependencies
- System information

### 2. Validate Configuration

```bash
energizados validate config/etl.yaml,config/train.yaml -v
```

This verifies:
- YAML syntax
- Required fields
- Valid parameter values
- File paths existence

### 3. Increase Verbosity

Add `-v`, `-vv`, or `-vvv` to commands to see more debug information:

```bash
energizados run train -vv
```

Verbosity levels:
- `-v`: INFO level logging
- `-vv` or `-vvv`: DEBUG level logging

### 4. Dry Run

Check the execution plan without running:

```bash
energizados run etl --dry-run
```

### 5. Common Issues Checklist

- [ ] Virtual environment is activated
- [ ] Configuration files are in correct paths
- [ ] Input data files exist and are readable
- [ ] Python version meets requirements (>= 3.10)
- [ ] Sufficient disk space for outputs
- [ ] Required optional packages are installed for the models you're using
- [ ] No circular dependencies in ETL `depends_on` lists
- [ ] Target column exists in input data
- [ ] Model files exist in output directory

---

## Getting Help

If you're still experiencing issues:

1. **Check the documentation:** https://energizados.readthedocs.io
2. **Search existing issues:** https://github.com/energizados/energizados/issues
3. **Report a new issue:** https://github.com/energizados/energizados/issues/new

When reporting an issue, include:

- Python version: `python --version`
- Energizados version: `energizados --version`
- Operating system
- Error message (full traceback)
- Configuration files (sanitized)
- Steps to reproduce

---

← [Configuration: Inference](configuration/infer.md) | [Getting Started](../getting-started/installation.md) →
