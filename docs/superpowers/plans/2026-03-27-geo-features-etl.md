# GeoFeaturesETL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify `GeoClusterETL` and the `geo_features` global transformer into a single `GeoFeaturesETL` in `etl/pipeline.py`, move config to `etl.yaml`, remove `GeoClusterETL` and `GeoCluster` entirely, and update all templates, docs, and tests.

**Architecture:** `GeoFeaturesETL` orchestrates two existing pieces: KMeans clustering (inline, from `GeoClusterETL` logic) + geographic hierarchy/distances (via `GeoFeatures(include_target_encoding=False).fit_transform()`). Target encoding is explicitly disabled — it belongs in feature engineering where a train/val/test split already exists. `GeoCluster` (sklearn transformer) and `GeoClusterETL` are deleted.

**Tech Stack:** scikit-learn KMeans, `GeoFeatures` transformer, pandas, IBGE/geobr shapefiles.

---

## File Map

| Action | File | What changes |
|--------|------|-------------|
| Modify | `src/energizados/etl/pipeline.py` | Add `GeoFeaturesETL`, delete `GeoClusterETL` |
| Modify | `src/energizados/preprocessing/geo_features.py` | Delete `GeoCluster` class (lines 279–377) |
| Modify | `src/energizados/feature_engineering/default.py` | Remove `"geo_features"` entry from transformer map |
| Modify | `src/energizados/preprocessing/__init__.py` | Remove `GeoCluster` export if present |
| Modify | `src/energizados/templates/config/etl.yaml.tpl` | Replace `geo_cluster` block with `geo_features` |
| Modify | `src/energizados/templates/config/train.yaml.tpl` | Remove commented `geo_features` block |
| Modify | `docs/user-guide/configuration/etl.md` | Add `GeoFeaturesETL` reference section |
| Modify | `docs/user-guide/configuration/train.md` | Remove `geo_features` from global_transformers section |
| Modify | `CLAUDE.md` | Update ETL class table |
| Modify | `.proyects/celesc/config/etl.yaml` | Rename `geo_cluster` → `geo_features`, add geo params |
| Create | `tests/etl/test_geo_features_etl.py` | Unit tests for `GeoFeaturesETL` |

---

## Task 1: Add `GeoFeaturesETL` to `etl/pipeline.py`

**Files:**
- Modify: `src/energizados/etl/pipeline.py`

- [ ] **Step 1: Write the failing test**

Create `tests/etl/test_geo_features_etl.py`:

```python
import numpy as np
import pandas as pd
import pytest

from energizados.etl.pipeline import GeoFeaturesETL
from energizados.core.exceptions import ETLError


def _make_df(n=20, valid=True):
    """DataFrame with lat/lon columns and a few extra columns."""
    rng = np.random.default_rng(42)
    if valid:
        lats = rng.uniform(-29.5, -26.0, n)
        lons = rng.uniform(-53.0, -48.5, n)
    else:
        lats = np.zeros(n)
        lons = np.zeros(n)
    return pd.DataFrame({"latitude": lats, "longitude": lons, "value": rng.integers(0, 100, n)})


def _make_etl(tmp_path, df, *, n_clusters=3, include_hierarchy=False, include_distances=False):
    """Helper to build, run, and return the result of GeoFeaturesETL."""
    input_path = str(tmp_path / "input.parquet")
    output_path = str(tmp_path / "output.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=output_path,
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=n_clusters,
        include_hierarchy=include_hierarchy,
        include_distances=include_distances,
    )
    raw = etl.extract()
    transformed = etl.transform(raw)
    etl.load(transformed, output_path)
    return transformed


def test_geo_cluster_column_added(tmp_path):
    df = _make_df(n=30)
    result = _make_etl(tmp_path, df, n_clusters=3)
    assert "geo_cluster" in result.columns
    assert result["geo_cluster"].dtype == int


def test_invalid_coords_get_minus_one(tmp_path):
    df = _make_df(n=20, valid=False)
    # Force enough valid rows to satisfy minimum
    valid = _make_df(n=20, valid=True)
    mixed = pd.concat([df.head(5), valid], ignore_index=True)
    result = _make_etl(tmp_path, mixed, n_clusters=3)
    # First 5 rows had zero coords → label -1
    assert (result.loc[:4, "geo_cluster"] == -1).all()


def test_missing_lat_col_raises(tmp_path):
    df = pd.DataFrame({"wrong_col": [1.0, 2.0], "longitude": [-50.0, -51.0]})
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)
    etl = GeoFeaturesETL(
        name="test", input_paths=[input_path], output_path=str(tmp_path / "out.parquet"),
        lat_col="latitude", lon_col="longitude",
    )
    raw = etl.extract()
    with pytest.raises(ETLError, match="latitude"):
        etl.transform(raw)


def test_too_few_valid_coords_raises(tmp_path):
    df = _make_df(n=5, valid=True)  # fewer than minimum 10
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)
    etl = GeoFeaturesETL(
        name="test", input_paths=[input_path], output_path=str(tmp_path / "out.parquet"),
        lat_col="latitude", lon_col="longitude",
    )
    raw = etl.extract()
    with pytest.raises(ETLError, match="valid coordinates"):
        etl.transform(raw)


def test_output_saved_to_disk(tmp_path):
    df = _make_df(n=30)
    _make_etl(tmp_path, df, n_clusters=3)
    assert (tmp_path / "output.parquet").exists()
    loaded = pd.read_parquet(tmp_path / "output.parquet")
    assert "geo_cluster" in loaded.columns


def test_geo_cluster_not_in_pipeline_imports():
    """GeoClusterETL must not exist anymore."""
    import energizados.etl.pipeline as m
    assert not hasattr(m, "GeoClusterETL"), "GeoClusterETL should be removed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/vvv/Develop/bid/energizados
pytest tests/etl/test_geo_features_etl.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError — `GeoFeaturesETL` does not exist yet.

- [ ] **Step 3: Add `GeoFeaturesETL` to `etl/pipeline.py`**

Append after the last ETL class (after `GeoClusterETL`, before the end of the module or after line 589). Do **not** remove `GeoClusterETL` yet — that's Task 2.

```python
class GeoFeaturesETL(BaseETL):
    """ETL that adds geographic features and cluster labels from lat/lon coordinates.

    Combines geographic clustering (KMeans → ``geo_cluster`` column) with IBGE
    geographic hierarchy (``geo_estado``, ``geo_municipio``, ``geo_regiao``) and
    optional distance features. Target encoding is intentionally excluded — run it
    in feature engineering where the train/val/test split is already in place.

    Run this ETL after the main dataset-building ETL and before training.

    Args:
        name: ETL name.
        input_paths: List with one path to the input file.
        output_path: Path to save the enriched dataset.
        lat_col: Latitude column name (default: ``"latitud"``).
        lon_col: Longitude column name (default: ``"longitud"``).
        n_clusters: Number of geographic KMeans clusters (default: ``10``).
        random_state: Random seed for KMeans (default: ``42``).
        include_hierarchy: Add ``geo_estado``, ``geo_municipio``, ``geo_regiao``
            columns via IBGE spatial join (default: ``True``).
        include_distances: Add haversine distance columns to reference cities
            (default: ``True``).
        distance_cities: List of city names for distance calculation. If ``None``,
            uses the top-5 default. Available cities: sao_paulo, rio_de_janeiro,
            brasilia, salvador, belo_horizonte, fortaleza, recife, curitiba,
            manaus, porto_alegre, florianopolis, blumenau, joinville, criciuma,
            chapeco, itajai, lages.
        include_coords: Keep original lat/lon columns in output (default: ``False``).
        cache_dir: Directory to persist IBGE shapefiles on disk (default: ``None``).
        **kwargs: Additional parameters (ignored).

    Example YAML:

    .. code-block:: yaml

        geo_features:
          enabled: true
          input: "@dataset_builder"
          output: "data/processed/dataset_with_geo.parquet"
          custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
          params:
            lat_col: "latitude"
            lon_col: "longitude"
            n_clusters: 10
            include_hierarchy: true
            include_distances: true
            distance_cities:
              - sao_paulo
              - rio_de_janeiro
              - brasilia
            include_coords: false
            cache_dir: ".cache/ibge"
          depends_on: [dataset_builder]
    """

    def __init__(
        self,
        name: str,
        input_paths: List[str],
        output_path: Optional[str] = None,
        lat_col: str = "latitud",
        lon_col: str = "longitud",
        n_clusters: int = 10,
        random_state: int = 42,
        include_hierarchy: bool = True,
        include_distances: bool = True,
        distance_cities: Optional[List[str]] = None,
        include_coords: bool = False,
        cache_dir: Optional[str] = None,
        **kwargs,
    ):
        self.name = name
        self.input_paths = input_paths
        self.output_path = output_path
        self.lat_col = lat_col
        self.lon_col = lon_col
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.include_hierarchy = include_hierarchy
        self.include_distances = include_distances
        self.distance_cities = distance_cities
        self.include_coords = include_coords
        self.cache_dir = cache_dir

    def extract(self) -> pd.DataFrame:
        """Read input file."""
        if not self.input_paths:
            raise ETLError(f"GeoFeaturesETL '{self.name}': input_paths is empty")

        from energizados.core.utils.secure_pickle import validate_no_traversal

        path = self.input_paths[0]
        validate_no_traversal(path, label=f"ETL '{self.name}' input")
        source_file = Path(path)

        if not source_file.exists():
            raise ETLError(f"File not found: {path}")

        if source_file.suffix in [".parquet", ".pq"]:
            df = pd.read_parquet(path)
        elif source_file.suffix == ".csv":
            df = pd.read_csv(path)
        else:
            raise ETLError(f"Unsupported format: {source_file.suffix}")

        logger.info("  • Read %d records from '%s'", len(df), source_file.name)
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append geo_cluster and optional geographic feature columns."""
        import numpy as np
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        df = df.copy()

        if self.lat_col not in df.columns or self.lon_col not in df.columns:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': columns '{self.lat_col}' or "
                f"'{self.lon_col}' not found. Available: {list(df.columns)}"
            )

        lats = pd.to_numeric(df[self.lat_col], errors="coerce").values
        lons = pd.to_numeric(df[self.lon_col], errors="coerce").values
        valid_mask = ~(np.isnan(lats) | np.isnan(lons) | ((lats == 0) & (lons == 0)))

        n_valid = int(valid_mask.sum())
        if n_valid < 10:
            raise ETLError(
                f"GeoFeaturesETL '{self.name}': only {n_valid} valid coordinates found. "
                "Need at least 10 to fit clusters."
            )

        # --- Geographic clustering ---
        coords = np.column_stack([lats[valid_mask], lons[valid_mask]])
        n_clusters = min(self.n_clusters, n_valid)

        scaler = StandardScaler()
        coords_scaled = scaler.fit_transform(coords)

        kmeans = KMeans(n_clusters=n_clusters, random_state=self.random_state, n_init=10)
        kmeans.fit(coords_scaled)

        labels = np.full(len(df), -1, dtype=int)
        labels[valid_mask] = kmeans.predict(coords_scaled)
        df["geo_cluster"] = labels

        invalid_count = int((~valid_mask).sum())
        logger.info(
            "  ✓ GeoFeaturesETL: %d clusters fitted on %d valid coordinates (%d → label -1)",
            n_clusters,
            n_valid,
            invalid_count,
        )

        # --- Geographic hierarchy and distances ---
        if self.include_hierarchy or self.include_distances:
            from energizados.preprocessing.geo_features import GeoFeatures

            transformer = GeoFeatures(
                lat_col=self.lat_col,
                lon_col=self.lon_col,
                include_hierarchy=self.include_hierarchy,
                include_target_encoding=False,
                include_distances=self.include_distances,
                distance_cities=self.distance_cities,
                include_coords=self.include_coords,
                cache_dir=self.cache_dir,
            )
            df = transformer.fit_transform(df)
            logger.info("  ✓ GeoFeaturesETL: geographic features added")

        return df

    def load(self, df: pd.DataFrame, path: str) -> None:
        """Save enriched dataset."""
        from energizados.core.utils.secure_pickle import validate_no_traversal

        validate_no_traversal(path, label=f"ETL '{self.name}' output")
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix in [".parquet", ".pq"]:
            df.to_parquet(path, index=False)
        elif output_path.suffix == ".csv":
            df.to_csv(path, index=False)
        else:
            df.to_parquet(str(output_path.with_suffix(".parquet")), index=False)

        logger.info("  ✓ Saved %d records to '%s'", len(df), path)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/etl/test_geo_features_etl.py -v -k "not geo_cluster_not_in"
```

Expected: all tests pass except `test_geo_cluster_not_in_pipeline_imports` (GeoClusterETL still exists — removed in Task 2).

- [ ] **Step 5: Commit**

```bash
git add src/energizados/etl/pipeline.py tests/etl/test_geo_features_etl.py
git commit -m "feat: add GeoFeaturesETL combining clustering and geographic features"
```

---

## Task 2: Remove `GeoClusterETL` and `GeoCluster`

**Files:**
- Modify: `src/energizados/etl/pipeline.py` — delete `GeoClusterETL` class (lines 442–589)
- Modify: `src/energizados/preprocessing/geo_features.py` — delete `GeoCluster` class (lines 279–377)
- Modify: `src/energizados/preprocessing/__init__.py` — remove `GeoCluster` from exports

- [ ] **Step 1: Remove `GeoClusterETL` from `etl/pipeline.py`**

Delete the entire `GeoClusterETL` class (currently lines 442–589) and remove its mention from the module docstring (line 6).

The module docstring at the top lists the available classes — update it:

```python
# Before (line 6):
# - GeoClusterETL: Adds a geo_cluster column via KMeans on lat/lon coordinates.

# After — replace with:
# - GeoFeaturesETL: Adds geo_cluster + geographic hierarchy and distance features.
```

- [ ] **Step 2: Remove `GeoCluster` from `preprocessing/geo_features.py`**

Delete the entire `GeoCluster` class (lines 279–377, the blank line at 378 included).

- [ ] **Step 3: Remove `GeoCluster` from `preprocessing/__init__.py`**

In `src/energizados/preprocessing/__init__.py`, remove:
- The import line: `from energizados.preprocessing.geo_features import GeoFeatures` — **keep** `GeoFeatures`, only remove `GeoCluster` if it appears separately.
- The `"GeoCluster"` entry from `__all__` if present.

Current file has:
```python
from energizados.preprocessing.geo_features import GeoFeatures
    "GeoFeatures",
```

`GeoCluster` is not exported there. No change needed to `__init__.py`.

- [ ] **Step 4: Run full test for removal**

```bash
pytest tests/etl/test_geo_features_etl.py -v
```

Expected: all 6 tests pass, including `test_geo_cluster_not_in_pipeline_imports`.

- [ ] **Step 5: Run broader test suite to check for regressions**

```bash
pytest tests/ -v --ignore=tests/test_e2e_pipeline.py -x -q 2>&1 | tail -20
```

Expected: all pass (no references to `GeoClusterETL` or `GeoCluster` in other tests).

- [ ] **Step 6: Commit**

```bash
git add src/energizados/etl/pipeline.py src/energizados/preprocessing/geo_features.py
git commit -m "feat: remove GeoClusterETL and GeoCluster, replaced by GeoFeaturesETL"
```

---

## Task 3: Remove `geo_features` from feature engineering

**Files:**
- Modify: `src/energizados/feature_engineering/default.py` — remove `"geo_features"` entry

`GeoFeatures` is now an ETL concern. Remove the transformer map entry so users get a clear error if they mistakenly configure it under `global_transformers` instead of in `etl.yaml`.

- [ ] **Step 1: Remove the `"geo_features"` entry from `default.py`**

In `src/energizados/feature_engineering/default.py`, delete lines 88–106:

```python
        "geo_features": (
            GeoFeatures,
            {
                "lat_col": "latitud",
                "lon_col": "longitud",
                "include_hierarchy": True,
                "include_target_encoding": True,
                "te_w": 20,
                "include_distances": True,
                "distance_cities": [
                    "sao_paulo",
                    "rio_de_janeiro",
                    "brasilia",
                    "salvador",
                    "belo_horizonte",
                ],
                "include_coords": False,
            },
        ),
```

Also remove the now-unused import at line 16:

```python
from energizados.preprocessing.geo_features import GeoFeatures
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/test_default_feature_engineering.py -v -q
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add src/energizados/feature_engineering/default.py
git commit -m "feat: remove geo_features from feature engineering transformer map"
```

---

## Task 4: Update config templates

**Files:**
- Modify: `src/energizados/templates/config/etl.yaml.tpl`
- Modify: `src/energizados/templates/config/train.yaml.tpl`

- [ ] **Step 1: Replace `geo_cluster` block in `etl.yaml.tpl`**

Find the block (lines 135–149):

```yaml
  # # ETL 7: Geographic clustering - assigns geo_cluster column via KMeans on lat/lon.
  # # Run AFTER your main ETL and BEFORE training.
  # # Required if using method: "stratified_time" in split config.
  # geo_cluster:
  #   enabled: false
  #   description: "Assign geographic clusters for stratified temporal split"
  #   input: "data/processed/sample_dataset.parquet"
  #   output: "data/processed/sample_dataset_with_clusters.parquet"
  #   custom_class: "energizados.etl.pipeline.GeoClusterETL"
  #   params:
  #     n_clusters: 10        # number of geographic clusters
  #     lat_col: "latitude"   # latitude column name
  #     lon_col: "longitude"  # longitude column name
  #     random_state: 42
  #   depends_on: []
```

Replace with:

```yaml
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
```

- [ ] **Step 2: Remove `geo_features` block from `train.yaml.tpl`**

Delete lines 168–185:

```yaml
        # Geographic features from lat/lon (uses IBGE shapefiles via geobr)
        # Generates: geo_estado, geo_municipio, geo_regiao + target encoding + distances
        # Available distance_cities: sao_paulo, rio_de_janeiro, brasilia, salvador,
        #   belo_horizonte, fortaleza, recife, curitiba, manaus, porto_alegre,
        #   florianopolis, blumenau, joinville, criciuma, chapeco, itajai, lages
        # - geo_features:
        #     lat_col: "latitud"
        #     lon_col: "longitud"
        #     include_hierarchy: true       # geo_estado, geo_municipio, geo_regiao
        #     include_target_encoding: true # target-encoded versions of hierarchy cols
        #     te_w: 20                      # smoothing weight for target encoding
        #     include_distances: true       # distances to reference cities
        #     distance_cities:
        #       - sao_paulo
        #       - rio_de_janeiro
        #       - brasilia
        #     include_coords: false         # keep lat/lon in output
        #     cache_dir: ".cache/ibge"      # persist IBGE shapefiles to disk (avoids re-download)
```

Replace with a short reference comment:

```yaml
        # Geographic features (geo_cluster, hierarchy, distances) are now configured
        # as an ETL step in etl.yaml using GeoFeaturesETL.
        # For target encoding of geographic columns, use GeoFeatures via custom_class.
```

- [ ] **Step 3: Commit**

```bash
git add src/energizados/templates/config/etl.yaml.tpl src/energizados/templates/config/train.yaml.tpl
git commit -m "feat: update config templates for GeoFeaturesETL"
```

---

## Task 5: Update celesc project config

**Files:**
- Modify: `.proyects/celesc/config/etl.yaml`

- [ ] **Step 1: Replace `geo_cluster` with `geo_features` in celesc etl.yaml**

Current block (lines 80–92):

```yaml
  geo_cluster:
    enabled: true
    description: "Asigna clusters geográficos (KMeans sobre lat/lon) para split estratificado temporal"
    input: "@dataset_builder"
    output: "data/processed/celesc_dataset_with_clusters.parquet"
    custom_class: "energizados.etl.pipeline.GeoClusterETL"
    params:
      n_clusters: 16
      lat_col: "latitude"
      lon_col: "longitude"
      random_state: 42
    depends_on:
      - dataset_builder
```

Replace with:

```yaml
  geo_features:
    enabled: true
    description: "Geographic features: clusters (KMeans), IBGE hierarchy and distances"
    input: "@dataset_builder"
    output: "data/processed/celesc_dataset_with_geo.parquet"
    custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
    params:
      n_clusters: 16
      lat_col: "latitude"
      lon_col: "longitude"
      random_state: 42
      include_hierarchy: true
      include_distances: true
      distance_cities:
        - sao_paulo
        - rio_de_janeiro
        - brasilia
      include_coords: false
      cache_dir: ".cache/ibge"
    depends_on:
      - dataset_builder
```

Also update any downstream ETL that uses `@geo_cluster` → `@geo_features`, and any `depends_on: [geo_cluster]` → `depends_on: [geo_features]`.

- [ ] **Step 2: Search for downstream references**

```bash
grep -n "geo_cluster\|celesc_dataset_with_clusters" /home/vvv/Develop/bid/energizados/.proyects/celesc/config/etl.yaml
```

Update any occurrences in `input:` or `depends_on:` fields.

- [ ] **Step 3: Update train configs referencing old output path**

```bash
grep -rn "celesc_dataset_with_clusters" /home/vvv/Develop/bid/energizados/.proyects/celesc/config/
```

Update any `input_path` referencing `celesc_dataset_with_clusters.parquet` → `celesc_dataset_with_geo.parquet`.

- [ ] **Step 4: Commit**

```bash
git add .proyects/celesc/config/
git commit -m "feat: migrate celesc config from geo_cluster to geo_features ETL"
```

---

## Task 6: Update documentation

**Files:**
- Modify: `docs/user-guide/configuration/etl.md`
- Modify: `docs/user-guide/configuration/train.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add `GeoFeaturesETL` section to `etl.md`**

Find the `## Custom ETL Classes` section (around line 365). Insert before it:

```markdown
## GeoFeaturesETL

Adds geographic features from latitude/longitude coordinates. Combines KMeans geographic
clustering, IBGE administrative hierarchy, and haversine distance features in a single ETL step.
Run after the main dataset-building ETL and before training.

**Generated columns:**

| Column | Type | Description |
|--------|------|-------------|
| `geo_cluster` | int | KMeans cluster label (−1 for invalid/zero coordinates) |
| `geo_estado` | str | Brazilian state (UF) from IBGE spatial join |
| `geo_municipio` | str | Municipality from IBGE spatial join |
| `geo_regiao` | str | Macro region (Norte, Nordeste, Sudeste, Sul, Centro-Oeste) |
| `geo_dist_capital_estado` | float | Haversine distance to state capital (km) |
| `geo_dist_{city}` | float | Haversine distance to each city in `distance_cities` (km) |

> Unmatched coordinates (outside Brazil or with invalid values) get `"sin_dato"` for
> hierarchy columns and `−1` for `geo_cluster`.

```yaml
geo_features:
  enabled: true
  input: "@dataset_builder"
  output: "data/processed/dataset_with_geo.parquet"
  custom_class: "energizados.etl.pipeline.GeoFeaturesETL"
  params:
    lat_col: "latitude"
    lon_col: "longitude"
    n_clusters: 10
    random_state: 42
    include_hierarchy: true
    include_distances: true
    distance_cities:
      - sao_paulo
      - rio_de_janeiro
      - brasilia
    include_coords: false
    cache_dir: ".cache/ibge"
  depends_on: [dataset_builder]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lat_col` | string | `"latitud"` | Latitude column name |
| `lon_col` | string | `"longitud"` | Longitude column name |
| `n_clusters` | int | `10` | Number of KMeans geographic clusters |
| `random_state` | int | `42` | Random seed for KMeans |
| `include_hierarchy` | bool | `true` | Add IBGE hierarchy columns |
| `include_distances` | bool | `true` | Add distance-to-city columns |
| `distance_cities` | list | top-5 | Cities for distance calculation (see available list below) |
| `include_coords` | bool | `false` | Keep original lat/lon columns in output |
| `cache_dir` | string | `null` | Directory to persist IBGE shapefiles on disk |

**Available cities for `distance_cities`:**

`sao_paulo`, `rio_de_janeiro`, `brasilia`, `salvador`, `belo_horizonte`, `fortaleza`,
`recife`, `curitiba`, `manaus`, `porto_alegre`, `florianopolis`, `blumenau`, `joinville`,
`criciuma`, `chapeco`, `itajai`, `lages`

> **Note:** `include_hierarchy` and `include_distances` require the `geobr` package.
> Set `cache_dir` to avoid re-downloading IBGE shapefiles on every run (recommended).

**Relationship with `stratified_time` split:** the `geo_cluster` column produced by this ETL
is required when using `method: stratified_time` in `train.yaml`.
```

- [ ] **Step 2: Update `train.md` — remove `geo_features` global transformer section**

Remove lines 317–355 (the `#### geo_features` section including the parameter table and note).

Replace with a short pointer:

```markdown
#### geo_features (moved to ETL)

Geographic features (hierarchy, distances, clustering) are now configured as an ETL step
using `GeoFeaturesETL` in `etl.yaml`. See [ETL configuration → GeoFeaturesETL](etl.md#geofeaturesletl).

To apply **target encoding** of geographic columns (e.g. `geo_estado_prob`), use
`GeoFeatures` directly via `custom_class` in `global_transformers`.
```

- [ ] **Step 3: Update `CLAUDE.md` ETL class table**

Find the table row for `GeoClusterETL`:

```markdown
- `GeoClusterETL`: Assigns geographic cluster labels via KMeans on lat/lon coordinates. Appends a `geo_cluster` (int) column. Run after the main ETL and before training so the column is available for `stratified_time` splits. Points with missing/zero coords get label `-1`. `custom_class: "energizados.etl.pipeline.GeoClusterETL"`. Params: `n_clusters` (default: 10), `lat_col`, `lon_col`, `random_state`.
```

Replace with:

```markdown
- `GeoFeaturesETL`: Adds geographic features from lat/lon coordinates. Appends `geo_cluster` (int, KMeans), IBGE hierarchy (`geo_estado`, `geo_municipio`, `geo_regiao`), and haversine distance columns. Run after the main dataset ETL and before training. Required if using `stratified_time` split. Points with invalid/zero coords get `geo_cluster=-1` and `"sin_dato"` for hierarchy. `custom_class: "energizados.etl.pipeline.GeoFeaturesETL"`. Params: `n_clusters` (default: 10), `lat_col`, `lon_col`, `random_state`, `include_hierarchy` (bool), `include_distances` (bool), `distance_cities` (list), `include_coords` (bool), `cache_dir` (str).
```

Also update the `geo_features` global_transformers table row in CLAUDE.md to remove it or add a note pointing to the ETL.

Find:
```markdown
| `geo_features` | Geographic features from lat/lon: estado, município, região, distances to capitals/cities, target encoding | ...
```

Replace `| `geo_features` | ... |` row with:

```markdown
| `geo_features` | **Moved to ETL** — use `GeoFeaturesETL` in `etl.yaml`. For target encoding of geographic columns only, use `GeoFeatures` via `custom_class`. | — |
```

- [ ] **Step 4: Commit**

```bash
git add docs/user-guide/configuration/etl.md docs/user-guide/configuration/train.md CLAUDE.md
git commit -m "docs: update documentation for GeoFeaturesETL migration"
```

---

## Self-Review

**Spec coverage:**
- ✅ New `GeoFeaturesETL` class (Task 1)
- ✅ Remove `GeoClusterETL` and `GeoCluster` (Task 2)
- ✅ Remove `geo_features` from feature engineering (Task 3)
- ✅ Update templates etl.yaml.tpl and train.yaml.tpl (Task 4)
- ✅ Update celesc project config (Task 5)
- ✅ Update docs/user-guide/configuration/etl.md (Task 6)
- ✅ Update docs/user-guide/configuration/train.md (Task 6)
- ✅ Update CLAUDE.md (Task 6)
- ✅ Tests for GeoFeaturesETL (Task 1)

**Type consistency:** `GeoFeaturesETL` uses the same constructor signature pattern as `GeoClusterETL` (name, input_paths, output_path, **kwargs). `GeoFeatures` is imported lazily inside `transform()` to avoid loading geobr at ETL construction time.

**No placeholders:** All code blocks are complete and runnable.
