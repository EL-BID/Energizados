# Infer Configuration for {{project_name}}
#
# Optionally combines two phases in one file:
#   1. etl   — builds the inference dataset (no target) from processed parquets
#   2. infer — scores with the trained model and produces predictions
#
# Usage:
#   energizados run infer                   # both phases (if etl section is present)
#   energizados run infer --step etl        # dataset only
#   energizados run infer --step infer      # predictions only (dataset must exist)
#
# If you don't need a custom inference ETL, remove the etl: section below
# and point input_path directly to your processed dataset.

# ============================================================
# Optional: Inference ETL (builds the dataset to score)
# ============================================================
# Uncomment and configure if you need to build the inference dataset
# from raw/processed sources before scoring.
#
# etl:
#   schema_version: 1
#
#   inference_dataset:
#     enabled: true
#     description: "Inference dataset: no target, windowed by start_period/end_period"
#     input:
#       - "data/processed/dataset.parquet"   # or multiple sources
#     output: "data/processed/dataset_infer.parquet"
#     custom_class: "data.inference_dataset_builder_etl.InferenceDatasetBuilderETL"
#     params:
#       start_period: "202401"   # YYYYMM — first period for active client filter
#       end_period: "202412"     # YYYYMM — last period included (window anchor)
#       min_num_measures_not_zero: 3
#       remove_constant_series: true
#     depends_on: []

infer:
  schema_version: 1
  enabled: true

  # Input/output paths
  input_path: "data/processed/dataset_infer.parquet"
  output_path: "output/predictions.csv"

  # Point to the training run to use:
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
  #
  # Syntax options:
  #   1. Simple equality (list):    zona: ["FLORIANOPOLIS", "PALHOCA"]
  #   2. Operators:                 consumo_1_anterior: {">": 0, "<=": 10000}
  #                                  fecha_inspeccion: {">=": "2026-01-01", "!=": null}
  #                                  actividad: {like: "INDUSTRI"}
  #   3. Pandas expression:         _expr: "(zona == 'FLORIANOPOLIS') & (consumo_1 > 500)"
  #
  # Available operators: >, <, >=, <=, !=, ==, like
  #
  # Example:
  #   columns_filter:
  #     zona: ["FLORIANOPOLIS", "PALHOCA"]
  #     nivel_tension: ["BT"]
  #     consumo_1_anterior:
  #       ">": 0
  #       "<=": 10000
  #     _expr: "(zona == 'FLORIANOPOLIS') & (consumo_1_anterior > 500)"

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

  # -----------------------------------------------------------
  # OPTIONAL: Per-Segment Thresholds (NEW in mejoras-3)
  # -----------------------------------------------------------
  # Apply different thresholds per segment (e.g., per region) instead of
  # a single global threshold. Requires segment_thresholds.json from evaluation.
  #
  # segment_thresholds:
  #   enabled: true
  #   path: "output/train-YYYYMMDD_HHMM/reports/evaluation/segment_thresholds_zona.json"
  #   fallback_threshold: 0.5         # threshold for unknown segments (null = use global)

  # -----------------------------------------------------------
  # OPTIONAL: Business Rules (NEW in v4)
  # -----------------------------------------------------------
  # Apply business rules to predictions AFTER segment_thresholds. Rules
  # evaluate pandas expressions against the RAW pre-FE data and modify
  # probabilities (score_boost / override) or just flag rows for analysis.
  #
  # Common use case: regions where the model has AUC<0.5 — the model score
  # is unreliable, so deterministic rules (consumption zero, abrupt drop)
  # provide an overlay. The operation uses these flags downstream.
  #
  # business_rules:
  #   enabled: true
  #   apply_to:
  #     column: "geo_region"           # column to filter on (default: geo_region)
  #     regions:                       # only these regions are eligible for rules
  #       - "REGION_A"
  #       - "REGION_B"
  #   rules:
  #     - name: "consumo_cero_3m"
  #       condition: "(`3_anterior` == 0) & (`2_anterior` == 0) & (`1_anterior` == 0)"
  #       action: "override"           # flag | override | score_boost
  #       value: 1.0                   # for score_boost: amount to add (clipped [0,1])
  #     - name: "caida_abrupta"
  #       condition: "(`1_anterior` * 11) < 0.4 * (`12_anterior` + `11_anterior` + `10_anterior` + `9_anterior` + `8_anterior` + `7_anterior` + `6_anterior` + `5_anterior` + `4_anterior` + `3_anterior` + `2_anterior`)"
  #       action: "score_boost"
  #       value: 0.3
  #     - name: "denuncia_sac"         # stub: never triggers until data arrives
  #       condition: "False"
  #       action: "flag"
  #   output:
  #     add_rule_columns: true         # add rule_<name> (bool) + rule_<name>_value (float)

  # Inference type
  type: "default"

  # Or use your own inference implementation:
  # custom_class: "inference.custom_inference.CustomInference"
  # params:
  #   threshold: 0.5
  #   batch_size: 1000
