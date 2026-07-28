"""
ETL Orchestrator for Energizados Framework.

This module provides the ETLOrchestrator which allows running multiple ETLs
respecting dependencies between them, implementing topological order.
"""

import glob
import json
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from energizados.core.exceptions import ETLDependencyError, ETLError
from energizados.core.utils import import_class
from energizados.core.utils.memory_sampler import MemorySampler

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
        ...     "transform": {
        ...         "input": "@extract", "output": "final.parquet", "depends_on": ["extract"]
        ...     }
        ... }
        >>> orchestrator = ETLOrchestrator(configs)
        >>> results = orchestrator.run()
    """

    def __init__(
        self,
        etl_configs: Dict[str, Dict],
        on_etl_start=None,
        on_etl_complete=None,
        on_etl_error=None,
        profile_memory: bool = False,
    ):
        """Initialize the orchestrator.

        Args:
            etl_configs: Dictionary with configuration for each ETL.
            profile_memory: When True, sample RSS around each ETL ``run`` and
                surface the stats via ``on_etl_complete(..., metrics=...)`` and
                ``self.memory_metrics``. Off by default to keep zero overhead
                in normal runs; the CLI enables it under ``-vv``.
        """
        from energizados._version import SCHEMA_VERSION_KEY

        # Filter top-level scalar keys that live under ``etl:`` but are NOT ETL
        # entries. SCHEMA_VERSION_KEY, output_base_dir and output_name (ADR: generalized run-dir)
        # would otherwise be treated as ETLs and fail validation (missing
        # ``input``) or register as bogus DAG nodes.
        _EXCLUDED_TOP_KEYS = {SCHEMA_VERSION_KEY, "output_base_dir", "output_name"}
        self.etl_configs = {k: v for k, v in etl_configs.items() if k not in _EXCLUDED_TOP_KEYS}
        self.etl_instances: Dict[str, object] = {}
        self.execution_order: List[str] = []
        self.results: Dict[str, pd.DataFrame] = {}
        self.on_etl_start = on_etl_start
        self.on_etl_complete = on_etl_complete
        self.on_etl_error = on_etl_error
        self.profile_memory = profile_memory
        self.memory_metrics: Dict[str, Dict[str, int]] = {}

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
            """Perform DFS from node; return True if a back-edge (cycle) is found."""
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
                    raise ETLDependencyError(
                        f"Cycle detected in ETL dependencies involving '{etl}'"
                    )

    def build_execution_order(self) -> List[str]:
        """
        Builds the execution order using topological order (BFS).

        Only includes ETLs with enabled=True (or no enabled key, defaults to True).

        Returns:
            List of ETL names in execution order

        Raises:
            ETLDependencyError: If the order cannot be determined (cycle)
        """
        enabled_configs = {
            name: config for name, config in self.etl_configs.items() if config.get("enabled", True)
        }

        enabled_names = set(enabled_configs.keys())

        in_degree = defaultdict(int)
        adj_list = defaultdict(list)

        for etl_name, config in enabled_configs.items():
            deps = config.get("depends_on", [])
            valid_deps = [d for d in deps if d in enabled_names]
            in_degree[etl_name] = len(valid_deps)
            for dep in valid_deps:
                adj_list[dep].append(etl_name)

        queue = deque([etl for etl in enabled_configs if in_degree[etl] == 0])
        order = []

        while queue:
            etl = queue.popleft()
            order.append(etl)

            for neighbor in adj_list[etl]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(enabled_configs):
            remaining = [e for e in enabled_configs if e not in order]
            raise ETLDependencyError(
                f"Could not determine topological order. Check dependencies of: {remaining}"
            )

        self.execution_order = order
        return order

    def _is_incremental(self, etl_name: str) -> bool:
        """Check if an ETL is configured in incremental mode.

        Args:
            etl_name: Name of the ETL.

        Returns:
            True if params.mode == "incremental".
        """
        config = self.etl_configs.get(etl_name, {})
        return config.get("params", {}).get("mode") == "incremental"

    def _read_manifest(self, state_file: Optional[str]) -> Optional[Dict]:
        """Read manifest data from the ETL's unified state file.

        The state file (.etl_state.json) contains both incremental tracking
        fields (processed_files, last_processed_value) and manifest fields
        (run_id, new_partitions, all_partitions) in a single JSON file.

        Args:
            state_file: Path to the ETL's state file.

        Returns:
            State dict (with manifest fields) or None if not found / unreadable.
        """
        if not state_file:
            return None

        state_path = Path(state_file)
        if not state_path.exists():
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"  • Could not read state file at {state_path}: {e}")
            return None

    def resolve_input_paths(self, etl_name: str) -> List[str]:
        """
        Resolves the input paths for an ETL.

        Supports:
        - Individual files: "data/file.csv"
        - File list: ["file1.csv", "file2.csv"]
        - Glob expressions: "*.csv", "data/**/*.parquet"
        - References to other ETLs: "@etl_name"
        - Manifest-aware resolution: when both upstream and downstream are
          incremental, returns only new partitions from the upstream manifest.

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

        downstream_incremental = self._is_incremental(etl_name)

        resolved_paths: List[str] = []
        for path_spec in raw_input:
            # Reference to another ETL (@etl_name)
            if path_spec.startswith("@"):
                ref_etl = path_spec[1:]
                if ref_etl in self.etl_configs:
                    ref_config = self.etl_configs[ref_etl]
                    if not ref_config.get("enabled", True):
                        logger.debug(
                            f"ETL '{etl_name}' references disabled ETL "
                            f"'{ref_etl}', skipping its output"
                        )
                        continue
                    ref_output = ref_config.get("output")
                    if not ref_output:
                        raise ETLDependencyError(
                            f"ETL '{etl_name}' references '{ref_etl}' via @, "
                            f"but '{ref_etl}' has no output path"
                        )

                    # Manifest-aware resolution: both upstream and downstream incremental
                    if downstream_incremental and self._is_incremental(ref_etl):
                        manifest = self._read_manifest(
                            ref_config.get("params", {}).get("state_file")
                        )
                        if manifest and manifest.get("new_partitions"):
                            # Return specific partition paths
                            for part_val in manifest["new_partitions"]:
                                partition_path = f"{ref_output}/partition={part_val}/data.parquet"
                                resolved_paths.append(partition_path)
                            continue
                        # No manifest → fall back to full output dir

                    resolved_paths.append(ref_output)
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
                # Check if this path is the output of an upstream ETL
                is_upstream_output = any(
                    self.etl_configs.get(upstream, {}).get("output") == path_spec
                    for upstream in self.etl_configs
                )
                if not is_upstream_output and not Path(path_spec).exists():
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
                raise ETLError(
                    f"ETL '{etl_name}': must specify 'custom_class'. "
                    f"Example: SourceETL (with mode='concat' or mode='merge'), or a custom class."
                )

            etl_class = import_class(config["custom_class"])
            # Copy params to avoid modifying the original config dict
            params = dict(config.get("params", {}))
            input_paths = self.resolve_input_paths(etl_name)
            output_path = config.get("output")

            # Pass name and paths as standard parameters
            params["name"] = etl_name
            params["input_paths"] = input_paths
            params["output_path"] = output_path
            self.etl_instances[etl_name] = etl_class(**params)

    def run(self) -> Dict[str, pd.DataFrame]:
        """
        Executes all ETLs respecting dependencies.

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

            output_path = etl_config.get("output")
            if output_path:
                logger.info(f"Output: {output_path}")

            # Verify dependencies
            deps = etl_config.get("depends_on", [])
            for dep in deps:
                if dep not in self.results:
                    raise ETLDependencyError(f"Dependency '{dep}' did not execute correctly")

            # Execute ETL
            etl = self.etl_instances.get(etl_name)
            if etl:
                if self.on_etl_start:
                    self.on_etl_start(etl_name, i, len(self.execution_order))
                try:
                    metrics = None
                    if self.profile_memory:
                        with MemorySampler() as sampler:
                            result = etl.run(output_path=etl_config.get("output"))
                        metrics = sampler.stats
                        self.memory_metrics[etl_name] = metrics
                    else:
                        result = etl.run(output_path=etl_config.get("output"))
                    self.results[etl_name] = result
                    logger.info(f"✓ {etl_name} completed ({len(result)} rows)")
                    if self.on_etl_complete:
                        self.on_etl_complete(etl_name, len(result), metrics=metrics)
                except Exception as e:
                    # Log a one-liner here. The full traceback is emitted once by the
                    # CLI top-level handler (cli.main.run) so it reaches run.log a
                    # single time and the console doesn't render the traceback twice.
                    logger.error("✗ %s failed: %s", etl_name, e)
                    if self.on_etl_error:
                        self.on_etl_error(etl_name, e)
                    raise ETLError(f"Error executing ETL '{etl_name}': {e}") from e

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
            output = config.get("output")
            if output:
                lines.append(f"   Output: {output}")

        return "\n".join(lines)
