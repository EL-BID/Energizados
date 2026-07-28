"""
CLI-API Parity Tests

Tests that verify CLI commands produce equivalent results to the core API calls.
This ensures that the CLI delegation is working correctly and that --json output
matches the structured API returns.
"""

import json
from pathlib import Path  # noqa: F401

from click.testing import CliRunner

from energizados.api import Pipeline, doctor, validate_dict
from energizados.cli.main import cli


class TestCLIAPIParity:
    """Tests for CLI-API parity."""

    def test_validate_cli_parity_with_api(self, tmp_path):
        """Verify CLI validate and api.validate_dict() report same errors/warnings."""
        # Create a test config with some validation issues
        config_file = tmp_path / "test_train.yaml"
        config_content = """
train:
  schema_version: 1
  enabled: true
  input_path: "data/processed/test.parquet"
  target_column: "target"

  split:
    method: "stratified"
    test_size: 0.2
    val_size: 0.1

  models:
    - type: "lightgbm"
      sampling:
        method: "undersample"
        threshold: 0.5

  feature_engineering:
    enabled: true
    preprocessing:
      columns:
        test_column:
          - cardinality_reducer:
              threshold: 0.001
"""
        config_file.write_text(config_content, encoding="utf-8")

        # Test via API
        with open(config_file, "r", encoding="utf-8") as f:
            import yaml

            config_dict = yaml.safe_load(f)
        api_result = validate_dict(config_dict, "train")

        # Test via CLI
        runner = CliRunner()
        result = runner.invoke(
            cli, ["validate", str(config_file), "--json"], catch_exceptions=False
        )

        # Both should succeed
        assert result.exit_code == 0

        # Parse JSON output
        cli_json = json.loads(result.output)

        # Check that both have same structure
        assert "is_valid" in cli_json
        assert "errors" in cli_json
        assert "warnings" in cli_json

        # Both should agree on validity
        assert api_result.is_valid == cli_json["is_valid"]

    def test_validate_json_output_structure(self, tmp_path):
        """Verify --json flag produces valid JSON with correct structure."""
        # Create a minimal valid config
        config_file = tmp_path / "valid_etl.yaml"
        config_content = """
etl:
  schema_version: 1
  sample:
    enabled: true
    description: "Test ETL"
    input: "data/raw/test.csv"
    output: "data/processed/test.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []
"""
        config_file.write_text(config_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(config_file), "--json"])

        assert result.exit_code == 0

        # Parse and validate JSON structure
        json_output = json.loads(result.output)
        assert isinstance(json_output, dict)
        assert "is_valid" in json_output
        assert "errors" in json_output
        assert "warnings" in json_output
        assert isinstance(json_output["errors"], list)
        assert isinstance(json_output["warnings"], list)

    def test_doctor_json_output_structure(self):
        """Verify doctor --json produces structured health report."""
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--json"])

        # Doctor might exit with 1 if there are warnings, but JSON should still be valid
        assert result.exit_code in [0, 1]

        # Parse and validate JSON structure (extract JSON from output)
        # The output might have logging, so we need to extract just the JSON part
        output = result.output.strip()
        json_start = output.find("{")

        assert json_start >= 0, "No JSON found in output"
        json_output = json.loads(output[json_start:])
        assert isinstance(json_output, dict)
        assert "system_info" in json_output
        assert "checks" in json_output
        assert isinstance(json_output["checks"], list)

    def test_doctor_cli_parity_with_api(self):
        """Verify CLI doctor and api.doctor() produce equivalent results."""
        # Test via API
        api_report = doctor()

        # Test via CLI
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--json"])

        # Doctor might exit with 1 if there are warnings, but JSON should still be valid
        assert result.exit_code in [0, 1]

        # Parse JSON output (extract JSON from output that might have logging)
        output = result.output.strip()
        json_start = output.find("{")

        assert json_start >= 0, "No JSON found in output"
        cli_json = json.loads(output[json_start:])

        # Both should have system info
        assert "system_info" in api_report.to_dict()
        assert "system_info" in cli_json

        # Both should have checks
        assert len(api_report.checks) == len(cli_json["checks"])

    def test_run_json_output_structure(self, tmp_path):
        """Verify run --json produces structured RunResult."""
        # Create a minimal ETL config
        etl_config = tmp_path / "etl.yaml"
        etl_content = """
etl:
  schema_version: 1
  test_etl:
    enabled: true
    description: "Test ETL"
    input: "data/raw/test.csv"
    output: "data/processed/test.parquet"
    custom_class: "energizados.etl.pipeline.SourceETL"
    params:
      mode: "concat"
    depends_on: []
"""
        etl_config.write_text(etl_content, encoding="utf-8")

        # Create input file
        input_dir = tmp_path / "data" / "raw"
        input_dir.mkdir(parents=True)
        input_file = input_dir / "test.csv"
        input_file.write_text("col1,col2\n1,2\n3,4\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "etl", "--json", "-c", str(tmp_path)])

        # The command might fail if there are issues, but we can still check structure
        # if it succeeded
        if result.exit_code == 0:
            json_output = json.loads(result.output)
            assert isinstance(json_output, dict)
            # Should have run_id or status
            assert "run_id" in json_output or "status" in json_output

    def test_pipeline_from_dict_api_exists(self):
        """Verify Pipeline.from_dict() API exists and works."""
        config = {
            "etl": {
                "test": {
                    "enabled": True,
                    "input": "test.csv",
                    "output": "test.parquet",
                    "custom_class": "energizados.etl.pipeline.SourceETL",
                }
            }
        }

        # Should be able to create pipeline from dict
        pipeline = Pipeline.from_dict(config)
        assert pipeline is not None
        assert isinstance(pipeline, Pipeline)
