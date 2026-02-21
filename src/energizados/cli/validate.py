"""
Validate command implementation for Energizados CLI.

Este módulo implementa la funcionalidad del comando 'validate' para
validar archivos de configuración YAML.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from energizados.core.exceptions import ConfigurationError


class ValidationResult:
    """Resultado de validación con errores y advertencias."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def is_valid(self) -> bool:
        """Retorna True si no hay errores."""
        return len(self.errors) == 0

    def add_error(self, message: str):
        """Agrega un error."""
        self.errors.append(message)

    def add_warning(self, message: str):
        """Agrega una advertencia."""
        self.warnings.append(message)

    def add_info(self, message: str):
        """Agrega información."""
        self.info.append(message)


def validate_config(config_path: str, verbose: bool = False) -> ValidationResult:
    """
    Valida un archivo de configuración YAML.

    Args:
        config_path: Ruta al archivo de configuración
        verbose: Si es True, muestra detalles completos

    Returns:
        ValidationResult: Resultado de la validación

    Raises:
        ConfigurationError: Si hay errores críticos en la configuración
    """
    result = ValidationResult()

    # Verificar que el archivo existe
    config_file = Path(config_path)
    if not config_file.exists():
        result.add_error(f"Archivo no encontrado: {config_path}")
        raise ConfigurationError(f"Archivo no encontrado: {config_path}", config_path)

    # Cargar YAML
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        result.add_error(f"Error al parsear YAML: {e}")
        raise ConfigurationError(f"Error al parsear YAML: {e}", config_path)

    if config is None:
        result.add_error("Archivo de configuración vacío")
        raise ConfigurationError("Archivo de configuración vacío", config_path)

    # Validar secciones
    _validate_project_section(config, result)
    _validate_etl_section(config, result)
    _validate_preprocessing_section(config, result)
    _validate_feature_selection_section(config, result)
    _validate_training_section(config, result)
    _validate_evaluation_section(config, result)

    # Mostrar resultados
    if verbose:
        _print_validation_results(result, config)

    if not result.is_valid():
        raise ConfigurationError(f"Validación falló con {len(result.errors)} errores", config_path)

    return result


def _validate_project_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección project."""
    if "project" not in config:
        result.add_warning("Sección 'project' no encontrada (opcional)")
        return

    project = config["project"]
    if "name" not in project:
        result.add_warning("project.name no definido")
    else:
        result.add_info(f"Proyecto: {project['name']}")


def _validate_etl_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección etls (múltiples ETLs con dependencias)."""
    if "etls" not in config:
        result.add_error("Sección 'etls' requerida no encontrada")
        return

    etls = config["etls"]
    if not isinstance(etls, dict):
        result.add_error("Sección 'etls' debe ser un diccionario")
        return

    if not etls:
        result.add_warning("Sección 'etls' está vacía")
        return

    # Validar cada ETL
    for etl_name, etl_config in etls.items():
        if not isinstance(etl_config, dict):
            result.add_error(f"ETL '{etl_name}': debe ser un diccionario")
            continue

        # Verificar campos requeridos
        if "input" not in etl_config:
            result.add_error(f"ETL '{etl_name}': campo 'input' requerido")

        if "output" not in etl_config:
            result.add_error(f"ETL '{etl_name}': campo 'output' requerido")

        if "depends_on" not in etl_config:
            result.add_warning(f"ETL '{etl_name}': campo 'depends_on' no encontrado, usando []")

        # custom_class es obligatorio
        if "custom_class" not in etl_config:
            result.add_error(f"ETL '{etl_name}': debe especificar 'custom_class'")
        else:
            _validate_class_reference(etl_config["custom_class"], result)

        enabled = etl_config.get("enabled", True)
        result.add_info(f"ETL '{etl_name}': {'habilitado' if enabled else 'deshabilitado'}")


def _validate_preprocessing_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección preprocessing."""
    if "preprocessing" not in config:
        result.add_error("Sección 'preprocessing' requerida no encontrada")
        return

    prep = config["preprocessing"]
    if not isinstance(prep, dict):
        result.add_error("Sección 'preprocessing' debe ser un diccionario")
        return

    if prep.get("enabled", True):
        if "output_path" not in prep:
            result.add_warning("preprocessing.output_path no definido")

        if "categorical_features" not in prep:
            result.add_warning("preprocessing.categorical_features no definido")
        else:
            features = prep["categorical_features"]
            if not isinstance(features, list) or len(features) == 0:
                result.add_warning("preprocessing.categorical_features debe ser una lista no vacía")
            else:
                result.add_info(f"Features categóricas: {len(features)}")

        result.add_info(f"Preprocessing: {'habilitado' if prep.get('enabled', True) else 'deshabilitado'}")


def _validate_feature_selection_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección feature_selection."""
    if "feature_selection" not in config:
        result.add_warning("Sección 'feature_selection' no encontrada (opcional)")
        return

    fs = config["feature_selection"]
    if not isinstance(fs, dict):
        result.add_error("Sección 'feature_selection' debe ser un diccionario")
        return

    if fs.get("enabled", False):
        # Verificar que tenga method o custom_class
        has_method = "method" in fs
        has_custom = "custom_class" in fs

        if not has_method and not has_custom:
            result.add_error("feature_selection: se requiere 'method' o 'custom_class' cuando está habilitado")

        if has_method:
            valid_methods = ["boruta", "correlation", "constant"]
            method = fs["method"]
            if method not in valid_methods:
                result.add_error(f"feature_selection.method inválido: {method}. Válidos: {valid_methods}")
            else:
                result.add_info(f"Feature selection: {method}")

        if has_custom:
            _validate_class_reference(fs["custom_class"], result)

        result.add_info("Feature selection: habilitado")
    else:
        result.add_info("Feature selection: deshabilitado")


