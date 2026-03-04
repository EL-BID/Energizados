"""
Init command implementation for Energizados CLI.

This module implements the 'init' command functionality to create
new projects with the base structure following the best practices
of the 2026 industry.
"""

import keyword
import shutil
from pathlib import Path

# Python keywords that cannot be used as module names
PYTHON_KEYWORDS = set(keyword.kwlist)


def _sanitize_package_name(name: str) -> str:
    """
    Sanitizes a project name to be valid as a Python package.

    Python packages cannot:
    - Start with a number
    - Start with _
    - Contain hyphens (-)
    - Be Python keywords (for, class, etc.)
    - Contain spaces

    Args:
        name: Name of the project to sanitize

    Returns:
        Sanitized name valid as a Python package
    """
    if not name:
        return "project"

    # Remove spaces
    name = name.replace(" ", "")

    # Replace hyphens with underscores
    name = name.replace("-", "_")

    # Remove underscores at the beginning
    name = name.lstrip("_")

    # If empty after cleaning, use default
    if not name:
        return "project"

    # If starts with a number, add prefix
    if name[0].isdigit():
        name = f"pkg_{name}"

    # If it's a Python keyword, add suffix
    if name in PYTHON_KEYWORDS:
        name = f"{name}_pkg"

    return name


def _get_template_path(template_name: str) -> Path:
    """Returns the path to a template file."""
    return Path(__file__).parent.parent.parent.parent / "templates" / template_name


def _load_template(template_name: str) -> str:
    """Loads the content of a template from the file."""
    template_path = _get_template_path(template_name)
    return template_path.read_text()


def create_project(
    project_name: str,
    project_path: Path,
    template: str = "default",
    copy_from: str = None,
    force: bool = False,
):
    """
    Creates a new Energizados project with the base structure.

    Args:
        project_name: Name of the project
        project_path: Path where to create the project
        template: Name of the template to use
        copy_from: Name of the source project to copy
        force: If True, removes the existing directory before creating

    Raises:
        FileExistsError: If the project directory already exists and force=False
        ValueError: If the template or source project does not exist
    """
    if project_path.exists():
        if not force:
            raise FileExistsError(f"The directory '{project_path}' already exists")
        # Remove existing directory
        if project_path.is_dir():
            shutil.rmtree(project_path)
        else:
            project_path.unlink()

    # Detect if it's a copy from old structure
    old_structure = False
    if copy_from:
        source_path = project_path.parent / copy_from
        old_structure = not _is_new_structure(source_path)

    # Create directory structure
    _create_directory_structure(project_path)

    # Copy from existing project or create from templates
    if copy_from:
        source_path = project_path.parent / copy_from
        _copy_project_source(source_path, project_path, copy_from, project_name, old_structure=old_structure)
    else:
        # Create base files
        _create_base_files(project_path, project_name)

        # Create code templates
        _create_code_templates(project_path, project_name)

        # Create test templates
        _create_test_templates(project_path, project_name)

        # Create documentation and utility templates
        _create_extra_templates(project_path, project_name)

        # Create configuration
        _create_config_files(project_path, project_name)

        # Create execution scripts
        _create_run_scripts(project_path, project_name)

        # Create requirements.txt
        _create_requirements_file(project_path)


def _is_new_structure(project_path: Path) -> bool:
    """Detects if a project uses the new structure (with src/)."""
    return (project_path / "src").exists()


