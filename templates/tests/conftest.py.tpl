"""
Pytest configuration and fixtures for {{project_name}}.

Este archivo contiene las configuraciones y fixtures compartidas
para todos los tests del proyecto.
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_data():
    """
    Dataset de ejemplo para tests.

    Returns:
        pd.DataFrame: DataFrame con datos de prueba
    """
    return pd.DataFrame({
        'feature1': [1, 2, 3, 4, 5],
        'feature2': ['a', 'b', 'a', 'b', 'a'],
        'feature3': [10.5, 20.3, 15.1, 25.0, 12.8],
        'target': [0, 1, 0, 1, 1]
    })


@pytest.fixture
def sample_model():
    """
    Modelo de ejemplo para tests.

    Returns:
        Modelo de scikit-learn configurado
    """
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=10,
        max_depth=3,
        random_state=42
    )


@pytest.fixture
def project_root():
    """
    Ruta al directorio raíz del proyecto.

    Returns:
        Path: Ruta al directorio raíz
    """
    return Path(__file__).parent.parent


@pytest.fixture
def data_dir(project_root):
    """
    Ruta al directorio de datos.

    Returns:
        Path: Ruta al directorio de datos
    """
    return project_root / "data"


@pytest.fixture
def config_dir(project_root):
    """
    Ruta al directorio de configuración.

    Returns:
        Path: Ruta al directorio de configuración
    """
    return project_root / "config"
