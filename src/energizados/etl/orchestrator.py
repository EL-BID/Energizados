"""
ETL Orchestrator for Energizados Framework.

Este módulo proporciona el ETLOrchestrator que permite ejecutar múltiples ETLs
respetando dependencias entre ellas, implementando un orden topológico.
"""

import glob
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List

import pandas as pd

from energizados.core.exceptions import ETLDependencyError, ETLError


class ETLOrchestrator:
    """
    Orquesta la ejecución de múltiples ETLs respetando dependencias.

    Implementa un orden topológico para ejecutar las ETLs en el orden correcto
    basado en sus dependencias, creando un DAG (Directed Acyclic Graph).

    Args:
        etl_configs: Diccionario con configuración de cada ETL
            {
                "etl_name": {
                    "enabled": bool,
                    "description": str,
                    "input": str or List[str],  # Archivos, glob, o referencia
                    "output": str,
                    "depends_on": ["etl1", "etl2"],
                    "custom_class": str (opcional),
                    "params": dict (opcional)
                }
            }

    Attributes:
        etl_configs: Configuración de todas las ETLs
        etl_instances: Instancias de ETL creadas
        execution_order: Orden de ejecución determinado
        results: Resultados de cada ETL ejecutada

    Example:
        >>> configs = {
        ...     "extract": {"input": "data.csv", "output": "ext.parquet", "depends_on": []},
        ...     "transform": {"input": "@extract", "output": "final.parquet", "depends_on": ["extract"]}
        ... }
        >>> orchestrator = ETLOrchestrator(configs)
        >>> results = orchestrator.run()
    """

    def __init__(self, etl_configs: Dict[str, Dict]):
        self.etl_configs = etl_configs
        self.etl_instances: Dict[str, object] = {}
        self.execution_order: List[str] = []
        self.results: Dict[str, pd.DataFrame] = {}

    def validate_dependencies(self) -> None:
        """
        Valida que el DAG de dependencias sea válido.

        Verifica que:
        - Todas las dependencias referenciadas existan
        - No haya ciclos en el grafo de dependencias

        Raises:
            ETLDependencyError: Si hay ciclos o referencias inválidas
        """
        all_etls = set(self.etl_configs.keys())

        for etl_name, config in self.etl_configs.items():
            deps = set(config.get("depends_on", []))
            unknown = deps - all_etls
            if unknown:
                raise ETLDependencyError(f"ETL '{etl_name}' tiene dependencias desconocidas: {unknown}")

        self._detect_cycles()

    def _detect_cycles(self) -> None:
        """
        Detecta ciclos en el grafo de dependencias usando DFS.

        Raises:
            ETLDependencyError: Si se detecta un ciclo
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {etl: WHITE for etl in self.etl_configs}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in self.etl_configs.get(node, {}).get("depends_on", []):
                if color[neighbor] == GRAY:
                    return True  # Ciclo detectado
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for etl in self.etl_configs:
            if color[etl] == WHITE:
                if dfs(etl):
                    raise ETLDependencyError(f"Detectado ciclo en dependencias de ETLs involucrando a '{etl}'")

    def build_execution_order(self) -> List[str]:
        """
        Construye el orden de ejecución usando orden topológico (BFS).

        Returns:
            Lista de nombres de ETLs en orden de ejecución

        Raises:
            ETLDependencyError: Si no se puede determinar el orden (ciclo)
        """
        in_degree = defaultdict(int)
        adj_list = defaultdict(list)

        for etl_name, config in self.etl_configs.items():
            deps = config.get("depends_on", [])
            in_degree[etl_name] = len(deps)
            for dep in deps:
                adj_list[dep].append(etl_name)

        queue = deque([etl for etl in self.etl_configs if in_degree[etl] == 0])
        order = []

        while queue:
            etl = queue.popleft()
            order.append(etl)

            for neighbor in adj_list[etl]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.etl_configs):
            raise ETLDependencyError("No se pudo determinar orden topológico (posible ciclo)")

        self.execution_order = order
        return order

    def resolve_input_paths(self, etl_name: str) -> List[str]:
        """
        Resuelve las rutas de input de una ETL.

        Soporta:
        - Archivos individuales: "data/file.csv"
        - Lista de archivos: ["file1.csv", "file2.csv"]
        - Expresiones glob: "*.csv", "data/**/*.parquet"
        - Referencias a otras ETLs: "@etl_name"

        Args:
            etl_name: Nombre de la ETL

        Returns:
            Lista de rutas de archivos resueltas

        Raises:
            ETLDependencyError: Si una referencia apunta a una ETL no ejecutada
            ETLError: Si un archivo no existe o un glob no coincide
        """
        config = self.etl_configs[etl_name]
        raw_input = config.get("input", [])

        if isinstance(raw_input, str):
            raw_input = [raw_input]

        resolved_paths = []
        for path_spec in raw_input:
            # Referencia a otra ETL (@etl_name)
            if path_spec.startswith("@"):
                ref_etl = path_spec[1:]
                if ref_etl in self.etl_configs:
                    # Obtener el output path del config de la ETL referenciada
                    # No importa si ya se ejecutó o no, el path está en el config
                    ref_config = self.etl_configs[ref_etl]
                    resolved_paths.append(ref_config["output"])
                else:
                    raise ETLDependencyError(f"ETL '{etl_name}' referencia ETL desconocida '{ref_etl}'")

            # Expresión glob
            elif "*" in path_spec or "?" in path_spec or "[" in path_spec:
                matched = glob.glob(path_spec, recursive=True)
                if not matched:
                    raise ETLError(f"ETL '{etl_name}': glob '{path_spec}' no coincidió con ningún archivo")
                resolved_paths.extend(sorted(matched))

            # Archivo específico
            else:
                if not Path(path_spec).exists():
                    raise ETLError(f"ETL '{etl_name}': archivo de input '{path_spec}' no existe")
                resolved_paths.append(path_spec)

        return resolved_paths

    def instantiate_etls(self) -> None:
        """
        Instancia las clases de ETL según la configuración.

        Crea instancias de DefaultETL o clases personalizadas según
        la configuración de cada ETL.
        """
        from energizados.etl.default import DefaultETL

        for etl_name, config in self.etl_configs.items():
            if not config.get("enabled", True):
                continue

            input_paths = self.resolve_input_paths(etl_name)
            output_path = config["output"]

            if "custom_class" in config:
                etl_class = self._import_class(config["custom_class"])
                params = config.get("params", {})
                params["input_paths"] = input_paths
                params["output_path"] = output_path
                self.etl_instances[etl_name] = etl_class(**params)
            else:
                source_path = input_paths[0] if len(input_paths) == 1 else input_paths
                self.etl_instances[etl_name] = DefaultETL(
                    sources=[source_path] if isinstance(source_path, str) else source_path,
                    output_path=output_path,
                    **config.get("params", {}),
                )

    def run(self, parallel: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Ejecuta todas las ETLs respetando las dependencias.

        Args:
            parallel: Si True, ejecuta ETLs independientes en paralelo (no implementado aún)

        Returns:
            Diccionario con los resultados de cada ETL

        Raises:
            ETLDependencyError: Si hay errores en las dependencias
            ETLError: Si falla la ejecución de alguna ETL
        """
        self.validate_dependencies()
        order = self.build_execution_order()
        self.instantiate_etls()

        print(f"\n{'=' * 60}")
        print(f"Ejecutando {len(self.execution_order)} ETLs en orden:")
        print(" → ".join(order))
        print(f"{'=' * 60}\n")

        for i, etl_name in enumerate(self.execution_order):
            etl_config = self.etl_configs[etl_name]

            if not etl_config.get("enabled", True):
                print(f"[SKIP] {etl_name} (disabled)")
                continue

            print(f"\n{'─' * 60}")
            print(f"ETL {i + 1}/{len(self.execution_order)}: {etl_name}")
            print(f"{'─' * 60}")

            description = etl_config.get("description", "N/A")
            if description != "N/A":
                print(f"Descripción: {description}")

            # Mostrar inputs resueltos
            input_paths = self.resolve_input_paths(etl_name)
            print(f"Input(s): {len(input_paths)} archivo(s)")
            for path in input_paths[:3]:
                print(f"  - {path}")
            if len(input_paths) > 3:
                print(f"  ... y {len(input_paths) - 3} más")

            print(f"Output: {etl_config['output']}")

            # Verificar dependencias
            deps = etl_config.get("depends_on", [])
            for dep in deps:
                if dep not in self.results:
                    raise ETLDependencyError(f"Dependencia '{dep}' no se ejecutó correctamente")

            # Ejecutar ETL
            etl = self.etl_instances.get(etl_name)
            if etl:
                try:
                    result = etl.run(output_path=etl_config["output"])
                    self.results[etl_name] = result
                    print(f"✓ {etl_name} completado ({len(result)} filas)")
                except Exception as e:
                    print(f"✗ {etl_name} falló: {e}")
                    raise ETLError(f"Error ejecutando ETL '{etl_name}': {e}")

        print(f"\n{'=' * 60}")
        print("TODAS LAS ETLs COMPLETADAS")
        print(f"{'=' * 60}")

        return self.results

    def _import_class(self, class_path: str):
        """
        Importa una clase desde su path completo.

        Args:
            class_path: Path completo (ej: "module.submodule.ClassName")

        Returns:
            Clase importada

        Raises:
            ConfigurationError: Si no se puede importar la clase
        """
        from energizados.core.exceptions import ConfigurationError

        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as e:
            raise ConfigurationError(f"No se puede importar clase {class_path}: {e}", None)

    def get_execution_plan(self) -> str:
        """
        Retorna una representación visual del plan de ejecución.

        Returns:
            String con el plan formateado
        """
        lines = ["\nPlan de Ejecución de ETLs:", "=" * 60]

        if not self.execution_order:
            try:
                self.build_execution_order()
            except ETLDependencyError:
                return "Error: No se puede construir el plan de ejecución (ciclo detectado)"

        for i, etl_name in enumerate(self.execution_order):
            config = self.etl_configs[etl_name]
            deps = config.get("depends_on", [])
            deps_str = f" (deps: {', '.join(deps)})" if deps else ""

            lines.append(f"{i + 1}. {etl_name}{deps_str}")

            raw_input = config.get("input", "N/A")
            if isinstance(raw_input, list):
                if len(raw_input) > 2:
                    input_str = f"[{raw_input[0]}, ... ({len(raw_input)} total)]"
                else:
                    input_str = str(raw_input)
            else:
                input_str = raw_input

            lines.append(f"   Input:  {input_str}")
            lines.append(f"   Output: {config['output']}")

        return "\n".join(lines)