def _create_directory_structure(project_path: Path):
    """Creates the directory structure of the project (2026 structure)."""
    directories = [
        # Source code in src/
        project_path / "src" / "data",
        project_path / "src" / "features",
        project_path / "src" / "models",
        project_path / "src" / "inference",
        project_path / "src" / "utils",
        # Execution scripts in src/run/
        project_path / "src" / "run",
        # Tests
        project_path / "tests",
        # Documentation
        project_path / "docs",
        # Configuration (singular)
        project_path / "config",
        # Data
        project_path / "data" / "raw",
        project_path / "data" / "processed",
        project_path / "data" / "splits",
        # Training outputs (organized by run)
        project_path / "output",
        # Notebooks
        project_path / "notebooks",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    # Create __init__.py files for each module in src/
    init_modules = {
        project_path / "src" / "__init__.py": ("", ""),
        project_path / "src" / "data" / "__init__.py": ("custom_etl", "CustomETL"),
        project_path / "src" / "features" / "__init__.py": ("custom_selector", "CustomSelector"),
        project_path / "src" / "models" / "__init__.py": ("custom_model", "CustomModel"),
        project_path / "src" / "inference" / "__init__.py": ("custom_inference", "CustomInference"),
        project_path / "src" / "utils" / "__init__.py": ("helpers", "Helpers"),
        project_path / "tests" / "__init__.py": ("", ""),
    }

    for init_file, (module_name, class_name) in init_modules.items():
        if module_name:
            init_file.write_text(f'''"""{init_file.parent.name} module of the project.

This module contains the custom implementations for {project_path.name}.
"""

from .{module_name} import {class_name}

__all__ = ["{class_name}"]
''')
        else:
            init_file.write_text(f'''"""{init_file.parent.name} module of the project."""''')


def _create_base_files(project_path: Path, project_name: str, source_name: str = None):
    """
    Creates base project files.

    Args:
        project_path: Path of the project
        project_name: Name of the project
        source_name: Name of the source project (if copying)
    """
    # Read templates
    readme_template = _load_template("README.md.tpl")
    gitignore_template = _load_template(".gitignore.tpl")

    # Replace placeholders in README
    readme_content = readme_template.replace("{{project_name}}", project_name)
    if source_name:
        origin_note = f"\n> **Note:** This project was created by copying from `{source_name}`.\n"
    else:
        origin_note = ""
    readme_content = readme_template.replace("{{origin_note}}", origin_note)

    # Write files
    (project_path / "README.md").write_text(readme_content)
    (project_path / ".gitignore").write_text(gitignore_template)

    # .gitkeep files to keep empty directories in git
    (project_path / "data" / "raw" / ".gitkeep").write_text("")
    (project_path / "data" / "processed" / ".gitkeep").write_text("")
    (project_path / "data" / "splits" / ".gitkeep").write_text("")
    (project_path / "output" / ".gitkeep").write_text("")

    # Copy example dataset if it exists (only for new projects, not copies)
    if source_name is None:
        source_dataset = Path(__file__).parent.parent.parent.parent / "templates" / "data" / "raw" / "sample_dataset.parquet"
        if source_dataset.exists():
            import shutil

            target_dir = project_path / "data" / "raw"
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(source_dataset, target_dir / "sample_dataset.parquet")


def _create_code_templates(project_path: Path, project_name: str, only: str = None):
    """
    Creates code templates for customization.

    Args:
        project_path: Path of the project
        project_name: Name of the project
        only: Create only this template ("data", "features", "models", "inference")
    """
    template_map = {
        "data": "src/data/custom_etl.py.tpl",
        "features": "src/features/custom_selector.py.tpl",
        "models": "src/models/custom_model.py.tpl",
        "inference": "src/inference/custom_inference.py.tpl",
    }

    target_map = {
        "data": project_path / "src" / "data" / "custom_etl.py",
        "features": project_path / "src" / "features" / "custom_selector.py",
        "models": project_path / "src" / "models" / "custom_model.py",
        "inference": project_path / "src" / "inference" / "custom_inference.py",
    }

    for module, template_file in template_map.items():
        if only is None or only == module:
            template_content = _load_template(template_file)
            content = template_content.replace("{{project_name}}", project_name)
            target_map[module].write_text(content)

    # Create example notebook from template
    notebook_template_path = _get_template_path("notebooks/example_notebook.ipynb.tpl")
    if notebook_template_path.exists():
        notebook_content = notebook_template_path.read_text()
        notebook_content = notebook_content.replace("{{project_name}}", project_name)
        (project_path / "notebooks" / "example_notebook.ipynb").write_text(notebook_content)


def _create_test_templates(project_path: Path, project_name: str):
    """
    Creates test templates for the project.

    Args:
        project_path: Path of the project
        project_name: Name of the project
    """
    test_templates = {
        "conftest.py": "tests/conftest.py.tpl",
        "test_data.py": "tests/test_data.py.tpl",
        "test_features.py": "tests/test_features.py.tpl",
        "test_models.py": "tests/test_models.py.tpl",
    }

    for filename, template_file in test_templates.items():
        template_path = _get_template_path(template_file)
        if template_path.exists():
            template_content = _load_template(template_file)
            content = template_content.replace("{{project_name}}", project_name)
            (project_path / "tests" / filename).write_text(content)
        # If the template does not exist, it is silently omitted
        # Users can create their own tests


def _create_extra_templates(project_path: Path, project_name: str):
    """
    Creates additional templates (docs and utils).

    Args:
        project_path: Path of the project
        project_name: Name of the project
    """
    extra_templates = {
        "helpers.py": "src/utils/helpers.py.tpl",
        "project_docs.md": "docs/project_docs.md.tpl",
    }

    for filename, template_file in extra_templates.items():
        template_content = _load_template(template_file)
        content = template_content.replace("{{project_name}}", project_name)

        if filename == "helpers.py":
            (project_path / "src" / "utils" / filename).write_text(content)
        else:
            (project_path / "docs" / filename).write_text(content)


def _create_requirements_file(project_path: Path):
    """
    Creates the requirements.txt file with base dependencies.

    Args:
        project_path: Path of the project
    """
    requirements_content = _load_template("requirements.txt.tpl")
    (project_path / "requirements.txt").write_text(requirements_content)


def _validate_source_project(source_path: Path, old_structure: bool = False) -> bool:
    """
    Validates that the source project exists and has a valid structure.

    Args:
        source_path: Path to the source project
        old_structure: If True, validates old structure

    Returns:
        True if the project is valid

    Raises:
        ValueError: If the source project does not exist or is not valid
    """
    if not source_path.exists():
        raise ValueError(f"Source project does not exist: {source_path}")

    # Detect structure automatically if not specified
    if old_structure is None:
        old_structure = not _is_new_structure(source_path)

    # Verify structure accordingly
    if old_structure:
        required_dirs = ["etl", "feature_selection", "models", "configs"]
    else:
        required_dirs = ["src/data", "src/features", "src/models", "config"]

    for dir_name in required_dirs:
        if not (source_path / dir_name).exists():
            raise ValueError(f"Source project does not have the directory '{dir_name}'")

    return True


def _copy_custom_file(
    source_path: Path,
    target_path: Path,
    filename: str,
    comment_origin: str = None,
    map_structure: bool = False,
    old_to_new_map: dict = None,
) -> bool:
    """
    Copies a custom file from the source project to the destination.

    Args:
        source_path: Base path of the source project
        target_path: Base path of the target project
        filename: Name of the file to copy (relative to the base)
        comment_origin: Comment to add indicating the origin
        map_structure: If True, maps old structure to new
        old_to_new_map: Dictionary of path mapping

    Returns:
        True if the file was copied, False if it did not exist
    """
    source_file = source_path / filename

    # Map target path if necessary
    target_filename = filename
    if map_structure and old_to_new_map:
        for old_prefix, new_prefix in old_to_new_map.items():
            if filename.startswith(old_prefix):
                target_filename = filename.replace(old_prefix, new_prefix, 1)
                break

    target_file = target_path / target_filename

    if source_file.exists():
        content = source_file.read_text()

        # Add origin comment if specified
        if comment_origin:
            comment = f"\n# This file was copied from: {comment_origin}\n"
            # Insert after the docstring if it exists
            if '"""' in content:
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if '"""' in line and i > 0:
                        lines.insert(i + 1, comment)
                        break
                content = "\n".join(lines)
            else:
                content = comment + "\n" + content

        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content)
        return True
    return False


