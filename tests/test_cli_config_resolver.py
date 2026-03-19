"""
Unit tests for config_resolver module.

Tests for resolving config names to file paths, error handling,
and config directory discovery.
"""

import tempfile
from pathlib import Path

import pytest

from energizados.cli.config_resolver import (
    ConfigResolutionError,
    _discover_config_dir,
    _list_available_configs,
    _resolve_single,
    resolve_configs,
)


class TestConfigResolver:
    """Tests for resolve_configs function."""

    def test_resolve_single_short_name(self):
        """Verify that a single short name resolves correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").touch()

            result = resolve_configs("etl", config_dir)
            assert len(result) == 1
            assert result[0] == str((config_dir / "etl.yaml").absolute())

    def test_resolve_comma_separated_names(self):
        """Verify that comma-separated names resolve correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").touch()
            (config_dir / "train.yaml").touch()

            result = resolve_configs("etl,train", config_dir)
            assert len(result) == 2
            assert result[0] == str((config_dir / "etl.yaml").absolute())
            assert result[1] == str((config_dir / "train.yaml").absolute())

    def test_resolve_with_whitespace(self):
        """Verify that whitespace around names is handled correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").touch()
            (config_dir / "train.yaml").touch()

            result = resolve_configs("etl , train", config_dir)
            assert len(result) == 2
            assert result[0] == str((config_dir / "etl.yaml").absolute())

    def test_resolve_trailing_comma(self):
        """Verify that trailing comma is ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").touch()

            result = resolve_configs("etl,", config_dir)
            assert len(result) == 1
            assert result[0] == str((config_dir / "etl.yaml").absolute())

    def test_resolve_empty_string_raises_error(self):
        """Verify that empty string raises ValueError."""
        with pytest.raises(ValueError, match="At least one config name is required"):
            resolve_configs("", None)

    def test_resolve_comma_only_raises_error(self):
        """Verify that comma-only string raises ValueError."""
        with pytest.raises(ValueError, match="At least one config name is required"):
            resolve_configs(",", None)

    def test_resolve_with_extension(self):
        """Verify that .yaml extension is treated as passthrough path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in CWD (not in config/)
            config_file = Path(tmpdir) / "etl.yaml"
            config_file.touch()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Since it ends with .yaml, it should be treated as passthrough
                # and looked up from CWD, not from config_dir
                result = resolve_configs("etl.yaml", None)
                assert len(result) == 1
                assert result[0] == str(config_file.absolute())
            finally:
                os.chdir(old_cwd)

    def test_resolve_with_yml_extension(self):
        """Verify that .yml extension is treated as passthrough path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config in CWD (not in config/)
            config_file = Path(tmpdir) / "etl.yml"
            config_file.touch()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # Since it ends with .yml, it should be treated as passthrough
                # and looked up from CWD, not from config_dir
                result = resolve_configs("etl.yml", None)
                assert len(result) == 1
                assert result[0] == str(config_file.absolute())
            finally:
                os.chdir(old_cwd)

    def test_resolve_absolute_path_passthrough(self):
        """Verify that absolute paths are passed through unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom.yaml"
            config_file.touch()

            result = resolve_configs(str(config_file), None)
            assert len(result) == 1
            assert result[0] == str(config_file.absolute())

    def test_resolve_relative_path_passthrough(self):
        """Verify that relative paths are resolved from CWD."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom.yaml"
            config_file.touch()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = resolve_configs("custom.yaml", None)
                assert len(result) == 1
                assert result[0] == str(config_file.absolute())
            finally:
                os.chdir(old_cwd)

    def test_resolve_path_with_slash_passthrough(self):
        """Verify that paths containing '/' are passed through unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            config_file = subdir / "custom.yaml"
            config_file.touch()

            result = resolve_configs(str(config_file), None)
            assert len(result) == 1
            assert result[0] == str(config_file.absolute())

    def test_resolve_nonexistent_name_raises_error(self):
        """Verify that nonexistent config name raises ConfigResolutionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").touch()

            with pytest.raises(ConfigResolutionError, match="Config 'missing' not found"):
                resolve_configs("missing", config_dir)

    def test_resolve_nonexistent_absolute_path_raises_error(self):
        """Verify that nonexistent absolute path raises ConfigResolutionError."""
        with pytest.raises(ConfigResolutionError, match="Config '/nonexistent.yaml' not found"):
            resolve_configs("/nonexistent.yaml", None)


