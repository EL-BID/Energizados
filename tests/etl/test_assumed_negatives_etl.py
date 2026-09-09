"""Unit tests for AssumedNegativesETL.

The ETL derives **Assumed Negatives** (consumption rows whose client id has no
inspection record) via an anti-join on ``id_column`` and materializes them as
a standalone parquet. It must never modify either input source.

Input roles are positional: ``input_paths[0]`` = consumption source,
``input_paths[1]`` = inspections source. Exactly 2 inputs are required —
fewer means a referenced ``@etl`` was disabled and silently dropped by the
orchestrator's resolution, which must fail loudly here.
"""

import logging
from pathlib import Path

import pandas as pd
import pytest

from energizados.core.exceptions import ETLError
from energizados.etl.orchestrator import ETLOrchestrator
from energizados.etl.pipeline import AssumedNegativesETL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_parquet(tmp_path, name, df):
    """Write a DataFrame to tmp_path/<name>.parquet and return its str path."""
    path = tmp_path / name
    df.to_parquet(path, index=False)
    return str(path)


def _consumption_df():
    """5 consumption rows over ids C1..C5."""
    return pd.DataFrame(
        {
            "contract_id": ["C1", "C2", "C3", "C4", "C5"],
            "consumo": [100.0, 200.0, 300.0, 400.0, 500.0],
            "zona": ["N", "S", "N", "S", "N"],
        }
    )


def _inspections_df(ids):
    """Inspection records covering the given ids."""
    return pd.DataFrame({"contract_id": list(ids), "fecha": ["2024-01-01"] * len(ids)})


# ---------------------------------------------------------------------------
# Initialization / configuration contract
# ---------------------------------------------------------------------------


class TestAssumedNegativesInit:
    def test_missing_id_column_raises_valueerror(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2"]))

        with pytest.raises(ValueError, match="id_column"):
            AssumedNegativesETL(name="negatives", input_paths=[consumption, inspections])

    def test_single_input_raises_with_role_hint(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())

        with pytest.raises(ValueError, match="consumption.*inspections|inspections.*consumption"):
            AssumedNegativesETL(
                name="negatives", input_paths=[consumption], id_column="contract_id"
            )

    def test_three_inputs_raise(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2"]))
        extra = _write_parquet(tmp_path, "extra.parquet", _inspections_df(["C1"]))

        with pytest.raises(ValueError, match="2"):
            AssumedNegativesETL(
                name="negatives",
                input_paths=[consumption, inspections, extra],
                id_column="contract_id",
            )

    def test_disabled_ref_drop_hint_in_error(self, tmp_path):
        """A shrunk input list (disabled @ref dropped) must name what happened."""
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())

        with pytest.raises(ValueError, match="disabled"):
            AssumedNegativesETL(
                name="negatives", input_paths=[consumption], id_column="contract_id"
            )

    def test_two_inputs_and_id_column_accepted(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2"]))

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections],
            output_path=str(tmp_path / "out.parquet"),
            id_column="contract_id",
        )
        assert etl.id_column == "contract_id"
        assert len(etl.input_paths) == 2


# ---------------------------------------------------------------------------
# Anti-join behavior (via run)
# ---------------------------------------------------------------------------


