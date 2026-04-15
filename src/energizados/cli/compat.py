"""Project compatibility checker for Energizados CLI.

Validates that the current framework version is compatible with
the schema_version declared inside each config section (etl, train, eda, infer).
"""

import logging
from typing import Any, Dict

from energizados._version import (
    CURRENT_SCHEMA_VERSIONS,
    SCHEMA_VERSION_KEY,
    get_version,
)
from energizados.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Maps config root keys to their config type for schema lookup
_SECTION_TO_TYPE = {
    "etl": "etl",
    "train": "train",
    "training": "train",
    "eda": "eda",
    "infer": "infer",
}


def check_project_compatibility(merged_config: Dict[str, Any]) -> None:
    """Check that each config section's schema_version is supported.

    Iterates over known config sections in the merged config and validates
    that their schema_version does not exceed what the framework supports.
    Missing schema_version is silently accepted (backwards compat).

    Args:
        merged_config: The merged configuration dictionary from all YAML files.

    Raises:
        ConfigurationError: If any section's schema_version is newer than supported.
    """
    if not merged_config:
        return

    framework_version = get_version()

    for section_key, config_type in _SECTION_TO_TYPE.items():
        section = merged_config.get(section_key)
        if not isinstance(section, dict):
            continue

        project_schema = section.get(SCHEMA_VERSION_KEY)
        if project_schema is None:
            logger.debug("Section '%s' has no %s — skipping check", section_key, SCHEMA_VERSION_KEY)
            continue

        supported = CURRENT_SCHEMA_VERSIONS.get(config_type)
        if supported is None:
            continue

        if project_schema > supported:
            raise ConfigurationError(
                f"Config section '{section_key}' requires schema version {project_schema}, "
                f"but the installed energizados ({framework_version}) only supports "
                f"up to schema version {supported} for '{config_type}'. "
                f"Update the framework: pip install --upgrade energizados",
            )

        if project_schema < supported:
            logger.warning(
                "Config section '%s' uses schema version %d, "
                "but the framework supports version %d. "
                "Consider updating your config file.",
                section_key,
                project_schema,
                supported,
            )

        logger.debug(
            "Schema check OK for '%s': project=%d, supported=%d",
            section_key,
            project_schema,
            supported,
        )
