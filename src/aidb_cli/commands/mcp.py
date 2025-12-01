"""MCP (Model Context Protocol) server management commands for AIDB CLI.

Personal development utilities for managing AIDB's Claude Code integration.
"""

import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons, ProjectNames
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.paths import ProjectPaths
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_logging import get_cli_logger
from aidb_logging.utils import get_log_file_path

if TYPE_CHECKING:
    from aidb_cli.core.output import OutputStrategy

logger = get_cli_logger(__name__)

# Thread lock for concurrent file access to Claude config
_status_lock = threading.Lock()


@click.group(name="mcp")
@click.pass_context
def group(ctx: click.Context) -> None:
    """MCP server management for Claude Code integration.

    \b Personal development utilities for managing AIDB's integration with Claude Code.
    These commands help with registration, testing, and debugging the MCP server.
    """  # noqa: W605


@group.command()
@click.pass_context
@handle_exceptions
def register(ctx: click.Context) -> None:
    """Register AIDB MCP server with Claude Code CLI."""
    output = ctx.obj.output
    output.section("MCP Server Registration", Icons.PLUG)

    if not _validate_mcp_server(output, ctx):
        msg = "MCP server validation failed - cannot register"
        raise AidbError(msg)

    repo_root = ctx.obj.repo_root
    venv_python = ProjectPaths.venv_python(repo_root)

    if not venv_python.exists():
        output.error(f"Virtual environment not found: {venv_python}")
        output.plain("Run './dev-cli install setup' first")
        msg = f"Virtual environment not found: {venv_python}"
        raise FileNotFoundError(msg)

    try:
        cmd = [
            "claude",
            "mcp",
            "add",
            ProjectNames.MCP_SERVER,
            "--scope",
            "local",
            "--",
            str(venv_python),
            "-m",
            "aidb_mcp",
        ]

        result = ctx.obj.command_executor.execute(cmd, capture_output=True, check=True)
        output.success("MCP server registered successfully")

        if ctx.obj.verbose:
            output.plain(f"Command: {' '.join(cmd)}")
            if result.stdout:
                output.plain(f"Output: {result.stdout.strip()}")

    except subprocess.CalledProcessError as e:
        output.error(f"MCP registration failed: {e.stderr.strip()}")
        msg = f"MCP registration failed: {e.stderr.strip()}"
        raise AidbError(msg) from e
    except FileNotFoundError:
        output.error("Claude Code CLI not found")
        output.plain("Install Claude Code CLI first: https://claude.ai/code")
        raise


@group.command()
@click.pass_context
@handle_exceptions
def unregister(ctx: click.Context) -> None:
    """Unregister AIDB MCP server from Claude Code CLI."""
    output = ctx.obj.output
    output.section("MCP Server Unregistration", Icons.TRASH)

    try:
        cmd = ["claude", "mcp", "remove", ProjectNames.MCP_SERVER, "--scope", "local"]
        ctx.obj.command_executor.execute(
            cmd,
            capture_output=True,
            check=False,
        )
        output.success("MCP server unregistered")

    except FileNotFoundError:
        output.error("Claude Code CLI not found")
        output.plain("Install Claude Code CLI first: https://claude.ai/code")
        raise


@group.command()
@click.pass_context
@handle_exceptions
def status(ctx: click.Context) -> None:
    """Check MCP server registration status."""
    output = ctx.obj.output
    output.plain(f"{Icons.MAGNIFYING} Checking MCP server status...")
    output.plain("")

    claude_config = Path.home() / ".claude.json"
    if not claude_config.exists():
        output.warning(f"Claude config file not found: {claude_config}")
        output.plain("Claude Code CLI may not be installed or configured")
        msg = f"Claude config file not found: {claude_config}"
        raise FileNotFoundError(msg)

    try:
        # Use thread lock for concurrent access safety
        with _status_lock:
            config = safe_read_json(claude_config) or {}

            repo_path = str(ctx.obj.repo_root)
            mcp_config = None

            if "projects" in config and repo_path in config["projects"]:
                project_config = config["projects"][repo_path]
                if (
                    "mcpServers" in project_config
                    and ProjectNames.MCP_SERVER in project_config["mcpServers"]
                ):
                    mcp_config = project_config["mcpServers"][ProjectNames.MCP_SERVER]

        # Display results outside the lock
        output.section("Registration Status")
        if mcp_config:
            output.plain(f"MCP server '{ProjectNames.MCP_SERVER}' is configured")
            if ctx.obj.verbose:
                output.plain(f"  Command: {mcp_config.get('command', 'N/A')}")
                output.plain(f"  Args: {mcp_config.get('args', [])}")
        else:
            server_name = ProjectNames.MCP_SERVER
            output.warning(f"MCP server '{server_name}' is not configured")
            output.plain("  Run './dev-cli mcp register' to register")

        output.plain("")
        output.plain(f"{Icons.FOLDER} Repository: {repo_path}")
        output.plain(f"{Icons.GEAR} Claude Config: {claude_config}")

    except FileOperationError as e:
        msg = f"Error reading Claude config: {e}"
        raise AidbError(msg) from e


