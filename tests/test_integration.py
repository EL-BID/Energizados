"""
Integration tests for Energizados Framework.

Pruebas de integración que verifican el funcionamiento conjunto
de los componentes del framework.
"""

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.pipeline import ConfigPipelineBuilder, Pipeline
from energizados.etl.orchestrator import ETLOrchestrator


class TestPipelineIntegration:
    """Tests de integración para Pipeline."""

    @pytest.fixture
    def temp_dir(self):
        """Crea directorio temporal para tests."""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def valid_config(self, temp_dir):
        """Crea configuración válida para pruebas."""
        config_file = temp_dir / "config.yaml"

        # Crear archivos de datos
        data_dir = temp_dir / "data"
        data_dir.mkdir()

        # Crear datos de prueba
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
  enabled: false

preprocessing:
  enabled: false

feature_selection:
  enabled: false

training:
  enabled: false

evaluation:
  enabled: false
"""
        config_file.write_text(config_content)

        return config_file

    def test_config_pipeline_builder_with_valid_config(self, valid_config):
        """Verifica que ConfigPipelineBuilder construya un pipeline válido."""
        builder = ConfigPipelineBuilder(str(valid_config))
        pipeline = builder.build()

        assert pipeline is not None
        assert isinstance(pipeline, Pipeline)

    def test_pipeline_run_with_no_steps(self, valid_config):
        """Verifica que un pipeline sin pasos se maneje correctamente."""
        builder = ConfigPipelineBuilder(str(valid_config))
        pipeline = builder.build()

        # Pipeline sin pasos debería poder crearse
        assert len(pipeline.steps) == 0

    def test_pipeline_with_multi_etl_config(self, temp_dir):
        """Verifica integración con múltiples ETLs."""
        config_file = temp_dir / "multi_etl_config.yaml"

        # Crear directorios para ETLs
        raw_dir = temp_dir / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Crear datos de prueba
        df1 = pd.DataFrame({"id": [1, 2], "valor": [10, 20]})
        df1.to_csv(raw_dir / "source1.csv", index=False)

        config_content = """
project:
  name: "multi_etl_test"
  version: "1.0.0"

etls:
  source1:
    enabled: true
    description: "Procesa fuente 1"
    input: "data/raw/source1.csv"
    output: "data/processed/source1.parquet"
    depends_on: []

preprocessing:
  enabled: false

training:
  enabled: false

evaluation:
  enabled: false
