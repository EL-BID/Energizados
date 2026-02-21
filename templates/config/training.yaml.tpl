# Training Configuration for {{project_name}}
#
# Este archivo configura el entrenamiento de modelos de ML
# para detección de fraude en consumo energético.

training:
  # Tipo de modelo a usar
  model_type: "lightgbm"  # Opciones: lightgbm, catboost, neural_network, lstm

  # Rutas de entrada/salida
  input_path: "data/processed/feature_pipeline.parquet"
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

  # O usa tu propio modelo personalizado:
  # custom_class: "{{project_name}}.models.custom_model.CustomModel"
  # params:
  #   learning_rate: 0.01
  #   epochs: 1000

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
