"""
Tests for Pipeline.from_dict() and plan() methods - framework-web-ready Phase 3.

Tests for Pipeline dict config support and planning API.
"""

import pytest

from energizados.core.exceptions import ETLDependencyError
from energizados.core.pipeline import ExecutionPlan, Pipeline


class TestPipelineDictConfigSupport:
    """framework-web-ready Phase 3.1: Pipeline.from_dict() classmethod."""

    def test_pipeline_from_dict_basic(self):
        """Pipeline.from_dict() creates Pipeline from dict config."""
        config = {"etl": {"sample": {"enabled": True}}}
        pipeline = Pipeline.from_dict(config)
        assert isinstance(pipeline, Pipeline)
        assert pipeline.config == config

    def test_pipeline_from_dict_equivalence_to_file_path(self):
        """Pipeline.from_dict() equivalent to Pipeline(config_path) when config matches."""
        config = {"etl": {"sample": {"enabled": True}}}

        # Both should create equivalent pipelines
        dict_pipeline = Pipeline.from_dict(config, context=None)
        direct_pipeline = Pipeline(config=config)

        assert dict_pipeline.config == direct_pipeline.config

    def test_pipeline_from_dict_with_context(self):
        """Pipeline.from_dict() accepts optional context parameter."""
        config = {"etl": {"sample": {"enabled": True}}}
        initial_context = {"initial": "data"}

        pipeline = Pipeline.from_dict(config, context=initial_context)
        # Context parameter is reserved for future use - pipeline should work
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_from_dict_invalid_config_no_raise(self):
        """Pipeline.from_dict() accepts invalid dict - validation happens at run time."""
        # Invalid config structure should not raise during instantiation
        invalid_config = {"invalid": True, "structure": "broken"}
        pipeline = Pipeline.from_dict(invalid_config)
        assert isinstance(pipeline, Pipeline)
        # Validation would fail at run time, not during instantiation


class TestPipelinePlanMethod:
    """framework-web-ready Phase 3.2: Pipeline.plan() method."""

    def test_pipeline_plan_returns_execution_plan(self):
        """Pipeline.plan() returns ExecutionPlan with steps and dependencies."""
        config = {
            "etl": {
                "step1": {"enabled": True, "depends_on": []},
                "step2": {"enabled": True, "depends_on": ["step1"]},
            }
        }
        pipeline = Pipeline.from_dict(config)

        plan = pipeline.plan()

        assert isinstance(plan, (dict, ExecutionPlan))
        # Should have steps field
        if hasattr(plan, "steps"):
            assert "step1" in plan.steps
            assert "step2" in plan.steps
        elif isinstance(plan, dict):
            assert "steps" in plan

    def test_pipeline_plan_reveals_dependency_cycle(self):
        """Pipeline.plan() raises ETLDependencyError for circular dependencies."""
        config = {
            "etl": {
                "step1": {"enabled": True, "depends_on": ["step2"]},
                "step2": {"enabled": True, "depends_on": ["step1"]},
            }
        }
        pipeline = Pipeline.from_dict(config)

        with pytest.raises(ETLDependencyError) as exc_info:
            pipeline.plan()

        assert exc_info.value.error_code == "ETL_DEPENDENCY_CYCLE"
        assert "cycle" in str(exc_info.value).lower() or "circular" in str(exc_info.value).lower()

    def test_pipeline_plan_filters_disabled_steps(self):
        """Pipeline.plan() excludes steps with enabled: false."""
        config = {
            "etl": {
                "enabled_step": {"enabled": True, "depends_on": []},
                "disabled_step": {"enabled": False, "depends_on": []},
            }
        }
        pipeline = Pipeline.from_dict(config)

        plan = pipeline.plan()

        # Should only include enabled steps
        if hasattr(plan, "steps"):
            assert "enabled_step" in plan.steps
            assert "disabled_step" not in plan.steps
        elif isinstance(plan, dict) and "steps" in plan:
            assert "enabled_step" in plan["steps"]
            assert "disabled_step" not in plan["steps"]


class TestPipelineBackwardCompatibility:
    """Verify existing Pipeline behavior is preserved."""

    def test_pipeline_config_path_still_works(self):
        """Pipeline(config_path="/path/to/config.yaml") still works."""
        # This test verifies that existing file-based initialization still works
        # (actual file loading would require creating a test YAML file)
        pipeline = Pipeline(config="test_config.yaml")
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_run_returns_dict(self):
        """Pipeline.run() continues to return dict (zero break)."""
        pipeline = Pipeline(config={})

        # Empty pipeline will raise PipelineError, but we can test the return type
        # by adding a mock step
        from energizados.core.base import PipelineStep

        class MockStep(PipelineStep):
            def validate_input(self, context):
                return True

            def execute(self, context):
                return context

        pipeline.add_step(MockStep())
        result = pipeline.run()
        assert isinstance(result, dict)


class TestPipelineProfiling:
    """Tests for the ``profile_memory`` flag on Pipeline.

    When profiling is on, ``on_step_complete`` receives a metrics dict and
    ``pipeline.memory_metrics`` accumulates per-step stats; when off, the
    callback is invoked with ``metrics=None`` (unchanged behavior).
    """

    @staticmethod
    def _alloc_step(name="_AllocStep", alloc_mb=80):
        """Build a PipelineStep subclass that allocates ``alloc_mb`` MB."""
        from energizados.core.base import PipelineStep

        class _AllocStep(PipelineStep):
            def validate_input(self, context):
                return True

            def execute(self, context):
                context["payload"] = bytearray(alloc_mb * 1024 * 1024)
                return context

            def get_required_keys(self):
                return []

            def get_output_keys(self):
                return ["payload"]

        _AllocStep.__name__ = name
        return _AllocStep()

    def test_profile_off_passes_none(self):
        pipeline = Pipeline(config={})
        pipeline.steps = [self._alloc_step()]
        captured = []
        pipeline.on_step_complete = lambda name, i, total, metrics=None: captured.append(
            (name, metrics)
        )
        pipeline.run()
        assert len(captured) == 1
        assert captured[0][1] is None
        assert pipeline.memory_metrics == {}

    def test_profile_on_passes_metrics_dict(self):
        pipeline = Pipeline(config={})
        pipeline.profile_memory = True
        pipeline.steps = [self._alloc_step()]
        captured = []
        pipeline.on_step_complete = lambda name, i, total, metrics=None: captured.append(
            (name, metrics)
        )
        pipeline.run()
        assert len(captured) == 1
        name, metrics = captured[0]
        assert name == "_AllocStep"
        assert metrics is not None
        assert set(metrics.keys()) == {"rss_start", "rss_end", "delta", "peak"}
        assert metrics["peak"] >= metrics["rss_start"] > 0

    def test_profile_on_accumulates_in_state(self):
        pipeline = Pipeline(config={})
        pipeline.profile_memory = True
        pipeline.steps = [self._alloc_step(name="StepA"), self._alloc_step(name="StepB")]
        pipeline.run()
        assert set(pipeline.memory_metrics.keys()) == {"StepA", "StepB"}
        for stats in pipeline.memory_metrics.values():
            assert "peak" in stats
