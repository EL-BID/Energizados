# Custom ETLs

## What It Is

An ETL (Extract-Transform-Load) is a data processing step in the pipeline. ETLs can read data from various sources, transform it, and save it to a target format. ETLs can depend on other ETLs, forming a directed acyclic graph (DAG) that executes in topological order.

## BaseETL Contract

```python
from abc import ABC, abstractmethod
import pandas as pd

class BaseETL(ABC):
    """Base class for custom ETL."""

    def __init__(self):
        """Initialize ETL instance."""
        pass

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """
        Extracts data from the source.

        Returns:
            pd.DataFrame: Raw data

        Raises:
            ETLError: If an error occurs during extraction
        """
        pass

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms and cleans the data.

        Args:
            df: Raw DataFrame

        Returns:
            pd.DataFrame: Clean DataFrame with expected schema

        Raises:
            ETLError: If an error occurs during transformation
        """
        pass

    @abstractmethod
    def load(self, df: pd.DataFrame, path: str) -> None:
        """
        Saves transformed data.

        Args:
            df: Transformed DataFrame
            path: Output path

        Raises:
            ETLError: If an error occurs during loading
        """
        pass

    def run(self, output_path: str) -> pd.DataFrame:
        """
        Executes the complete ETL pipeline.

        Can be overridden to add additional logic.

        Args:
            output_path: Path to save the transformed data

        Returns:
            pd.DataFrame: Transformed DataFrame
        """
        # Default implementation: extract() -> transform() -> load()
```

## Minimal Example: SimpleFilterETL

```python
# src/data/custom_etl.py
from energizados.etl.base import BaseETL
import pandas as pd


class SimpleFilterETL(BaseETL):
    """ETL that removes rows with nulls and saves to parquet."""

    def __init__(self, input_path=None, output_path=None, **kwargs):
        super().__init__(**kwargs)
        self.input_path = input_path
        self.output_path = output_path

    def extract(self) -> pd.DataFrame:
        """Read raw data from CSV."""
        return pd.read_csv(self.input_path)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Drop rows with any null values."""
        return df.dropna()

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save to parquet format."""
        df.to_parquet(path, index=False)
```

Wire it in `config/etl.yaml`:
```yaml
etl:
  filter_data:
    enabled: true
    description: "Removes rows with null values"
    input: "data/raw/data.csv"
    output: "data/processed/clean.parquet"
    custom_class: "src.data.custom_etl.SimpleFilterETL"
    params:
      input_path: "data/raw/data.csv"
      output_path: "data/processed/clean.parquet"
    depends_on: []
```

## Advanced Example: Merging Multiple Sources

The built-in `SourceETL` class supports merging multiple data sources horizontally using `mode="merge"`:

```yaml
etl:
  consumos:
    enabled: true
    description: "Consumption data"
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []
 
  clientes:
    enabled: true
    description: "Customer data"
    input: "data/raw/clientes.csv"
    output: "data/processed/clientes.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []
 
  merge_all:
    enabled: true
    description: "Merges consumos and clientes by id_cliente"
    input:
      - "@consumos"
      - "@clientes"
    output: "data/processed/merged.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "merge"
      merge_config:
        how: "left"
        on: "id_cliente"
    depends_on: ["consumos", "clientes"]
```

The `merge_config` section accepts any parameter from pandas `pd.merge()`: `how`, `on`, `left_on`, `right_on`, `left_index`, `right_index`.

## Advanced Pattern: Dataset Builder ETL (Long-to-Wide Transformation)

Many fraud detection scenarios require transforming longitudinal consumption data from **long format** (one row per customer-period) to **wide format** (one row per customer with columns for each period like `consumo_1_anterior`, `consumo_2_anterior`, etc.).

This is a domain-specific operation that is best implemented as a **custom ETL extending `SourceETL`**. The pattern shown below is based on real production implementations.

### When to Use This Pattern

