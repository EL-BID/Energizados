"""
Integration tests for Energizados Framework.

Integration tests that verify the joint operation of
framework components.
"""

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.pipeline import ConfigPipelineBuilder, Pipeline
from energizados.etl.orchestrator import ETLOrchestrator


class TestPipelineIntegration:
    """Integration tests for Pipeline."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests.

        Yields:
            Path: Path to temporary directory that is cleaned up after test.
        """
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def valid_config(self, temp_dir):
        """Create a valid configuration for testing.

        Args:
            temp_dir: Temporary directory path.

        Yields:
            Path: Path to the configuration file.
        """
        config_file = temp_dir / "config.yaml"

        # Create data files
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        # Create test data
        test_df = pd.DataFrame(
            {
                "consumo_12_anterior": [100, 200, 150],
                "consumo_11_anterior": [110, 210, 160],
                "actividad": ["Comercio", "Industrial", "Residencial"],
                "tipo_tarifa": ["T1", "T2", "T1"],
                "target": [0, 1, 0],
            }
        )
        test_df.to_parquet(data_dir / "test.parquet", index=False)

        config_content = """
project:
  name: "test_project"
  version: "1.0.0"

etl:
  sample:
    enabled: false
    input: "data/test.parquet"
    output: "data/output.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
"""
        config_file.write_text(config_content)

        return config_file

    def test_config_pipeline_builder_with_valid_config(self, valid_config):
        """Verify that ConfigPipelineBuilder builds a valid pipeline."""
        builder = ConfigPipelineBuilder(str(valid_config))
        pipeline = builder.build()

        assert pipeline is not None
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_run_with_no_steps(self, valid_config):
        """Verify that a pipeline with no steps is handled correctly."""
        builder = ConfigPipelineBuilder(str(valid_config))
        pipeline = builder.build()

        # Pipeline should have 1 step (ETLStep is created even when enabled=false)
        # The ETLBuilder checks if 'etl' section exists, not if individual ETLs are enabled
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].__class__.__name__ == "ETLStep"

    def test_pipeline_with_multi_etl_config(self, temp_dir):
        """Verify integration with multiple ETLs."""
        config_file = temp_dir / "multi_etl_config.yaml"

        # Create directories for ETLs
        raw_dir = temp_dir / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Create test data
        df1 = pd.DataFrame({"id": [1, 2], "valor": [10, 20]})
        df1.to_csv(raw_dir / "source1.csv", index=False)

        config_content = """
project:
  name: "multi_etl_test"
  version: "1.0.0"

etl:
  source1:
    enabled: true
    description: "Processes source 1"
    input: "data/raw/source1.csv"
    output: "data/processed/source1.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: []

train:
  enabled: false

evaluation:
  enabled: false
"""
        config_file.write_text(config_content)

        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()

        # Verify that ETLStep was created
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].__class__.__name__ == "ETLStep"


class TestETLOrchestratorIntegration:
    """Integration tests for ETLOrchestrator."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests.

        Yields:
            Path: Path to temporary directory that is cleaned up after test.
        """
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_full_etl_workflow(self, temp_dir):
        """Verify complete ETL workflow with dependencies."""
        # Create directories and test files
        raw_dir = temp_dir / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Create test data
        df_consumos = pd.DataFrame(
            {
                "id_cliente": [1, 2, 3, 4],
                "consumo": [100, 200, 150, 180],
            }
        )
        df_clientes = pd.DataFrame(
            {
                "id_cliente": [1, 2, 3, 4],
                "zona": ["Norte", "Sur", "Este", "Oeste"],
            }
        )

        df_consumos.to_csv(raw_dir / "consumos.csv", index=False)
        df_clientes.to_csv(raw_dir / "clientes.csv", index=False)

        # Configuration with multiple ETLs - only the ones we can test
        configs = {
            "consumos": {
                "enabled": True,
                "description": "Processes consumptions",
                "input": "data/raw/consumos.csv",
                "output": "data/consumos.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "params": {"name": "consumos", "source_path": "data/raw/consumos.csv"},
                "depends_on": [],
            },
            "clientes": {
                "enabled": True,
                "description": "Processes customers",
                "input": "data/raw/clientes.csv",
                "output": "data/clientes.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "params": {"name": "clientes", "source_path": "data/raw/clientes.csv"},
                "depends_on": [],
            },
        }

        # Change to temporary directory
        import os

        original_dir = os.getcwd()
        os.chdir(temp_dir)

        try:
            orchestrator = ETLOrchestrator(configs)

            # Validate dependencies
            orchestrator.validate_dependencies()

            # Get execution order
            order = orchestrator.build_execution_order()
            assert set(order) == {"consumos", "clientes"}

            # Run ETLs
            results = orchestrator.run()

            # Verify results
            assert "consumos" in results
            assert "clientes" in results

        finally:
            os.chdir(original_dir)


