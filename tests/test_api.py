"""
Tests for the energizados.api package.

Following strict TDD: tests written first (RED), then implementation (GREEN).
"""

import json
from datetime import datetime, timezone

import pytest


# Test imports and __all__ exports
def test_api_public_surface():
    """Test that api.__all__ exports are importable."""
    from energizados import api

    # Check that __all__ is defined
    assert hasattr(api, "__all__")
    expected_exports = [
        "validate_dict",
        "ValidationResult",
        "ConfigError",
        "ConfigWarning",
        "ConfigInfo",
        "Pipeline",
        "ConfigPipelineBuilder",  # PR1 task 1.1: new re-export
        # NOTE: from_dict removed from __all__ to avoid ambiguity (M7 fix)
        "RunManager",
        "RunResult",
        "RunMetadata",
        "ProgressEvent",
        "console_progress",
        "format_error",
        "merge_configs",
        "doctor",
        "DoctorReport",
        "CheckResult",
    ]
    assert set(api.__all__) == set(expected_exports)

    # Check that each export is actually importable
    for export in expected_exports:
        assert hasattr(api, export), f"Missing export: {export}"


# Test validate_dict
def test_validate_dict_valid_config():
    """Test validate_dict with valid ETL config."""
    from energizados.api import validate_dict

    valid_config = {
        "etl": {
            "sample": {
                "enabled": True,
                "input": "data/raw/sample_dataset.parquet",
                "output": "data/processed/sample_dataset.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "params": {"mode": "concat"},
                "depends_on": [],
            }
        }
    }

    result = validate_dict(valid_config, "etl")
    assert result.is_valid
    assert len(result.errors) == 0
    assert isinstance(result.warnings, list)
    assert isinstance(result.info, list)


def test_validate_dict_invalid_config():
    """Test validate_dict with invalid config (missing required fields)."""
    from energizados.api import validate_dict

    invalid_config = {
        "etl": {
            "broken_etl": {
                "enabled": True,
                # Missing required fields: input, output, custom_class
            }
        }
    }

    result = validate_dict(invalid_config, "etl")
    assert not result.is_valid
    assert len(result.errors) > 0
    # Should complain about missing custom_class at minimum
    error_messages = [str(e) for e in result.errors]
    assert any("custom_class" in str(e) for e in error_messages)


def test_validate_dict_unknown_type():
    """Test validate_dict with unknown config_type raises ConfigurationError."""
    from energizados.api import validate_dict
    from energizados.core.exceptions import ConfigurationError

    valid_config = {"etl": {}}

    with pytest.raises(ConfigurationError) as exc_info:
        validate_dict(valid_config, "unknown_type")

    assert exc_info.value.error_code == "CONFIG_UNKNOWN_TYPE"


def test_validation_result_to_dict():
    """Test ValidationResult.to_dict returns JSON-serializable dict."""
    from energizados.api import ConfigError, ValidationResult

    result = ValidationResult()
    result.is_valid = False
    result.errors = [ConfigError(field="test", message="Test error", location="etl.test")]
    result.warnings = []
    result.info = []

    result_dict = result.to_dict()
    assert result_dict["is_valid"] is False
    assert len(result_dict["errors"]) == 1
    assert result_dict["errors"][0]["field"] == "test"
    assert result_dict["warnings"] == []
    assert result_dict["info"] == []

    # Verify JSON serializable
    json.dumps(result_dict)


# Test RunResult
def test_run_result_from_context():
    """Test RunResult.from_context extracts fields correctly."""
    from energizados.api import RunResult

    context = {
        "run_id": "test-run-123",
        "status": "success",
        "start_time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "end_time": datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
        "metrics": {"auc": 0.85, "f1": 0.78},
        "output_paths": {"model": "/path/to/model.pkl"},
        "extra_field": "should_be_preserved_in_context",
    }

    result = RunResult.from_context(context)

    assert result.run_id == "test-run-123"
    assert result.status == "success"
    assert result.start_time == context["start_time"]
    assert result.end_time == context["end_time"]
    assert result.metrics == {"auc": 0.85, "f1": 0.78}
    assert result.output_paths == {"model": "/path/to/model.pkl"}

    # Context reference is preserved (not copied)
    assert result._context is context
    assert result._context["extra_field"] == "should_be_preserved_in_context"


