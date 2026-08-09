"""
Tests for the worker entrypoint (Phase 1 multi-project).

Verifies db_path is resolved to an absolute path and exported via
ENERGIZADOS_JOBS_DB so child processes inherit it (critical after the child
``os.chdir``s into a project directory). Also covers --workspace-root parsing.
"""

from unittest.mock import patch

from energizados.web.worker import parse_args


class TestWorkerArgParse:
    """Test worker command-line argument parsing."""

    def test_parse_args_defaults(self):
        with patch("sys.argv", ["energizados-web-worker"]):
            args = parse_args()

            assert args.db_path == "data/web/jobs.db"
            assert args.log_level == "INFO"
            assert args.workspace_root is None

    def test_parse_args_custom(self):
        with patch(
            "sys.argv",
            [
                "energizados-web-worker",
                "--db-path",
                "/custom/jobs.db",
                "--log-level",
                "DEBUG",
                "--workspace-root",
                "/custom/ws",
            ],
        ):
            args = parse_args()

            assert args.db_path == "/custom/jobs.db"
            assert args.log_level == "DEBUG"
            assert args.workspace_root == "/custom/ws"


class TestWorkerSetup:
    """Test the worker startup setup (db_path resolution + env export)."""

    def test_setup_resolves_db_path_absolute_and_sets_env(self, tmp_path, monkeypatch):
        from energizados.web.worker import setup_worker

        monkeypatch.delenv("ENERGIZADOS_JOBS_DB", raising=False)
        rel_db = str(tmp_path / "jobs.db")

        abs_db, workspace_root = setup_worker(db_path=rel_db, workspace_root=None)

        assert abs_db.is_absolute()
        assert abs_db == tmp_path.resolve() / "jobs.db"
        import os

        assert os.environ["ENERGIZADOS_JOBS_DB"] == str(abs_db)

    def test_setup_explicit_db_path_stays_absolute(self, tmp_path, monkeypatch):
        from energizados.web.worker import setup_worker

        monkeypatch.delenv("ENERGIZADOS_JOBS_DB", raising=False)
        abs_input = tmp_path.resolve() / "custom.db"

        abs_db, _ = setup_worker(db_path=str(abs_input), workspace_root=None)

        assert abs_db == abs_input

    def test_setup_workspace_root_from_arg(self, tmp_path, monkeypatch):
        from energizados.web.worker import setup_worker

        monkeypatch.delenv("ENERGIZADOS_WORKSPACE_ROOT", raising=False)
        ws = tmp_path / "ws"

        _, workspace_root = setup_worker(db_path=str(tmp_path / "j.db"), workspace_root=str(ws))

        assert workspace_root == ws.resolve()

    def test_setup_workspace_root_from_env(self, tmp_path, monkeypatch):
        from energizados.web.worker import setup_worker

        ws = tmp_path / "env_ws"
        monkeypatch.setenv("ENERGIZADOS_WORKSPACE_ROOT", str(ws))

        _, workspace_root = setup_worker(db_path=str(tmp_path / "j.db"), workspace_root=None)

        assert workspace_root == ws.resolve()
