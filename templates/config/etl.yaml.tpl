# ETL Configuration for {{project_name}}
#
# This file defines the data transformations (Extract, Transform, Load)
# using the multiple ETL with dependencies system.

etl:
  # ETL "sample" - Processes the included example dataset
  sample:
    enabled: true
    description: "Processes example dataset (removes rows with NULL)"
    input: "data/raw/sample_dataset.parquet"
    output: "data/processed/sample_dataset.parquet"
    custom_class: "data.custom_etl.CustomETL"
    params:
      mode: "concat"  # 'concat' (default) or 'merge'
    depends_on: []

  # ============================================
  # ADDITIONAL EXAMPLES (commented out)
  # ============================================
  # Uncomment and adapt as needed
  #
  # # ETL 1: Consumos - No dependencies
  # consumos:
  #   enabled: false
  #   description: "Processes monthly consumption data"
  #   input: "data/raw/consumos.csv"
  #   output: "data/processed/consumos.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"  # Concatenate files (default)
  #   depends_on: []
  #
  # # ETL 1b: Consumos with CSV options
  # # Use input_params / output_params for CSV-specific settings.
  # # Keys map directly to pd.read_csv() / df.to_csv() parameters.
  # consumos_csv:
  #   enabled: false
  #   description: "Processes semicolon-delimited CSV with custom options"
  #   input: "data/raw/consumos.csv"
  #   output: "data/processed/consumos.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"
  #     input_params:
  #       sep: ";"              # Field separator (default: ",")
  #       engine: "python"      # CSV engine: "c" (fast), "python", "pyarrow"
  #       on_bad_lines: "skip"  # Skip malformed lines (pandas >= 1.3)
  #     # output_params applies when output is also a CSV file:
  #     # output_params:
  #     #   sep: ";"
  #   depends_on: []
  #
  # # ETL 2: Clientes - No dependencies
  # clientes:
  #   enabled: false
  #   description: "Processes customer data"
  #   input: "data/raw/clientes.csv"
  #   output: "data/processed/clientes.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"
  #   depends_on: []
  #
  # # ETL 3: Concatenate multiple files
  # # Useful when you have several files with the same schema
  # concatenar_archivos:
  #   enabled: false
  #   description: "Concatenates multiple CSVs with the same schema"
  #   input:
  #     - "data/raw/consumos_2023.csv"
  #     - "data/raw/consumos_2024.csv"
  #     - "data/raw/consumos_2025.csv"
  #   output: "data/processed/consumos_completo.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"  # Concatenate vertically
  #     # input_params applies to all files in the list equally:
  #     # input_params:
  #     #   sep: ";"
  #   depends_on: []
  #
  # # ETL 4: Merge - Join files horizontally
  # # Use mode='merge' with required merge_config
  # merge_dataset:
  #   enabled: false
  #   description: "Combines consumos and clientes by id_cliente"
  #   input:
  #     - "data/processed/consumos.parquet"
  #     - "data/processed/clientes.parquet"
  #   output: "data/processed/dataset_mergeado.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "merge"  # Join horizontally
  #     merge_config:
  #       how: "left"       # 'left', 'right', 'inner', 'outer'
  #       on: "id_cliente"  # Column to merge on
  #   # Dependencies on other ETLs
  #   depends_on:
  #     - "consumos"
  #     - "clientes"
  #
  # # ETL 5: Example using reference to another ETL
  # enriquecido:
  #   enabled: false
  #   description: "Enriched dataset with additional data"
  #   # Use @etl_name reference instead of hardcoded path
  #   input:
  #     - "@merge_dataset"  # Resolves to merge_dataset output
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
