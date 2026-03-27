# Train Configuration for .sample
#
# This file configures the full training workflow:
# 1. Split: Split data into train/val/test
# 2. Feature Engineering: Preprocessing and Feature Selection
# 3. Model: Model training
# 4. Evaluation: Evaluation of the trained model

train:
  enabled: true

  description: |
    This experiment allows.

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
    method: "time_series"  # Options: stratified, random, time_series, group_based, stratified_time

    # For stratified/random methods:
    # test_size: 0.2
    # val_size: 0.1
    # random_state: 42

    # For time_series method:
    date_column: "fecha_inspeccion"
    train_period: ["2010-01-01", "2017-08-01"]  # [start, end] or just [start]
    val_period: ["2017-09-01", "2017-12-31"]
    test_period: ["2018-01-01"]

    # For group_based method (prevents data leakage by keeping all rows
    # with the same group value in the same split):
    # group_column: "customer_id"  # Column to group by (required for group_based)
    # Note: Proportions apply at group level, not row level

    # For stratified_time method (temporal split within each geographic cluster):
    # Ensures all clusters appear in train/val/test while preserving temporal order.
    # Requires GeoClusterETL to have been run first (generates the geo_cluster column).
    # method: "stratified_time"
    # date_column: "fecha_inspeccion"
    # cluster_column: "geo_cluster"
    # test_size: 0.15
    # val_size: 0.15
    # input_path: "data/processed/sample_dataset_with_clusters.parquet"

    # Save splits for reproducibility
    save_splits: true
    splits_dir: "data/splits/"

  # ============================================
  # Feature Engineering Configuration
  # ============================================
  feature_engineering:
    enabled: true

    preprocessing:
      enabled: true
      output_parquet: "data/processed/feat/preprocessing.parquet"

      drop_columns: [index]  # columns to exclude from model

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
        # Clip extreme consumption values (data reading errors)
        # Should run BEFORE other global transformers to clean input data
        # - clip_outliers:
        #     threshold: 100000          # values above this are clipped
        #     periods_suffix: *period_suffix  # auto-detects columns matching *_anterior

        # Time series feature extraction with tsfel
        # Specify features inline (recommended) or omit to use all domains.
        # When omitted, generated feature names are logged at INFO level for copy-paste.
        # - tsfel_vars:
        #     num_periodos: 12
        #     features:                   # optional: inline feature selection
        #       statistical:
        #         - Mean
        #         - Standard deviation
        #         - Max
        #         - Min
        #         - Median
        #         - Skewness
        #         - Kurtosis
        #         - Mean absolute deviation
        #       temporal:
        #         - Autocorrelation
        #         - Mean absolute diff
        #         - Median absolute diff
        #         - Slope
        #         - Zero crossing rate
        #     periods_suffix: *period_suffix
        #     n_jobs: -1        # -1 = all cores, 1 = sequential (default)
        #     chunk_size: 500   # rows per chunk per worker
        #     cache_dir: null   # e.g.: ".cache/tsfel" to cache on disk

        # Statistical features for different time windows
        # - extra_vars:
        #     num_periodos: 3
        #     periods_suffix: *period_suffix
        # - extra_vars:
        #     num_periodos: 6
        #     periods_suffix: *period_suffix
        # - extra_vars:
        #     num_periodos: 12
        #     periods_suffix: *period_suffix

        # Domain-specific consumption patterns for fraud detection
        # - consumption_patterns:
        #     num_periodos: 12
        #     periods_suffix: *period_suffix

        # Geographic features from lat/lon (uses IBGE shapefiles via geobr)
        # Generates: geo_estado, geo_municipio, geo_regiao + target encoding + distances
        # Available distance_cities: sao_paulo, rio_de_janeiro, brasilia, salvador,
        #   belo_horizonte, fortaleza, recife, curitiba, manaus, porto_alegre,
        #   florianopolis, blumenau, joinville, criciuma, chapeco, itajai, lages
        # - geo_features:
        #     lat_col: "latitud"
        #     lon_col: "longitud"
        #     include_hierarchy: true       # geo_estado, geo_municipio, geo_regiao
        #     include_target_encoding: true # target-encoded versions of hierarchy cols
        #     te_w: 20                      # smoothing weight for target encoding
        #     include_distances: true       # distances to reference cities
        #     distance_cities:
        #       - sao_paulo
        #       - rio_de_janeiro
        #       - brasilia
        #     include_coords: false         # keep lat/lon in output
        #     cache_dir: ".cache/ibge"      # persist IBGE shapefiles to disk (avoids re-download)

      #   # Option: Custom class for global transformers
      #   - custom_class: "preprocessing.CustomGlobalTransformer"
      #     params:
      #       custom_param: value

    feature_selection:
      enabled: true
      output_parquet: "data/processed/feat/feature_selection.parquet"

      # List of sequential selection steps
      steps:
        - name: drop_constant
          method: constant          # constant | correlation | boruta | mutual_info | categorical | selection
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

      #   - name: solo_categoricas
      #     method: categorical
      #     # params:
      #     #   include_object: true   # include dtype 'object' (default: true)
      #     #   include_category: true # include dtype 'category' (default: true)
      #     columns:
      #       - "*"

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
  # Available model types:
  #   - lightgbm: Gradient Boosting (requires preprocessing)
  #   - catboost: CatBoost (requires preprocessing)
  #   - neural_network / nn: Feedforward Neural Network (requires preprocessing)
  #   - lstm: LSTM Neural Network for sequential data (requires preprocessing)
  #   - simple_trend: Rule-based trend detector (uses raw consumption data)
  #   - simple_constant: Rule-based constant consumption detector (uses raw consumption data)
  models:
    - type: "lightgbm"  # Options: lightgbm, catboost, neural_network, lstm, simple_trend, simple_constant

      # Class balancing: choose ONE of sampling or class_weight
      # Option 1: Sampling (resamples the data)
      sampling:
        method: "undersample"  # Options: oversample, undersample, smotetomek, none
        threshold: 0.5

      # Option 2: Class weights (balances via internal model weights)
      # Use "balanced" for auto-computed weights, or specify manually
      # class_weight: "balanced"  # Options: "balanced", null, or dict like {0: 1, 1: 10}

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

      # Probability calibration (FR-EVAL-016)
      # Adjust raw model scores to reflect true frequencies
      # calibration:
      #   enabled: true
      #   method: "sigmoid"   # Options: "sigmoid" (Platt scaling), "isotonic"
      #   cv: 3               # CV folds for calibration (used if not 'prefit')

  # ============================================
  # Model Examples (commented)
  # ============================================
  # Uncomment ONE of the following model blocks and replace the models section above

  # ----- Example: CatBoost -----
  # models:
  #   - type: "catboost"
  #     sampling:
  #       method: "undersample"
  #       threshold: 0.5
  #     hyperparams:
  #       iterations: 500
  #       learning_rate: 0.05
  #       depth: 6

  # ----- Example: Neural Network (Feedforward) -----
  # models:
  #   - type: "neural_network"
  #     sampling:
  #       method: "smotetomek"
  #       threshold: 0.5

  # ----- Example: LSTM (for sequential consumption data) -----
  # models:
  #   - type: "lstm"
  #     sampling:
  #       method: "smotetomek"
  #       threshold: 0.5

  # ----- Example: Simple Trend (rule-based, no ML) -----
  # Uses raw consumption columns, does NOT require preprocessing
  # models:
  #   - type: "simple_trend"
  #     threshold: 50              # % drop to flag as fraud
  #     last_base_value: 6         # periods for baseline
  #     last_eval_value: 3         # periods for evaluation

  # ----- Example: Simple Constant (rule-based, no ML) -----
  # Uses raw consumption columns, does NOT require preprocessing
  # models:
  #   - type: "simple_constant"
  #     min_count_constante: 3     # consecutive equal values to flag

  # ============================================
  # Comparison Mode (NEW - multiple models, no ensemble)
  # ============================================
  # Uncomment the block below to enable comparison mode.
  # Each model is trained independently and gets its own evaluation report.
  # A comparative report is generated at the end.

  # models:
  #   - name: "lgbm"
  #     type: "lightgbm"
  #     sampling: { method: "undersample", threshold: 0.5 }
  #     hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
  #     hyperparam_search: { enabled: false }
  #
  #   - name: "cat"
  #     type: "catboost"
  #     sampling: { method: "undersample", threshold: 0.5 }
  #     hyperparams: { iterations: 300 }
  #     hyperparam_search: { enabled: false }
  #
  # # NO ensemble: section → comparison mode (each model evaluated independently)

  # ============================================
  # Ensemble Configuration (requires len(models) > 1)
  # ============================================
  # Uncomment both `models` and `ensemble` blocks below to enable ensemble.
  # When using ensemble, replace the `models` block above with the one below.

  # models:
  #   - name: "lgbm"
  #     type: "lightgbm"
  #     sampling: { method: "undersample", threshold: 0.5 }
  #     hyperparams: { num_leaves: 31, learning_rate: 0.05, n_estimators: 500 }
  #     hyperparam_search: { enabled: false }
  #
  #   - name: "cat"
  #     type: "catboost"
  #     sampling: { method: "undersample", threshold: 0.5 }
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

    # SHAP model explainability (feature importance and attribution)
    # shap:
    #   enabled: true
    #   max_samples: 500      # Max samples for SHAP computation (controls compute time)
    #   top_n_features: 20    # Number of top features in SHAP plots
    #   plot_types: [summary, bar]  # Plot types: summary (beeswarm) and/or bar (importance)
