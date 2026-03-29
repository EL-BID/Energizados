# Infer Configuration for {{project_name}}
#
# This file configures inference and prediction
# using trained models.

infer:
  enabled: false  # Change to true to enable

  # Input/output paths
  input_path: "data/processed/feature_pipeline.parquet"
  output_path: "output/predictions.csv"

  # Model auto-detection (optional - if not specified, uses latest run)
  # Leave empty to auto-detect from output/train-YYYYMMDD_HHMM/
  # model_path: "output/train-YYYYMMDD_HHMM/models/model.pkl"
  # feature_engineering_path: "output/train-YYYYMMDD_HHMM/models/feature_engineering.pkl"

  # Base directory to search for latest training run (default: "output")
  # output_base_dir: "output"

  # ============================================================
  # Filtering Options (applied BEFORE feature engineering)
  # ============================================================

  # columns_filter: Filter rows by column values BEFORE expensive FE
  # Use this to filter by zona, region, etc. to avoid running
  # tsfel on records you don't need to score.
  # Example:
  #   columns_filter:
  #     zona: ["FLORIANOPOLIS", "PALHOCA"]
  #     nivel_tension: ["BT"]

  # contratos_list: Score only specific contracts from a list
  # Useful for targeted scoring campaigns.
  # Example:
  #   contratos_list:
  #     - 12345
  #     - 67890
  #     - 11111

  # ============================================================
  # Output Options
  # ============================================================

  # output_include_input: Append original input columns to output
  # (default: false)
  # output_include_input: true

  # output_columns: Select specific columns for output CSV
  # If not specified, outputs: prediction, probability
  # Example:
  #   output_columns:
  #     - cliente
  #     - actividad
  #     - zona
  #     - prediction
  #     - probability

  # output_format: "csv" or "parquet" (default: csv)
  # output_format: "csv"

  # Threshold for binary predictions
  threshold: 0.5

  # Inference type
  type: "default"

  # Or use your own inference implementation:
  # custom_class: "inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5
  #   batch_size: 1000
