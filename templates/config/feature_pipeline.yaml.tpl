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
    # Cada columna declara sus propias transformaciones en orden secuencial
    columns:
      # Actividad: reducir cardinalidad + one-hot encoding
      actividad:
        - cardinality_reducer:
            threshold: 0.001  # Agrupa categorías con <0.1% frecuencia en "otros"
        - to_dummy: {}       # One-hot encoding (crea múltiples columnas binarias)

      # Tipo Tarifa: reducir cardinalidad + target encoding
      tipo_tarifa:
        - cardinality_reducer:
            threshold: 0.001
        - target_encoding:
            w: 20  # Peso de suavizado (mayor = más suavizado hacia el promedio global)

      # Zona: encoding ordinal simple (valores numéricos 0, 1, 2, ...)
      zona:
        - ordinal_encoding: {}

      # Nivel Tensión: encoding ordinal simple
      nivel_tension:
        - ordinal_encoding: {}

      # Material Instalación: target encoding directo
      material_instalacion:
        - target_encoding:
            w: 10

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

# Transformaciones disponibles:
# =============================
# cardinality_reducer:
#   - Agrupa categorías poco frecuentes en "otros"
#   - Parámetros:
#       threshold: float (0-1) - frecuencia mínima para mantener categoría (default: 0.001)
#
# to_dummy:
#   - One-hot encoding (crea columnas binarias)
#   - Parámetros: ninguno
#
# target_encoding:
#   - Reemplaza cada categoría con la probabilidad del target
#   - Requiere que el target 'y' esté disponible durante fit
#   - Parámetros:
#       w: int - peso de suavizado (default: 20)
#
# ordinal_encoding:
#   - Reemplaza cada categoría con un número (0, 1, 2, ...)
#   - Parámetros: sklearn OrdinalEncoder params
#
# minmax_scaler_row:
#   - Escala cada fila independientemente a un rango [0, 1]
#   - Útil para series temporales de consumo
#   - Parámetros:
#       feature_range: tuple - rango de salida (default: [0, 1])