- You have consumption data in long format (customer_id, period, consumo)
- You need to pivot to wide format for ML models
- You need to join multiple sources (consumption + inspections + customer master)
- You need to filter consumption data to periods before the inspection date

### Template: DatasetBuilderETL

```python
# src/etl/dataset_builder_etl.py
"""Dataset Builder ETL: Joins and pivots consumption data to wide format."""

import pandas as pd
from energizados.etl.pipeline import SourceETL
from energizados.core.exceptions import ETLError


class DatasetBuilderETL(SourceETL):
    """
    ETL that builds a wide-format dataset for fraud detection.
    
    Expected input (from depends_on):
        - maestros: Customer master data
        - consumos: Longitudinal consumption data  
        - inspecciones: Inspection/fraud label data
    
    Output: Wide-format dataset with:
        - Customer attributes from maestros
        - Consumption columns: N_anterior (1-12) from consumos
        - Inspection columns: target, date, etc.
    """
    
    def __init__(
        self,
        name: str,
        input_paths: list = None,
        output_path: str = None,
        # DatasetBuilder-specific parameters
        consumo_key: str = "id_cliente",
        inspeccion_key: str = "id_cliente",
        maestro_key: str = "id_cliente",
        consumo_period_col: str = "periodo",
        inspeccion_period_col: str = "fecha_inspeccion",
        num_periodos: int = 12,
        periods_suffix: str = "_anterior",
        min_num_measures: int = 3,
        min_num_measures_not_zero: int = 1,
        fill_empty_values_cycle: bool = True,
        fill_empty_values_str: str = "sin_dato",
        **kwargs,
    ):
        # Call parent __init__ with minimal params (we handle input ourselves)
        super().__init__(
            name=name,
            input_paths=input_paths or [],
            output_path=output_path,
            mode="concat",  # Not used - we override extract()
            **kwargs,
        )
        
        # DatasetBuilder-specific config
        self.consumo_key = consumo_key
        self.inspeccion_key = inspeccion_key
        self.maestro_key = maestro_key
        self.consumo_period_col = consumo_period_col
        self.inspeccion_period_col = inspeccion_period_col
        self.num_periodos = num_periodos
        self.periods_suffix = periods_suffix
        self.min_num_measures = min_num_measures
        self.min_num_measures_not_zero = min_num_measures_not_zero
        self.fill_empty_values_cycle = fill_empty_values_cycle
        self.fill_empty_values_str = fill_empty_values_str
    
    def extract(self) -> pd.DataFrame:
        """
        Extract data from three sources: maestros, consumos, inspecciones.
        
        Input paths should be resolved by the orchestrator:
            - input_paths[0] -> maestros
            - input_paths[1] -> consumos  
            - input_paths[2] -> inspecciones
        """
        if len(self.input_paths) != 3:
            raise ETLError(
                f"DatasetBuilderETL requires 3 input paths "
                f"(maestros, consumos, inspecciones), got {len(self.input_paths)}"
            )
        
        maestros_path, consumos_path, inspecciones_path = self.input_paths
        
        # Read all three sources
        maestros = pd.read_parquet(maestros_path)
        consumos = pd.read_parquet(consumos_path)
        inspecciones = pd.read_parquet(inspecciones_path)
        
        logger.info(f"  • Maestros: {len(maestros):,} records")
        logger.info(f"  • Consumos: {len(consumos):,} records")
        logger.info(f"  • Inspecciones: {len(inspecciones):,} records")
        
        return {
            "maestros": maestros,
            "consumos": consumos,
            "inspecciones": inspecciones,
        }
    
    def transform(self, df_dict: dict) -> pd.DataFrame:
        """
        Transform: Join and pivot to wide format.
        
        Args:
            df_dict: Dict with 'maestros', 'consumos', 'inspecciones' DataFrames
        """
        maestros = df_dict["maestros"]
        consumos = df_dict["consumos"]
        inspecciones = df_dict["inspecciones"]
        
        # Step 1: Filter consumos to periods BEFORE inspection
        inspecciones = inspecciones.copy()
        inspecciones[self.inspeccion_period_col] = pd.to_datetime(
            inspecciones[self.inspeccion_period_col]
        )
        
        # Extract year-month from inspection date
        inspecciones["insp_year_month"] = (
            inspecciones[self.inspeccion_period_col].dt.year * 100 + 
            inspecciones[self.inspeccion_period_col].dt.month
        )
        
        # Convert consumo period to numeric
        consumos = consumos.copy()
        consumos[self.consumo_period_col] = pd.to_numeric(
            consumos[self.consumo_period_col], errors="coerce"
        )
        
        # Filter: consumo period must be strictly less than inspection period
        merged = inspecciones.merge(
            consumos,
            left_on=[self.inspeccion_key, "insp_year_month"],
            right_on=[self.consumo_key, self.consumo_period_col],
            how="inner",
        )
        
        # Step 2: Calculate rank (months before inspection)
        merged["rank"] = merged["insp_year_month"] - merged[self.consumo_period_col]
        
        # Filter to only the last N periods
        merged = merged[merged["rank"].between(1, self.num_periodos)]
        
        # Step 3: Pivot wide - consumo by rank -> columns
        pivot = merged.pivot_table(
            index=self.consumo_key,
            columns="rank",
            values="consumo",  # Adjust to your actual column name
            aggfunc="first",
        )
        
        # Rename columns: 1 -> "1_anterior", 2 -> "2_anterior", etc.
        pivot.columns = [f"{col}{self.periods_suffix}" for col in pivot.columns]
        pivot = pivot.reset_index()
        
        # Step 4: Merge with maestros (customer attributes)
        result = pivot.merge(
            maestros,
            left_on=self.consumo_key,
            right_on=self.maestro_key,
            how="left",
        )
        
        # Step 5: Merge with inspecciones (target and metadata)
        # Keep latest inspection per customer
        latest_inspecciones = inspecciones.sort_values(
            self.inspeccion_period_col, ascending=False
        ).drop_duplicates(subset=[self.inspeccion_key], keep="first")
        
        result = result.merge(
            latest_inspecciones,
            left_on=self.consumo_key,
            right_on=self.inspeccion_key,
            how="left",
        )
        
        # Step 6: Add auxiliary features
        consumo_cols = [c for c in result.columns if c.endswith(self.periods_suffix)]
        result["num_measures"] = result[consumo_cols].notna().sum(axis=1)
        result["num_measures_not_zero"] = (
            result[consumo_cols].fillna(0) > 0
        ).sum(axis=1)
        
        # Step 7: Filter by minimum measures
        before = len(result)
        result = result[
            (result["num_measures"] >= self.min_num_measures) &
            (result["num_measures_not_zero"] >= self.min_num_measures_not_zero)
        ]
        logger.info(f"  • Filtered {before - len(result):,} rows (min measures)")
        
        # Step 8: Fill empty values
        if self.fill_empty_values_cycle:
            # Forward/backward fill for consumption columns
            consumo_cols_sorted = sorted(
                [c for c in result.columns if c.endswith(self.periods_suffix)]
            )
            result[consumo_cols_sorted] = result[consumo_cols_sorted].ffill(axis=1)
            result[consumo_cols_sorted] = result[consumo_cols_sorted].bfill(axis=1)
        
        # Fill string columns
        str_cols = result.select_dtypes(include=["object"]).columns
        result[str_cols] = result[str_cols].fillna(self.fill_empty_values_str)
        
        # Step 9: Order columns logically
        id_cols = [c for c in result.columns if "id" in c.lower()]
        inspeccion_cols = [c for c in result.columns if "insp" in c.lower() or "target" in c.lower()]
        consumo_cols = [c for c in result.columns if self.periods_suffix in c]
        other_cols = [c for c in result.columns if c not in id_cols + inspeccion_cols + consumo_cols]
        
        result = result[id_cols + inspeccion_cols + consumo_cols + other_cols]
        
        logger.info(f"  ✓ Dataset built: {len(result):,} records, {len(result.columns)} columns")
        return result
    
    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save to parquet format."""
        df.to_parquet(path, index=False)
        logger.info(f"  ✓ Saved dataset to '{path}'")
```

