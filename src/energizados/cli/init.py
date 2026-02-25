"""
Init command implementation for Energizados CLI.

Este módulo implementa la funcionalidad del comando 'init' para crear
nuevos proyectos con la estructura base siguiendo las mejores prácticas
de la industria 2026.
"""

import keyword
import shutil
from pathlib import Path

# Python keywords that cannot be used as module names
PYTHON_KEYWORDS = set(keyword.kwlist)


def _sanitize_package_name(name: str) -> str:
    """
    Sanitiza un nombre de proyecto para que sea válido como paquete Python.

    Los paquetes Python no pueden:
    - Empezar con un número
    - Empezar con _
    - Contener guiones (-)
    - Ser keywords de Python (for, class, etc.)
    - Contener espacios

    Args:
        name: Nombre del proyecto a sanitizar

    Returns:
        Nombre sanitizado válido como paquete Python
    """
    if not name:
        return "project"

    # Eliminar espacios
    name = name.replace(" ", "")

    # Reemplazar guiones con guiones bajos
    name = name.replace("-", "_")

    # Eliminar guiones bajos al inicio
    name = name.lstrip("_")

    # Si está vacío después de limpiar, usar default
    if not name:
        return "project"

    # Si empieza con número, agregar prefijo
    if name[0].isdigit():
        name = f"pkg_{name}"

    # Si es keyword de Python, agregar sufijo
    if name in PYTHON_KEYWORDS:
        name = f"{name}_pkg"

    return name


def _get_template_path(template_name: str) -> Path:
    """Retorna la ruta a un archivo de template."""
    return Path(__file__).parent.parent.parent.parent / "templates" / template_name


def _load_template(template_name: str) -> str:
    """Carga el contenido de un template desde el archivo."""
    template_path = _get_template_path(template_name)
    return template_path.read_text()


def create_project(project_name: str, project_path: Path, template: str = "default", copy_from: str = None, force: bool = False):
    """
    Crea un nuevo proyecto Energizados con la estructura base.

    Args:
        project_name: Nombre del proyecto
        project_path: Ruta donde crear el proyecto
        template: Nombre del template a usar
        copy_from: Nombre del proyecto origen para copiar
        force: Si es True, elimina el directorio existente antes de crear

    Raises:
        FileExistsError: Si el directorio del proyecto ya existe y force=False
        ValueError: Si el template o proyecto origen no existe
    """
    if project_path.exists():
        if not force:
            raise FileExistsError(f"El directorio '{project_path}' ya existe")
        # Eliminar directorio existente
        if project_path.is_dir():
            shutil.rmtree(project_path)
        else:
            project_path.unlink()

    # Detectar si es copia desde estructura antigua
    old_structure = False
    if copy_from:
        source_path = project_path.parent / copy_from
        old_structure = not _is_new_structure(source_path)

    # Crear estructura de directorios
    _create_directory_structure(project_path)

    # Copiar desde proyecto existente o crear desde templates
    if copy_from:
        source_path = project_path.parent / copy_from
        _copy_project_source(source_path, project_path, copy_from, project_name, old_structure=old_structure)
    else:
        # Crear archivos base
        _create_base_files(project_path, project_name)

        # Crear templates de código
        _create_code_templates(project_path, project_name)

        # Crear templates de tests
        _create_test_templates(project_path, project_name)

        # Crear templates de documentación y utilidades
        _create_extra_templates(project_path, project_name)

        # Crear configuración
        _create_config_files(project_path, project_name)

        # Crear scripts de ejecución
        _create_run_scripts(project_path, project_name)

        # Crear requirements.txt
        _create_requirements_file(project_path)


def _is_new_structure(project_path: Path) -> bool:
    """Detecta si un proyecto usa la estructura nueva (con src/)."""
    return (project_path / "src").exists()


