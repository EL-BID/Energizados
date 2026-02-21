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
    custom_class: "energizados.etl.pipeline.SourceETL"
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
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   depends_on: []
  #
  # # ETL 2: Clientes - No tiene dependencias
  # clientes:
  #   enabled: false
  #   description: "Procesa datos de clientes"
  #   input: "data/raw/clientes.csv"
  #   output: "data/processed/clientes.parquet"
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   depends_on: []
  #
  # # ETL 3: Merge - Depende de consumos y clientes
  # # Input puede ser múltiples archivos
  # merge_dataset:
  #   enabled: false
  #   description: "Combina consumos y clientes"
  #   input:
  #     - "data/processed/consumos.parquet"
  #     - "data/processed/clientes.parquet"
  #   output: "data/processed/dataset_limpio.parquet"
  #   custom_class: "energizados.etl.pipeline.MultiSourceETL"
  #   # Dependencias de otras ETLs
  #   depends_on:
  #     - "consumos"
  #     - "clientes"
  #
  # # ETL 4: Ejemplo usando referencia a otra ETL
  # enriquecido:
  #   enabled: false
  #   description: "Dataset enriquecido"
  #   # Usar referencia @etl_name en lugar de path hardcoded
  #   input:
  #     - "@merge_dataset"  # Se resuelve al output de merge_dataset
  #   output: "data/processed/dataset_final.parquet"
  #   custom_class: "energizados.etl.pipeline.MultiSourceETL"
  #   depends_on:
  #     - "merge_dataset"
