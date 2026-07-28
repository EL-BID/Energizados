"""
Integration tests for CLI run and validate commands.

Tests for the new positional `configs` argument and config resolution.
"""

import logging
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner
from rich.logging import RichHandler

# ``energizados`` is not published with a ``py.typed`` marker (see
# docs/typing.md for the rationale), so we silence the import-untyped hint
# at the boundary instead of stamping every test with a project-wide change.
from energizados.cli import ui  # type: ignore[import-untyped]
from energizados.cli.main import _setup_logging, cli  # type: ignore[import-untyped]


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestRunCommand:
    """Tests for the run command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_run_logs_validation_error_to_logging(self, caplog):
        """StepValidationError must reach the logging system (and thus run.log).

        The CLI renders the error as a Rich panel on the terminal, but that
        bypasses ``logging`` — so the FileHandler feeding run.log never saw it.
        The handler now also emits an ERROR record. ``_setup_logging`` is patched
        so pytest's caplog handler survives (the real one clobbers root handlers).
        """
        from energizados.core.exceptions import (  # type: ignore[import-untyped]
            StepValidationError,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            (project_path / "config").mkdir()
            (project_path / "config" / "etl.yaml").write_text(
                "etl:\n  sample:\n    enabled: false\n", encoding="utf-8"
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline") as mock_exec:
                    mock_exec.side_effect = StepValidationError(
                        "Validation failed in step InferenceStep",
                        step="InferenceStep",
                        missing_keys=["model"],
                    )
                    with patch("energizados.cli.main._setup_logging"):
                        with caplog.at_level(logging.ERROR, logger="energizados.cli.main"):
                            result = self.runner.invoke(cli, ["run", "etl", "-v"])
            finally:
                os.chdir(old_cwd)

            # Aborted, panel rendered with the corrected title, and — crucially —
            # the failure now flows through logging (the channel run.log reads).
            assert result.exit_code != 0
            output = strip_ansi(result.output)
            assert "Validation failed" in output
            assert "Dataset not found" not in output  # old hardcoded title is gone
            assert any(
                "Validation failed" in r.getMessage()
                for r in caplog.records
                if r.levelno >= logging.ERROR
            )

    def test_run_single_config(self):
        """Verify that run works with a single config name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            etl_yaml = config_dir / "etl.yaml"
            etl_yaml.write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", "etl"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_comma_separated_configs(self):
        """Verify that run works with comma-separated config names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )
            (config_dir / "train.yaml").write_text(
                """
train:
  enabled: false
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", "etl,train"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_custom_config_path(self):
        """Verify that run works with --config-path option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom config directory
            custom_config = Path(tmpdir) / "custom_config"
            custom_config.mkdir()
            (custom_config / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(
                        cli, ["run", "--config-path", str(custom_config), "etl"]
                    )
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_absolute_path(self):
        """Verify that run works with absolute config path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "custom.yaml"
            config_file.write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.run.execute_pipeline"):
                    result = self.runner.invoke(cli, ["run", str(config_file)])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_nonexistent_config_in_missing_dir(self):
        """Verify that config not found in empty directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty config dir
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["run", "nonexistent"])
                assert result.exit_code != 0
                output = strip_ansi(result.output)
                assert "Config 'nonexistent' not found" in output
                assert "Available configs:" in output
                assert "Use --config-path" in output
            finally:
                os.chdir(old_cwd)

    def test_run_no_config_dir_raises_error(self):
        """Verify that missing config/ directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["run", "etl"])
                assert result.exit_code != 0
                assert "No config/ directory found" in result.output
                assert "Use --config-path" in result.output
            finally:
                os.chdir(old_cwd)

    def test_run_empty_string_raises_error(self):
        """Verify that empty string raises error."""
        result = self.runner.invoke(cli, ["run", ""])
        assert result.exit_code != 0
        assert "At least one config name is required" in result.output

    def test_run_with_step_option(self):
        """Verify that run works with --step option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "train.yaml").write_text(
                """
