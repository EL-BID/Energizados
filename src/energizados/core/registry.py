"""
Unified Registry abstraction for Energizados Framework.

Provides a centralized, domain-specific registry system for models,
transformers, and selectors. This unified approach reduces extension
mechanisms from multiple domain-specific registries to a single pattern.

Key design decisions (from unified-registry SDD design):
- Instance methods (not classmethods) for multiple registry instances
- Case-insensitive lookup via name.lower() for storage and retrieval
- KeyError with available names on missing get()
- Per-domain isolation (model_registry, transformer_registry, selector_registry)
"""

from typing import Dict, List


class Registry:
    """
    Centralized registry for framework components.

    Provides case-insensitive name registration and retrieval with
    clear error messages for missing entries.

    Attributes:
        name: Human-readable name for this registry (e.g., "models")
        _registry: Internal storage (name.lower() -> factory mapping)
    """

    def __init__(self, name: str) -> None:
        """
        Initialize a new registry.

        Args:
            name: Human-readable name for this registry (e.g., "models")
        """
        self.name = name
        self._registry: Dict[str, type] = {}

    def register(self, name: str, factory: type) -> None:
        """
        Register a factory under a name (case-insensitive).

        Args:
            name: Name to register the factory under
            factory: Factory class or function to register

        Note:
            If a name is already registered, it will be overwritten.
        """
        self._registry[name.lower()] = factory

    def get(self, name: str) -> type:
        """
        Get a registered factory by name (case-insensitive).

        Args:
            name: Name of the factory to retrieve

        Returns:
            type: The registered factory

        Raises:
            KeyError: If name is not registered, with helpful message
                      listing all available names
        """
        name_lower = name.lower()
        if name_lower not in self._registry:
            available = ", ".join(self._registry.keys())
            raise KeyError(
                f"'{name}' not found in {self.name} registry. " f"Available: {available}"
            )
        return self._registry[name_lower]

    def is_registered(self, name: str) -> bool:
        """
        Check if a name is registered (case-insensitive).

        Args:
            name: Name to check

        Returns:
            bool: True if name is registered, False otherwise
        """
        return name.lower() in self._registry

    def list_registered(self) -> List[str]:
        """
        List all registered names.

        Returns:
            List[str]: All registered names (lowercase, as stored)
        """
        return list(self._registry.keys())


# ---------------------------------------------------------------------------
# Per-domain registry instances
# ---------------------------------------------------------------------------

# Primary registry for machine learning models
model_registry = Registry("models")

# Placeholder registries for future migration (PR3 deferred)
# These will be populated when transformers/selectors adopt the unified pattern
transformer_registry = Registry("transformers")
selector_registry = Registry("selectors")
