"""Integration tests for pipeline construction in no-holdout mode."""

from energizados.core.builders.director import PipelineDirector
from energizados.evaluation.evaluator import DefaultEvaluator

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
