"""Tests for EDABuilder run-dir relocation (ADR-0001).

When the director runs a typed EDA job it passes ``run_dir``; the report and
artifacts must land inside that run dir, even when the YAML sets
``output.output_dir`` to a different path.
"""

import energizados.core.builders.eda_builder as eda_builder_mod
from energizados.core.builders.eda_builder import EDABuilder


class _FakeExplorer:
    """Records the output_dir / config it was constructed with."""

    def __init__(self, **kwargs):
        eda_builder_mod._captured = {
            "output_dir": kwargs["output_dir"],
            "config": kwargs.get("config"),
        }

    def run(self):
        return {"report_path": "UNUSED"}


def test_run_dir_wins_over_config_output_dir(tmp_path, monkeypatch):
    run_dir = tmp_path / "eda-20260101_1200"
    run_dir.mkdir()

    config = {
        "enabled": True,
        "data_sources": {"primary": {"path": "x.parquet", "target_col": "target"}},
        "output": {"output_dir": "output/eda/", "report_name": "eda_report.html"},
        "sections": {},
    }

    monkeypatch.setattr(eda_builder_mod, "DatasetExplorer", _FakeExplorer)

    builder = EDABuilder(config, run_dir=run_dir)
    step = builder.build()
    assert step is not None
    step.execute({})

    captured = eda_builder_mod._captured
    # Explicit kwarg must point at the run dir
    assert captured["output_dir"] == str(run_dir)
    # Config handed to DatasetExplorer must also resolve output_dir to run dir
    assert captured["config"]["output"]["output_dir"] == str(run_dir)
    # Original caller config must NOT be mutated
    assert config["output"]["output_dir"] == "output/eda/"


def test_no_run_dir_honors_config_output_dir(monkeypatch):
    config = {
        "enabled": True,
        "data_sources": {"primary": {"path": "x.parquet"}},
        "output": {"output_dir": "output/eda/"},
        "sections": {},
    }

    monkeypatch.setattr(eda_builder_mod, "DatasetExplorer", _FakeExplorer)

    builder = EDABuilder(config, run_dir=None)
    step = builder.build()
    step.execute({})

    captured = eda_builder_mod._captured
    assert captured["output_dir"] == "output/eda/"
    assert captured["config"]["output"]["output_dir"] == "output/eda/"