def _create_directory_structure(project_path: Path):
    """Crea la estructura de directorios del proyecto (estructura 2026)."""
    directories = [
        # Código fuente en src/
        project_path / "src" / "data",
        project_path / "src" / "features",
        project_path / "src" / "models",
        project_path / "src" / "inference",
        project_path / "src" / "utils",
        # Tests
        project_path / "tests",
        # Documentación
        project_path / "docs",
        # Configuración (singular)
        project_path / "config",
        # Datos
        project_path / "data" / "raw",
        project_path / "data" / "processed",
        project_path / "data" / "splits",
        # Modelos entrenados (solo archivos)
        project_path / "models" / "trained",
        # Notebooks y reportes
        project_path / "notebooks",
        project_path / "reports",
        # Scripts de ejecución
        project_path / "run",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    # Crear archivos __init__.py para cada módulo en src/
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
            init_file.write_text(f'''"""Módulo {init_file.parent.name} del proyecto.

Este módulo contiene las implementaciones personalizadas para {project_path.name}.
"""

from .{module_name} import {class_name}

__all__ = ["{class_name}"]
''')
        else:
            init_file.write_text(f'''"""Módulo {init_file.parent.name} del proyecto."""''')


def _create_base_files(project_path: Path, project_name: str, source_name: str = None):
    """
    Crea archivos base del proyecto.

    Args:
        project_path: Ruta del proyecto
        project_name: Nombre del proyecto
        source_name: Nombre del proyecto origen (si se copia)
    """
    # Leer templates
    readme_template = _load_template("README.md.tpl")
    gitignore_template = _load_template(".gitignore.tpl")

    # Reemplazar placeholders en README
    readme_content = readme_template.replace("{{project_name}}", project_name)
    if source_name:
        origin_note = f"\n> **Nota:** Este proyecto fue creado copiando desde `{source_name}`.\n"
    else:
        origin_note = ""
    readme_content = readme_content.replace("{{origin_note}}", origin_note)

    # Escribir archivos
    (project_path / "README.md").write_text(readme_content)
    (project_path / ".gitignore").write_text(gitignore_template)

    # Archivos .gitkeep para mantener directorios vacíos en git
    (project_path / "data" / "raw" / ".gitkeep").write_text("")
    (project_path / "data" / "processed" / ".gitkeep").write_text("")
    (project_path / "data" / "splits" / ".gitkeep").write_text("")
    (project_path / "models" / "trained" / ".gitkeep").write_text("")
    (project_path / "reports" / ".gitkeep").write_text("")

    # Copiar dataset de ejemplo si existe (solo para proyectos nuevos, no copias)
    if source_name is None:
        source_dataset = Path(__file__).parent.parent.parent.parent / "templates" / "data" / "raw" / "sample_dataset.parquet"
        if source_dataset.exists():
            import shutil

            target_dir = project_path / "data" / "raw"
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(source_dataset, target_dir / "sample_dataset.parquet")


def _create_code_templates(project_path: Path, project_name: str, only: str = None):
    """
    Crea templates de código para personalización.

    Args:
        project_path: Ruta del proyecto
        project_name: Nombre del proyecto
        only: Crear solo este template ("data", "features", "models", "inference")
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
    Crea templates de tests para el proyecto.

    Args:
        project_path: Ruta del proyecto
        project_name: Nombre del proyecto
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
        # Si el template no existe, se omite silenciosamente
        # Los usuarios pueden crear sus propios tests


def _create_extra_templates(project_path: Path, project_name: str):
    """
    Crea templates adicionales (docs y utils).

    Args:
        project_path: Ruta del proyecto
        project_name: Nombre del proyecto
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
    Crea el archivo requirements.txt con dependencias base.

    Args:
        project_path: Ruta del proyecto
    """
    requirements_content = _load_template("requirements.txt.tpl")
    (project_path / "requirements.txt").write_text(requirements_content)


def _validate_source_project(source_path: Path, old_structure: bool = False) -> bool:
    """
    Valida que el proyecto origen exista y tenga estructura válida.

    Args:
        source_path: Ruta al proyecto origen
        old_structure: Si es True, valida estructura antigua

    Returns:
        True si el proyecto es válido

    Raises:
        ValueError: Si el proyecto origen no existe o no es válido
    """
    if not source_path.exists():
        raise ValueError(f"El proyecto origen no existe: {source_path}")

    # Detectar estructura automáticamente si no se especifica
    if old_structure is None:
        old_structure = not _is_new_structure(source_path)

    # Verificar estructura según corresponda
    if old_structure:
        required_dirs = ["etl", "feature_selection", "models", "configs"]
    else:
        required_dirs = ["src/data", "src/features", "src/models", "config"]

    for dir_name in required_dirs:
        if not (source_path / dir_name).exists():
            raise ValueError(f"El proyecto origen no tiene el directorio '{dir_name}'")

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
    Copia un archivo custom del proyecto origen al destino.

    Args:
        source_path: Ruta base del proyecto origen
        target_path: Ruta base del proyecto destino
        filename: Nombre del archivo a copiar (relativo a la base)
        comment_origin: Comentario a agregar indicando el origen
        map_structure: Si es True, mapea estructura antigua a nueva
        old_to_new_map: Diccionario de mapeo de paths

    Returns:
        True si se copió el archivo, False si no existía
    """
    source_file = source_path / filename

    # Mapear path de destino si es necesario
    target_filename = filename
    if map_structure and old_to_new_map:
        for old_prefix, new_prefix in old_to_new_map.items():
            if filename.startswith(old_prefix):
                target_filename = filename.replace(old_prefix, new_prefix, 1)
                break

    target_file = target_path / target_filename

    if source_file.exists():
        content = source_file.read_text()

        # Agregar comentario de origen si se especifica
        if comment_origin:
            comment = f"\n# Este archivo fue copiado desde: {comment_origin}\n"
            # Insertar después del docstring si existe
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
    Mapea rutas de estructura antigua a nueva.

    Args:
        old_path: Ruta en formato antiguo

    Returns:
        Ruta en formato nuevo
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
    Copia y adapta los archivos de configuración del proyecto origen.

    Args:
        source_path: Ruta del proyecto origen
        target_path: Ruta del proyecto destino
        old_name: Nombre del proyecto origen
        new_name: Nombre del proyecto destino
        old_structure: Si el origen usa estructura antigua
    """
    import re

    # Sanitizar nombres para usar en imports de paquetes
    old_package = _sanitize_package_name(old_name)
    new_package = _sanitize_package_name(new_name)

    # Lista de archivos de configuración a copiar
    config_files = ["etls.yaml", "training.yaml", "inference.yaml"]

    for config_file in config_files:
        # Determinar ruta según estructura
        if old_structure:
            source_yaml = source_path / "configs" / config_file
        else:
            source_yaml = source_path / "config" / config_file

        target_yaml = target_path / "config" / config_file

        if source_yaml.exists():
            content = source_yaml.read_text()

            # Reemplazar el nombre del proyecto en la configuración
            patterns = [
                # En comentarios del encabezado (ej: "# ... for old_project")
                (rf"# .* for {re.escape(old_name)}", f"# ... for {new_name}"),
                (rf"#.*Configuration for {re.escape(old_name)}", f"# Configuration for {new_name}"),
                # En campos YAML (si existen)
                (rf'name:\s*"{re.escape(old_name)}"', f'name: "{new_name}"'),
                (rf"name:\s*'{re.escape(old_name)}'", f"name: '{new_name}'"),
            ]

            # Mapear imports usando nombres de paquetes sanitizados
            if old_structure:
                patterns.extend(
                    [
                        (rf"{re.escape(old_package)}\.etl", f"{new_package}.src.data"),
                        (rf"{re.escape(old_package)}\.feature_selection", f"{new_package}.src.features"),
                        (rf"{re.escape(old_package)}\.models", f"{new_package}.src.models"),
                        (rf"{re.escape(old_package)}\.inference", f"{new_package}.src.inference"),
                    ]
                )
                # Renombrar configs/ -> config/ en comentarios
                content = content.replace("configs/", "config/")
            else:
                patterns.extend(
                    [
                        # Nuevos proyectos usan {package}.data.custom_etl.CustomETL
                        (rf"{re.escape(old_package)}\.data\.custom_etl", f"{new_package}.data.custom_etl"),
                        (rf"{re.escape(old_package)}\.features\.custom_selector", f"{new_package}.features.custom_selector"),
                        (rf"{re.escape(old_package)}\.models\.custom_model", f"{new_package}.models.custom_model"),
                        (rf"{re.escape(old_package)}\.inference\.custom_inference", f"{new_package}.inference.custom_inference"),
                        # Por si acaso, también el formato src.*
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
            # Si no existe, crear desde template
            _create_config_files(target_path, new_name)
            break  # Solo crear templates una vez


def _copy_project_source(source_path: Path, target_path: Path, source_name: str, target_name: str, old_structure: bool = False):
    """
    Copia archivos personalizados desde un proyecto existente.

    Args:
        source_path: Ruta del proyecto origen
        target_path: Ruta del proyecto destino
        source_name: Nombre del proyecto origen
        target_name: Nombre del proyecto destino
        old_structure: Si el origen usa estructura antigua

    Raises:
        ValueError: Si el proyecto origen no es válido
    """
    # Validar proyecto origen
    _validate_source_project(source_path, old_structure)

    # Mapeo de archivos según estructura
    if old_structure:
        custom_files = [
            "etl/custom_etl.py",
            "feature_selection/custom_selector.py",
            "models/custom_model.py",
            "inference/custom_inference.py",
        ]
        # Mapeo de estructura antigua a nueva
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
            source_path, target_path, file_path, f"{source_name}/{file_path}", map_structure=old_structure, old_to_new_map=structure_map
        ):
            copied_files.append(file_path)

    # Crear archivos base (README, .gitignore) adaptados
    _create_base_files(target_path, target_name, source_name=source_name)

    # Copiar y adaptar pipeline.yaml
    _copy_and_adapt_pipeline_yaml(source_path, target_path, source_name, target_name, old_structure)

    # Crear templates para archivos que no existían en el origen
    # Mapeo de módulos a nombres internos
    module_map = {
        "data": "etl",
        "features": "feature_selection",
        "models": "models",
        "inference": "inference",
    }

    for new_name_short, old_name_short in module_map.items():
        # Buscar tanto en estructura antigua como nueva
        old_found = False
        for old_path in ["etl", "feature_selection", "models", "inference", "src/data", "src/features", "src/models", "src/inference"]:
            # El nombre del archivo puede variar
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
            # Crear template
            if new_name_short == "data":
                _create_code_templates(target_path, target_name, only="data")
            elif new_name_short == "features":
                _create_code_templates(target_path, target_name, only="features")
            elif new_name_short == "models":
                _create_code_templates(target_path, target_name, only="models")
            elif new_name_short == "inference":
                _create_code_templates(target_path, target_name, only="inference")

    # Crear tests, docs y requirements si no se copiaron
    if not (target_path / "tests" / "conftest.py").exists():
        _create_test_templates(target_path, target_name)
    if not (target_path / "docs" / "project_docs.md").exists():
        _create_extra_templates(target_path, target_name)
    if not (target_path / "requirements.txt").exists():
        _create_requirements_file(target_path)


def _create_run_scripts(project_path: Path, project_name: str):
    """
    Crea scripts de Python para ejecutar cada etapa del pipeline.

    Scripts creados:
    - 01_etl.py - Ejecuta ETLs
    - 02_training.py - Ejecuta entrenamiento
    - 03_evaluation.py - Ejecuta evaluación
    - 04_inference.py - Ejecuta inferencia

    Nota: Estos scripts usan el API Python directamente, sin invocar al CLI.
    """
    scripts = {
        "01_etl.py": "src/run/01_etl.py.tpl",
        "02_training.py": "src/run/02_training.py.tpl",
        "03_evaluation.py": "src/run/03_evaluation.py.tpl",
        "04_inference.py": "src/run/04_inference.py.tpl",
    }

    for filename, template_path in scripts.items():
        template_content = _load_template(template_path)
        script_path = project_path / "run" / filename
        script_path.write_text(template_content)
        script_path.chmod(0o755)  # Make executable


def _create_config_files(project_path: Path, project_name: str):
    """
    Crea archivos de configuración del proyecto.

    Crea 3 archivos de configuración separados:
    - etls.yaml
    - training.yaml
    - inference.yaml

    Args:
        project_path: Ruta del proyecto
        project_name: Nombre del proyecto
    """
    # Sanitizar nombre para imports de paquetes
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
