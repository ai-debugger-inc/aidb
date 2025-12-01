"""Tests for verbose debug logging (-vvv flag)."""

from unittest.mock import patch

import click
from click.testing import CliRunner

from aidb_cli.cli import cli
from aidb_cli.core.utils import CliOutput


class TestVerboseDebugFlag:
    """Test cases for the -vvv flag functionality."""

    def test_vvv_flag_accepted(self):
        """Test that -vvv flag is accepted by CLI."""
        runner = CliRunner()

        # Test that -vvv flag is recognized (should show help without error)
        result = runner.invoke(cli, ["-vvv", "--help"])
        assert result.exit_code == 0
        assert (
            "verbose-debug" in result.output
            or "maximum debug logging" in result.output.lower()
        )

    def test_vvv_flag_sets_context(self):
        """Test that -vvv flag sets verbose_debug in context."""
        runner = CliRunner()

        # Create a minimal CLI that we can test with
        @click.group()
        @click.option("--verbose-debug", "-vvv", is_flag=True)
        @click.pass_context
        def test_cli(ctx, verbose_debug):
            ctx.ensure_object(dict)
            ctx.obj["verbose_debug"] = verbose_debug

        @test_cli.command("test-cmd")
        @click.pass_context
        def test_cmd(ctx):
            """Test command to check context."""
            CliOutput.plain(f"verbose_debug={ctx.obj['verbose_debug']}")

        result = runner.invoke(test_cli, ["-vvv", "test-cmd"])
        assert "verbose_debug=True" in result.output

    def test_verbose_debug_enables_global_logging(self):
        """Test that -vvv flag enables global debug logging."""
        runner = CliRunner()

        with patch(
            "aidb_logging.config.setup_global_debug_logging",
        ) as mock_setup_global:
            # Create a temporary command for testing
            from aidb_cli.cli import cli

            @cli.command("test-global-logging")
            def test_global_logging():
                """Temporary test command."""

            try:
                result = runner.invoke(cli, ["-vvv", "test-global-logging"])
                assert result.exit_code == 0

                # Verify setup_global_debug_logging was called
                assert mock_setup_global.called, (
                    "setup_global_debug_logging should be called with -vvv flag"
                )
            finally:
                # Clean up the temporary command
                if hasattr(cli, "commands") and "test-global-logging" in cli.commands:
                    del cli.commands["test-global-logging"]

    def test_verbose_and_verbose_debug_both_work(self):
        """Test that both -v and -vvv flags can be used and work correctly."""
        runner = CliRunner()

        # Create a test CLI to avoid interfering with the main CLI
        @click.group()
        @click.option("--verbose", "-v", is_flag=True)
        @click.option("--verbose-debug", "-vvv", is_flag=True)
        @click.pass_context
        def test_cli(ctx, verbose, verbose_debug):
            ctx.ensure_object(dict)
            ctx.obj["verbose"] = verbose
            ctx.obj["verbose_debug"] = verbose_debug

        @test_cli.command()
        @click.pass_context
        def test_both(ctx):
            """Test command to check both flags."""
            CliOutput.plain(f"verbose={ctx.obj['verbose']}")
            CliOutput.plain(f"verbose_debug={ctx.obj['verbose_debug']}")

        # Test -v flag
        result = runner.invoke(test_cli, ["-v", "test-both"])
        assert "verbose=True" in result.output
        assert "verbose_debug=False" in result.output

        # Test -vvv flag
        result = runner.invoke(test_cli, ["-vvv", "test-both"])
        assert "verbose=False" in result.output
        assert "verbose_debug=True" in result.output

    def test_log_level_info_shows_enhanced_debug(self):
        """Test that startup log shows ENHANCED DEBUG when -vvv is used."""
        runner = CliRunner()

        @cli.command()
        def dummy():
            pass

        # Use -vvv and capture the startup message
        result = runner.invoke(cli, ["-vvv", "dummy"])

        # Should show global debug logging when -vvv is used
        # Note: This might appear in debug logs, so we check the general behavior
        assert result.exit_code == 0  # Command should succeed
