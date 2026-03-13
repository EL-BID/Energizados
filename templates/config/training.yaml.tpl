# Training Configuration for .sample
#
# This file configures the full training workflow:
# 1. Split: Split data into train/val/test
# 2. Feature Engineering: Preprocessing and Feature Selection
# 3. Model: Model training
# 4. Evaluation: Evaluation of the trained model

training:
  enabled: true

  # Input from ETL
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"
  periods_suffix: &period_suffix "_anterior"

  # Output: each run generates output/train-YYYYMMDD_HHMM/
  # with subdirectories models/, reports/evaluation/ and config/.
  # output_base_dir: "output"  # optional override

  # ============================================
  # Split Configuration
  # ============================================
  split:
    method: "time_series"  # Options: stratified, random, time_series

    # For stratified/random methods:
    # test_size: 0.2
    # val_size: 0.1
    # random_state: 42

    # For time_series method:
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]  # [start, end] or just [start]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]

    # Save splits for reproducibility
    save_splits: true
    splits_dir: "data/splits/"

  # ============================================
  # Feature Engineering Configuration
  # ============================================
  feature_engineering:
    enabled: true
    output_pkl: "data/processed/feature_engineering.pkl"

    preprocessing:
      enabled: true
      output_parquet: "data/processed/preprocessing.parquet"

      drop_columns: [index, fecha_inspeccion]  # columns to exclude from model

      # Option 1: Use per-column configuration with built-in transformers
      columns:
        # actividad: reduce cardinality + one-hot encoding
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}
          #- cast_dtype:
          #    dtype: "category"

        # tipo_tarifa: reduce cardinality + target encoding
        tipo_tarifa:
          - cardinality_reducer:
              threshold: 0.001
          - target_encoding:
              w: 20
          #- cast_dtype:
          #    dtype: "category"

        # zona: simple ordinal encoding
        zona:
          - ordinal_encoding: {}
          #- cast_dtype:
          #    dtype: "category"

        # nivel_tension: simple ordinal encoding
        nivel_tension:
          - ordinal_encoding: {}
          #- cast_dtype:
          #    dtype: "category"

        # material_instalacion: direct target encoding
        material_instalacion:
          - target_encoding:
              w: 10
          #- cast_dtype:
          #    dtype: "category"

        # Option 2: Mix built-in and custom transformers on the same column
        # otra_columna:
        #   - cardinality_reducer:
        #       threshold: 0.01
        #   - custom_class: "mi_paquete.preprocessing.MiEncoder"
        #     params:
        #       method: "frequency"

      # Global transformers
      global_transformers:
        # Time series feature extraction with tsfel
        - tsfel_vars:
            num_periodos: 12
            features_names_path: null  # or path to JSON with custom configuration
            periods_suffix: *period_suffix
            n_jobs: -1        # -1 = all cores, 1 = sequential (default)
            chunk_size: 500   # rows per chunk per worker
            cache_dir: null   # e.g.: ".cache/tsfel" to cache on disk

        # Statistical features for different time windows
        - extra_vars:
            num_periodos: 3
            periods_suffix: *period_suffix
        - extra_vars:
            num_periodos: 6
            periods_suffix: *period_suffix
        - extra_vars:
            num_periodos: 12
            periods_suffix: *period_suffix

      #   # Option: Custom class for global transformers
      #   - custom_class: "preprocessing.CustomGlobalTransformer"
      #     params:
      #       custom_param: value

    feature_selection:
      enabled: true
      output_parquet: "data/processed/feature_selection.parquet"

      # List of sequential selection steps
      steps:
        - name: drop_constant
          method: constant          # constant | correlation | boruta | selection
          params:
            threshold: 0.99
          columns:
            - "*"
            - "!index"
            - "!*_anterior"
            - "!*zona*"
            - "!*actividad*"
            - "!*tipo_tarifa*"
            - "!*nivel_tension*"
            - "!*material_instalacion*"

      #   - name: boruta_consumo
      #     method: boruta
      #     params:
      #       n_estimators: 100
      #       max_iter: 100
      #     columns:
      #       - "*_anterior"          # Glob: 12_anterior, 11_anterior, ...
      #       - "!12_anterior"        # Exclude a specific one

      #   - name: corr_categoricas
      #     method: correlation
      #     params:
      #       threshold: 0.9
      #     columns:
      #       - "actividad_*"         # Glob: all actividad dummies
      #       - "tipo_tarifa"         # Literal
      #       - "re:^zona.*"          # Regex with re: prefix
      #       - "@drop_constant"      # Reference to previous step result
      #       - "!nivel_tension"      # Exclude

        - name: final
          method: selection
          operation: union          # union | intersection | difference
          columns:
            - "*_anterior"
            - "*zona*"
            - "*actividad*"
            - "*tipo_tarifa*"
            - "*nivel_tension*"
            - "*material_instalacion*"
            - "@drop_constant"

  # ============================================
  # Model Configuration
  # ============================================
  # Single model: one item in the list — evaluated directly (no ensemble)
  models:
    - type: "lightgbm"  # Options: lightgbm, catboost, neural_network, lstm

      # Class balancing
      sampling:
        method: "under"  # Options: over, under, none
        threshold: 0.5

      # Hyperparameters
      hyperparams:
        num_leaves: 31
        max_depth: -1
        learning_rate: 0.05
        n_estimators: 1000

      # Hyperparameter search
      hyperparam_search:
        enabled: true
        n_iter: 60
        cv: 3

  # ============================================
  # Ensemble Configuration (requires len(models) > 1)
  # ============================================
  # Uncomment both `models` and `ensemble` blocks below to enable ensemble.
  # When using ensemble, replace the `models` block above with the one below.

  # models:
  #   - name: "lgbm"
  #     type: "lightgbm"
  #     sampling: { method: "under", threshold: 0.5 }
  #     hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
  #     hyperparam_search: { enabled: false }
  #
  #   - name: "cat"
  #     type: "catboost"
  #     sampling: { method: "under", threshold: 0.5 }
  #     hyperparams: { iterations: 300 }
  #     hyperparam_search: { enabled: false }
  #
  # ensemble:
  #   method: "stacking"          # "stacking" | "soft_voting"
  #   meta_learner:
  #     type: "logistic_regression"   # default; could be "lightgbm", etc.
  #     params:
  #       C: 1.0
  #       max_iter: 1000
  #   use_val_as_oof: true        # true = blending (fast); false = proper CV OOF (expensive)
  #   cv: 5                       # used only when use_val_as_oof: false

  # Soft voting alternative:
  # ensemble:
  #   method: "soft_voting"
  #   weights: [0.6, 0.4]        # optional; null = equal weights

  # ============================================
  # Evaluation Configuration
  # ============================================
  evaluation:
    enabled: true
    # output_dir is managed automatically within the run directory
    threshold: 0.5  # Ignored if calibration.enabled=true

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

    # Automatic threshold calibration using validation set
    # The optimal threshold is found on val and applied on test
    # calibration:
    #   enabled: true
    #   method: "cost_benefit"   # Options: cost_benefit | operational | precision_recall
    #   params:
    #     # For cost_benefit (minimizes total FP/FN cost):
    #     cost_fp: 1    # cost of inspecting a legitimate user
    #     cost_fn: 10   # cost of missing a fraud
    #     # For operational (fixes number of alerts):
    #     # capacity: 200   # maximum alerts per period
    #     # For precision_recall (guaranteed minimum recall):
    #     # min_recall: 0.80