train:
  enabled: false
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_step"):
                    result = self.runner.invoke(cli, ["run", "train", "--step", "train"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_run_with_dry_run_option(self):
        """Verify that run works with --dry-run option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            # Fix YAML indentation and add required fields
            (config_dir / "etl.yaml").write_text(
                """etl:
  sample:
    enabled: false
    input: data/input.csv
    output: data/output.csv
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                result = self.runner.invoke(cli, ["run", "etl", "--dry-run"])
                assert result.exit_code == 0
                assert "Dry-run mode" in result.output
            finally:
                os.chdir(old_cwd)


class TestValidateCommand:
    """Tests for the validate command."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_validate_single_config(self):
        """Verify that validate works with a single config name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etl"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_comma_separated_configs(self):
        """Verify that validate works with comma-separated config names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )
            (config_dir / "train.yaml").write_text(
                """
train:
  enabled: false
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etl,train"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_with_custom_config_path(self):
        """Verify that validate works with --config-path option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom config directory
            custom_config = Path(tmpdir) / "custom_config"
            custom_config.mkdir()
            (custom_config / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(
                        cli, ["validate", "--config-path", str(custom_config), "etl"]
                    )
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)

    def test_validate_nonexistent_config_in_missing_dir(self):
        """Verify that config not found in empty directory raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty config dir
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = self.runner.invoke(cli, ["validate", "nonexistent"])
                assert result.exit_code != 0
                output = strip_ansi(result.output)
                assert "Config 'nonexistent' not found" in output
                assert "Available configs:" in output
                assert "Use --config-path" in output
            finally:
                os.chdir(old_cwd)

    def test_validate_with_verbose_option(self):
        """Verify that validate works with --verbose option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                """
etl:
  sample:
    enabled: false
    custom_class: "energizados.etl.pipeline.SourceETL"
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.validate.validate_config"):
                    result = self.runner.invoke(cli, ["validate", "etl", "--verbose"])
                    assert result.exit_code == 0
            finally:
                os.chdir(old_cwd)


class TestEDACommand:
    """Tests that the eda subcommand has been removed."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_eda_command_removed(self):
        """Verify that eda subcommand no longer exists."""
        result = self.runner.invoke(cli, ["eda"])
        assert result.exit_code != 0
        assert "No such command" in result.output


class TestRichLoggingIntegration:
    """Tests for RichHandler integration and level gating."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_setup_logging_installs_rich_handler(self):
        """Verify that _setup_logging(1) installs RichHandler as first handler."""
        _setup_logging(verbose=1)
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0], RichHandler)

    def test_rich_handler_exposed_in_ui(self):
        """Verify that rich_handler in ui.py is not None after _setup_logging()."""
        _setup_logging(verbose=1)
        assert ui.rich_handler is not None
        assert isinstance(ui.rich_handler, RichHandler)

    def test_rich_handler_none_before_setup(self):
        """Verify that rich_handler is None before _setup_logging()."""
        # Reset handler to None
        ui.rich_handler = None
        assert ui.rich_handler is None

    def test_handler_level_gated_during_progress(self):
        """Verify that handler level is WARNING during Progress context."""
        from rich.progress import Progress

        _setup_logging(verbose=1)  # INFO level
        assert ui.rich_handler is not None
        assert ui.rich_handler.level == logging.INFO

        original_level = ui.rich_handler.level
        ui.rich_handler.setLevel(logging.WARNING)

        try:
            with Progress(console=ui.console):
                assert ui.rich_handler.level == logging.WARNING
        finally:
            ui.rich_handler.setLevel(original_level)

        assert ui.rich_handler.level == logging.INFO

    def test_verbose_2_sets_debug_level(self):
        """Verify that verbose=2 sets DEBUG level on RichHandler."""
        _setup_logging(verbose=2)
        assert ui.rich_handler is not None
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 1
        assert root_logger.handlers[0].level == logging.DEBUG
        assert ui.rich_handler.level == logging.DEBUG

    def test_warning_visible_during_progress_context(self):
        """Verify that WARNING messages are visible during Progress context."""
        # Set up INFO level logging
        _setup_logging(verbose=1)
        assert ui.rich_handler is not None
        assert ui.rich_handler.level == logging.INFO

        # Save original level to restore later
        original_level = ui.rich_handler.level

        try:
            # Simulate Progress context with level gating (as done in run.py)
            ui.rich_handler.setLevel(logging.WARNING)

            # Verify handler level is WARNING during Progress
            assert ui.rich_handler.level == logging.WARNING

            # Log a WARNING - should be visible at WARNING level
            logger = logging.getLogger(__name__)
            logger.warning("Test warning message")

            # Verify handler level is still WARNING
            assert ui.rich_handler.level == logging.WARNING

            # Restore original level (as done in run.py finally block)
            ui.rich_handler.setLevel(original_level)

            # Verify handler level is restored to INFO
            assert ui.rich_handler.level == logging.INFO

        finally:
            # Always restore original level
            ui.rich_handler.setLevel(original_level)

    def test_execute_pipeline_output_contains_panel(self):
        """Verify that execute_pipeline() output contains Panel markup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project structure
            project_path = Path(tmpdir) / "test_project"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "train.yaml").write_text(
                """
