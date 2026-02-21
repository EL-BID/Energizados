"""
Unit tests for CLI init command.

Pruebas para el comando de inicialización de proyectos incluyendo
la funcionalidad de copiar desde proyectos existentes.
"""

import tempfile
from pathlib import Path

from click.testing import CliRunner

from energizados.cli.main import cli


class TestInitCommand:
    """Tests para el comando init."""

    def setup_method(self):
        """Configura el entorno de prueba."""
        self.runner = CliRunner()

    def test_init_creates_project_structure(self):
        """Verifica que init cree la estructura correcta del proyecto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verificar directorios creados (incluyendo inference y notebooks)
            assert (project_path / "etl").exists()
            assert (project_path / "feature_selection").exists()
            assert (project_path / "models").exists()
            assert (project_path / "inference").exists()
            assert (project_path / "notebooks").exists()
            assert (project_path / "configs").exists()
            assert (project_path / "data" / "raw").exists()
            assert (project_path / "data" / "processed").exists()
            assert (project_path / "models" / "trained").exists()
            assert (project_path / "reports").exists()

            # Verificar archivos creados (incluyendo inference y notebook)
            assert (project_path / "etl" / "custom_etl.py").exists()
            assert (project_path / "feature_selection" / "custom_selector.py").exists()
            assert (project_path / "models" / "custom_model.py").exists()
            assert (project_path / "inference" / "custom_inference.py").exists()
            assert (project_path / "notebooks" / "example_notebook.ipynb").exists()
            assert (project_path / "configs" / "pipeline.yaml").exists()
            assert (project_path / "README.md").exists()
            assert (project_path / ".gitignore").exists()

    def test_init_fails_if_project_exists(self):
        """Verifica que init falle si el proyecto ya existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "existing_project"
            project_path.mkdir()

            result = self.runner.invoke(cli, ["init", "existing_project", "--path", tmpdir])

            assert result.exit_code != 0
            assert "ya existe" in result.output.lower()

    def test_init_copy_from_nonexistent_project(self):
        """Verifica que init falle si el proyecto origen no existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "nonexistent", "--path", tmpdir])

            assert result.exit_code != 0
            assert "no existe" in result.output.lower()

    def test_init_copy_from_project(self):
        """Verifica que init copie correctamente desde un proyecto existente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Primero crear un proyecto base
            base_result = self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            assert base_result.exit_code == 0

            # Modificar un archivo custom para verificar que se copia
            base_path = Path(tmpdir) / "base_project"
            custom_etl = base_path / "etl" / "custom_etl.py"
            content = custom_etl.read_text()
            custom_etl.write_text(content.replace("# TODO:", "# MODIFIED:"))

            # Copiar el proyecto
            copy_result = self.runner.invoke(cli, ["init", "copied_project", "--copy", "base_project", "--path", tmpdir])
            assert copy_result.exit_code == 0

            # Verificar que el archivo fue copiado
            copied_path = Path(tmpdir) / "copied_project"
            copied_etl = copied_path / "etl" / "custom_etl.py"
            copied_content = copied_etl.read_text()

            assert "# MODIFIED:" in copied_content

    def test_init_copy_updates_project_name_in_yaml(self):
        """Verifica que init actualice el nombre del proyecto en pipeline.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copiar proyecto
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verificar que el nombre se actualizó en YAML
            yaml_content = (new_path / "configs" / "pipeline.yaml").read_text()
            assert 'name: "new_project"' in yaml_content
            assert 'name: "base_project"' not in yaml_content

    def test_init_copy_creates_readme_with_origin_note(self):
        """Verifica que el README indique el proyecto origen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copiar proyecto
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verificar nota de origen en README
            readme_content = (new_path / "README.md").read_text()
            assert "base_project" in readme_content

    def test_init_copy_without_custom_files_uses_templates(self):
        """Verifica que si no hay archivos custom, se usen templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Eliminar archivo custom
            (base_path / "etl" / "custom_etl.py").unlink()

            # Copiar proyecto
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            assert result.exit_code == 0

            # Verificar que se creó el template
            new_path = Path(tmpdir) / "new_project"
            assert (new_path / "etl" / "custom_etl.py").exists()

    def test_init_copy_validates_source_structure(self):
        """Verifica que se valide la estructura del proyecto origen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear directorio incompleto
            incomplete_path = Path(tmpdir) / "incomplete_project"
            incomplete_path.mkdir()
            (incomplete_path / "etl").mkdir()

            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "incomplete_project", "--path", tmpdir])

            assert result.exit_code != 0

    def test_init_copy_preserves_init_files(self):
        """Verifica que se preserven los __init__.py con imports correctos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copiar proyecto
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verificar __init__.py files
            etl_init = (new_path / "etl" / "__init__.py").read_text()
            assert "CustomETL" in etl_init
            assert "custom_etl" in etl_init

    def test_init_copy_does_not_copy_data_or_models(self):
        """Verifica que no se copien datos ni modelos entrenados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Crear archivos de datos y modelos (que no deben copiarse)
            (base_path / "data" / "raw" / "data.csv").write_text("test,data")
            (base_path / "models" / "trained" / "model.pkl").write_text("model")

            # Copiar proyecto
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verificar que NO se copiaron
            assert not (new_path / "data" / "raw" / "data.csv").exists()
            assert not (new_path / "models" / "trained" / "model.pkl").exists()
            # Pero sí los .gitkeep
            assert (new_path / "data" / "raw" / ".gitkeep").exists()
            assert (new_path / "models" / "trained" / ".gitkeep").exists()
