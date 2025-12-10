"""Install commands for AIDB CLI.

Handles installation, reinstallation, and dependency setup. Optionally installs shell
completion in the user's shell rc files.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import click

from aidb.common.errors import AidbError
from aidb_cli.core.constants import Icons
from aidb_cli.core.decorators import handle_exceptions
from aidb_cli.core.paths import ProjectPaths
from aidb_common.path import normalize_path
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.core.output import OutputStrategy

logger = get_cli_logger(__name__)


def _build_completion_command(
    repo_root: Path,
    completion_shell: str | None,
    completion_rc_file: Path | None,
    completion_no_backup: bool,
    completion_also_bashrc: bool,
) -> list[str]:
    """Build shell completion install command.

    Parameters
    ----------
    repo_root : Path
        Repository root directory
    completion_shell : str | None
        Shell for completion (bash, zsh, fish)
    completion_rc_file : Path | None
        Explicit rc file path
    completion_no_backup : bool
        Skip creating backup files
    completion_also_bashrc : bool
        Also update ~/.bashrc on macOS

    Returns
    -------
    list[str]
        Command arguments for completion installation
    """
    cmd = [str(repo_root / "dev-cli"), "completion", "install", "--yes"]

    if completion_shell:
        cmd += ["--shell", completion_shell]
    if completion_rc_file is not None:
        cmd += ["--rc-file", str(completion_rc_file)]
    if completion_no_backup:
        cmd += ["--no-backup"]
    if completion_also_bashrc:
        cmd += ["--also-bashrc"]

    return cmd


def _install_completion_if_requested(
    aidb_ctx,
    output: "OutputStrategy",
    repo_root: Path,
    completion: bool,
    completion_shell: str | None,
    completion_rc_file: Path | None,
    completion_no_backup: bool,
    completion_also_bashrc: bool,
) -> None:
    """Install shell completion if requested.

    Parameters
    ----------
    aidb_ctx
        CLI context with command executor
    output : OutputStrategy
        Output strategy for CLI messages
    repo_root : Path
        Repository root directory
    completion : bool
        Whether to install completion
    completion_shell : str | None
        Shell for completion
    completion_rc_file : Path | None
        Explicit rc file path
    completion_no_backup : bool
        Skip creating backup files
    completion_also_bashrc : bool
        Also update ~/.bashrc on macOS
    """
    if completion:
        comp_cmd = _build_completion_command(
            repo_root,
            completion_shell,
            completion_rc_file,
            completion_no_backup,
            completion_also_bashrc,
        )

        output.plain("Installing shell completion (requested)...")
        result = aidb_ctx.command_executor.execute(
            comp_cmd,
            cwd=repo_root,
            check=False,
            capture_output=True,
        )

        if result.returncode == 0:
            output.success("Shell completion installed.")
        else:
            output.plain(
                "Shell completion install returned a non-zero status; "
                "you can run './dev-cli completion install' manually.",
            )
    else:
        output.plain(
            "Optional: enable shell completion with './dev-cli completion install'",
        )


@click.group(name="install")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Installation and setup commands."""


@group.command()
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose installation output",
)
@click.option("--completion", is_flag=True, help="Install shell completion after setup")
@click.option(
    "--completion-shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    help="Shell for completion install (defaults to auto-detect)",
)
@click.option(
    "--completion-rc-file",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit rc file to write for completion",
)
@click.option(
    "--completion-no-backup",
    is_flag=True,
    help="Skip creating a .bak backup when modifying rc files",
)
@click.option(
    "--completion-also-bashrc",
    is_flag=True,
    help="On macOS bash, also update ~/.bashrc to cover non-login shells",
)
@click.pass_context
@handle_exceptions
def setup(
    ctx: click.Context,
    verbose: bool,
    completion: bool,
    completion_shell: str | None,
    completion_rc_file: Path | None,
    completion_no_backup: bool,
    completion_also_bashrc: bool,
) -> None:
    """Install AIDB, test packages, and dev dependencies."""
    output = ctx.obj.output
    aidb_ctx = ctx.obj
    repo_root = aidb_ctx.repo_root

    output.section("AIDB Installation", Icons.ROCKET)

    install_script = normalize_path(repo_root / ProjectPaths.INSTALL_SCRIPT)

    if not install_script.exists():
        msg = f"Install script not found: {install_script}"
        raise FileNotFoundError(msg)

    output.plain(
        f"{Icons.ROCKET} Installing AIDB, test packages, and dev dependencies...",
    )

    cmd = [str(install_script)]
    if verbose or aidb_ctx.verbose:
        cmd.append("-v")

    result = aidb_ctx.command_executor.execute(
        cmd,
        cwd=repo_root,
        check=False,
        passthrough_no_stream=True,
    )
    if result.returncode == 0:
        output.success("Installation complete.")

        _install_completion_if_requested(
            aidb_ctx,
            output,
            repo_root,
            completion,
            completion_shell,
            completion_rc_file,
            completion_no_backup,
            completion_also_bashrc,
        )
    else:
        msg = "Installation failed"
        raise AidbError(msg)


