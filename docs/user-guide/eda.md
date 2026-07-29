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

## Section Key Aliases

The configuration normalizes several legacy section keys to their canonical form. Both the original and canonical names are accepted:

| Alias (also accepted) | Canonical key | Notes |
|-----------------------|---------------|-------|
| `target_analysis` | `target` | Phase 3 section key |
| `data_quality` | `global_stats` | Data quality features are computed inside `global_stats` |
| `missing_values` | `global_stats` | Missing value stats are part of `global_stats` |
| `duplicates` | `global_stats` | Duplicate detection is part of `global_stats` |

!!! note
    The YAML template uses the alias form (`data_quality`, `missing_values`, `duplicates`, `target_analysis`) for readability. The framework internally maps them to their canonical keys before processing.

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

- **Numeric**: Histogram, boxplot
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

### Outlier Detection (within Phase 2)

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

**Population Segmentation** (NEW):

When `population_analysis: enabled: true`, the EDA module detects **multiple distinct populations** within a single distribution by identifying significant jumps between consecutive percentiles. This is particularly useful for detecting:

- **Multiple data sources**: Different segments of customers mixed together
- **Data quality issues**: Errors that create artificial populations (e.g., extreme values)
- **Business insights**: Distinct customer behaviors (e.g., residential vs industrial)

```yaml
sections:
  outliers:
    population_analysis:
      enabled: true
      percentile_step: 0.5      # Step size for percentile calculation (0.1-1.0)
      jump_ratio_threshold: 5.0  # Minimum ratio to detect a "jump" (2.0+)
      max_populations: 5          # Maximum populations to detect (2-10)
      min_population_pct: 0.5    # Minimum % of rows for a population (0.1-10.0)
      # Additional columns to analyze (besides consumption columns)
      # additional_columns: ["feature_1", "feature_2"]
```

**How it works:**

1. **Dense percentile calculation**: Calculates percentiles at `percentile_step` intervals (default: every 0.5%)
2. **Jump detection**: Identifies where the ratio between consecutive percentiles exceeds `jump_ratio_threshold` (default: 5.0x)
3. **Population segmentation**: Groups data into populations based on detected jump points
4. **Interpretation generation**: Creates human-readable descriptions including:
   - Position in distribution (Lower tail / Middle range / Upper tail)
   - Population size (Majority / Secondary / Minor)
   - Target rate (if `target_col` is set)

**Report output:**

For each column with multiple populations detected, the EDA report generates:

- **Population table**: Showing range, percentile, row count, and interpretation
- **Detected jumps table**: Showing percentile ranges, value changes, and ratios

!!! example
    For consumption data with 3 populations:
    - **Population 1** (0–21,000, 92%): "Lower tail | Majority | High target rate (5.84%)"
    - **Population 2** (21k–100k, 5%): "Middle range | Secondary | Low target rate (0.52%)"
    - **Population 3** (>100k, 3%): "Upper tail | Minor | (wide range) | Low target rate (0.00%)"

    The jump from P97.5 (21k) to P100 (100k+) with a ratio >5x indicates the upper population is likely **data errors or extreme outliers**, not legitimate high-value customers.

!!! tip
    Adjust `jump_ratio_threshold` to be more sensitive (lower value) or less sensitive (higher value) depending on your data:
    - **2.0–3.0**: Highly sensitive — detects more, smaller populations
    - **5.0–10.0**: Balanced — recommended for most datasets
    - **10.0+**: Less sensitive — only detects very extreme populations

!!! note
    Electricity fraud detection datasets typically have no traditional numeric columns — all numeric data are consumption period columns (`12_anterior`, `11_anterior`, ...). The outlier section will display these with a green "consumption" badge.

### Phase 3: Target Variable Analysis

Analyzes the target column behavior:

- **Class balance**: Pie chart showing fraud vs non-fraud distribution
- **Temporal rate**: Target rate over time (identifies temporal drift)
- **Segment rates**: Target rate by key categorical segments (e.g., by zone, tariff type)

!!! note
    This phase is automatically skipped if `target_col` is set to `null`.

### Phase 4: Geospatial Analysis (Optional)

Performs spatial analysis when latitude/longitude columns are provided:

- **Clustering**: Groups customers into geographic clusters (k-means)
- **Hotspot identification**: Identifies areas with high fraud rates
- **Spatial distribution**: Scatter plot colored by target

```yaml
sections:
  geospatial:
    enabled: true
    clustering:
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

## Configurable Thresholds

The `thresholds` section controls when alerts are raised across all phases:

| Key | Default | Alert triggered when... |
|-----|---------|------------------------|
| `missing_threshold` | `0.5` | A column has more than 50% missing values (`HIGH_MISSING`) |
| `correlation_threshold` | `0.95` | Two columns have Pearson correlation above 0.95 (`HIGHLY_CORRELATED`) |
| `cardinality_high` | `100` | A categorical column has more than 100 unique values (`HIGH_CARDINALITY`) |
| `cardinality_low` | `10` | A numeric column has fewer than 10 unique values (`LOW_CARDINALITY_NUMERIC`) |
| `class_imbalance_ratio` | `10` | Majority class is more than 10× the minority class (`CLASS_IMBALANCE`) |
| `iv_threshold_weak` | `0.02` | A feature's IV is below 0.02 — considered a weak predictor (`WEAK_PREDICTORS`) |
| `iv_threshold_leakage` | `0.8` | A feature's IV exceeds 0.8 — potential data leakage (`POTENTIAL_LEAKAGE`) |
| `iv_threshold_strong` | `0.3` | Reference value for strong predictors (no alert, used in report labeling) |
| `ks_significance` | `0.05` | KS test p-value threshold for significance |

```yaml
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
```

## Output

The EDA module generates:

1. **HTML Report**: `output/eda/eda_report.html` - Self-contained interactive report with inline SVG charts
2. **JSON Artifact**: `output/eda/outlier_analysis.json` with full outlier detection results

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
    duplicates:
      enabled: true
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

      # Population segmentation analysis
      population_analysis:
        enabled: true
        percentile_step: 0.5      # Step size for percentile calculation
        jump_ratio_threshold: 5.0  # Minimum ratio to detect a "jump"
        max_populations: 5          # Maximum populations to detect
        min_population_pct: 0.5    # Minimum % of rows for a population
        # additional_columns: ["feature_1", "feature_2"]  # Optional: extra columns
    related_columns:
      enabled: false
      hierarchies: []
      # hierarchies:
      #   - name: "Proceso de inspección"
      #     columns: ["TIPO_SERVICO", "ACAO", "CATEGORIA_NOTA"]
      #   - name: "Ubicación × Tarifa"
      #     columns: ["ZONA", "TIPO_TARIFA"]
    geospatial:
      enabled: false
      clustering:
        n_clusters: 10
      country_bounds: [[-34.8, -74], [5.3, -28]]  # Brazil
    feature_importance:
      enabled: true
      methods: ["iv", "ks_chi2", "cramers_v", "correlation"]
    segmentation:
      enabled: true
      segment_cols: ["zona", "actividad", "tipo_tarifa"]
      min_segment_size: 100

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
```

## Next Steps

- [Understanding Results](understanding-results.md) - Learn how to interpret training results
- [Configuration Guide](configuration/) - Detailed configuration options
- [Advanced EDA](../advanced/extending/custom-etl.md) - Creating custom EDA analyzers
