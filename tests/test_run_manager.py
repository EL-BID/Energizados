"""
Unit tests for RunManager run metadata persistence.

Tests cover:
- finalize_run() writes run_metadata.json
- Metadata includes version, git, duration, model info
- Backward compat when context is None
- Git/version fallback to "unknown"
- RunMetadata.from_dict() tolerant loader (Phase 4)
- RunManager query API (Phase 4)
"""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from energizados.core.builders.run_manager import RunManager
from energizados.core.exceptions import ConfigurationError


class TestRunMetadata:
    """Tests for run_metadata.json persistence."""

    def test_finalize_run_creates_metadata_file(self, tmp_path):
        """finalize_run() creates run_metadata.json when context is provided."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        metadata_path = tmp_path / "run_metadata.json"
        assert metadata_path.exists()

    def test_metadata_contains_version_info(self, tmp_path):
        """run_metadata.json contains energizados_version and python_version."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        with open(tmp_path / "run_metadata.json") as f:
            metadata = json.load(f)

        assert "energizados_version" in metadata
        assert "python_version" in metadata
        assert isinstance(metadata["energizados_version"], str)
        assert isinstance(metadata["python_version"], str)

    def test_metadata_contains_duration(self, tmp_path):
        """run_metadata.json contains duration_seconds."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        with open(tmp_path / "run_metadata.json") as f:
            metadata = json.load(f)

        assert "duration_seconds" in metadata
        assert isinstance(metadata["duration_seconds"], (int, float))
        assert metadata["duration_seconds"] >= 0

    def test_metadata_contains_run_id(self, tmp_path):
        """run_metadata.json contains run_id."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        with open(tmp_path / "run_metadata.json") as f:
            metadata = json.load(f)

        assert "run_id" in metadata
        assert isinstance(metadata["run_id"], str)

    def test_metadata_contains_config_files(self, tmp_path):
        """run_metadata.json contains config_files list."""
        rm = RunManager(config_paths=["config/train.yaml", "config/etl.yaml"])
        rm._run_dir = tmp_path

        rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        with open(tmp_path / "run_metadata.json") as f:
            metadata = json.load(f)

        assert "config_files" in metadata
        assert metadata["config_files"] == ["train.yaml", "etl.yaml"]

    def test_git_commit_fallback_on_failure(self, tmp_path):
        """Git commit defaults to 'unknown' when git command fails."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        with patch(
            "energizados.core.builders.run_manager.subprocess.run", side_effect=Exception("no git")
        ):
            rm.finalize_run(context={"val_auc": 0.85, "val_f1": 0.72})

        with open(tmp_path / "run_metadata.json") as f:
            metadata = json.load(f)

        assert metadata.get("git_commit") == "unknown"

    def test_backward_compat_no_context(self, tmp_path):
        """finalize_run() works with context=None (backward compat, no metadata written)."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        # Must not raise — backward compatible
        rm.finalize_run(context=None)

        # No metadata file when context=None (requires context for full metadata)
        assert not (tmp_path / "run_metadata.json").exists()


class TestRunMetadataTolerantLoader:
    """Test RunMetadata.from_dict() tolerant loader (Phase 4)."""

    def test_from_dict_with_all_fields(self):
        """Test loading with all fields present."""
        from energizados.core.builders.run_manager import RunMetadata

        data = {
            "run_id": "train-20240101_120000",
            "timestamp": "2024-01-01T12:00:00",
            "duration_seconds": 123.45,
            "energizados_version": "0.2.7",
            "python_version": "3.10.12",
            "git_commit": "abc123",
            "model_types": ["LGBMModel"],
            "status": "success",
            "val_auc": 0.85,
            "val_f1": 0.78,
            "feature_count": 42,
            "config_files": ["train.yaml"],
            "output_paths": {"model": "output/train-20240101_120000/models/model.pkl"},
        }

        metadata = RunMetadata.from_dict(data)

        assert metadata.run_id == "train-20240101_120000"
        assert metadata.timestamp == "2024-01-01T12:00:00"
        assert metadata.duration_seconds == 123.45
        assert metadata.energizados_version == "0.2.7"
        assert metadata.python_version == "3.10.12"
        assert metadata.git_commit == "abc123"
        assert metadata.model_types == ["LGBMModel"]
        assert metadata.status == "success"
        assert metadata.val_auc == 0.85
        assert metadata.val_f1 == 0.78
        assert metadata.feature_count == 42
        assert metadata.config_files == ["train.yaml"]
        assert metadata.output_paths == {"model": "output/train-20240101_120000/models/model.pkl"}

    def test_from_dict_tolerant_missing_fields(self):
        """Test tolerant loader supplies defaults for missing fields."""
        from energizados.core.builders.run_manager import RunMetadata

        # Old run metadata without status and output_paths
        data = {
            "run_id": "train-20240101_120000",
            "timestamp": "2024-01-01T12:00:00",
            "duration_seconds": 123.45,
            "energizados_version": "0.2.6",
            "python_version": "3.10.12",
            "git_commit": "abc123",
            "model_types": ["LGBMModel"],
            # Missing: status, val_auc, val_f1, feature_count, config_files, output_paths
        }

        metadata = RunMetadata.from_dict(data)

        assert metadata.run_id == "train-20240101_120000"
        assert metadata.status == "success"  # Default for old runs
        assert metadata.val_auc is None
        assert metadata.val_f1 is None
        assert metadata.feature_count is None
        assert metadata.config_files == []  # Default empty list
        assert metadata.output_paths == {}  # Default empty dict

    def test_from_dict_with_minimal_data(self):
        """Test loading with only required fields."""
        from energizados.core.builders.run_manager import RunMetadata

        data = {
            "run_id": "train-20240101_120000",
        }

        metadata = RunMetadata.from_dict(data)

        assert metadata.run_id == "train-20240101_120000"
        assert metadata.status == "success"  # Default
        assert metadata.output_paths == {}  # Default


