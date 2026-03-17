"""
Unit tests for RunIndexGenerator.

Tests the scanning of training run directories and HTML index generation.
"""

import json
import tempfile
from pathlib import Path

from energizados.evaluation.index import RunIndexGenerator


class TestRunIndexGenerator:
    """Tests for RunIndexGenerator."""

    def _make_run(
        self, output_dir: Path, run_name: str, metrics: dict = None, model_type: str = "LGBMModel"
    ) -> Path:
        """Helper: create a fake training run directory with evaluation report.

        Args:
            output_dir: Output directory path.
            run_name: Name of the run directory.
            metrics: Optional dictionary of metrics.
            model_type: Model class name.

        Returns:
            Path: Path to the created run directory.
        """
        run_dir = output_dir / run_name
        eval_dir = run_dir / "reports" / "evaluation"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "models").mkdir(exist_ok=True)
        (run_dir / "config").mkdir(exist_ok=True)

        report = {
            "timestamp": "2026-03-03T14:30:00",
            "metrics": metrics or {"auc": 0.85, "f1": 0.72, "precision": 0.80, "recall": 0.65},
            "model_info": {"model_class": model_type},
        }
        (eval_dir / "evaluation_report.json").write_text(json.dumps(report))
        (eval_dir / "evaluation_report.html").write_text("<html>report</html>")
        return run_dir

    def test_scan_runs_finds_directories(self):
        """Verify that scan_runs returns all runs with evaluation reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")
            self._make_run(output_dir, "train-20260302_0900")

            generator = RunIndexGenerator()
            runs = generator.scan_runs(output_dir)

            assert len(runs) == 2

    def test_scan_runs_sorted_newest_first(self):
        """Verify that scan_runs returns runs sorted newest first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260301_1000")
            self._make_run(output_dir, "train-20260303_1430")
            self._make_run(output_dir, "train-20260302_0900")

            generator = RunIndexGenerator()
            runs = generator.scan_runs(output_dir)

            assert runs[0]["run_name"] == "train-20260303_1430"
            assert runs[-1]["run_name"] == "train-20260301_1000"

    def test_scan_runs_skips_missing_json(self):
        """Verify that scan_runs tolerates run directories without evaluation_report.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")

            # Create run dir without JSON
            empty_run = output_dir / "train-20260302_0900"
            empty_run.mkdir()

            generator = RunIndexGenerator()
            runs = generator.scan_runs(output_dir)

            assert len(runs) == 1
            assert runs[0]["run_name"] == "train-20260303_1430"

    def test_scan_runs_skips_invalid_json(self):
        """Verify that scan_runs tolerates run directories with malformed JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")

            # Create run with malformed JSON
            bad_run = output_dir / "train-20260302_0900"
            eval_dir = bad_run / "reports" / "evaluation"
            eval_dir.mkdir(parents=True)
            (eval_dir / "evaluation_report.json").write_text("{invalid json")

            generator = RunIndexGenerator()
            runs = generator.scan_runs(output_dir)

            assert len(runs) == 1

    def test_scan_runs_extracts_metrics(self):
        """Verify that scan_runs correctly extracts metrics from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430", metrics={"auc": 0.92, "f1": 0.88})

            generator = RunIndexGenerator()
            runs = generator.scan_runs(output_dir)

            assert runs[0]["auc"] == 0.92
            assert runs[0]["f1"] == 0.88
            assert runs[0]["model_type"] == "LGBMModel"

    def test_generate_index_html_creates_file(self):
        """Verify that generate_index_html creates output/index.html."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")

            generator = RunIndexGenerator()
            index_path = generator.generate_index_html(output_dir)

            assert index_path is not None
            assert index_path.exists()
            assert index_path.name == "index.html"

    def test_generate_index_html_contains_run_names(self):
        """Verify that the generated HTML contains run names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")
            self._make_run(output_dir, "train-20260302_0900")

            generator = RunIndexGenerator()
            generator.generate_index_html(output_dir)

            html = (output_dir / "index.html").read_text()
            assert "train-20260303_1430" in html
            assert "train-20260302_0900" in html

    def test_generate_index_html_contains_links(self):
        """Verify that the generated HTML contains links to evaluation reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            self._make_run(output_dir, "train-20260303_1430")

            generator = RunIndexGenerator()
            generator.generate_index_html(output_dir)

            html = (output_dir / "index.html").read_text()
            assert "evaluation_report.html" in html
            assert "View Report" in html

    def test_generate_index_html_empty_output(self):
        """Verify that generate_index_html works with no training runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            generator = RunIndexGenerator()
            index_path = generator.generate_index_html(output_dir)

            assert index_path is not None
            html = index_path.read_text()
            assert "No training runs found" in html

    def test_generate_index_html_nonexistent_dir(self):
        """Verify that generate_index_html returns None for a nonexistent directory."""
        generator = RunIndexGenerator()
        result = generator.generate_index_html(Path("/nonexistent/output"))
        assert result is None

    def test_fmt_handles_none(self):
        """Verify that _fmt returns dash for None values."""
        generator = RunIndexGenerator()
        assert generator._fmt(None) == "—"

    def test_fmt_formats_float(self):
        """Verify that _fmt correctly formats float values."""
        generator = RunIndexGenerator()
        assert generator._fmt(0.85432) == "0.8543"
        assert generator._fmt(1.0) == "1.0000"