@group.command()
@click.pass_context
@handle_exceptions
def test(ctx: click.Context) -> None:
    """Test MCP server functionality (validation + functionality tests)."""
    output = ctx.obj.output
    output.section("MCP Server Testing", Icons.TEST)

    output.plain(f"{Icons.GEAR} Step 1: Validating MCP server...")
    if not _validate_mcp_server(output, ctx):
        msg = "MCP server validation failed"
        raise AidbError(msg)
    output.success("MCP server validation passed")
    output.plain("")

    output.plain(f"{Icons.GEAR} Step 2: Testing MCP CLI functionality...")
    if not _test_mcp_cli(output, ctx):
        msg = "MCP CLI test failed"
        raise AidbError(msg)
    output.success("MCP CLI functionality passed")
    output.plain("")

    output.plain(f"{Icons.GEAR} Step 3: Testing server instantiation...")
    if not _test_server_instantiation(output, ctx):
        msg = "Server instantiation test failed"
        raise AidbError(msg)
    output.success("Server instantiation passed")
    output.plain("")

    output.success("All MCP tests passed - server is healthy!")


@group.command()
@click.pass_context
@handle_exceptions
def restart(ctx: click.Context) -> None:
    """Restart MCP server (unregister + register)."""
    output = ctx.obj.output
    output.section("MCP Server Restart", Icons.LOOP)

    try:
        cmd = ["claude", "mcp", "remove", ProjectNames.MCP_SERVER, "--scope", "local"]
        ctx.obj.command_executor.execute(cmd, capture_output=True, check=False)
    except FileNotFoundError:
        pass

    import time

    time.sleep(1)

    ctx.invoke(register)
    output.success("MCP server restarted successfully")


@group.command()
@click.pass_context
@handle_exceptions
def logs(ctx: click.Context) -> None:
    """Comprehensive MCP server debugging and log analysis."""
    output = ctx.obj.output
    output.section("MCP Server Debug Analysis", Icons.MAGNIFYING)
    _run_server_instantiation_test(output, ctx)
    _run_server_startup_test(output, ctx)
    _check_mcp_logs(output, ctx.obj.verbose)