@group.command()
@click.option("--completion", is_flag=True, help="Install shell completion after setup")
@click.option(
    "--completion-shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    help="Shell for completion install (defaults to auto-detect)",
)
@click.option(
    "--completion-rc-file",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit rc file to write for completion",
)
@click.option(
    "--completion-no-backup",
    is_flag=True,
    help="Skip creating a .bak backup when modifying rc files",
)
@click.option(
    "--completion-also-bashrc",
    is_flag=True,
    help="On macOS bash, also update ~/.bashrc to cover non-login shells",
)
@click.pass_context
@handle_exceptions
def debug(
    ctx: click.Context,
    completion: bool,
    completion_shell: str | None,
    completion_rc_file: Path | None,
    completion_no_backup: bool,
    completion_also_bashrc: bool,
) -> None:
    """Debug installation with verbose mode enabled."""
    output = ctx.obj.output
    output.section("Debug Installation", Icons.DEBUG)

    aidb_ctx = ctx.obj
    repo_root = aidb_ctx.repo_root

    install_script = normalize_path(repo_root / ProjectPaths.INSTALL_SCRIPT)

    if not install_script.exists():
        msg = f"Install script not found: {install_script}"
        raise FileNotFoundError(msg)

    output.debug("Debug Install: Verbose mode enabled.")

    cmd = [str(install_script), "-v"]

    result = aidb_ctx.command_executor.execute(
        cmd,
        cwd=repo_root,
        check=False,
        passthrough_no_stream=True,
    )
    if result.returncode == 0:
        output.success("Installation complete.")
        _install_completion_if_requested(
            aidb_ctx,
            output,
            repo_root,
            completion,
            completion_shell,
            completion_rc_file,
            completion_no_backup,
            completion_also_bashrc,
        )
    else:
        msg = "Debug installation failed"
        raise AidbError(msg)


@group.command()
@click.confirmation_option(
    prompt="This will remove the existing venv and reinstall. Continue?",
)
@click.option("--completion", is_flag=True, help="Install shell completion after setup")
@click.option(
    "--completion-shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    help="Shell for completion install (defaults to auto-detect)",
)
@click.option(
    "--completion-rc-file",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit rc file to write for completion",
)
@click.option(
    "--completion-no-backup",
    is_flag=True,
    help="Skip creating a .bak backup when modifying rc files",
)
@click.option(
    "--completion-also-bashrc",
    is_flag=True,
    help="On macOS bash, also update ~/.bashrc to cover non-login shells",
)
@click.pass_context
@handle_exceptions
def reinstall(
    ctx: click.Context,
    completion: bool,
    completion_shell: str | None,
    completion_rc_file: Path | None,
    completion_no_backup: bool,
    completion_also_bashrc: bool,
) -> None:
    """Remove existing venv and reinstall."""
    output = ctx.obj.output
    output.section("AIDB Reinstallation", Icons.LOOP)

    aidb_ctx = ctx.obj
    repo_root = aidb_ctx.repo_root

    venv_path = repo_root / "venv"
    install_script = normalize_path(repo_root / ProjectPaths.INSTALL_SCRIPT)

    if not install_script.exists():
        msg = f"Install script not found: {install_script}"
        raise FileNotFoundError(msg)

    # Remove existing venv
    if venv_path.exists():
        output.plain(f"{Icons.TRASH} Removing existing virtual environment...")
        import shutil

        try:
            shutil.rmtree(venv_path)
        except (OSError, shutil.Error) as e:
            logger.error("Failed to remove venv: %s", e)
            msg = f"Failed to remove existing venv: {e}"
            raise AidbError(msg) from e

    output.plain(
        f"{Icons.ROCKET} Reinstalling AIDB, test packages, and dev dependencies...",
    )

    cmd = [str(install_script), "-v"]

    result = aidb_ctx.command_executor.execute(
        cmd,
        cwd=repo_root,
        check=False,
        passthrough_no_stream=True,
    )
    if result.returncode == 0:
        output.success("Installation complete.")

        _install_completion_if_requested(
            aidb_ctx,
            output,
            repo_root,
            completion,
            completion_shell,
            completion_rc_file,
            completion_no_backup,
            completion_also_bashrc,
        )
    else:
        msg = "Reinstallation failed"
        raise AidbError(msg)
