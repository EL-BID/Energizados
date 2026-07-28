from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.pipeline import GeoFeaturesETL

geobr = pytest.importorskip("geobr")


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


def test_geo_cluster_not_in_pipeline_imports():
    """GeoClusterETL must not exist anymore."""
    import energizados.etl.pipeline as m

    assert not hasattr(m, "GeoClusterETL"), "GeoClusterETL should be removed"


def test_include_cluster_false_skips_clustering(tmp_path):
    """When include_cluster=False, geo_cluster is NOT added and hierarchy/distances still work."""
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    output_path = str(tmp_path / "output.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=output_path,
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_cluster=False,
        include_hierarchy=False,
        include_distances=False,
    )
    raw = etl.extract()
    result = etl.transform(raw)

    assert "geo_cluster" not in result.columns


# --- _resolve_hierarchy_levels ---


def test_resolve_hierarchy_levels_true():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    result = _resolve_hierarchy_levels(True)
    assert result == [("estado", "estado"), ("municipio", "municipio"), ("regiao", "regiao")]


def test_resolve_hierarchy_levels_false():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    assert _resolve_hierarchy_levels(False) == []


def test_resolve_hierarchy_levels_list():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    result = _resolve_hierarchy_levels(["estado", "regiao"])
    assert result == [("estado", "estado"), ("regiao", "regiao")]


def test_resolve_hierarchy_levels_single():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    result = _resolve_hierarchy_levels(["municipio"])
    assert result == [("municipio", "municipio")]


def test_resolve_hierarchy_levels_invalid():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    with pytest.raises(ValueError, match="Invalid hierarchy level"):
        _resolve_hierarchy_levels(["estado", "invalid_level"])


def test_resolve_hierarchy_levels_english_aliases():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    # English aliases: display name preserved, data_key resolved to Portuguese
    result = _resolve_hierarchy_levels(["state", "municipality", "region"])
    assert result == [
        ("state", "estado"),
        ("municipality", "municipio"),
        ("region", "regiao"),
    ]


def test_resolve_hierarchy_levels_city_alias():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    result = _resolve_hierarchy_levels(["city"])
    assert result == [("city", "municipio")]


def test_resolve_hierarchy_levels_mixed_languages():
    from energizados.preprocessing.geo_features import _resolve_hierarchy_levels

    result = _resolve_hierarchy_levels(["state", "municipio"])
    assert result == [("state", "estado"), ("municipio", "municipio")]


# --- GeoFeaturesETL with hierarchy_levels list ---


def test_hierarchy_levels_list_only_estado(tmp_path):
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    output_path = str(tmp_path / "output.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=output_path,
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=["estado"],
        include_distances=False,
    )
    raw = etl.extract()
    result = etl.transform(raw)

    assert "geo_cluster" in result.columns
    assert "geo_estado" in result.columns
    assert "geo_municipio" not in result.columns
    assert "geo_regiao" not in result.columns


def test_hierarchy_levels_list_estado_and_regiao(tmp_path):
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    output_path = str(tmp_path / "output.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=output_path,
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=["estado", "regiao"],
        include_distances=False,
    )
    raw = etl.extract()
    result = etl.transform(raw)

    assert "geo_estado" in result.columns
    assert "geo_regiao" in result.columns
    assert "geo_municipio" not in result.columns


def test_hierarchy_levels_empty_list_no_hierarchy_columns(tmp_path):
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    output_path = str(tmp_path / "output.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=output_path,
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=[],
        include_distances=False,
    )
    raw = etl.extract()
    result = etl.transform(raw)

    assert "geo_cluster" in result.columns
    assert "geo_estado" not in result.columns
    assert "geo_municipio" not in result.columns
    assert "geo_regiao" not in result.columns


def test_hierarchy_levels_invalid_raises(tmp_path):
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=str(tmp_path / "output.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=["estado", "invalido"],
        include_distances=False,
    )
    raw = etl.extract()
    with pytest.raises(ValueError, match="Invalid hierarchy level"):
        etl.transform(raw)


# --- _normalize_name ---


