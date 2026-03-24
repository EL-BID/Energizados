"""Config resolver for CLI - resolves config names to file paths."""

import fnmatch
from pathlib import Path
from typing import List


class ConfigResolutionError(Exception):
    """Raised when config resolution fails."""

    def __init__(self, name: str, config_dir: str, available: List[str]):
        self.name = name
        self.config_dir = config_dir
        self.available = available
        avail_str = ", ".join(available) if available else "(none)"
        super().__init__(
            f"Config '{name}' not found in {config_dir}/\n"
            f"Available configs: {avail_str}\n"
            f"Hint: Use --config-path to specify a different directory"
        )


def resolve_configs(configs_str: str, config_path: str | None = None) -> List[str]:
    """
    Resolve comma-separated config names to full file paths.

    Resolution rules (in order):
    1. If name contains '/' or ends with .yaml/.yml → passthrough as-is
    2. Strip .yaml/.yml if present, append .yaml
    3. Look in config_dir (default ./config/, override via --config-path)
    4. If not found → error with available configs

    Args:
        configs_str: Comma-separated names or paths (e.g. "etl,train")
        config_path: Override config directory. Default: ./config/

    Returns:
        List of resolved absolute file paths.

    Raises:
        ConfigResolutionError: If a config name cannot be resolved.
        FileNotFoundError: If config_dir does not exist and no passthrough paths.
    """
    # Split comma-separated names and strip whitespace
    names = [n.strip() for n in configs_str.split(",") if n.strip()]

    if not names:
        raise ValueError(
            "At least one config name is required. "
            "Example: 'energizados run etl' or 'energizados run etl,train'"
        )

    # Discover config directory only if needed (non-passthrough names or wildcards)
    has_passthrough = any("/" in n or n.endswith((".yaml", ".yml")) for n in names)
    has_wildcard = any(_is_wildcard(n) for n in names)
    if not has_passthrough or has_wildcard or config_path:
        config_dir = _discover_config_dir(config_path)
    else:
        # Use default config dir if it exists, otherwise will be set per-name
        default_config = Path.cwd() / "config"
        config_dir = default_config if default_config.exists() else None

    # Resolve each name
    resolved_paths = []
    for name in names:
        # Passthrough paths (contain '/' or end with .yaml/.yml)
        if "/" in name or name.endswith((".yaml", ".yml")):
            path = Path(name)
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists():
                available = _list_available_configs(config_dir) if config_dir else []
                raise ConfigResolutionError(name, str(config_dir or "."), available)
            resolved_paths.append(str(path.absolute()))
        elif _is_wildcard(name):
            # Wildcard patterns (e.g. "train_01*", "train_*_baseline")
            if config_dir is None:
                raise FileNotFoundError(
                    "No config/ directory found. Use --config-path to specify location."
                )
            matches = _resolve_wildcard(name, config_dir)
            resolved_paths.extend(matches)
        else:
            # Non-passthrough names need config_dir
            if config_dir is None:
                # Check for default config directory
                default_config = Path.cwd() / "config"
                if default_config.exists():
                    # Config dir exists but config not found
                    available = _list_available_configs(default_config)
                    raise ConfigResolutionError(name, str(default_config), available)
                else:
                    # No config/ directory at all
                    raise FileNotFoundError(
                        "No config/ directory found. Use --config-path to specify location."
                    )
            path = _resolve_single(name, config_dir)
            resolved_paths.append(str(path))

    return resolved_paths


def _is_wildcard(name: str) -> bool:
    """Return True if name contains glob wildcard characters."""
    return any(c in name for c in ("*", "?", "["))


def _resolve_wildcard(pattern: str, config_dir: Path) -> List[str]:
    """
    Expand a wildcard pattern against config_dir, returning sorted absolute paths.

    The pattern is matched against config stems (filenames without .yaml).
    For example, "train_01*" matches train_01_baseline.yaml, train_01_lgbm.yaml, etc.

    Args:
        pattern: Glob pattern (e.g. "train_01*", "train_*")
        config_dir: Directory to search

    Returns:
        Sorted list of absolute path strings for all matching configs

    Raises:
        ConfigResolutionError: If no files match the pattern
    """
    all_yamls = sorted(config_dir.glob("*.yaml")) + sorted(config_dir.glob("*.yml"))
    matches = [p for p in all_yamls if fnmatch.fnmatch(p.stem, pattern)]

    if not matches:
        available = _list_available_configs(config_dir)
        raise ConfigResolutionError(pattern, str(config_dir), available)

    return [str(p.absolute()) for p in sorted(matches)]


def _resolve_single(name: str, config_dir: Path) -> Path:
    """
    Resolve one config name to a path.

    This function assumes the name does NOT contain '/' and does NOT end with
    .yaml/.yml (those are handled as passthrough in resolve_configs).

    Rules (in order):
    1. Strip .yaml/.yml suffix if present, append .yaml
    2. Look up in config_dir
    3. Error with available list

    Args:
        name: Config name (not a path, passthrough handled by caller)
        config_dir: Directory to search for config files

    Returns:
        Path object with absolute path to the config file

    Raises:
        ConfigResolutionError: If name cannot be resolved
    """
    # Rule 1: Strip .yaml/.yml if present, then append .yaml
    clean_name = name.removesuffix(".yaml").removesuffix(".yml")
    clean_name = clean_name + ".yaml"

    # Rule 2: Look up in config_dir
    config_file = config_dir / clean_name
    if config_file.exists():
        return config_file.absolute()

    # Rule 3: Not found - error with available list
    available = _list_available_configs(config_dir)
    raise ConfigResolutionError(name, str(config_dir), available)


def _discover_config_dir(config_path: str | None) -> Path:
    """
    Find the config directory.

    1. If config_path provided → use it (error if not exists)
    2. ./config/ exists → use it
    3. Error: "No config/ directory found. Use --config-path."

    Args:
        config_path: Explicit config directory path override

    Returns:
        Path to the config directory

    Raises:
        FileNotFoundError: If config directory cannot be found
    """
    # Rule 1: Explicit override
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Config directory not found: {config_path}\nPlease verify the path exists."
            )
        return path.absolute()

    # Rule 2: ./config/ relative to CWD
    default_config = Path.cwd() / "config"
    if default_config.exists():
        return default_config

    # Rule 3: Not found
    raise FileNotFoundError("No config/ directory found. Use --config-path to specify location.")


def _list_available_configs(config_dir: Path) -> List[str]:
    """
    List .yaml/.yml files in config_dir, return stems.

    Args:
        config_dir: Directory to search for config files

    Returns:
        List of config names (without .yaml extension)
    """
    if not config_dir.exists():
        return []

    configs = []
    for path in config_dir.glob("*.yaml"):
        configs.append(path.stem)
    for path in config_dir.glob("*.yml"):
        configs.append(path.stem)

    return sorted(configs)
