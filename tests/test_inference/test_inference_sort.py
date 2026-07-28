"""Tests for ``sort_by_probability`` in inference output.

Behavioral contract (seam: ``InferenceBuilder(config).build().execute(ctx)`` →
the written predictions file):

``sort_by_probability`` controls the ROW ORDER of the inference output. Default
is ``True``: rows are sorted by ``probability`` DESCENDING (most suspicious
first). Set ``sort_by_probability: false`` to preserve input order.

Sorting is applied AFTER ``output_columns`` selection, on the final frame, so
the probability column moves with its row (input columns reorder too).
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder


class TestSortByProbability:
    """Inference output row ordering by probability."""

    @pytest.fixture
    def mock_model(self):
        """Mock model returning probabilities [0.2, 0.6, 0.9] for rows c1, c2, c3."""
        model = MagicMock()
        model.predict_proba.return_value = np.array([0.2, 0.6, 0.9])
        return model

    def _write_data(self, tmp_path: Path) -> Path:
        data = pd.DataFrame(
            {
                "cliente": ["c1", "c2", "c3"],
                "consumo_1_anterior": [10.0, 50.0, 0.0],
            }
        )
        path = tmp_path / "infer_data.parquet"
        data.to_parquet(path, index=False)
        return path

    def _run(self, config: dict, tmp_path: Path, mock_model) -> pd.DataFrame:
        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None
        step.config["model_path"] = None
        step.config["_resolved_model_path"] = None
        step.config["_resolved_feature_engineering_path"] = None
        step.execute({"model": mock_model})
        out = config["output_path"]
        assert Path(out).exists()
        return pd.read_csv(out)

    def test_default_sorts_by_probability_desc(self, tmp_path, mock_model):
        """Default behavior: output sorted by probability descending."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._run(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_columns": ["cliente", "probability"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        # probas [0.2(c1), 0.6(c2), 0.9(c3)] desc -> [0.9, 0.6, 0.2]
        np.testing.assert_array_almost_equal(df["probability"].values, np.array([0.9, 0.6, 0.2]))
        # cliente reordered to follow its probability
        assert list(df["cliente"].values) == ["c3", "c2", "c1"]

    def test_sort_disabled_preserves_input_order(self, tmp_path, mock_model):
        """sort_by_probability: false keeps the original input row order."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._run(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_columns": ["cliente", "probability"],
                "output_format": "csv",
                "sort_by_probability": False,
            },
            tmp_path,
            mock_model,
        )
        np.testing.assert_array_almost_equal(df["probability"].values, np.array([0.2, 0.6, 0.9]))
        assert list(df["cliente"].values) == ["c1", "c2", "c3"]

    def test_sort_works_without_output_columns(self, tmp_path, mock_model):
        """Default sort applies even with the minimal [prediction, probability] output."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._run(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        assert list(df.columns) == ["prediction", "probability"]
        np.testing.assert_array_almost_equal(df["probability"].values, np.array([0.9, 0.6, 0.2]))
