# ETLs Configuration for {{project_name}}
#
# Este archivo define las transformaciones de datos (Extract, Transform, Load)
# utilizando el sistema de múltiples ETLs con dependencias.

etls:
  # ETL "sample" - Procesa el dataset de ejemplo incluido
  sample:
    enabled: true
    description: "Procesa dataset de ejemplo (elimina filas con NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "data.custom_etl.CustomETL"
    params:
      mode: "concat"  # 'concat' (default) o 'merge'
    depends_on: []

  # ============================================
  # EJEMPLOS ADICIONALES (comentados)
  # ============================================
  # Descomenta y adapta según tus necesidades
  #
  # # ETL 1: Consumos - No tiene dependencias
  # consumos:
  #   enabled: false
  #   description: "Procesa datos de consumo mensual"
  #   input: "data/raw/consumos.csv"
  #   output: "data/processed/consumos.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"  # Concatena archivos (default)
  #   depends_on: []
  #
  # # ETL 2: Clientes - No tiene dependencias
  # clientes:
  #   enabled: false
  #   description: "Procesa datos de clientes"
  #   input: "data/raw/clientes.csv"
  #   output: "data/processed/clientes.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"
  #   depends_on: []
  #
  # # ETL 3: Concatenar múltiples archivos
  # # Útil cuando tienes varios archivos con el mismo esquema
  # concatenar_archivos:
  #   enabled: false
  #   description: "Concatena múltiples CSV del mismo esquema"
  #   input:
  #     - "data/raw/consumos_2023.csv"
  #     - "data/raw/consumos_2024.csv"
  #     - "data/raw/consumos_2025.csv"
  #   output: "data/processed/consumos_completo.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"  # Concatenar verticalmente
  #   depends_on: []
  #
  # # ETL 4: Merge - Une archivos horizontalmente
  # # Usa mode='merge' con merge_config obligatorio
  # merge_dataset:
  #   enabled: false
  #   description: "Combina consumos y clientes por id_cliente"
  #   input:
  #     - "data/processed/consumos.parquet"
  #     - "data/processed/clientes.parquet"
  #   output: "data/processed/dataset_mergeado.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "merge"  # Unir horizontalmente
  #     merge_config:
  #       how: "left"       # 'left', 'right', 'inner', 'outer'
  #       on: "id_cliente"  # Columna para hacer el merge
  #   # Dependencias de otras ETLs
  #   depends_on:
  #     - "consumos"
  #     - "clientes"
  #
  # # ETL 5: Ejemplo usando referencia a otra ETL
  # enriquecido:
  #   enabled: false
  #   description: "Dataset enriquecido con más datos"
  #   # Usar referencia @etl_name en lugar de path hardcoded
  #   input:
  #     - "@merge_dataset"  # Se resuelve al output de merge_dataset
  #     - "data/raw/inspecciones.csv"
  #   output: "data/processed/dataset_final.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "merge"
  #     merge_config:
  #       how: "left"
  #       on: "id_cliente"
  #   depends_on:
  #     - "merge_dataset"
