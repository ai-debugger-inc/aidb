"""Shell completion utilities for AIDB CLI.

Commands:
- completion show [--shell SHELL]
- completion install [--shell SHELL] [--yes]
- completion uninstall [--shell SHELL] [--yes]

When using the dev entrypoint, prefix with `./dev-cli`.
Supported shells: zsh, bash, fish.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import click

from aidb_cli.core.decorators import handle_exceptions
from aidb_common.env import reader
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.core.output import OutputStrategy

logger = get_cli_logger(__name__)


SUPPORTED_SHELLS = {"zsh", "bash", "fish"}

# Shared header comment placed above the eval snippet in rc files
AIDB_COMPLETION_HEADER = "# AIDB CLI completion"

ENV_PREFIX_CHUNK = "AIDB_CONSOLE_LOGGING=0 AIDB_NO_FILE_LOGGING=1 _AIDB_COMPLETE"


def _detect_shell(explicit: str | None = None) -> str:
    """Detect the user's shell or use explicit selection.

    Returns one of: zsh, bash, fish. Defaults to zsh on mac if unknown.
    """
    if explicit:
        s = explicit.strip().lower()
        if s in SUPPORTED_SHELLS:
            return s
        msg = f"Unsupported shell: {explicit}"
        raise click.ClickException(msg)

    # Try SHELL env (e.g. /bin/zsh, /bin/bash, /usr/local/bin/fish)
    shell_path = reader.read_str("SHELL", default="").lower()
    if shell_path.endswith("zsh"):
        return "zsh"
    if shell_path.endswith("bash"):
        return "bash"
    if shell_path.endswith("fish"):
        return "fish"

    # On Windows (optional), detect powershell/cmd
    if os.name == "nt":
        # Not officially supported here; fall back to bash semantics
        return "bash"

    # mac default is zsh
    return "zsh"


def _program_name() -> str:
    """Resolve the program name to use in completion snippets.

    Prefer the local dev entrypoint absolute path when running in the repo so
    developers get a working snippet that works from any directory. Fallback
    to the historical console script name `aidb` if repo detection fails.
    """
    try:
        from aidb_common.repo import detect_repo_root

        repo_root = detect_repo_root()
        dev_cli = repo_root / "dev-cli"
        if dev_cli.exists():
            # Use absolute path so completion works from any directory,
            # not just within the repo.
            return str(dev_cli.resolve())
    except Exception as e:
        logger.debug("Program name detection failed: %s", e)
    return "aidb"


def _eval_snippet(shell: str, prog: str) -> str:
    """Return the shell-eval snippet, with extra wiring for ./dev-cli and dev-cli.

    For dev workflows, users typically invoke the CLI as `./dev-cli` or `dev-cli`
    (if in PATH). Click's stock zsh snippet checks `$+commands[...]` and binds to
    the detected program name, which can prevent completions from triggering. We
    generate extra shims where needed so completion attaches to both `./dev-cli`
    and `dev-cli` while keeping the standard script for packaged installs.
    """
    is_dev_cli = Path(prog).name == "dev-cli"

    if shell == "zsh":
        base = f'eval "$({ENV_PREFIX_CHUNK}=zsh_source {prog})"'
        if is_dev_cli:
            # Provide a direct zsh completion function for dev-cli (without ./)
            # that delegates to Click's zsh_complete. The base eval already
            # handles ./dev-cli.
            extra = r"""

# Also register completion for dev-cli (without ./) in zsh.
_aidb_dev_cli_completion() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) \
_AIDB_COMPLETE=zsh_complete ./dev-cli)}")

    for type key descr in ${response}; do
        if [[ "$type" == "plain" ]]; then
            if [[ "$descr" == "_" ]]; then
                completions+=("$key")
            else
                completions_with_descriptions+=("$key":"$descr")
            fi
        elif [[ "$type" == "dir" ]]; then
            _path_files -/
        elif [[ "$type" == "file" ]]; then
            _path_files -f
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _aidb_dev_cli_completion dev-cli
"""
            return base + extra
        return base

    if shell == "bash":
        base = f'eval "$({ENV_PREFIX_CHUNK}=bash_source {prog})"'
        if is_dev_cli:
            # Also bind to dev-cli (without ./) when the program is ./dev-cli
            # Extract basename to match Click's function naming
            prog_basename = Path(prog).name
            safe_name = re.sub(
                r"\W*",
                "",
                prog_basename.replace("-", "_"),
                flags=re.ASCII,
            )
            func_name = f"_{safe_name}_completion"
            base += f"\ncomplete -o nosort -F {func_name} dev-cli"
        elif not is_dev_cli:
            # Also bind to ./dev-cli in dev repos when the program name is
            # something else (e.g. packaged installs).
            # Extract basename to match Click's function naming
            prog_basename = Path(prog).name
            safe_name = re.sub(
                r"\W*",
                "",
                prog_basename.replace("-", "_"),
                flags=re.ASCII,
            )
            func_name = f"_{safe_name}_completion"
            base += f"\ncomplete -o nosort -F {func_name} ./dev-cli"
        return base

    if shell == "fish":
        base = f"{ENV_PREFIX_CHUNK}=fish_source {prog} | source"
        if is_dev_cli:
            # Provide an additional fish binding for dev-cli (without ./) by
            # defining a small wrapper that calls fish_complete. The base source
            # already handles ./dev-cli.
            extra = r"""