# Test EDA output_paths (PR1 tasks 1.3-1.4)
class TestEDAOutputPaths:
    """Test EDA report path is added to output_paths (PR1 task 1.4)."""

    def test_write_run_metadata_with_eda_report(self, tmp_path):
        """Test that EDA report_path is added to output_paths (PR1 task 1.4)."""
        rm = RunManager(config_paths=["config/eda.yaml"])
        rm._run_dir = tmp_path

        # Context with EDA results (as generated by EDABuilder)
        context = {
            "eda_results": {
                "report_path": str(tmp_path / "eda_report.html"),
                "dataset_path": "data/processed/sample.parquet",
            }
        }

        rm.finalize_run(context=context)

        # Verify metadata was written
        metadata_path = tmp_path / "run_metadata.json"
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Check that output_paths contains eda_report
        assert "output_paths" in metadata
        assert "eda_report" in metadata["output_paths"]
        assert metadata["output_paths"]["eda_report"] == str(tmp_path / "eda_report.html")

    def test_write_run_metadata_without_eda_results(self, tmp_path):
        """Test that non-EDA runs don't get eda_report in output_paths (PR1 task 1.4)."""
        rm = RunManager(config_paths=["config/train.yaml"])
        rm._run_dir = tmp_path

        # Context without EDA results (normal training run)
        context = {
            "val_auc": 0.85,
            "val_f1": 0.72,
            "model_path": str(tmp_path / "models" / "model.pkl"),
        }

        rm.finalize_run(context=context)

        # Verify metadata was written
        metadata_path = tmp_path / "run_metadata.json"
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Check that output_paths does NOT contain eda_report
        assert "output_paths" in metadata
        assert "eda_report" not in metadata["output_paths"]

    def test_write_run_metadata_with_eda_results_missing_report_path(self, tmp_path):
        """Test that eda_results without report_path doesn't add key (PR1 task 1.4)."""
        rm = RunManager(config_paths=["config/eda.yaml"])
        rm._run_dir = tmp_path

        # Context with eda_results but missing report_path
        context = {
            "eda_results": {
                "dataset_path": "data/processed/sample.parquet",
                # Missing report_path
            }
        }

        rm.finalize_run(context=context)

        # Verify metadata was written
        metadata_path = tmp_path / "run_metadata.json"
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Check that output_paths does NOT contain eda_report
        assert "output_paths" in metadata
        assert "eda_report" not in metadata["output_paths"]


