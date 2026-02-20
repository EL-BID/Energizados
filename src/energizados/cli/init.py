"""
Init command implementation for Energizados CLI.

Este módulo implementa la funcionalidad del comando 'init' para crear
nuevos proyectos con la estructura base.
"""

from pathlib import Path


def create_project(project_name: str, project_path: Path, template: str = "default"):
    """
    Crea un nuevo proyecto Energizados con la estructura base.

    Args:
        project_name: Nombre del proyecto
        project_path: Ruta donde crear el proyecto
        template: Nombre del template a usar

    Raises:
        FileExistsError: Si el directorio del proyecto ya existe
        ValueError: Si el template no existe
    """
    if project_path.exists():
        raise FileExistsError(f"El directorio '{project_path}' ya existe")

    # Crear estructura de directorios
    _create_directory_structure(project_path)

    # Crear archivos base
    _create_base_files(project_path, project_name)

    # Crear templates de código
    _create_code_templates(project_path, project_name)

    # Crear configuración
    _create_config_files(project_path, project_name)


def _create_directory_structure(project_path: Path):
    """Crea la estructura de directorios del proyecto."""
    directories = [
        project_path / "etl",
        project_path / "feature_selection",
        project_path / "models",
        project_path / "configs",
        project_path / "data" / "raw",
        project_path / "data" / "processed",
        project_path / "models" / "trained",
        project_path / "reports",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    # Crear archivos __init__.py para cada módulo
    init_modules = {
        project_path / "etl" / "__init__.py": ("custom_etl", "CustomETL"),
        project_path / "feature_selection" / "__init__.py": ("custom_selector", "CustomSelector"),
        project_path / "models" / "__init__.py": ("custom_model", "CustomModel"),
    }

    for init_file, (module_name, class_name) in init_modules.items():
        init_file.write_text(f'''"""Módulo {init_file.parent.name} del proyecto.

Este módulo contiene las implementaciones personalizadas para {project_path.name}.
"""

from .{module_name} import {class_name}

__all__ = ["{class_name}"]
''')


def _create_base_files(project_path: Path, project_name: str):
    """Crea archivos base del proyecto."""
    # README.md
    readme_content = f"""# {project_name}

Proyecto de detección de fraude energético con Energizados Framework.

## Estructura del Proyecto

```
{project_name}/
├── etl/                    # ETL personalizado
│   ├── __init__.py
│   └── custom_etl.py       # Tu implementación de ETL
├── feature_selection/      # Selectores de features personalizados
│   ├── __init__.py
│   └── custom_selector.py  # Tu implementación de selector
├── models/                 # Modelos personalizados
│   ├── __init__.py
│   └── custom_model.py     # Tu implementación de modelo
├── configs/                # Configuraciones del pipeline
│   └── pipeline.yaml       # Configuración principal
├── data/                   # Datos del proyecto
│   ├── raw/               # Datos crudos
│   └── processed/         # Datos procesados
├── models/                 # Modelos entrenados
│   └── trained/           # Modelos guardados
└── reports/                # Reportes y resultados
```

## Uso

### Ejecutar el pipeline completo

```bash
energizados run --config configs/pipeline.yaml
```

### Ejecutar solo un paso específico

```bash
energizados run --config configs/pipeline.yaml --step etl
energizados run --config configs/pipeline.yaml --step training
```

### Ejecutar una ETL específica (con múltiples ETLs)

```bash
# Ejecutar una ETL y sus dependencias
energizados run --config configs/pipeline.yaml --etl merge_etl

# Ver plan de ejecución sin ejecutar
energizados run --config configs/pipeline.yaml --dry-run
```

### Validar configuración

```bash
energizados validate --config configs/pipeline.yaml
```

## Personalización

### 1. Personalizar ETL

Edita `etl/custom_etl.py` para implementar tu lógica de extracción,
transformación y carga de datos.

**Soporta múltiples fuentes de datos:**
- Archivo único: `input: "data/file.csv"`
- Múltiples archivos: `input: ["file1.csv", "file2.csv"]`
- Glob pattern: `input: "data/raw/*.csv"`
- Referencia a otra ETL: `input: "@otra_etl"`

### 2. Configurar Múltiples ETLs

Edita `configs/pipeline.yaml` y usa la sección `etls` en lugar de `etl`:

```yaml
etls:
  consumos:
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    depends_on: []

  merge:
    input:
      - "@consumos"
      - "data/raw/clientes.csv"
    output: "data/processed/merged.parquet"
    depends_on: ["consumos"]
```

### 3. Personalizar Feature Selection (opcional)

Edita `feature_selection/custom_selector.py` para implementar tu propia
lógica de selección de variables.

### 4. Personalizar Modelo

Edita `models/custom_model.py` para implementar tu propio modelo
de ML, heredando de `BaseModel`.

## Documentación

Para más información sobre el framework Energizados, visita:
https://github.com/yourusername/energizados
"""
    (project_path / "README.md").write_text(readme_content)

    # .gitignore
    gitignore_content = """# Energizados Project

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# Energizados specific
data/raw/*
!data/raw/.gitkeep
models/trained/*
!models/trained/.gitkeep
reports/*
!reports/.gitkeep

# Jupyter
.ipynb_checkpoints/

# OS
.DS_Store
Thumbs.db
"""
    (project_path / ".gitignore").write_text(gitignore_content)

    # Archivos .gitkeep para mantener directorios vacíos en git
    (project_path / "data" / "raw" / ".gitkeep").write_text("")
    (project_path / "models" / "trained" / ".gitkeep").write_text("")
    (project_path / "reports" / ".gitkeep").write_text("")


def _create_code_templates(project_path: Path, project_name: str):
    """Crea templates de código para personalización."""

    # ETL Template
    etl_template = f'''"""
ETL Personalizado para {project_name}.

Este módulo implementa la extracción, transformación y carga de datos
específica para este proyecto.

Edita los métodos extract(), transform() y load() según tus necesidades.
"""

from energizados.core.base import BaseETL
import pandas as pd


class CustomETL(BaseETL):
    """
    ETL personalizado para {project_name}.

    Hereda de BaseETL e implementa los métodos abstractos para definir
    el proceso específico de este proyecto.

    Soporta múltiples inputs (string o lista) según configuración YAML.
    """

    def __init__(self, input_paths: list = None, output_path: str = None, **kwargs):
        """
        Inicializa el ETL.

        Args:
            input_paths: Lista de rutas de archivos de entrada
            output_path: Ruta de salida para los datos transformados
            **kwargs: Parámetros adicionales desde la configuración
        """
        super().__init__(**kwargs)
        self.input_paths = input_paths or []
        self.output_path = output_path

    def extract(self) -> pd.DataFrame:
        """
        Extrae datos de la fuente.

        Edita este método para implementar tu lógica de extracción.
        Usa self.input_paths para acceder a los archivos configurados.

        Returns:
            pd.DataFrame: Datos crudos
        """
        # TODO: Implementar tu lógica de extracción
        # Ejemplo con un solo archivo:
        # if self.input_paths:
        #     return pd.read_csv(self.input_paths[0])

        # Ejemplo con múltiples archivos:
        # dfs = [pd.read_csv(f) for f in self.input_paths]
        # return pd.concat(dfs, axis=0)

        raise NotImplementedError("Implementa el método extract() en tu ETL")

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma y limpia los datos.

        Edita este método para implementar tu lógica de transformación.

        Args:
            df: DataFrame crudo

        Returns:
            pd.DataFrame: DataFrame limpio
        """
        # TODO: Implementar tu lógica de transformación
        # Ejemplo:
        # df = df.dropna()
        # df['fecha'] = pd.to_datetime(df['fecha'])
        # return df

        raise NotImplementedError("Implementa el método transform() en tu ETL")

    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Guarda los datos transformados.

        Por defecto guarda en formato parquet, pero puedes cambiarlo.

        Args:
            df: DataFrame transformado
            path: Ruta de salida
        """
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def run(self, output_path: str = None) -> pd.DataFrame:
        """
        Ejecuta el pipeline completo de ETL.

        Args:
            output_path: Ruta de salida (usa self.output_path si no se especifica)

        Returns:
            pd.DataFrame: DataFrame transformado
        """
        if output_path is None:
            output_path = self.output_path

        df = self.extract()
        df = self.transform(df)

        if output_path:
            self.load(df, output_path)

        return df
'''
    (project_path / "etl" / "custom_etl.py").write_text(etl_template)

    # Feature Selection Template
    selector_template = f'''"""
Selector de Features Personalizado para {project_name}.

Este módulo implementa la lógica de selección de variables
específica para este proyecto.

Edita los métodos fit() y transform() según tus necesidades.
"""

from energizados.preprocessing.feature_selection.base import BaseFeatureSelector
import pandas as pd


class CustomSelector(BaseFeatureSelector):
    """
    Selector de features personalizado para {project_name}.

    Hereda de BaseFeatureSelector e implementa los métodos abstractos
    para definir la lógica específica de este proyecto.
    """

    def __init__(self, config = None, **kwargs):
        """
        Inicializa el selector.

        Args:
            config: Diccionario de configuración (opcional)
            **kwargs: Parámetros adicionales desde la configuración YAML
        """
        super().__init__(config)
        # Agrega tus parámetros personalizados aquí
        # self.threshold = config.get('threshold', 0.01) if config else 0.01

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "CustomSelector":
        """
        Aprende qué variables seleccionar.

        Edita este método para implementar tu lógica de selección.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento

        Returns:
            self: Retorna la instancia entrenada
        """
        # TODO: Implementar tu lógica de selección
        # Ejemplo simple con varianza:
        # from sklearn.feature_selection import VarianceThreshold
        # selector = VarianceThreshold(threshold=0.01)
        # selector.fit(X)
        # self.selected_features_ = X.columns[selector.get_support()].tolist()

        # Ejemplo con correlación:
        # corr_matrix = X.corr().abs()
        # upper_triangle = corr_matrix.where(
        #     np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        # )
        # to_drop = [column for column in upper_triangle.columns if any(upper_triangle[column] > 0.95)]
        # self.selected_features_ = [col for col in X.columns if col not in to_drop]

        raise NotImplementedError("Implementa el método fit() en tu selector")

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforma X dejando solo las variables seleccionadas.

        Args:
            X: DataFrame a transformar

        Returns:
            pd.DataFrame: DataFrame con variables seleccionadas
        """
        if self.selected_features_ is None:
            raise ValueError("Debes llamar a fit() antes de transform()")

        return X[self.selected_features_]
'''
    (project_path / "feature_selection" / "custom_selector.py").write_text(selector_template)

    # Model Template
    model_template = f'''"""
Modelo Personalizado para {project_name}.

Este módulo implementa un modelo de ML
específico para este proyecto.

Edita los métodos fit(), predict() y predict_proba() según tus necesidades.
"""

from energizados.modeling.base import BaseModel
import pandas as pd
import numpy as np


class CustomModel(BaseModel):
    """
    Modelo personalizado para {project_name}.

    Hereda de BaseModel e implementa los métodos abstractos
    para definir la lógica específica de este proyecto.
    """

    def __init__(self, config = None, **kwargs):
        """
        Inicializa el modelo.

        Args:
            config: Diccionario de configuración (opcional)
            **kwargs: Parámetros adicionales desde la configuración YAML
        """
        super().__init__(config)
        # Agrega tus parámetros personalizados aquí
        # self.learning_rate = config.get('learning_rate', 0.01) if config else 0.01
        self.model_ = None
        self.is_fitted_ = False

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None
    ) -> "CustomModel":
        """
        Entrena el modelo.

        Edita este método para implementar tu lógica de entrenamiento.

        Args:
            X: Features de entrenamiento
            y: Target de entrenamiento
            X_val: Features de validación (opcional)
            y_val: Target de validación (opcional)

        Returns:
            self: Retorna la instancia entrenada
        """
        # TODO: Implementar tu lógica de entrenamiento
        # Ejemplo simple con scikit-learn:
        # from sklearn.ensemble import RandomForestClassifier
        # self.model_ = RandomForestClassifier(
        #     n_estimators=100,
        #     max_depth=10,
        #     random_state=42
        # )
        # self.model_.fit(X, y)
        # self.is_fitted_ = True

        raise NotImplementedError("Implementa el método fit() en tu modelo")

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones binarias.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Predicciones binarias (0 o 1)
        """
        self.check_fitted()

        # TODO: Implementar tu lógica de predicción
        # Ejemplo:
        # return self.model_.predict(X).astype(int)

        raise NotImplementedError("Implementa el método predict() en tu modelo")

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Realiza predicciones de probabilidad.

        Args:
            X: Features para predicción

        Returns:
            np.ndarray: Probabilidades de la clase positiva
        """
        self.check_fitted()

        # TODO: Implementar tu lógica de predicción de probabilidades
        # Ejemplo:
        # return self.model_.predict_proba(X)[:, 1]

        raise NotImplementedError("Implementa el método predict_proba() en tu modelo")
'''
    (project_path / "models" / "custom_model.py").write_text(model_template)


def _create_config_files(project_path: Path, project_name: str):
    """Crea archivos de configuración del proyecto."""

    # Leer template desde el framework
    import energizados

    # Ruta al template del framework
    template_path = Path(energizados.__file__).parent.parent.parent / "templates" / "pipeline.yaml.tpl"

    if template_path.exists():
        config_content = template_path.read_text()
        # Reemplazar variables
        config_content = config_content.replace("{{project_name}}", project_name)
    else:
        # Config por defecto si no existe template
        config_content = _get_default_config(project_name)

    (project_path / "configs" / "pipeline.yaml").write_text(config_content)


def _get_default_config(project_name: str) -> str:
    """Retorna la configuración por defecto."""
    return f"""# Energizados Pipeline Configuration for {project_name}
#
# Este archivo define el workflow completo de ML

project:
  name: "{project_name}"
  version: "1.0.0"

# ETL Step
etl:
  enabled: true
  output_path: "data/processed/dataset_limpio.parquet"

  # Usa implementación por defecto
  type: "default"

  # O usa tu propia implementación:
  # custom_class: "{project_name}.etl.custom_etl.CustomETL"
  # params:
  #   source_path: "data/raw/"

# Preprocessing Step
preprocessing:
  enabled: true
  input_path: "data/processed/dataset_limpio.parquet"
  output_path: "data/processed/dataset_preprocesado.parquet"

  preprocessor_num: 4
  categorical_features:
    - actividad
    - tipo_tarifa
    - nivel_tension
    - material_instalacion
    - zona

# Feature Selection Step
feature_selection:
  enabled: false  # true para habilitar

  # Usa método predefinido
  method: "boruta"  # boruta, correlation, constant
  params:
    n_estimators: 100
    max_iter: 100

  # O usa tu propio selector:
  # custom_class: "{project_name}.feature_selection.custom_selector.CustomSelector"
  # params:
  #   threshold: 0.01

# Training Step
training:
  model_type: "lightgbm"  # lightgbm, catboost, neural_network, lstm

  input_path: "data/processed/dataset_preprocesado.parquet"
  output_dir: "models/trained/"

  test_size: 0.2
  val_size: 0.1
  random_state: 42

  sampling:
    method: "under"  # over, under, none
    threshold: 0.5

  hyperparams:
    num_leaves: 31
    max_depth: -1
    learning_rate: 0.05
    n_estimators: 1000

  hyperparam_search:
    enabled: true
    n_iter: 60
    cv: 3

  # O usa tu propio modelo:
  # custom_class: "{project_name}.models.custom_model.CustomModel"
  # params:
  #   learning_rate: 0.01

# Evaluation Step
evaluation:
  enabled: true
  output_dir: "reports/"

  metrics:
    - auc
    - precision
    - recall
    - f1
    - confusion_matrix

  generate_plots: true
  generate_html_report: true
"""
