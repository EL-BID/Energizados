"""
ETL Orchestrator for Energizados Framework.

This module provides the ETLOrchestrator which allows running multiple ETLs
respecting dependencies between them, implementing topological order.
"""

import glob
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List

import pandas as pd

from energizados.core.exceptions import ETLDependencyError, ETLError
from energizados.core.utils import import_class

logger = logging.getLogger(__name__)


class ETLOrchestrator:
    """Orchestrates the execution of multiple ETLs respecting dependencies.

    Implements topological order to execute ETLs in the correct order
    based on their dependencies, creating a DAG (Directed Acyclic Graph).

    Args:
        etl_configs: Dictionary with configuration for each ETL.
            {
                "etl_name": {
                    "enabled": bool,
                    "description": str,
                    "input": str or List[str],  # Files, glob, or reference
                    "output": str,
                    "depends_on": ["etl1", "etl2"],
                    "custom_class": str (optional),
                    "params": dict (optional)
                }
            }

    Attributes:
        etl_configs: Configuration of all ETLs.
        etl_instances: Created ETL instances.
        execution_order: Determined execution order.
        results: Results of each executed ETL.

    Example:
        >>> configs = {
        ...     "extract": {"input": "data.csv", "output": "ext.parquet", "depends_on": []},
        ...     "transform": {"input": "@extract", "output": "final.parquet", "depends_on": ["extract"]}
        ... }
        >>> orchestrator = ETLOrchestrator(configs)
        >>> results = orchestrator.run()
    """

    def __init__(self, etl_configs: Dict[str, Dict]):
        """Initialize the orchestrator.

        Args:
            etl_configs: Dictionary with configuration for each ETL.
        """
        self.etl_configs = etl_configs
        self.etl_instances: Dict[str, object] = {}
        self.execution_order: List[str] = []
        self.results: Dict[str, pd.DataFrame] = {}

    def validate_dependencies(self) -> None:
        """
        Validates that the dependency DAG is valid.

        Verifies that:
        - All referenced dependencies exist
        - There are no cycles in the dependency graph

        Raises:
            ETLDependencyError: If there are cycles or invalid references
        """
        all_etls = set(self.etl_configs.keys())

        for etl_name, config in self.etl_configs.items():
            deps = set(config.get("depends_on", []))
            unknown = deps - all_etls
            if unknown:
                raise ETLDependencyError(f"ETL '{etl_name}' has unknown dependencies: {unknown}")

        self._detect_cycles()

    def _detect_cycles(self) -> None:
        """
        Detects cycles in the dependency graph using DFS.

        Raises:
            ETLDependencyError: If a cycle is detected
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {etl: WHITE for etl in self.etl_configs}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in self.etl_configs.get(node, {}).get("depends_on", []):
                if color[neighbor] == GRAY:
                    return True  # Cycle detected
                if color[neighbor] == WHITE and dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        for etl in self.etl_configs:
            if color[etl] == WHITE:
                if dfs(etl):
                    raise ETLDependencyError(f"Cycle detected in ETL dependencies involving '{etl}'")

    def build_execution_order(self) -> List[str]:
        """
        Builds the execution order using topological order (BFS).

        Returns:
            List of ETL names in execution order

        Raises:
            ETLDependencyError: If the order cannot be determined (cycle)
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
            raise ETLDependencyError("Could not determine topological order (possible cycle)")

        self.execution_order = order
        return order

    def resolve_input_paths(self, etl_name: str) -> List[str]:
        """
        Resolves the input paths for an ETL.

        Supports:
        - Individual files: "data/file.csv"
        - File list: ["file1.csv", "file2.csv"]
        - Glob expressions: "*.csv", "data/**/*.parquet"
        - References to other ETLs: "@etl_name"

        Args:
            etl_name: Name of the ETL

        Returns:
            List of resolved file paths

        Raises:
            ETLDependencyError: If a reference points to an unexecuted ETL
            ETLError: If a file doesn't exist or glob doesn't match
        """
        config = self.etl_configs[etl_name]
        raw_input = config.get("input", [])

        if isinstance(raw_input, str):
            raw_input = [raw_input]

        resolved_paths = []
        for path_spec in raw_input:
            # Reference to another ETL (@etl_name)
            if path_spec.startswith("@"):
                ref_etl = path_spec[1:]
                if ref_etl in self.etl_configs:
                    # Get the output path from the referenced ETL config
                    # It doesn't matter if it was already executed, the path is in the config
                    ref_config = self.etl_configs[ref_etl]
                    resolved_paths.append(ref_config["output"])
                else:
                    raise ETLDependencyError(f"ETL '{etl_name}' references unknown ETL '{ref_etl}'")

            # Glob expression
            elif "*" in path_spec or "?" in path_spec or "[" in path_spec:
                matched = glob.glob(path_spec, recursive=True)
                if not matched:
                    raise ETLError(f"ETL '{etl_name}': glob '{path_spec}' did not match any files")
                resolved_paths.extend(sorted(matched))

            # Specific file
            else:
                if not Path(path_spec).exists():
                    raise ETLError(f"ETL '{etl_name}': input file '{path_spec}' does not exist")
                resolved_paths.append(path_spec)

        return resolved_paths

    def instantiate_etls(self) -> None:
        """
        Instantiates ETL classes according to configuration.

        Requires that each ETL specify a custom_class.
        """
        for etl_name, config in self.etl_configs.items():
            if not config.get("enabled", True):
                continue

            if "custom_class" not in config:
                raise ETLError(f"ETL '{etl_name}': must specify 'custom_class'. " f"Example: SourceETL, MultiSourceETL, or a custom class.")

            etl_class = import_class(config["custom_class"])
            params = config.get("params", {})
            input_paths = self.resolve_input_paths(etl_name)
            output_path = config["output"]

            # Pass name and paths as standard parameters
            params["name"] = etl_name
            params["input_paths"] = input_paths
            params["output_path"] = output_path
            self.etl_instances[etl_name] = etl_class(**params)

    def run(self, parallel: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Executes all ETLs respecting dependencies.

        Args:
            parallel: If True, executes independent ETLs in parallel (not implemented yet)

        Returns:
            Dictionary with results of each ETL

        Raises:
            ETLDependencyError: If there are dependency errors
            ETLError: If any ETL execution fails
        """
        self.validate_dependencies()
        order = self.build_execution_order()
        self.instantiate_etls()

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Executing {len(self.execution_order)} ETLs in order:")
        logger.info(" → ".join(order))
        logger.info(f"{'=' * 60}\n")

        for i, etl_name in enumerate(self.execution_order):
            etl_config = self.etl_configs[etl_name]

            if not etl_config.get("enabled", True):
                logger.info(f"[SKIP] {etl_name} (disabled)")
                continue

            logger.info(f"\n{'─' * 60}")
            logger.info(f"ETL {i + 1}/{len(self.execution_order)}: {etl_name}")
            logger.info(f"{'─' * 60}")

            description = etl_config.get("description", "N/A")
            if description != "N/A":
                logger.info(f"Description: {description}")

            # Show resolved inputs
            input_paths = self.resolve_input_paths(etl_name)
            logger.info(f"Input(s): {len(input_paths)} file(s)")
            for path in input_paths[:3]:
                logger.info(f"  - {path}")
            if len(input_paths) > 3:
                logger.info(f"  ... and {len(input_paths) - 3} more")

            logger.info(f"Output: {etl_config['output']}")

            # Verify dependencies
            deps = etl_config.get("depends_on", [])
            for dep in deps:
                if dep not in self.results:
                    raise ETLDependencyError(f"Dependency '{dep}' did not execute correctly")

            # Execute ETL
            etl = self.etl_instances.get(etl_name)
            if etl:
                try:
                    result = etl.run(output_path=etl_config["output"])
                    self.results[etl_name] = result
                    logger.info(f"✓ {etl_name} completed ({len(result)} rows)")
                except Exception as e:
                    logger.error(f"✗ {etl_name} failed: {e}")
                    raise ETLError(f"Error executing ETL '{etl_name}': {e}")

        logger.info(f"\n{'=' * 60}")
        logger.info("ALL ETLs COMPLETED")
        logger.info(f"{'=' * 60}")

        return self.results

    def get_execution_plan(self) -> str:
        """
        Returns a visual representation of the execution plan.

        Returns:
            String with formatted plan
        """
        lines = ["\nETL Execution Plan:", "=" * 60]

        if not self.execution_order:
            try:
                self.build_execution_order()
            except ETLDependencyError:
                return "Error: Could not build execution plan (cycle detected)"

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