class TestRunManagerQueryAPI:
    """Test RunManager query methods (Phase 4)."""

    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """Create a temporary output directory with fake run data."""
        from datetime import datetime

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create fake run directories with metadata
        runs = [
            "train-20240101_120000",
            "eda-20240102_130000",
            "inference-20240103_140000",
            "train-20240104_150000",
        ]

        for i, run_id in enumerate(runs):
            run_dir = output_dir / run_id
            run_dir.mkdir()

            # Create incrementing timestamps so they sort properly
            timestamp = datetime(2024, 1, 1, 12, 0, 0) + pd.Timedelta(hours=i)

            metadata = {
                "run_id": run_id,
                "timestamp": timestamp.isoformat(),
                "duration_seconds": 100.0 + i,
                "energizados_version": "0.2.7",
                "python_version": "3.10.12",
                "git_commit": "abc123",
                "model_types": ["LGBMModel"],
                "status": "success",
                "val_auc": 0.8 + (i * 0.01),
                "val_f1": 0.75 + (i * 0.01),
                "config_files": ["train.yaml"],
                "output_paths": {"model": f"{run_id}/model.pkl"},
            }

            with open(run_dir / "run_metadata.json", "w") as f:
                json.dump(metadata, f)

        # Create a directory that doesn't look like a run (no metadata)
        junk_dir = output_dir / "not_a_run"
        junk_dir.mkdir()

        return str(output_dir)

    def test_get_run_existing(self, temp_output_dir):
        """Test get_run returns RunMetadata for existing run."""
        manager = RunManager(output_dir=temp_output_dir)
        metadata = manager.get_run("train-20240101_120000")

        assert metadata is not None
        assert metadata.run_id == "train-20240101_120000"
        assert metadata.status == "success"
        assert metadata.val_auc == 0.8

    def test_get_run_nonexistent(self, temp_output_dir):
        """Test get_run returns None for nonexistent run."""
        manager = RunManager(output_dir=temp_output_dir)
        metadata = manager.get_run("nonexistent_run")

        assert metadata is None

    def test_get_run_missing_metadata_file(self, temp_output_dir):
        """Test get_run returns None for run without metadata file."""
        # Create a run directory without metadata file
        output_path = Path(temp_output_dir)
        empty_run = output_path / "empty_run"
        empty_run.mkdir()

        manager = RunManager(output_dir=temp_output_dir)
        metadata = manager.get_run("empty_run")

        assert metadata is None

    def test_list_runs_all(self, temp_output_dir):
        """Test list_runs returns all runs sorted by timestamp descending."""
        manager = RunManager(output_dir=temp_output_dir)
        runs = manager.list_runs()

        assert len(runs) == 4
        # Check descending order by timestamp (most recent first)
        assert runs[0].run_id == "train-20240104_150000"
        assert runs[1].run_id == "inference-20240103_140000"
        assert runs[2].run_id == "eda-20240102_130000"
        assert runs[3].run_id == "train-20240101_120000"

    def test_list_runs_with_limit(self, temp_output_dir):
        """Test list_runs respects limit parameter."""
        manager = RunManager(output_dir=temp_output_dir)
        runs = manager.list_runs(limit=2)

        assert len(runs) == 2
        assert runs[0].run_id == "train-20240104_150000"
        assert runs[1].run_id == "inference-20240103_140000"

    def test_list_runs_with_status_filter(self, temp_output_dir):
        """Test list_runs filters by status."""
        manager = RunManager(output_dir=temp_output_dir)
        runs = manager.list_runs(filter={"status": "success"})

        # All our test runs have status "success"
        assert len(runs) == 4
        assert all(r.status == "success" for r in runs)

    def test_list_runs_skips_non_run_directories(self, temp_output_dir):
        """Test list_runs skips directories without metadata files."""
        manager = RunManager(output_dir=temp_output_dir)
        runs = manager.list_runs()

        # Should not include "not_a_run" directory
        assert len(runs) == 4
        assert all(r.run_id.startswith(("train-", "eda-", "inference-")) for r in runs)

    def test_list_runs_discovers_all_run_types(self, temp_output_dir):
        """Test list_runs discovers train, eda, and inference runs."""
        manager = RunManager(output_dir=temp_output_dir)
        runs = manager.list_runs()

        run_ids = [r.run_id for r in runs]
        assert "train-20240101_120000" in run_ids
        assert "eda-20240102_130000" in run_ids
        assert "inference-20240103_140000" in run_ids

    def test_get_latest_run(self, temp_output_dir):
        """Test get_latest_run returns most recent run."""
        manager = RunManager(output_dir=temp_output_dir)
        latest = manager.get_latest_run()

        assert latest is not None
        assert latest.run_id == "train-20240104_150000"

    def test_get_latest_run_empty_output_dir(self, tmp_path):
        """Test get_latest_run returns None when no runs exist."""
        empty_output = tmp_path / "empty_output"
        empty_output.mkdir()

        manager = RunManager(output_dir=str(empty_output))
        latest = manager.get_latest_run()

        assert latest is None


class TestRunNameValidation:
    """Path-traversal guard for user-supplied run_name.

    generate_run_dir() does shutil.rmtree on run_dir. If run_name is
    attacker-controlled (web console), a traversal or absolute path would
    let it delete arbitrary directories. These tests pin the guard.
    """

    def _manager(self):
        # Minimal RunManager; generate_run_dir only needs the instance.
        return RunManager()

    def test_traversal_run_name_rejected(self, tmp_path):
        """A ../ run_name that escapes base must raise before any deletion."""
        base = tmp_path / "output"
        base.mkdir()
        victim = tmp_path / "victim_outside_base"
        victim.mkdir()

        manager = self._manager()
        with pytest.raises(ConfigurationError):
            manager.generate_run_dir(base_output_dir=str(base), run_name="../victim_outside_base")

        # Victim directory must survive (no rmtree ran).
        assert victim.exists()

    def test_absolute_run_name_rejected(self, tmp_path):
        """An absolute run_name must not escape the output dir."""
        base = tmp_path / "output"
        base.mkdir()

        manager = self._manager()
        with pytest.raises(ConfigurationError):
            manager.generate_run_dir(base_output_dir=str(base), run_name=str(tmp_path / "evil"))

    def test_valid_relative_run_name_allowed(self, tmp_path):
        """A plain relative run_name inside base still works."""
        base = tmp_path / "output"
        base.mkdir()

        manager = self._manager()
        run_dir = manager.generate_run_dir(base_output_dir=str(base), run_name="my-experiment")

        assert run_dir == base / "my-experiment"
        assert run_dir.exists()
        assert (run_dir / "models").exists()

    def test_traversal_with_subdir_rejected(self, tmp_path):
        """Deeper traversal must also be caught."""
        base = tmp_path / "output"
        base.mkdir()
        (tmp_path / "sibling").mkdir()

        manager = self._manager()
        with pytest.raises(ConfigurationError):
            manager.generate_run_dir(base_output_dir=str(base), run_name="legit/../../sibling")