def _map_old_to_new_structure(old_path: str) -> str:
    """
    Maps old structure paths to new structure paths.

    Args:
        old_path: Path in old format

    Returns:
        Path in new format
    """
    mapping = {
        "etl/": "src/data/",
        "feature_selection/": "src/features/",
        "models/": "src/models/",
        "inference/": "src/inference/",
        "configs/": "config/",
    }

    for old, new in mapping.items():
        if old_path.startswith(old):
            return old_path.replace(old, new, 1)

    return old_path


def _copy_and_adapt_pipeline_yaml(source_path: Path, target_path: Path, old_name: str, new_name: str, old_structure: bool = False):
    """
    Copies and adapts the configuration files from the source project.

    Args:
        source_path: Path to the source project
        target_path: Path to the target project
        old_name: Name of the source project
        new_name: Name of the target project
        old_structure: Whether the source uses old structure
    """
    import re

    # Sanitize names for use in package imports
    old_package = _sanitize_package_name(old_name)
    new_package = _sanitize_package_name(new_name)

    # List of configuration files to copy
    config_files = ["etls.yaml", "training.yaml", "inference.yaml"]

    for config_file in config_files:
        # Determine path according to structure
        if old_structure:
            source_yaml = source_path / "configs" / config_file
        else:
            source_yaml = source_path / "config" / config_file

        target_yaml = target_path / "config" / config_file

        if source_yaml.exists():
            content = source_yaml.read_text()

            # Replace project name in configuration
            patterns = [
                # In header comments (e.g.: "# ... for old_project")
                (rf"# .* for {re.escape(old_name)}", f"# ... for {new_name}"),
                (rf"#.*Configuration for {re.escape(old_name)}", f"# Configuration for {new_name}"),
                # In YAML fields (if they exist)
                (rf'name:\s*"{re.escape(old_name)}"', f'name: "{new_name}"'),
                (rf"name:\s*'{re.escape(old_name)}'", f"name: '{new_name}'"),
            ]

            # Map imports using sanitized package names
            if old_structure:
                patterns.extend(
                    [
                        (rf"{re.escape(old_package)}\.etl", f"{new_package}.src.data"),
                        (
                            rf"{re.escape(old_package)}\.feature_selection",
                            f"{new_package}.src.features",
                        ),
                        (rf"{re.escape(old_package)}\.models", f"{new_package}.src.models"),
                        (rf"{re.escape(old_package)}\.inference", f"{new_package}.src.inference"),
                    ]
                )
                # Rename configs/ -> config/ in comments
                content = content.replace("configs/", "config/")
            else:
                patterns.extend(
                    [
                        # New projects use {package}.data.custom_etl.CustomETL
                        (
                            rf"{re.escape(old_package)}\.data\.custom_etl",
                            f"{new_package}.data.custom_etl",
                        ),
                        (
                            rf"{re.escape(old_package)}\.features\.custom_selector",
                            f"{new_package}.features.custom_selector",
                        ),
                        (
                            rf"{re.escape(old_package)}\.models\.custom_model",
                            f"{new_package}.models.custom_model",
                        ),
                        (
                            rf"{re.escape(old_package)}\.inference\.custom_inference",
                            f"{new_package}.inference.custom_inference",
                        ),
                        # Also handle src.* format just in case
                        (rf"{re.escape(old_package)}\.src\.data", f"{new_package}.data"),
                        (rf"{re.escape(old_package)}\.src\.features", f"{new_package}.features"),
                        (rf"{re.escape(old_package)}\.src\.models", f"{new_package}.models"),
                        (rf"{re.escape(old_package)}\.src\.inference", f"{new_package}.inference"),
                    ]
                )

            for pattern, replacement in patterns:
                content = re.sub(pattern, replacement, content)

            target_yaml.write_text(content)
        else:
            # If not found, create from template
            _create_config_files(target_path, new_name)
            break  # Only create templates once


