"""YAML utilities for the Energizados framework."""

from pathlib import Path
from typing import Dict

import yaml

from energizados.core.exceptions import ConfigurationError


def load_yaml_config(path: str) -> Dict:
    """
    Load configuration from a YAML file.

    Args:
        path: Path to the YAML file

    Returns:
        Dict: Loaded configuration

    Raises:
        ConfigurationError: If the file does not exist or has format errors
    """
    config_file = Path(path)
    if not config_file.exists():
        raise ConfigurationError(f"Configuration file not found: {path}", path)

    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Error parsing YAML: {e}", path) from e
