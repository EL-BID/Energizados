"""Import utilities for dynamically importing classes from local projects."""

import sys
from pathlib import Path


def import_class(class_path: str) -> type:
    """
    Import a class from its full path, supporting local projects.

    This function allows importing classes from local projects that are not
    installed as packages, temporarily adding the project directory
    to sys.path if necessary.

    Args:
        class_path: Full path (e.g., "module.submodule.ClassName")

    Returns:
        Imported class

    Raises:
        ImportError: If the class cannot be imported
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError):
        # If it fails, try adding the current directory to sys.path
        cwd = Path.cwd()

        # Add current directory to sys.path temporarily
        if str(cwd) not in sys.path:
            sys.path.insert(0, str(cwd))

        # If src/ exists, also add it
        src_path = cwd / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as e:
            raise ImportError(
                f"Cannot import class {class_path}. " f"Make sure you are running from the project directory " f"and the module exists."
            ) from e
