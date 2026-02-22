# Feature Pipeline Configuration for {{project_name}}
#
# Este archivo configura el paso de Feature Pipeline que combina
# preprocessing y feature_selection en un solo paso unificado.

feature_pipeline:
  enabled: true

  # Input/Output paths
  input_path: "data/processed/sample_dataset.parquet"
  output_pkl: "data/processed/feature_pipeline.pkl"
  output_parquet: "data/processed/feature_pipeline.parquet"  # Opcional, guardar datos transformados

  # Configuración de Preprocessing
  preprocessing:
    # Número de preprocesador a usar (1-4)
    # 4: Preprocesador completo con target encoding y dummy variables
    preprocessor_num: 4

    # Lista de features categóricas a procesar
    categorical_features:
      - actividad
      - tipo_tarifa
      - nivel_tension
      - material_instalacion
      - zona

  # Configuración de Feature Selection (opcional)
  feature_selection:
    enabled: true  # Cambiar a false para deshabilitar

    # Método de selección de features
    method: "boruta"  # Opciones: boruta, correlation, constant

    # Parámetros del método seleccionado
    params:
      n_estimators: 100
      max_iter: 100
      # threshold: 0.9  # Para correlation
      # threshold: 0.99  # Para constant

  # O usa tu propio Feature Pipeline personalizado:
  # custom_class: "features.custom_selector.CustomSelector"
  # params:
  #   custom_param: value
