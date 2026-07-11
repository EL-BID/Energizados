"""
ProjectService: multi-project workspace registry for the web console.

A *project* is a directory on disk (the single source of truth) containing at
least a ``config/`` and ``src/`` subdirectory. The registry
(``data/web/projects.json``) is a bookmark file — NOT the source of truth. Every
access re-validates the path against disk, so a moved/deleted project is treated
as unknown (and surfaces as 404 in the web layer).

Create-side confinement: ``create_project`` targets must resolve strictly under
``workspace_root`` (rejecting path traversal and symlink escapes).
Register-side accepts arbitrary absolute paths (the user's own projects) but
stores the resolved-absolute path and re-validates on each access.

project_id is a URL-safe slug derived from the project name (never a raw
filesystem path); collisions are resolved with a numeric suffix.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_ROOT = "data/web/workspace"
DEFAULT_REGISTRY_PATH = "data/web/projects.json"


@dataclass
class Project:
    """A registered project (registry entry)."""

    project_id: str  # URL-safe slug, the only identifier in URLs
    name: str  # Human-readable name
    path: Path  # Resolved absolute path to the project directory
    created_at: str  # ISO timestamp
    template: str = "default"  # Template used at creation


def is_valid_project(path: Path) -> bool:
    """
    Return True if ``path`` is a valid Energizados project on disk.

    A valid project has both a ``config/`` and a ``src/`` directory (mirrors the
    ``_is_new_structure`` check in ``cli/init.py``).

    Args:
        path: Candidate project directory (need not be resolved).

    Returns:
        True if both subdirectories exist.
    """
    return (path / "config").is_dir() and (path / "src").is_dir()


def slugify_project_id(name: str) -> str:
    """
    Derive a URL-safe project_id slug from a project name.

    Lowercases, replaces whitespace/underscores with hyphens, strips characters
    that are not alphanumeric or hyphens, and collapses consecutive hyphens.

    Args:
        name: Project name.

    Returns:
        URL-safe slug (e.g. ``"My Project!"`` → ``"my-project"``).
    """
    slug = name.strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


def _resolve_workspace_root(workspace_root: Optional[Path]) -> Path:
    """
    Resolve workspace root: explicit arg → env → default.

    Args:
        workspace_root: Explicit workspace root (arg) or None.

    Returns:
        Resolved (absolute) workspace root Path.
    """
    if workspace_root is not None:
        return Path(workspace_root).resolve()
    env_root = os.environ.get("ENERGIZADOS_WORKSPACE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(DEFAULT_WORKSPACE_ROOT).resolve()


class ProjectService:
    """
    Registry-backed project manager.

    The registry is a JSON file mapping ``project_id`` → ``{name, path,
    created_at, template}``. Writes are atomic (temp file + ``os.replace``).
    """

    def __init__(self, workspace_root: Path, registry_path: Path):
        """
        Initialize the service.

        Args:
            workspace_root: Root under which new projects are created.
            registry_path: Path to the JSON registry file.
        """
        self.workspace_root: Path = Path(workspace_root).resolve()
        self.registry_path: Path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Registry I/O
    # ------------------------------------------------------------------
    def _read_registry(self) -> Dict[str, Dict]:
        """Load the registry from disk (empty dict if missing/corrupt)."""
        if not self.registry_path.is_file():
            return {}
        try:
            return json.loads(self.registry_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Registry unreadable ({e}); starting empty")
            return {}

    def _write_registry(self, data: Dict[str, Dict]) -> None:
        """Atomically write the registry (temp file + os.rename)."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(self.registry_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        os.replace(tmp, self.registry_path)

    # ------------------------------------------------------------------
    # Create / Register
    # ------------------------------------------------------------------
    def create_project(
        self,
        name: str,
        template: str = "default",
        copy_from: Optional[str] = None,
        force: bool = False,
    ) -> Project:
        """
        Create a new project under ``workspace_root`` and register it.

        Security: the target directory must resolve strictly under
        ``workspace_root``. Path traversal (e.g. ``../escape``) and symlink
        escapes are rejected.

        Args:
            name: Project name (also used for the directory and slug).
            template: Template name passed to ``cli.init.create_project``.
            copy_from: Optional source project to copy from.
            force: If True, overwrite an existing target directory.

        Returns:
            The registered Project.

        Raises:
            ValueError: If the resolved target escapes ``workspace_root``.
            FileExistsError: If the target exists and ``force`` is False.
        """
        from energizados.cli.init import create_project as _create_on_disk

        # SECURITY: derive the directory name from the slug so traversal in the
        # raw name cannot escape workspace_root. Reject empty/escape slugs.
        dir_slug = slugify_project_id(name)
        if not dir_slug or dir_slug in {"", "."}:
            raise ValueError(f"Invalid project name: {name!r}")

        ws_resolved = self.workspace_root.resolve()

        # Dedupe the directory name against BOTH the filesystem (existing dirs
        # under workspace_root) and the registry IDs, so two projects named
        # "demo" get distinct paths and IDs (demo, demo-2, ...) instead of
        # colliding. With force=True the caller accepts overwriting the base.
        registry = self._read_registry()
        if force and (ws_resolved / dir_slug).exists():
            unique_dir = dir_slug
        else:
            unique_dir = self._unique_dir_and_id(ws_resolved, dir_slug, registry)

        target = (ws_resolved / unique_dir).resolve()

        # Confinement: target must live under workspace_root. This is defense-
        # in-depth: slugify already neutralizes traversal, but this check also
        # rejects symlink escapes (resolve() follows links).
        try:
            target.relative_to(ws_resolved)
        except ValueError:
            raise ValueError(f"Project target {target} escapes workspace root {ws_resolved}")

        # Reject symlink escape: if target is a symlink pointing outside root.
        if target.is_symlink():
            link_target = target.resolve()
            try:
                link_target.relative_to(ws_resolved)
            except ValueError:
                raise ValueError(f"Symlink {target} escapes workspace root {ws_resolved}")

        # Create on disk via the CLI init helper
        _create_on_disk(
            project_name=name,
            project_path=target,
            template=template,
            copy_from=copy_from,
            force=force,
        )

        project_id = self._dedupe_id(unique_dir, registry)
        project = Project(
            project_id=project_id,
            name=name,
            path=target,
            created_at=datetime.now(timezone.utc).isoformat(),
            template=template,
        )
        self._register(project)
        logger.info(f"Created project {project_id} at {target}")
        return project

    def register_existing(self, path: Path, name: Optional[str] = None) -> Project:
        """
        Register an existing project directory by absolute path.

        Accepts arbitrary absolute paths (the user's own projects), stores the
        resolved-absolute path, and dedupes by path (re-registering the same
        path returns the existing entry). The path must be a valid project
        (``config/`` + ``src/``) at registration time and is re-validated on
        every access.

        Args:
            path: Existing project directory.
            name: Optional display name (defaults to the directory name).

        Returns:
            The registered Project.

        Raises:
            ValueError: If the path is not a valid project.
        """
        resolved = Path(path).resolve()
        if not is_valid_project(resolved):
            raise ValueError(f"Not a valid project (missing config/ or src/): {resolved}")

        display_name = name or resolved.name

        # Dedupe by resolved path: if already registered, return the entry.
        existing = self._find_by_path(resolved)
        if existing is not None:
            return existing

        project_id = self._dedupe_id(slugify_project_id(display_name))
        project = Project(
            project_id=project_id,
            name=display_name,
            path=resolved,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._register(project)
        logger.info(f"Registered existing project {project_id} at {resolved}")
        return project

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def list_projects(self) -> List[Project]:
        """List all registered projects whose paths are still valid on disk."""
        data = self._read_registry()
        projects = []
        for entry in data.values():
            try:
                project = Project(
                    project_id=entry["project_id"],
                    name=entry["name"],
                    path=Path(entry["path"]),
                    created_at=entry["created_at"],
                    template=entry.get("template", "default"),
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"Skipping malformed registry entry {entry!r}: {e}")
                continue
            if is_valid_project(project.path):
                projects.append(project)
        return projects

    def get_project(self, project_id: str) -> Optional[Project]:
        """
        Get a project by ID, re-validating against disk.

        Returns None if the ID is unknown OR the project directory is no longer
        valid on disk (moved/deleted) — this is the path-traversal gate for the
        web layer (callers should surface 404 on None).
        """
        data = self._read_registry()
        entry = data.get(project_id)
        if entry is None:
            return None
        try:
            project = Project(
                project_id=entry["project_id"],
                name=entry["name"],
                path=Path(entry["path"]),
                created_at=entry["created_at"],
                template=entry.get("template", "default"),
            )
        except (KeyError, TypeError):
            return None
        if not is_valid_project(project.path):
            logger.warning(f"Project {project_id} path {project.path} no longer valid")
            return None
        return project

    def get_by_path(self, path: Path) -> Optional[Project]:
        """Get a project by its resolved path, re-validating against disk."""
        resolved = Path(path).resolve()
        return self._find_by_path(resolved)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _find_by_path(self, resolved_path: Path) -> Optional[Project]:
        data = self._read_registry()
        for entry in data.values():
            try:
                p = Path(entry["path"])
            except (KeyError, TypeError):
                continue
            if p.resolve() == resolved_path:
                return Project(
                    project_id=entry["project_id"],
                    name=entry["name"],
                    path=p,
                    created_at=entry["created_at"],
                    template=entry.get("template", "default"),
                )
        return None

    def _dedupe_id(self, base_slug: str, registry: Optional[Dict[str, Dict]] = None) -> str:
        """Return a project_id unique within the registry."""
        data = registry if registry is not None else self._read_registry()
        if base_slug not in data:
            return base_slug
        suffix = 2
        while f"{base_slug}-{suffix}" in data:
            suffix += 1
        return f"{base_slug}-{suffix}"

    def _unique_dir_and_id(self, ws_root: Path, base_slug: str, registry: Dict[str, Dict]) -> str:
        """
        Find a directory slug unique against both the filesystem and registry.

        Avoids collisions with existing directories under ``ws_root`` AND with
        existing registry IDs, so a second "demo" becomes "demo-2".
        """
        candidate = base_slug
        suffix = 2
        while (ws_root / candidate).exists() or candidate in registry:
            candidate = f"{base_slug}-{suffix}"
            suffix += 1
        return candidate

    def _register(self, project: Project) -> None:
        """Upsert a project into the registry (atomic write)."""
        data = self._read_registry()
        data[project.project_id] = {
            "project_id": project.project_id,
            "name": project.name,
            "path": str(project.path),
            "created_at": project.created_at,
            "template": project.template,
        }
        self._write_registry(data)


def default_project_service(registry_path: Optional[Path] = None) -> ProjectService:
    """
    Build the default ProjectService from env/args.

    Workspace root resolution order: ``ENERGIZADOS_WORKSPACE_ROOT`` env →
    ``data/web/workspace`` default. Registry path defaults to
    ``data/web/projects.json`` unless overridden.

    Args:
        registry_path: Optional explicit registry path.

    Returns:
        A configured ProjectService.
    """
    ws = _resolve_workspace_root(None)
    reg = Path(registry_path) if registry_path is not None else Path(DEFAULT_REGISTRY_PATH)
    return ProjectService(workspace_root=ws, registry_path=reg)
