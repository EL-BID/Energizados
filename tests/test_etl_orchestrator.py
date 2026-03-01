"""
Unit tests for ETLOrchestrator.

Pruebas para el orquestador de múltiples ETLs con dependencias.
"""

import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLDependencyError
from energizados.etl.orchestrator import ETLOrchestrator


class MockETL:
    """ETL mock para pruebas."""

    def __init__(self, input_paths=None, output_path=None, **kwargs):
        self.input_paths = input_paths or []
        self.output_path = output_path

    def extract(self):
        return pd.DataFrame({"data": [1, 2, 3]})

    def transform(self, df):
        return df

    def load(self, df, path):
        pass

    def run(self, output_path=None):
        df = self.extract()
        df = self.transform(df)
        if output_path or self.output_path:
            self.load(df, output_path or self.output_path)
        return df


class TestETLOrchestrator:
    """Tests para ETLOrchestrator."""

    @pytest.fixture
    def sample_configs(self):
        """Retorna configuraciones de ejemplo."""
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
        """Verifica que el orchestrator se inicialice correctamente."""
        orchestrator = ETLOrchestrator(sample_configs)
        assert orchestrator.etl_configs == sample_configs
        assert orchestrator.execution_order == []
        assert orchestrator.results == {}

    def test_validate_dependencies_passes_with_valid_config(self, sample_configs):
        """Verifica que validate_dependencies pase con configuración válida."""
        orchestrator = ETLOrchestrator(sample_configs)
        # No debería lanzar excepción
        orchestrator.validate_dependencies()

    def test_validate_dependencies_raises_on_unknown_dependency(self):
        """Verifica que validate_dependencies lance error con dependencia desconocida."""
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
        """Verifica que se detecten ciclos en las dependencias."""
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
        """Verifica que build_execution_order retorne el orden correcto."""
        orchestrator = ETLOrchestrator(sample_configs)
        order = orchestrator.build_execution_order()

        assert order == ["etl1", "etl2"]

    def test_execution_order_with_multiple_roots(self):
        """Verifica el orden de ejecución con múltiples ETLs raíz."""
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

        # root1 y root2 pueden estar en cualquier orden, pero child debe estar último
        assert order[-1] == "child"
        assert set(order[:2]) == {"root1", "root2"}

    def test_execution_order_with_diamond_dependency(self):
        """Verifica el orden de ejecución con patrón diamante."""
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
        """Verifica resolución de input con string simple."""
        configs = {
            "etl1": {
                "enabled": True,
                "input": "data/file.csv",
                "output": "data/out.parquet",
                "depends_on": [],
            },
        }

        # Crear archivo temporal
        temp_dir = Path(tempfile.mkdtemp())
        try:
            test_file = temp_dir / "data"
            test_file.mkdir(parents=True)
            (test_file / "file.csv").write_text("data")

            # Cambiar al directorio temporal para que las rutas relativas funcionen
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
        """Verifica resolución de input con lista."""
        # Crear archivos temporales para el test
        temp_dir = Path(tempfile.mkdtemp())
        try:
            file1 = temp_dir / "file1.csv"
            file2 = temp_dir / "file2.csv"
            file1.write_text("data1")
            file2.write_text("data2")

            # Cambiar al directorio temporal
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
        """Verifica resolución de input con referencia @etl_name."""
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

        # Simular que etl1 ya se ejecutó
        orchestrator.results["etl1"] = pd.DataFrame()

        paths = orchestrator.resolve_input_paths("etl2")
        assert paths == ["data/output1.parquet"]

    def test_get_execution_plan_returns_formatted_plan(self, sample_configs):
        """Verifica que get_execution_plan retorne un plan formateado."""
        orchestrator = ETLOrchestrator(sample_configs)
        orchestrator.build_execution_order()

        plan = orchestrator.get_execution_plan()

        assert "ETL Execution Plan" in plan
        assert "etl1" in plan
        assert "etl2" in plan
