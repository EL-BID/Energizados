"""Tests for unified ``output_columns`` selection in inference output.

Behavioral contract (seam: ``InferenceBuilder(config).build().execute(ctx)`` →
the written predictions file):

``output_columns`` is the AUTHORITATIVE final selector over the combined output
frame ``[input columns] + [prediction, probability] + [rule_*]``. It is applied
LAST and is SELF-SUFFICIENT: naming an input column in it includes that column
automatically — no ``output_include_input`` needed.

- If ``output_columns`` is set, only the listed columns are written, in order.
- Omitting ``prediction`` from the list drops it from the output.
- Naming an input column includes it even when ``output_include_input`` is false.
- If ``output_columns`` is ABSENT, ALL columns are written (input + prediction +
  probability + any ``rule_*``). The deprecated ``output_include_input`` flag is
  now a redundant no-op (still emits a DeprecationWarning when set).
- If both ``output_columns`` and ``output_include_input`` are set, ``output_columns``
  wins and ``output_include_input`` is ignored (DeprecationWarning).
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from energizados.core.builders.inference_builder import InferenceBuilder


class TestOutputColumnsUnified:
    """Integration tests for unified output_columns selection."""

    @pytest.fixture
    def mock_model(self):
        """Mock model returning predictable probabilities (3 rows)."""
        model = MagicMock()
        model.predict_proba.return_value = np.array([0.2, 0.6, 0.9])
        return model

    def _write_data(self, tmp_path: Path) -> Path:
        """Write a 3-row parquet with identifiable input columns."""
        data = pd.DataFrame(
            {
                "cliente": ["c1", "c2", "c3"],
                "actividad": ["COMERCIO", "INDUSTRIA", "RESIDENCIAL"],
                "zona": ["NORTE", "SUR", "NORTE"],
                "consumo_1_anterior": [10.0, 50.0, 0.0],
            }
        )
        path = tmp_path / "infer_data.parquet"
        data.to_parquet(path, index=False)
        return path

    def _build_and_execute(self, config: dict, tmp_path: Path, mock_model) -> pd.DataFrame:
        """Build the inference step, execute against the mock model, return output frame."""
        builder = InferenceBuilder(config)
        step = builder.build()
        assert step is not None, "build() should not return None with valid config"
        # Force resolution to the context model (no on-disk model).
        step.config["model_path"] = None
        step.config["_resolved_model_path"] = None
        step.config["_resolved_feature_engineering_path"] = None

        output_path = config["output_path"]
        step.execute({"model": mock_model})
        assert Path(output_path).exists(), "output file should be written"
        fmt = config.get("output_format", "csv")
        reader = pd.read_csv if fmt == "csv" else pd.read_parquet
        return reader(output_path)

    # -- Backward compatibility (no output_columns) ---------------------------

    def test_no_output_columns_returns_all_columns(self, tmp_path, mock_model):
        """No output_columns → ALL columns (input + prediction + probability)."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": False,
                "output_format": "csv",
                # Isolate column-selection behavior from row-ordering: the
                # global default now sorts by probability desc, which would
                # reorder these rows. Sort is covered in test_inference_sort.py.
                "sort_by_probability": False,
            },
            tmp_path,
            mock_model,
        )
        # All input columns prepended, then prediction + probability.
        assert list(df.columns[:4]) == ["cliente", "actividad", "zona", "consumo_1_anterior"]
        assert "prediction" in df.columns
        assert "probability" in df.columns
        # probas [0.2, 0.6, 0.9] @ 0.5 → [0, 1, 1]
        np.testing.assert_array_equal(df["prediction"].values, np.array([0, 1, 1]))

    def test_no_output_columns_no_include_input_key_returns_all(self, tmp_path, mock_model):
        """No output_columns and no output_include_input key → ALL columns."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_format": "csv",
                "sort_by_probability": False,
            },
            tmp_path,
            mock_model,
        )
        # Default behavior includes all input columns.
        assert list(df.columns[:4]) == ["cliente", "actividad", "zona", "consumo_1_anterior"]
        assert "prediction" in df.columns
        assert "probability" in df.columns

    def test_no_output_columns_with_include_input_keeps_all(self, tmp_path, mock_model):
        """No output_columns + output_include_input=true → all input + prediction + probability."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": True,
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        # All input columns prepended, then prediction + probability.
        assert list(df.columns[:4]) == ["cliente", "actividad", "zona", "consumo_1_anterior"]
        assert "prediction" in df.columns
        assert "probability" in df.columns

    # -- Unified selection (the new behavior) --------------------------------

    def test_output_columns_selects_input_and_result_columns(self, tmp_path, mock_model):
        """output_columns selects a mix of input + result columns (bug-fix core)."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": True,
                "output_columns": ["cliente", "prediction", "probability"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        # Exactly the listed columns, in order; unlisted input cols are dropped.
        assert list(df.columns) == ["cliente", "prediction", "probability"]
        assert "actividad" not in df.columns
        assert "zona" not in df.columns

    def test_output_columns_omits_prediction_when_not_listed(self, tmp_path, mock_model):
        """Omitting 'prediction' from output_columns drops it from the output."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": True,
                "output_columns": ["cliente", "probability"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        assert list(df.columns) == ["cliente", "probability"]
        assert "prediction" not in df.columns

    def test_output_columns_respects_order(self, tmp_path, mock_model):
        """output_columns order is honored in the written file."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": True,
                "output_columns": ["probability", "zona", "prediction"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        assert list(df.columns) == ["probability", "zona", "prediction"]

    def test_output_columns_includes_input_without_include_input(self, tmp_path, mock_model):
        """output_columns is self-sufficient: naming an input column includes it
        even when output_include_input is false (or absent). No warning emitted."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": False,
                "output_columns": ["cliente", "probability"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        # 'cliente' is auto-included because it is named in output_columns — no
        # output_include_input needed.
        assert list(df.columns) == ["cliente", "probability"]

    def test_output_include_input_true_deprecated_warns(self, tmp_path, mock_model):
        """output_include_input: true alone still works (all input) but is deprecated."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        with pytest.warns(DeprecationWarning, match="output_include_input"):
            df = self._build_and_execute(
                {
                    "threshold": 0.5,
                    "input_path": str(data_path),
                    "output_path": out,
                    "output_include_input": True,
                    "output_format": "csv",
                },
                tmp_path,
                mock_model,
            )
        # Legacy all-input behavior preserved.
        assert "cliente" in df.columns
        assert "actividad" in df.columns
        assert "prediction" in df.columns
        assert "probability" in df.columns

    def test_output_columns_overrides_output_include_input(self, tmp_path, mock_model):
        """When both are set, output_columns wins; output_include_input is ignored."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        with pytest.warns(DeprecationWarning, match="ignored"):
            df = self._build_and_execute(
                {
                    "threshold": 0.5,
                    "input_path": str(data_path),
                    "output_path": out,
                    "output_include_input": True,
                    "output_columns": ["cliente", "probability"],
                    "output_format": "csv",
                },
                tmp_path,
                mock_model,
            )
        # output_columns selects exactly these two; prediction dropped.
        assert list(df.columns) == ["cliente", "probability"]
        assert "prediction" not in df.columns

    def test_output_columns_unknown_column_warns_and_skipped(self, tmp_path, mock_model, caplog):
        """A column that exists nowhere is warned about and skipped, no crash."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        with caplog.at_level("WARNING"):
            df = self._build_and_execute(
                {
                    "threshold": 0.5,
                    "input_path": str(data_path),
                    "output_path": out,
                    "output_include_input": True,
                    "output_columns": ["cliente", "no_existe_esta_columna", "probability"],
                    "output_format": "csv",
                },
                tmp_path,
                mock_model,
            )
        assert list(df.columns) == ["cliente", "probability"]
        assert any("no_existe_esta_columna" in rec.getMessage() for rec in caplog.records)

    def test_output_columns_drops_rule_columns_when_not_listed(self, tmp_path, mock_model):
        """rule_* columns are dropped when output_columns does not list them."""
        data_path = self._write_data(tmp_path)
        out = str(tmp_path / "preds.csv")
        df = self._build_and_execute(
            {
                "threshold": 0.5,
                "input_path": str(data_path),
                "output_path": out,
                "output_include_input": True,
                "business_rules": {
                    "enabled": True,
                    "rules": [
                        {
                            "name": "consumo_cero",
                            "condition": "(`consumo_1_anterior` == 0)",
                            "action": "flag",
                            "value": 1.0,
                        }
                    ],
                    "output": {"add_rule_columns": True},
                },
                "output_columns": ["cliente", "probability"],
                "output_format": "csv",
            },
            tmp_path,
            mock_model,
        )
        assert list(df.columns) == ["cliente", "probability"]
        assert "rule_consumo_cero" not in df.columns
