# Energizados Pipeline Configuration for {{project_name}}
#
# Este archivo define el workflow completo de ML para detección de fraude
#
# Soporta dos formatos para ETL:
# 1. ETL único (simple): usa la sección 'etl'
# 2. Múltiples ETLs con dependencias: usa la sección 'etls' (comentar 'etl' y descomentar 'etls')

project:
  name: "{{project_name}}"
  version: "1.0.0"

# ============================================
# Opción 1: ETL Único (Simple)
# ============================================
etl:
  enabled: true
  output_path: "data/processed/dataset_limpio.parquet"

  # Usa implementación por defecto del framework
  type: "default"

  # O usa tu propia implementación:
  # custom_class: "{{project_name}}.etl.custom_etl.CustomETL"
  # params:
  #   source_path: "data/raw/"

# ============================================
# Opción 2: Múltiples ETLs con Dependencias
# ============================================
# etls:
#   # ETL 1: Consumos - No tiene dependencias
#   consumos:
#     enabled: true
#     description: "Procesa datos de consumo mensual"
#
#     # Input: puede ser un archivo, lista, glob, o referencia (@etl_name)
#     input: "data/raw/consumos.csv"
#
#     # Salida
#     output: "data/processed/consumos.parquet"
#
#     # Dependencias (vacío = ETL raíz)
#     depends_on: []
#
#   # ETL 2: Clientes - No tiene dependencias
#   clientes:
#     enabled: true
#     description: "Procesa datos de clientes"
#
#     input: "data/raw/clientes.csv"
#     output: "data/processed/clientes.parquet"
#     depends_on: []
#
#   # ETL 3: Merge - Depende de consumos y clientes
#   # Input puede ser múltiples archivos
#   merge_dataset:
#     enabled: true
#     description: "Combina consumos y clientes"
#
#     input:
#       - "data/processed/consumos.parquet"
#       - "data/processed/clientes.parquet"
#
#     output: "data/processed/dataset_limpio.parquet"
#
#     # Dependencias de otras ETLs
#     depends_on:
#       - "consumos"
#       - "clientes"
#
#     # Custom ETL para merge (opcional)
#     # custom_class: "{{project_name}}.etl.MergeETL"
#     # params:
#     #   merge_key: "id_cliente"
#
#   # ETL 4: Ejemplo usando referencia a otra ETL
#   enriquecido:
#     enabled: false
#     description: "Dataset enriquecido"
#
#     # Usar referencia @etl_name en lugar de path hardcoded
#     input:
#       - "@merge_dataset"  # Se resuelve al output de merge_dataset
#
#     output: "data/processed/dataset_final.parquet"
#     depends_on:
#       - "merge_dataset"
#
#   # ETL 5: Ejemplo usando glob para múltiples archivos
#   batch_process:
#     enabled: false
#     description: "Procesa múltiples CSVs"
#
#     # Glob para capturar múltiples archivos
#     input: "data/raw/*.csv"
#
#     output: "data/processed/batch.parquet"
#     depends_on: []

# ============================================
# Preprocessing Step - Preprocesamiento de datos
# ============================================
preprocessing:
  enabled: true
  input_path: "data/processed/dataset_limpio.parquet"
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
  # custom_class: "{{project_name}}.feature_selection.custom_selector.CustomSelector"
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
  # custom_class: "{{project_name}}.models.custom_model.CustomModel"
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
  # custom_class: "{{project_name}}.inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5