def test_normalize_name_removes_accents():
    from energizados.preprocessing.geo_features import _normalize_name

    assert _normalize_name("Florianópolis") == "FLORIANOPOLIS"


def test_normalize_name_handles_multiword_with_accents():
    from energizados.preprocessing.geo_features import _normalize_name

    assert _normalize_name("São José") == "SAO JOSE"


def test_normalize_name_already_normalized():
    from energizados.preprocessing.geo_features import _normalize_name

    assert _normalize_name("LAGES") == "LAGES"


# --- _load_regions_mapping ---


def test_load_regions_mapping_basic(tmp_path):
    from energizados.preprocessing.geo_features import _load_regions_mapping

    csv = tmp_path / "regioes.csv"
    csv.write_text(
        '"REGION";"CITY"\n"Florianopolis";"FLORIANOPOLIS"\n"Blumenau";"BLUMENAU"\n',
        encoding="utf-8",
    )
    mapping = _load_regions_mapping(str(csv))
    assert mapping["FLORIANOPOLIS"] == "Florianopolis"
    assert mapping["BLUMENAU"] == "Blumenau"


def test_load_regions_mapping_normalizes_accented_city(tmp_path):
    from energizados.preprocessing.geo_features import _load_regions_mapping

    csv = tmp_path / "regioes.csv"
    csv.write_text('"REGION";"CITY"\n"Florianopolis";"Florianópolis"\n', encoding="utf-8")
    mapping = _load_regions_mapping(str(csv))
    assert "FLORIANOPOLIS" in mapping


def test_load_regions_mapping_bom_encoding(tmp_path):
    from energizados.preprocessing.geo_features import _load_regions_mapping

    csv = tmp_path / "regioes.csv"
    csv.write_bytes(b'\xef\xbb\xbf"REGION";"CITY"\n"Joinville";"JOINVILLE"\n')
    mapping = _load_regions_mapping(str(csv))
    assert mapping["JOINVILLE"] == "Joinville"


def test_load_regions_mapping_parquet(tmp_path):
    from energizados.preprocessing.geo_features import _load_regions_mapping

    df = pd.DataFrame(
        {"REGION": ["Florianopolis", "Blumenau"], "CITY": ["FLORIANOPOLIS", "BLUMENAU"]}
    )
    parquet_path = tmp_path / "regioes.parquet"
    df.to_parquet(parquet_path, index=False)
    mapping = _load_regions_mapping(str(parquet_path))
    assert mapping["FLORIANOPOLIS"] == "Florianopolis"
    assert mapping["BLUMENAU"] == "Blumenau"


# --- _compute_nearest_city ---


def test_compute_nearest_city_assigns_closest():
    from energizados.preprocessing.geo_features import GeoFeatures

    gf = GeoFeatures(region_cities=["florianopolis", "blumenau"])
    lats = np.array([-27.59, -26.92])
    lons = np.array([-48.55, -49.07])
    valid_mask = np.array([True, True])
    result = gf._compute_nearest_city(lats, lons, valid_mask)
    assert result[0] == "florianopolis"
    assert result[1] == "blumenau"


def test_compute_nearest_city_invalid_points_get_sin_dato():
    from energizados.preprocessing.geo_features import GeoFeatures

    gf = GeoFeatures(region_cities=["florianopolis", "blumenau"])
    lats = np.array([-27.59, np.nan])
    lons = np.array([-48.55, np.nan])
    valid_mask = np.array([True, False])
    result = gf._compute_nearest_city(lats, lons, valid_mask)
    assert result[0] == "florianopolis"
    assert result[1] == "sin_dato"


def test_unknown_region_city_raises_on_fit(tmp_path):
    from energizados.preprocessing.geo_features import GeoFeatures

    df = pd.DataFrame({"lat": [-27.5], "lon": [-48.5]})
    gf = GeoFeatures(
        lat_col="lat",
        lon_col="lon",
        include_hierarchy=False,
        include_distances=False,
        region_cities=["cidade_inexistente"],
    )
    with pytest.raises(ValueError, match="Unknown region_city"):
        gf.fit(df)


# --- regions_file via GeoFeaturesETL ---

