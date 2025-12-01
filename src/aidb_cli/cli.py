"""Main CLI entry point for AIDB.

This module provides the main Click command group and coordinates all AIDB operations
through subcommands.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from aidb_cli.commands import (
    adapters,
    ci,
    completion,
    config,
    dev,
    docker,
    docs,
    install,
    mcp,
    test,
    versions,
)
from aidb_cli.core.constants import ALL_LOG_LEVELS, EnvVars, LogLevel
from aidb_cli.core.output import OutputStrategy, Verbosity
from aidb_cli.core.paths import CachePaths
from aidb_cli.managers import ConfigManager
from aidb_cli.managers.build import BuildManager
from aidb_cli.managers.environment_manager import EnvironmentManager
from aidb_cli.managers.test import TestManager, TestOrchestrator
from aidb_cli.services import CommandExecutor
from aidb_common.config import VersionManager
from aidb_common.config import config as runtime_config
from aidb_common.env import reader
from aidb_common.repo import detect_repo_root
from aidb_logging import configure_logger, get_cli_logger
from aidb_logging.utils import get_log_file_path

logger = get_cli_logger(__name__)

# Constants for logging configuration
LOGGING_PACKAGES = ("aidb_cli", "aidb", "aidb_mcp")

LOG_HEADER_TEMPLATE = """
{'=' * 60}
AIDB CLI Session Started - {timestamp}
Mode: {mode}
Command: {cmd_str}
Repository: {repo_root}
Log Type: {log_type}
{'=' * 60}

