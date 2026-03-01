"""Import utilities for dynamically importing classes from local projects."""

import sys
from pathlib import Path


def import_class(class_path: str) -> type:
    """
    Importa una clase desde su path completo, soportando proyectos locales.

    Esta función permite importar clases desde proyectos locales que no están
    instalados como paquetes, agregando temporalmente el directorio del proyecto
    a sys.path si es necesario.

    Args:
        class_path: Path completo (ej: "module.submodule.ClassName")

    Returns:
        Clase importada

    Raises:
        ImportError: Si no se puede importar la clase
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError):
        # Si falla, intentar agregando el directorio actual a sys.path
        cwd = Path.cwd()

        # Agregar directorio actual a sys.path temporalmente
        if str(cwd) not in sys.path:
            sys.path.insert(0, str(cwd))

        # Si existe src/, también agregarlo
        src_path = cwd / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as e:
            raise ImportError(
                f"No se puede importar clase {class_path}. "
                f"Asegúrate de estar ejecutando desde el directorio del proyecto "
                f"y que el módulo existe."
            ) from e
