# Training Configuration for .sample
#
# Este archivo configura el flujo completo de entrenamiento:
# 1. Split: División de datos en train/val/test
# 2. Feature Engineering: Preprocessing y Feature Selection
# 3. Model: Entrenamiento del modelo
# 4. Evaluation: Evaluación del modelo entrenado

training:
  enabled: true

  # Input desde ETL
  input_path: "data/processed/sample_dataset.parquet"
  target_column: "target"
  periods_suffix: &period_suffix "_anterior"

  # Output
  output_dir: "models/trained/"

  # ============================================
  # Split Configuration
  # ============================================
  split:
    method: "time_series"  # Opciones: stratified, random, time_series

    # Para métodos stratified/random:
    # test_size: 0.2
    # val_size: 0.1
    # random_state: 42

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

    preprocessing:
      enabled: true
      # output_parquet: "data/processed/preprocessing.parquet"  # opcional

      # Opción 1: Usar configuración por columna con transformers built-in
      columns:
        # Actividad: reducir cardinalidad + one-hot encoding
        actividad:
          - cardinality_reducer:
              threshold: 0.001
          - to_dummy: {}
        #  - cast_dtype:
        #      dtype: "category"

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

        # Opción 2: Mezclar built-in y custom en la misma columna
        # otra_columna:
        #   - cardinality_reducer:
        #       threshold: 0.01
        #   - custom_class: "mi_paquete.preprocessing.MiEncoder"
        #     params:
        #       method: "frequency"

      # Transformers globales
      global_transformers:
        # Extracción de features de series temporales con tsfel
        - tsfel_vars:
            num_periodos: 12
            features_names_path: null  # o path a JSON con configuración custom
            periods_suffix: *period_suffix
            n_jobs: -1        # -1 = todos los cores, 1 = secuencial (default)
            chunk_size: 500   # filas por chunk por worker
            cache_dir: null   # ej: ".cache/tsfel" para cachear en disco

        # Variables estadísticas para diferentes ventanas de tiempo
        - extra_vars:
            num_periodos: 3
            periods_suffix: *period_suffix
        - extra_vars:
            num_periodos: 6
            periods_suffix: *period_suffix
        - extra_vars:
            num_periodos: 12
            periods_suffix: *period_suffix

      #   # Opción: Custom class para transformers globales
      #   - custom_class: "preprocessing.CustomGlobalTransformer"
      #     params:
      #       custom_param: value

    feature_selection:
      enabled: true
      # output_parquet: "data/processed/feature_selection.parquet"  # opcional

      # Lista de pasos secuenciales de selección
      steps:
        - name: drop_constant
          method: constant          # constant | correlation | boruta | selection
          params:
            threshold: 0.99
          columns:
            - "*"
            - "!index"
            - "!*_anterior"

      #   - name: boruta_consumo
      #     method: boruta
      #     params:
      #       n_estimators: 100
      #       max_iter: 100
      #     columns:
      #       - "*_anterior"          # Glob: 12_anterior, 11_anterior, ...
      #       - "!12_anterior"        # Excluir una específica

      #   - name: corr_categoricas
      #     method: correlation
      #     params:
      #       threshold: 0.9
      #     columns:
      #       - "actividad_*"         # Glob: todas las dummies de actividad
      #       - "tipo_tarifa"         # Literal
      #       - "re:^zona.*"          # Regex con prefijo re:
      #       - "@drop_constant"      # Referencia a resultado de paso anterior
      #       - "!nivel_tension"      # Excluir

        - name: final
          method: selection
          operation: union          # union | intersection | difference
          columns:
            - "*_anterior"
            - "zona"
            - "actividad"
            - "tipo_tarifa"
            - "nivel_tension"
            - "material_instalacion"
            - "@drop_constant"

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
    threshold: 0.5  # Ignorado si calibration.enabled=true

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

    # Calibración automática del threshold usando validation set
    # El threshold óptimo se busca en val y se aplica sobre test
    # calibration:
    #   enabled: true
    #   method: "cost_benefit"   # Opciones: cost_benefit | operational | precision_recall
    #   params:
    #     # Para cost_benefit (minimiza costo total FP/FN):
    #     cost_fp: 1    # costo de inspeccionar un usuario legítimo
    #     cost_fn: 10   # costo de no detectar un fraude
    #     # Para operational (fija cantidad de alarmas):
    #     # capacity: 200   # alarmas máximas por período
    #     # Para precision_recall (recall mínimo garantizado):
    #     # min_recall: 0.80