_MOCK_GEOCODE = "energizados.preprocessing.geo_features._IBGEGeocoder.geocode_points"


def _make_etl_with_regions_file(tmp_path, csv_content, region_cities=None):
    """Build a GeoFeaturesETL with a temp regions CSV and mocked IBGE."""
    csv_path = tmp_path / "regioes.csv"
    csv_path.write_text(csv_content, encoding="utf-8")

    n = 20
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "latitude": rng.uniform(-29.5, -26.0, n),
            "longitude": rng.uniform(-53.0, -48.5, n),
        }
    )
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test",
        input_paths=[input_path],
        output_path=str(tmp_path / "output.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=["regiao"],
        include_distances=False,
        regions_file=str(csv_path),
        region_cities=region_cities,
    )

    municipios = np.array(["Florianopolis"] * 10 + ["Blumenau"] * 10)
    ufs = np.array(["SC"] * 20)
    regioes = np.array(["Sul"] * 20)

    raw = etl.extract()
    with patch(_MOCK_GEOCODE, return_value=(municipios, ufs, regioes)):
        return etl.transform(raw)


def test_regions_file_assigns_region_from_csv(tmp_path):
    csv = '"REGION";"CITY"\n"Florianopolis";"FLORIANOPOLIS"\n"Blumenau";"BLUMENAU"\n'
    result = _make_etl_with_regions_file(tmp_path, csv)
    assert "geo_regiao" in result.columns
    values = result["geo_regiao"].astype(str).unique().tolist()
    assert set(values) == {"Florianopolis", "Blumenau"}


def test_regions_file_unmatched_municipio_gets_sin_dato(tmp_path):
    # CSV only maps Florianopolis — Blumenau points should get "sin_dato"
    csv = '"REGION";"CITY"\n"Florianopolis";"FLORIANOPOLIS"\n'
    result = _make_etl_with_regions_file(tmp_path, csv)
    assert "sin_dato" in result["geo_regiao"].astype(str).values


def test_regions_file_takes_priority_over_region_cities(tmp_path):
    # regions_file maps to "Florianopolis"/"Blumenau"; region_cities would give
    # different lowercase values — confirm regions_file wins
    csv = '"REGION";"CITY"\n"RegFromFile";"FLORIANOPOLIS"\n"RegFromFile";"BLUMENAU"\n'
    result = _make_etl_with_regions_file(tmp_path, csv, region_cities=["florianopolis", "blumenau"])
    assert all(result["geo_regiao"].astype(str) == "RegFromFile")


# --- _apply_regions_mapping and diagnostics attributes ---


def test_apply_regions_mapping_basic():
    """_apply_regions_mapping normalises both sides and returns correct regions."""
    from energizados.preprocessing.geo_features import GeoFeatures, _normalize_name

    gf = GeoFeatures(include_hierarchy=False, include_distances=False)
    gf.regions_mapping_ = {
        _normalize_name("Florianópolis"): "Florianopolis",
        _normalize_name("Blumenau"): "Blumenau",
    }

    municipios = np.array(["Florianópolis", "Blumenau", "Lages"])
    result = gf._apply_regions_mapping(municipios, log=False)

    assert result[0] == "Florianopolis"
    assert result[1] == "Blumenau"
    assert result[2] == "sin_dato"


def test_apply_regions_mapping_accent_insensitive():
    """IBGE name with accents matches CSV key without accents."""
    from energizados.preprocessing.geo_features import GeoFeatures

    gf = GeoFeatures(include_hierarchy=False, include_distances=False)
    # CSV has plain ASCII, IBGE has accented names
    gf.regions_mapping_ = {
        "FLORIANOPOLIS": "Regiao1",
        "SAO JOSE": "Regiao2",
    }

    municipios = np.array(["Florianópolis", "São José"])
    result = gf._apply_regions_mapping(municipios, log=False)

    assert result[0] == "Regiao1"
    assert result[1] == "Regiao2"


