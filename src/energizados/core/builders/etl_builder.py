"""
ETL Step Builder.

This module constructs ETL pipeline steps from configuration.
"""

from typing import Any, Dict, List, Optional

from energizados.core.base import PipelineStep
from energizados.core.builders.base import StepBuilder
from energizados.etl.orchestrator import ETLOrchestrator


class ETLBuilder(StepBuilder):
    """
    Builder for ETL pipeline steps.

    Constructs a step that orchestrates multiple ETLs with dependencies
    based on the 'etls' section of the configuration.
    """

    def build(self) -> Optional[PipelineStep]:
        """
        Build the ETL step from configuration.

        The configuration should contain an 'etls' key with ETL definitions.

        Returns:
            PipelineStep: The ETL step, or None if no ETLs are configured
        """
        etl_configs = self.config.get("etls", {})
        if not etl_configs:
            return None

        orchestrator = ETLOrchestrator(etl_configs)

        class ETLStep(PipelineStep):
            """Pipeline step that executes multiple ETLs."""

            def __init__(self, orchestrator: ETLOrchestrator):
                self.orchestrator = orchestrator

            def validate_input(self, context: Dict[str, Any]) -> bool:
                """Return True; ETLs read from disk and require no prior context.

                Args:
                    context: Pipeline context dict (unused).

                Returns:
                    bool: Always True.
                """
                # ETLs do not require previous input from context
                return True

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                """Run all ETLs via the orchestrator and populate context.

                Args:
                    context: Pipeline context dict.

                Returns:
                    Dict: Updated context with ``data`` (last ETL output) and
                        ``etl_results`` (all ETL outputs).
                """
                # Execute all ETLs in topological order
                results = self.orchestrator.run()

                # Pass the output of the last ETL to context
                if self.orchestrator.execution_order:
                    last_etl = self.orchestrator.execution_order[-1]
                    context["data"] = results[last_etl]

                context["etl_results"] = results
                return context

            def get_required_keys(self) -> List[str]:
                """Return empty list; ETLStep has no required context keys.

                Returns:
                    List[str]: Empty list.
                """
                return []

            def get_output_keys(self) -> List[str]:
                """Return the context keys produced by this step.

                Returns:
                    List[str]: ``["data", "etl_results"]``.
                """
                return ["data", "etl_results"]

        return ETLStep(orchestrator)

    def is_enabled(self) -> bool:
        """Check if ETL step is enabled.

        Returns:
            bool: True if 'etls' key exists in config
        """
        return "etls" in self.config and bool(self.config.get("etls"))