class TestDiscoverConfigDir:
    """Tests for _discover_config_dir function."""

    def test_discover_with_explicit_path(self):
        """Verify that explicit config_path is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom"
            custom_dir.mkdir()

            result = _discover_config_dir(str(custom_dir))
            assert result == custom_dir.absolute()

    def test_discover_with_nonexistent_explicit_path(self):
        """Verify that nonexistent explicit path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Config directory not found"):
            _discover_config_dir("/nonexistent")

    def test_discover_with_default_config_dir(self):
        """Verify that ./config/ is used by default."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                config_dir = Path(tmpdir) / "config"
                config_dir.mkdir()

                result = _discover_config_dir(None)
                assert result == config_dir.absolute()
            finally:
                os.chdir(old_cwd)

    def test_discover_without_default_config_dir_raises_error(self):
        """Verify that missing ./config/ raises FileNotFoundError."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with pytest.raises(FileNotFoundError, match="No config/ directory found"):
                    _discover_config_dir(None)
            finally:
                os.chdir(old_cwd)


class TestListAvailableConfigs:
    """Tests for _list_available_configs function."""

    def test_list_returns_sorted_stems(self):
        """Verify that configs are returned as sorted stems."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "b.yaml").touch()
            (Path(tmpdir) / "a.yaml").touch()
            (Path(tmpdir) / "c.yaml").touch()

            result = _list_available_configs(Path(tmpdir))
            assert result == ["a", "b", "c"]

    def test_list_includes_yml_files(self):
        """Verify that .yml files are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.yaml").touch()
            (Path(tmpdir) / "config.yml").touch()

            result = _list_available_configs(Path(tmpdir))
            assert "config" in result

    def test_list_ignores_non_yaml_files(self):
        """Verify that non-yaml files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.yaml").touch()
            (Path(tmpdir) / "readme.txt").touch()
            (Path(tmpdir) / "data.json").touch()

            result = _list_available_configs(Path(tmpdir))
            assert result == ["config"]

    def test_list_empty_directory(self):
        """Verify that empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _list_available_configs(Path(tmpdir))
            assert result == []

    def test_list_nonexistent_directory(self):
        """Verify that nonexistent directory returns empty list."""
        result = _list_available_configs(Path("/nonexistent"))
        assert result == []


class TestResolveSingle:
    """Tests for _resolve_single function."""

    def test_resolve_single_with_name(self):
        """Verify resolving a simple name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "etl.yaml").touch()

            result = _resolve_single("etl", config_dir)
            assert result == (config_dir / "etl.yaml").absolute()

    def test_resolve_single_simple_name(self):
        """Verify resolving a simple name without extension or slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom.yaml"
            config_file.touch()

            # _resolve_single is only called for non-passthrough names
            # (no slash, no .yaml/.yml extension)
            result = _resolve_single("custom", Path(tmpdir))
            assert result == config_file.absolute()

    def test_resolve_single_strips_yaml_extension(self):
        """Verify that .yaml extension is stripped when present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "etl.yaml").touch()

            # _resolve_single assumes name doesn't end with .yaml
            # so we pass "etl" (without extension)
            result = _resolve_single("etl", config_dir)
            assert result == (config_dir / "etl.yaml").absolute()

    def test_resolve_single_strips_yml_extension(self):
        """Verify that .yml extension is stripped and converted to .yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "etl.yaml").touch()

            # _resolve_single assumes name doesn't end with .yml
            # so we pass "etl" (without extension)
            result = _resolve_single("etl", config_dir)
            assert result == (config_dir / "etl.yaml").absolute()

    def test_resolve_single_nonexistent_raises_error(self):
        """Verify that nonexistent name raises ConfigResolutionError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            (config_dir / "etl.yaml").touch()

            with pytest.raises(ConfigResolutionError):
                _resolve_single("missing", config_dir)
