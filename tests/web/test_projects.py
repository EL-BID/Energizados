"""
Tests for ProjectService (Phase 1 multi-project foundation).

ProjectService manages a JSON registry of project directories (bookmarks, not
source of truth) with create-under-workspace-root confinement and
register-existing for arbitrary paths. Every access re-validates against disk.
"""

import json
from pathlib import Path

import pytest

from energizados.web.projects import (
    Project,
    ProjectService,
    default_project_service,
    is_valid_project,
    slugify_project_id,
)


class TestIsValidProject:
    """Test the project-on-disk validator."""

    def test_valid_project_has_config_and_src(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "src").mkdir()

        assert is_valid_project(tmp_path) is True

    def test_invalid_missing_config(self, tmp_path):
        (tmp_path / "src").mkdir()

        assert is_valid_project(tmp_path) is False

    def test_invalid_missing_src(self, tmp_path):
        (tmp_path / "config").mkdir()

        assert is_valid_project(tmp_path) is False

    def test_invalid_nonexistent_path(self, tmp_path):
        assert is_valid_project(tmp_path / "nope") is False


class TestSlugify:
    """Test project_id slug derivation."""

    def test_simple_name(self):
        assert slugify_project_id("My Project") == "my-project"

    def test_underscores_and_spaces(self):
        # Spaces → hyphens, underscores collapsed
        assert slugify_project_id("fraud_demo 2") == "fraud-demo-2"

    def test_special_chars_stripped(self):
        sid = slugify_project_id("Proj! @#Name")
        assert sid == "proj-name"


class TestProjectServiceCreate:
    """Test create_project (lands under workspace_root)."""

    def test_create_lands_under_workspace_root(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        project = svc.create_project("demo")

        assert project.path.parent == ws.resolve()
        assert project.path.is_dir()
        assert (project.path / "config").is_dir()
        assert (project.path / "src").is_dir()
        assert project.project_id == "demo"
        assert project.name == "demo"

    def test_create_persists_to_registry(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        svc.create_project("demo")

        data = json.loads(registry.read_text(encoding="utf-8"))
        assert "demo" in data
        assert Path(data["demo"]["path"]).is_absolute()

    def test_create_outside_root_confined(self, tmp_path):
        """Traversal in the name is neutralized by slugify; result is confined."""
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        # A traversal-ish name must NOT escape workspace_root.
        project = svc.create_project("../escape")

        ws_resolved = ws.resolve()
        # The path is strictly under workspace_root (confined)
        assert project.path.resolve().relative_to(ws_resolved)
        # And the slug is neutralized (no "..")
        assert ".." not in project.path.name

    def test_create_idempotent_slug_dedupe(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        p1 = svc.create_project("demo")
        p2 = svc.create_project("demo")

        assert p1.project_id == "demo"
        # Second "demo" gets a suffixed id; distinct paths
        assert p2.project_id != "demo"
        assert p2.project_id.startswith("demo")
        assert p1.path != p2.path


class TestProjectServiceRegisterExisting:
    """Test register_existing (arbitrary paths)."""

    def test_register_valid_existing(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        # Build a valid existing project on disk
        existing = tmp_path / "external" / "proj"
        (existing / "config").mkdir(parents=True)
        (existing / "src").mkdir(parents=True)

        project = svc.register_existing(existing)

        assert project.path == existing.resolve()
        assert project.project_id == "proj"

    def test_register_invalid_missing_config(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        bad = tmp_path / "bad"
        (bad / "src").mkdir(parents=True)

        with pytest.raises(ValueError):
            svc.register_existing(bad)

    def test_register_invalid_missing_src(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        bad = tmp_path / "bad"
        (bad / "config").mkdir(parents=True)

        with pytest.raises(ValueError):
            svc.register_existing(bad)

    def test_register_dedupe_by_path(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        existing = tmp_path / "proj"
        (existing / "config").mkdir(parents=True)
        (existing / "src").mkdir(parents=True)

        p1 = svc.register_existing(existing)
        p2 = svc.register_existing(existing)

        # Same path → same project_id (deduped, not duplicated)
        assert p1.project_id == p2.project_id


class TestProjectServiceRegistryIO:
    """Test registry persistence: atomic write + reload round-trip."""

    def test_registry_atomic_write_and_reload(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        svc.create_project("alpha")

        # New service instance reads the same registry
        svc2 = ProjectService(workspace_root=ws, registry_path=registry)
        projects = svc2.list_projects()
        ids = [p.project_id for p in projects]
        assert "alpha" in ids

    def test_registry_reload_roundtrip_path(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "projects.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        created = svc.create_project("beta")

        svc2 = ProjectService(workspace_root=ws, registry_path=registry)
        loaded = svc2.get_project("beta")
        assert loaded is not None
        assert loaded.path == created.path


class TestProjectServiceGet:
    """Test get_project and get_by_path."""

    def test_get_project_unknown_id_returns_none(self, tmp_path):
        svc = ProjectService(workspace_root=tmp_path / "ws", registry_path=tmp_path / "p.json")
        assert svc.get_project("nope") is None

    def test_get_project_path_deleted_returns_none(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "p.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        created = svc.create_project("doomed")
        # Delete the project directory on disk
        import shutil

        shutil.rmtree(created.path)

        # Re-validate on access: path no longer valid → None
        assert svc.get_project("doomed") is None

    def test_get_by_path(self, tmp_path):
        ws = tmp_path / "ws"
        registry = tmp_path / "p.json"
        svc = ProjectService(workspace_root=ws, registry_path=registry)

        created = svc.create_project("gamma")

        found = svc.get_by_path(created.path)
        assert found is not None
        assert found.project_id == "gamma"

    def test_get_by_path_unknown(self, tmp_path):
        svc = ProjectService(workspace_root=tmp_path / "ws", registry_path=tmp_path / "p.json")
        assert svc.get_by_path(tmp_path / "unknown") is None


class TestDefaultProjectService:
    """Test the default factory from env."""

    def test_default_from_env(self, tmp_path, monkeypatch):
        ws = tmp_path / "envws"
        registry = tmp_path / "envprojects.json"
        monkeypatch.setenv("ENERGIZADOS_WORKSPACE_ROOT", str(ws))

        svc = default_project_service(registry_path=registry)
        assert svc.workspace_root == ws.resolve()
        assert svc.registry_path == registry


class TestProjectDataclass:
    """Test the Project dataclass."""

    def test_project_fields(self, tmp_path):
        p = Project(
            project_id="x",
            name="X",
            path=tmp_path.resolve(),
            created_at="2024-01-01",
        )
        assert p.project_id == "x"
        assert p.template == "default"  # default
