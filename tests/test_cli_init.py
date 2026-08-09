"""
Unit tests for CLI init command.

Tests for the project initialization command including
the functionality to copy from existing projects.

Updated to support the new 2026 structure with src/, tests/, docs/, etc.
"""

import tempfile
from pathlib import Path

import pytest
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
            assert (project_path / "data" / "temp" / "splits").exists()
            assert (project_path / "output").exists()
            assert (project_path / "notebooks").exists()
            assert (project_path / "src" / "run").exists()

            # Verify execution scripts
            assert (project_path / "src" / "run" / "00_etl.py").exists()
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

            # Verify configuration files
            assert (project_path / "config" / "etl.yaml").exists()
            assert (project_path / "config" / "train.yaml").exists()
            assert (project_path / "config" / "infer.yaml").exists()

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

            # Verify correct imports (dynamic pkgutil pattern)
            data_init = (project_path / "src" / "data" / "__init__.py").read_text(encoding="utf-8")
            assert "pkgutil" in data_init
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

            requirements = (project_path / "requirements.txt").read_text(encoding="utf-8")
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

            docs = (project_path / "docs" / "project_docs.md").read_text(encoding="utf-8")
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
            result = self.runner.invoke(
                cli, ["init", "new_project", "--copy", "nonexistent", "--path", tmpdir]
            )

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
            content = custom_etl.read_text(encoding="utf-8")
            custom_etl.write_text(content.replace("# TODO:", "# MODIFIED:"), encoding="utf-8")

            # Copy the project
            copy_result = self.runner.invoke(
                cli, ["init", "copied_project", "--copy", "base_project", "--path", tmpdir]
            )
            assert copy_result.exit_code == 0

            # Verify that the file was copied
            copied_path = Path(tmpdir) / "copied_project"
            copied_etl = copied_path / "src" / "data" / "custom_etl.py"
            copied_content = copied_etl.read_text(encoding="utf-8")

            assert "# MODIFIED:" in copied_content

    def test_init_copy_updates_project_name_in_yaml(self):
        """Verify that init updates the project name in YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(
                cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir]
            )
            new_path = Path(tmpdir) / "new_project"

            # Verify that the name was updated in YAML
            etl_yaml = (new_path / "config" / "etl.yaml").read_text(encoding="utf-8")
            # The name appears in the header comment
            assert "new_project" in etl_yaml
            assert "base_project" not in etl_yaml

    def test_init_copy_creates_readme_with_origin_note(self):
        """Verify that the README indicates the source project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(
                cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir]
            )
            new_path = Path(tmpdir) / "new_project"

            # Verify origin note in README
            readme_content = (new_path / "README.md").read_text(encoding="utf-8")
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
            (old_path / "etl" / "custom_etl.py").write_text("# OLD ETL", encoding="utf-8")
            (old_path / "feature_selection" / "custom_selector.py").write_text(
                "# OLD SELECTOR", encoding="utf-8"
            )
            (old_path / "models" / "custom_model.py").write_text("# OLD MODEL", encoding="utf-8")
            (old_path / "inference" / "custom_inference.py").write_text(
                "# OLD INFERENCE", encoding="utf-8"
            )
            (old_path / "configs" / "etl.yaml").write_text(
                """
# ETLs Configuration for old_project
etl:
  sample:
    enabled: true
    custom_class: "old_project.etl.custom_etl.CustomETL"
""",
                encoding="utf-8",
            )

            # Copy from old structure
            result = self.runner.invoke(
                cli, ["init", "new_project", "--copy", "old_project", "--path", tmpdir]
            )
            assert result.exit_code == 0

            new_path = Path(tmpdir) / "new_project"

            # Verify new structure was created
            assert (new_path / "src" / "data" / "custom_etl.py").exists()
            assert (new_path / "src" / "features" / "custom_selector.py").exists()
            assert (new_path / "src" / "models" / "custom_model.py").exists()
            assert (new_path / "src" / "inference" / "custom_inference.py").exists()

            # Verify that 3 config files were created
            assert (new_path / "config" / "etl.yaml").exists()
            assert (new_path / "config" / "train.yaml").exists()
            assert (new_path / "config" / "infer.yaml").exists()

            # Verify that custom files were copied
            assert "# OLD ETL" in (new_path / "src" / "data" / "custom_etl.py").read_text(
                encoding="utf-8"
            )

            # Verify that the name was updated in YAML (in comment)
            yaml_content = (new_path / "config" / "etl.yaml").read_text(encoding="utf-8")
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
            result = self.runner.invoke(
                cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir]
            )
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

            result = self.runner.invoke(
                cli, ["init", "new_project", "--copy", "incomplete_project", "--path", tmpdir]
            )

            assert result.exit_code != 0

    def test_init_copy_preserves_init_files(self):
        """Verify that __init__.py files are preserved with correct imports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copy project
            self.runner.invoke(
                cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir]
            )
            new_path = Path(tmpdir) / "new_project"

            # Verify __init__.py files (dynamic pkgutil pattern)
            data_init = (new_path / "src" / "data" / "__init__.py").read_text(encoding="utf-8")
            assert "pkgutil" in data_init
            assert "custom_etl" in data_init

    def test_init_copy_does_not_copy_data_or_models(self):
        """Verify that data and training outputs are not copied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base project
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Create data files (that should not be copied)
            (base_path / "data" / "raw" / "data.csv").write_text("test,data", encoding="utf-8")
            # Simulate a training run in output/
            run_dir = base_path / "output" / "train-20260303_1430" / "models"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "model.pkl").write_text("model", encoding="utf-8")

            # Copy project
            self.runner.invoke(
                cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir]
            )
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
            assert (project_path / "config" / "etl.yaml").exists()
            assert (project_path / "config" / "train.yaml").exists()
            assert (project_path / "config" / "infer.yaml").exists()

            # Must NOT be configs/ (plural)
            assert not (project_path / "configs").exists()

    def test_init_gitignore_includes_tests_and_docs(self):
        """Verify that .gitignore includes entries for tests and docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            gitignore = (project_path / ".gitignore").read_text(encoding="utf-8")
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
            assert (
                result == expected
            ), f"For {input_name!r}, expected {expected!r} but got {result!r}"

    def test_init_underscore_project_name_generates_valid_yaml(self):
        """Verify that a project name with leading _ generates valid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project with invalid name
            result = self.runner.invoke(cli, ["init", "_sample", "--path", tmpdir])
            assert result.exit_code == 0

            project_path = Path(tmpdir) / "_sample"

            # Verify that YAML uses correct import path (without package prefix)
            etl_yaml = (project_path / "config" / "etl.yaml").read_text(encoding="utf-8")
            # YAML must use "data.custom_etl.CustomETL" (without package prefix)
            assert "data.custom_etl.CustomETL" in etl_yaml
            # Must not contain sanitized package prefix
            assert "sample.data.custom_etl.CustomETL" not in etl_yaml
            # Header comment can use original name
            assert "_sample" in etl_yaml  # In comment

    def test_init_copy_sanitizes_package_names_in_yaml(self):
        """Verify that package names are sanitized when copying projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project with invalid name
            self.runner.invoke(cli, ["init", "_old", "--path", tmpdir])

            # Copy to another project with invalid name
            self.runner.invoke(cli, ["init", "_new", "--copy", "_old", "--path", tmpdir])

            new_path = Path(tmpdir) / "_new"

            # Verify that YAML uses correct import path (without package prefix)
            etl_yaml = (new_path / "config" / "etl.yaml").read_text(encoding="utf-8")
            # Imports must use paths without package prefix
            assert "data.custom_etl.CustomETL" in etl_yaml
            # Must not contain package prefixes
            assert "new.data.custom_etl.CustomETL" not in etl_yaml
            assert "_new.data" not in etl_yaml
            assert "_old.data" not in etl_yaml


class TestTemplateResolution:
    """Tests that templates are resolvable from within the installed package."""

    def test_get_template_path_resolves_inside_package(self):
        """Verify that _get_template_path points inside the installed package, not the repo root."""
        from energizados.cli.init import _get_template_path

        path = _get_template_path("config/etl.yaml.tpl")
        assert path.exists(), f"Template not found at {path}"
        path_str = path.as_posix()
        assert "src/energizados/templates" in path_str or "energizados/templates" in path_str

    def test_all_expected_templates_exist(self):
        """Verify that all templates required by init are present in the package."""
        from energizados.cli.init import _get_template_path

        required = [
            "config/etl.yaml.tpl",
            "config/train.yaml.tpl",
            "config/infer.yaml.tpl",
            "src/data/custom_etl.py.tpl",
            "src/features/custom_selector.py.tpl",
            "src/models/custom_model.py.tpl",
            "src/inference/custom_inference.py.tpl",
            "src/utils/helpers.py.tpl",
            "src/run/00_etl.py.tpl",
            "src/run/01_eda.py.tpl",
            "src/run/02_training.py.tpl",
            "src/run/03_inference.py.tpl",
            "README.md.tpl",
            "requirements.txt.tpl",
            "docs/project_docs.md.tpl",
            ".gitignore.tpl",
            "data/raw/sample_dataset.parquet",
        ]
        for tpl in required:
            path = _get_template_path(tpl)
            assert path.exists(), f"Missing template: {tpl} (expected at {path})"


class TestPerSectionSchemaVersion:
    """Tests for per-section schema_version in config files."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_init_configs_have_schema_version(self):
        """Verify that each generated config file has schema_version inside its root section."""
        import yaml

        from energizados._version import CURRENT_SCHEMA_VERSIONS

        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])
            assert result.exit_code == 0

            config_dir = Path(tmpdir) / "test_project" / "config"

            # Each config must declare the current schema_version for its section
            etl_data = yaml.safe_load((config_dir / "etl.yaml").read_text(encoding="utf-8"))
            assert etl_data["etl"]["schema_version"] == CURRENT_SCHEMA_VERSIONS["etl"]

            train_data = yaml.safe_load((config_dir / "train.yaml").read_text(encoding="utf-8"))
            assert train_data["train"]["schema_version"] == CURRENT_SCHEMA_VERSIONS["train"]

            infer_data = yaml.safe_load((config_dir / "infer.yaml").read_text(encoding="utf-8"))
            assert infer_data["infer"]["schema_version"] == CURRENT_SCHEMA_VERSIONS["infer"]

            eda_data = yaml.safe_load((config_dir / "eda.yaml").read_text(encoding="utf-8"))
            assert eda_data["eda"]["schema_version"] == CURRENT_SCHEMA_VERSIONS["eda"]

    def test_no_general_yaml_created(self):
        """Verify that general.yaml is NOT created by init."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])
            assert result.exit_code == 0
            assert not (Path(tmpdir) / "test_project" / "config" / "general.yaml").exists()

    def test_requirements_pins_version(self):
        """Verify that requirements.txt uses compatible release operator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])
            assert result.exit_code == 0

            requirements = (Path(tmpdir) / "test_project" / "requirements.txt").read_text(
                encoding="utf-8"
            )
            assert "energizados~=" in requirements
            assert "energizados>=1.0.0" not in requirements