def test_run_result_to_dict():
    """Test RunResult.to_dict returns JSON-serializable dict."""
    from datetime import datetime, timezone

    from energizados.api import RunResult

    context = {
        "run_id": "test-run-123",
        "status": "success",
        "start_time": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        "end_time": datetime(2024, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
        "metrics": {"auc": 0.85},
        "output_paths": {},
    }

    result = RunResult.from_context(context)
    result_dict = result.to_dict()

    assert result_dict["run_id"] == "test-run-123"
    assert result_dict["status"] == "success"
    assert result_dict["start_time"] == "2024-01-01T12:00:00+00:00"
    assert result_dict["end_time"] == "2024-01-01T12:30:00+00:00"
    assert result_dict["metrics"] == {"auc": 0.85}

    # Verify JSON serializable
    json.dumps(result_dict)


def test_run_result_from_context_missing_metrics():
    """Test RunResult.from_context handles missing metrics gracefully."""
    from energizados.api import RunResult

    context = {
        "run_id": "test-run-123",
        "status": "success",
        # No metrics, no output_paths
    }

    result = RunResult.from_context(context)
    assert result.metrics == {}
    assert result.output_paths == {}


# Test ProgressEvent
def test_progress_event_to_dict():
    """Test ProgressEvent.to_dict returns JSON-serializable dict."""
    from datetime import datetime, timezone

    from energizados.api import ProgressEvent

    fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    event = ProgressEvent(
        run_id="test-run",
        step_name="ETLStep",
        phase="start",
        message="Starting ETL",
        percent=0.0,
        timestamp=fixed_time,
    )

    event_dict = event.to_dict()
    assert event_dict["run_id"] == "test-run"
    assert event_dict["step_name"] == "ETLStep"
    assert event_dict["phase"] == "start"
    assert event_dict["message"] == "Starting ETL"
    assert event_dict["percent"] == 0.0
    assert event_dict["timestamp"] == "2024-01-01T12:00:00+00:00"

    # Verify JSON serializable
    json.dumps(event_dict)


def test_progress_event_defaults():
    """Test ProgressEvent default values."""
    from energizados.api import ProgressEvent

    event = ProgressEvent(run_id="test", step_name="Test", phase="complete", message="Done")
    assert event.percent is None
    assert isinstance(event.timestamp, datetime)


# Test format_error
def test_format_error_energizados_error():
    """Test format_error with EnergizadosError."""
    from energizados.api import format_error
    from energizados.core.exceptions import ConfigurationError

    error = ConfigurationError("Invalid config", config_path="/path/to/config.yaml")
    error_dict = format_error(error)

    assert error_dict["error_code"] == "CONFIG_INVALID"
    assert "Invalid config" in error_dict["message"]  # Message is modified by ConfigurationError
    assert "config_path" in error_dict
    assert error_dict["config_path"] == "/path/to/config.yaml"


def test_format_error_generic_exception():
    """Test format_error with generic Exception."""
    from energizados.api import format_error

    error = ValueError("Some error")
    error_dict = format_error(error)

    assert "error_code" in error_dict
    assert error_dict["message"] == "Some error"
    assert error_dict["error_type"] == "ValueError"


# Test merge_configs
def test_merge_configs_last_wins():
    """Test merge_configs follows 'last wins' semantics."""
    from energizados.api import merge_configs

    config1 = {"etl": {"etl1": {"value": 1}}, "train": {"epochs": 10}}
    config2 = {"etl": {"etl2": {"value": 2}}, "train": {"epochs": 20}}

    merged = merge_configs([config1, config2])

    # ETL should be deep-merged (both etl1 and etl2 present)
    assert "etl1" in merged["etl"]
    assert "etl2" in merged["etl"]
    # Scalar values follow last-wins
    assert merged["train"]["epochs"] == 20


def test_merge_configs_dict_merge():
    """Test merge_configs deep merges dict values."""
    from energizados.api import merge_configs

    config1 = {"train": {"models": [{"name": "lgbm"}], "epochs": 10}}
    config2 = {"train": {"models": [{"name": "catboost"}], "batch_size": 32}}

    merged = merge_configs([config1, config2])

    # models should be from config2 (last wins for lists)
    assert merged["train"]["models"] == [{"name": "catboost"}]
    # epochs from config1
    assert merged["train"]["epochs"] == 10
    # batch_size from config2
    assert merged["train"]["batch_size"] == 32


# Test doctor
def test_doctor_returns_structured_report():
    """Test doctor() returns structured DoctorReport."""
    from energizados.api import DoctorReport, doctor

    report = doctor()

    assert isinstance(report, DoctorReport)
    assert hasattr(report, "system_info")
    assert hasattr(report, "checks")
    assert isinstance(report.system_info, dict)
    assert isinstance(report.checks, list)
    assert len(report.system_info) > 0
    assert len(report.checks) > 0


def test_doctor_report_has_system_info():
    """Test doctor report contains expected system info keys."""
    from energizados.api import doctor

    report = doctor()
    expected_keys = ["python_version", "platform", "energizados_version"]
    for key in expected_keys:
        assert key in report.system_info


def test_doctor_report_has_hardware_info():
    """Regression: doctor() must gather CPU/memory/disk info via psutil.

    The CLI previously relied on api.doctor() for system_info, but the
    hardware collection (get_system_info in cli/doctor.py) was never
    invoked, rendering an empty System Summary panel.
    """
    import psutil

    from energizados.api import doctor

    report = doctor()

    hardware_keys = [
        "cpu_physical_cores",
        "cpu_logical_cores",
        "cpu_freq_mhz",
        "cpu_usage",
        "memory_total",
        "memory_available",
        "memory_percent",
        "disk_total",
        "disk_used",
        "disk_free",
        "disk_percent",
    ]
    for key in hardware_keys:
        assert key in report.system_info, f"missing key: {key}"
        assert report.system_info[key], f"empty value for {key}"

    # With psutil installed, values must be real (not the fallback message)
    assert psutil is not None  # ensures the test env has psutil
    assert "install psutil" not in report.system_info["memory_total"]
    assert "Unknown" not in report.system_info["memory_total"]


def test_doctor_report_checks_have_required_fields():
    """Test doctor report checks have name, status, message."""
    from energizados.api import doctor

    report = doctor()
    for check in report.checks:
        assert hasattr(check, "name")
        assert hasattr(check, "status")
        assert hasattr(check, "message")
        assert check.status in ["ok", "warning", "error"]


def test_required_packages_separate_import_name_from_pypi_name():
    """Regression: REQUIRED_PACKAGES must use the Python import name as key,
    not the PyPI name. Importing scikit-learn by its PyPI name always fails
    because the import name is ``sklearn``; same for PyYAML (imports as ``yaml``).

    This pins the bug from issue #40 (doctor always reported scikit-learn missing).
    """
    from energizados.api.config import REQUIRED_PACKAGES

    # The bug was using "scikit-learn" as the import key.
    assert "scikit-learn" not in REQUIRED_PACKAGES
    assert "sklearn" in REQUIRED_PACKAGES
    # And the value must carry the PyPI name for the install hint.
    assert REQUIRED_PACKAGES["sklearn"][0] == "scikit-learn"

    # Same shape for PyYAML.
    assert "pyyaml" not in REQUIRED_PACKAGES
    assert "yaml" in REQUIRED_PACKAGES
    assert REQUIRED_PACKAGES["yaml"][0] == "pyyaml"


def test_find_missing_packages_uses_import_name_not_pypi_name():
    """Regression for issue #40: _find_missing_packages must call
    ``__import__(import_name)`` (sklearn, yaml), not ``__import__(pypi_name)``
    (scikit-learn, pyyaml). Returns pypi names in the install hint.
    """
    from energizados.api.config import _find_missing_packages

    # All keys here are importable in the test environment → none reported missing.
    installed = {
        "sklearn": ("scikit-learn", "1.4.2"),
        "yaml": ("pyyaml", "6.0"),
    }
    assert _find_missing_packages(installed) == []

    # A genuinely unimportable module returns its PyPI name (for pip install).
    bogus = {
        "definitely_not_a_real_module_xyz": ("real-pypi-name", "1.0"),
    }
    assert _find_missing_packages(bogus) == ["real-pypi-name"]


# Test Pipeline re-export
def test_pipeline_reexport():
    """Test that api.Pipeline is the same as core.Pipeline."""
    from energizados.api import Pipeline
    from energizados.core.pipeline import Pipeline as CorePipeline

    assert Pipeline is CorePipeline


def test_pipeline_from_dict_via_api():
    """Test that Pipeline.from_dict is accessible via api."""
    from energizados.api import Pipeline

    config = {"train": {"enabled": True}}
    pipeline = Pipeline.from_dict(config)

    assert isinstance(pipeline, Pipeline)
    assert pipeline.config == config


# Test RunManager and RunMetadata re-exports
def test_run_manager_reexport():
    """Test that api.RunManager is the same as core.builders.run_manager.RunManager."""
    from energizados.api import RunManager
    from energizados.core.builders.run_manager import RunManager as CoreRunManager

    assert RunManager is CoreRunManager


def test_run_metadata_reexport():
    """Test that api.RunMetadata is the same as core.builders.run_manager.RunMetadata."""
    from energizados.api import RunMetadata
    from energizados.core.builders.run_manager import RunMetadata as CoreRunMetadata

    assert RunMetadata is CoreRunMetadata


def test_api_from_dict_not_in_public_surface():
    """Test that api.from_dict is not in __all__ to avoid ambiguity (M7 fix)."""
    from energizados import api

    # from_dict should not be in __all__
    assert "from_dict" not in api.__all__

    # But the class methods should still be accessible
    assert hasattr(api.Pipeline, "from_dict")
    assert hasattr(api.RunMetadata, "from_dict")

    # Internal alias exists but is not public
    assert hasattr(api, "from_dict")


# Test ConfigPipelineBuilder re-export (PR1 task 1.2)
def test_config_pipeline_builder_reexport():
    """Test that ConfigPipelineBuilder is importable from energizados.api (PR1 task 1.2)."""
    from energizados.api import ConfigPipelineBuilder
    from energizados.core.pipeline import (
        ConfigPipelineBuilder as CoreConfigPipelineBuilder,
    )

    # Should be the same class
    assert ConfigPipelineBuilder is CoreConfigPipelineBuilder

    # Should be in __all__
    from energizados import api

    assert "ConfigPipelineBuilder" in api.__all__


def test_config_pipeline_builder_instantiable_via_api():
    """Test that ConfigPipelineBuilder can be instantiated via API (PR1 task 1.2)."""
    from energizados.api import ConfigPipelineBuilder

    # Should be instantiable with config dict
    config = {
        "train": {"enabled": True, "input_path": "data/test.parquet", "target_column": "target"}
    }
    builder = ConfigPipelineBuilder(config=config)

    assert isinstance(builder, ConfigPipelineBuilder)
    # Config is stored internally in _director, not exposed
    assert hasattr(builder, "_director")
    assert builder._director.config_path is None  # config dict takes precedence