def _copy_project_source(
    source_path: Path,
    target_path: Path,
    source_name: str,
    target_name: str,
    old_structure: bool = False,
):
    """
    Copies custom files from an existing project.

    Args:
        source_path: Path of the source project
        target_path: Path of the target project
        source_name: Name of the source project
        target_name: Name of the target project
        old_structure: If the source uses old structure

    Raises:
        ValueError: If the source project is not valid
    """
    # Validate source project
    _validate_source_project(source_path, old_structure)

    # File mapping according to structure
    if old_structure:
        custom_files = [
            "etl/custom_etl.py",
            "feature_selection/custom_selector.py",
            "models/custom_model.py",
            "inference/custom_inference.py",
        ]
        # Old structure to new structure mapping
        structure_map = {
            "etl/": "src/data/",
            "feature_selection/": "src/features/",
            "models/": "src/models/",
            "inference/": "src/inference/",
        }
    else:
        custom_files = [
            "src/data/custom_etl.py",
            "src/features/custom_selector.py",
            "src/models/custom_model.py",
            "src/inference/custom_inference.py",
        ]
        structure_map = {}

    copied_files = []
    for file_path in custom_files:
        if _copy_custom_file(
            source_path,
            target_path,
            file_path,
            f"{source_name}/{file_path}",
            map_structure=old_structure,
            old_to_new_map=structure_map,
        ):
            copied_files.append(file_path)

    # Create base files (README, .gitignore) adapted
    _create_base_files(target_path, target_name, source_name=source_name)

    # Copy and adapt pipeline.yaml
    _copy_and_adapt_pipeline_yaml(source_path, target_path, source_name, target_name, old_structure)

    # Create templates for files that didn't exist in the source
    # Mapping of modules to internal names
    module_map = {
        "data": "etl",
        "features": "feature_selection",
        "models": "models",
        "inference": "inference",
    }

    for new_name_short, old_name_short in module_map.items():
        # Search both in old and new structure
        old_found = False
        for old_path in [
            "etl",
            "feature_selection",
            "models",
            "inference",
            "src/data",
            "src/features",
            "src/models",
            "src/inference",
        ]:
            # The file name may vary
            if old_name_short == "inference":
                file_name = "custom_inference.py"
            elif old_name_short == "etl":
                file_name = "custom_etl.py"
            elif old_name_short == "feature_selection":
                file_name = "custom_selector.py"
            else:
                file_name = f"custom_{old_name_short}.py"

            check_path_full = f"{old_path}/{file_name}"

            if (source_path / check_path_full).exists():
                old_found = True
                break

        if not old_found:
            # Create template
            if new_name_short == "data":
                _create_code_templates(target_path, target_name, only="data")
            elif new_name_short == "features":
                _create_code_templates(target_path, target_name, only="features")
            elif new_name_short == "models":
                _create_code_templates(target_path, target_name, only="models")
            elif new_name_short == "inference":
                _create_code_templates(target_path, target_name, only="inference")

    # Create tests, docs and requirements if not copied
    if not (target_path / "tests" / "conftest.py").exists():
        _create_test_templates(target_path, target_name)
    if not (target_path / "docs" / "project_docs.md").exists():
        _create_extra_templates(target_path, target_name)
    if not (target_path / "requirements.txt").exists():
        _create_requirements_file(target_path)