class TestInitPathValidation:
    """Verify that `init` rejects project names that would escape the target directory.

    The project name is concatenated with `--path` and then with subpaths
    (e.g. `project_path / "src" / "data" / "custom_etl.py"`). A name that
    contains `..` or path separators would write files outside the intended
    directory (CodeQL: py/path-injection). The CLI must reject these inputs
    with a clear error.
    """

    def setup_method(self):
        self.runner = CliRunner()

    @pytest.mark.parametrize(
        "bad_name,reason",
        [
            ("../escape", "parent-directory reference"),
            ("..", "parent-directory reference alone"),
            ("foo/../bar", "embedded parent-directory reference"),
            ("foo/bar", "forward slash"),
            ("foo\\bar", "backslash"),
            (".hidden", "leading dot"),
            ("", "empty"),
            ("   ", "whitespace only"),
        ],
    )
    def test_init_rejects_unsafe_project_name(self, bad_name, reason):
        """`init` must refuse names that would escape the target directory.

        The validation must run BEFORE any filesystem write: if a bad name
        reaches the filesystem layer, it could write files outside the target
        directory before a later check (e.g. ``FileExistsError``) aborts.
        We assert the validation error message in the output to guarantee the
        name was caught at the CLI boundary.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", bad_name, "--path", tmpdir])
            assert result.exit_code != 0, (
                f"Expected non-zero exit for {bad_name!r} ({reason}); "
                f"got exit_code=0 and output:\n{result.output}"
            )
            # The click-rendered usage error must come from our validation,
            # not from a downstream filesystem failure after the bad name was
            # already used to build a path.
            assert "Invalid value" in result.output, (
                f"Expected validation error for {bad_name!r} "
                f"(reason: {reason}); got output:\n{result.output}"
            )

    def test_init_rejects_name_with_leading_or_trailing_whitespace(self):
        """A name with surrounding whitespace is rejected (ambiguous on the filesystem)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "  my_project  ", "--path", tmpdir])
            assert result.exit_code != 0
            assert not (Path(tmpdir) / "  my_project  ").exists()

    def test_init_accepts_valid_names(self):
        """Sanity check: a normal name still works after the new validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "my_project", "--path", tmpdir])
            assert result.exit_code == 0
            assert (Path(tmpdir) / "my_project").is_dir()


class TestCreateProjectPathValidation:
    """Verify the path-traversal neutralization at the ``create_project`` sink.

    The web console (``ProjectService.create_project``) calls
    ``create_project`` directly, bypassing the CLI command. The CLI command
    rejects traversal-shaped names with a clear error; the sink here takes
    the permissive route and slugifies the name so the resulting directory
    is confined to ``project_path``'s parent. This is the behavior CodeQL
    tracks as a taint sanitizer (via ``os.path.basename`` and the
    ``re.sub`` fallback in ``_slugify_for_filesystem``), and it matches the
    pre-existing ``tests/web/test_projects.py::TestProjectServiceCreate::
    test_create_outside_root_confined`` contract: a traversal-shaped name
    produces a project whose path is strictly inside the workspace root and
    whose final component contains no ``..`` / ``/`` / ``\\``.
    """

    @pytest.mark.parametrize(
        "raw_name,slug",
        [
            ("../escape", "escape"),
            ("foo/../bar", "bar"),
            ("foo/bar", "bar"),
        ],
    )
    def test_create_project_slugifies_traversal_names(self, raw_name, slug):
        """Traversal-shaped names slug to a safe directory name; the result
        lives under ``project_path.parent`` (the workspace) and never escapes."""
        from energizados.cli.init import create_project

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            project_path = workspace / "intended"
            create_project(project_name=raw_name, project_path=project_path)
            # The project was created at <workspace>/<slug> (NOT at
            # project_path; the slug replaced the name component).
            created = workspace / slug
            assert created.is_dir(), (
                f"Expected the project to be created at {created} for input "
                f"{raw_name!r}; instead the directory is missing"
            )
            # The slug must not contain path-traversal characters.
            assert ".." not in created.name
            assert "/" not in created.name
            assert "\\" not in created.name
            # The created path is strictly inside the workspace.
            assert str(created.resolve()).startswith(
                str(workspace.resolve())
            ), f"Project path {created} escaped workspace {workspace}"

    @pytest.mark.parametrize(
        "empty_slug_name,reason",
        [
            ("..", "parent-directory reference alone"),
            ("", "empty"),
            ("   ", "whitespace only"),
            (".", "single dot"),
            ("...", "only dots"),
        ],
    )
    def test_create_project_rejects_names_that_slug_to_empty(self, empty_slug_name, reason):
        """Names that slug to an empty string raise ``ValueError`` because
        no safe directory name can be derived."""
        from energizados.cli.init import create_project

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "intended"
            with pytest.raises(ValueError) as excinfo:
                create_project(project_name=empty_slug_name, project_path=project_path)
            msg = str(excinfo.value).lower()
            assert "must not" in msg or "not safe" in msg, (
                f"Expected a clear validation message for {empty_slug_name!r} "
                f"({reason}); got: {excinfo.value}"
            )
            assert (
                not project_path.exists()
            ), f"create_project was called with {empty_slug_name!r} but a directory was created"

    def test_create_project_rejects_name_with_leading_or_trailing_whitespace_only(self):
        from energizados.cli.init import create_project

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "intended"
            with pytest.raises(ValueError):
                create_project(project_name="  ", project_path=project_path)

    def test_create_project_accepts_valid_name(self):
        """Sanity check: a normal name still works."""
        from energizados.cli.init import create_project

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "my_project"
            create_project(project_name="my_project", project_path=project_path)
            assert project_path.is_dir()


class TestSchemaValidation:
    """Tests for per-section schema compatibility checker."""

    def test_check_passes_with_current_schema(self):
        """Verify that compatibility check passes with current schema versions."""
        from energizados._version import CURRENT_SCHEMA_VERSIONS
        from energizados.cli.compat import check_project_compatibility

        config = {
            "etl": {"schema_version": CURRENT_SCHEMA_VERSIONS["etl"], "sample": {}},
            "train": {"schema_version": CURRENT_SCHEMA_VERSIONS["train"], "enabled": True},
        }
        # Should not raise
        check_project_compatibility(config)

    def test_check_fails_with_newer_schema(self):
        """Verify that compatibility check fails when a section schema is newer."""

        from energizados._version import CURRENT_SCHEMA_VERSIONS
        from energizados.cli.compat import check_project_compatibility
        from energizados.core.exceptions import ConfigurationError

        config = {
            "etl": {"schema_version": CURRENT_SCHEMA_VERSIONS["etl"] + 1, "sample": {}},
        }
        with pytest.raises(ConfigurationError, match="schema version"):
            check_project_compatibility(config)

    def test_check_passes_without_schema_version(self):
        """Verify that missing schema_version does not block execution (backwards compat)."""
        from energizados.cli.compat import check_project_compatibility

        config = {"etl": {"sample": {"enabled": True}}}
        # Should not raise — backwards compatible
        check_project_compatibility(config)

    def test_check_independent_per_section(self):
        """Verify that each section is checked independently."""

        from energizados._version import CURRENT_SCHEMA_VERSIONS
        from energizados.cli.compat import check_project_compatibility
        from energizados.core.exceptions import ConfigurationError

        # etl OK, train too new -> should fail on train
        config = {
            "etl": {"schema_version": CURRENT_SCHEMA_VERSIONS["etl"]},
            "train": {"schema_version": CURRENT_SCHEMA_VERSIONS["train"] + 1},
        }
        with pytest.raises(ConfigurationError, match="train"):
            check_project_compatibility(config)


class TestETLSchemaVersionFiltering:
    """Tests that schema_version is filtered out when parsing ETL configs."""

    def test_orchestrator_ignores_schema_version(self):
        """Verify that ETLOrchestrator filters out schema_version key."""
        from energizados.etl.orchestrator import ETLOrchestrator

        configs = {
            "schema_version": 1,
            "sample": {
                "enabled": True,
                "input": "data.csv",
                "output": "out.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "depends_on": [],
            },
        }
        orchestrator = ETLOrchestrator(configs)
        assert "schema_version" not in orchestrator.etl_configs
        assert "sample" in orchestrator.etl_configs