"""


def _configure_logging_environment(
    verbose: bool,
    verbose_debug: bool,
    log_level: str | None,
) -> str | None:
    """Configure logging environment variables based on CLI flags.

    Parameters
    ----------
    verbose : bool
        Whether -v verbose mode is enabled
    verbose_debug : bool
        Whether -vvv verbose debug mode is enabled
    log_level : str | None
        Explicit log level if provided

    Returns
    -------
    str | None
        The effective log level to use, or None if no logging changes needed
    """
    if log_level:
        runtime_config.set_env_var(EnvVars.LOG_LEVEL, log_level)
        return log_level

    if verbose_debug:
        # Enable maximum observability for -vvv mode
        runtime_config.set_env_var(EnvVars.LOG_LEVEL, "TRACE")
        runtime_config.set_env_var(EnvVars.ADAPTER_TRACE, "1")
        runtime_config.set_env_var(EnvVars.CONSOLE_LOGGING, "1")
        return "TRACE"

    if verbose:
        runtime_config.set_env_var(EnvVars.LOG_LEVEL, LogLevel.DEBUG.value)
        runtime_config.set_env_var(EnvVars.ADAPTER_TRACE, "1")
        return LogLevel.DEBUG.value

    return None


def _configure_package_loggers(effective_level: str, verbose_debug: bool) -> None:
    """Configure package loggers for file-only logging.

    Parameters
    ----------
    effective_level : str
        The log level to set
    verbose_debug : bool
        Whether verbose debug mode is enabled for global logging
    """
    for pkg_name in LOGGING_PACKAGES:
        try:
            configure_logger(
                pkg_name,
                profile="cli",
                level=effective_level,
                to_console=False,
                verbose_debug=verbose_debug,
            )
        except Exception as e:
            logger.debug(
                "Failed to configure logger for package %s: %s",
                pkg_name,
                e,
            )


def _write_log_header(
    log_name: str,
    log_type: str,
    mode: str,
    cmd_args: list[str],
    repo_root: Path,
) -> None:
    """Write a header to a specific log file.

    Parameters
    ----------
    log_name : str
        Name of the log file (e.g., "cli", "test")
    log_type : str
        Display name for the log type
    mode : str
        Verbose mode description
    cmd_args : list[str]
        Command line arguments
    repo_root : Path
        Repository root directory
    """
    try:
        log_path = get_log_file_path(log_name)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cmd_str = " ".join(cmd_args)

        header = LOG_HEADER_TEMPLATE.format(
            timestamp=timestamp,
            mode=mode,
            cmd_str=cmd_str,
            repo_root=repo_root,
            log_type=log_type,
        )

        # Append header to log file
        log_path_obj = Path(log_path)
        log_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with log_path_obj.open("a", encoding="utf-8") as f:
            f.write(header)

    except Exception as e:
        # Best effort - don't fail CLI startup if header writing fails
        logger.debug("Failed to write log header to %s log: %s", log_name, e)


def _write_verbose_log_headers(
    verbose: bool,
    verbose_debug: bool,
    repo_root: Path,
    cmd_args: list[str],
) -> None:
    """Write informative headers to log files when verbose modes are enabled.

    Parameters
    ----------
    verbose : bool
        Whether -v verbose mode is enabled
    verbose_debug : bool
        Whether -vvv verbose debug mode is enabled
    repo_root : Path
        Repository root directory
    cmd_args : list[str]
        Command line arguments
    """
    if not (verbose or verbose_debug):
        return

    mode = "verbose debug (-vvv)" if verbose_debug else "verbose (-v)"

    # Always write CLI log header
    _write_log_header("cli", "CLI", mode, cmd_args, repo_root)


def _show_debug_banner(output: OutputStrategy) -> None:
    """Show debug banner for -vvv mode with log file locations.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for consistent output
    """
    log_dir = CachePaths.log_dir()
    repo_root = detect_repo_root()
    output.plain("")
    output.section("GLOBAL DEBUG LOGGING ENABLED (-vvv mode)", "🔧")
    output.plain(f"CLI log: {log_dir / 'cli.log'}")
    container_log = log_dir / "test-container-output.log"
    output.plain(f"Container logs: {container_log} (Docker tests only)")
    local_test_log = repo_root / "pytest-logs" / "test-results.log"
    output.plain(f"Local test output: {local_test_log}")
    output.plain("Note: This includes debug output from all third-party libraries")
    output.plain("")


def _is_help_command() -> bool:
    """Detect if the current command is requesting help.

    Returns
    -------
    bool
        True if help is being requested, False otherwise
    """
    # Check if --help or -h is in the command line arguments
    return "--help" in sys.argv or "-h" in sys.argv


class Context:
    """CLI context object for sharing state between commands."""

    def __init__(self, repo_root: Path | None = None) -> None:
        """Initialize CLI context.

        Parameters
        ----------
        repo_root : Path, optional
            Repository root directory. If not provided, will be auto-detected.
        """
        self.verbose: bool = False
        self.verbose_debug: bool = False
        self.repo_root: Path = repo_root or detect_repo_root()
        self.config: dict[str, Any] = {}

        # Centralized environment resolution - initialized early
        self.env_manager = EnvironmentManager(self.repo_root)

        # Legacy version manager (still used by some commands)
        self._version_manager: VersionManager | None = None

        self._build_manager: BuildManager | None = None
        self._config_manager: ConfigManager | None = None
        self._test_manager: TestManager | None = None
        self._test_orchestrator: TestOrchestrator | None = None
        self._command_executor: CommandExecutor | None = None
        self._output: OutputStrategy | None = None

    @property
    def resolved_env(self) -> dict[str, str]:
        """Get the current resolved environment.

        This property ensures we always get the current state of the
        environment from the manager, including any updates that have
        been applied.

        Returns
        -------
        dict[str, str]
            The current resolved environment variables
        """
        return self.env_manager.get_environment()

    @property
    def version_manager(self) -> VersionManager:
        """Get version manager instance, creating if necessary.

        Returns
        -------
        VersionManager
            Version manager instance
        """
        if self._version_manager is None:
            self._version_manager = VersionManager()
        return self._version_manager

    @property
    def build_manager(self) -> BuildManager:
        """Get build manager singleton instance.

        Returns
        -------
        BuildManager
            Build manager instance
        """
        if self._build_manager is None:
            self._build_manager = BuildManager(self.repo_root, self.command_executor)
        return self._build_manager

    @property
    def config_manager(self) -> ConfigManager:
        """Get config manager singleton instance.

        Returns
        -------
        ConfigManager
            Config manager instance
        """
        if self._config_manager is None:
            self._config_manager = ConfigManager(self.repo_root)
        return self._config_manager

    @property
    def test_manager(self) -> TestManager:
        """Get test manager singleton instance.

        Returns
        -------
        TestManager
            Test manager instance
        """
        if self._test_manager is None:
            self._test_manager = TestManager(self.repo_root, self.command_executor)
        return self._test_manager

    @property
    def test_orchestrator(self) -> TestOrchestrator:
        """Get test orchestrator singleton instance.

        Returns
        -------
        TestOrchestrator
            Test orchestrator instance
        """
        if self._test_orchestrator is None:
            self._test_orchestrator = TestOrchestrator(
                self.repo_root,
                self.command_executor,
            )
        return self._test_orchestrator

    @property
    def command_executor(self) -> CommandExecutor:
        """Get command executor singleton instance.

        Returns
        -------
        CommandExecutor
            Command executor instance with smart streaming detection
        """
        if self._command_executor is None:
            # Create CommandExecutor with Click context so streaming honors -v/-vvv
            try:
                import click  # Local import to avoid CLI import cycles

                click_ctx = click.get_current_context(silent=True)
            except Exception:  # No active Click context (e.g., tests)
                click_ctx = None

            self._command_executor = CommandExecutor(ctx=click_ctx)
        return self._command_executor

    @property
    def output(self) -> OutputStrategy:
        """Get output strategy singleton instance.

        The output strategy provides unified output with verbosity contracts:
        - NORMAL: Progress, results, errors, warnings
        - VERBOSE (-v): + Operation details
        - DEBUG (-vvv): + Full streaming, protocol traces

        Returns
        -------
        OutputStrategy
            Output strategy configured with current verbosity
        """
        if self._output is None:
            verbosity = Verbosity.from_flags(self.verbose, self.verbose_debug)
            self._output = OutputStrategy(verbosity=verbosity)
        return self._output


# Create a custom pass decorator for our Context class
# This allows any command to use @pass_context to automatically receive the context
pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output with streaming",
)
@click.option(
    "--verbose-debug",
    "-vvv",
    is_flag=True,
    help=(
        "Enable verbose output with global debug logging "
        "(includes third-party libraries)"
    ),
)
@click.option(
    "--log-level",
    type=click.Choice([level.value for level in ALL_LOG_LEVELS]),
    help="Set logging level",
)
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    verbose_debug: bool,
    log_level: str | None,
) -> None:
    """AIDB - AI Debugger Command Line Interface.

    \b
    A comprehensive CLI for managing AIDB installation, testing, and operations.
    """  # noqa: W605
    # Initialize context
    ctx.ensure_object(Context)
    aidb_ctx: Context = ctx.obj
    aidb_ctx.verbose = verbose
    aidb_ctx.verbose_debug = verbose_debug

    # Configure logging
    effective_level = _configure_logging_environment(verbose, verbose_debug, log_level)

    if effective_level:
        _configure_package_loggers(effective_level, verbose_debug)
        _write_verbose_log_headers(verbose, verbose_debug, aidb_ctx.repo_root, sys.argv)
        logger.info("AIDB CLI starting with repo root: %s", aidb_ctx.repo_root)

        if verbose_debug:
            _show_debug_banner(aidb_ctx.output)


cli.add_command(install.group)
cli.add_command(adapters.group)
cli.add_command(ci.group)
cli.add_command(completion.group)
cli.add_command(versions.group)
cli.add_command(test.group)
cli.add_command(docker.group)
cli.add_command(config.group)
cli.add_command(mcp.group)
cli.add_command(dev.group)
cli.add_command(docs.group)


@cli.command()
@click.option(
    "--versions",
    is_flag=True,
    help="Include version information",
)
@click.pass_context
def info(ctx: click.Context, versions: bool) -> None:
    """Show AIDB CLI information."""
    from aidb_cli.core.constants import Icons

    aidb_ctx: Context = ctx.obj
    output = aidb_ctx.output

    output.section("AIDB CLI Information", Icons.INFO)

    output.plain(f"AIDB CLI v{__import__('aidb_cli').__version__}")
    output.plain(f"Repository root: {aidb_ctx.repo_root}")
    output.plain(f"Python executable: {sys.executable}")

    if aidb_ctx.verbose or aidb_ctx.verbose_debug:
        output.plain("")
        output.subsection("Verbose Mode Configuration")
        mode = "debug" if aidb_ctx.verbose_debug else "verbose"
        output.plain(f"Verbose mode: {mode}")
        output.plain(
            f"AIDB_LOG_LEVEL: {reader.read_str(EnvVars.LOG_LEVEL, default='not set')}",
        )
        output.plain(
            (
                "AIDB_ADAPTER_TRACE: "
                f"{reader.read_str(EnvVars.ADAPTER_TRACE, default='not set')}"
            ),
        )

        if aidb_ctx.verbose_debug:
            output.plain(
                (
                    "AIDB_CONSOLE_LOGGING: "
                    f"{reader.read_str(EnvVars.CONSOLE_LOGGING, default='not set')}"
                ),
            )

    if versions:
        output.plain("")
        output.subsection("Version Information")
        output.plain(aidb_ctx.version_manager.format_versions_output("text"))


def main() -> None:
    """Serve as the main entry point for the CLI."""
    # Choose a friendly program name for help/completion.
    # Use `./dev-cli` when running from the repo so docs and shell completion
    # match what developers actually type; fall back to `aidb` for installs.
    try:
        repo_root = detect_repo_root()
        prog = "./dev-cli" if (repo_root / "dev-cli").exists() else "aidb"
    except Exception:
        prog = "aidb"

    # Keep a stable completion env var name regardless of how invoked.
    cli(prog_name=prog, complete_var="_AIDB_COMPLETE")


if __name__ == "__main__":
    main()