### Wiring in YAML

```yaml
etl:
  # Step 1: Load raw consumption data
  consumos:
    enabled: true
    input: "data/raw/consumos_*.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # Step 2: Load customer master data  
  maestros:
    enabled: true
    input: "data/raw/maestros.csv"
    output: "data/processed/maestros.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # Step 3: Load inspection data
  inspecciones:
    enabled: true
    input: "data/raw/inspecciones.csv"
    output: "data/processed/inspecciones.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  # Step 4: Build wide-format dataset
  dataset_builder:
    enabled: true
    description: "Join and pivot to wide format for ML training"
    input:
      - "@maestros"    # Index 0
      - "@consumos"   # Index 1
      - "@inspecciones" # Index 2
    output: "data/processed/dataset_wide.parquet"
    custom_class: "src.etl.dataset_builder_etl.DatasetBuilderETL"
    params:
      consumo_key: "id_cliente"
      inspeccion_key: "id_cliente"
      maestro_key: "id_cliente"
      consumo_period_col: "periodo"
      inspeccion_period_col: "fecha_inspeccion"
      num_periodos: 12
      periods_suffix: "_anterior"
      min_num_measures: 3
      min_num_measures_not_zero: 1
    depends_on: [maestros, consumos, inspecciones]
```

### Key Points

