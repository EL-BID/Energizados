"""
Unit tests for RunManager run metadata persistence.

Tests cover:
- finalize_run() writes run_metadata.json
- Metadata includes version, git, duration, model info
- Backward compat when context is None
- Git/version fallback to "unknown"
"""

import json
from unittest.mock import patch

from energizados.core.builders.run_manager import RunManager


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