class TestETLDependencyScenarios:
    """Tests for complex dependency scenarios."""

    def test_linear_chain_dependency(self):
        """Verify linear dependency chain (A → B → C)."""
        configs = {
            "a": {"enabled": True, "input": "a.csv", "output": "a.parquet", "depends_on": []},
            "b": {"enabled": True, "input": "@a", "output": "b.parquet", "depends_on": ["a"]},
            "c": {"enabled": True, "input": "@b", "output": "c.parquet", "depends_on": ["b"]},
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        assert order == ["a", "b", "c"]

    def test_diamond_dependency_pattern(self):
        """Verify diamond pattern (top → left/right → bottom)."""
        configs = {
            "top": {"enabled": True, "input": "top.csv", "output": "top.parquet", "depends_on": []},
            "left": {
                "enabled": True,
                "input": "@top",
                "output": "left.parquet",
                "depends_on": ["top"],
            },
            "right": {
                "enabled": True,
                "input": "@top",
                "output": "right.parquet",
                "depends_on": ["top"],
            },
            "bottom": {
                "enabled": True,
                "input": ["@left", "@right"],
                "output": "bottom.parquet",
                "depends_on": ["left", "right"],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # top must be first, bottom last
        assert order[0] == "top"
        assert order[-1] == "bottom"
        # left and right must be in middle
        assert set(order[1:3]) == {"left", "right"}

    def test_multiple_independent_roots(self):
        """Verify multiple independent roots that converge."""
        configs = {
            "root1": {"enabled": True, "input": "r1.csv", "output": "r1.parquet", "depends_on": []},
            "root2": {"enabled": True, "input": "r2.csv", "output": "r2.parquet", "depends_on": []},
            "root3": {"enabled": True, "input": "r3.csv", "output": "r3.parquet", "depends_on": []},
            "final": {
                "enabled": True,
                "input": ["@root1", "@root2", "@root3"],
                "output": "final.parquet",
                "depends_on": ["root1", "root2", "root3"],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # The three roots can be in any order at the beginning
        roots = set(order[:3])
        assert roots == {"root1", "root2", "root3"}
        # final must be last
        assert order[-1] == "final"

    def test_complex_dependency_graph(self):
        """Verify complex dependency graph."""
        configs = {
            "a": {"enabled": True, "input": "a.csv", "output": "a.parquet", "depends_on": []},
            "b": {"enabled": True, "input": "a.csv", "output": "b.parquet", "depends_on": []},
            "c": {
                "enabled": True,
                "input": ["@a", "@b"],
                "output": "c.parquet",
                "depends_on": ["a", "b"],
            },
            "d": {"enabled": True, "input": "@c", "output": "d.parquet", "depends_on": ["c"]},
            "e": {"enabled": True, "input": "@d", "output": "e.parquet", "depends_on": ["d"]},
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # Verify topological order
        assert "a" in order[:2]  # a must be in first (no dependencies)
        assert "e" == order[-1]  # e must be last (depends on all)

        # Verify that each ETL appears after its dependencies
        for i, etl_name in enumerate(order):
            deps = configs[etl_name]["depends_on"]
            for dep in deps:
                assert order.index(dep) < i


class TestCLIIntegration:
    """Integration tests for the CLI."""

    def test_validate_command_with_valid_config(self, tmp_path):
        """Verify that the validate command works with valid config."""
        from energizados.cli.validate import validate_config

        config_file = tmp_path / "config.yaml"
        config_content = """
project:
  name: "test"
  version: "1.0.0"

etls:
  consumos:
    enabled: false
    description: "Processes consumption data"
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: []

training:
  enabled: false
  models:
    - type: lightgbm

evaluation:
  enabled: false
"""
        config_file.write_text(config_content)

        # Should not raise exception
        validate_config([str(config_file)])

    def test_validate_command_with_invalid_yaml(self, tmp_path):
        """Verify that the validate command detects invalid YAML."""

        from energizados.cli.validate import validate_config
        from energizados.core.exceptions import ConfigurationError

        config_file = tmp_path / "invalid.yaml"
        # Use truly invalid YAML that causes parsing error
        config_file.write_text("invalid: [unclosed")

        with pytest.raises(ConfigurationError):
            validate_config([str(config_file)])


class TestTrainingConfigIntegration:
    """Integration tests for the new models: list config schema."""

    def test_pipeline_builds_with_single_model_list(self, tmp_path):
        """ConfigPipelineBuilder accepts train.models list with one entry."""
        from energizados.core.pipeline import ConfigPipelineBuilder, Pipeline

        config_file = tmp_path / "training_single.yaml"
        config_file.write_text("""
train:
  enabled: true
  target_column: target
  models:
    - type: lightgbm
      hyperparams: {}
      hyperparam_search:
        enabled: false
  feature_engineering:
    enabled: false
""")
        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()
        assert isinstance(pipeline, Pipeline)
        # One training step
        assert len(pipeline.steps) == 1

    def test_pipeline_builds_with_ensemble_config(self, tmp_path):
        """ConfigPipelineBuilder accepts training.models list with ensemble."""
        from energizados.core.pipeline import ConfigPipelineBuilder, Pipeline

        config_file = tmp_path / "training_ensemble.yaml"
        config_file.write_text("""
training:
  enabled: true
  target_column: target
  models:
    - name: lgbm
      type: lightgbm
      hyperparams: {}
      hyperparam_search: {enabled: false}
    - name: cat
      type: catboost
      hyperparams: {}
      hyperparam_search: {enabled: false}
  ensemble:
    method: soft_voting
    weights: [0.6, 0.4]
  feature_engineering:
    enabled: false
""")
        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()
        assert isinstance(pipeline, Pipeline)

    def test_training_step_receives_models_configs(self, tmp_path):
        """TrainingStep inside the pipeline has models_configs populated."""
        from energizados.core.pipeline import ConfigPipelineBuilder
        from energizados.core.steps.training import TrainingStep

        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("""
train:
  enabled: true
  models:
    - type: lightgbm
      hyperparams: {}
  feature_engineering:
    enabled: false
""")
        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()

        training_step = pipeline.steps[0]
        assert isinstance(training_step, TrainingStep)
        assert len(training_step.models_configs) == 1
        assert training_step.models_configs[0]["type"] == "lightgbm"

    def test_training_step_ensemble_config_propagated(self, tmp_path):
        """ensemble_config is correctly propagated to TrainingStep."""
        from energizados.core.pipeline import ConfigPipelineBuilder
        from energizados.core.steps.training import TrainingStep

        config_file = tmp_path / "cfg2.yaml"
        config_file.write_text("""
train:
  enabled: true
  models:
    - type: lightgbm
    - type: catboost
  ensemble:
    method: stacking
    use_val_as_oof: true
  feature_engineering:
    enabled: false
""")
        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()

        training_step = pipeline.steps[0]
        assert isinstance(training_step, TrainingStep)
        assert training_step.ensemble_config is not None
        assert training_step.ensemble_config["method"] == "stacking"


@pytest.mark.slow
class TestEndToEndScenarios:
    """End-to-end tests simulating real use cases."""

    @pytest.fixture
    def project_dir(self):
        """Create a test project directory.

        Yields:
            Path: Path to temporary project directory.
        """
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_create_and_run_simple_project(self, project_dir):
        """Verify creation and execution of a simple project."""
        from energizados.cli.init import create_project

        project_name = "simple_test"
        project_path = project_dir / project_name

        # Create project
        create_project(project_name, project_path)

        # Verify created structure (new 2026 structure)
        assert (project_path / "src" / "data" / "custom_etl.py").exists()
        assert (project_path / "src" / "features" / "custom_selector.py").exists()
        assert (project_path / "src" / "models" / "custom_model.py").exists()
        # Verify that config exists with 3 separate files
        assert (project_path / "config" / "etl.yaml").exists()
        assert (project_path / "config" / "train.yaml").exists()
        assert (project_path / "config" / "infer.yaml").exists()
        assert (project_path / "README.md").exists()
        # Test templates are no longer created by default
        assert (project_path / "tests" / "__init__.py").exists()
        assert (project_path / "docs" / "project_docs.md").exists()
        assert (project_path / "requirements.txt").exists()
