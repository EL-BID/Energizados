"""Import utilities for dynamically importing classes from local projects."""

import sys
from pathlib import Path

# Allowlist of permitted module prefixes for dynamic class imports.
# Prevents arbitrary code execution via malicious YAML class references.
ALLOWED_PREFIXES = [
    "energizados.",
    "src.",
    "data.",
    "features.",
    "models.",
    "inference.",
    "preprocessing.",
    "etl.",
    "tests.",
]


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
        ImportError: If the class cannot be imported or not in the allowlist.
    """
    if not any(class_path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise ImportError(f"Class '{class_path}' is not in the allowed module prefixes. " f"Allowed prefixes: {ALLOWED_PREFIXES}")

    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError):
        # If it fails, try adding the current directory to sys.path temporarily
        cwd = Path.cwd()
        added_paths = []

        # Add current directory to sys.path temporarily
        if str(cwd) not in sys.path:
            sys.path.insert(0, str(cwd))
            added_paths.append(str(cwd))

        # If src/ exists, also add it temporarily
        src_path = cwd / "src"
        if src_path.exists() and str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
            added_paths.append(str(src_path))

        try:
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as e:
            raise ImportError(
                f"Cannot import class {class_path}. " f"Make sure you are running from the project directory " f"and the module exists."
            ) from e
        finally:
            for p in added_paths:
                try:
                    sys.path.remove(p)
                except ValueError:
                    pass