class TestAssumedNegativesRun:
    def test_emits_exactly_uninspected_rows(self, tmp_path):
        """Output contains exactly the consumption rows with uninspected ids."""
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2", "C3"]))
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections],
            output_path=output,
            id_column="contract_id",
        )
        result = etl.run(output)

        expected = _consumption_df()[lambda df: df["contract_id"].isin(["C1", "C4", "C5"])]
        assert len(result) == 3
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True), expected.reset_index(drop=True)
        )

        written = pd.read_parquet(output)
        pd.testing.assert_frame_equal(written, expected.reset_index(drop=True))

    def test_no_inspected_id_in_output(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C1", "C5"]))
        output = str(tmp_path / "negatives.parquet")

        AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections],
            output_path=output,
            id_column="contract_id",
        ).run(output)

        written = pd.read_parquet(output)
        assert set(written["contract_id"]) == {"C2", "C3", "C4"}
        assert not set(written["contract_id"]) & {"C1", "C5"}

    def test_empty_antijoin_writes_zero_row_parquet_with_warning(self, tmp_path, caplog):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(
            tmp_path, "inspections.parquet", _inspections_df(["C1", "C2", "C3", "C4", "C5"])
        )
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections],
            output_path=output,
            id_column="contract_id",
        )

        with caplog.at_level(logging.WARNING):
            result = etl.run(output)

        assert len(result) == 0
        assert Path(output).exists(), "0-row parquet must still be written"
        written = pd.read_parquet(output)
        assert len(written) == 0

        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "no assumed negatives" in w.lower() for w in warnings
        ), f"Expected 'no assumed negatives' WARNING, got: {warnings}"

    def test_duplicate_ids_kept_and_counted(self, tmp_path, caplog):
        consumption = pd.DataFrame(
            {
                "contract_id": ["C1", "C1", "C2"],
                "consumo": [10.0, 11.0, 20.0],
            }
        )
        consumption_path = _write_parquet(tmp_path, "consumption.parquet", consumption)
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2"]))
        output = str(tmp_path / "negatives.parquet")

        with caplog.at_level(logging.INFO):
            result = AssumedNegativesETL(
                name="negatives",
                input_paths=[consumption_path, inspections],
                output_path=output,
                id_column="contract_id",
            ).run(output)

        # Both C1 rows emitted — rows are never collapsed
        assert len(result) == 2
        assert list(result["contract_id"]) == ["C1", "C1"]
        assert list(result["consumo"]) == [10.0, 11.0]

        logs = " ".join(r.getMessage() for r in caplog.records)
        assert "duplicat" in logs.lower(), f"Log should report duplicate-id counts, got: {logs}"

    def test_main_dataset_untouched(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2"]))
        output = str(tmp_path / "negatives.parquet")

        before = pd.read_parquet(consumption)

        AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections],
            output_path=output,
            id_column="contract_id",
        ).run(output)

        after = pd.read_parquet(consumption)
        pd.testing.assert_frame_equal(before, after)

    def test_join_stats_logged(self, tmp_path, caplog):
        consumption = pd.DataFrame(
            {
                "contract_id": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10"],
                "consumo": range(10),
            }
        )
        consumption_path = _write_parquet(tmp_path, "consumption.parquet", consumption)
        # C2, C4, C6 are inspected → 3 matched rows, 7 emitted
        inspections = _write_parquet(
            tmp_path, "inspections.parquet", _inspections_df(["C2", "C4", "C6"])
        )
        output = str(tmp_path / "negatives.parquet")

        with caplog.at_level(logging.INFO):
            AssumedNegativesETL(
                name="negatives",
                input_paths=[consumption_path, inspections],
                output_path=output,
                id_column="contract_id",
            ).run(output)

        stats_logs = [
            r.getMessage()
            for r in caplog.records
            if "matched" in r.getMessage() and "emitted" in r.getMessage()
        ]
        assert stats_logs, "Expected a join-stats log line"
        stats_line = stats_logs[0]
        assert "10" in stats_line, f"consumption rows-in missing: {stats_line}"
        assert "3" in stats_line, f"matched count missing: {stats_line}"
        assert "7" in stats_line, f"emitted count missing: {stats_line}"

    def test_id_column_absent_from_inspections_raises_with_role(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        wrong_inspections = _write_parquet(
            tmp_path,
            "inspections.parquet",
            pd.DataFrame({"other_id": ["C1"], "fecha": ["2024-01-01"]}),
        )
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, wrong_inspections],
            output_path=output,
            id_column="contract_id",
        )

        with pytest.raises(ETLError) as excinfo:
            etl.run(output)
        message = str(excinfo.value).lower()
        assert "inspection" in message, f"Error must name the inspection role: {message}"
        assert "contract_id" in message, f"Error must name the missing column: {message}"
        assert "other_id" in message, f"Error must list available columns: {message}"

    def test_id_column_absent_from_consumption_raises_with_role(self, tmp_path):
        wrong_consumption = _write_parquet(
            tmp_path,
            "consumption.parquet",
            pd.DataFrame({"other_id": ["C1"], "consumo": [1.0]}),
        )
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C1"]))
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[wrong_consumption, inspections],
            output_path=output,
            id_column="contract_id",
        )

        with pytest.raises(ETLError) as excinfo:
            etl.run(output)
        message = str(excinfo.value).lower()
        assert "consumption" in message, f"Error must name the consumption role: {message}"
        assert "contract_id" in message

    def test_missing_input_file_raises(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        missing = str(tmp_path / "missing.parquet")
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, missing],
            output_path=output,
            id_column="contract_id",
        )

        with pytest.raises(ETLError, match="[Ff]ile not found"):
            etl.run(output)


# ---------------------------------------------------------------------------
# Directory inputs (Hive-partitioned ETL outputs, e.g. incremental consumos/)
# ---------------------------------------------------------------------------


