"""
Unit tests for ComparativeEvaluator.

Tests cover: report generation, ranking calculation, HTML building,
and JSON output.
"""

import json
import tempfile
from pathlib import Path

import pytest

from energizados.evaluation.comparative import ComparativeEvaluator


class TestComparativeEvaluator:
    @pytest.fixture
    def temp_dir(self):
        """Temporary directory for test outputs."""
        d = Path(tempfile.mkdtemp())
        yield d
        # Cleanup happens automatically with tmpdir

    @pytest.fixture
    def sample_metrics(self):
        """Sample metrics for two models."""
        return {
            "lgbm": {
                "auc": 0.85,
                "f1": 0.72,
                "precision": 0.78,
                "recall": 0.67,
                "accuracy": 0.80,
                "threshold": 0.5,
            },
            "cat": {
                "auc": 0.83,
                "f1": 0.70,
                "precision": 0.75,
                "recall": 0.65,
                "accuracy": 0.78,
                "threshold": 0.5,
            },
        }

    @pytest.fixture
    def sample_model_info(self):
        """Sample model info for two models."""
        return {
            "lgbm": {
                "model_class": "lightgbm",
                "inner_model": "LGBMClassifier",
                "n_estimators": 100,
                "hyperparams": {"num_leaves": 31, "learning_rate": 0.05},
            },
            "cat": {
                "model_class": "catboost",
                "inner_model": "CatBoostClassifier",
                "n_estimators": 300,
                "hyperparams": {"depth": 6, "learning_rate": 0.05},
            },
        }

    def test_initialization(self, temp_dir):
        """Test evaluator initializes correctly."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        assert evaluator.output_dir == temp_dir
        assert temp_dir.exists()

    def test_compare_returns_expected_keys(self, temp_dir, sample_metrics, sample_model_info):
        """compare() should return html, json, and ranking keys."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        assert "html" in result
        assert "json" in result
        assert "ranking" in result
        assert isinstance(result["ranking"], list)

    def test_html_report_created(self, temp_dir, sample_metrics, sample_model_info):
        """HTML report file should be created."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        html_path = Path(result["html"])
        assert html_path.exists()
        assert html_path.name == "comparison.html"
        assert html_path.parent == temp_dir

    def test_json_report_created(self, temp_dir, sample_metrics, sample_model_info):
        """JSON report file should be created."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        json_path = Path(result["json"])
        assert json_path.exists()
        assert json_path.name == "comparison.json"
        assert json_path.parent == temp_dir

    def test_json_content_structure(self, temp_dir, sample_metrics, sample_model_info):
        """JSON report should contain ranking and model data."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        json_path = Path(result["json"])
        data = json.loads(json_path.read_text())

        assert "ranking" in data
        assert "models" in data
        assert isinstance(data["ranking"], list)
        assert isinstance(data["models"], dict)

        # Check model data structure
        for model_name in sample_metrics.keys():
            assert model_name in data["models"]
            assert "metrics" in data["models"][model_name]
            assert "info" in data["models"][model_name]

    def test_ranking_by_auc(self, temp_dir, sample_metrics, sample_model_info):
        """Ranking should be by AUC descending (primary key)."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        ranking = result["ranking"]
        assert len(ranking) == 2
        assert ranking[0] == "lgbm"  # AUC 0.85 > 0.83
        assert ranking[1] == "cat"

    def test_ranking_with_three_models(self, temp_dir):
        """Ranking should work correctly with three models."""
        metrics = {
            "model_a": {"auc": 0.75, "f1": 0.60},
            "model_b": {"auc": 0.90, "f1": 0.80},
            "model_c": {"auc": 0.82, "f1": 0.75},
        }
        model_info = {k: {"model_class": k} for k in metrics.keys()}

        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(metrics, model_info)

        ranking = result["ranking"]
        assert ranking == ["model_b", "model_c", "model_a"]  # By AUC descending

    def test_ranking_with_equal_auc(self, temp_dir):
        """When AUC is equal, ranking should use secondary metrics."""
        metrics = {
            "model_a": {"auc": 0.85, "f1": 0.75, "precision": 0.70, "recall": 0.80},
            "model_b": {"auc": 0.85, "f1": 0.72, "precision": 0.68, "recall": 0.78},
        }
        model_info = {k: {"model_class": k} for k in metrics.keys()}

        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(metrics, model_info)

        ranking = result["ranking"]
        # Equal AUC, model_a has higher F1 (0.75 > 0.72)
        assert ranking[0] == "model_a"
        assert ranking[1] == "model_b"

    def test_html_contains_model_names(self, temp_dir, sample_metrics, sample_model_info):
        """HTML should contain all model names."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        html_content = Path(result["html"]).read_text()
        assert "lgbm" in html_content
        assert "cat" in html_content

    def test_html_contains_metrics_table(self, temp_dir, sample_metrics, sample_model_info):
        """HTML should contain a metrics table with AUC, F1, etc."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        html_content = Path(result["html"]).read_text()
        assert "AUC" in html_content
        assert "F1" in html_content
        assert "Precision" in html_content
        assert "Recall" in html_content
        assert "Accuracy" in html_content

    def test_html_contains_best_values(self, temp_dir, sample_metrics, sample_model_info):
        """HTML should highlight best values with star symbol."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        html_content = Path(result["html"]).read_text()
        # Best AUC (0.85) should have a star
        assert "★" in html_content

    def test_html_contains_links_to_reports(self, temp_dir, sample_metrics, sample_model_info):
        """HTML should contain links to individual model reports."""
        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(sample_metrics, sample_model_info)

        html_content = Path(result["html"]).read_text()
        # Check for links to model-specific reports
        assert 'href="lgbm/evaluation.html"' in html_content
        assert 'href="cat/evaluation.html"' in html_content

    def test_badge_class_mapping(self, temp_dir):
        """Model type badges should have correct Tailwind classes."""
        evaluator = ComparativeEvaluator(str(temp_dir))

        # Test various model types
        model_types = [
            ("lightgbm", "bg-green-100 text-green-800"),
            ("catboost", "bg-blue-100 text-blue-800"),
            ("neural_network", "bg-purple-100 text-purple-800"),
            ("lstm", "bg-pink-100 text-pink-800"),
            ("simple_trend", "bg-yellow-100 text-yellow-800"),
            ("simple_constant", "bg-orange-100 text-orange-800"),
            ("unknown", "bg-gray-100 text-gray-800"),
        ]

        for model_type, expected_class in model_types:
            badge_class = evaluator._get_badge_class(model_type)
            assert badge_class == expected_class

    def test_get_best_model_for_metric(self, temp_dir):
        """_get_best_model_for_metric should return the model with the highest value."""
        metrics = {
            "model_a": {"auc": 0.75, "f1": 0.60},
            "model_b": {"auc": 0.90, "f1": 0.80},
            "model_c": {"auc": 0.82, "f1": 0.75},
        }
        models = {k: {"metrics": v} for k, v in metrics.items()}

        evaluator = ComparativeEvaluator(str(temp_dir))

        assert (
            evaluator._get_best_model_for_metric(["model_a", "model_b", "model_c"], models, "auc")
            == "model_b"
        )
        assert (
            evaluator._get_best_model_for_metric(["model_a", "model_b", "model_c"], models, "f1")
            == "model_b"
        )

    def test_single_model_comparison(self, temp_dir):
        """Comparison report should work with just one model."""
        metrics = {
            "lgbm": {
                "auc": 0.85,
                "f1": 0.72,
                "precision": 0.78,
                "recall": 0.67,
                "threshold": 0.5,
            }
        }
        model_info = {"lgbm": {"model_class": "lightgbm"}}

        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(metrics, model_info)

        assert len(result["ranking"]) == 1
        assert result["ranking"][0] == "lgbm"
        assert Path(result["html"]).exists()
        assert Path(result["json"]).exists()

    def test_missing_optional_metrics(self, temp_dir):
        """Report should handle models with different metrics."""
        metrics = {
            "model_a": {
                "auc": 0.85,
                "f1": 0.72,
                "precision": 0.78,
                "recall": 0.67,
                "accuracy": 0.80,
            },
            "model_b": {"auc": 0.82, "f1": 0.70},  # Missing some metrics
        }
        model_info = {k: {"model_class": k} for k in metrics.keys()}

        evaluator = ComparativeEvaluator(str(temp_dir))
        result = evaluator.compare(metrics, model_info)

        # Should not raise an error
        assert len(result["ranking"]) == 2
        assert Path(result["html"]).exists()
