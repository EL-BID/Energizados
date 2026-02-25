# Training Configuration for {{project_name}}
#
# Este archivo configura el flujo completo de entrenamiento:
# 1. Split: División de datos en train/val/test
# 2. Feature Engineering: Preprocessing y Feature Selection
# 3. Model: Entrenamiento del modelo
# 4. Evaluation: Evaluación del modelo entrenado
#
# El flujo previene data leakage: fit solo en train, transform en val/test

training:
  enabled: true

  # Input desde ETL
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"

  # Output
  output_dir: "models/trained/"

  # ============================================
  # Split Configuration
  # ============================================
  split:
method: "time_series"  # Opciones: stratified, random, time_series

    # Para métodos stratified/random:
    test_size: 0.2
    val_size: 0.1
    random_state: 42

    # Para método time_series:
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]  # [start, end] o solo [start]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]

    # Guardar splits para reproducibilidad
    save_splits: true
    splits_dir: "data/splits/"

  # ============================================
  # Feature Engineering Configuration
  # ============================================
  feature_engineering:
    enabled: true
    output_pkl: "data/processed/feature_engineering.pkl"
    output_parquet: "data/processed/feature_engineering.parquet"  # opcional

    preprocessing:
      enabled: true

      # Opción 1: Usar configuración por columna (formato actual)
      columns:
        # Actividad: reducir cardinalidad + one-hot encoding
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}

        # Tipo Tarifa: reducir cardinalidad + target encoding
        tipo_tarifa:
          - cardinality_reducer:
              threshold: 0.001
          - target_encoding:
              w: 20

        # Zona: encoding ordinal simple
        zona:
          - ordinal_encoding: {}

        # Nivel Tensión: encoding ordinal simple
        nivel_tension:
          - ordinal_encoding: {}

        # Material Instalación: target encoding directo
        material_instalacion:
          - target_encoding:
              w: 10

    feature_selection:
      enabled: false
      method: "boruta"  # Opciones: boruta, correlation, constant
      params:
        n_estimators: 100
        max_iter: 100

  # ============================================
  # Model Configuration
  # ============================================
  model:
    type: "lightgbm"  # Opciones: lightgbm, catboost, neural_network, lstm

    # Balanceo de clases
    sampling:
      method: "under"  # Opciones: over, under, none
      threshold: 0.5

    # Hiperparámetros
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

  # ============================================
  # Evaluation Configuration
  # ============================================
  evaluation:
    enabled: true
    output_dir: "reports/evaluation/"
    threshold: 0.5

    metrics:
      - auc
      - precision
      - recall
      - f1
      - confusion_matrix
      - cumulative_gains

    generate_plots: true
    generate_html_report: true
    generate_json_report: true

# ============================================
# Uso de clases personalizadas
# ============================================
# Para usar tu propio Preprocesador (solo reemplaza preprocessing, NO feature_engineering completo):
# training:
#   feature_engineering:
#     preprocessing:
#       enabled: true
#       custom_class: "preprocessing.custom_preprocessor.CustomPreprocessor"
#       params:
#         threshold: 0.5
#
# Para usar tu propio Feature Engineering (completo):
# training:
#   feature_engineering:
#     custom_class: "features.custom_selector.CustomSelector"
#     params:
#       custom_param: value
#
# Para usar tu propio Modelo:
# training:
#   model:
#     custom_class: "models.custom_model.CustomModel"
#     params:
#       learning_rate: 0.01
#       epochs: 1000
