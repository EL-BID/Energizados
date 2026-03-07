"""
Unit tests for CLI init command.

Tests for the project initialization command including
the functionality to copy from existing projects.

Updated to support the new 2026 structure with src/, tests/, docs/, etc.
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from energizados.cli.main import cli


class TestInitCommand:
    """Tests for the init command."""

    def setup_method(self):
        """Set up the test environment."""
        self.runner = CliRunner()

    def test_init_creates_project_structure(self):
        """Verify that init creates the correct project structure (2026 structure)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verify created directories (new structure with src/)
            assert (project_path / "src" / "data").exists()
            assert (project_path / "src" / "features").exists()
            assert (project_path / "src" / "models").exists()
            assert (project_path / "src" / "inference").exists()
            assert (project_path / "src" / "utils").exists()
            assert (project_path / "tests").exists()
            assert (project_path / "docs").exists()
            assert (project_path / "config").exists()
            assert (project_path / "data" / "raw").exists()
            assert (project_path / "data" / "processed").exists()
            assert (project_path / "data" / "splits").exists()
            assert (project_path / "output").exists()
            assert (project_path / "notebooks").exists()
            assert (project_path / "src" / "run").exists()

            # Verify execution scripts
            assert (project_path / "src" / "run" / "01_etl.py").exists()
            assert (project_path / "src" / "run" / "02_training.py").exists()
            assert (project_path / "src" / "run" / "03_inference.py").exists()

            # Verify created files
            assert (project_path / "src" / "data" / "custom_etl.py").exists()
            assert (project_path / "src" / "features" / "custom_selector.py").exists()
            assert (project_path / "src" / "models" / "custom_model.py").exists()
            assert (project_path / "src" / "inference" / "custom_inference.py").exists()
            assert (project_path / "src" / "utils" / "helpers.py").exists()
            # Test templates are no longer created by default (users create their own tests)
            assert (project_path / "tests" / "__init__.py").exists()
            assert (project_path / "docs" / "project_docs.md").exists()

            # Verify configuration files (3 separate files)
            assert (project_path / "config" / "etls.yaml").exists()
            assert (project_path / "config" / "training.yaml").exists()
            assert (project_path / "config" / "inference.yaml").exists()

            # Verify that the old pipeline.yaml NO longer exists
            assert not (project_path / "config" / "pipeline.yaml").exists()

            assert (project_path / "requirements.txt").exists()
            assert (project_path / "README.md").exists()
            assert (project_path / ".gitignore").exists()

    def test_init_creates_src_init_files(self):
        """Verify that __init__.py files are created in src/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verify __init__.py files
            assert (project_path / "src" / "__init__.py").exists()
            assert (project_path / "src" / "data" / "__init__.py").exists()
            assert (project_path / "src" / "features" / "__init__.py").exists()
            assert (project_path / "src" / "models" / "__init__.py").exists()
            assert (project_path / "src" / "inference" / "__init__.py").exists()
            assert (project_path / "src" / "utils" / "__init__.py").exists()
            assert (project_path / "tests" / "__init__.py").exists()

            # Verify correct imports
            data_init = (project_path / "src" / "data" / "__init__.py").read_text()
            assert "CustomETL" in data_init
            assert "custom_etl" in data_init

    def test_init_creates_test_templates(self):
        """Verify that the tests directory is created with __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verify that tests directory exists
            assert (project_path / "tests").exists()
            assert (project_path / "tests" / "__init__.py").exists()
            # Test templates are no longer created by default
            # Users can create their own tests as needed

    def test_init_creates_requirements_txt(self):
        """Verify that requirements.txt is created with dependencies."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            requirements = (project_path / "requirements.txt").read_text()
            assert "energizados" in requirements
            assert "pytest" in requirements
            assert "pandas" in requirements
            assert "scikit-learn" in requirements

    def test_init_creates_docs_template(self):
        """Verify that documentation template is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            docs = (project_path / "docs" / "project_docs.md").read_text()
            assert "test_project" in docs
            assert "src/" in docs
            assert "pytest" in docs

    def test_init_fails_if_project_exists(self):
        """Verify that init fails if the project already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "existing_project"
            project_path.mkdir()

            result = self.runner.invoke(cli, ["init", "existing_project", "--path", tmpdir])

            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_init_copy_from_nonexistent_project(self):
        """Verify that init fails if the source project does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "nonexistent", "--path", tmpdir])

            assert result.exit_code != 0
            assert "does not exist" in result.output.lower()

    def test_init_copy_from_new_structure_project(self):
        """Verify that init correctly copies from a project with new structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First create a base project (new structure)
            base_result = self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            assert base_result.exit_code == 0

            # Modify a custom file to verify it's copied
            base_path = Path(tmpdir) / "base_project"
            custom_etl = base_path / "src" / "data" / "custom_etl.py"
            content = custom_etl.read_text()
            custom_etl.write_text(content.replace("# TODO:", "# MODIFIED:"))

            # Copy the project
            copy_result = self.runner.invoke(cli, ["init", "copied_project", "--copy", "base_project", "--path", tmpdir])
            assert copy_result.exit_code == 0

            # Verify that the file was copied
            copied_path = Path(tmpdir) / "copied_project"
            copied_etl = copied_path / "src" / "data" / "custom_etl.py"
            copied_content = copied_etl.read_text()

            assert "# MODIFIED:" in copied_content

    def test_init_copy_updates_project_name_in_yaml(self):
        """Verify that init updates the project name in YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verify that the name was updated in YAML
            etls_yaml = (new_path / "config" / "etls.yaml").read_text()
            # The name appears in the header comment
            assert "new_project" in etls_yaml
            assert "base_project" not in etls_yaml

    def test_init_copy_creates_readme_with_origin_note(self):
        """Verify that the README indicates the source project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verify origin note in README
            readme_content = (new_path / "README.md").read_text()
            assert "base_project" in readme_content

    def test_init_copy_from_old_structure_project(self):
        """Verify copy from project with old structure (without src/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Manually create old structure
            old_path = Path(tmpdir) / "old_project"
            old_path.mkdir()
            (old_path / "etl").mkdir()
            (old_path / "feature_selection").mkdir()
            (old_path / "models").mkdir()
            (old_path / "inference").mkdir()
            (old_path / "configs").mkdir()

            # Create required files
            (old_path / "etl" / "custom_etl.py").write_text("# OLD ETL")
            (old_path / "feature_selection" / "custom_selector.py").write_text("# OLD SELECTOR")
            (old_path / "models" / "custom_model.py").write_text("# OLD MODEL")
            (old_path / "inference" / "custom_inference.py").write_text("# OLD INFERENCE")
            (old_path / "configs" / "etls.yaml").write_text("""
# ETLs Configuration for old_project
etls:
  sample:
    enabled: true
    custom_class: "old_project.etl.custom_etl.CustomETL"
""")

            # Copy from old structure
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "old_project", "--path", tmpdir])
            assert result.exit_code == 0

            new_path = Path(tmpdir) / "new_project"

            # Verify new structure was created
            assert (new_path / "src" / "data" / "custom_etl.py").exists()
            assert (new_path / "src" / "features" / "custom_selector.py").exists()
            assert (new_path / "src" / "models" / "custom_model.py").exists()
            assert (new_path / "src" / "inference" / "custom_inference.py").exists()

            # Verify that 3 config files were created
            assert (new_path / "config" / "etls.yaml").exists()
            assert (new_path / "config" / "training.yaml").exists()
            assert (new_path / "config" / "inference.yaml").exists()

            # Verify that custom files were copied
            assert "# OLD ETL" in (new_path / "src" / "data" / "custom_etl.py").read_text()

            # Verify that the name was updated in YAML (in comment)
            yaml_content = (new_path / "config" / "etls.yaml").read_text()
            assert "new_project" in yaml_content
            assert "old_project" not in yaml_content

    def test_init_copy_without_custom_files_uses_templates(self):
        """Verify that templates are used if custom files are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Delete custom file
            (base_path / "src" / "data" / "custom_etl.py").unlink()

            # Copy project
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            assert result.exit_code == 0

            # Verify that template was created
            new_path = Path(tmpdir) / "new_project"
            assert (new_path / "src" / "data" / "custom_etl.py").exists()

    def test_init_copy_validates_source_structure(self):
        """Verify that the source project structure is validated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create incomplete directory
            incomplete_path = Path(tmpdir) / "incomplete_project"
            incomplete_path.mkdir()
            (incomplete_path / "src").mkdir()

            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "incomplete_project", "--path", tmpdir])

            assert result.exit_code != 0

    def test_init_copy_preserves_init_files(self):
        """Verify that __init__.py files are preserved with correct imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verify __init__.py files
            data_init = (new_path / "src" / "data" / "__init__.py").read_text()
            assert "CustomETL" in data_init
            assert "custom_etl" in data_init

    def test_init_copy_does_not_copy_data_or_models(self):
        """Verify that data and training outputs are not copied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Create data files (that should not be copied)
            (base_path / "data" / "raw" / "data.csv").write_text("test,data")
            # Simulate a training run in output/
            run_dir = base_path / "output" / "train-20260303_1430" / "models"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "model.pkl").write_text("model")

            # Copy project
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verify that data and runs were NOT copied
            assert not (new_path / "data" / "raw" / "data.csv").exists()
            assert not (new_path / "output" / "train-20260303_1430").exists()
            # But .gitkeep files are present
            assert (new_path / "data" / "raw" / ".gitkeep").exists()
            assert (new_path / "output" / ".gitkeep").exists()

    def test_init_config_singular_not_configs(self):
        """Verify that it's config/ and not configs/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Must be config/ (singular)
            assert (project_path / "config").exists()

            # Must have the 3 config files
            assert (project_path / "config" / "etls.yaml").exists()
            assert (project_path / "config" / "training.yaml").exists()
            assert (project_path / "config" / "inference.yaml").exists()

            # Must NOT be configs/ (plural)
            assert not (project_path / "configs").exists()

    def test_init_gitignore_includes_tests_and_docs(self):
        """Verify that .gitignore includes entries for tests and docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            gitignore = (project_path / ".gitignore").read_text()
            assert ".pytest_cache/" in gitignore
            assert ".coverage" in gitignore
            assert "htmlcov/" in gitignore

    def test_init_sanitizes_invalid_package_names(self):
        """Verify that init sanitizes invalid Python package names."""
        from energizados.cli.init import _sanitize_package_name

        # Test cases for sanitization
        test_cases = [
            ("_sample", "sample"),  # Removes leading _
            ("__test", "test"),  # Removes multiple leading _
            ("my-project", "my_project"),  # Replaces - with _
            ("my-project-name", "my_project_name"),  # Multiple -
            ("123project", "pkg_123project"),  # Prefix if starts with number
            ("test", "test"),  # Valid name unchanged
            ("Test_Project", "Test_Project"),  # Valid name with uppercase
            ("for", "for_pkg"),  # Python keyword
            ("class", "class_pkg"),  # Python keyword
            ("", "project"),  # Empty -> "project"
            ("_", "project"),  # Only _ -> "project"
            ("___", "project"),  # Multiple _ only -> "project"
            ("project-123", "project_123"),  # - with numbers
            ("my project", "myproject"),  # Spaces removed
        ]

        for input_name, expected in test_cases:
            result = _sanitize_package_name(input_name)
            assert result == expected, f"For {input_name!r}, expected {expected!r} but got {result!r}"

    def test_init_underscore_project_name_generates_valid_yaml(self):
        """Verify that a project name with leading _ generates valid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project with invalid name
            result = self.runner.invoke(cli, ["init", "_sample", "--path", tmpdir])
            assert result.exit_code == 0

            project_path = Path(tmpdir) / "_sample"

            # Verify that YAML uses correct import path (without package prefix)
            etls_yaml = (project_path / "config" / "etls.yaml").read_text()
            # YAML must use "data.custom_etl.CustomETL" (without package prefix)
            assert "data.custom_etl.CustomETL" in etls_yaml
            # Must not contain sanitized package prefix
            assert "sample.data.custom_etl.CustomETL" not in etls_yaml
            # Header comment can use original name
            assert "_sample" in etls_yaml  # In comment

    def test_init_copy_sanitizes_package_names_in_yaml(self):
        """Verify that package names are sanitized when copying projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project with invalid name
            self.runner.invoke(cli, ["init", "_old", "--path", tmpdir])

            # Copy to another project with invalid name
            self.runner.invoke(cli, ["init", "_new", "--copy", "_old", "--path", tmpdir])

            new_path = Path(tmpdir) / "_new"

            # Verify that YAML uses correct import path (without package prefix)
            etls_yaml = (new_path / "config" / "etls.yaml").read_text()
            # Imports must use paths without package prefix
            assert "data.custom_etl.CustomETL" in etls_yaml
            # Must not contain package prefixes
            assert "new.data.custom_etl.CustomETL" not in etls_yaml
            assert "_new.data" not in etls_yaml
            assert "_old.data" not in etls_yaml
