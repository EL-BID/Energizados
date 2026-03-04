# Inference Configuration for {{project_name}}
#
# Este archivo configura la inferencia y predicción
# utilizando modelos entrenados.

inference:
  enabled: false  # Cambiar a true para habilitar

  # Rutas de entrada/salida
  input_path: "data/processed/feature_pipeline.parquet"
  output_path: "output/predictions.csv"

  # Apuntar al último run de entrenamiento:
  # model_path: "output/train-YYYYMMDD_HHMM/models/model.pkl"
  # feature_engineering_path: "output/train-YYYYMMDD_HHMM/models/feature_engineering.pkl"

  # Umbral para predicciones binarias
  threshold: 0.5

  # Tipo de inferencia
  type: "default"

  # O usa tu propia implementación de inferencia:
  # custom_class: "inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5
  #   batch_size: 1000
