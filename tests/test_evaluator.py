"""Tests for DefaultEvaluator._export_segment_thresholds method.

TDD for mejoras-3 change - Task T-F2a-1
"""

import json
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from energizados.evaluation.evaluator import DefaultEvaluator


class TestExportSegmentThresholds:
    """Tests for the _export_segment_thresholds method."""

    def test_export_segment_thresholds_writes_json_file(self, tmp_path):
        """Test that JSON file is written to output_dir with correct name."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Norte": {
                "threshold": 0.37,
                "threshold_mode": "youden",
                "auc": 0.82,
                "n_samples": 1500,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        expected_file = output_dir / "segment_thresholds_Norte.json"
        assert expected_file.exists(), f"Expected file {expected_file} not found"
        assert len(result) == 1
        assert result[0] == expected_file

    def test_export_segment_thresholds_json_structure(self, tmp_path):
        """Test JSON structure matches expected schema."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Sul": {
                "threshold": 0.63,
                "threshold_mode": "youden",
                "auc": 0.79,
                "n_samples": 1200,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.45,
            threshold_mode="youden",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_Sul.json"
        with open(json_file) as f:
            data = json.load(f)

        # Verify schema
        assert "segment_column" in data
        assert "threshold_mode" in data
        assert "default_threshold" in data
        assert "segments" in data

        assert data["segment_column"] == "Sul"
        assert data["threshold_mode"] == "youden"
        assert data["default_threshold"] == 0.45
        assert isinstance(data["segments"], dict)

    def test_export_segment_thresholds_multiple_columns(self, tmp_path):
        """Test that multiple segment columns produce multiple JSON files."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "Norte": {
                "threshold": 0.37,
                "threshold_mode": "youden",
                "auc": 0.82,
                "n_samples": 1500,
            },
            "Sul": {
                "threshold": 0.63,
                "threshold_mode": "youden",
                "auc": 0.79,
                "n_samples": 1200,
            },
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        assert len(result) == 2
        assert (output_dir / "segment_thresholds_Norte.json").exists()
        assert (output_dir / "segment_thresholds_Sul.json").exists()

    def test_export_segment_thresholds_segment_values_in_segments(self, tmp_path):
        """Test that segment values are correctly nested in segments dict."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "zona": {
                "norte": {
                    "threshold": 0.37,
                    "threshold_mode": "youden",
                    "auc": 0.82,
                    "n_samples": 1500,
                },
                "sul": {
                    "threshold": 0.63,
                    "threshold_mode": "youden",
                    "auc": 0.79,
                    "n_samples": 1200,
                },
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="youden",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_zona.json"
        with open(json_file) as f:
            data = json.load(f)

        assert "segments" in data
        assert "norte" in data["segments"]
        assert "sul" in data["segments"]

        norte_data = data["segments"]["norte"]
        assert norte_data["threshold"] == 0.37
        assert norte_data["threshold_mode"] == "youden"
        assert norte_data["auc"] == 0.82
        assert norte_data["n_samples"] == 1500

    def test_export_segment_thresholds_json_indent(self, tmp_path):
        """Test that JSON is written with indent=2 for human readability."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {
            "test_col": {
                "threshold": 0.5,
                "threshold_mode": "global",
                "auc": 0.8,
                "n_samples": 100,
            }
        }
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="global",
        )

        # Assert
        json_file = output_dir / "segment_thresholds_test_col.json"
        content = json_file.read_text()

        # Check for indentation by looking for newlines and spaces
        assert "\n" in content, "JSON should be indented (contain newlines)"
        assert "  " in content, "JSON should be indented (contain spaces)"

    def test_export_segment_thresholds_empty_metrics(self, tmp_path):
        """Test that empty segmented_metrics produces no files."""
        # Arrange
        evaluator = DefaultEvaluator(output_dir=str(tmp_path))
        segmented_metrics = {}
        output_dir = tmp_path / "test_output"
        output_dir.mkdir()

        # Act
        result = evaluator._export_segment_thresholds(
            segmented_metrics=segmented_metrics,
            output_dir=output_dir,
            global_threshold=0.5,
            threshold_mode="global",
        )

        # Assert
        assert result == []
        assert len(list(output_dir.glob("*.json"))) == 0


class TestExportSegmentThresholdsIntegration:
    """Integration tests for _export_segment_thresholds within execute()."""

    def test_execute_calls_export_when_segmented_enabled(self, tmp_path):
        """Test that _export_segment_thresholds is called when segmented_evaluation is enabled."""
        # Arrange - Create a real parquet file with enough data for segments

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()
        # The default export location follows the trained model (deployment
        # artifact rationale). Set an explicit model_path so the test
        # controls where the JSON lands.
        models_dir = tmp_path / "models"
        model_path = models_dir / "model.pkl"

        # Create enough samples per segment (min_samples default is 30)
        np.random.seed(42)
        n_samples = 100
        test_data = pd.DataFrame(
            {
                "target": np.random.randint(0, 2, n_samples),
                "feature1": np.random.random(n_samples),
                "zona": ["Norte"] * 50 + ["Sul"] * 50,
            }
        )
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            model_path=str(model_path),
            segmented_evaluation={
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
                "min_samples": 10,  # Lower threshold for test
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        # Create a simple mock model with enough predictions
        class SimpleMockModel:
            def predict_proba(self, X):
                return np.random.random(len(X))

        # Patch the _load_model method
        with patch.object(evaluator, "_load_model", return_value=SimpleMockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                # Act
                context = {}
                _ = evaluator.execute(context)

        # Assert - Check that segment threshold files were created in the
        # model directory (the new default; the JSON is a deployment
        # artifact, not a report).
        assert (
            models_dir / "segment_thresholds_zona.json"
        ).exists(), "Segment threshold JSON file should be created in the model dir"
        assert not (output_dir / "segment_thresholds_zona.json").exists(), (
            "Segment threshold JSON should NOT land in output_dir (the legacy "
            "reports dir) when a model_path is available"
        )

        # Verify the JSON content
        with open(models_dir / "segment_thresholds_zona.json") as f:
            data = json.load(f)
        assert "segment_column" in data
        assert data["segment_column"] == "zona"
        assert "segments" in data
        assert "Norte" in data["segments"] or "Sul" in data["segments"]

    def test_execute_no_export_when_segmented_disabled(self, tmp_path):
        """Test that no export happens when segmented_evaluation is disabled."""
        # Arrange - Create a real parquet file with minimal data

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        test_data = pd.DataFrame(
            {
                "target": [0, 1, 0, 1, 0, 1],
                "feature1": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                "zona": ["Norte", "Sul", "Norte", "Sul", "Norte", "Sul"],
            }
        )
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            segmented_evaluation={"enabled": False},
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        # Create a simple mock model
        class SimpleMockModel:
            def predict_proba(self, X):
                return np.array([0.3, 0.7, 0.4, 0.6, 0.5, 0.8])

        # Patch the _load_model method
        with patch.object(evaluator, "_load_model", return_value=SimpleMockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                # Act
                context = {}
                evaluator.execute(context)

        # Assert - Check that no segment threshold files were created
        json_files = list(output_dir.glob("segment_thresholds_*.json"))
        assert (
            len(json_files) == 0
        ), "No segment threshold JSON files should be created when disabled"


class TestSegmentedHeadlineReconciliation:
    """TDD tests for headline-metrics reconciliation with segmented evaluation.

    Bug: when ``segmented_evaluation.enabled: True`` with a per-segment
    threshold mode (e.g. ``youden``), the headline ``/metrics/recall``
    reported the GLOBAL-threshold operating point instead of the per-segment
    aggregate. This caused v2/v3 result docs to over-report operational
    recall by ~0.23-0.32 points.
    """

    @staticmethod
    def _build_synthetic_dataset(tmp_path):
        """Build a dataset where global and per-segment thresholds diverge.

        Segment ``high_prev``: 60 rows, 30 positives — high probabilities.
        Segment ``low_prev``: 60 rows, 5 positives — low probabilities.

        With a single global threshold, many ``low_prev`` positives are
        missed; per-segment Youden picks a lower threshold for ``low_prev``
        and captures them.
        """
        rng = np.random.RandomState(42)
        # high_prev: 30 pos (proba ~0.8), 30 neg (proba ~0.3)
        high_pos = rng.beta(8, 2, size=30)  # skewed high
        high_neg = rng.beta(2, 5, size=30)  # skewed low
        # low_prev: 5 pos (proba ~0.4), 55 neg (proba ~0.1)
        low_pos = rng.beta(5, 5, size=5)  # mid-range
        low_neg = rng.beta(1, 9, size=55)  # very low

        proba = np.concatenate([high_pos, high_neg, low_pos, low_neg])
        y_true = np.concatenate(
            [
                np.ones(30),
                np.zeros(30),  # high_prev
                np.ones(5),
                np.zeros(55),  # low_prev
            ]
        )
        seg = np.array(["high_prev"] * 60 + ["low_prev"] * 60)
        feat = rng.random(120)

        test_data = pd.DataFrame(
            {
                "target": y_true.astype(int),
                "feature1": feat,
                "geo_region": seg,
            }
        )
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)
        return test_path, proba, y_true, seg

    def test_headline_recall_matches_segment_aggregate_not_global(self, tmp_path):
        """When segmented_evaluation uses per-segment thresholds, the headline
        recall MUST equal the per-segment aggregate, NOT the global-threshold
        recall."""
        test_path, proba, y_true, seg = self._build_synthetic_dataset(tmp_path)

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        class ProbabilisticMockModel:
            """Returns pre-set probabilities for deterministic testing."""

            def __init__(self, probabilities):
                self._proba = probabilities

            def predict_proba(self, x):
                return self._proba.copy()

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            threshold=0.5,
            metrics=["auc", "precision", "recall", "f1", "confusion_matrix"],
            segmented_evaluation={
                "enabled": True,
                "by": ["geo_region"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        model = ProbabilisticMockModel(proba)
        with patch.object(evaluator, "_load_model", return_value=model):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                context = {}
                result = evaluator.execute(context)

        metrics = result["metrics"]

        # --- Compute expected per-segment aggregate recall ---
        from energizados.evaluation.metrics import (
            Metrics,
            find_optimal_threshold_youden,
        )

        m = Metrics(y_true, np.zeros_like(y_true), proba, threshold=0.5)
        seg_metrics = m.segment_metrics(seg, threshold_mode="youden")
        total_tp = sum(int(round(d["recall"] * d["n_positives"])) for d in seg_metrics.values())
        total_pos = int(y_true.sum())
        expected_aggregate_recall = total_tp / total_pos

        # --- Compute global-threshold recall (what the bug reported) ---
        global_thr = find_optimal_threshold_youden(y_true, proba)
        global_recall = recall_at(proba, y_true, global_thr)

        # The two must differ (otherwise the test setup is degenerate)
        assert expected_aggregate_recall != global_recall, (
            "Test setup is degenerate: aggregate and global recall are equal "
            f"({expected_aggregate_recall}). Need a dataset where they differ."
        )

        # CORE ASSERTION: headline recall = per-segment aggregate
        assert metrics["recall"] == pytest.approx(expected_aggregate_recall, abs=0.02), (
            f"Headline recall {metrics['recall']:.4f} should equal per-segment "
            f"aggregate {expected_aggregate_recall:.4f}, not global "
            f"{global_recall:.4f}"
        )

        # The headline must NOT equal the global-threshold recall
        assert metrics["recall"] != pytest.approx(global_recall, abs=0.01), (
            f"Headline recall {metrics['recall']:.4f} should NOT equal global "
            f"recall {global_recall:.4f}"
        )

    def test_global_threshold_metrics_preserved(self, tmp_path):
        """When segmented_evaluation is active, the global-threshold numbers
        must be preserved under a labeled key (not deleted)."""
        test_path, proba, y_true, seg = self._build_synthetic_dataset(tmp_path)

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        class ProbabilisticMockModel:
            def __init__(self, probabilities):
                self._proba = probabilities

            def predict_proba(self, x):
                return self._proba.copy()

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            threshold=0.5,
            metrics=["auc", "precision", "recall", "f1", "confusion_matrix"],
            segmented_evaluation={
                "enabled": True,
                "by": ["geo_region"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        model = ProbabilisticMockModel(proba)
        with patch.object(evaluator, "_load_model", return_value=model):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                context = {}
                result = evaluator.execute(context)

        metrics = result["metrics"]

        # Global-threshold metrics must be preserved
        assert (
            "global_threshold_metrics" in metrics
        ), "global_threshold_metrics key must be present when segmented evaluation is active"
        gtm = metrics["global_threshold_metrics"]
        for key in ("recall", "precision", "f1", "confusion_matrix", "threshold"):
            assert key in gtm, f"global_threshold_metrics missing key '{key}'"

        # Headline threshold should be marked as segment-based
        assert (
            metrics.get("threshold_mode") is not None
        ), "threshold_mode field should be set to indicate segment-based headline"

    def test_html_report_with_segmented_headline_does_not_crash(self, tmp_path):
        """Regression: HTML report generation must not crash when the headline
        is reconciled with per-segment thresholds.

        The reconciler sets ``metrics["threshold"] = None`` to signal a
        segment-based headline. The threshold-sweep HTML builder read it via
        ``metrics.get("threshold", 0.5)``, which returns ``None`` (the key
        exists, so the default does not apply) and then crashed with
        ``TypeError: unsupported operand type(s) for -: 'float' and 'NoneType'``
        when computing the nearest-threshold row.

        This test runs the full evaluator with ``generate_html_report=True``
        (the path all the other tests in this class skip) and asserts the HTML
        file is produced.
        """
        test_path, proba, y_true, seg = self._build_synthetic_dataset(tmp_path)

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        class ProbabilisticMockModel:
            def __init__(self, probabilities):
                self._proba = probabilities

            def predict_proba(self, x):
                return self._proba.copy()

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            threshold=0.5,
            metrics=["auc", "precision", "recall", "f1", "confusion_matrix"],
            segmented_evaluation={
                "enabled": True,
                "by": ["geo_region"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=True,
            generate_json_report=False,
        )

        model = ProbabilisticMockModel(proba)
        with patch.object(evaluator, "_load_model", return_value=model):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                result = evaluator.execute({})

        # The reconciler still marks the headline as segment-based
        metrics = result["metrics"]
        assert metrics.get("threshold") is None, "headline threshold must be None for segment mode"
        assert "global_threshold_metrics" in metrics, "global numbers must be preserved"

        # The HTML report must exist (this is the line that crashed before the fix)
        html_files = list(output_dir.glob("*.html"))
        assert html_files, f"HTML report was not generated in {output_dir}"

    def test_disabled_segmented_evaluation_unchanged(self, tmp_path):
        """When segmented_evaluation is absent/disabled, headline MUST remain
        the global-threshold operating point (backward compatibility)."""
        test_path, proba, y_true, seg = self._build_synthetic_dataset(tmp_path)

        output_dir = tmp_path / "eval_output"
        output_dir.mkdir()

        class ProbabilisticMockModel:
            def __init__(self, probabilities):
                self._proba = probabilities

            def predict_proba(self, x):
                return self._proba.copy()

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            threshold=0.5,
            metrics=["auc", "precision", "recall", "f1", "confusion_matrix"],
            segmented_evaluation={"enabled": False},
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        model = ProbabilisticMockModel(proba)
        with patch.object(evaluator, "_load_model", return_value=model):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                context = {}
                result = evaluator.execute(context)

        metrics = result["metrics"]

        # No reconciliation should happen — no global_threshold_metrics key
        assert (
            "global_threshold_metrics" not in metrics
        ), "global_threshold_metrics should NOT be present when segmented evaluation is disabled"
        assert (
            "threshold_mode" not in metrics
        ), "threshold_mode should NOT be set when segmented evaluation is disabled"
        # Standard threshold behavior
        assert metrics["threshold"] == 0.5


def recall_at(proba, y_true, threshold):
    """Helper: recall at a given threshold."""
    y_pred = (proba >= threshold).astype(int)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


class TestEvaluatorNoHoldout:
    """FR5: evaluator skips gracefully when no test_path is available."""

    def test_evaluator_no_test_path_skips_gracefully(self, tmp_path):
        ev = DefaultEvaluator(output_dir=str(tmp_path / "eval"))
        result = ev.execute({})  # no test_path in context
        assert result.get("skipped") is True
        assert result.get("metrics") == {}


class TestResolveThresholdsOutputDir:
    """Tests for ``_resolve_thresholds_output_dir``.

    The segment_thresholds_*.json export is a deployment artifact, not a
    report. Its default location must follow the trained model so the
    inference step can pair it with the model file. The resolver picks the
    effective directory in this order:

    1. ``self.thresholds_output_dir`` (explicit override) — used as-is,
       created if missing.
    2. ``Path(model_path).parent`` (model directory) — used when the
       evaluator has a resolved model_path.
    3. ``self.output_dir`` (legacy reports dir) — fallback when the
       evaluator was called without a model.
    """

    def test_returns_override_when_set(self, tmp_path):
        """Override path is used verbatim and created if missing."""
        custom_dir = tmp_path / "exports" / "thresholds"
        # NOT created yet
        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            thresholds_output_dir=str(custom_dir),
        )

        result = evaluator._resolve_thresholds_output_dir(
            model_path=str(tmp_path / "models" / "model.pkl"),
        )

        assert result == custom_dir
        assert result.is_dir()

    def test_returns_model_parent_when_no_override(self, tmp_path):
        """No override + model_path → ``Path(model_path).parent``."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_path = models_dir / "model.pkl"
        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            thresholds_output_dir=None,
        )

        result = evaluator._resolve_thresholds_output_dir(model_path=str(model_path))

        assert result == models_dir
        assert result.is_dir()

    def test_returns_output_dir_fallback(self, tmp_path):
        """No override + no model_path → ``self.output_dir`` (legacy behavior)."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()
        evaluator = DefaultEvaluator(
            output_dir=str(reports_dir),
            thresholds_output_dir=None,
        )

        result = evaluator._resolve_thresholds_output_dir(model_path=None)

        assert result == reports_dir
        assert result.is_dir()

    def test_creates_missing_override_dir_with_parents(self, tmp_path):
        """An override path several levels deep is created via mkdir(parents=True)."""
        custom_dir = tmp_path / "deep" / "nested" / "export"
        # not created
        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            thresholds_output_dir=str(custom_dir),
        )

        result = evaluator._resolve_thresholds_output_dir(model_path=None)

        assert result == custom_dir
        assert result.is_dir()
        # parents were created all the way down
        assert (tmp_path / "deep" / "nested").is_dir()

    def test_model_parent_dir_is_created_if_missing(self, tmp_path):
        """If the model directory does not exist yet, mkdir it so the export
        succeeds. This is the default behavior when run resolves
        ``model_path`` from context before the model file itself is
        actually written."""
        models_dir = tmp_path / "models"
        model_path = models_dir / "model.pkl"
        # models_dir NOT created
        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            thresholds_output_dir=None,
        )

        result = evaluator._resolve_thresholds_output_dir(model_path=str(model_path))

        assert result == models_dir
        assert result.is_dir()

    def test_override_takes_precedence_over_model_path(self, tmp_path):
        """When both are present, override wins over the model directory."""
        custom_dir = tmp_path / "exports"
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            thresholds_output_dir=str(custom_dir),
        )

        result = evaluator._resolve_thresholds_output_dir(
            model_path=str(models_dir / "model.pkl"),
        )

        assert result == custom_dir


class TestExecuteUsesResolvedThresholdsDir:
    """Integration tests: ``execute()`` writes segment_thresholds_*.json to
    the directory resolved by ``_resolve_thresholds_output_dir``."""

    @staticmethod
    def _build_dataset(tmp_path, n_per_segment=50, seed=42):
        rng = np.random.RandomState(seed)
        test_data = pd.DataFrame(
            {
                "target": rng.randint(0, 2, n_per_segment * 2),
                "feature1": rng.random(n_per_segment * 2),
                "zona": ["Norte"] * n_per_segment + ["Sul"] * n_per_segment,
            }
        )
        test_path = tmp_path / "test.parquet"
        test_data.to_parquet(test_path)
        return test_path

    def test_default_exports_to_model_dir_when_model_path_set(self, tmp_path):
        """When model_path is set, the JSON lands in the model directory."""
        output_dir = tmp_path / "reports"
        models_dir = tmp_path / "models"
        model_path = models_dir / "model.pkl"
        test_path = self._build_dataset(tmp_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            model_path=str(model_path),
            segmented_evaluation={
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        class MockModel:
            def predict_proba(self, X):
                return np.random.RandomState(7).random(len(X))

        with patch.object(evaluator, "_load_model", return_value=MockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                evaluator.execute({})

        # JSON should land in the model dir, NOT the reports dir
        assert (
            models_dir / "segment_thresholds_zona.json"
        ).exists(), "Expected segment_thresholds_*.json in the model directory by default"
        assert not (output_dir / "segment_thresholds_zona.json").exists(), (
            "segment_thresholds_*.json should NOT be written to output_dir when "
            "model_path is available"
        )

    def test_explicit_override_dir_takes_precedence(self, tmp_path):
        """``thresholds_output_dir`` overrides the model dir default."""
        output_dir = tmp_path / "reports"
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        custom_dir = tmp_path / "data" / "exports"
        test_path = self._build_dataset(tmp_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            model_path=str(models_dir / "model.pkl"),
            thresholds_output_dir=str(custom_dir),
            segmented_evaluation={
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        class MockModel:
            def predict_proba(self, X):
                return np.random.RandomState(7).random(len(X))

        with patch.object(evaluator, "_load_model", return_value=MockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                evaluator.execute({})

        assert (custom_dir / "segment_thresholds_zona.json").exists()
        # Neither the model dir nor the reports dir should receive the file
        assert not (models_dir / "segment_thresholds_zona.json").exists()
        assert not (output_dir / "segment_thresholds_zona.json").exists()

    def test_fallback_to_output_dir_when_no_model_path(self, tmp_path):
        """Without a resolved model_path, the JSON falls back to output_dir.

        The DefaultEvaluator constructor's default model_path is
        ``"output/models/model.pkl"``; passing ``model_path=None`` is the
        way to opt out of the model-dir default and exercise the
        standalone-evaluator code path that keeps the legacy reports-dir
        destination.
        """
        output_dir = tmp_path / "reports"
        test_path = self._build_dataset(tmp_path)

        evaluator = DefaultEvaluator(
            input_path=str(test_path),
            output_dir=str(output_dir),
            model_path=None,  # opt out of the default models/ fallback
            segmented_evaluation={
                "enabled": True,
                "by": ["zona"],
                "threshold_mode": "youden",
                "min_samples": 10,
            },
            generate_plots=False,
            generate_html_report=False,
            generate_json_report=False,
        )

        class MockModel:
            def predict_proba(self, X):
                return np.random.RandomState(7).random(len(X))

        with patch.object(evaluator, "_load_model", return_value=MockModel()):
            with patch.object(evaluator, "_load_feature_engineering", return_value=None):
                evaluator.execute({})

        # Standalone-evaluator case: no model_path resolved → output_dir is the
        # only sensible destination.
        assert (output_dir / "segment_thresholds_zona.json").exists()
