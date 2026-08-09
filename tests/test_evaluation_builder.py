"""Tests for EvaluationBuilder wiring of DefaultEvaluator kwargs.

The builder turns the ``evaluation`` YAML config into a ``DefaultEvaluator``
step. It must forward the new ``segmented_evaluation.thresholds_output_dir``
config key so that users can override the default segment_thresholds_*.json
export destination via YAML.
"""

from energizados.core.builders.evaluation_builder import EvaluationBuilder
from energizados.evaluation.evaluator import DefaultEvaluator


class TestEvaluationBuilderThresholdsOutputDir:
    """TDD tests for the builder propagation of ``thresholds_output_dir``."""

    @staticmethod
    def _config(**overrides):
        """Minimal valid evaluation config with sensible defaults."""
        cfg = {
            "enabled": True,
            "output_dir": "output/reports/evaluation/",
            "segmented_evaluation": {
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
            },
        }
        for k, v in overrides.items():
            if k == "segmented_evaluation":
                cfg["segmented_evaluation"].update(v)
            else:
                cfg[k] = v
        return cfg

    def test_builder_forwards_thresholds_output_dir_from_config(self):
        """``segmented_evaluation.thresholds_output_dir`` is forwarded as a kwarg."""
        config = self._config(
            segmented_evaluation={"thresholds_output_dir": "data/exports/segment_thresholds"},
        )

        step = EvaluationBuilder(config).build()

        assert isinstance(step, DefaultEvaluator)
        assert step.thresholds_output_dir == "data/exports/segment_thresholds"

    def test_builder_defaults_thresholds_output_dir_to_none(self):
        """When the config key is absent, ``thresholds_output_dir`` defaults to None."""
        config = self._config()  # no thresholds_output_dir

        step = EvaluationBuilder(config).build()

        assert isinstance(step, DefaultEvaluator)
        assert step.thresholds_output_dir is None

    def test_builder_forwards_thresholds_output_dir_when_segmented_disabled(self):
        """The override key is forwarded even if segmented_evaluation is disabled —
        users may pre-configure it for a later enable, or the override may be
        intentionally set even with a different threshold_mode."""
        config = self._config(
            segmented_evaluation={
                "enabled": False,
                "thresholds_output_dir": "exports/custom",
            },
        )

        step = EvaluationBuilder(config).build()

        assert isinstance(step, DefaultEvaluator)
        assert step.thresholds_output_dir == "exports/custom"
