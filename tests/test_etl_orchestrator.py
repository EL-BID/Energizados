"""
Unit tests for ETLOrchestrator.

Tests for the orchestrator of multiple ETLs with dependencies.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLDependencyError
from energizados.etl.orchestrator import ETLOrchestrator


class MockETL:
    """Mock ETL for testing."""

    def __init__(self, input_paths=None, output_path=None, **kwargs):
        """Initialize the MockETL.

        Args:
            input_paths: List of input file paths.
            output_path: Output file path.
            **kwargs: Additional keyword arguments.
        """
        self.input_paths = input_paths or []
        self.output_path = output_path

    def extract(self):
        """Extract data from source.

        Returns:
            pd.DataFrame: A simple DataFrame with test data.
        """
        return pd.DataFrame({"data": [1, 2, 3]})

    def transform(self, df):
        """Transform the data (no-op).

        Args:
            df: Input DataFrame.

        Returns:
            pd.DataFrame: The unchanged DataFrame.
        """
        return df

    def load(self, df, path):
        """Load data to destination (no-op).

        Args:
            df: DataFrame to load.
            path: Destination path.
        """
        pass

    def run(self, output_path=None):
        """Run the full ETL process.

        Args:
            output_path: Optional output path.

        Returns:
            pd.DataFrame: The transformed DataFrame.
        """
        df = self.extract()
        df = self.transform(df)
        if output_path or self.output_path:
            self.load(df, output_path or self.output_path)
        return df


class TestETLOrchestrator:
    """Tests for ETLOrchestrator."""

    @pytest.fixture
    def sample_configs(self):
        """Returns sample configurations.

        Returns:
            dict: A dictionary of ETL configurations for testing.
        """
        return {
            "etl1": {
                "enabled": True,
                "description": "ETL 1",
                "input": "data/input1.csv",
                "output": "data/output1.parquet",
                "depends_on": [],
            },
            "etl2": {
                "enabled": True,
                "description": "ETL 2",
                "input": ["data/output1.parquet", "data/input2.csv"],
                "output": "data/output2.parquet",
                "depends_on": ["etl1"],
            },
        }

    def test_orchestrator_initialization(self, sample_configs):
        """Verify that the orchestrator initializes correctly."""
        orchestrator = ETLOrchestrator(sample_configs)
        assert orchestrator.etl_configs == sample_configs
        assert orchestrator.execution_order == []
        assert orchestrator.results == {}

    def test_validate_dependencies_passes_with_valid_config(self, sample_configs):
        """Verify that validate_dependencies passes with valid config."""
        orchestrator = ETLOrchestrator(sample_configs)
        # Should not raise exception
        orchestrator.validate_dependencies()

    def test_validate_dependencies_raises_on_unknown_dependency(self):
        """Verify that validate_dependencies raises error with unknown dependency."""
        configs = {
            "etl1": {
                "enabled": True,
                "input": "data/input1.csv",
                "output": "data/output1.parquet",
                "depends_on": ["unknown_etl"],
            }
        }

        orchestrator = ETLOrchestrator(configs)

        with pytest.raises(ETLDependencyError, match="unknown dependencies"):
            orchestrator.validate_dependencies()

    def test_detect_cycles_raises_on_cycle(self):
        """Verify that cycles in dependencies are detected."""
        from energizados.core.exceptions import ETLDependencyError

        configs = {
            "a": {
                "enabled": True,
                "input": "data/a.csv",
                "output": "data/a.parquet",
                "depends_on": ["b"],
            },
            "b": {
                "enabled": True,
                "input": "data/b.csv",
                "output": "data/b.parquet",
                "depends_on": ["a"],
            },
        }

        orchestrator = ETLOrchestrator(configs)

        with pytest.raises(ETLDependencyError):
            orchestrator.validate_dependencies()

    def test_build_execution_order_returns_correct_order(self, sample_configs):
        """Verify that build_execution_order returns the correct order."""
        orchestrator = ETLOrchestrator(sample_configs)
        order = orchestrator.build_execution_order()

        assert order == ["etl1", "etl2"]

    def test_execution_order_with_multiple_roots(self):
        """Verify execution order with multiple root ETLs."""
        configs = {
            "root1": {
                "enabled": True,
                "input": "data/r1.csv",
                "output": "data/r1.parquet",
                "depends_on": [],
            },
            "root2": {
                "enabled": True,
                "input": "data/r2.csv",
                "output": "data/r2.parquet",
                "depends_on": [],
            },
            "child": {
                "enabled": True,
                "input": ["@root1", "@root2"],
                "output": "data/child.parquet",
                "depends_on": ["root1", "root2"],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # root1 and root2 can be in any order, but child must be last
        assert order[-1] == "child"
        assert set(order[:2]) == {"root1", "root2"}

    def test_execution_order_with_diamond_dependency(self):
        """Verify execution order with diamond pattern."""
        configs = {
            "top": {
                "enabled": True,
                "input": "data/top.csv",
                "output": "data/top.parquet",
                "depends_on": [],
            },
            "left": {
                "enabled": True,
                "input": "@top",
                "output": "data/left.parquet",
                "depends_on": ["top"],
            },
            "right": {
                "enabled": True,
                "input": "@top",
                "output": "data/right.parquet",
                "depends_on": ["top"],
            },
            "bottom": {
                "enabled": True,
                "input": ["@left", "@right"],
                "output": "data/bottom.parquet",
                "depends_on": ["left", "right"],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        assert order[0] == "top"
        assert order[-1] == "bottom"
        assert set(order[1:3]) == {"left", "right"}

    def test_resolve_input_paths_with_string(self):
        """Verify input resolution with simple string."""
        configs = {
            "etl1": {
                "enabled": True,
                "input": "data/file.csv",
                "output": "data/out.parquet",
                "depends_on": [],
            },
        }

        # Create temporary file
        temp_dir = Path(tempfile.mkdtemp())
        try:
            test_file = temp_dir / "data"
            test_file.mkdir(parents=True)
            (test_file / "file.csv").write_text("data")

            # Change to temp directory so relative paths work
            import os

            original_dir = os.getcwd()
            os.chdir(temp_dir)

            try:
                orchestrator = ETLOrchestrator(configs)
                paths = orchestrator.resolve_input_paths("etl1")
                assert paths == ["data/file.csv"]
            finally:
                os.chdir(original_dir)
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_input_paths_with_list(self):
        """Verify input resolution with list."""
        # Create temp files for testing
        temp_dir = Path(tempfile.mkdtemp())
        try:
            file1 = temp_dir / "file1.csv"
            file2 = temp_dir / "file2.csv"
            file1.write_text("data1")
            file2.write_text("data2")

            # Change to temp directory
            import os

            original_dir = os.getcwd()
            os.chdir(temp_dir)

            try:
                configs = {
                    "etl1": {
                        "enabled": True,
                        "input": ["file1.csv", "file2.csv"],
                        "output": "data/out.parquet",
                        "depends_on": [],
                    },
                }

                orchestrator = ETLOrchestrator(configs)
                paths = orchestrator.resolve_input_paths("etl1")
                assert paths == ["file1.csv", "file2.csv"]
            finally:
                os.chdir(original_dir)
        finally:
            shutil.rmtree(temp_dir)

    def test_resolve_input_paths_with_reference(self):
        """Verify input resolution with @etl_name reference."""
        configs = {
            "etl1": {
                "enabled": True,
                "input": "data/input.csv",
                "output": "data/output1.parquet",
                "depends_on": [],
            },
            "etl2": {
                "enabled": True,
                "input": "@etl1",
                "output": "data/output2.parquet",
                "depends_on": ["etl1"],
            },
        }

        orchestrator = ETLOrchestrator(configs)

        # Simulate that etl1 already executed
        orchestrator.results["etl1"] = pd.DataFrame()

        paths = orchestrator.resolve_input_paths("etl2")
        assert paths == ["data/output1.parquet"]

    def test_get_execution_plan_returns_formatted_plan(self, sample_configs):
        """Verify that get_execution_plan returns a formatted plan."""
        orchestrator = ETLOrchestrator(sample_configs)
        orchestrator.build_execution_order()

        plan = orchestrator.get_execution_plan()

        assert "ETL Execution Plan" in plan
        assert "etl1" in plan
        assert "etl2" in plan


class TestManifestAwareResolution:
    """Tests for resolve_input_paths with manifest-aware resolution (task 4.4)."""

    def test_incremental_to_incremental_returns_new_partition_paths(self):
        """When both upstream and downstream are incremental, resolve returns
        only the new partition paths from the upstream state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create upstream output directory with partitions
            upstream_output = tmpdir_path / "upstream_out"
            upstream_output.mkdir()
            (upstream_output / "partition=2024-01").mkdir()
            (upstream_output / "partition=2024-02").mkdir()

            # Create state file with manifest fields (as SourceETL writes them)
            state_dir = tmpdir_path / "states"
            state_dir.mkdir()
            state = {
                "run_id": "2024-06-01T10:00:00+00:00",
                "new_partitions": ["2024-02"],
                "all_partitions": ["2024-01", "2024-02"],
                "last_processed_value": "2024-02-28",
                "processed_files": ["raw.parquet"],
            }
            state_file = state_dir / "state.json"
            with open(state_file, "w") as f:
                json.dump(state, f)

            configs = {
                "upstream": {
                    "enabled": True,
                    "input": "data/raw.parquet",
                    "output": str(upstream_output),
                    "depends_on": [],
                    "params": {
                        "mode": "incremental",
                        "state_file": str(state_file),
                    },
                },
                "downstream": {
                    "enabled": True,
                    "input": "@upstream",
                    "output": str(tmpdir_path / "downstream_out"),
                    "depends_on": ["upstream"],
                    "params": {"mode": "incremental"},
                },
            }

            orchestrator = ETLOrchestrator(configs)
            orchestrator.results["upstream"] = pd.DataFrame()

            paths = orchestrator.resolve_input_paths("downstream")
            assert len(paths) == 1
            assert paths[0] == f"{upstream_output}/partition=2024-02/data.parquet"

    def test_no_manifest_fallback_returns_full_path(self):
        """When no manifest exists (first run), resolve returns the full
        upstream output path as fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            upstream_output = tmpdir_path / "upstream_out"

            # No state dir or manifest
            configs = {
                "upstream": {
                    "enabled": True,
                    "input": "data/raw.parquet",
                    "output": str(upstream_output),
                    "depends_on": [],
                    "params": {
                        "mode": "incremental",
                        "state_file": str(tmpdir_path / "nonexistent" / "state.json"),
                    },
                },
                "downstream": {
                    "enabled": True,
                    "input": "@upstream",
                    "output": str(tmpdir_path / "downstream_out"),
                    "depends_on": ["upstream"],
                    "params": {"mode": "incremental"},
                },
            }

            orchestrator = ETLOrchestrator(configs)
            orchestrator.results["upstream"] = pd.DataFrame()

            paths = orchestrator.resolve_input_paths("downstream")
            assert paths == [str(upstream_output)]

    def test_non_incremental_downstream_gets_full_path(self):
        """When downstream is NOT incremental, it gets the full upstream path
        even if upstream is incremental with a state file containing manifest fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            upstream_output = tmpdir_path / "upstream_out"
            upstream_output.mkdir()

            # State file exists with manifest fields but downstream is NOT incremental
            state_dir = tmpdir_path / "states"
            state_dir.mkdir()
            state = {
                "run_id": "2024-06-01T10:00:00+00:00",
                "new_partitions": ["2024-02"],
                "all_partitions": ["2024-01", "2024-02"],
                "last_processed_value": "2024-02-28",
                "processed_files": ["raw.parquet"],
            }
            state_file = state_dir / "state.json"
            with open(state_file, "w") as f:
                json.dump(state, f)

            configs = {
                "upstream": {
                    "enabled": True,
                    "input": "data/raw.parquet",
                    "output": str(upstream_output),
                    "depends_on": [],
                    "params": {
                        "mode": "incremental",
                        "state_file": str(state_file),
                    },
                },
                "downstream": {
                    "enabled": True,
                    "input": "@upstream",
                    "output": str(tmpdir_path / "downstream_out"),
                    "depends_on": ["upstream"],
                    # No params or params without mode="incremental"
                },
            }

            orchestrator = ETLOrchestrator(configs)
            orchestrator.results["upstream"] = pd.DataFrame()

            paths = orchestrator.resolve_input_paths("downstream")
            assert paths == [str(upstream_output)]

    def test_mixed_ref_and_direct_paths(self):
        """When downstream has both @ref and direct paths, manifest-aware
        resolution applies only to the @ref portion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            upstream_output = tmpdir_path / "upstream_out"
            upstream_output.mkdir()

            # Direct file
            direct_file = tmpdir_path / "extra.csv"
            direct_file.write_text("a,b\n1,2\n")

            # State file for upstream (with manifest fields)
            state_dir = tmpdir_path / "states"
            state_dir.mkdir()
            state = {
                "run_id": "2024-06-01T10:00:00+00:00",
                "new_partitions": ["2024-03"],
                "all_partitions": ["2024-01", "2024-03"],
                "last_processed_value": "2024-03-31",
                "processed_files": ["raw.parquet"],
            }
            state_file = state_dir / "state.json"
            with open(state_file, "w") as f:
                json.dump(state, f)

            configs = {
                "upstream": {
                    "enabled": True,
                    "input": "data/raw.parquet",
                    "output": str(upstream_output),
                    "depends_on": [],
                    "params": {
                        "mode": "incremental",
                        "state_file": str(state_file),
                    },
                },
                "downstream": {
                    "enabled": True,
                    "input": ["@upstream", str(direct_file)],
                    "output": str(tmpdir_path / "downstream_out"),
                    "depends_on": ["upstream"],
                    "params": {"mode": "incremental"},
                },
            }

            orchestrator = ETLOrchestrator(configs)
            orchestrator.results["upstream"] = pd.DataFrame()

            paths = orchestrator.resolve_input_paths("downstream")
            assert len(paths) == 2
            # First path is the manifest-aware partition path
            assert paths[0] == f"{upstream_output}/partition=2024-03/data.parquet"
            # Second path is the direct file
            assert paths[1] == str(direct_file)

    def test_is_incremental_helper(self):
        """_is_incremental returns True only when params.mode == incremental."""
        configs = {
            "inc": {
                "enabled": True,
                "input": "data/a.csv",
                "output": "data/a.parquet",
                "depends_on": [],
                "params": {"mode": "incremental"},
            },
            "concat": {
                "enabled": True,
                "input": "data/b.csv",
                "output": "data/b.parquet",
                "depends_on": [],
                "params": {"mode": "concat"},
            },
            "no_params": {
                "enabled": True,
                "input": "data/c.csv",
                "output": "data/c.parquet",
                "depends_on": [],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        assert orchestrator._is_incremental("inc") is True
        assert orchestrator._is_incremental("concat") is False
        assert orchestrator._is_incremental("no_params") is False

    def test_read_manifest_returns_none_when_missing(self):
        """_read_manifest returns None when the state file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            orchestrator = ETLOrchestrator({})
            result = orchestrator._read_manifest(str(state_file))
            assert result is None

    def test_read_manifest_returns_dict_when_present(self):
        """_read_manifest returns parsed JSON from the state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            state = {
                "run_id": "2024-01-01",
                "new_partitions": ["2024-01"],
                "processed_files": ["raw.parquet"],
            }
            with open(state_file, "w") as f:
                json.dump(state, f)

            orchestrator = ETLOrchestrator({})
            result = orchestrator._read_manifest(str(state_file))
            assert result == state

    def test_read_manifest_returns_none_for_none_state_file(self):
        """_read_manifest returns None when state_file is None."""
        orchestrator = ETLOrchestrator({})
        result = orchestrator._read_manifest(None)
        assert result is None

    def test_incremental_chain_end_to_end(self):
        """End-to-end: upstream SourceETL writes partitions + state file,
        orchestrator resolves downstream input to only new partition paths."""
        from energizados.etl.pipeline import SourceETL

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create raw data for upstream
            df = pd.DataFrame(
                {
                    "fecha": pd.to_datetime(["2024-01-15", "2024-02-10"]),
                    "valor": [10, 20],
                }
            )
            raw_file = tmpdir_path / "raw.parquet"
            df.to_parquet(raw_file, index=False)

            upstream_output = tmpdir_path / "upstream_out"
            upstream_state = tmpdir_path / "states" / "upstream_state.json"
            upstream_state.parent.mkdir(parents=True)

            # Run upstream SourceETL (incremental)
            upstream_etl = SourceETL(
                name="upstream",
                mode="incremental",
                input_paths=[str(raw_file)],
                output_path=str(upstream_output),
                incremental_key="fecha",
                state_file=str(upstream_state),
            )
            upstream_etl.run(str(upstream_output))

            # Verify state file was written with manifest fields
            assert upstream_state.exists()
            with open(upstream_state) as f:
                state = json.load(f)
            assert "new_partitions" in state
            assert set(state["new_partitions"]) == {"2024-01", "2024-02"}

            # Now configure orchestrator with upstream + downstream
            configs = {
                "upstream": {
                    "enabled": True,
                    "input": str(raw_file),
                    "output": str(upstream_output),
                    "depends_on": [],
                    "params": {
                        "mode": "incremental",
                        "state_file": str(upstream_state),
                    },
                },
                "downstream": {
                    "enabled": True,
                    "input": "@upstream",
                    "output": str(tmpdir_path / "downstream_out"),
                    "depends_on": ["upstream"],
                    "params": {"mode": "incremental"},
                },
            }

            orchestrator = ETLOrchestrator(configs)
            orchestrator.results["upstream"] = pd.DataFrame()

            paths = orchestrator.resolve_input_paths("downstream")

            # Should resolve to the partition paths written by upstream
            assert len(paths) == 2
            assert f"{upstream_output}/partition=2024-01/data.parquet" in paths
            assert f"{upstream_output}/partition=2024-02/data.parquet" in paths


class TestETLOrchestratorProfiling:
    """Tests for the ``profile_memory`` flag and per-ETL memory metrics.

    Covers the contract used by the ``-vv`` CLI profiling feature: when
    profiling is on, ``on_etl_complete`` receives a metrics dict; when off,
    behavior is unchanged (``metrics=None``).
    """

    @pytest.fixture
    def mock_configs(self, tmp_path):
        """Single-ETL config that resolves to the module-level MockETL.

        Uses a real on-disk CSV because ``resolve_input_paths`` validates
        existence of literal (non-``@``) input paths.
        """
        input_file = tmp_path / "input1.csv"
        input_file.write_text("data\n1\n2\n3\n")
        return {
            "etl1": {
                "enabled": True,
                "input": str(input_file),
                "output": str(tmp_path / "output1.parquet"),
                "custom_class": "tests.test_etl_orchestrator.MockETL",
                "depends_on": [],
            },
        }

    def test_default_profiling_off_passes_none(self, mock_configs):
        """Without profile_memory, on_etl_complete receives metrics=None."""
        orch = ETLOrchestrator(mock_configs)
        captured = []
        orch.on_etl_complete = lambda name, rows, metrics=None: captured.append(metrics)
        orch.run()
        assert captured == [None]
        assert orch.memory_metrics == {}

    def test_profile_memory_passes_metrics_dict(self, mock_configs):
        """With profile_memory=True, on_etl_complete receives a metrics dict."""
        orch = ETLOrchestrator(mock_configs, profile_memory=True)
        captured = []
        orch.on_etl_complete = lambda name, rows, metrics=None: captured.append(metrics)
        orch.run()
        assert len(captured) == 1
        metrics = captured[0]
        assert set(metrics.keys()) == {"rss_start", "rss_end", "delta", "peak"}
        assert metrics["peak"] >= metrics["rss_start"] > 0

    def test_profile_memory_accumulates_in_state(self, mock_configs):
        """The orchestrator stores per-ETL metrics in ``memory_metrics``."""
        orch = ETLOrchestrator(mock_configs, profile_memory=True)
        orch.run()
        assert "etl1" in orch.memory_metrics
        assert set(orch.memory_metrics["etl1"].keys()) == {
            "rss_start",
            "rss_end",
            "delta",
            "peak",
        }
