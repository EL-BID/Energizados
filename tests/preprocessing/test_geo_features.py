"""Tests for the GeoFeatures transformer's clustering responsibility.

These cover the NEW behaviour introduced by ADR-0001: GeoFeatures owns KMeans
clustering (moved out of GeoFeaturesETL) with pure scikit-learn semantics —
``fit`` learns without persisting, ``transform`` applies, ``save``/``load`` carry
the KMeans+scaler model. ``include_cluster`` defaults to ``False`` so existing
``global_transformers`` usage (hierarchy/distances only) is unchanged.

Clustering is independent of IBGE geocoding, so these tests run with
``include_hierarchy=False`` / ``include_distances=False`` and need no geobr mock.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from energizados.preprocessing.geo_features import GeoFeatures


def _make_df(n=30, valid=True, seed=42):
    """DataFrame with SC-ish lat/lon columns (no geocoding needed)."""
    rng = np.random.default_rng(seed)
    if valid:
        lats = rng.uniform(-29.5, -26.0, n)
        lons = rng.uniform(-53.0, -48.5, n)
    else:
        lats = np.zeros(n)
        lons = np.zeros(n)
    return pd.DataFrame({"latitude": lats, "longitude": lons, "value": rng.integers(0, 100, n)})


def _no_geo_kwargs():
    """Kwargs that disable hierarchy/distances/TE so no geocoding runs."""
    return dict(include_hierarchy=False, include_distances=False, include_target_encoding=False)


# --------------------------------------------------------------------------- #
# include_cluster default — must NOT cluster (preserves global_transformers use)
# --------------------------------------------------------------------------- #


def test_include_cluster_default_is_false():
    """A default-constructed GeoFeatures must not add geo_cluster."""
    df = _make_df(n=30)
    gf = GeoFeatures(lat_col="latitude", lon_col="longitude", **_no_geo_kwargs())
    result = gf.fit_transform(df)
    assert "geo_cluster" not in result.columns


# --------------------------------------------------------------------------- #
# Clustering on
# --------------------------------------------------------------------------- #


def test_cluster_adds_geo_cluster_column():
    df = _make_df(n=30)
    gf = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=3,
        **_no_geo_kwargs(),
    )
    result = gf.fit_transform(df)
    assert "geo_cluster" in result.columns
    assert result["geo_cluster"].dtype == int
    # labels within [−1, n_clusters)
    assert result["geo_cluster"].min() >= -1
    assert result["geo_cluster"].max() < 3


def test_cluster_invalid_coords_get_minus_one():
    valid = _make_df(n=25, valid=True)
    zeros = _make_df(n=5, valid=False)
    df = pd.concat([zeros, valid], ignore_index=True)
    gf = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=3,
        **_no_geo_kwargs(),
    )
    result = gf.fit_transform(df)
    # First 5 rows had zero coords → label -1
    assert (result.loc[:4, "geo_cluster"] == -1).all()


def test_cluster_too_few_valid_coords_raises():
    df = _make_df(n=5, valid=True)  # < 10 valid
    gf = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=3,
        **_no_geo_kwargs(),
    )
    with pytest.raises(Exception):
        gf.fit(df)


# --------------------------------------------------------------------------- #
# Pure scikit-learn semantics — fit never touches disk
# --------------------------------------------------------------------------- #


def test_fit_does_not_persist_even_with_geo_model_path(tmp_path):
    """Q4 principle: fit() learns but never writes, even when geo_model_path is set."""
    df = _make_df(n=30)
    model_path = str(tmp_path / "geo_model.pkl")
    gf = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=3,
        geo_model_path=model_path,
        **_no_geo_kwargs(),
    )
    gf.fit(df)
    assert not Path(model_path).exists(), "fit() must not persist; save() is explicit"


# --------------------------------------------------------------------------- #
# save / load round-trip
# --------------------------------------------------------------------------- #


def test_save_load_roundtrip_reproduces_clusters(tmp_path):
    df = _make_df(n=40)
    model_path = str(tmp_path / "geo_model.pkl")

    # Train: fit → save → transform
    train = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=4,
        **_no_geo_kwargs(),
    )
    train.fit(df)
    train.save(model_path)
    assert Path(model_path).exists()
    expected = train.transform(df)["geo_cluster"].to_numpy()

    # Infer: new instance, load → transform (NO fit of clustering)
    infer = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=4,
        **_no_geo_kwargs(),
    )
    assert not getattr(infer, "_cluster_loaded_", False)
    infer.load(model_path)
    assert infer._cluster_loaded_ is True
    got = infer.transform(df)["geo_cluster"].to_numpy()

    np.testing.assert_array_equal(got, expected)


def test_load_then_fit_does_not_refit_clustering(tmp_path):
    """The load-or-fit contract: after load(), fit() must skip clustering refit.

    A transformer that loads the trained model then fits on *different* data must
    still assign the ORIGINAL model's clusters (hierarchy refits from data, but
    clustering must NOT be retrained).
    """
    df_a = _make_df(n=40, seed=1)
    df_b = _make_df(n=40, seed=2)
    model_path = str(tmp_path / "geo_model.pkl")

    train = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=4,
        **_no_geo_kwargs(),
    )
    train.fit(df_a)
    train.save(model_path)
    baseline = train.transform(df_a)["geo_cluster"].to_numpy()

    # load() then fit() on DIFFERENT data (df_b) — clustering must come from the file
    loaded = GeoFeatures(
        lat_col="latitude",
        lon_col="longitude",
        include_cluster=True,
        n_clusters=4,
        **_no_geo_kwargs(),
    )
    loaded.load(model_path)
    loaded.fit(df_b)  # fits hierarchy (no-op here) but must NOT refit KMeans
    got = loaded.transform(df_a)["geo_cluster"].to_numpy()

    np.testing.assert_array_equal(got, baseline)