def _write_partitioned_dir(tmp_path, name, df, n_partitions=2):
    """Write a DataFrame as a Hive-style partitioned directory.

    Layout: tmp_path/<name>/partition=<i>/data.parquet (splits df rows evenly).
    Returns the directory path as str.
    """
    root = tmp_path / name
    chunk = max(1, len(df) // n_partitions)
    for i, start in enumerate(range(0, len(df), chunk)):
        part = df.iloc[start : start + chunk]
        part_dir = root / f"partition={i}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part.to_parquet(part_dir / "data.parquet", index=False)
    return str(root)


class TestAssumedNegativesDirectoryInputs:
    def test_consumption_as_partitioned_directory(self, tmp_path):
        """Consumption given as a Hive dir (e.g. '@consumos' incremental output)."""
        consumption_dir = _write_partitioned_dir(tmp_path, "consumos", _consumption_df())
        inspections = _write_parquet(tmp_path, "inspections.parquet", _inspections_df(["C2", "C3"]))
        output = str(tmp_path / "negatives.parquet")

        result = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption_dir, inspections],
            output_path=output,
            id_column="contract_id",
        ).run(output)

        expected = _consumption_df()[lambda df: df["contract_id"].isin(["C1", "C4", "C5"])]
        assert len(result) == 3
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True), expected.reset_index(drop=True)
        )

    def test_inspections_as_partitioned_directory(self, tmp_path):
        """Inspections given as a Hive dir (e.g. '@inspecciones' incremental output)."""
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspections_dir = _write_partitioned_dir(
            tmp_path, "inspecciones", _inspections_df(["C2", "C3"])
        )
        output = str(tmp_path / "negatives.parquet")

        AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, inspections_dir],
            output_path=output,
            id_column="contract_id",
        ).run(output)

        written = pd.read_parquet(output)
        assert set(written["contract_id"]) == {"C1", "C4", "C5"}

    def test_both_roles_as_directories(self, tmp_path):
        """celesc-style wiring: both inputs are partitioned ETL output dirs."""
        consumption_dir = _write_partitioned_dir(tmp_path, "consumos", _consumption_df())
        inspections_dir = _write_partitioned_dir(
            tmp_path, "inspecciones", _inspections_df(["C2", "C3"])
        )
        output = str(tmp_path / "negatives.parquet")

        AssumedNegativesETL(
            name="negativos",
            input_paths=[consumption_dir, inspections_dir],
            output_path=output,
            id_column="contract_id",
        ).run(output)

        written = pd.read_parquet(output)
        assert set(written["contract_id"]) == {"C1", "C4", "C5"}
        assert list(written.columns) == ["contract_id", "consumo", "zona"]

    def test_empty_directory_raises_etlerror_naming_role(self, tmp_path):
        """A directory with no parquet files must fail naming the role, not crash."""
        empty_dir = tmp_path / "empty_source"
        empty_dir.mkdir()
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        output = str(tmp_path / "negatives.parquet")

        etl = AssumedNegativesETL(
            name="negatives",
            input_paths=[consumption, str(empty_dir)],
            output_path=output,
            id_column="contract_id",
        )

        with pytest.raises(ETLError, match="inspections.*[Nn]o parquet|[Nn]o parquet.*inspections"):
            etl.run(output)


# ---------------------------------------------------------------------------
# Orchestrator integration (@ref resolution)
# ---------------------------------------------------------------------------


class TestAssumedNegativesOrchestrator:
    def test_mixed_refs_resolve_and_run(self, tmp_path):
        """Literal consumption path + '@inspecciones' ref must both resolve."""
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        inspecciones_output = str(tmp_path / "insp_out.parquet")
        negatives_output = str(tmp_path / "negatives.parquet")

        configs = {
            "inspecciones": {
                "enabled": True,
                # Helper ETL writes a fixed parquet; input must exist for resolution
                "input": consumption,
                "output": inspecciones_output,
                "custom_class": "tests.etl.test_assumed_negatives_etl._StaticInspectionsETL",
                "params": {"output_path": inspecciones_output},
                "depends_on": [],
            },
            "negatives": {
                "enabled": True,
                "description": "Assumed negatives anti-join",
                "input": [consumption, "@inspecciones"],
                "output": negatives_output,
                "custom_class": "energizados.etl.pipeline.AssumedNegativesETL",
                "params": {"id_column": "contract_id"},
                "depends_on": ["inspecciones"],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        results = orchestrator.run()

        assert "negatives" in results
        written = pd.read_parquet(negatives_output)
        # C2, C3 inspected → C1, C4, C5 emitted
        assert set(written["contract_id"]) == {"C1", "C4", "C5"}

    def test_disabled_ref_fails_loudly_at_instantiation(self, tmp_path):
        consumption = _write_parquet(tmp_path, "consumption.parquet", _consumption_df())
        negatives_output = str(tmp_path / "negatives.parquet")

        configs = {
            "inspecciones": {
                "enabled": False,
                "input": "unused.parquet",
                "output": str(tmp_path / "insp_out.parquet"),
                "custom_class": "energizados.etl.pipeline.SourceETL",
                "params": {},
                "depends_on": [],
            },
            "negatives": {
                "enabled": True,
                "input": [consumption, "@inspecciones"],
                "output": negatives_output,
                "custom_class": "energizados.etl.pipeline.AssumedNegativesETL",
                "params": {"id_column": "contract_id"},
                "depends_on": [],
            },
        }

        orchestrator = ETLOrchestrator(configs)
        with pytest.raises(ValueError, match="disabled|2"):
            orchestrator.run()


class _StaticInspectionsETL:
    """Tiny helper ETL that writes a fixed inspections parquet (no inputs)."""

    def __init__(self, name=None, input_paths=None, output_path=None, **kwargs):
        from energizados.etl.pipeline import (  # noqa: F401  (pattern reuse)
            CleanFilesETL,
        )

        self.name = name
        self.input_paths = input_paths or []
        self.output_path = output_path

    def run(self, output_path=None):
        df = _inspections_df(["C2", "C3"])
        df.to_parquet(self.output_path, index=False)
        return df