def test_apply_regions_mapping_logging(caplog):
    """_apply_regions_mapping logs matched and unmatched municipalities when log=True."""
    import logging

    from energizados.preprocessing.geo_features import GeoFeatures

    gf = GeoFeatures(include_hierarchy=False, include_distances=False)
    gf.regions_mapping_ = {
        "FLORIANOPOLIS": "Florianopolis",
        "BLUMENAU": "Blumenau",
    }

    municipios = np.array(["Florianópolis", "Blumenau", "Lages"])

    with caplog.at_level(logging.INFO, logger="energizados.preprocessing.geo_features"):
        gf._apply_regions_mapping(municipios, log=True)

    # Check INFO log has match summary
    match_msgs = [r.message for r in caplog.records if "regions_file match" in r.message]
    assert len(match_msgs) == 1
    assert "2/3 municipalities resolved" in match_msgs[0]
    assert "(2 matched, 1 unmatched)" in match_msgs[0]

    # Check WARNING log for unmatched
    warn_msgs = [
        r.message
        for r in caplog.records
        if r.levelno >= logging.WARNING and "Unmatched" in r.message
    ]
    assert len(warn_msgs) == 1
    assert "LAGES" in warn_msgs[0]


def test_fit_populates_unmatched_municipalities(tmp_path):
    """After fit(), unmatched_municipalities_ and matched_municipalities_ are set."""
    from unittest.mock import patch

    from energizados.preprocessing.geo_features import GeoFeatures

    # Create a small regions CSV
    csv_path = tmp_path / "regioes.csv"
    csv_path.write_text('"REGION";"CITY"\n"Regiao1";"FLORIANOPOLIS"\n', encoding="utf-8")

    df = pd.DataFrame({"lat": [-27.59, -26.92, -27.82], "lon": [-48.55, -49.07, -50.33]})

    gf = GeoFeatures(
        lat_col="lat",
        lon_col="lon",
        include_hierarchy=["regiao"],
        include_distances=False,
        regions_file=str(csv_path),
    )

    municipios = np.array(["Florianópolis", "Blumenau", "Lages"])
    ufs = np.array(["SC", "SC", "SC"])
    regioes = np.array(["Sul", "Sul", "Sul"])

    with patch(
        "energizados.preprocessing.geo_features._IBGEGeocoder.geocode_points",
        return_value=(municipios, ufs, regioes),
    ):
        gf.fit(df)

    # Check diagnostics attributes
    assert isinstance(gf.unmatched_municipalities_, list)
    assert isinstance(gf.matched_municipalities_, list)
    assert "FLORIANOPOLIS" in gf.matched_municipalities_
    assert "BLUMENAU" in gf.unmatched_municipalities_
    assert "LAGES" in gf.unmatched_municipalities_


def test_fit_no_regions_file_empty_attributes():
    """Without regions_file, diagnostics attributes are empty lists."""
    from unittest.mock import patch

    from energizados.preprocessing.geo_features import GeoFeatures

    df = pd.DataFrame({"lat": [-27.59], "lon": [-48.55]})

    gf = GeoFeatures(
        lat_col="lat",
        lon_col="lon",
        include_hierarchy=["estado"],
        include_distances=False,
    )

    municipios = np.array(["Florianópolis"])
    ufs = np.array(["SC"])
    regioes = np.array(["Sul"])

    with patch(
        "energizados.preprocessing.geo_features._IBGEGeocoder.geocode_points",
        return_value=(municipios, ufs, regioes),
    ):
        gf.fit(df)

    assert gf.unmatched_municipalities_ == []
    assert gf.matched_municipalities_ == []


# ===================================================================
# R2a: geo_model_path — persist KMeans+scaler on fit, load on predict
# ===================================================================


def test_geo_model_persisted_on_fit(tmp_path):
    """Fitting with geo_model_path saves .pkl + .sig with scaler/kmeans/n_clusters."""
    from energizados.core.utils.secure_pickle import secure_load

    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    model_path = str(tmp_path / "geo_model.pkl")
    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=str(tmp_path / "output.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=False,
        include_distances=False,
        geo_model_path=model_path,
    )
    raw = etl.extract()
    etl.transform(raw)

    assert Path(model_path).exists()
    assert Path(model_path + ".sig").exists()
    model = secure_load(model_path)
    assert "scaler" in model
    assert "kmeans" in model
    assert "n_clusters" in model
    assert model["n_clusters"] == 3


