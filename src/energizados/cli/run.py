"""
Run command implementation for Energizados CLI.

Este módulo implementa la funcionalidad del comando 'run' para ejecutar
pipelines desde configuración YAML.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from energizados.core.exceptions import ConfigurationError, PipelineError
from energizados.core.pipeline import ConfigPipelineBuilder


def merge_configs(config_paths: List[str]) -> Dict[str, Any]:
    """
    Mezcla múltiples archivos de configuración en uno solo.

    La estrategia es "last wins": si hay claves duplicadas,
    el último archivo sobrescribe los valores anteriores.

    Args:
        config_paths: Lista de rutas a archivos YAML

    Returns:
        Dict: Configuración combinada

    Raises:
        ConfigurationError: Si algún archivo no existe o tiene errores de formato
    """
    merged_config = {}

    for config_path in config_paths:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigurationError(f"Archivo de configuración no encontrado: {config_path}", config_path)

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                if config is None:
                    config = {}
                merged_config.update(config)
                logger = __import__("logging").getLogger(__name__)
                logger.debug(f"Configuración cargada desde: {config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error al parsear YAML en {config_path}: {e}", config_path)

    return merged_config


def execute_pipeline(config_paths: List[str]) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo desde configuración(es) YAML.

    Args:
        config_paths: Lista de rutas a archivos de configuración YAML

    Returns:
        Dict: Contexto final con resultados del pipeline

    Raises:
        ConfigurationError: Si hay errores en la configuración
        PipelineError: Si hay errores durante la ejecución
    """
    # Mezclar configuraciones
    merged_config = merge_configs(config_paths)

    # Construir pipeline desde configuración
    builder = ConfigPipelineBuilder(config=merged_config)
    pipeline = builder.build()

    # Ejecutar pipeline
    result = pipeline.run()

    return result


def execute_step(config_paths: List[str], step_name: str) -> Dict[str, Any]:
    """
    Ejecuta un solo paso del pipeline.

    Args:
        config_paths: Lista de rutas a archivos de configuración YAML
        step_name: Nombre del paso a ejecutar

    Returns:
        Dict: Contexto actualizado después del paso

    Raises:
        ConfigurationError: Si hay errores en la configuración
        PipelineError: Si el paso no existe o hay errores durante la ejecución
    """
    # Mapeo de nombres de pasos
    step_map = {
        "etl": "ETLStep",
        "split": "SplitStep",
        "training": "TrainingStep",
        "evaluation": "EvaluationStep",
        "inference": "InferenceStep",
    }

    if step_name not in step_map:
        raise PipelineError(f"Paso desconocido: {step_name}. " f"Pasos disponibles: {list(step_map.keys())}")

    # Mezclar configuraciones
    merged_config = merge_configs(config_paths)

    # Construir pipeline completo
    builder = ConfigPipelineBuilder(config=merged_config)
    pipeline = builder.build()

    # Filtrar solo el paso solicitado
    step_class_name = step_map[step_name]
    filtered_steps = [s for s in pipeline.steps if s.__class__.__name__ == step_class_name]

    if not filtered_steps:
        raise PipelineError(f"El paso '{step_name}' no está configurado o no está habilitado")

    # Reemplazar pasos del pipeline
    pipeline.steps = filtered_steps

    # Ejecutar solo el paso seleccionado
    result = pipeline.run()

    return result


def execute_etl(config_paths: List[str], etl_name: str = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Ejecuta ETLs desde la configuración.

    Soporta:
    - Ejecutar todas las ETLs
    - Ejecutar una ETL específica (y sus dependencias)
    - Mostrar plan de ejecución sin ejecutar (dry-run)

    Args:
        config_paths: Lista de rutas a archivos de configuración YAML
        etl_name: Nombre de la ETL específica a ejecutar (None = todas)
        dry_run: Si True, solo muestra el plan de ejecución

    Returns:
        Dict: Resultados de las ETLs ejecutadas

    Raises:
        ConfigurationError: Si hay errores en la configuración
        PipelineError: Si hay errores durante la ejecución
    """
    from energizados.etl.orchestrator import ETLOrchestrator

    # Mezclar configuraciones
    merged_config = merge_configs(config_paths)

    # Verificar si hay configuración de ETLs
    etl_configs = merged_config.get("etls")

    if not etl_configs:
        raise PipelineError("No hay ETLs configuradas. Use la sección 'etls:' para configurar múltiples ETLs.")

    # Si se solicita una ETL específica, filtrar sus dependencias
    if etl_name:
        if etl_name not in etl_configs:
            raise PipelineError(f"ETL '{etl_name}' no encontrada. " f"ETLs disponibles: {list(etl_configs.keys())}")

        # Filtrar solo las ETLs necesarias (etl_name + dependencias)
        filtered_configs = _get_etl_with_dependencies(etl_configs, etl_name)
        orchestrator = ETLOrchestrator(filtered_configs)
    else:
        orchestrator = ETLOrchestrator(etl_configs)

    # Mostrar plan de ejecución
    print(orchestrator.get_execution_plan())

    if dry_run:
        print("\n--dry-run: No se ejecutaron las ETLs --")
        return {}

    # Ejecutar ETLs
    results = orchestrator.run()

    return results


def _get_etl_with_dependencies(etl_configs: Dict[str, Dict], etl_name: str) -> Dict[str, Dict]:
    """
    Obtiene una ETL y todas sus dependencias recursivamente.

    Args:
        etl_configs: Configuración de todas las ETLs
        etl_name: Nombre de la ETL objetivo

    Returns:
        Dict con la ETL y sus dependencias
    """
    result = {}
    visited = set()

    def collect_deps(name: str):
        if name in visited:
            return
        if name not in etl_configs:
            raise PipelineError(f"ETL '{name}' no encontrada en configuración")

        visited.add(name)
        config = etl_configs[name]

        # Primero recolectar dependencias
        for dep in config.get("depends_on", []):
            collect_deps(dep)

        # Luego agregar esta ETL
        result[name] = config

    collect_deps(etl_name)
    return result


def show_etl_plan(config_paths: List[str]) -> str:
    """
    Muestra el plan de ejecución de ETLs sin ejecutarlas.

    Args:
        config_paths: Lista de rutas a archivos de configuración YAML

    Returns:
        str: Plan de ejecución formateado

    Raises:
        ConfigurationError: Si hay errores en la configuración
    """
    return execute_etl(config_paths, dry_run=True)
