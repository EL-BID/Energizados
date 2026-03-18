"""
Integration tests for CLI run and validate commands.

Tests for the new positional `configs` argument and config resolution.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from energizados.cli.main import cli


class TestRunCommand:
    """Tests for the run command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_run_single_config(self):
        """Verify that run works with a single config name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            etls_yaml = config_dir / "etls.yaml"
            etls_yaml.write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", "etls"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_comma_separated_configs(self):
        """Verify that run works with comma-separated config names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")
            (config_dir / "training.yaml").write_text("""
training:
  enabled: false
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", "etls,training"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_custom_config_path(self):
        """Verify that run works with --config-path option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom config directory
            custom_config = Path(tmpdir) / "custom_config"
            custom_config.mkdir()
            (custom_config / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(
                        cli, ["run", "--config-path", str(custom_config), "etls"]
                    )
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_absolute_path(self):
        """Verify that run works with absolute config path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom.yaml"
            config_file.write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", str(config_file)])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_nonexistent_config_in_missing_dir(self):
        """Verify that config not found in empty directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty config dir
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["run", "nonexistent"])
                assert result.exit_code != 0
                assert "Config 'nonexistent' not found" in result.output
                assert "Available configs:" in result.output
                assert "Use --config-path" in result.output
            finally:
                os.chdir(old_cwd)

    def test_run_no_config_dir_raises_error(self):
        """Verify that missing config/ directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["run", "etls"])
                assert result.exit_code != 0
                assert "No config/ directory found" in result.output
                assert "Use --config-path" in result.output
            finally:
                os.chdir(old_cwd)

    def test_run_empty_string_raises_error(self):
        """Verify that empty string raises error."""
        result = self.runner.invoke(cli, ["run", ""])
        assert result.exit_code != 0
        assert "At least one config name is required" in result.output

    def test_run_with_step_option(self):
        """Verify that run works with --step option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "training.yaml").write_text("""
training:
  enabled: false
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_step"):
                    result = self.runner.invoke(cli, ["run", "training", "--step", "training"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_dry_run_option(self):
        """Verify that run works with --dry-run option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            # Fix YAML indentation and add required fields
            (config_dir / "etls.yaml").write_text("""etls:
  sample:
    enabled: false
    input: data/input.csv
    output: data/output.csv
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                result = self.runner.invoke(cli, ["run", "etls", "--dry-run"])
                assert result.exit_code == 0
                assert "Dry-run mode" in result.output
            finally:
                os.chdir(old_cwd)


class TestValidateCommand:
    """Tests for the validate command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_validate_single_config(self):
        """Verify that validate works with a single config name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etls"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_comma_separated_configs(self):
        """Verify that validate works with comma-separated config names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")
            (config_dir / "training.yaml").write_text("""
training:
  enabled: false
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etls,training"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_with_custom_config_path(self):
        """Verify that validate works with --config-path option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom config directory
            custom_config = Path(tmpdir) / "custom_config"
            custom_config.mkdir()
            (custom_config / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(
                        cli, ["validate", "--config-path", str(custom_config), "etls"]
                    )
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_nonexistent_config_in_missing_dir(self):
        """Verify that config not found in empty directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty config dir
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["validate", "nonexistent"])
                assert result.exit_code != 0
                assert "Config 'nonexistent' not found" in result.output
                assert "Available configs:" in result.output
                assert "Use --config-path" in result.output
            finally:
                os.chdir(old_cwd)

    def test_validate_with_verbose_option(self):
        """Verify that validate works with --verbose option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etls.yaml").write_text("""
etls:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""")

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etls", "--verbose"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)


class TestEDACommand:
    """Tests that the eda subcommand has been removed."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_eda_command_removed(self):
        """Verify that eda subcommand no longer exists."""
        result = self.runner.invoke(cli, ["eda"])
        assert result.exit_code != 0
        assert "No such command" in result.output