function _aidb_dev_cli_completion;
    set -l response (env _AIDB_COMPLETE=fish_complete COMP_WORDS=(commandline -cp) \
COMP_CWORD=(commandline -t) ./dev-cli);
    for completion in $response;
        set -l metadata (string split "," $completion);
        if test $metadata[1] = "dir";
            __fish_complete_directories $metadata[2];
        else if test $metadata[1] = "file";
            __fish_complete_path $metadata[2];
        else if test $metadata[1] = "plain";
            echo $metadata[2];
        end;
    end;
end;

complete --no-files --command dev-cli --arguments "(_aidb_dev_cli_completion)";
"""
            return base + extra
        return base

    msg = f"Unsupported shell: {shell}"
    raise click.ClickException(msg)


def _target_rc_file(shell: str) -> Path:
    home = Path.home()
    if shell == "zsh":
        return home / ".zshrc"
    if shell == "bash":
        # On macOS, Terminal/iTerm start login shells by default; use .bash_profile
        if sys.platform == "darwin":
            return home / ".bash_profile"
        # Other platforms: prefer .bashrc
        return home / ".bashrc"
    if shell == "fish":
        # We'll place a conf snippet in conf.d; not an rc file per se
        return home / ".config" / "fish" / "conf.d" / "aidb.fish"
    msg = f"Unsupported shell: {shell}"
    raise click.ClickException(msg)


def _candidate_rc_files(shell: str) -> list[Path]:
    """Return a list of rc files to consider for the given shell.

    This allows uninstall to remove snippets from multiple files when appropriate.
    """
    home = Path.home()
    if shell == "zsh":
        return [home / ".zshrc"]
    if shell == "bash":
        if sys.platform == "darwin":
            return [home / ".bash_profile", home / ".bashrc"]
        return [home / ".bashrc", home / ".bash_profile"]
    if shell == "fish":
        return [home / ".config" / "fish" / "conf.d" / "aidb.fish"]
    msg = f"Unsupported shell: {shell}"
    raise click.ClickException(msg)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _backup_file(path: Path) -> Path | None:
    if not path.exists() or path.is_dir():
        return None
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak-{ts}")
    shutil.copy2(path, backup)
    return backup


def _atomic_write(path: Path, content: str) -> None:
    """Atomically write text to a file by writing to a temp file and renaming.

    Uses os.replace for an atomic move within the same filesystem.
    """
    tmp = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    _ensure_parent_dir(path)
    tmp.write_text(content)
    tmp.replace(path)


def rc_options(func):
    """Add common rc-related options to commands."""
    func = click.option(
        "--also-bashrc",
        is_flag=True,
        help="On macOS bash, also update ~/.bashrc to cover non-login shells",
    )(func)
    func = click.option(
        "--rc-file",
        type=click.Path(path_type=Path, dir_okay=False),
        help="Explicit rc file to use (overrides default detection)",
    )(func)
    return click.option(
        "--backup/--no-backup",
        "backup_enabled",
        default=True,
        help="Create a .bak backup before modifying rc file (default: on)",
    )(func)


def _append_snippet_to_path(
    path: Path,
    snippet: str,
    header_comment: str | None,
    backup_enabled: bool,
) -> tuple[bool, Path | None]:
    """Append the snippet to the rc file if not already present.

    Returns (changed, backup_path). Raises ClickException on failure.
    """
    try:
        _ensure_parent_dir(path)
        content = path.read_text() if path.exists() else ""
        if snippet in content:
            return False, None
        backup_path = _backup_file(path) if backup_enabled else None
        new_content = content
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        if header_comment:
            new_content += "\n" + header_comment + "\n"
        new_content += snippet + "\n"
        _atomic_write(path, new_content)
        return True, backup_path
    except Exception as e:
        msg = f"Failed to update {path}: {e}"
        raise click.ClickException(msg) from e


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    """Collapse sequences of 3+ consecutive blank lines to 2 blank lines.

    This cleans up artifacts from install/uninstall cycles while preserving intentional
    double blank lines commonly used in shell configs.
    """
    result = []
    blank_count = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    return result


def _remove_snippet_from_path(
    path: Path,
    snippet: str,
    shell: str,
    backup_enabled: bool,
) -> tuple[bool, Path | None, bool]:
    """Remove the snippet from the rc file.

    Returns (changed, backup_path, removed_file). For fish, if the file only contains
    the snippet, the file is deleted. Raises ClickException on failure.
    """
    try:
        if not path.exists():
            return False, None, False

        content = path.read_text()
        if shell == "fish":
            if content.strip() == snippet.strip():
                path.unlink(missing_ok=True)
                return True, None, True
            if snippet not in content:
                return False, None, False
            backup = _backup_file(path) if backup_enabled else None
            snippet_lines = set(snippet.splitlines())
            lines = [ln for ln in content.splitlines() if ln not in snippet_lines]
            lines = _collapse_blank_lines(lines)
            _atomic_write(path, "\n".join(lines) + "\n")
            return True, backup, False

        if snippet not in content:
            return False, None, False
        backup = _backup_file(path) if backup_enabled else None
        snippet_lines = set(snippet.splitlines())
        lines = [
            ln
            for ln in content.splitlines()
            if ln not in snippet_lines and ln.strip() != AIDB_COMPLETION_HEADER
        ]
        lines = _collapse_blank_lines(lines)
        _atomic_write(path, "\n".join(lines) + "\n")
        return True, backup, False
    except Exception as e:
        msg = f"Failed to update {path}: {e}"
        raise click.ClickException(msg) from e


@click.group(name="completion")
@click.pass_context
def group(ctx: click.Context) -> None:
    """Shell completion management for AIDB."""


@group.command(name="show")
@click.option(
    "--shell",
    "shell_name",
    help="Shell to show snippet for (zsh, bash, fish)",
)
@click.pass_context
@handle_exceptions
def show(ctx: click.Context, shell_name: str | None) -> None:
    """Print the eval snippet for shell completion setup."""
    from aidb_cli.core.constants import Icons

    output = ctx.obj.output
    output.section("Shell Completion Snippet", Icons.SHELL)

    shell = _detect_shell(shell_name)
    snippet = _eval_snippet(shell, _program_name())
    output.plain(snippet)


@group.command(name="install")
@click.option("--shell", "shell_name", help="Shell to install for (zsh, bash, fish)")
@click.option("--yes", "assume_yes", is_flag=True, help="Proceed without confirmation")
@rc_options
@click.pass_context
@handle_exceptions
def install(
    ctx: click.Context,
    shell_name: str | None,
    assume_yes: bool,
    backup_enabled: bool,
    rc_file: Path | None,
    also_bashrc: bool,
) -> None:
    """Install shell completion by appending the eval snippet to your shell rc.

    \b
    Safe and idempotent: will not duplicate lines, creates a .bak timestamped backup
    when modifying existing rc files. For fish, writes a small conf.d file.
    """  # noqa: W605
    from aidb_cli.core.constants import Icons

    output = ctx.obj.output
    output.section("Installing Shell Completion", Icons.ROCKET)

    shell = _detect_shell(shell_name)
    prog = _program_name()
    snippet = _eval_snippet(shell, prog)
    if rc_file is not None:
        candidates = [rc_file]
    elif shell == "bash" and sys.platform == "darwin" and also_bashrc:
        candidates = _candidate_rc_files(shell)
    else:
        candidates = [_target_rc_file(shell)]

    if not assume_yes:
        summary = "\n".join(f"- {p}" for p in candidates)
        proceed = click.confirm(
            f"Install completion for {shell} by modifying:\n{summary}",
            default=True,
        )
        if not proceed:
            output.warning("Installation cancelled")
            return

    for path in candidates:
        header = None if shell == "fish" else AIDB_COMPLETION_HEADER
        changed, backup_path = _append_snippet_to_path(
            path,
            snippet,
            header,
            backup_enabled,
        )
        if changed:
            if backup_path:
                output.success(
                    f"Completion installed. Backup saved at {backup_path}",
                )
            else:
                output.success(f"Completion installed in {path}")
        else:
            output.info(f"Completion already installed in {path}")


def _process_removal_result(
    output: OutputStrategy,
    changed: bool,
    backup: Path | None,
    removed_file: bool,
    rc_path: Path,
) -> None:
    """Output appropriate message based on removal result.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    changed : bool
        Whether the file was modified
    backup : Path | None
        Path to backup file if created
    removed_file : bool
        Whether the entire file was removed
    rc_path : Path
        Path to the rc file that was processed
    """
    if not changed:
        output.info(f"No matching completion snippet found in {rc_path}")
        return

    if removed_file:
        output.success(f"Removed file {rc_path}")
    elif backup:
        output.success(f"Completion removed. Backup saved at {backup}")
    else:
        output.success(f"Completion removed from {rc_path}")


def _uninstall_from_explicit_rc(
    output: OutputStrategy,
    rc_path: Path,
    snippet: str,
    shell: str,
    backup_enabled: bool,
    assume_yes: bool,
) -> bool:
    """Remove completion from an explicitly specified rc file.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    rc_path : Path
        Path to the rc file
    snippet : str
        Completion snippet to remove
    shell : str
        Shell type (zsh, bash, fish)
    backup_enabled : bool
        Whether to create backups
    assume_yes : bool
        Skip confirmation prompts

    Returns
    -------
    bool
        True if removal succeeded, False if cancelled or file doesn't exist
    """
    if not rc_path.exists():
        output.info(f"No completion configuration found at {rc_path}")
        return False

    if not assume_yes:
        proceed = click.confirm(
            f"Remove completion from {rc_path}?",
            default=True,
        )
        if not proceed:
            output.warning("Uninstall cancelled")
            return False

    changed, backup, removed_file = _remove_snippet_from_path(
        rc_path,
        snippet,
        shell,
        backup_enabled,
    )
    _process_removal_result(output, changed, backup, removed_file, rc_path)
    return True


def _cleanup_also_bashrc(
    output: OutputStrategy,
    snippet: str,
    shell: str,
    backup_enabled: bool,
) -> None:
    """Clean up ~/.bashrc for macOS bash when also_bashrc is enabled.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    snippet : str
        Completion snippet to remove
    shell : str
        Shell type (should be 'bash')
    backup_enabled : bool
        Whether to create backups
    """
    bashrc = Path.home() / ".bashrc"
    if not bashrc.exists():
        return

    changed, backup, removed_file = _remove_snippet_from_path(
        bashrc,
        snippet,
        shell,
        backup_enabled,
    )
    if not changed:
        return

    if removed_file:
        output.success(f"Removed file {bashrc}")
    elif backup:
        output.success(f"Also cleaned {bashrc} (backup at {backup})")
    else:
        output.success(f"Also cleaned {bashrc}")


def _uninstall_from_candidates(
    output: OutputStrategy,
    candidates: list[Path],
    snippet: str,
    shell: str,
    backup_enabled: bool,
    assume_yes: bool,
) -> None:
    """Remove completion from all candidate rc files.

    Parameters
    ----------
    output : OutputStrategy
        Output strategy for CLI messages
    candidates : list[Path]
        List of candidate rc files
    snippet : str
        Completion snippet to remove
    shell : str
        Shell type (zsh, bash, fish)
    backup_enabled : bool
        Whether to create backups
    assume_yes : bool
        Skip confirmation prompts
    """
    existing = [p for p in candidates if p.exists()]
    if not existing:
        joined = ", ".join(str(p) for p in candidates)
        output.info(f"No completion configuration found in any of: {joined}")
        return

    if not assume_yes:
        summary = "\n".join(f"- {p}" for p in existing)
        proceed = click.confirm(
            f"Remove completion from the following {len(existing)} file(s)?\n{summary}",
            default=True,
        )
        if not proceed:
            output.warning("Uninstall cancelled")
            return

    removed_any = False
    for rc_path in existing:
        changed, backup, removed_file = _remove_snippet_from_path(
            rc_path,
            snippet,
            shell,
            backup_enabled,
        )
        if changed:
            removed_any = True
            _process_removal_result(output, changed, backup, removed_file, rc_path)

    if not removed_any:
        output.info("No matching completion snippet found to remove.")


@group.command(name="uninstall")
@click.option("--shell", "shell_name", help="Shell to uninstall from (zsh, bash, fish)")
@click.option("--yes", "assume_yes", is_flag=True, help="Proceed without confirmation")
@rc_options
@click.pass_context
@handle_exceptions
def uninstall(
    ctx: click.Context,
    shell_name: str | None,
    assume_yes: bool,
    backup_enabled: bool,
    rc_file: Path | None,
    also_bashrc: bool,
) -> None:
    """Remove shell completion snippet from your shell configuration."""
    from aidb_cli.core.constants import Icons

    output = ctx.obj.output
    output.section("Uninstalling Shell Completion", Icons.TRASH)

    shell = _detect_shell(shell_name)
    prog = _program_name()
    snippet = _eval_snippet(shell, prog)

    if rc_file is not None:
        success = _uninstall_from_explicit_rc(
            output,
            rc_file,
            snippet,
            shell,
            backup_enabled,
            assume_yes,
        )
        if success and also_bashrc and shell == "bash" and sys.platform == "darwin":
            _cleanup_also_bashrc(output, snippet, shell, backup_enabled)
        return

    candidates = _candidate_rc_files(shell)
    _uninstall_from_candidates(
        output,
        candidates,
        snippet,
        shell,
        backup_enabled,
        assume_yes,
    )
