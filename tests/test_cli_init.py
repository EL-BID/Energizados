"""
Unit tests for CLI init command.

Pruebas para el comando de inicialización de proyectos incluyendo
la funcionalidad de copiar desde proyectos existentes.

Actualizado para soportar la nueva estructura 2026 con src/, tests/, docs/, etc.
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
        """Verifica que init cree la estructura correcta del proyecto (estructura 2026)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verificar directorios creados (estructura nueva con src/)
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
            assert (project_path / "models" / "trained").exists()
            assert (project_path / "notebooks").exists()
            assert (project_path / "reports").exists()
            assert (project_path / "src" / "run").exists()

            # Verificar scripts de ejecución
            assert (project_path / "src" / "run" / "01_etl.py").exists()
            assert (project_path / "src" / "run" / "02_training.py").exists()
            assert (project_path / "src" / "run" / "03_evaluation.py").exists()
            assert (project_path / "src" / "run" / "04_inference.py").exists()

            # Verificar archivos creados
            assert (project_path / "src" / "data" / "custom_etl.py").exists()
            assert (project_path / "src" / "features" / "custom_selector.py").exists()
            assert (project_path / "src" / "models" / "custom_model.py").exists()
            assert (project_path / "src" / "inference" / "custom_inference.py").exists()
            assert (project_path / "src" / "utils" / "helpers.py").exists()
            # Test templates ya no se crean por defecto (los usuarios crean sus propios tests)
            assert (project_path / "tests" / "__init__.py").exists()
            assert (project_path / "docs" / "project_docs.md").exists()

            # Verificar archivos de configuración (3 archivos separados)
            assert (project_path / "config" / "etls.yaml").exists()
            assert (project_path / "config" / "training.yaml").exists()
            assert (project_path / "config" / "inference.yaml").exists()

            # Verificar que el antiguo pipeline.yaml ya NO existe
            assert not (project_path / "config" / "pipeline.yaml").exists()

            assert (project_path / "requirements.txt").exists()
            assert (project_path / "README.md").exists()
            assert (project_path / ".gitignore").exists()

    def test_init_creates_src_init_files(self):
        """Verifica que se creen los archivos __init__.py en src/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verificar __init__.py files
            assert (project_path / "src" / "__init__.py").exists()
            assert (project_path / "src" / "data" / "__init__.py").exists()
            assert (project_path / "src" / "features" / "__init__.py").exists()
            assert (project_path / "src" / "models" / "__init__.py").exists()
            assert (project_path / "src" / "inference" / "__init__.py").exists()
            assert (project_path / "src" / "utils" / "__init__.py").exists()
            assert (project_path / "tests" / "__init__.py").exists()

            # Verificar imports correctos
            data_init = (project_path / "src" / "data" / "__init__.py").read_text()
            assert "CustomETL" in data_init
            assert "custom_etl" in data_init

    def test_init_creates_test_templates(self):
        """Verifica que se cree el directorio de tests con __init__.py."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Verificar que el directorio de tests existe
            assert (project_path / "tests").exists()
            assert (project_path / "tests" / "__init__.py").exists()
            # Los templates de tests ya no se crean por defecto
            # Los usuarios pueden crear sus propios tests según sus necesidades

    def test_init_creates_requirements_txt(self):
        """Verifica que se cree requirements.txt con dependencias."""
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
        """Verifica que se cree template de documentación."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            docs = (project_path / "docs" / "project_docs.md").read_text()
            assert "test_project" in docs
            assert "src/" in docs
            assert "pytest" in docs

    def test_init_fails_if_project_exists(self):
        """Verifica que init falle si el proyecto ya existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "existing_project"
            project_path.mkdir()

            result = self.runner.invoke(cli, ["init", "existing_project", "--path", tmpdir])

            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_init_copy_from_nonexistent_project(self):
        """Verifica que init falle si el proyecto origen no existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "nonexistent", "--path", tmpdir])

            assert result.exit_code != 0
            assert "no existe" in result.output.lower()

    def test_init_copy_from_new_structure_project(self):
        """Verifica que init copie correctamente desde proyecto con estructura nueva."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Primero crear un proyecto base (estructura nueva)
            base_result = self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            assert base_result.exit_code == 0

            # Modificar un archivo custom para verificar que se copia
            base_path = Path(tmpdir) / "base_project"
            custom_etl = base_path / "src" / "data" / "custom_etl.py"
            content = custom_etl.read_text()
            custom_etl.write_text(content.replace("# TODO:", "# MODIFIED:"))

            # Copiar el proyecto
            copy_result = self.runner.invoke(cli, ["init", "copied_project", "--copy", "base_project", "--path", tmpdir])
            assert copy_result.exit_code == 0

            # Verificar que el archivo fue copiado
            copied_path = Path(tmpdir) / "copied_project"
            copied_etl = copied_path / "src" / "data" / "custom_etl.py"
            copied_content = copied_etl.read_text()

            assert "# MODIFIED:" in copied_content

    def test_init_copy_updates_project_name_in_yaml(self):
        """Verifica que init actualice el nombre del proyecto en los archivos YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])

            # Copiar proyecto
            self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            new_path = Path(tmpdir) / "new_project"

            # Verificar que el nombre se actualizó en el YAML
            etls_yaml = (new_path / "config" / "etls.yaml").read_text()
            # El nombre aparece en el comentario del encabezado
            assert "new_project" in etls_yaml
            assert "base_project" not in etls_yaml

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

    def test_init_copy_from_old_structure_project(self):
        """Verifica copia desde proyecto con estructura antigua (sin src/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear estructura antigua manualmente
            old_path = Path(tmpdir) / "old_project"
            old_path.mkdir()
            (old_path / "etl").mkdir()
            (old_path / "feature_selection").mkdir()
            (old_path / "models").mkdir()
            (old_path / "inference").mkdir()
            (old_path / "configs").mkdir()

            # Crear archivos necesarios
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

            # Copiar desde estructura antigua
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "old_project", "--path", tmpdir])
            assert result.exit_code == 0

            new_path = Path(tmpdir) / "new_project"

            # Verificar estructura nueva creada
            assert (new_path / "src" / "data" / "custom_etl.py").exists()
            assert (new_path / "src" / "features" / "custom_selector.py").exists()
            assert (new_path / "src" / "models" / "custom_model.py").exists()
            assert (new_path / "src" / "inference" / "custom_inference.py").exists()

            # Verificar que se crearon los 3 archivos de config
            assert (new_path / "config" / "etls.yaml").exists()
            assert (new_path / "config" / "training.yaml").exists()
            assert (new_path / "config" / "inference.yaml").exists()

            # Verificar que los archivos custom se copiaron
            assert "# OLD ETL" in (new_path / "src" / "data" / "custom_etl.py").read_text()

            # Verificar que el nombre se actualizó en el YAML (en el comentario)
            yaml_content = (new_path / "config" / "etls.yaml").read_text()
            assert "new_project" in yaml_content
            assert "old_project" not in yaml_content

    def test_init_copy_without_custom_files_uses_templates(self):
        """Verifica que si no hay archivos custom, se usen templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto base
            self.runner.invoke(cli, ["init", "base_project", "--path", tmpdir])
            base_path = Path(tmpdir) / "base_project"

            # Eliminar archivo custom
            (base_path / "src" / "data" / "custom_etl.py").unlink()

            # Copiar proyecto
            result = self.runner.invoke(cli, ["init", "new_project", "--copy", "base_project", "--path", tmpdir])
            assert result.exit_code == 0

            # Verificar que se creó el template
            new_path = Path(tmpdir) / "new_project"
            assert (new_path / "src" / "data" / "custom_etl.py").exists()

    def test_init_copy_validates_source_structure(self):
        """Verifica que se valide la estructura del proyecto origen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear directorio incompleto
            incomplete_path = Path(tmpdir) / "incomplete_project"
            incomplete_path.mkdir()
            (incomplete_path / "src").mkdir()

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
            data_init = (new_path / "src" / "data" / "__init__.py").read_text()
            assert "CustomETL" in data_init
            assert "custom_etl" in data_init

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

    def test_init_config_singular_not_configs(self):
        """Verifica que sea config/ y no configs/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            # Debe ser config/ (singular)
            assert (project_path / "config").exists()

            # Debe tener los 3 archivos de config
            assert (project_path / "config" / "etls.yaml").exists()
            assert (project_path / "config" / "training.yaml").exists()
            assert (project_path / "config" / "inference.yaml").exists()

            # NO debe ser configs/ (plural)
            assert not (project_path / "configs").exists()

    def test_init_gitignore_includes_tests_and_docs(self):
        """Verifica que .gitignore incluya entradas para tests y docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.runner.invoke(cli, ["init", "test_project", "--path", tmpdir])

            assert result.exit_code == 0
            project_path = Path(tmpdir) / "test_project"

            gitignore = (project_path / ".gitignore").read_text()
            assert ".pytest_cache/" in gitignore
            assert ".coverage" in gitignore
            assert "htmlcov/" in gitignore

    def test_init_sanitizes_invalid_package_names(self):
        """Verifica que init sanitize nombres inválidos de paquetes Python."""
        from energizados.cli.init import _sanitize_package_name

        # Casos de prueba para sanitización
        test_cases = [
            ("_sample", "sample"),  # Elimina _ al inicio
            ("__test", "test"),  # Elimina múltiples _ al inicio
            ("my-project", "my_project"),  # Reemplaza - con _
            ("my-project-name", "my_project_name"),  # Múltiples -
            ("123project", "pkg_123project"),  # Prefijo si empieza con número
            ("test", "test"),  # Nombre válido sin cambios
            ("Test_Project", "Test_Project"),  # Nombre válido con mayúsculas
            ("for", "for_pkg"),  # Keyword de Python
            ("class", "class_pkg"),  # Keyword de Python
            ("", "project"),  # Vacío → "project"
            ("_", "project"),  # Solo _ → "project"
            ("___", "project"),  # Solo _ múltiples → "project"
            ("project-123", "project_123"),  # - con números
            ("my project", "myproject"),  # Espacios eliminados
        ]

        for input_name, expected in test_cases:
            result = _sanitize_package_name(input_name)
            assert result == expected, f"Para {input_name!r}, se esperaba {expected!r} pero se obtuvo {result!r}"

    def test_init_underscore_project_name_generates_valid_yaml(self):
        """Verifica que un nombre de proyecto con _ al inicio genere YAML válido."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto con nombre inválido
            result = self.runner.invoke(cli, ["init", "_sample", "--path", tmpdir])
            assert result.exit_code == 0

            project_path = Path(tmpdir) / "_sample"

            # Verificar que el YAML use la ruta de importación correcta (sin prefijo de paquete)
            etls_yaml = (project_path / "config" / "etls.yaml").read_text()
            # El YAML debe usar "data.custom_etl.CustomETL" (sin prefijo de paquete)
            assert "data.custom_etl.CustomETL" in etls_yaml
            # No debe contener el prefijo del paquete sanitizado
            assert "sample.data.custom_etl.CustomETL" not in etls_yaml
            # El comentario del encabezado puede usar el nombre original
            assert "_sample" in etls_yaml  # En el comentario

    def test_init_copy_sanitizes_package_names_in_yaml(self):
        """Verifica que al copiar proyectos se sanitize los nombres de paquetes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear proyecto con nombre inválido
            self.runner.invoke(cli, ["init", "_old", "--path", tmpdir])

            # Copiar a otro proyecto con nombre inválido
            self.runner.invoke(cli, ["init", "_new", "--copy", "_old", "--path", tmpdir])

            new_path = Path(tmpdir) / "_new"

            # Verificar que el YAML use la ruta de importación correcta (sin prefijo de paquete)
            etls_yaml = (new_path / "config" / "etls.yaml").read_text()
            # Los imports deben usar rutas sin prefijo de paquete
            assert "data.custom_etl.CustomETL" in etls_yaml
            # No debe contener prefijos de paquete
            assert "new.data.custom_etl.CustomETL" not in etls_yaml
            assert "_new.data" not in etls_yaml
            assert "_old.data" not in etls_yaml
