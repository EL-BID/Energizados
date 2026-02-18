"""
Pipeline Orchestrator para el Framework Energizados.

Este módulo contiene las clases que orquestan la ejecución del workflow
de ML, coordinando los diferentes pasos del pipeline.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    ConfigurationError,
    PipelineError,
    StepValidationError,
)


class Pipeline:
    """
    Orquestador del workflow de ML.

    Ejecuta los pasos en orden y maneja el contexto compartido entre pasos.

    Args:
        config_path: Ruta al archivo de configuración YAML
        config: Diccionario de configuración (opcional, si se pasa se ignora config_path)

    Attributes:
        config: Diccionario con la configuración del pipeline
        context: Diccionario con los datos compartidos entre pasos
        steps: Lista de pasos a ejecutar

    Example:
        >>> pipeline = Pipeline("config.yaml")
        >>> pipeline.add_step(ETLStep())
        >>> pipeline.add_step(TrainingStep())
        >>> results = pipeline.run()
    """

    def __init__(self, config_path: str = None, config: Dict = None):
        """
        Inicializa el pipeline.

        Args:
            config_path: Ruta al archivo de configuración YAML
            config: Diccionario de configuración (opcional)
        """
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = self._load_config(config_path)
        else:
            self.config = {}

        self.context: Dict[str, Any] = {}
        self.steps: List[PipelineStep] = []

    def _load_config(self, path: str) -> Dict:
        """
        Carga configuración desde YAML.

        Args:
            path: Ruta al archivo YAML

        Returns:
            Dict: Configuración cargada

        Raises:
            ConfigurationError: Si el archivo no existe o tiene errores de formato
        """
        config_file = Path(path)
        if not config_file.exists():
            raise ConfigurationError(f"Archivo de configuración no encontrado: {path}", path)

        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error al parsear YAML: {e}", path)

    def add_step(self, step: PipelineStep) -> "Pipeline":
        """
        Agrega un paso al pipeline.

        Args:
            step: Paso a agregar

        Returns:
            self: Permite encadenar llamadas
        """
        self.steps.append(step)
        return self

    def run(self) -> Dict[str, Any]:
        """
        Ejecuta todos los pasos del pipeline.

        Returns:
            Dict: Contexto final con resultados

        Raises:
            PipelineError: Si ocurre un error durante la ejecución
            StepValidationError: Si la validación de un paso falla
        """
        if not self.steps:
            raise PipelineError("No hay pasos configurados en el pipeline")

        total_steps = len(self.steps)

        for i, step in enumerate(self.steps, 1):
            step_name = step.__class__.__name__

            print(f"\n{'=' * 60}")
            print(f"PASO {i}/{total_steps}: {step_name}")
            print(f"{'=' * 60}")

            # Validar entrada
            if not step.validate_input(self.context):
                missing_keys = step.get_required_keys()
                raise StepValidationError(f"Validación falló en paso {step_name}", step=step_name, missing_keys=missing_keys)

            # Ejecutar paso
            try:
                self.context = step.execute(self.context)
                print(f"✓ Paso {step_name} completado")
            except Exception as e:
                raise PipelineError(f"Error ejecutando paso {step_name}: {e}", step=step_name)

        print(f"\n{'=' * 60}")
        print("PIPELINE COMPLETADO EXITOSAMENTE")
        print(f"{'=' * 60}")

        return self.context

    def get_context(self) -> Dict[str, Any]:
        """
        Retorna el contexto actual del pipeline.

        Returns:
            Dict: Contexto actual
        """
        return self.context.copy()

    def reset(self):
        """Resetea el contexto y los pasos del pipeline."""
        self.context = {}
        self.steps = []


class ConfigPipelineBuilder:
    """
    Constructor de pipeline desde configuración YAML.

    Esta clase lee un archivo de configuración YAML y construye
    automáticamente el pipeline con los pasos correspondientes.

    Args:
        config_path: Ruta al archivo de configuración YAML

    Example:
        >>> builder = ConfigPipelineBuilder("config.yaml")
        >>> pipeline = builder.build()
        >>> results = pipeline.run()
    """

    # Registries se poblarán dinámicamente
    MODEL_REGISTRY = {}
    SELECTOR_REGISTRY = {}
    ETL_REGISTRY = {}
    PREPROCESSOR_REGISTRY = {}

    def __init__(self, config_path: str):
        """
        Inicializa el builder.

        Args:
            config_path: Ruta al archivo de configuración YAML
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict:
        """
        Carga configuración desde YAML.

        Args:
            path: Ruta al archivo YAML

        Returns:
            Dict: Configuración cargada
        """
        config_file = Path(path)
        if not config_file.exists():
            raise ConfigurationError(f"Archivo de configuración no encontrado: {path}", path)

        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error al parsear YAML: {e}", path)

    def build(self) -> Pipeline:
        """
        Construye el pipeline desde la configuración.

        Returns:
            Pipeline: Pipeline configurado listo para ejecutar

        Raises:
            ConfigurationError: Si falta configuración requerida
        """
        pipeline = Pipeline(config=self.config)

        # Paso 1: ETL
        if self.config.get("etl", {}).get("enabled", True):
            etl_step = self._build_etl_step()
            if etl_step is not None:
                pipeline.add_step(etl_step)

        # Paso 2: Preprocessing
        if self.config.get("preprocessing", {}).get("enabled", True):
            prep_step = self._build_preprocessing_step()
            if prep_step is not None:
                pipeline.add_step(prep_step)

        # Paso 3: Feature Selection
        if self.config.get("feature_selection", {}).get("enabled", False):
            fs_step = self._build_feature_selection_step()
            if fs_step is not None:
                pipeline.add_step(fs_step)

        # Paso 4: Training
        train_step = self._build_training_step()
        if train_step is not None:
            pipeline.add_step(train_step)

        # Paso 5: Evaluation
        if self.config.get("evaluation", {}).get("enabled", True):
            eval_step = self._build_evaluation_step()
            if eval_step is not None:
                pipeline.add_step(eval_step)

        return pipeline

    def _build_etl_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de ETL desde la configuración.

        Returns:
            PipelineStep: Paso de ETL o None si no está configurado
        """
        etl_config = self.config.get("etl", {})
        if not etl_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in etl_config:
            return self._import_and_instantiate(etl_config["custom_class"], etl_config.get("params", {}))

        # Usa implementación del registry
        etl_type = etl_config.get("type", "default")
        etl_class = self.ETL_REGISTRY.get(etl_type)
        if etl_class:
            return etl_class(**etl_config)

        return None

    def _build_feature_selection_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de feature selection desde la configuración.

        Returns:
            PipelineStep: Paso de feature selection o None si no está configurado
        """
        fs_config = self.config.get("feature_selection", {})
        if not fs_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in fs_config:
            return self._import_and_instantiate(fs_config["custom_class"], fs_config.get("params", {}))

        # Usa método del registry
        method = fs_config.get("method")
        if method:
            selector_class = self.SELECTOR_REGISTRY.get(method)
            if selector_class:
                return selector_class(**fs_config.get("params", {}))

        return None

    def _build_training_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de entrenamiento desde la configuración.

        Returns:
            PipelineStep: Paso de entrenamiento o None si no está configurado
        """
        train_config = self.config.get("training", {})
        if not train_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in train_config:
            return self._import_and_instantiate(train_config["custom_class"], train_config.get("params", {}))

        # Usa modelo del registry
        model_type = train_config.get("model_type")
        if model_type:
            model_class = self.MODEL_REGISTRY.get(model_type)
            if model_class:
                return model_class(**train_config.get("params", {}))

        return None

    def _build_preprocessing_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de preprocesamiento desde la configuración.

        Returns:
            PipelineStep: Paso de preprocesamiento o None si no está configurado
        """
        prep_config = self.config.get("preprocessing", {})
        if not prep_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in prep_config:
            return self._import_and_instantiate(prep_config["custom_class"], prep_config.get("params", {}))

        # Usa preprocesador del registry
        prep_type = prep_config.get("type", "default")
        prep_class = self.PREPROCESSOR_REGISTRY.get(prep_type)
        if prep_class:
            return prep_class(**prep_config.get("params", {}))

        return None

    def _build_evaluation_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de evaluación desde la configuración.

        Returns:
            PipelineStep: Paso de evaluación o None si no está configurado
        """
        eval_config = self.config.get("evaluation", {})
        if not eval_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in eval_config:
            return self._import_and_instantiate(eval_config["custom_class"], eval_config.get("params", {}))

        # TODO: Implementar evaluador default cuando esté disponible
        return None

    def _import_and_instantiate(self, class_path: str, params: Dict):
        """
        Importa una clase desde su path completo y la instancia.

        Args:
            class_path: Path completo de la clase (ej: "module.submodule.ClassName")
            params: Parámetros para instanciar la clase

        Returns:
            Instancia de la clase

        Raises:
            ConfigurationError: Si no se puede importar la clase
        """
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name)
            return cls(**params)
        except (ImportError, AttributeError) as e:
            raise ConfigurationError(f"No se puede importar clase {class_path}: {e}", self.config_path)
        except Exception as e:
            raise ConfigurationError(f"Error instanciando {class_path}: {e}", self.config_path)

    @classmethod
    def register_model(cls, name: str, model_class: type):
        """
        Registra un modelo en el registry.

        Args:
            name: Nombre del modelo
            model_class: Clase del modelo
        """
        cls.MODEL_REGISTRY[name] = model_class

    @classmethod
    def register_selector(cls, name: str, selector_class: type):
        """
        Registra un selector en el registry.

        Args:
            name: Nombre del selector
            selector_class: Clase del selector
        """
        cls.SELECTOR_REGISTRY[name] = selector_class

    @classmethod
    def register_etl(cls, name: str, etl_class: type):
        """
        Registra un ETL en el registry.

        Args:
            name: Nombre del ETL
            etl_class: Clase del ETL
        """
        cls.ETL_REGISTRY[name] = etl_class

    @classmethod
    def register_preprocessor(cls, name: str, preprocessor_class: type):
        """
        Registra un preprocesador en el registry.

        Args:
            name: Nombre del preprocesador
            preprocessor_class: Clase del preprocesador
        """
        cls.PREPROCESSOR_REGISTRY[name] = preprocessor_class
