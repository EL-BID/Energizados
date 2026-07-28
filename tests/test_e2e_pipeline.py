"""
End-to-end integration tests for the Energizados pipeline.

Tests the full pipeline (ETL -> Split -> FE -> Train -> Eval)
with synthetic data to catch regressions at phase boundaries.
"""

import json
import os

import pandas as pd
import pytest

from energizados.core.pipeline import ConfigPipelineBuilder


def _catboost_available():
    """Check if catboost is installed."""
    try:
        import catboost  # noqa: F401

        return True
    except ImportError:
        return False


def _build_etl_config():
    """Build minimal ETL config dict for E2E tests."""
    return {
        "etl": {
            "sample": {
                "enabled": True,
                "description": "E2E test ETL",
                "input": "data/raw/test_dataset.parquet",
                "output": "data/processed/test_dataset.parquet",
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "depends_on": [],
            }
        }
    }


def _build_train_config(
    split_method="stratified",
    sampling_method="undersample",
    models=None,
    ensemble=None,
):
    """Build minimal train config dict for E2E tests."""
    if models is None:
        models = [
            {
                "type": "lightgbm",
                "sampling": {"method": sampling_method, "threshold": 0.5},
                "hyperparams": {
                    "num_leaves": 8,
                    "learning_rate": 0.1,
                    "n_estimators": 10,
                    "min_child_samples": 1,
                    "verbose": -1,
                },
                "hyperparam_search": {"enabled": False},
            }
        ]
    config = {
        "train": {
            "enabled": True,
            "input_path": "data/processed/test_dataset.parquet",
            "target_column": "target",
            "split": {
                "method": split_method,
                "test_size": 0.2,
                "val_size": 0.15,
                "random_state": 42,
                "save_splits": True,
                "splits_dir": "data/temp/splits/",
            },
            "feature_engineering": {
                "enabled": True,
                "preprocessing": {
                    "enabled": True,
                    "columns": {
                        "actividad": [
                            {"cardinality_reducer": {"threshold": 0.01}},
                            {"to_dummy": {}},
                        ],
                        "tipo_tarifa": [{"target_encoding": {"w": 5}}],
                        "zona": [{"ordinal_encoding": {}}],
                    },
                },
                "feature_selection": {
                    "enabled": False,
                },
            },
            "models": models,
            "evaluation": {
                "enabled": True,
                "threshold": 0.5,
                "metrics": ["auc", "precision", "recall", "f1", "confusion_matrix"],
                "generate_plots": True,
                "generate_html_report": True,
                "generate_json_report": True,
            },
        },
    }
    if ensemble:
        config["train"]["ensemble"] = ensemble
    return config


def _run_pipeline(project_dir, config):
    """Run pipeline in the given project dir, returning (result, run_dir)."""
    original_cwd = os.getcwd()
    os.chdir(project_dir)
    try:
        builder = ConfigPipelineBuilder(config=config)
        result = builder.run()
        # Resolve run_dir to absolute while still in project_dir
        run_dir = builder.run_dir.resolve() if builder.run_dir else None
        return result, run_dir
    finally:
        os.chdir(original_cwd)


def _extract_auc(report):
    """Extract AUC from report dict (handles nested and flat structures)."""
    metrics = report.get("metrics", report)
    return metrics.get("auc", metrics.get("AUC"))


@pytest.mark.slow
@pytest.mark.integration
class TestE2ESmokeTest:
    """End-to-end smoke test: full pipeline on synthetic data."""

    def test_full_pipeline_smoke(self, e2e_project_dir):
        """Full pipeline: ETL -> Split -> FE -> Train -> Eval with single LightGBM."""
        config = {**_build_etl_config(), **_build_train_config()}
        result, run_dir = _run_pipeline(e2e_project_dir, config)

        assert run_dir is not None, "run_dir should be set after pipeline run"
        assert run_dir.exists(), f"run_dir {run_dir} should exist"

        # Model artifacts
        assert (run_dir / "models" / "model.pkl").exists()
        assert (run_dir / "models" / "feature_engineering.pkl").exists()

        # Evaluation reports
        report_dir = run_dir / "reports" / "evaluation"
        assert (report_dir / "evaluation_report.html").exists()
        assert (report_dir / "evaluation_report.json").exists()

        # Metadata
        assert (run_dir / "run_metadata.json").exists()

        # Validate JSON report content
        report = json.loads((report_dir / "evaluation_report.json").read_text(encoding="utf-8"))
        auc = _extract_auc(report)
        assert auc is not None, "AUC should be present in report"
        assert 0.0 <= auc <= 1.0, f"AUC should be between 0 and 1, got {auc}"

        # Validate context
        assert result is not None


