"""
Pipeline Orchestrator para el Framework Energizados.

Este módulo contiene las clases que orquestan la ejecución del workflow
de ML, coordinando los diferentes pasos del pipeline.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from energizados.core.base import PipelineStep
from energizados.core.exceptions import (
    ConfigurationError,
    PipelineError,
    StepValidationError,
)

logger = logging.getLogger(__name__)


def _load_yaml_config(path: str) -> Dict:
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
        return _load_yaml_config(path)

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

            logger.info(f"\n{'=' * 60}")
            logger.info(f"PASO {i}/{total_steps}: {step_name}")
            logger.info(f"{'=' * 60}")

            # Validar entrada
            if not step.validate_input(self.context):
                missing_keys = step.get_required_keys()
                raise StepValidationError(f"Validación falló en paso {step_name}", step=step_name, missing_keys=missing_keys)

            # Ejecutar paso
            try:
                self.context = step.execute(self.context)
                logger.info(f"✓ Paso {step_name} completado")
            except Exception as e:
                raise PipelineError(f"Error ejecutando paso {step_name}: {e}", step=step_name)

        logger.info(f"\n{'=' * 60}")
        logger.info("PIPELINE COMPLETADO EXITOSAMENTE")
        logger.info(f"{'=' * 60}")

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
    INFERENCE_REGISTRY = {}

    def __init__(self, config_path: str = None, config: Dict = None):
        """
        Inicializa el builder.

        Args:
            config_path: Ruta al archivo de configuración YAML (opcional)
            config: Diccionario de configuración (opcional, tiene prioridad sobre config_path)
        """
        if config is not None:
            self.config = config
            self.config_path = None
        elif config_path is not None:
            self.config_path = config_path
            self.config = self._load_config(config_path)
        else:
            raise ValueError("Debe proporcionar config_path o config")

    def _load_config(self, path: str) -> Dict:
        """
        Carga configuración desde YAML.

        Args:
            path: Ruta al archivo YAML

        Returns:
            Dict: Configuración cargada
        """
        return _load_yaml_config(path)

    def build(self) -> Pipeline:
        """
        Construye el pipeline desde la configuración.

        Returns:
            Pipeline: Pipeline configurado listo para ejecutar

        Raises:
            ConfigurationError: Si falta configuración requerida
        """
        pipeline = Pipeline(config=self.config)

        # Paso 1: ETL (múltiples ETLs con dependencias)
        if "etls" in self.config:
            etl_step = self._build_etl_step()
            if etl_step is not None:
                pipeline.add_step(etl_step)

        # Paso 2: Feature Pipeline (preprocessing + feature_selection unificados)
        if self.config.get("feature_pipeline", {}).get("enabled", True):
            fp_step = self._build_feature_pipeline_step()
            if fp_step is not None:
                pipeline.add_step(fp_step)

        # Paso 3: Training
        train_step = self._build_training_step()
        if train_step is not None:
            pipeline.add_step(train_step)

        # Paso 4: Evaluation
        if self.config.get("evaluation", {}).get("enabled", True):
            eval_step = self._build_evaluation_step()
            if eval_step is not None:
                pipeline.add_step(eval_step)

        # Paso 5: Inference
        if self.config.get("inference", {}).get("enabled", False):
            inference_step = self._build_inference_step()
            if inference_step is not None:
                pipeline.add_step(inference_step)

        return pipeline

    def _build_etl_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de ETL desde la configuración.

        Usa múltiples ETLs con dependencias (sección 'etls:').

        Returns:
            PipelineStep: Paso de ETL o None si no está configurado
        """
        if "etls" in self.config:
            return self._build_multi_etl_step()
        return None

    def _build_multi_etl_step(self) -> Optional[PipelineStep]:
        """
        Construye un paso que orquesta múltiples ETLs con dependencias.

        Returns:
            PipelineStep: ETLStep o None si no hay ETLs configuradas
        """
        from energizados.core.base import PipelineStep
        from energizados.etl.orchestrator import ETLOrchestrator

        etl_configs = self.config.get("etls", {})
        if not etl_configs:
            return None

        orchestrator = ETLOrchestrator(etl_configs)

        class ETLStep(PipelineStep):
            """Paso del pipeline que ejecuta múltiples ETLs."""

            def __init__(self, orchestrator: ETLOrchestrator):
                self.orchestrator = orchestrator

            def validate_input(self, context: Dict[str, Any]) -> bool:
                # Las ETLs no requieren input previo del contexto
                return True

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                # Ejecutar todas las ETLs en orden topológico
                results = self.orchestrator.run()

                # Pasar el output de la última ETL al contexto
                if self.orchestrator.execution_order:
                    last_etl = self.orchestrator.execution_order[-1]
                    context["data"] = results[last_etl]

                context["etl_results"] = results
                return context

            def get_required_keys(self) -> List[str]:
                return []

        return ETLStep(orchestrator)

    def _build_feature_pipeline_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de feature pipeline desde la configuración.

        Este paso unifica preprocessing y feature_selection en un solo paso.

        Returns:
            PipelineStep: Paso de feature pipeline o None si no está configurado
        """
        from energizados.core.base import PipelineStep
        from energizados.feature_pipeline.default import DefaultFeaturePipeline

        fp_config = self.config.get("feature_pipeline", {})
        if not fp_config:
            return None

        # Si el usuario especificó una clase personalizada
        if "custom_class" in fp_config:
            pipeline_instance = self._import_and_instantiate(fp_config["custom_class"], fp_config.get("params", {}))
        else:
            # Usar DefaultFeaturePipeline
            preprocessing_config = fp_config.get("preprocessing", {})
            fs_config = fp_config.get("feature_selection", {})

            pipeline_instance = DefaultFeaturePipeline(
                preprocessor_num=preprocessing_config.get("preprocessor_num", 4),
                categorical_features=preprocessing_config.get("categorical_features", []),
                feature_selection_config=fs_config,
            )

        # Envolver en un PipelineStep
        input_path = fp_config.get("input_path")
        output_pkl = fp_config.get("output_pkl")
        output_parquet = fp_config.get("output_parquet")

        class FeaturePipelineStep(PipelineStep):
            """Paso del pipeline que ejecuta preprocessing + feature_selection."""

            def __init__(self, feature_pipeline, config):
                self.feature_pipeline = feature_pipeline
                self.config = config

            def validate_input(self, context: Dict[str, Any]) -> bool:
                # Verificar que haya datos disponibles
                if input_path:
                    # Se leerán desde archivo
                    return True
                return "data" in context or "etl_results" in context

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                # Obtener datos
                if input_path:
                    import pandas as pd

                    data = pd.read_parquet(input_path)
                elif "data" in context:
                    data = context["data"]
                elif "etl_results" in context:
                    # Usar el último resultado de ETL
                    last_etl = list(context["etl_results"].keys())[-1]
                    data = context["etl_results"][last_etl]
                else:
                    raise ValueError("No se encontraron datos para el feature pipeline")

                # Separar features y target si existe
                target_col = self.config.get("target_column", "target")
                if target_col in data.columns:
                    X = data.drop(columns=[target_col])
                    y = data[target_col]
                else:
                    X = data
                    y = None

                # Fit y transform
                if y is not None:
                    X_transformed = self.feature_pipeline.fit_transform(X, y)
                else:
                    X_transformed = self.feature_pipeline.transform(X)

                # Guardar pipeline como pickle
                if output_pkl:
                    self.feature_pipeline.save(output_pkl)
                    logger.info(f"Feature pipeline guardado en: {output_pkl}")

                # Guardar datos transformados como parquet (opcional)
                if output_parquet:
                    df_output = X_transformed.copy()
                    if y is not None:
                        df_output[target_col] = y.values
                    df_output.to_parquet(output_parquet, index=False)
                    logger.info(f"Datos transformados guardados en: {output_parquet}")
                    context["feature_pipeline_data"] = df_output
                else:
                    context["feature_pipeline_data"] = X_transformed

                # Guardar el pipeline en el contexto para uso posterior
                context["feature_pipeline"] = self.feature_pipeline

                return context

            def get_required_keys(self) -> List[str]:
                return []

            def get_output_keys(self) -> List[str]:
                keys = ["feature_pipeline"]
                if output_parquet:
                    keys.append("feature_pipeline_data")
                return keys

        return FeaturePipelineStep(pipeline_instance, fp_config)

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

    def _build_inference_step(self) -> Optional[PipelineStep]:
        """
        Construye el paso de inferencia desde la configuración.

        Returns:
            PipelineStep: Paso de inferencia o None si no está configurado
        """
        from energizados.core.base import PipelineStep

        inference_config = self.config.get("inference", {})
        if not inference_config:
            return None

        # Leer configuración
        input_path = inference_config.get("input_path")
        output_path = inference_config.get("output_path")
        threshold = inference_config.get("threshold", 0.5)
        custom_class = inference_config.get("custom_class")

        # Importar clase de inferencia
        if custom_class:
            from energizados.utils import import_class

            InferenceClass = import_class(custom_class)
        else:
            from energizados.inference.default import DefaultInference

            InferenceClass = DefaultInference

        inference = InferenceClass(threshold=threshold)

        class InferenceStep(PipelineStep):
            """Paso del pipeline para hacer predicciones con modelos entrenados."""

            def __init__(self, inference_engine, config):
                self.inference = inference_engine
                self.config = config

            def validate_input(self, context: Dict[str, Any]) -> bool:
                """Valida que haya modelo y datos disponibles."""
                return "model" in context and context["model"] is not None

            def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
                """Ejecuta la inferencia."""
                model = context.get("model")

                # Obtener datos de inferencia
                if input_path:
                    import pandas as pd

                    data = pd.read_parquet(input_path)
                elif "inference_data" in context:
                    data = context["inference_data"]
                elif "X_test" in context:
                    data = context["X_test"]
                else:
                    raise ValueError("No se encontraron datos para inferencia")

                # Hacer predicciones
                predictions = self.inference.predict(model, data)
                probas = self.inference.predict_proba(model, data)

                # Guardar en contexto
                context["predictions"] = predictions
                context["prediction_probas"] = probas

                # Guardar en archivo si se especificó output_path
                if output_path:
                    self.inference.save_predictions(predictions, output_path)
                    logger.info(f"Predicciones guardadas en: {output_path}")

                return context

            def get_required_keys(self) -> List[str]:
                return ["model"]

            def get_output_keys(self) -> List[str]:
                return ["predictions", "prediction_probas"]

        return InferenceStep(inference, inference_config)

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

    @classmethod
    def register_inference(cls, name: str, inference_class: type):
        """
        Registra una clase de inferencia en el registry.

        Args:
            name: Nombre de la clase de inferencia
            inference_class: Clase de inferencia
        """
        cls.INFERENCE_REGISTRY[name] = inference_class
