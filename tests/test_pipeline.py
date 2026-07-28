"""Integration tests for pipeline construction in no-holdout mode."""

from energizados.core.builders.director import (
    PipelineDirector,  # type: ignore[import-untyped]
)
from energizados.evaluation.evaluator import (
    DefaultEvaluator,  # type: ignore[import-untyped]
)

_NO_HOLDOUT_CONFIG = """
train:
  enabled: true
  input_path: data/x.parquet
  target_column: target
  output_base_dir: output
  split:
    method: none
    splits_dir: data/splits
  models:
    - type: lightgbm
  evaluation:
    enabled: true
    threshold: 0.5
    metrics: [auc]
"""


class TestPipelineNoHoldout:
    """FR4: director auto-skips evaluation when split.method='none'."""

    def test_pipeline_no_holdout_eval_skipped(self, tmp_path, caplog):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(_NO_HOLDOUT_CONFIG)
        director = PipelineDirector(str(cfg_path))
        pipeline = director.build()
        steps = getattr(pipeline, "steps", [])
        has_evaluator = any(isinstance(st, DefaultEvaluator) for st in steps)
        assert not has_evaluator, "Evaluator step should be skipped in no-holdout mode"
        assert any(
            "split.method is 'none'" in rec.getMessage()
            for rec in caplog.records
            if rec.levelname == "WARNING"
        )


class TestPipelinePlan:
    """Tests for ``Pipeline.plan()`` with ETL configurations."""

    def test_plan_respects_etl_dependencies(self, tmp_path):
        """``plan()`` must return the topological execution order from
        ``ETLOrchestrator.build_execution_order()``, not the dict-insertion
        order fallback.

        Regression: ``pipeline.py`` called ``orchestrator.get_execution_order()``
        (a method that does not exist) which raised ``AttributeError`` and was
        silently caught by a broad ``except Exception`` — returning a plan with
        ETLs in raw config order and ignoring ``depends_on``.
        """
        from energizados.core.pipeline import Pipeline  # type: ignore[import-untyped]

        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "etl:\n  a:\n    enabled: true\n    depends_on: [b]\n  b:\n    enabled: true\n"
        )
        pipeline = Pipeline(config_path=str(cfg))
        plan = pipeline.plan()

        # b must execute before a (a depends on b)
        assert plan.steps == ["b", "a"]
        assert plan.dependencies == {"a": ["b"], "b": []}
