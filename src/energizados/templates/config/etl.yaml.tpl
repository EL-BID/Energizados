# ETL Configuration for {{project_name}}
#
# This file defines the data transformations (Extract, Transform, Load)
# using the multiple ETL with dependencies system.

etl:
  schema_version: 1

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
  #     # sample: 10000  # Optional: read only N rows for quick testing
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
  #
  # # ETL 6: Clip outliers - remove data reading errors from consumption columns
  # # Run this AFTER your main ETL and BEFORE training to clean extreme values
  # clip_outliers:
  #   enabled: false
  #   description: "Clip extreme consumption values (data reading errors)"
  #   input: "data/processed/sample_dataset.parquet"
  #   output: "data/processed/sample_dataset_clipped.parquet"
  #   custom_class: "energizados.etl.pipeline.ClipOutliersETL"
  #   params:
  #     threshold: 100000          # values above this are clipped
  #     periods_suffix: "_anterior"  # auto-detects *_anterior columns
  #   depends_on: []
  #
  # # ETL 7: Geographic features - clusters + IBGE hierarchy + distances from lat/lon.
  # # Run AFTER your main ETL and BEFORE training.
  # # Generates: geo_cluster (int), geo_estado, geo_municipio, geo_regiao, geo_dist_* columns.
  # # geo_cluster is required if using method: "stratified_time" in split config.
  # geo_features:
  #   enabled: false
  #   description: "Geographic features: clusters, hierarchy and distances from lat/lon"
  #   input: "data/processed/sample_dataset.parquet"
  #   output: "data/processed/sample_dataset_with_geo.parquet"
  #   custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
  #   params:
  #     lat_col: "latitude"          # latitude column name
  #     lon_col: "longitude"         # longitude column name
  #     n_clusters: 10               # number of geographic KMeans clusters
  #     random_state: 42
  #     include_hierarchy: true      # geo_estado, geo_municipio, geo_regiao (IBGE)
  #     include_distances: true      # haversine distances to reference cities
  #     distance_cities:             # available: sao_paulo, rio_de_janeiro, brasilia,
  #       - sao_paulo                #   salvador, belo_horizonte, fortaleza, recife,
  #       - rio_de_janeiro           #   curitiba, manaus, porto_alegre, florianopolis,
  #       - brasilia                 #   blumenau, joinville, criciuma, chapeco, itajai, lages
  #     include_coords: false        # keep original lat/lon in output
  #     cache_dir: ".cache/ibge"     # persist IBGE shapefiles to disk (avoids re-download)
  #   depends_on: []
  #
  # # ETL 8: Quick testing with sample
  # # Use 'sample' to read only N rows - useful for development and debugging
  # quick_test:
  #   enabled: false
  #   description: "Quick test with sampled data"
  #   input: "data/raw/full_dataset.csv"
  #   output: "data/processed/sample_test.parquet"
  #   custom_class: "data.custom_etl.CustomETL"
  #   params:
  #     mode: "concat"
  #     sample: 1000  # Read only 1000 rows for fast iteration
  #   depends_on: []
  #
  # # ETL 9: Incremental load - load only new records since last run
  # # incremental_key: datetime/numeric column used to detect new records.
  # #   On first run: processes all records and stores max(incremental_key) in state.
  # #   Subsequent runs: filters records where incremental_key > last saved value.
  # # partition_by: Hive-style partitioned output (year=2024/month=03/data.parquet).
  # #   'year' and 'month' are derived automatically from incremental_key if missing.
  # incremental_consumos:
  #   enabled: false
  #   description: "Incremental load of consumption data (only new records)"
  #   input: "data/raw/consumos_*.csv"  # glob pattern to discover new files
  #   output: "data/processed/consumos/"  # directory; partitions written inside
  #   custom_class: "energizados.etl.pipeline.SourceETL"
  #   params:
  #     mode: "incremental"
  #     incremental_key: "fecha_actualizacion"  # datetime column tracking new records
  #     partition_by:
  #       - year   # derived automatically from incremental_key
  #       - month  # derived automatically from incremental_key (zero-padded: "01".."12")
  #     overwrite: false
  #     state_file: ".cache/etl_states/incremental_consumos.json"
  #     # last_processed: "2024-01-01"  # optional: initial cutoff on first run
  #   depends_on: []

  # ETL 10: Clean intermediate files after pipeline completion
  # # Use this to free disk space by removing intermediate outputs.
  # # List files to delete in 'input' — supports direct paths, @etl_name
  # # references, and glob patterns (e.g. "data/processed/tmp_*.parquet").
  # # 'output' is a placeholder; no file is actually written.
  # # Set missing_ok: false to fail loudly if a file was not produced.
  # clean_files:
  #   enabled: false
  #   description: "Remove intermediate outputs after pipeline completes"
  #   input:
  #     - "@consumos"                         # reference to another ETL's output
  #     - "@clientes"
  #     - "data/processed/dataset_mergeado.parquet"   # direct path
  #     # - "data/processed/tmp_*.parquet"    # glob pattern also supported
  #   output: "data/processed/.clean_done"
  #   custom_class: "energizados.etl.pipeline.CleanFilesETL"
  #   params:
  #     missing_ok: true   # silently skip files that don't exist
  #   depends_on:
  #     - sample           # run last — after all ETLs that produce the files above
