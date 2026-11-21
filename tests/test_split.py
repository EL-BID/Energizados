"""Tests for SplitStep no-holdout method (split.method='none')."""

import json

import pandas as pd

from energizados.core.steps.split import SplitStep


def _make_dataset(path, n=50):
    df = pd.DataFrame(
        {"f1": [float(i % 10) for i in range(n)], "target": [i % 2 for i in range(n)]}
    )
    df.to_parquet(path, index=False)
    return df


class TestSplitMethodNone:
    """FR1: split.method='none' assigns all data to train, no val/test."""

    def test_split_method_none_all_data_in_train(self, tmp_path):
        df = _make_dataset(str(tmp_path / "in.parquet"))
        step = SplitStep(
            input_path=str(tmp_path / "in.parquet"),
            target_column="target",
            splits_dir=str(tmp_path / "splits"),
            method="none",
        )
        ctx = step.execute({})
        train = pd.read_parquet(ctx["train_path"])
        assert len(train) == len(df)
        assert ctx["val_path"] is None
        assert ctx["test_path"] is None

    def test_split_none_writes_train_parquet_only(self, tmp_path):
        _make_dataset(str(tmp_path / "in.parquet"))
        step = SplitStep(
            input_path=str(tmp_path / "in.parquet"),
            target_column="target",
            splits_dir=str(tmp_path / "splits"),
            method="none",
        )
        step.execute({})
        files = sorted(p.name for p in (tmp_path / "splits").iterdir())
        assert "train.parquet" in files
        assert "val.parquet" not in files
        assert "test.parquet" not in files

    def test_split_none_metadata_zero_val_test(self, tmp_path):
        _make_dataset(str(tmp_path / "in.parquet"))
        step = SplitStep(
            input_path=str(tmp_path / "in.parquet"),
            target_column="target",
            splits_dir=str(tmp_path / "splits"),
            method="none",
        )
        step.execute({})
        meta = json.loads((tmp_path / "splits" / "split_metadata.json").read_text(encoding="utf-8"))
        assert meta["n_val"] == 0
        assert meta["n_test"] == 0

    def test_split_none_backward_compat_stratified(self, tmp_path):
        """Existing methods still write 3 parquets and 3 paths (backward compat)."""
        _make_dataset(str(tmp_path / "in.parquet"))
        step = SplitStep(
            input_path=str(tmp_path / "in.parquet"),
            target_column="target",
            splits_dir=str(tmp_path / "splits"),
            method="stratified",
            test_size=0.2,
            val_size=0.1,
        )
        ctx = step.execute({})
        files = sorted(p.name for p in (tmp_path / "splits").iterdir())
        assert "train.parquet" in files
        assert "val.parquet" in files
        assert "test.parquet" in files
        assert ctx["val_path"] is not None
        assert ctx["test_path"] is not None


class TestSplitBuilderEtlOutputHints:
    """SplitBuilder passes merged-config ETL outputs to SplitStep so split-time
    @etl_name references (e.g. split.unlabeled_negatives.source_path) resolve
    in standalone train runs that re-use artifacts from a previous ETL run."""

    def test_hints_built_from_global_config(self):
        from energizados.core.builders.split_builder import SplitBuilder

        builder = SplitBuilder(
            {"method": "stratified"},
            global_config={
                "train": {"input_path": "data.parquet"},
                "etl": {
                    "schema_version": 1,
                    "negativos": {"enabled": True, "output": "data/processed/neg.parquet"},
                    "clean": {"enabled": True},  # no output -> excluded
                },
            },
        )
        step = builder.build()
        assert step.etl_output_hints == {"negativos": "data/processed/neg.parquet"}

    def test_no_etl_section_gives_no_hints(self):
        from energizados.core.builders.split_builder import SplitBuilder

        builder = SplitBuilder({"method": "stratified"}, global_config={"train": {}})
        step = builder.build()
        assert step.etl_output_hints is None

    def test_builder_passes_cluster_column(self):
        """stratified_time configs need cluster_column — the builder must pass
        it through (it was dropped, breaking every stratified_time config)."""
        from energizados.core.builders.split_builder import SplitBuilder

        builder = SplitBuilder(
            {"method": "stratified_time", "cluster_column": "geo_cluster"},
            global_config={"train": {"input_path": "data.parquet"}},
        )
        step = builder.build()
        assert step.cluster_column == "geo_cluster"