def _run_server_instantiation_test(
    output: "OutputStrategy",
    ctx: click.Context,
) -> None:
    """Test MCP server instantiation.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context
    """
    output.subsection("Testing server instantiation", Icons.DEBUG)
    try:
        result = ctx.obj.command_executor.execute(
            [
                str(ProjectPaths.venv_python(ctx.obj.repo_root)),
                "-c",
                "from aidb_mcp.server.app import AidbMCPServer; "
                "s = AidbMCPServer(); print('Server starts OK')",
            ],
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            output.plain(f"{result.stdout.strip()}")
        else:
            output.error("Server instantiation failed:")
            output.plain(f"    {result.stderr.strip()}")

    except subprocess.TimeoutExpired:
        output.warning("Server instantiation timed out")
    except Exception as e:
        output.error(f"Error testing server: {e}")


def _run_server_startup_test(
    output: "OutputStrategy",
    ctx: click.Context,
) -> None:
    """Test MCP server startup.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context
    """
    output.subsection("Testing server startup", Icons.DEBUG)
    try:
        result = ctx.obj.command_executor.execute(
            [
                str(ProjectPaths.venv_python(ctx.obj.repo_root)),
                "-m",
                "aidb_mcp",
            ],
            capture_output=True,
            timeout=1,
        )

        if result.returncode == 0:
            output.plain("Server starts and exits cleanly")
        else:
            output.error("Server startup issues:")
            if result.stderr:
                output.plain(f"    {result.stderr.strip()}")

        if result.stdout:
            output.plain(f"  Output: {result.stdout.strip()}")

    except subprocess.TimeoutExpired:
        output.plain("Server started (timeout triggered as expected)")
    except Exception as e:
        output.error(f"Error testing startup: {e}")


def _check_mcp_logs(output: "OutputStrategy", verbose: bool) -> None:
    """Check MCP logs for errors and warnings.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    verbose : bool
        Whether to show verbose log output
    """
    try:
        mcp_log_path = Path(get_log_file_path("mcp"))
        output.subsection("Checking MCP logs for errors", Icons.DEBUG)
        output.plain(f"Log file: {mcp_log_path}")

        if not mcp_log_path.exists():
            output.plain("No MCP log file found")
            return

        try:
            with mcp_log_path.open() as f:
                lines = f.readlines()

                if verbose:
                    _display_verbose_log_lines(output, lines)

                _check_recent_log_lines(output, lines)

        except Exception as log_error:
            output.warning(f"Error reading MCP log file: {log_error}")

    except Exception as e:
        output.error(f"Error accessing MCP log path: {e}")


def _display_verbose_log_lines(output: "OutputStrategy", lines: list[str]) -> None:
    """Display verbose log output.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    lines : list[str]
        All log lines
    """
    from aidb_cli.core.constants import DEFAULT_LOG_LINES

    verbose_lines = (
        lines[-DEFAULT_LOG_LINES:] if len(lines) > DEFAULT_LOG_LINES else lines
    )
    if verbose_lines:
        output.subsection(
            f"Last {len(verbose_lines)} lines of MCP log",
            Icons.INFO,
        )
        for line in verbose_lines:
            output.plain(f"  {line.rstrip()}")
    else:
        output.info("MCP log file is empty")


def _check_recent_log_lines(output: "OutputStrategy", lines: list[str]) -> None:
    """Check recent log lines for errors and warnings.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    lines : list[str]
        All log lines
    """
    recent_lines = lines[-50:]

    if not recent_lines:
        output.info("MCP log file is empty")
        return

    output.info("Checking last 50 lines for errors and warnings...")

    error_found = False
    warning_found = False

    for line in recent_lines:
        line_lower = line.lower()
        if "error" in line_lower or "failed" in line_lower:
            if not error_found:
                output.plain(f"{Icons.WARNING} Found recent errors:")
                error_found = True
            output.plain(f"  {line.strip()}")
        elif "warning" in line_lower or "warn" in line_lower:
            if not warning_found and not error_found:
                output.plain(f"{Icons.WARNING} Found recent warnings:")
                warning_found = True
            if not error_found:
                output.plain(f"  {line.strip()}")

    if not error_found and not warning_found:
        output.plain("No recent errors or warnings in MCP logs")


def _run_mcp_test(
    output: "OutputStrategy",
    ctx: click.Context,
    test_type: str,
) -> bool:
    """Run a specific MCP test.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context
    test_type : str
        Type of test: 'validation', 'cli', or 'instantiation'

    Returns
    -------
    bool
        True if test passed, False otherwise
    """
    python_path = str(ProjectPaths.venv_python(ctx.obj.repo_root))

    if test_type == "validation":
        cmd = [
            python_path,
            "-c",
            "from aidb_mcp.server.cli import main; print('MCP server imports valid')",
        ]
        error_prefix = "Import"
        success_msg = "MCP server imports valid"
    elif test_type == "cli":
        cmd = [python_path, "-m", "aidb_mcp", "--help"]
        error_prefix = "CLI test"
        success_msg = None
    elif test_type == "instantiation":
        cmd = [
            python_path,
            "-c",
            "from aidb_mcp.server.app import AidbMCPServer; "
            "s = AidbMCPServer(); print('Server instantiated successfully')",
        ]
        error_prefix = "Instantiation"
        success_msg = "Server instantiated successfully"
    else:
        msg = f"Unknown test type: {test_type}"
        raise ValueError(msg)

    try:
        result = ctx.obj.command_executor.execute(
            cmd,
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            if ctx.obj.verbose and success_msg and result.stdout:
                output.plain(f"{result.stdout.strip()}")
            return True

        if result.stderr:
            output.error(f"{error_prefix} error: {result.stderr.strip()}")
        return False

    except subprocess.TimeoutExpired:
        output.error(f"{error_prefix} timed out")
        return False
    except Exception as e:
        output.error(f"{error_prefix} error: {e}")
        return False


def _validate_mcp_server(output: "OutputStrategy", ctx: click.Context) -> bool:
    """Validate that MCP server imports work correctly.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context

    Returns
    -------
    bool
        True if validation passed
    """
    return _run_mcp_test(output, ctx, "validation")


def _test_mcp_cli(output: "OutputStrategy", ctx: click.Context) -> bool:
    """Test MCP CLI functionality.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context

    Returns
    -------
    bool
        True if test passed
    """
    return _run_mcp_test(output, ctx, "cli")


def _test_server_instantiation(output: "OutputStrategy", ctx: click.Context) -> bool:
    """Test that MCP server can be instantiated.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    ctx : click.Context
        Click context

    Returns
    -------
    bool
        True if test passed
    """
    return _run_mcp_test(output, ctx, "instantiation")