"""
        config_file.write_text(config_content)

        builder = ConfigPipelineBuilder(str(config_file))
        pipeline = builder.build()

        # Verificar que se creó el paso MultiETLStep
        assert len(pipeline.steps) == 1


class TestETLOrchestratorIntegration:
    """Tests de integración para ETLOrchestrator."""

    @pytest.fixture
    def temp_dir(self):
        """Crea directorio temporal para tests."""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_full_etl_workflow(self, temp_dir):
        """Verifica flujo completo de ETLs con dependencias."""
        # Crear directorios y archivos de prueba
        raw_dir = temp_dir / "data" / "raw"
        raw_dir.mkdir(parents=True)

        # Crear datos de prueba
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

        # Configuración con múltiples ETLs - solo las que podemos probar
        configs = {
            "consumos": {
                "enabled": True,
                "description": "Procesa consumos",
                "input": "data/raw/consumos.csv",
                "output": "data/consumos.parquet",
                "depends_on": [],
                "type": "default",
            },
            "clientes": {
                "enabled": True,
                "description": "Procesa clientes",
                "input": "data/raw/clientes.csv",
                "output": "data/clientes.parquet",
                "depends_on": [],
                "type": "default",
            },
        }

        # Cambiar al directorio temporal
        import os

        original_dir = os.getcwd()
        os.chdir(temp_dir)

        try:
            orchestrator = ETLOrchestrator(configs)

            # Validar dependencias
            orchestrator.validate_dependencies()

            # Obtener orden de ejecución
            order = orchestrator.build_execution_order()
            assert set(order) == {"consumos", "clientes"}

            # Ejecutar ETLs
            results = orchestrator.run()

            # Verificar resultados
            assert "consumos" in results
            assert "clientes" in results

        finally:
            os.chdir(original_dir)


class TestETLDependencyScenarios:
    """Tests de escenarios de dependencias complejas."""

    def test_linear_chain_dependency(self):
        """Verifica cadena lineal de dependencias (A → B → C)."""
        configs = {
            "a": {"enabled": True, "input": "a.csv", "output": "a.parquet", "depends_on": []},
            "b": {"enabled": True, "input": "@a", "output": "b.parquet", "depends_on": ["a"]},
            "c": {"enabled": True, "input": "@b", "output": "c.parquet", "depends_on": ["b"]},
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        assert order == ["a", "b", "c"]

    def test_diamond_dependency_pattern(self):
        """Verifica patrón diamante (top → left/right → bottom)."""
        configs = {
            "top": {"enabled": True, "input": "top.csv", "output": "top.parquet", "depends_on": []},
            "left": {"enabled": True, "input": "@top", "output": "left.parquet", "depends_on": ["top"]},
            "right": {"enabled": True, "input": "@top", "output": "right.parquet", "depends_on": ["top"]},
            "bottom": {"enabled": True, "input": ["@left", "@right"], "output": "bottom.parquet", "depends_on": ["left", "right"]},
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # top debe estar primero, bottom último
        assert order[0] == "top"
        assert order[-1] == "bottom"
        # left y right deben estar en medio
        assert set(order[1:3]) == {"left", "right"}

    def test_multiple_independent_roots(self):
        """Verifica múltiples raíces independientes que convergen."""
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

        # Las tres raíces pueden estar en cualquier orden al inicio
        roots = set(order[:3])
        assert roots == {"root1", "root2", "root3"}
        # final debe estar último
        assert order[-1] == "final"

    def test_complex_dependency_graph(self):
        """Verifica grafo complejo de dependencias."""
        configs = {
            "a": {"enabled": True, "input": "a.csv", "output": "a.parquet", "depends_on": []},
            "b": {"enabled": True, "input": "a.csv", "output": "b.parquet", "depends_on": []},
            "c": {"enabled": True, "input": ["@a", "@b"], "output": "c.parquet", "depends_on": ["a", "b"]},
            "d": {"enabled": True, "input": "@c", "output": "d.parquet", "depends_on": ["c"]},
            "e": {"enabled": True, "input": "@d", "output": "e.parquet", "depends_on": ["d"]},
        }

        orchestrator = ETLOrchestrator(configs)
        order = orchestrator.build_execution_order()

        # Verificar orden topológico
        assert "a" in order[:2]  # a debe estar en los primeros (sin dependencias)
        assert "e" == order[-1]  # e debe estar último (depende de todos)

        # Verificar que cada ETL aparezca después de sus dependencias
        for i, etl_name in enumerate(order):
            deps = configs[etl_name]["depends_on"]
            for dep in deps:
                assert order.index(dep) < i


class TestCLIIntegration:
    """Tests de integración para la CLI."""

    def test_validate_command_with_valid_config(self, tmp_path):
        """Verifica que el comando validate funcione con configuración válida."""
        from energizados.cli.validate import validate_config

        config_file = tmp_path / "config.yaml"
        config_content = """
project:
  name: "test"
  version: "1.0.0"

etl:
  enabled: false

preprocessing:
  enabled: false

training:
  enabled: false
  model_type: "lightgbm"

evaluation:
  enabled: false
"""
        config_file.write_text(config_content)

        # No debería lanzar excepción
        validate_config(str(config_file))

    def test_validate_command_with_invalid_yaml(self, tmp_path):
        """Verifica que el comando validate detecte YAML inválido."""

        from energizados.cli.validate import validate_config
        from energizados.core.exceptions import ConfigurationError

        config_file = tmp_path / "invalid.yaml"
        # Usar YAML realmente inválido que cause error de parsing
        config_file.write_text("invalid: [unclosed")

        with pytest.raises(ConfigurationError):
            validate_config(str(config_file))


@pytest.mark.slow
class TestEndToEndScenarios:
    """Tests end-to-end que simulan casos de uso reales."""

    @pytest.fixture
    def project_dir(self):
        """Crea un proyecto de prueba."""
        temp = Path(tempfile.mkdtemp())
        yield temp
        shutil.rmtree(temp)

    def test_create_and_run_simple_project(self, project_dir):
        """Verifica creación y ejecución de un proyecto simple."""
        from energizados.cli.init import create_project

        project_name = "simple_test"
        project_path = project_dir / project_name

        # Crear proyecto
        create_project(project_name, project_path)

        # Verificar estructura creada
        assert (project_path / "etl" / "custom_etl.py").exists()
        assert (project_path / "feature_selection" / "custom_selector.py").exists()
        assert (project_path / "models" / "custom_model.py").exists()
        assert (project_path / "configs" / "pipeline.yaml").exists()
        assert (project_path / "README.md").exists()