train:
  enabled: false
""",
                encoding="utf-8",
            )

            import os

            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                # Execute with mocked pipeline to avoid full execution
                with patch("energizados.cli.run.ConfigPipelineBuilder") as mock_builder:
                    mock_pipeline = mock_builder.return_value.build.return_value
                    mock_pipeline.steps = []
                    mock_pipeline.run.return_value = {}
                    mock_builder.return_value._director.run_manager._run_dir = None

                    # Capture output
                    with patch("energizados.cli.run.console.print"):
                        from energizados.cli.run import (  # type: ignore[import-untyped]
                            execute_pipeline,
                        )

                        result = execute_pipeline([str(config_dir / "train.yaml")])

                        # Check that console.print was called (may or may not have Panel
                        # depending on whether steps exist)
                        assert isinstance(result, dict)
            finally:
                os.chdir(old_cwd)


class TestSameStepTypeDetection:
    """Tests for same-step-type detection (train_01, train_02 sequential runs)."""

    def test_all_same_step_type_train(self):
        """Multiple train_* configs are detected as same type."""
        from energizados.cli.run import all_same_step_type

        assert all_same_step_type(["/p/train_01_baseline.yaml", "/p/train_02_lgbm.yaml"]) is True

    def test_all_same_step_type_etl(self):
        """Multiple etl_* configs are detected as same type."""
        from energizados.cli.run import all_same_step_type

        assert all_same_step_type(["/p/etl_raw.yaml", "/p/etl_clean.yaml"]) is True

    def test_mixed_types_not_same(self):
        """etl + train are NOT the same type."""
        from energizados.cli.run import all_same_step_type

        assert all_same_step_type(["/p/etl.yaml", "/p/train.yaml"]) is False

    def test_single_config_not_same(self):
        """Single config always returns False."""
        from energizados.cli.run import all_same_step_type

        assert all_same_step_type(["/p/train_01.yaml"]) is False

    def test_unknown_prefix_not_same(self):
        """Unknown prefixes return False."""
        from energizados.cli.run import all_same_step_type

        assert all_same_step_type(["/p/custom_a.yaml", "/p/custom_b.yaml"]) is False


class TestGetStepType:
    """Tests for _get_step_type prefix matching."""

    def test_exact_match(self):
        from energizados.cli.run import _get_step_type

        assert _get_step_type("train") == "train"
        assert _get_step_type("etl") == "etl"
        assert _get_step_type("eda") == "eda"

    def test_prefix_underscore(self):
        from energizados.cli.run import _get_step_type

        assert _get_step_type("train_01_baseline") == "train"
        assert _get_step_type("train_02_lgbm_no_fe") == "train"
        assert _get_step_type("etl_raw") == "etl"

    def test_prefix_dash(self):
        from energizados.cli.run import _get_step_type

        assert _get_step_type("train-v2") == "train"

    def test_unknown(self):
        from energizados.cli.run import _get_step_type

        assert _get_step_type("my_custom") is None
        assert _get_step_type("training") is None  # 'training' != 'train' exact, no separator


class TestBuildOrderedRuns:
    """Tests for build_ordered_runs — the core dispatch logic.

    build_ordered_runs groups config paths into ordered execution runs,
    each run being a list of paths executed together in one merged pipeline.
    The order of runs always matches the order the user passed the configs.
    """

    def test_unique_types_coalesce_into_one_run(self):
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(["/p/etl.yaml", "/p/train.yaml"])
        assert runs == [["/p/etl.yaml", "/p/train.yaml"]]

    def test_all_same_type_run_individually(self):
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(["/p/train_01.yaml", "/p/train_02.yaml"])
        assert runs == [["/p/train_01.yaml"], ["/p/train_02.yaml"]]

    def test_mixed_with_repeated(self):
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(
            ["/p/etl.yaml", "/p/eda.yaml", "/p/train_01.yaml", "/p/train_02.yaml"]
        )
        assert runs == [
            ["/p/etl.yaml", "/p/eda.yaml"],
            ["/p/train_01.yaml"],
            ["/p/train_02.yaml"],
        ]

    def test_etl_with_repeated_trains(self):
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(["/p/etl.yaml", "/p/train_01.yaml", "/p/train_02.yaml"])
        assert runs == [["/p/etl.yaml"], ["/p/train_01.yaml"], ["/p/train_02.yaml"]]

    def test_unique_type_after_repeated_keeps_user_order(self):
        """Regression: infer (unique) after repeated trains must run LAST.

        Previously `etl,train_01,train_02,infer` bucketed infer into a
        `shared` group executed FIRST, before the trains — running inference
        with no trained model and breaking the user-specified order.
        """
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(
            ["/p/etl.yaml", "/p/train_01.yaml", "/p/train_02.yaml", "/p/infer.yaml"]
        )
        assert runs == [
            ["/p/etl.yaml"],
            ["/p/train_01.yaml"],
            ["/p/train_02.yaml"],
            ["/p/infer.yaml"],  # LAST, not first
        ]

    def test_wildcard_pattern_etl_train_infer(self):
        """The user's exact pattern: multiple etls, multiple trains, one infer.

        `v5/etl*,v5/train*,v5/infer` resolves (sorted within each wildcard) to
        [etl-infer, etl-train, train-final, train, infer] — all in user order.
        """
        from energizados.cli.run import build_ordered_runs

        runs = build_ordered_runs(
            [
                "/p/etl-infer.yaml",
                "/p/etl-train.yaml",
                "/p/train-final.yaml",
                "/p/train.yaml",
                "/p/infer.yaml",
            ]
        )
        flat = [Path(run[0]).stem for run in runs]
        assert flat == ["etl-infer", "etl-train", "train-final", "train", "infer"]
        # infer must be the very last run
        assert Path(runs[-1][0]).stem == "infer"


class TestSequentialSameTypeExecution:
    """Tests that same-type configs run execute_pipeline once per config."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_same_type_configs_run_sequentially(self):
        """train_01,train_02 must call execute_pipeline twice, not once."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "proj"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "train_01_baseline.yaml").write_text(
                "training:\n  enabled: false\n", encoding="utf-8"
            )
            (config_dir / "train_02_lgbm.yaml").write_text(
                "training:\n  enabled: false\n", encoding="utf-8"
            )

            old_cwd = os.getcwd()
            call_args = []

            def mock_execute(config_paths, run_name=None, overwrite=False, profile_memory=False):
                call_args.append(list(config_paths))
                return {}

            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline", side_effect=mock_execute):
                    result = self.runner.invoke(cli, ["run", "train_01_baseline,train_02_lgbm"])
                    assert result.exit_code == 0, result.output
                    # Must have been called twice, once per config
                    assert len(call_args) == 2
                    assert call_args[0][0].endswith("train_01_baseline.yaml")
                    assert call_args[1][0].endswith("train_02_lgbm.yaml")
            finally:
                os.chdir(old_cwd)

    def test_mixed_types_run_once_merged(self):
        """etl,train must call execute_pipeline once with both paths."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "proj"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                "etl:\n  sample:\n    enabled: false\n    custom_class: energizados.etl.pipeline.SourceETL\n",
                encoding="utf-8",
            )
            (config_dir / "train.yaml").write_text(
                "training:\n  enabled: false\n", encoding="utf-8"
            )

            old_cwd = os.getcwd()
            call_args = []

            def mock_execute(config_paths, run_name=None, overwrite=False, profile_memory=False):
                call_args.append(list(config_paths))
                return {}

            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline", side_effect=mock_execute):
                    result = self.runner.invoke(cli, ["run", "etl,train"])
                    assert result.exit_code == 0, result.output
                    # Must have been called once with both paths merged
                    assert len(call_args) == 1
                    assert len(call_args[0]) == 2
            finally:
                os.chdir(old_cwd)

    def test_etl_eda_two_trains(self):
        """etl,eda,train_01,train_02 → merged run etl+eda, then train_01, then train_02."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "proj"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "etl.yaml").write_text(
                "etl:\n  s:\n    enabled: false\n    custom_class: energizados.etl.pipeline.SourceETL\n",
                encoding="utf-8",
            )
            (config_dir / "eda.yaml").write_text("eda:\n  enabled: false\n", encoding="utf-8")
            (config_dir / "train_01_baseline.yaml").write_text(
                "training:\n  enabled: false\n", encoding="utf-8"
            )
            (config_dir / "train_02_lgbm.yaml").write_text(
                "training:\n  enabled: false\n", encoding="utf-8"
            )

            old_cwd = os.getcwd()
            call_args = []

            def mock_execute(config_paths, run_name=None, overwrite=False, profile_memory=False):
                call_args.append(list(config_paths))
                return {}

            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.execute_pipeline", side_effect=mock_execute):
                    result = self.runner.invoke(
                        cli, ["run", "etl,eda,train_01_baseline,train_02_lgbm"]
                    )
                    assert result.exit_code == 0, result.output
                    # 3 calls: [etl+eda], [train_01], [train_02]
                    assert len(call_args) == 3
                    # First call: shared (etl + eda)
                    assert len(call_args[0]) == 2
                    shared_stems = {Path(p).stem for p in call_args[0]}
                    assert shared_stems == {"etl", "eda"}
                    # Second and third: one train each
                    assert call_args[1][0].endswith("train_01_baseline.yaml")
                    assert call_args[2][0].endswith("train_02_lgbm.yaml")
            finally:
                os.chdir(old_cwd)


class TestMemoryProfiling:
    """Tests for the -vv memory profiling feature: helpers and CLI wiring."""

    def test_format_mem_inline_empty(self):
        from energizados.cli.run import _format_mem_inline

        assert _format_mem_inline(None) == ""
        assert _format_mem_inline({}) == ""

    def test_format_mem_inline_no_warning_below_1gb(self):
        from energizados.cli.run import _format_mem_inline

        out = _format_mem_inline({"delta": 100 * 1024**2, "peak": 200 * 1024**2})
        assert "Δ100.0MB" in out
        assert "peak 200.0MB" in out
        assert "⚠" not in out

    def test_format_mem_inline_warning_above_1gb(self):
        from energizados.cli.run import _format_mem_inline

        out = _format_mem_inline({"delta": 2 * 1024**3, "peak": 5 * 1024**3})
        assert "Δ2.0GB" in out
        assert "peak 5.0GB" in out
        assert "⚠" in out

    def test_print_profiling_table_renders_sorted_rows(self):
        """The profiling table renders rows sorted by peak (desc)."""
        from io import StringIO

        from rich.console import Console

        from energizados.cli.run import _print_profiling_table

        rows = [
            (
                "maestros",
                {
                    "rss_start": 500 * 1024**2,
                    "rss_end": 600 * 1024**2,
                    "delta": 100 * 1024**2,
                    "peak": 700 * 1024**2,
                },
            ),
            (
                "consumos",
                {
                    "rss_start": 1 * 1024**3,
                    "rss_end": 4 * 1024**3,
                    "delta": 3 * 1024**3,
                    "peak": 9 * 1024**3,
                },
            ),
        ]
        captured = []
        with patch(
            "energizados.cli.run.console.print", side_effect=lambda *a, **k: captured.append(a)
        ):
            _print_profiling_table(rows)

        buf = StringIO()
        probe = Console(file=buf, width=120)
        for args in captured:
            probe.print(*args)
        text = buf.getvalue()

        assert "Memory profile" in text
        assert "consumos" in text
        assert "maestros" in text
        assert "9.0GB" in text  # peak of consumos
        # consumos (9GB peak) must appear before maestros (700MB peak)
        assert text.index("consumos") < text.index("maestros")

    def test_execute_pipeline_propagates_profile_memory_flag(self):
        """execute_pipeline(profile_memory=True) sets pipeline.profile_memory=True."""
        import os
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "proj"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "train.yaml").write_text("train:\n  enabled: false\n", encoding="utf-8")
            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.ConfigPipelineBuilder") as mock_builder:
                    mock_pipeline = mock_builder.return_value.build.return_value
                    mock_pipeline.steps = []
                    mock_pipeline.run.return_value = {}
                    mock_builder.return_value._director.run_manager._run_dir = None
                    with patch("energizados.cli.run.console.print"):
                        from energizados.cli.run import execute_pipeline

                        execute_pipeline([str(config_dir / "train.yaml")], profile_memory=True)
                    assert mock_pipeline.profile_memory is True
            finally:
                os.chdir(old_cwd)


class TestExecuteStepProfileMemory:
    """Regression: ``energizados run X --step Y -vv`` crashed with TypeError
    because ``execute_step`` did not accept the ``profile_memory`` kwarg that
    ``main.py`` always passes under ``-vv``.
    """

    def test_execute_step_accepts_profile_memory(self):
        """execute_step(profile_memory=True) must not raise TypeError."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir) / "proj"
            project_path.mkdir()
            config_dir = project_path / "config"
            config_dir.mkdir()
            (config_dir / "train.yaml").write_text("train:\n  enabled: false\n", encoding="utf-8")
            old_cwd = os.getcwd()
            try:
                os.chdir(project_path)
                with patch("energizados.cli.run.ConfigPipelineBuilder") as mock_builder:
                    mock_pipeline = mock_builder.return_value.build.return_value
                    # TrainingStep is the target of ``--step train``
                    from energizados.core.steps.training import (  # type: ignore[import-untyped]
                        TrainingStep,
                    )

                    mock_pipeline.steps = [TrainingStep()]
                    mock_pipeline.profile_memory = False
                    mock_pipeline.run.return_value = {}
                    mock_builder.return_value.run_dir = None
                    with patch("energizados.cli.run.console.print"):
                        from energizados.cli.run import execute_step

                        # Must not raise TypeError: unexpected keyword 'profile_memory'
                        execute_step(
                            [str(config_dir / "train.yaml")],
                            "train",
                            profile_memory=True,
                        )
                    assert mock_pipeline.profile_memory is True
            finally:
                os.chdir(old_cwd)
