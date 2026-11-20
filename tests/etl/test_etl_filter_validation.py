"""Validation-surface tests for ETL row filtering (SDD §6.1, §6.4, §6.6).

Covers the T3 surface: the ETL JSON schema accepting structured inputs,
both validators (CLI ``_validate_etl_section`` and the service-layer
``ConfigValidator``) reporting malformed input objects and both filter
levels before execution, the ``energizados validate`` command, and the
``energizados run etl --dry-run`` plan display.
"""

import json

import pytest
import yaml
from click.testing import CliRunner

from energizados.api import validate_dict
from energizados.cli.main import cli  # type: ignore[import-untyped]
from energizados.core.schemas.config_validator import ConfigValidator


def _etl_section(inputs, params=None):
    """Build a minimal valid etl section with the given input spec."""
    return {
        "schema_version": 1,
        "sample": {
            "enabled": True,
            "input": inputs,
            "output": "data/processed/out.parquet",
            "custom_class": "energizados.etl.pipeline.SourceETL",
            "params": {"mode": "concat"} if params is None else params,
            "depends_on": [],
        },
    }


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch):
    """Keep rich from wrapping long paths/messages inside CLI output."""
    monkeypatch.setenv("COLUMNS", "500")


def _write_config(tmp_path, etl_section, name="etl.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump({"etl": etl_section}, sort_keys=False), encoding="utf-8")
    return path


class TestSchemaAcceptsStructuredInputs:
    """ETL_SCHEMA: legacy strings stay valid; structured items are checked."""

    def test_legacy_string_input_is_valid(self):
        errors = ConfigValidator().validate_config({"etl": _etl_section("data/raw/a.csv")})
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_legacy_list_of_strings_is_valid(self):
        errors = ConfigValidator().validate_config(
            {"etl": _etl_section(["data/raw/a.csv", "data/raw/b.csv"])}
        )
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_mixed_string_and_structured_inputs_are_valid(self):
        inputs = [
            "data/raw/a.csv",
            {"path": "data/raw/b.csv", "filter": {"zona": "NORTE"}},
            {
                "path": "data/raw/c_*.csv",
                "filter": {"_expr": "consumo > 0"},
            },
        ]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_structured_input_unknown_key_is_rejected(self):
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": "NORTE"}, "bad": 1}]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors, "Expected schema errors for unknown key"
        assert any("'bad'" in e.message for e in errors), [str(e) for e in errors]

    def test_structured_input_missing_path_is_rejected(self):
        inputs = [{"filter": {"zona": "NORTE"}}]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors, "Expected schema errors for missing 'path'"

    def test_structured_input_empty_path_is_rejected(self):
        inputs = [{"path": "", "filter": {"zona": "NORTE"}}]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors, "Expected schema errors for empty 'path'"

    def test_structured_input_non_string_path_is_rejected(self):
        inputs = [{"path": 123}]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors, "Expected schema errors for non-string 'path'"

    def test_structured_input_non_mapping_filter_is_rejected(self):
        inputs = [{"path": "data/raw/b.csv", "filter": 5}]
        errors = ConfigValidator().validate_config({"etl": _etl_section(inputs)})
        assert errors, "Expected schema errors for non-mapping filter"
        assert any("filter" in e.message for e in errors), [str(e) for e in errors]


class TestConfigValidatorReportsFilterGrammar:
    """Service-layer ConfigValidator reports both filter levels as results."""

    def _errors(self, config):
        # Must return result objects, never leak exceptions.
        return ConfigValidator().validate_config(config)

    def test_input_filter_unknown_operator_reported(self):
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": {"~": "NORTE"}}}]
        errors = self._errors({"etl": _etl_section(inputs)})
        assert any("unknown operator '~'" in e.message for e in errors), [str(e) for e in errors]

    def test_input_filter_non_mapping_reported(self):
        inputs = [{"path": "data/raw/b.csv", "filter": 5}]
        errors = self._errors({"etl": _etl_section(inputs)})
        assert any(
            "input filter" in e.message and "must be a mapping" in e.message for e in errors
        ), [str(e) for e in errors]

    def test_input_filter_expr_must_be_string_reported(self):
        inputs = [{"path": "data/raw/b.csv", "filter": {"_expr": 3}}]
        errors = self._errors({"etl": _etl_section(inputs)})
        assert any("_expr must be a string" in e.message for e in errors), [str(e) for e in errors]

    def test_etl_level_filter_unknown_operator_reported(self):
        params = {"mode": "concat", "filter": {"consumo": {">=": 0, "<>": 5}}}
        errors = self._errors({"etl": _etl_section(["data/raw/a.csv"], params)})
        assert any("unknown operator '<>'" in e.message for e in errors), [str(e) for e in errors]

    def test_etl_level_filter_non_mapping_reported(self):
        params = {"mode": "concat", "filter": "nope"}
        errors = self._errors({"etl": _etl_section(["data/raw/a.csv"], params)})
        assert any(
            "ETL-level filter" in e.message and "must be a mapping" in e.message for e in errors
        ), [str(e) for e in errors]

    def test_valid_filters_at_both_levels_report_no_errors(self):
        inputs = [
            {"path": "data/raw/b.csv", "filter": {"zona": ["N", "S"], "_expr": "consumo > 0"}}
        ]
        params = {"mode": "concat", "filter": {"consumo": {">": 0, "<=": 100}}}
        errors = self._errors({"etl": _etl_section(inputs, params)})
        assert errors == [], f"Expected no errors, got: {[str(e) for e in errors]}"


class TestCliValidateCommand:
    """`energizados validate` must report ETL filter problems and exit non-zero."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_cli_validate_accepts_legacy_and_mixed_inputs(self, tmp_path):
        inputs = ["data/raw/a.csv", {"path": "data/raw/b.csv", "filter": {"zona": "NORTE"}}]
        config = _write_config(tmp_path, _etl_section(inputs))

        result = self.runner.invoke(cli, ["validate", str(config)], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "Configuration is valid" in result.output

    def test_cli_validate_rejects_malformed_input_object(self, tmp_path):
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": "NORTE"}, "bad": 1}]
        config = _write_config(tmp_path, _etl_section(inputs))

        result = self.runner.invoke(cli, ["validate", str(config)], catch_exceptions=False)

        assert result.exit_code != 0, result.output
        assert "Configuration is valid" not in result.output
        assert (
            "structured input requires a non-empty 'path' and only allows 'path'/'filter'"
            in result.output
        )

    def test_cli_validate_rejects_unknown_operator_in_input_filter(self, tmp_path):
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": {"~": "NORTE"}}}]
        config = _write_config(tmp_path, _etl_section(inputs))

        result = self.runner.invoke(cli, ["validate", str(config)], catch_exceptions=False)

        assert result.exit_code != 0, result.output
        assert "unknown operator '~'" in result.output
        assert "Configuration is valid" not in result.output

    def test_cli_validate_rejects_malformed_etl_level_filter(self, tmp_path):
        params = {"mode": "concat", "filter": "nope"}
        config = _write_config(tmp_path, _etl_section(["data/raw/a.csv"], params))

        result = self.runner.invoke(cli, ["validate", str(config)], catch_exceptions=False)

        assert result.exit_code != 0, result.output
        assert "ETL-level filter" in result.output
        assert "Configuration is valid" not in result.output

    def test_cli_validate_json_reports_invalid_for_bad_filter(self, tmp_path):
        params = {"mode": "concat", "filter": {"consumo": {">": 0, "<>": 5}}}
        config = _write_config(tmp_path, _etl_section(["data/raw/a.csv"], params))

        result = self.runner.invoke(
            cli, ["validate", str(config), "--json"], catch_exceptions=False
        )

        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["is_valid"] is False
        assert payload["errors"], "Expected errors in JSON output"
        assert any("unknown operator '<>'" in e["message"] for e in payload["errors"])


class TestServiceLayerValidateDict:
    """`validate_dict` must return result objects, never leak exceptions."""

    def test_validate_dict_returns_result_for_malformed_filters(self):
        inputs = [{"path": "data/raw/b.csv", "filter": 5}]
        params = {"mode": "concat", "filter": "nope"}
        config = {"etl": _etl_section(inputs, params)}

        result = validate_dict(config, "etl")

        # Normal result object, no exception leakage.
        assert hasattr(result, "errors")
        assert isinstance(result.errors, list)
        assert hasattr(result, "is_valid")

    def test_validate_dict_invalid_for_malformed_input_level_filter(self):
        """Malformed input-level filter grammar makes is_valid False (SDD §6.6)."""
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": {"~": "NORTE"}}}]
        config = {"etl": _etl_section(inputs)}

        result = validate_dict(config, "etl")

        assert result.is_valid is False
        assert any(
            "input filter" in e.message and "unknown operator '~'" in e.message
            for e in result.errors
        ), [e.message for e in result.errors]

    def test_validate_dict_invalid_for_malformed_input_object(self):
        """Structured input objects require a non-empty 'path' and reject unknown keys."""
        inputs = [{"path": "data/raw/b.csv", "filter": {"zona": "NORTE"}, "bad": 1}]
        config = {"etl": _etl_section(inputs)}

        result = validate_dict(config, "etl")

        assert result.is_valid is False
        assert any(
            "structured input requires a non-empty 'path'" in e.message for e in result.errors
        ), [e.message for e in result.errors]

    def test_validate_dict_invalid_for_malformed_etl_level_filter(self):
        """Malformed ETL-level filter grammar makes is_valid False (SDD §6.6)."""
        params = {"mode": "concat", "filter": {"consumo": {">": 0, "<>": 5}}}
        config = {"etl": _etl_section(["data/raw/a.csv"], params)}

        result = validate_dict(config, "etl")

        assert result.is_valid is False
        assert any(
            "ETL-level filter" in e.message and "unknown operator '<>'" in e.message
            for e in result.errors
        ), [e.message for e in result.errors]

    def test_validate_dict_valid_filters_at_both_levels(self):
        """Valid filters at both levels keep the config valid through validate_dict."""
        inputs = [
            "data/raw/a.csv",
            {"path": "data/raw/b.csv", "filter": {"zona": ["N", "S"]}},
        ]
        params = {"mode": "concat", "filter": {"consumo": {">": 0, "<=": 100}}}
        config = {"etl": _etl_section(inputs, params)}

        result = validate_dict(config, "etl")

        assert result.is_valid is True, [e.message for e in result.errors]


class TestDryRun:
    """`energizados run etl --dry-run` accepts structured inputs."""

    def setup_method(self):
        self.runner = CliRunner()

    def _project(self, tmp_path, inputs):
        data_dir = tmp_path / "data" / "raw"
        data_dir.mkdir(parents=True)
        (data_dir / "a.csv").write_text("id\n1\n", encoding="utf-8")
        (data_dir / "b.csv").write_text("id\n2\n", encoding="utf-8")
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        section = _etl_section(inputs)
        section["sample"]["input"] = [
            str(data_dir / "a.csv"),
            {"path": str(data_dir / "b.csv"), "filter": {"zona": "NORTE"}},
        ]
        (config_dir / "etl.yaml").write_text(
            yaml.safe_dump({"etl": section}, sort_keys=False), encoding="utf-8"
        )
        return tmp_path

    def test_dry_run_shows_resolved_paths_without_mapping_repr(self, tmp_path, monkeypatch):
        project = self._project(tmp_path, ["ignored"])
        monkeypatch.chdir(project)

        result = self.runner.invoke(cli, ["run", "etl", "--dry-run"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert str(project / "data" / "raw" / "a.csv") in result.output
        assert str(project / "data" / "raw" / "b.csv") in result.output
        assert "'path':" not in result.output

    def test_dry_run_does_not_crash_on_malformed_structured_input(self, tmp_path, monkeypatch):
        project = self._project(tmp_path, ["ignored"])
        config_path = project / "config" / "etl.yaml"
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        loaded["etl"]["sample"]["input"] = [{"unknown_key": 1}]
        config_path.write_text(yaml.safe_dump(loaded, sort_keys=False), encoding="utf-8")
        monkeypatch.chdir(project)

        result = self.runner.invoke(cli, ["run", "etl", "--dry-run"], catch_exceptions=False)

        assert result.exit_code == 0, result.output
        assert "Execution Plan" in result.output
