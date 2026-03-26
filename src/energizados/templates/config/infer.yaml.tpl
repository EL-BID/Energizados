# Infer Configuration for {{project_name}}
#
# This file configures inference and prediction
# using trained models.

infer:
  enabled: false  # Change to true to enable

  # Input/output paths
  input_path: "data/processed/feature_pipeline.parquet"
  output_path: "output/predictions.csv"

  # Point to the latest training run:
  # model_path: "output/train-YYYYMMDD_HHMM/models/model.pkl"
  # feature_engineering_path: "output/train-YYYYMMDD_HHMM/models/feature_engineering.pkl"

  # Threshold for binary predictions
  threshold: 0.5

  # Inference type
  type: "default"

  # Or use your own inference implementation:
  # custom_class: "inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5
  #   batch_size: 1000
