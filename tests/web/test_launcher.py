"""
Tests for the Energizados web launcher.

Tests cross-platform subprocess spawning, signal handling, and graceful shutdown.
Argv construction and argument parsing are unit-tested without spawning; the
help test spawns `--help` once to verify the CLI end-to-end.
"""

import subprocess  # nosec B404 - imported for patching/mocking in tests
import sys
from unittest.mock import patch

import pytest

from energizados.web.launcher import _web_argv, _worker_argv, parse_args


class TestLauncherArgv:
    """Test argv construction for web and worker processes."""

    def test_web_argv_default(self):
        """Test web argv with default parameters."""
        argv = _web_argv("127.0.0.1", 8000)

        assert sys.executable in argv
        assert "-m" in argv
        assert "uvicorn" in argv
        assert "energizados.web.app:app" in argv
        assert "--host" in argv
        assert "127.0.0.1" in argv
        assert "--port" in argv
        assert "8000" in argv

    def test_web_argv_custom(self):
        """Test web argv with custom host and port."""
        argv = _web_argv("192.168.1.10", 8080)

        assert "192.168.1.10" in argv
        assert "8080" in argv

    def test_worker_argv_default(self):
        """Test worker argv with default parameters."""
        argv = _worker_argv("data/web/jobs.db", "INFO")

        assert sys.executable in argv
        assert "-m" in argv
        assert "energizados.web.worker" in argv
        assert "--db-path" in argv
        assert "data/web/jobs.db" in argv
        assert "--log-level" in argv
        assert "INFO" in argv

    def test_worker_argv_custom(self):
        """Test worker argv with custom db path and log level."""
        argv = _worker_argv("/custom/path/jobs.db", "DEBUG")

        assert "/custom/path/jobs.db" in argv
        assert "DEBUG" in argv


class TestLauncherArgParse:
    """Test command-line argument parsing."""

    def test_parse_args_defaults(self):
        """Test parsing arguments with default values."""
        with patch("sys.argv", ["energizados-web"]):
            args = parse_args()

            assert args.host == "127.0.0.1"
            assert args.port == 8000
            assert args.db_path == "data/web/jobs.db"
            assert args.log_level == "INFO"

    def test_parse_args_custom(self):
        """Test parsing arguments with custom values."""
        with patch(
            "sys.argv",
            [
                "energizados-web",
                "--host",
                "192.168.1.10",
                "--port",
                "8080",
                "--db-path",
                "/custom/db",
                "--log-level",
                "DEBUG",
            ],
        ):
            args = parse_args()

            assert args.host == "192.168.1.10"
            assert args.port == 8080
            assert args.db_path == "/custom/db"
            assert args.log_level == "DEBUG"

    def test_parse_args_invalid_log_level(self):
        """Test parsing with invalid log level."""
        with patch("sys.argv", ["energizados-web", "--log-level", "INVALID"]):
            with pytest.raises(SystemExit):
                parse_args()


class TestLauncherHelp:
    """Test launcher help and usage."""

    def test_help_message(self):
        """Test that help message is available."""
        # Runs `energizados-web --help` via fixed arg list; no shell, no untrusted input.
        result = subprocess.run(  # nosec B603
            [sys.executable, "-m", "energizados.web.launcher", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Energizados Web Console" in result.stdout
        assert "--host" in result.stdout
        assert "--port" in result.stdout
        assert "--db-path" in result.stdout
        assert "--log-level" in result.stdout
        assert "--allow-remote" in result.stdout


class TestRemoteHostGuard:
    """Regression tests for issue #41: the launcher must refuse to bind to a
    non-loopback interface without explicit opt-in via --allow-remote, since
    the console has no auth and accepts arbitrary YAML as job configuration
    (code-execution surface).
    """

    def test_loopback_host_passes_without_opt_in(self):
        """127.0.0.1 is the default and must work without --allow-remote."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        # Should NOT raise.
        _assert_safe_host_or_explicit_opt_in("127.0.0.1", allow_remote=False)

    def test_localhost_alias_passes(self):
        """The string 'localhost' is also safe."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        _assert_safe_host_or_explicit_opt_in("localhost", allow_remote=False)

    def test_ipv6_loopback_passes(self):
        """::1 is the IPv6 loopback and is also safe."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        _assert_safe_host_or_explicit_opt_in("::1", allow_remote=False)

    def test_non_loopback_host_refuses_without_opt_in(self, capsys):
        """A non-loopback host without --allow-remote must fail-closed."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        with pytest.raises(SystemExit) as exc_info:
            _assert_safe_host_or_explicit_opt_in("0.0.0.0", allow_remote=False)  # nosec B104

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "SECURITY" in captured.err
        assert "0.0.0.0" in captured.err  # nosec B104
        assert "--allow-remote" in captured.err

    def test_non_loopback_host_passes_with_opt_in(self):
        """A non-loopback host WITH --allow-remote must pass (opt-in respected)."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        # Should NOT raise.
        _assert_safe_host_or_explicit_opt_in("0.0.0.0", allow_remote=True)  # nosec B104

    def test_lan_ip_refuses_without_opt_in(self, capsys):
        """A LAN IP without --allow-remote must also fail-closed."""
        from energizados.web.launcher import _assert_safe_host_or_explicit_opt_in

        with pytest.raises(SystemExit) as exc_info:
            _assert_safe_host_or_explicit_opt_in("192.168.1.100", allow_remote=False)  # nosec B104

        assert exc_info.value.code == 2
        assert "192.168.1.100" in capsys.readouterr().err
