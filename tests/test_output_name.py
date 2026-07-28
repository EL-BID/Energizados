"""Tests for the ``output_name`` config option.

Behavioral contract (mirrors ``output_base_dir``):

``output_name`` sets the run-directory NAME — the same thing the CLI ``-n`` /
``--name`` flag does. When present in a config section it is used as the run
name; the CLI ``-n`` takes PRECEDENCE over the config value (explicit override).

Resolution priority across sections is ``train > infer > eda > etl`` (identical
to ``_resolve_base_output_dir``). When no section sets it, ``None`` is returned
and the run dir falls back to the timestamped default.
"""

import pytest

from energizados.core.builders.director import PipelineDirector


class TestDirectorResolveOutputName:
    """PipelineDirector._resolve_output_name mirrors output_base_dir resolution."""

    @pytest.fixture(autouse=True)
    def _bypass_validation(self, monkeypatch):
        monkeypatch.setattr(
            "energizados.core.schemas.config_validator.ConfigValidator.validate_config",
            lambda self, cfg, name: [],
        )

    def _director(self, config, tmp_path, monkeypatch, run_name=None):
        monkeypatch.chdir(tmp_path)
        return PipelineDirector(config=config, run_name=run_name)

    def test_resolve_output_name_defaults_to_none(self, tmp_path, monkeypatch):
        d = self._director({"eda": {"enabled": True}}, tmp_path, monkeypatch)
        assert d._resolve_output_name() is None

    def test_resolve_output_name_from_train(self, tmp_path, monkeypatch):
        d = self._director(
            {"train": {"enabled": True, "output_name": "exp-train"}}, tmp_path, monkeypatch
        )
        assert d._resolve_output_name() == "exp-train"

    def test_resolve_output_name_from_infer(self, tmp_path, monkeypatch):
        d = self._director(
            {"infer": {"enabled": True, "output_name": "exp-infer"}}, tmp_path, monkeypatch
        )
        assert d._resolve_output_name() == "exp-infer"

    def test_resolve_output_name_from_etl(self, tmp_path, monkeypatch):
        d = self._director(
            {"etl": {"output_name": "exp-etl", "sample": {"enabled": True}}}, tmp_path, monkeypatch
        )
        assert d._resolve_output_name() == "exp-etl"

    def test_resolve_output_name_priority_train_over_infer(self, tmp_path, monkeypatch):
        d = self._director(
            {
                "train": {"enabled": True, "output_name": "from-train"},
                "infer": {"output_name": "from-infer"},
            },
            tmp_path,
            monkeypatch,
        )
        assert d._resolve_output_name() == "from-train"

    def test_resolve_output_name_priority_infer_over_etl(self, tmp_path, monkeypatch):
        d = self._director(
            {
                "infer": {"output_name": "from-infer"},
                "etl": {"output_name": "from-etl"},
            },
            tmp_path,
            monkeypatch,
        )
        assert d._resolve_output_name() == "from-infer"


class TestDirectorBuildUsesOutputName:
    """build() threads output_name into the run dir; CLI run_name wins."""

    @pytest.fixture(autouse=True)
    def _bypass_validation(self, monkeypatch):
        monkeypatch.setattr(
            "energizados.core.schemas.config_validator.ConfigValidator.validate_config",
            lambda self, cfg, name: [],
        )

    def _director(self, config, tmp_path, monkeypatch, run_name=None):
        monkeypatch.chdir(tmp_path)
        return PipelineDirector(config=config, run_name=run_name)

    def test_build_uses_config_output_name_as_run_dir(self, tmp_path, monkeypatch):
        d = self._director(
            {"eda": {"enabled": True, "output_name": "my-exp"}}, tmp_path, monkeypatch
        )
        d.build()
        assert d.run_manager.run_dir is not None
        assert d.run_manager.run_dir.name == "my-exp"

    def test_cli_run_name_overrides_config_output_name(self, tmp_path, monkeypatch):
        d = self._director(
            {"eda": {"enabled": True, "output_name": "cfg-name"}},
            tmp_path,
            monkeypatch,
            run_name="cli-name",
        )
        d.build()
        assert d.run_manager.run_dir.name == "cli-name"

    def test_build_without_output_name_uses_timestamped_default(self, tmp_path, monkeypatch):
        d = self._director({"eda": {"enabled": True}}, tmp_path, monkeypatch)
        d.build()
        assert d.run_manager.run_dir is not None
        # Default is a typed prefix + timestamp, NOT a bare custom name.
        assert d.run_manager.run_dir.name.startswith("eda-")