def _create_run_scripts(project_path: Path, project_name: str):
    """
    Creates Python scripts to execute each stage of the pipeline.

    Scripts created in src/run/:
    - 01_etl.py - Executes ETLs
    - 02_training.py - Executes training
    - 03_evaluation.py - Executes evaluation
    - 04_inference.py - Executes inference

    Note: These scripts use the Python API directly, without invoking the CLI.
    """
    scripts = {
        "01_etl.py": "src/run/01_etl.py.tpl",
        "02_training.py": "src/run/02_training.py.tpl",
        "03_evaluation.py": "src/run/03_evaluation.py.tpl",
        "04_inference.py": "src/run/04_inference.py.tpl",
    }

    run_dir = project_path / "src" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    for filename, template_path in scripts.items():
        template_content = _load_template(template_path)
        script_path = run_dir / filename
        script_path.write_text(template_content)
        script_path.chmod(0o755)  # Make executable


def _create_config_files(project_path: Path, project_name: str):
    """
    Creates configuration files of the project.

    Creates 3 separate configuration files:
    - etls.yaml
    - training.yaml
    - inference.yaml

    Args:
        project_path: Path of the project
        project_name: Name of the project
    """
    # Sanitize name for package imports
    package_name = _sanitize_package_name(project_name)

    config_templates = {
        "etls.yaml": "config/etls.yaml.tpl",
        "training.yaml": "config/training.yaml.tpl",
        "inference.yaml": "config/inference.yaml.tpl",
    }

    for filename, template_path in config_templates.items():
        template_content = _load_template(template_path)
        config_content = template_content.replace("{{project_name}}", project_name)
        config_content = config_content.replace("{{package}}", package_name)
        (project_path / "config" / filename).write_text(config_content)