def test_predict_mode_matches_fit_mode(tmp_path):
    """geo_cluster from predict mode (loaded model) == fit mode on same coords."""
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    model_path = str(tmp_path / "geo_model.pkl")

    # ETL #1: fit mode (no file yet -> fits + saves)
    etl1 = GeoFeaturesETL(
        name="train",
        input_paths=[input_path],
        output_path=str(tmp_path / "out1.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=False,
        include_distances=False,
        geo_model_path=model_path,
    )
    raw1 = etl1.extract()
    result1 = etl1.transform(raw1)

    # ETL #2: predict mode (file exists -> loads instead of fitting)
    etl2 = GeoFeaturesETL(
        name="infer",
        input_paths=[input_path],
        output_path=str(tmp_path / "out2.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=False,
        include_distances=False,
        geo_model_path=model_path,
    )
    raw2 = etl2.extract()
    result2 = etl2.transform(raw2)

    np.testing.assert_array_equal(result1["geo_cluster"].values, result2["geo_cluster"].values)


def test_predict_mode_without_file_falls_back_to_fit(tmp_path):
    """geo_model_path pointing at a nonexistent path -> fits normally, no error."""
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=str(tmp_path / "output.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=False,
        include_distances=False,
        geo_model_path=str(tmp_path / "nonexistent" / "geo_model.pkl"),
    )
    raw = etl.extract()
    result = etl.transform(raw)
    assert "geo_cluster" in result.columns


def test_no_geo_model_path_keeps_old_behavior(tmp_path):
    """Without geo_model_path, no file is written (backward compatible)."""
    df = _make_df(n=30)
    input_path = str(tmp_path / "input.parquet")
    df.to_parquet(input_path, index=False)

    etl = GeoFeaturesETL(
        name="test_geo",
        input_paths=[input_path],
        output_path=str(tmp_path / "output.parquet"),
        lat_col="latitude",
        lon_col="longitude",
        n_clusters=3,
        include_hierarchy=False,
        include_distances=False,
    )
    raw = etl.extract()
    result = etl.transform(raw)
    assert "geo_cluster" in result.columns
    # No model file should have been written anywhere in tmp_path
    assert not list(tmp_path.glob("*.pkl"))


# ===================================================================
# R2b: chunked geocode_points — result-preserving equivalence
# ===================================================================


def test_geocode_points_chunked_equals_unchunked(tmp_path):
    """Chunked geocode_points (chunk_size=5) == unchunked (chunk_size=10_000)."""
    import geopandas as gpd
    from shapely.geometry import box

    from energizados.preprocessing.geo_features import _IBGEGeocoder

    # Synthetic municipios: 3 non-overlapping boxes over SC-ish coords
    synthetic_gdf = gpd.GeoDataFrame(
        {
            "name_muni": ["MuniA", "MuniB", "MuniC"],
            "abbrev_state": ["SC", "SC", "SC"],
            "geometry": [
                box(-49.5, -28.0, -48.5, -27.0),
                box(-48.5, -28.0, -47.5, -27.0),
                box(-49.5, -29.0, -48.5, -28.0),
            ],
        },
        crs="EPSG:4326",
    )

    rng = np.random.default_rng(99)
    n = 50
    lats = rng.uniform(-29.0, -27.0, n)
    lons = rng.uniform(-49.5, -47.5, n)

    with patch(
        "energizados.preprocessing.geo_features._IBGEGeocoder._load_municipios",
        return_value=synthetic_gdf,
    ):
        mun_chunked, uf_chunked, reg_chunked = _IBGEGeocoder.geocode_points(
            lats, lons, chunk_size=5
        )
        mun_full, uf_full, reg_full = _IBGEGeocoder.geocode_points(lats, lons, chunk_size=10_000)

    np.testing.assert_array_equal(mun_chunked, mun_full)
    np.testing.assert_array_equal(uf_chunked, uf_full)
    np.testing.assert_array_equal(reg_chunked, reg_full)
