# Outlier Analysis Notebook Guide

## Overview

The `template_outlier_analysis.ipynb` notebook provides a structured approach to detect, analyze, and document outliers in your dataset before running the ETL pipeline.

## When to Use This Notebook

### 1. Before ETL (Recommended)
Run this notebook **before** any ETL operations to:
- Identify data quality issues early
- Understand data distribution and anomalies
- Plan appropriate preprocessing steps

### 2. During EDA
Use during Exploratory Data Analysis to:
- Deep dive into specific columns with high outlier percentages
- Compare outlier patterns across features
- Inform feature engineering decisions

### 3. When Detecting Drift
Compare outlier patterns over time:
- Run on historical data snapshots
- Track changes in outlier distribution
- Identify potential data quality degradation

## Quick Start

### Step 1: Open the Notebook
```bash
jupyter lab notebooks/template_outlier_analysis.ipynb
```

### Step 2: Configure Parameters
Edit Cell 1 to set your dataset path and target column:

```python
DATASET_PATH = "../data/raw/your_dataset.parquet"  # Change this
TARGET_COL = "target"  # Optional — set to None if no target
```

### Step 3: Run All Cells
Execute cells in order (Kernel → Run All) or run individually.

## Notebook Structure

### Cell 1: Setup
- Imports required libraries
- Configures dataset path and target column
- Sets visualization style

### Cell 2: Load Data
- Loads the dataset from the configured path
- Displays basic information (shape, columns, data types)
- Shows first few rows

### Cell 3: Classify Columns
- Automatically classifies columns into:
  - **Numeric**: Continuous numerical variables
  - **Categorical**: Discrete categorical variables
  - **Consumption**: Time-series consumption columns (detected by naming pattern)

### Cell 4: Multi-Method Detection
- Detects outliers using three statistical methods:
  - **IQR (Interquartile Range)**: Robust to extreme values
  - **Z-Score**: Standard deviations from the mean
  - **Modified Z-Score**: MAD-based, resistant to outliers

### Cell 5: Summary Table
- Displays a comparison table of outlier counts across methods
- Shows percentage of outliers per column
- Highlights columns with the highest outlier percentages

### Cell 6: Boxplots
- Visualizes outliers with boxplots
- Only shows columns with detected outliers for cleaner visualization
- Outliers are highlighted in red

### Cell 7: Consumption Anomalies
- Analyzes consumption-specific patterns (if consumption columns exist)
- Detects:
  - Zero-variance rows (suspiciously constant consumption)
  - High-variability patterns
  - Extreme consumption values

### Cell 8: Row-level Analysis
- Identifies rows that are outliers across multiple columns
- Computes an "outlier score" for each row
- Shows the top 10 most outlier-prone rows

### Cell 9: Recommendations
- Provides data preprocessing recommendations based on outlier analysis:
  - **HIGH (>20%)**: Consider capping (winsorizing) or removing column
  - **MEDIUM (10-20%)**: Investigate origin before deciding
  - **LOW-MEDIUM (5-10%)**: Monitor in next data refresh
  - **OK (<5%)**: Within acceptable range

### Cell 10: Export Report
- Saves outlier analysis results as JSON for documentation
- Includes dataset metadata, outlier summary, and recommendations
- Can be used for comparison across time periods

## How to Interpret Results

### Outlier Percentage Guidelines

| Range | Interpretation | Recommended Action |
|-------|---------------|-------------------|
| 0-5% | Normal distribution | No action needed |
| 5-10% | Slightly elevated | Monitor in future runs |
| 10-20% | Concerning | Investigate data collection or entry errors |
| >20% | Critical | Consider capping, winsorizing, or removing column |

### Multi-Method Agreement
When multiple methods (IQR, Z-Score, Modified Z-Score) agree on outliers:
- **Higher confidence** that these are genuine outliers
- **Stronger justification** for preprocessing decisions

### Consumption Anomalies
Look for these patterns:
- **Zero variance**: May indicate meter failures or data entry errors
- **Extreme range**: Suspiciously high variability (range/mean > 5)
- **Mean Z-score outliers**: Global consumption anomalies