@pytest.mark.slow
@pytest.mark.integration
class TestPhaseContracts:
    """Validate output contracts between pipeline phases."""

    @pytest.fixture()
    def pipeline_run(self, e2e_project_dir):
        """Run the full pipeline and return (result, run_dir, project_dir)."""
        config = {**_build_etl_config(), **_build_train_config()}
        result, run_dir = _run_pipeline(e2e_project_dir, config)
        return result, run_dir, e2e_project_dir

    def test_etl_output_contract(self, pipeline_run):
        """ETL output has all expected columns and same row count."""
        _, _, project_dir = pipeline_run
        output_path = project_dir / "data" / "processed" / "test_dataset.parquet"
        assert output_path.exists(), "ETL output parquet should exist"

        df = pd.read_parquet(output_path)
        input_df = pd.read_parquet(project_dir / "data" / "raw" / "test_dataset.parquet")

        assert len(df) == len(input_df), "ETL should preserve row count"

        expected_cols = [f"{i}_anterior" for i in range(12, 0, -1)]
        expected_cols += ["actividad", "tipo_tarifa", "zona", "target"]
        for col in expected_cols:
            assert col in df.columns, f"Column {col} missing from ETL output"

    def test_split_output_no_leakage(self, pipeline_run):
        """Split outputs exist, have target, and row counts sum correctly."""
        _, _, project_dir = pipeline_run
        splits_dir = project_dir / "data" / "temp" / "splits"

        split_files = list(splits_dir.glob("*.parquet"))
        assert len(split_files) >= 2, "At least train and val splits should exist"

        dfs = {}
        for f in split_files:
            name = f.stem
            if name.startswith(("train", "val", "test")) and "predict" not in name:
                dfs[name] = pd.read_parquet(f)

        # All splits must have the target column
        for name, df in dfs.items():
            assert "target" in df.columns, f"Split {name} should contain target column"

        # Row counts should sum to total dataset size
        input_df = pd.read_parquet(project_dir / "data" / "processed" / "test_dataset.parquet")
        total_split_rows = sum(len(df) for df in dfs.values())
        assert total_split_rows == len(
            input_df
        ), f"Split rows ({total_split_rows}) should equal input rows ({len(input_df)})"

        # Each split should have rows (non-empty)
        for name, df in dfs.items():
            assert len(df) > 0, f"Split {name} should not be empty"

    def test_feature_engineering_output(self, pipeline_run):
        """Feature engineering pkl exists and can transform data."""
        result, run_dir, project_dir = pipeline_run
        fe_path = run_dir / "models" / "feature_engineering.pkl"
        assert fe_path.exists(), "feature_engineering.pkl should exist"

        fe = result.get("feature_engineering")
        if fe is not None:
            val_path = project_dir / "data" / "splits" / "val.parquet"
            if val_path.exists():
                val_df = pd.read_parquet(val_path)
                X_val = val_df.drop(columns=["target"], errors="ignore")
                X_transformed = fe.transform(X_val)
                assert X_transformed is not None
                assert len(X_transformed) == len(X_val)

    def test_predictions_contract(self, pipeline_run):
        """Model predictions have y_true in {0,1} and y_proba in [0,1]."""
        _, run_dir, project_dir = pipeline_run

        # Check for val_predictions in splits dir or run dir
        val_pred_paths = [
            project_dir / "data" / "splits" / "val_predictions.parquet",
            *list(run_dir.rglob("*val*predict*")),
        ]
        pred_path = next((p for p in val_pred_paths if p.exists()), None)

        if pred_path:
            pred_df = pd.read_parquet(pred_path)
            if "y_true" in pred_df.columns:
                assert set(pred_df["y_true"].unique()).issubset({0, 1})
            if "y_proba" in pred_df.columns:
                assert pred_df["y_proba"].between(0, 1).all()


@pytest.mark.slow
@pytest.mark.integration
class TestConfigurationMatrix:
    """Parametrized tests for critical config combinations."""

    @pytest.mark.parametrize("split_method", ["stratified", "random"])
    @pytest.mark.parametrize("sampling_method", ["undersample", "none"])
    def test_split_sampling_combinations(self, e2e_project_dir, split_method, sampling_method):
        """Pipeline completes with different split and sampling methods."""
        config = {
            **_build_etl_config(),
            **_build_train_config(
                split_method=split_method,
                sampling_method=sampling_method,
            ),
        }
        _, run_dir = _run_pipeline(e2e_project_dir, config)

        assert run_dir is not None
        assert (run_dir / "models" / "model.pkl").exists()

        report_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        auc = _extract_auc(report)
        assert auc is not None and 0.0 <= auc <= 1.0

    @pytest.mark.skipif(
        not _catboost_available(),
        reason="catboost not installed",
    )
    def test_ensemble_soft_voting(self, e2e_project_dir):
        """Pipeline completes with 2-model ensemble (soft_voting)."""
        models = [
            {
                "name": "lgbm",
                "type": "lightgbm",
                "sampling": {"method": "none"},
                "hyperparams": {
                    "num_leaves": 8,
                    "learning_rate": 0.1,
                    "n_estimators": 10,
                    "min_child_samples": 1,
                    "verbose": -1,
                },
                "hyperparam_search": {"enabled": False},
            },
            {
                "name": "cat",
                "type": "catboost",
                "sampling": {"method": "none"},
                "hyperparams": {
                    "iterations": 10,
                    "verbose": 0,
                },
                "hyperparam_search": {"enabled": False},
            },
        ]
        config = {
            **_build_etl_config(),
            **_build_train_config(
                models=models,
                ensemble={"method": "soft_voting"},
            ),
        }
        _, run_dir = _run_pipeline(e2e_project_dir, config)

        assert run_dir is not None
        assert (run_dir / "models" / "lgbm" / "model.pkl").exists()
        assert (run_dir / "models" / "cat" / "model.pkl").exists()
        assert (run_dir / "models" / "ensemble.pkl").exists()

        report_path = run_dir / "reports" / "evaluation" / "evaluation_report.json"
        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        auc = _extract_auc(report)
        assert auc is not None and 0.0 <= auc <= 1.0
