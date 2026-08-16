"""Tests for the main CLI group help output (bare ``energizados`` invocation)."""

from click.testing import CliRunner

from energizados._version import get_version  # type: ignore[import-untyped]
from energizados.cli.main import cli  # type: ignore[import-untyped]


class TestVersionInHelp:
    """Bare ``energizados`` and ``energizados --help`` must show the framework version."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_version_line_in_group_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert f"v{get_version()}" in result.output

    def test_version_line_in_bare_invocation(self):
        result = self.runner.invoke(cli, [])
        # click>=8.2 exits with code 2 for a bare group invocation (no
        # subcommand); older click versions exit 0. Both are acceptable here —
        # what matters is that the auto-printed help includes the version.
        assert result.exit_code in (0, 2)
        assert f"v{get_version()}" in result.output
