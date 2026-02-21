# Energizados Pipeline Configuration for {{project_name}}
#
# Este archivo define el workflow completo de ML para detección de fraude
#
# El pipeline usa múltiples ETLs con dependencias.

project:
  name: "{{project_name}}"
  version: "1.0.0"

# ============================================
# Múltiples ETLs con Dependencias
# ============================================
etls:
  # ETL "sample" - Procesa el dataset de ejemplo incluido
  sample:
    enabled: true
    description: "Procesa dataset de ejemplo (elimina filas con NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: []

  # ============================================
  # EJEMPLOS ADICIONALES (comentados)
  # ============================================
  # Descomenta y adapta según tus necesidades
  #
  # # ETL 1: Consumos - No tiene dependencias
  # consumos:
  #   enabled: false
  #   description: "Procesa datos de consumo mensual"
  #   input: "data/raw/consumos.csv"
  #   output: "data/processed/consumos.parquet"
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   depends_on: []
  #
  # # ETL 2: Clientes - No tiene dependencias
  # clientes:
  #   enabled: false
  #   description: "Procesa datos de clientes"
  #   input: "data/raw/clientes.csv"
  #   output: "data/processed/clientes.parquet"
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   depends_on: []
  #
  # # ETL 3: Merge - Depende de consumos y clientes
  # # Input puede ser múltiples archivos
  # merge_dataset:
  #   enabled: false
  #   description: "Combina consumos y clientes"
  #   input:
  #     - "data/processed/consumos.parquet"
  #     - "data/processed/clientes.parquet"
  #   output: "data/processed/dataset_limpio.parquet"
  #   custom_class: "energizados.etl.pipeline.MultiSourceETL"
  #   # Dependencias de otras ETLs
  #   depends_on:
  #     - "consumos"
  #     - "clientes"
  #
  # # ETL 4: Ejemplo usando referencia a otra ETL
  # enriquecido:
  #   enabled: false
  #   description: "Dataset enriquecido"
  #   # Usar referencia @etl_name en lugar de path hardcoded
  #   input:
  #     - "@merge_dataset"  # Se resuelve al output de merge_dataset
  #   output: "data/processed/dataset_final.parquet"
  #   custom_class: "energizados.etl.pipeline.MultiSourceETL"
  #   depends_on:
  #     - "merge_dataset"
  #
  # # ETL 5: Ejemplo usando glob para múltiples archivos
  # batch_process:
  #   enabled: false
  #   description: "Procesa múltiples CSVs"
  #   # Glob para capturar múltiples archivos
  #   input: "data/raw/*.csv"
  #   output: "data/processed/batch.parquet"
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   depends_on: []

# ============================================
# Preprocessing Step - Preprocesamiento de datos
# ============================================
preprocessing:
  enabled: true
  input_path: "data/processed/sample_dataset.parquet"
  output_path: "data/processed/dataset_preprocesado.parquet"

  # Número de preprocesador a usar (según configuración del framework)
  preprocessor_num: 4

  # Features categóricas a procesar
  categorical_features:
    - actividad
    - tipo_tarifa
    - nivel_tension
    - material_instalacion
    - zona

# ============================================
# Feature Selection Step - Selección de variables
# ============================================
feature_selection:
  enabled: false  # Cambiar a true para habilitar

  # Usa método predefinido del framework
  method: "boruta"  # Opciones: boruta, correlation, constant
  params:
    n_estimators: 100
    max_iter: 100

  # O usa tu propio selector:
  # custom_class: "{{project_name}}.src.features.custom_selector.CustomSelector"
  # params:
  #   threshold: 0.01

# ============================================
# Training Step - Entrenamiento del modelo
# ============================================
training:
  # Tipo de modelo a usar
  model_type: "lightgbm"  # Opciones: lightgbm, catboost, neural_network, lstm

  # Rutas de entrada/salida
  input_path: "data/processed/dataset_preprocesado.parquet"
  output_dir: "models/trained/"

  # Partición de datos
  test_size: 0.2
  val_size: 0.1
  random_state: 42

  # Balanceo de clases
  sampling:
    method: "under"  # Opciones: over, under, none
    threshold: 0.5

  # Hiperparámetros del modelo
  hyperparams:
    num_leaves: 31
    max_depth: -1
    learning_rate: 0.05
    n_estimators: 1000

  # Búsqueda de hiperparámetros
  hyperparam_search:
    enabled: true
    n_iter: 60
    cv: 3

  # O usa tu propio modelo:
  # custom_class: "{{project_name}}.src.models.custom_model.CustomModel"
  # params:
  #   learning_rate: 0.01

# ============================================
# Evaluation Step - Evaluación del modelo
# ============================================
evaluation:
  enabled: true
  output_dir: "reports/"

  # Métricas a calcular
  metrics:
    - auc
    - precision
    - recall
    - f1
    - confusion_matrix
    - cumulative_gains

  # Generar visualizaciones y reportes
  generate_plots: true
  generate_html_report: true

# ============================================
# Inference Step - Inferencia y predicciones
# ============================================
inference:
  enabled: false  # Cambiar a true para habilitar
  input_path: "data/processed/dataset_preprocesado.parquet"
  output_path: "reports/predictions.csv"

  # Umbral para predicciones binarias
  threshold: 0.5

  # Usa implementación por defecto
  type: "default"

  # O usa tu propia implementación:
  # custom_class: "{{project_name}}.src.inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5

