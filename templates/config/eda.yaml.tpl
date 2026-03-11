# EDA Configuration for {{project_name}}
#
# Exploratory Data Analysis of raw datasources before preprocessing.
# Run with: energizados eda --config config/eda.yaml

eda:
  enabled: true

  # ============================================
  # Data Sources
  # ============================================
  data_sources:
    primary:
      path: "data/processed/sample_dataset.parquet"
      target_col: "target"      # Set to column name (e.g. "target") for supervised EDA.
                                # If null: phases 3 (target analysis), 7 (feature importance),
                                # and 8 (segmentation) are skipped automatically.

  # ============================================
  # Key Columns
  # ============================================
  column_detection:
    id_col: null              # e.g. "CLIENTE" — null if not present
    date_col: "fecha_inspeccion"
    lat_col: null             # e.g. "LATITUDE" — null if not present
    lon_col: null             # e.g. "LONGITUDE" — null if not present
    zone_col: null            # e.g. "ZONA"
    periods_suffix: "_anterior"

  # ============================================
  # Phase 0: CSV Loading
  # ============================================
  loading:
    file_encoding: "utf-8-sig"      # Windows BOM handling
    decimal_separator: "."          # "," for CELESC-style data
    detect_numeric_as_string: true  # Alert if numbers loaded as object
    auto_strip_strings: true        # Trim trailing whitespace in categoricals
    on_bad_lines: "warn"            # warn | skip | error

  # ============================================
  # Enabled Sections
  # ============================================
  sections:
    data_quality:
      enabled: true
    missing_values:
      enabled: true
      correlation_analysis: true
      funnel_generation: true
    duplicates:
      enabled: true
      check_by_id: true
      check_by_id_date: true
    target_analysis:
      enabled: true           # Skipped automatically if target_col is null
    categorical:
      enabled: true
      iv_woe_calculation: true
      cramers_v: true
      detailed_charts: true        # Per-column collapsible detail charts
    numeric:
      enabled: true
      ks_test: true
      iv_woe_binned: true
      outliers_by_iqr: true
      detailed_charts: true        # Per-column collapsible detail charts
    consumption:
      enabled: true
      anomaly_detection: true
    related_columns:
      enabled: false
      hierarchies: []
      # hierarchies:
      #   - name: "Proceso de inspección"
      #     columns: ["TIPO_SERVICO", "ACAO", "CATEGORIA_NOTA"]
      #   - name: "Ubicación × Tarifa"
      #     columns: ["ZONA", "TIPO_TARIFA"]
    geospatial:
      enabled: false            # Enable if lat_col / lon_col are set
      clustering:
        method: "kmeans"        # kmeans | dbscan
        n_clusters: 10
      country_bounds: [[-34.8, -74], [5.3, -28]]  # Brazil
    feature_importance:
      enabled: true             # Skipped automatically if target_col is null
      methods: ["iv", "ks_chi2", "cramers_v", "correlation"]
      lgbm_quick:
        enabled: false          # Enable for LightGBM-based feature importance
        n_estimators: 50
        max_depth: 5
    segmentation:
      enabled: true            # Requires target_col to be set
      segment_cols: ["zona", "actividad", "tipo_tarifa"]  # e.g. ["TIPO_CLIENTE", "TIPO_TARIFA", "ZONA"]
      min_segment_size: 100

  # ============================================
  # Visualization
  # ============================================
  visualization:
    plotly_template: "plotly_white"
    seaborn_palette: "muted"
    figsize_standard: [12, 6]
    figsize_large: [14, 8]
    max_categories_plot: 30

  # ============================================
  # Thresholds and Alerts
  # ============================================
  thresholds:
    missing_threshold: 0.5        # HIGH_MISSING alert
    correlation_threshold: 0.95   # HIGHLY_CORRELATED alert
    cardinality_high: 100         # HIGH_CARDINALITY alert
    cardinality_low: 10           # LOW_CARDINALITY_NUMERIC alert
    class_imbalance_ratio: 10     # CLASS_IMBALANCE alert
    iv_threshold_weak: 0.02       # WEAK_PREDICTORS alert
    iv_threshold_strong: 0.3      # Reference
    iv_threshold_leakage: 0.8     # POTENTIAL_LEAKAGE alert
    ks_significance: 0.05

  # ============================================
  # Output
  # ============================================
  output:
    output_dir: "output/eda/"
    report_name: "eda_report.html"
    export_plots: true
    export_csv: true              # Export summary tables as CSV
    sample_size: null             # null = full dataset