1. **Extend `SourceETL`** instead of `BaseETL` to inherit logging and path resolution
2. **Override `extract()`** to handle multiple input sources as a dictionary
3. **Override `transform()`** to receive the dictionary and perform join+pivot logic
4. **Use `depends_on`** in YAML to ensure source ETLs run first
5. **Input path order matters**: the orchestrator resolves `@references` to paths in order

### Variations

- **With GeoFeatures**: Add `depends_on: [dataset_builder]` and use `GeoFeaturesETL` after
- **With Negative Sampling**: Add logic in `transform()` to include non-fraud cases
- **With Column Filtering**: Add parameters to filter by zona, region, etc.

## ETL Dependencies with @etl_name Syntax

Reference other ETL outputs using the `@etl_name` syntax in the `input` field:

```yaml
etl:
  step1:
    input: "data/raw/source.csv"
    output: "data/processed/step1.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
 
  step2:
    input: "@step1"  # References step1's output
    output: "data/processed/step2.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    depends_on: ["step1"]  # Explicit dependency
```

## Testing Custom ETLs

```python
# tests/test_custom_etl.py
import pytest
import pandas as pd
from pathlib import Path

from src.data.custom_etl import SimpleFilterETL


@pytest.fixture
def sample_data(temp_dir):
    """Create sample CSV data for testing."""
    data = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'value': [10, 20, None, 40, 50],
        'category': ['A', 'B', 'C', 'D', 'E']
    })
    csv_path = temp_dir / "test_data.csv"
    data.to_csv(csv_path, index=False)
    return csv_path


def test_simple_filter_etl(sample_data, temp_dir):
    """Test SimpleFilterETL removes rows with nulls."""
    output_path = temp_dir / "output.parquet"

    etl = SimpleFilterETL(
        input_path=str(sample_data),
        output_path=str(output_path)
    )

    df = etl.run(str(output_path))

    # Assert row with null is removed
    assert len(df) == 4
    assert df['value'].isnull().sum() == 0

    # Assert output file exists
    assert Path(output_path).exists()
```

Run tests:
```bash
pytest tests/test_custom_etl.py -v
```

## See Also

- [Custom Models](custom-model.md) - Learn about extending with custom models
- [Custom Feature Engineering](custom-feature-engineering.md) - Feature engineering pipeline customization
- [Custom Inference](custom-inference.md) - Inference implementations
- [Security Allowlist](custom-preprocessing.md#the-security-allowlist) - Dynamic import security

---

← [Extending Framework](../extending/) | [Custom Models](custom-model.md) →