def _validate_training_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección training."""
    if "training" not in config:
        result.add_error("Sección 'training' requerida no encontrada")
        return

    training = config["training"]
    if not isinstance(training, dict):
        result.add_error("Sección 'training' debe ser un diccionario")
        return

    # Verificar modelo
    has_model_type = "model_type" in training
    has_custom = "custom_class" in training

    if not has_model_type and not has_custom:
        result.add_error("training: se requiere 'model_type' o 'custom_class'")

    if has_model_type:
        valid_models = ["lightgbm", "lgbm", "catboost", "cat", "neural_network", "nn", "lstm", "simple_trend", "simple_constant"]
        model_type = training["model_type"]
        if model_type not in valid_models:
            result.add_warning(f"training.model_type desconocido: {model_type}")
        else:
            result.add_info(f"Modelo: {model_type}")

    if has_custom:
        _validate_class_reference(training["custom_class"], result)

    # Verificar parámetros de partición
    if "test_size" in training:
        test_size = training["test_size"]
        if not 0 < test_size < 1:
            result.add_warning(f"training.test_size debe estar entre 0 y 1, got: {test_size}")

    if "val_size" in training:
        val_size = training["val_size"]
        if not 0 < val_size < 1:
            result.add_warning(f"training.val_size debe estar entre 0 y 1, got: {val_size}")

    # Verificar sampling
    if "sampling" in training:
        sampling = training["sampling"]
        if isinstance(sampling, dict):
            valid_methods = ["over", "under", "none"]
            method = sampling.get("method")
            if method and method not in valid_methods:
                result.add_warning(f"training.sampling.method inválido: {method}")


def _validate_evaluation_section(config: Dict[str, Any], result: ValidationResult):
    """Valida la sección evaluation."""
    if "evaluation" not in config:
        result.add_warning("Sección 'evaluation' no encontrada (opcional)")
        return

    eval_config = config["evaluation"]
    if not isinstance(eval_config, dict):
        result.add_error("Sección 'evaluation' debe ser un diccionario")
        return

    if eval_config.get("enabled", True):
        if "metrics" in eval_config:
            metrics = eval_config["metrics"]
            if not isinstance(metrics, list):
                result.add_error("evaluation.metrics debe ser una lista")
            else:
                valid_metrics = ["auc", "precision", "recall", "f1", "confusion_matrix", "cumulative_gains"]
                for metric in metrics:
                    if metric not in valid_metrics:
                        result.add_warning(f"Métrica desconocida: {metric}")

        result.add_info(f"Evaluación: {'habilitada' if eval_config.get('enabled', True) else 'deshabilitada'}")


def _validate_class_reference(class_path: str, result: ValidationResult):
    """
    Valida que una referencia de clase sea válida.

    Args:
        class_path: Path completo de la clase (ej: "module.submodule.ClassName")
        result: Resultado de validación para agregar errores
    """
    if not class_path or "." not in class_path:
        result.add_error(f"Referencia de clase inválida: {class_path}")
        return

    try:
        module_path, class_name = class_path.rsplit(".", 1)

        # Intentar importar
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name, None)

        if cls is None:
            result.add_warning(f"Clase '{class_name}' no encontrada en módulo '{module_path}'")
    except (ImportError, AttributeError) as e:
        result.add_warning(f"No se pudo importar '{class_path}': {e}")


def _print_validation_results(result: ValidationResult, config: Dict[str, Any]):
    """Imprime los resultados de la validación."""
    print("\n" + "=" * 60)
    print("RESULTADOS DE VALIDACIÓN")
    print("=" * 60)

    if result.info:
        print("\n📋 Información:")
        for info in result.info:
            print(f"  • {info}")

    if result.warnings:
        print(f"\n⚠️  Advertencias ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  • {warning}")

    if result.errors:
        print(f"\n❌ Errores ({len(result.errors)}):")
        for error in result.errors:
            print(f"  • {error}")

    print("\n" + "=" * 60)
    if result.is_valid():
        print("✓ CONFIGURACIÓN VÁLIDA")
    else:
        print("✗ CONFIGURACIÓN INVÁLIDA")
    print("=" * 60)
