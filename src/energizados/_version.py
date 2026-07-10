"""Centralized version access for the Energizados framework."""

import importlib.metadata

__version__ = "0.3.0"

# Reserved key used inside each config section to track schema evolution.
SCHEMA_VERSION_KEY = "schema_version"

# Current schema version per config type.
# Each config evolves independently. Increment ONLY on breaking changes
# to that specific config's structure.
CURRENT_SCHEMA_VERSIONS = {
    "etl": 1,
    "train": 2,  # 2: added segmented_evaluation with threshold modes and column combinations
    "eda": 1,
    "infer": 1,
}


def get_version() -> str:
    """Return the installed energizados version, or 'unknown' as fallback."""
    try:
        return importlib.metadata.version("energizados")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"
