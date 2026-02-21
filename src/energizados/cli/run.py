"""
Run command implementation for Energizados CLI.

Este módulo implementa la funcionalidad del comando 'run' para ejecutar
pipelines desde configuración YAML.
"""

from pathlib import Path
from typing import Any, Dict

from energizados.core.exceptions import ConfigurationError, PipelineError
from energizados.core.pipeline import ConfigPipelineBuilder


def execute_pipeline(config_path: str) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo desde configuración YAML.

    Args:
        config_path: Ruta al archivo de configuración YAML

    Returns:
        Dict: Contexto final con resultados del pipeline

    Raises:
        ConfigurationError: Si hay errores en la configuración
        PipelineError: Si hay errores durante la ejecución
    """
    # Construir pipeline desde configuración
    builder = ConfigPipelineBuilder(config_path)
    pipeline = builder.build()

    # Ejecutar pipeline
    result = pipeline.run()

    return result


def execute_step(config_path: str, step_name: str) -> Dict[str, Any]:
    """
    Ejecuta un solo paso del pipeline.

    Args:
        config_path: Ruta al archivo de configuración YAML
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
        "preprocessing": "PreprocessingStep",
        "feature_selection": "FeatureSelectionStep",
        "training": "TrainingStep",
        "evaluation": "EvaluationStep",
        "inference": "InferenceStep",
    }

    if step_name not in step_map:
        raise PipelineError(f"Paso desconocido: {step_name}. " f"Pasos disponibles: {list(step_map.keys())}")

    # Construir pipeline completo
    builder = ConfigPipelineBuilder(config_path)
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


def execute_etl(config_path: str, etl_name: str = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Ejecuta ETLs desde la configuración.

    Soporta:
    - Ejecutar todas las ETLs
    - Ejecutar una ETL específica (y sus dependencias)
    - Mostrar plan de ejecución sin ejecutar (dry-run)

    Args:
        config_path: Ruta al archivo de configuración YAML
        etl_name: Nombre de la ETL específica a ejecutar (None = todas)
        dry_run: Si True, solo muestra el plan de ejecución

    Returns:
        Dict: Resultados de las ETLs ejecutadas

    Raises:
        ConfigurationError: Si hay errores en la configuración
        PipelineError: Si hay errores durante la ejecución
    """
    import yaml

    from energizados.etl.orchestrator import ETLOrchestrator

    # Cargar configuración
    config_file = Path(config_path)
    if not config_file.exists():
        raise ConfigurationError(f"Archivo de configuración no encontrado: {config_path}", config_path)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Error al parsear YAML: {e}", config_path)

    # Verificar si hay configuración de ETLs
    etl_configs = config.get("etls")

    if not etl_configs:
        # Verificar si hay ETL único (formato legacy)
        legacy_etl = config.get("etl", {})
        if legacy_etl and legacy_etl.get("enabled", True):
            print("Configuración de ETL único detectada. Ejecutando pipeline completo...")
            return execute_step(config_path, "etl")
        else:
            raise PipelineError("No hay ETLs configuradas. Use 'etl' para ETL único o 'etls' para múltiples.")

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


def show_etl_plan(config_path: str) -> str:
    """
    Muestra el plan de ejecución de ETLs sin ejecutarlas.

    Args:
        config_path: Ruta al archivo de configuración YAML

    Returns:
        str: Plan de ejecución formateado

    Raises:
        ConfigurationError: Si hay errores en la configuración
    """
    return execute_etl(config_path, dry_run=True)
