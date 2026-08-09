"""
Tests for import utilities - framework-web-ready Phase 2: Import Safety Hardening.

Tests for narrowed ALLOWED_PREFIXES and register_allowed_prefix() function.
"""

import pytest

from energizados.core.exceptions import ConfigurationError
from energizados.core.utils.import_utils import import_class, register_allowed_prefix


class TestImportSafetyHardening:
    """framework-web-ready Phase 2: Narrow ALLOWED_PREFIXES and add extension function."""

    def test_allowed_prefixes_is_narrowed_set(self):
        """ALLOWED_PREFIXES is narrowed to set with only energizados. and src."""
        # Check source code to verify default value
        import inspect

        import energizados.core.utils.import_utils as import_utils_module

        # Get the source code
        source = inspect.getsource(import_utils_module)

        # Check that the default definition in source code is narrow
        assert (
            "ALLOWED_PREFIXES: Set[str] = {" in source
        ), "ALLOWED_PREFIXES should be defined as Set[str]"
        assert '"energizados.",' in source, "Default should include 'energizados.'"
        assert '"src.",' in source, "Default should include 'src.'"

        # Verify the runtime value is a set
        from energizados.core.utils.import_utils import ALLOWED_PREFIXES

        assert isinstance(ALLOWED_PREFIXES, set), "ALLOWED_PREFIXES should be a set"

        # Check that it contains at least the required defaults (it may have more due to conftest.py)
        assert "energizados." in ALLOWED_PREFIXES, "Should contain 'energizados.'"
        assert "src." in ALLOWED_PREFIXES, "Should contain 'src.'"

    def test_import_class_blocked_prefix_raises_configuration_error(self):
        """Importing class from blocked prefix raises ConfigurationError with specific error_code."""
        with pytest.raises(ConfigurationError) as exc_info:
            import_class("dangerous.EvilClass")

        assert exc_info.value.error_code == "CONFIG_INVALID_CLASS_PREFIX"
        assert "dangerous.EvilClass" in str(exc_info.value)
        assert "energizados." in str(exc_info.value) or "src." in str(exc_info.value)

    def test_register_allowed_prefix_adds_to_set(self):
        """register_allowed_prefix() adds prefix to ALLOWED_PREFIXES set."""
        from energizados.core.utils.import_utils import ALLOWED_PREFIXES

        initial_size = len(ALLOWED_PREFIXES)
        register_allowed_prefix("custom")
        assert len(ALLOWED_PREFIXES) == initial_size + 1
        assert "custom." in ALLOWED_PREFIXES

    def test_register_allowed_prefix_adds_trailing_dot(self):
        """register_allowed_prefix() adds trailing dot if missing."""
        from energizados.core.utils.import_utils import ALLOWED_PREFIXES

        register_allowed_prefix("ml_models")
        assert "ml_models." in ALLOWED_PREFIXES

    def test_register_allowed_prefix_existing_prefix_works(self):
        """After registering prefix, import from that prefix succeeds."""
        from energizados.core.utils.import_utils import ALLOWED_PREFIXES

        # Register a test prefix
        if "test_module." in ALLOWED_PREFIXES:
            ALLOWED_PREFIXES.remove("test_module.")

        register_allowed_prefix("test_module")

        # This will still fail because the module doesn't exist, but it should
        # get past the prefix check and raise ImportError for different reason
        with pytest.raises(ImportError) as exc_info:
            import_class("test_module.NonExistentClass")

        # Should not be ConfigurationError (passed prefix check)
        assert "Cannot import class" in str(exc_info.value)

    def test_energizados_prefix_still_works(self):
        """Existing 'energizados.' prefix still works after narrowing."""
        # This should work - importing a real class from framework
        from energizados.core.base import BaseModel

        cls = import_class("energizados.core.base.BaseModel")
        assert cls is BaseModel

    def test_src_prefix_still_works(self):
        """Existing 'src.' prefix still works after narrowing."""
        # This will fail because module doesn't exist, but should pass prefix check
        with pytest.raises(ImportError) as exc_info:
            import_class("src.models.CustomModel")
        # Should be regular ImportError, not ConfigurationError
        assert "Cannot import class" in str(exc_info.value)
