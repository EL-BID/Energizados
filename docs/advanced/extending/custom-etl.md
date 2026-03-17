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

Wire it in `config/etls.yaml`:
```yaml
etls:
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

## Advanced Example: MultiSourceETL with Error Handling

```python
# src/data/multi_source_etl.py
from energizados.etl.base import BaseETL
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MultiSourceETL(BaseETL):
    """ETL that merges multiple sources with error handling."""

    def __init__(self, source_paths=None, merge_key=None, **kwargs):
        super().__init__(**kwargs)
        self.source_paths = source_paths or []
        self.merge_key = merge_key

    def extract(self) -> pd.DataFrame:
        """Extract and merge multiple data sources."""
        dfs = []
        for path in self.source_paths:
            try:
                if path.endswith('.csv'):
                    df = pd.read_csv(path)
                elif path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                else:
                    raise ValueError(f"Unsupported file format: {path}")
                dfs.append(df)
                logger.info(f"Loaded {len(df)} rows from {path}")
            except Exception as e:
                logger.error(f"Failed to load {path}: {e}")
                raise

        if not dfs:
            raise ValueError("No data sources loaded successfully")

        return dfs

    def transform(self, df_list: list) -> pd.DataFrame:
        """Merge all DataFrames on the specified key."""
        if len(df_list) == 1:
            return df_list[0]

        merged = df_list[0]
        for df in df_list[1:]:
            merged = pd.merge(
                merged,
                df,
                on=self.merge_key,
                how='left'
            )
            logger.info(f"Merged: {len(merged)} rows")

        return merged

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save to parquet with compression."""
        df.to_parquet(path, index=False, compression='snappy')
        logger.info(f"Saved {len(df)} rows to {path}")
```

Wire it in `config/etls.yaml` with dependencies:
```yaml
etls:
  consumos:
    enabled: true
    input: "data/raw/consumos.csv"
    output: "data/processed/consumos.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []

  clientes:
    enabled: true
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
    custom_class: "src.data.multi_source_etl.MultiSourceETL"
    params:
      source_paths: ["@consumos", "@clientes"]
      merge_key: "id_cliente"
    depends_on: ["consumos", "clientes"]
```

## ETL Dependencies with @etl_name Syntax

Reference other ETL outputs using the `@etl_name` syntax in the `input` field:

```yaml
etls:
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
