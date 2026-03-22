# EDA Module

The Exploratory Data Analysis (EDA) module generates comprehensive, interactive HTML reports from your raw datasets. It helps you understand data quality, feature distributions, target behavior, and relationships between columns before building models.

!!! info
    The EDA module is particularly useful in fraud detection scenarios where understanding data quality, class imbalance, and feature predictive power is critical.

## Running EDA

```bash
energizados run eda
```

## Configuration Structure

The `eda.yaml` file controls all aspects of the EDA process:

```yaml
eda:
  enabled: true

  # Data Sources
  data_sources:
    primary:
      path: "data/processed/sample_dataset.parquet"
      target_col: "target"      # Required for supervised phases

  # Key Columns
  column_detection:
    id_col: null
    date_col: "fecha_inspeccion"
    lat_col: null
    lon_col: null
    zone_col: null
    periods_suffix: "_anterior"

  # Loading Options
  loading:
    file_encoding: "utf-8-sig"
    decimal_separator: "."
    detect_numeric_as_string: true
    auto_strip_strings: true
    on_bad_lines: "warn"

  # Section Configuration
  sections:
    data_quality:
      enabled: true
    missing_values:
      enabled: true
    # ... other sections

  # Output
  output:
    output_dir: "output/eda/"
    report_name: "eda_report.html"
```

## Analysis Phases

The EDA module runs through multiple phases, each producing specific insights:

### Phase 0: Loading Validation

Validates the initial data load and alerts on potential issues:

- **BOM detection**: Identifies byte-order marks that can cause encoding issues
- **Encoding verification**: Ensures characters are read correctly
- **Numeric-as-string detection**: Flags when numbers are loaded as text (common with CSV export issues)
- **Whitespace detection**: Identifies trailing/leading spaces in categorical values

!!! tip
    Always review the Phase 0 alerts first—they often reveal data quality issues that can corrupt subsequent analysis.

### Phase 1: Global Statistics

Provides an overview of the entire dataset:

- **Row and column counts**
- **Missing value percentages** per column
- **Duplicate record detection**
- **Constant column identification**

### Phase 2: Column Analysis

Analyzes each column based on its type (numeric, categorical, temporal, or consumption):

- **Numeric columns**: Distribution statistics, multi-method outlier detection, histogram/boxplot
- **Categorical columns**: Cardinality, value counts, treemap visualization
- **Temporal columns**: Date range, distribution over time
- **Consumption columns**: Pattern analysis (zeros, negatives, constant values, abrupt drops) — controlled by `sections.outliers.consumption_patterns`

#### Detailed Charts (Optional)

When `detailed_charts: true` is set under `sections.numeric` or `sections.categorical`, each column generates a collapsible `<details>` block with:

- **Numeric**: Histogram, boxplot, Q-Q plot, target rate by bin
- **Categorical**: Bar chart, treemap, target rate by category

```yaml
sections:
  categorical:
    enabled: true
    detailed_charts: true  # Enable per-column detail charts
  numeric:
    enabled: true
    detailed_charts: true  # Enable per-column detail charts
```

!!! warning
    Enabling `detailed_charts` with many columns (100+) will significantly increase report generation time. Use it selectively during deep-dive analysis.

### Phase 2.5: Outlier Detection

Performs multi-method outlier detection on **all numeric columns** (including consumption period columns with `_anterior` suffix) and generates domain-specific consumption pattern analysis:

```yaml
sections:
  outliers:
    enabled: true
    methods:
      - iqr             # IQR multiplier (default 1.5x)
      - zscore          # Standard deviations (default 3.0)
      - modified_zscore # MAD-based threshold (default 3.5)
    thresholds:
      iqr: 1.5
      zscore: 3.0
      modified_zscore: 3.5
    consumption_patterns: true  # Analyze consumption columns for fraud patterns
    alert_threshold: 10         # % of outliers that triggers a WARNING alert
    max_outlier_values_shown: 20
    detailed_charts: true       # Generate boxplots and heatmap SVGs
```

**Detection methods:**

| Method | How it works | Threshold |
|--------|-------------|-----------|
| IQR | Values beyond Q1 - 1.5×IQR or Q3 + 1.5×IQR | multiplier |
| Z-score | Values beyond ±N standard deviations from mean | std deviations |
| Modified Z-score | Median Absolute Deviation (MAD) based | MAD threshold |

**Consumption patterns** (when `consumption_patterns: true`):

- **Zero Variance Rows**: identical consumption across all periods (potential meter bypass)
- **Extreme Range Outliers**: rows with consumption range-to-mean ratio > 5.0
- **Global Mean Outliers**: rows with mean consumption z-score > 3.0

**Report output:**

- Summary table with outlier counts per column and method (with "consumption" badge for period columns)
- Outlier boxplots and heatmap (SVG, embedded inline)
- Consumption Outlier Patterns section with 3 key metrics
- WARNING alerts for columns exceeding `alert_threshold`

!!! note
    Datasets like CELESC have no traditional numeric columns — all numeric data are consumption period columns (`12_anterior`, `11_anterior`, ...). The outlier section will display these with a green "consumption" badge.

### Phase 3: Target Variable Analysis

Analyzes the target column behavior:

- **Class balance**: Pie chart showing fraud vs non-fraud distribution
- **Temporal rate**: Target rate over time (identifies temporal drift)
- **Segment rates**: Target rate by key categorical segments (e.g., by zone, tariff type)

!!! note
    This phase is automatically skipped if `target_col` is set to `null`.

### Phase 4: Geospatial Analysis (Optional)

Performs spatial analysis when latitude/longitude columns are provided:

- **Clustering**: Groups customers into geographic clusters (k-means or DBSCAN)
- **Hotspot identification**: Identifies areas with high fraud rates
- **Spatial distribution**: Scatter plot colored by target

```yaml
sections:
  geospatial:
    enabled: true
    clustering:
      method: "kmeans"      # kmeans | dbscan
      n_clusters: 10
    country_bounds: [[-34.8, -74], [5.3, -28]]  # Brazil
```

### Phase 5: Feature Importance

Ranks features by their predictive power using multiple metrics:

- **Information Value (IV)**: Measures feature's ability to distinguish between classes
- **Kolmogorov-Smirnov (KS)**: Maximum separation between fraud/non-fraud distributions
- **Cramér's V**: Association strength for categorical features
- **Correlation**: Pearson correlation for numeric features

```yaml
sections:
  feature_importance:
    enabled: true
    methods: ["iv", "ks_chi2", "cramers_v", "correlation"]
```

!!! tip
    Focus on features with IV > 0.02 (weak predictors) and prioritize those with IV > 0.3 (strong predictors). Features with IV > 0.8 may indicate data leakage.

### Phase 6: Segmentation Analysis (Optional)

Analyzes how target behavior varies across different segments:

- **Segment distribution**: Customer count by segment
- **Segment target rates**: Fraud rate per segment
- **Drift detection**: Identifies segments with unusual patterns

```yaml
sections:
  segmentation:
    enabled: true
    segment_cols: ["zona", "actividad", "tipo_tarifa"]
    min_segment_size: 100
```

### Phase 7: Related Columns Analysis

Analyzes hierarchical relationships between multiple categorical columns. This is useful for understanding multi-dimensional patterns like inspection processes or location hierarchies.

```yaml
sections:
  related_columns:
    enabled: true
    hierarchies:
      - name: "Inspection Process"
        columns: ["TIPO_SERVICO", "ACAO", "CATEGORIA_NOTA"]
      - name: "Location × Tariff"
        columns: ["ZONA", "TIPO_TARIFA"]
```

For each hierarchy, the EDA generates:

- **Tree breakdown**: Visual hierarchy showing customer counts at each level
- **Cross-tabulation**: Contingency tables between adjacent hierarchy levels
- **Sunburst chart**: Interactive radial chart showing segment sizes
- **Sankey diagram**: Flow diagram showing transitions between hierarchy levels
- **Target rate heatmap**: Heatmap showing fraud rates across all segment combinations

!!! example
    For a hierarchy `["ZONA", "TIPO_TARIFA"]`, the target rate heatmap shows which zone-tariff combinations have the highest fraud rates, helping identify high-risk segments for targeted inspection.

## Output

The EDA module generates:

1. **HTML Report**: `output/eda/eda_report.html` - Self-contained interactive report with inline SVG charts
2. **CSV Exports**: Summary tables exported as CSV files in `output/eda/csv/`
3. **JSON Artifact**: `output/eda/outlier_analysis.json` with full outlier detection results

## Complete Example Configuration

```yaml
# config/eda.yaml
eda:
  enabled: true

  data_sources:
    primary:
      path: "data/processed/sample_dataset.parquet"
      target_col: "target"

  column_detection:
    id_col: null
    date_col: "fecha_inspeccion"
    lat_col: null
    lon_col: null
    zone_col: "zona"
    periods_suffix: "_anterior"

  loading:
    file_encoding: "utf-8-sig"
    decimal_separator: "."
    detect_numeric_as_string: true
    auto_strip_strings: true
    on_bad_lines: "warn"

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
      enabled: true
    categorical:
      enabled: true
      iv_woe_calculation: true
      cramers_v: true
      detailed_charts: false
    numeric:
      enabled: true
      ks_test: true
      iv_woe_binned: true
      outliers_by_iqr: true
      detailed_charts: false
    outliers:
      enabled: true
      methods:
        - iqr
        - zscore
        - modified_zscore
      thresholds:
        iqr: 1.5
        zscore: 3.0
        modified_zscore: 3.5
      consumption_patterns: true  # Detects abrupt drops, zeros, negatives, constants
      alert_threshold: 10         # % of outliers that triggers a WARNING alert
      max_outlier_values_shown: 20
      detailed_charts: true       # Generate boxplots and heatmap SVGs
    related_columns:
      enabled: true
      hierarchies:
        - name: "Zone × Activity"
          columns: ["zona", "actividad"]
        - name: "Tariff × Voltage"
          columns: ["tipo_tarifa", "nivel_tension"]
    geospatial:
      enabled: false
    feature_importance:
      enabled: true
      methods: ["iv", "ks_chi2", "cramers_v", "correlation"]
    segmentation:
      enabled: true
      segment_cols: ["zona", "actividad", "tipo_tarifa"]
      min_segment_size: 100

  visualization:
    plotly_template: "plotly_white"
    seaborn_palette: "muted"
    figsize_standard: [12, 6]
    figsize_large: [14, 8]
    max_categories_plot: 30

  thresholds:
    missing_threshold: 0.5
    correlation_threshold: 0.95
    cardinality_high: 100
    cardinality_low: 10
    class_imbalance_ratio: 10
    iv_threshold_weak: 0.02
    iv_threshold_strong: 0.3
    iv_threshold_leakage: 0.8
    ks_significance: 0.05

  output:
    output_dir: "output/eda/"
    report_name: "eda_report.html"
    export_plots: true
    export_csv: true
    sample_size: null
```

## Next Steps

- [Understanding Results](understanding-results.md) - Learn how to interpret training results
- [Configuration Guide](configuration/) - Detailed configuration options
- [Advanced EDA](../advanced/extending/custom-etl.md) - Creating custom EDA analyzers
