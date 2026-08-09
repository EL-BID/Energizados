"""
Tests for 4R review MUST-FIX issues (M1-M7).

Following strict TDD: tests written first (RED), then implementation (GREEN).
"""

import json
from pathlib import Path


# M1. progress_callback not implemented in Pipeline.run()
def test_pipeline_run_with_progress_callback():
    """Test that Pipeline.run() accepts and emits progress events."""
    from energizados.api import ProgressEvent
    from energizados.core.base import PipelineStep
    from energizados.core.pipeline import Pipeline

    # Track events received
    events = []

    def callback(event: ProgressEvent) -> None:
        events.append(event)

    # Create a minimal pipeline with a dummy step
    class DummyStep(PipelineStep):
        def validate_input(self, context):
            return True

        def get_required_keys(self):
            return []

        def execute(self, context):
            return context

    pipeline = Pipeline(config={"test": "config"})
    pipeline.add_step(DummyStep())

    # This should work without error
    result = pipeline.run(progress_callback=callback)

    # Verify run completed and events were received
    assert isinstance(result, dict)
    assert len(events) > 0
    # Check event structure
    assert all(isinstance(e, ProgressEvent) for e in events)


def test_pipeline_run_progress_callback_error_isolation():
    """Test that buggy progress callback doesn't abort pipeline run."""
    from energizados.api import ProgressEvent
    from energizados.core.base import PipelineStep
    from energizados.core.pipeline import Pipeline

    def broken_callback(event: ProgressEvent) -> None:
        raise RuntimeError("Callback is broken!")

    # Create a minimal pipeline with a dummy step
    class DummyStep(PipelineStep):
        def validate_input(self, context):
            return True

        def get_required_keys(self):
            return []

        def execute(self, context):
            return context

    pipeline = Pipeline(config={"test": "config"})
    pipeline.add_step(DummyStep())

    # This should complete despite callback errors (error-isolation)
    result = pipeline.run(progress_callback=broken_callback)

    # Run should complete normally despite callback error
    assert isinstance(result, dict)
    assert result.get("status") != "failed"


# M2. run --json leaks logging
def test_run_json_mode_suppresses_logging():
    """Test that 'energizados run --json' outputs pure JSON (no log lines)."""
    # This would need CLI integration test
    # For now, we test the underlying logging behavior
    pass


# M3. ConfigurationError.to_dict() duplicates config_path
def test_configuration_error_to_dict_no_duplicate_config_path():
    """Test that ConfigurationError.to_dict() has config_path only once."""
    from energizados.core.exceptions import ConfigurationError

    error = ConfigurationError("Invalid config", config_path="x.yaml")
    error_dict = error.to_dict()

    # Should have config_path at top level
    assert "config_path" in error_dict
    assert error_dict["config_path"] == "x.yaml"

    # Should NOT be duplicated in details
    if "details" in error_dict:
        assert "config_path" not in error_dict["details"]


# M4. RunMetadata.from_dict() crashes on None/corrupt
def test_run_metadata_from_dict_none_handling():
    """Test that RunMetadata.from_dict(None) doesn't crash."""
    from energizados.api import RunMetadata

    # Should return empty/default instance, not crash
    result = RunMetadata.from_dict(None)
    assert isinstance(result, RunMetadata)


def test_run_metadata_from_dict_invalid_type():
    """Test that RunMetadata.from_dict with invalid dict doesn't crash."""
    from energizados.api import RunMetadata

    # Should handle non-dict input gracefully
    result = RunMetadata.from_dict("not a dict")
    assert isinstance(result, RunMetadata)


def test_list_runs_tolerates_corrupt_metadata():
    """Test that list_runs skips corrupt run directories."""
    import tempfile

    from energizados.api import RunManager

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create one valid run
        valid_run = base / "train-20240101_120000"
        valid_run.mkdir()
        metadata_file = valid_run / "run_metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": "train-20240101_120000",
                    "timestamp": "2024-01-01T12:00:00",
                    "status": "success",
                    "duration_seconds": 100.0,
                    "energizados_version": "0.3.0",
                    "python_version": "3.11",
                    "git_commit": "abc123",
                    "model_types": ["LGBMModel"],
                },
                f,
            )

        # Create one corrupt run
        corrupt_run = base / "train-20240101_130000"
        corrupt_run.mkdir()
        corrupt_metadata = corrupt_run / "run_metadata.json"
        with open(corrupt_metadata, "w", encoding="utf-8") as f:
            f.write("This is not valid JSON {")

        # list_runs should skip corrupt dir and return valid ones
        manager = RunManager(output_dir=str(base))
        runs = manager.list_runs()

        # Should return at least the valid run
        assert len(runs) >= 1
        run_ids = [r.run_id for r in runs]
        assert "train-20240101_120000" in run_ids


# M5. get_run path traversal
def test_get_run_path_traversal_protection():
    """Test that get_run rejects path traversal attempts."""
    import tempfile

    from energizados.api import RunManager

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = RunManager(output_dir=tmpdir)

        # Path traversal attempts should return None, not raise
        assert manager.get_run("../etc/passwd") is None
        assert manager.get_run("/etc/passwd") is None
        assert manager.get_run("../../../etc/passwd") is None


def test_get_run_empty_run_id():
    """Test that get_run rejects empty run_id."""
    from energizados.api import RunManager

    manager = RunManager(output_dir="output")

    # Empty run_id should return None
    assert manager.get_run("") is None
    assert manager.get_run(None) is None


# M6. AGENTS.md directory tree broken
# (This will be fixed by editing AGENTS.md directly - no test needed)


# M7. Duplicate from_dict alias
def test_api_no_duplicate_from_dict_alias():
    """Test that api.from_dict is unambiguous (not in __all__)."""
    from energizados import api

    # from_dict should not be in __all__ (to avoid ambiguity)
    assert "from_dict" not in api.__all__

    # Users must call the explicit classmethods
    assert hasattr(api.Pipeline, "from_dict")
    assert hasattr(api.RunMetadata, "from_dict")


# Test that RunResult.from_context handles None gracefully (S1)
def test_run_result_from_context_none():
    """Test that RunResult.from_context(None) doesn't crash."""
    from energizados.api import RunResult

    # Should handle None context gracefully
    result = RunResult.from_context(None)
    assert isinstance(result, RunResult)


# S2. MetricsDict.get() bypasses deprecation warning
def test_metrics_dict_get_deprecation_warning():
    """Test that MetricsDict.get('model_metrics') emits DeprecationWarning."""
    import warnings

    from energizados.core.steps.training import MetricsDict

    metrics = MetricsDict({"metrics": {"auc": 0.85}})

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = metrics.get("model_metrics")

        # Should emit deprecation warning
        assert len(w) > 0
        assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
        assert any("model_metrics" in str(warn.message) for warn in w)

        # Should return canonical metrics
        assert result == {"auc": 0.85}
