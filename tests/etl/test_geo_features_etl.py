import numpy as np
import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.pipeline import GeoFeaturesETL


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
        name="test",
        input_paths=[input_path],
        output_path=str(tmp_path / "out.parquet"),
        lat_col="latitude",
        lon_col="longitude",
    )
    raw = etl.extract()
    with pytest.raises(ETLError, match="latitude"):
        etl.transform(raw)


def test_too_few_valid_coords_raises(tmp_path):
    df = _make_df(n=5, valid=True)  # fewer than minimum 10
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)
    etl = GeoFeaturesETL(
        name="test",
        input_paths=[input_path],
        output_path=str(tmp_path / "out.parquet"),
        lat_col="latitude",
        lon_col="longitude",
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


@pytest.mark.xfail(reason="GeoClusterETL removed in Task 2", strict=True)
def test_geo_cluster_not_in_pipeline_imports():
    """GeoClusterETL must not exist anymore."""
    import energizados.etl.pipeline as m

    assert not hasattr(m, "GeoClusterETL"), "GeoClusterETL should be removed"
