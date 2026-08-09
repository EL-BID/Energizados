"""
Shared pytest fixtures for energizados tests.

Provides common fixtures for:
- Synthetic classification data
- Mock trained models
- Temporary directories
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Register test prefix for fixtures that dynamically import test classes
# This allows test fixtures to import classes with "tests." prefix while keeping
# the production default narrow (only "energizados." and "src.")
from energizados.core.utils.import_utils import register_allowed_prefix


@pytest.fixture
def synthetic_classification_data():
    """
    Generate synthetic binary classification data.

    Returns:
        tuple: (X, y) where X is DataFrame with features and y is Series with binary target
    """
    n_samples = 100
    n_features = 10

    np.random.seed(42)
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features), columns=[f"feature_{i}" for i in range(n_features)]
    )
    y = pd.Series(np.random.randint(0, 2, n_samples), name="target")

    return X, y


@pytest.fixture
def synthetic_classification_data_small():
    """
    Generate small synthetic binary classification data for quick tests.

    Returns:
        tuple: (X, y) with 20 samples
    """
    n_samples = 20
    n_features = 5

    np.random.seed(42)
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features), columns=[f"feature_{i}" for i in range(n_features)]
    )
    y = pd.Series(np.random.randint(0, 2, n_samples), name="target")

    return X, y


@pytest.fixture
def mock_trained_model():
    """
    Create a mock trained model with predict and predict_proba methods.

    Returns:
        MagicMock: A mock model that returns predictable outputs
    """
    model = MagicMock()
    model.is_fitted_ = True
    model.predict.return_value = np.array([0, 1, 0, 1, 0])
    model.predict_proba.return_value = np.array([0.3, 0.7, 0.4, 0.6, 0.2])
    return model


@pytest.fixture
def mock_trained_model_with_cols():
    """
    Create a mock trained model that works with specific column names.

    Args:
        cols: List of column names the model expects

    Returns:
        MagicMock: A mock model with proper column handling
    """

    def _make_model(cols):
        model = MagicMock()
        model.is_fitted_ = True
        model.cols_for_model = cols

        def predict(df):
            return np.ones(len(df), dtype=int)

        def predict_proba(df):
            return np.random.rand(len(df))

        model.predict = predict
        model.predict_proba = predict_proba
        return model

    return _make_model


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory that is cleaned up after the test.

    Yields:
        Path: Path to temporary directory
    """
    d = Path(tempfile.mkdtemp())
    yield d
    import shutil

    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_csv_file(temp_dir, synthetic_classification_data):
    """
    Create a CSV file with synthetic classification data.

    Args:
        temp_dir: Temporary directory fixture
        synthetic_classification_data: Data fixture

    Returns:
        Path: Path to the created CSV file
    """
    X, y = synthetic_classification_data
    df = pd.concat([X, y], axis=1)
    csv_path = temp_dir / "test_data.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def sample_parquet_file(temp_dir, synthetic_classification_data):
    """
    Create a Parquet file with synthetic classification data.

    Args:
        temp_dir: Temporary directory fixture
        synthetic_classification_data: Data fixture

    Returns:
        Path: Path to the created Parquet file
    """
    X, y = synthetic_classification_data
    df = pd.concat([X, y], axis=1)
    parquet_path = temp_dir / "test_data.parquet"
    df.to_parquet(parquet_path, index=False)
    return parquet_path


@pytest.fixture
def nn_adapter_data():
    """
    Generate data suitable for NN/LSTM adapters (features + consumption columns).

    Returns:
        tuple: (X, y, features_names, spents_names)
    """
    n_samples = 50

    np.random.seed(42)

    # Categorical/feature columns
    features_names = ["zona", "tarifa", "actividad"]
    features_data = {
        "zona": np.random.choice(["norte", "sur", "este", "oeste"], n_samples),
        "tarifa": np.random.choice(["residencial", "comercial", "industrial"], n_samples),
        "actividad": np.random.choice(["domestico", "servicios", "manufactura"], n_samples),
    }

    # Consumption columns (12 months)
    spents_names = [f"mes_{i}_anterior" for i in range(12, 0, -1)]
    spents_data = {name: np.random.uniform(100, 1000, n_samples) for name in spents_names}

    X = pd.DataFrame({**features_data, **spents_data})
    y = pd.Series(np.random.randint(0, 2, n_samples), name="target")

    return X, y, features_names, spents_names


@pytest.fixture
def e2e_synthetic_dataset():
    """Generate a synthetic dataset for E2E pipeline tests."""
    n = 100
    np.random.seed(42)

    data = {}
    for i in range(12, 0, -1):
        data[f"{i}_anterior"] = np.random.uniform(50, 1000, n)

    data["actividad"] = np.random.choice(
        ["Comercio", "Industrial", "Residencial", "Servicios", "Agricola"],
        n,
        p=[0.3, 0.2, 0.3, 0.15, 0.05],
    )
    data["tipo_tarifa"] = np.random.choice(["T1", "T2", "T3"], n, p=[0.5, 0.3, 0.2])
    data["zona"] = np.random.choice(["Norte", "Sur", "Este", "Oeste"], n)
    data["target"] = np.random.choice([0, 1], n, p=[0.8, 0.2])

    return pd.DataFrame(data)


@pytest.fixture
def e2e_project_dir(tmp_path, e2e_synthetic_dataset):
    """Create a temporary project directory structure for E2E tests."""
    for subdir in ["data/raw", "data/processed", "data/temp/splits", "output", "config"]:
        (tmp_path / subdir).mkdir(parents=True, exist_ok=True)

    e2e_synthetic_dataset.to_parquet(tmp_path / "data/raw/test_dataset.parquet", index=False)

    return tmp_path


# Register test prefix at import time
register_allowed_prefix("tests")