## Configuration Options

### Detector Parameters (Cell 4)
```python
detector = OutlierDetector(
    methods=["iqr", "zscore", "modified_zscore"],  # Methods to use
    iqr_multiplier=1.5,                            # IQR fence multiplier (default: 1.5)
    zscore_threshold=3.0,                         # Z-score threshold (default: 3.0)
)
```

**Adjusting Sensitivity:**
- **More sensitive**: Use `iqr_multiplier=1.0`, `zscore_threshold=2.5`
- **Less sensitive**: Use `iqr_multiplier=3.0`, `zscore_threshold=3.5`

### Visualization Columns (Cell 6)
```python
cols_with_outliers = [c for c, r in outlier_summary.items() 
                      if r.get("iqr", {}).get("outlier_pct", 0) > 0]
```

**Modify threshold:** Change `> 0` to `> 5` for only columns with >5% outliers

## Common Workflows

### Workflow 1: Initial Data Assessment
1. Run notebook with default settings
2. Review summary table for high-outlier columns
3. Examine boxplots for visual confirmation
4. Check row-level analysis for problematic rows
5. Export report for documentation

### Workflow 2: Targeted Investigation
1. Identify columns of interest from EDA report
2. Modify Cell 4 to detect only those columns
3. Deep dive into consumption anomalies if applicable
4. Compare with domain knowledge to validate findings

### Workflow 3: Preprocessing Validation
1. Apply preprocessing (winsorization, capping, removal)
2. Save processed dataset
3. Re-run notebook on processed data
4. Compare reports to validate improvements

## Exported Report Structure

The JSON report (`outlier_report.json`) contains:

```json
{
  "generated_at": "2026-03-22 00:00:00",
  "dataset": "../data/raw/sample_dataset.parquet",
  "n_rows": 10000,
  "n_numeric_cols": 5,
  "n_categorical_cols": 4,
  "n_consumption_cols": 12,
  "target_column": "target",
  "outlier_summary": {
    "column_name": {
      "iqr": {
        "method": "iqr",
        "outlier_count": 50,
        "outlier_pct": 0.5,
        "sample_values": [...],
        "has_alert": false,
        "fences": {"lower": 0.0, "upper": 100.0}
      },
      "zscore": {...},
      "modified_zscore": {...}
    }
  }
}
```

## Troubleshooting

### Issue: "No columns detected"
**Cause:** Dataset may have no numeric columns or different column naming patterns
**Solution:** 
- Check dataset structure with `df.info()`
- Manually specify column lists in Cell 3

### Issue: "ImportError: No module named 'energizados'"
**Cause:** Energizados package not installed
**Solution:** 
```bash
pip install -e .
# or
pip install energizados
```

### Issue: "FileNotFoundError"
**Cause:** Incorrect dataset path
**Solution:** 
- Use relative path from notebook directory (e.g., `../data/raw/`)
- Use absolute path if needed

### Issue: Outlier masks are empty
**Cause:** All NaN values in column
**Solution:** 
- Check for NaN: `df[column].isna().sum()`
- Consider imputation before outlier detection

## Integration with EDA Pipeline

This notebook complements the full EDA report generated by:

```bash
energizados run eda
```

**Key differences:**
- **Notebook**: Interactive, focused on outlier detection, allows deep dive
- **EDA Report**: Comprehensive, covers all EDA phases, automated

**Recommended workflow:**
1. Run full EDA to identify issues
2. Use outlier notebook to investigate specific concerns
3. Update preprocessing based on findings
4. Re-run EDA to validate improvements

## Related Documentation

- **EDA Module**: `docs/eda.md`
- **ETL Configuration**: `config/eda.yaml`
- **Source Code**: `src/energizados/eda/_outlier_detector.py`

## Feedback and Questions

For issues or questions about the outlier analysis:
1. Check the troubleshooting section above
2. Review the full EDA documentation
3. Open an issue on the project repository
