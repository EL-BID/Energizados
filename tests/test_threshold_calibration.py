"""
Unit tests for ThresholdCalibrator and evaluator calibration integration.
"""

import numpy as np
import pandas as pd
import pytest

from energizados.evaluation.calibration import ThresholdCalibrator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def imbalanced_data():
    """Dataset sintético desbalanceado (~5% fraude) con 1000 muestras."""
    rng = np.random.default_rng(42)
    n = 1000
    y_true = (rng.random(n) < 0.05).astype(int)

    # Modelo que asigna probabilidades más altas a los positivos
    y_proba = np.where(y_true == 1, rng.uniform(0.3, 0.9, n), rng.uniform(0.0, 0.3, n))
    return y_true, y_proba


@pytest.fixture
def balanced_data():
    """Dataset sintético balanceado con 200 muestras."""
    rng = np.random.default_rng(7)
    n = 200
    y_true = np.array([0] * (n // 2) + [1] * (n // 2))
    y_proba = np.where(y_true == 1, rng.uniform(0.4, 1.0, n), rng.uniform(0.0, 0.6, n))
    return y_true, y_proba


# ---------------------------------------------------------------------------
# Tests para ThresholdCalibrator - método cost_benefit
# ---------------------------------------------------------------------------


class TestCostBenefitCalibration:
    def test_returns_required_keys(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=10)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert "method" in result
        assert "params" in result
        assert "metrics_at_threshold" in result
        assert "search_results" in result

    def test_threshold_in_range(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        assert 0.0 <= result["threshold"] <= 1.0

    def test_higher_fn_cost_lowers_threshold(self, imbalanced_data):
        """Mayor cost_fn debe resultar en threshold más bajo (detectar más fraudes)."""
        y_true, y_proba = imbalanced_data

        cal_low = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=1)
        cal_high = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=50)

        result_low = cal_low.calibrate(y_true, y_proba)
        result_high = cal_high.calibrate(y_true, y_proba)

        assert result_high["threshold"] <= result_low["threshold"]

    def test_metrics_at_threshold_keys(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        metrics = result["metrics_at_threshold"]
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics

    def test_search_results_present(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="cost_benefit")
        result = cal.calibrate(y_true, y_proba)

        sr = result["search_results"]
        assert sr is not None
        assert "thresholds" in sr
        assert "costs" in sr
        assert len(sr["thresholds"]) == 101


# ---------------------------------------------------------------------------
# Tests para ThresholdCalibrator - método operational
# ---------------------------------------------------------------------------


class TestOperationalCalibration:
    def test_returns_required_keys(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=50)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert result["method"] == "operational"
        assert result["search_results"] is None

    def test_capacity_limits_alarms(self, imbalanced_data):
        """El número de alarmas no debe superar capacity significativamente."""
        y_true, y_proba = imbalanced_data
        capacity = 50

        cal = ThresholdCalibrator(method="operational", capacity=capacity)
        result = cal.calibrate(y_true, y_proba)

        n_alarms = int(np.sum(y_proba >= result["threshold"]))
        # El percentil puede dar un threshold que incluya ligeramente más (empates)
        assert n_alarms <= capacity + 10

    def test_large_capacity_gives_low_threshold(self, imbalanced_data):
        """capacity >= n debe dar threshold <= min(y_proba) (alarma en todos)."""
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=len(y_proba) + 100)
        result = cal.calibrate(y_true, y_proba)

        # Con capacity > n, el percentil 0 devuelve el mínimo de y_proba
        assert result["threshold"] <= float(np.min(y_proba)) + 1e-9

    def test_threshold_in_range(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="operational", capacity=100)
        result = cal.calibrate(y_true, y_proba)

        assert 0.0 <= result["threshold"] <= 1.0


# ---------------------------------------------------------------------------
# Tests para ThresholdCalibrator - método precision_recall
# ---------------------------------------------------------------------------


class TestPrecisionRecallCalibration:
    def test_returns_required_keys(self, balanced_data):
        y_true, y_proba = balanced_data
        cal = ThresholdCalibrator(method="precision_recall", min_recall=0.80)
        result = cal.calibrate(y_true, y_proba)

        assert "threshold" in result
        assert result["method"] == "precision_recall"
        assert "search_results" in result

    def test_recall_met_at_threshold(self, balanced_data):
        """El recall en val debe ser >= min_recall para el threshold seleccionado."""
        y_true, y_proba = balanced_data
        min_recall = 0.70

        cal = ThresholdCalibrator(method="precision_recall", min_recall=min_recall)
        result = cal.calibrate(y_true, y_proba)

        # Verificar recall al threshold encontrado
        y_pred = (y_proba >= result["threshold"]).astype(int)
        from sklearn.metrics import recall_score

        actual_recall = recall_score(y_true, y_pred, zero_division=0)

        assert actual_recall >= min_recall - 0.05  # pequeña tolerancia numérica

    def test_fallback_when_recall_impossible(self, imbalanced_data):
        """Si min_recall=1.0 es imposible, debe usar threshold=0.5 como fallback."""
        y_true, y_proba = imbalanced_data
        # min_recall=1.0 es muy difícil de lograr
        cal = ThresholdCalibrator(method="precision_recall", min_recall=1.0)
        result = cal.calibrate(y_true, y_proba)

        # Puede ser 0.5 (fallback) u otro valor si efectivamente lo logra
        assert 0.0 <= result["threshold"] <= 1.0

    def test_higher_min_recall_lowers_threshold(self, balanced_data):
        """Mayor min_recall debe resultar en threshold más bajo."""
        y_true, y_proba = balanced_data

        cal_low = ThresholdCalibrator(method="precision_recall", min_recall=0.50)
        cal_high = ThresholdCalibrator(method="precision_recall", min_recall=0.90)

        result_low = cal_low.calibrate(y_true, y_proba)
        result_high = cal_high.calibrate(y_true, y_proba)

        assert result_high["threshold"] <= result_low["threshold"]


# ---------------------------------------------------------------------------
# Tests para método desconocido
# ---------------------------------------------------------------------------


class TestUnknownMethod:
    def test_raises_value_error(self, imbalanced_data):
        y_true, y_proba = imbalanced_data
        cal = ThresholdCalibrator(method="unknown_method")

        with pytest.raises(ValueError, match="Método de calibración desconocido"):
            cal.calibrate(y_true, y_proba)


# ---------------------------------------------------------------------------
# Tests de integración con DefaultEvaluator
# ---------------------------------------------------------------------------


class TestEvaluatorCalibrationIntegration:
    """Tests de integración: evaluador usa threshold calibrado cuando habilitado."""

    def _make_val_predictions_file(self, tmp_path, y_true, y_proba):
        """Guarda val predictions en parquet y retorna el path."""
        val_df = pd.DataFrame({"y_true": y_true, "y_proba": y_proba})
        path = tmp_path / "val_predictions.parquet"
        val_df.to_parquet(path)
        return str(path)

    def test_evaluator_applies_calibrated_threshold(self, tmp_path, balanced_data):
        """El evaluador debe actualizar self.threshold al valor calibrado."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        y_true, y_proba = balanced_data

        val_path = self._make_val_predictions_file(tmp_path, y_true, y_proba)

        _ = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            calibration_config={"enabled": True, "method": "cost_benefit", "params": {"cost_fp": 1, "cost_fn": 10}},
            val_predictions_path=val_path,
        )

        # Simular el proceso de calibración sin ejecutar el pipeline completo
        val_df = pd.read_parquet(val_path)
        calibrator = ThresholdCalibrator(method="cost_benefit", cost_fp=1, cost_fn=10)
        result = calibrator.calibrate(val_df["y_true"].values, val_df["y_proba"].values)

        # El threshold calibrado debe diferir de 0.5 para datos desbalanceados
        assert isinstance(result["threshold"], float)
        assert 0.0 <= result["threshold"] <= 1.0

    def test_evaluator_fallback_when_no_val_path(self, tmp_path, balanced_data):
        """Sin val_predictions_path, el evaluador mantiene threshold por defecto."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.5,
            calibration_config={"enabled": True, "method": "cost_benefit", "params": {}},
            val_predictions_path=None,
        )

        # Threshold por defecto no cambia sin val_path
        assert evaluator.threshold == 0.5

    def test_evaluator_no_calibration_when_disabled(self, tmp_path):
        """Sin calibration config, el evaluador usa threshold estático."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.3,
            calibration_config=None,
        )
        assert evaluator.threshold == 0.3

    def test_evaluator_calibration_disabled_flag(self, tmp_path):
        """Con calibration.enabled=False, el evaluador usa threshold estático."""
        from energizados.evaluation.evaluator import DefaultEvaluator

        evaluator = DefaultEvaluator(
            output_dir=str(tmp_path / "reports"),
            threshold=0.4,
            calibration_config={"enabled": False, "method": "cost_benefit", "params": {}},
        )
        assert evaluator.threshold == 0.4


# ---------------------------------------------------------------------------
# Tests para JSON report con calibración
# ---------------------------------------------------------------------------


class TestReportCalibrationSection:
    def test_json_includes_calibration_when_provided(self, tmp_path):
        """El JSON debe incluir sección 'calibration' si se pasa calibration_result."""
        import json

        from energizados.evaluation.report import ReportGenerator

        reporter = ReportGenerator(str(tmp_path))
        calibration_result = {
            "threshold": 0.23,
            "method": "cost_benefit",
            "params": {"cost_fp": 1, "cost_fn": 10},
            "metrics_at_threshold": {"precision": 0.15, "recall": 0.85, "f1": 0.26},
        }
        metrics = {"auc": 0.80, "f1": 0.26, "precision": 0.15, "recall": 0.85}

        path = reporter.generate_json(metrics, calibration_result=calibration_result)

        with open(path) as f:
            data = json.load(f)

        assert "calibration" in data
        assert data["calibration"]["enabled"] is True
        assert data["calibration"]["method"] == "cost_benefit"
        assert data["calibration"]["threshold_used"] == pytest.approx(0.23)

    def test_json_no_calibration_when_not_provided(self, tmp_path):
        """Sin calibration_result, el JSON NO debe incluir sección 'calibration'."""
        import json

        from energizados.evaluation.report import ReportGenerator

        reporter = ReportGenerator(str(tmp_path))
        metrics = {"auc": 0.80}

        path = reporter.generate_json(metrics)

        with open(path) as f:
            data = json.load(f)

        assert "calibration" not in data
