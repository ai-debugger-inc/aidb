"""Custom Click decorators for common CLI patterns."""

import functools
import traceback
from collections.abc import Callable
from typing import Any, TypeVar

import click

from aidb.common.errors import AidbError
from aidb_cli.core.cleanup import ResourceCleaner
from aidb_cli.core.constants import ExitCode
from aidb_cli.core.param_types import LanguageParamType
from aidb_cli.core.utils import CliOutput
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _is_test_run_command(ctx: click.Context) -> bool:
    """Check if the current context is a test run command.

    Parameters
    ----------
    ctx : click.Context
        Click context to check

    Returns
    -------
    bool
        True if this is a 'test run' command context
    """
    return (
        ctx.obj is not None
        and hasattr(ctx.obj, "repo_root")
        and hasattr(ctx.obj, "command_executor")
        and ctx.info_name == "run"
        and ctx.parent is not None
        and ctx.parent.info_name == "test"
    )


def handle_exceptions(func: F) -> F:
    """Handle exceptions and convert to appropriate exit codes.

    Parameters
    ----------
    func : Callable
        Function to wrap

    Returns
    -------
    Callable
        Wrapped function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> None:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            # Graceful abort: set a context flag so services can downgrade noise
            ctx = click.get_current_context()
            try:
                if getattr(ctx, "obj", None) is not None:
                    ctx.obj.aborting = True
            except Exception as e:
                logger.debug("Failed to set aborting flag: %s", e)

            # Attempt best-effort cleanup unless --no-cleanup
            try:
                if _is_test_run_command(ctx):
                    no_cleanup = getattr(ctx.obj, "no_cleanup", False)
                    if not no_cleanup:
                        cleaner = ResourceCleaner(
                            ctx.obj.repo_root,
                            ctx.obj.command_executor,
                            ctx=ctx,
                        )
                        cleaner.cleanup_docker_resources()
            except Exception as cleanup_error:
                logger.debug("Cleanup attempt failed after abort: %s", cleanup_error)

            # Exit with a generic interrupt code; Click will handle terminal state
            ctx.exit(ExitCode.GENERAL_ERROR)
        except (AidbError, FileNotFoundError, PermissionError, Exception) as e:
            # Allow Click's normal exit mechanism to propagate
            if isinstance(e, click.exceptions.Exit):
                raise

            # Try to cleanup docker resources if this appears to be a test command
            # BUT respect --no-cleanup flag if set
            ctx = click.get_current_context()
            try:
                if _is_test_run_command(ctx):
                    # Check if no_cleanup flag is set
                    no_cleanup = getattr(ctx.obj, "no_cleanup", False)
                    if not no_cleanup:
                        cleaner = ResourceCleaner(
                            ctx.obj.repo_root,
                            ctx.obj.command_executor,
                            ctx=ctx,
                        )
                        cleaner.cleanup_docker_resources()
                    else:
                        logger.info(
                            "Skipping cleanup on exception (--no-cleanup flag set)",
                        )
            except Exception as cleanup_error:
                # Best effort cleanup - don't let cleanup errors mask the original error
                logger.debug("Cleanup attempt failed: %s", cleanup_error)

            # Handle specific exception types
            if isinstance(e, AidbError):
                CliOutput.error(str(e))
                ctx.exit(ExitCode.GENERAL_ERROR)
            elif isinstance(e, FileNotFoundError):
                CliOutput.error(f"File not found: {e}")
                ctx.exit(ExitCode.NOT_FOUND)
            elif isinstance(e, PermissionError):
                CliOutput.error(f"Permission denied: {e}")
                ctx.exit(ExitCode.PERMISSION_ERROR)
            else:
                CliOutput.error(f"Unexpected error: {e}")
                # Show full traceback only in verbose-debug mode
                try:
                    verbose_debug = bool(getattr(ctx.obj, "verbose_debug", False))
                except Exception:
                    verbose_debug = False
                if verbose_debug:
                    CliOutput.error("Full traceback:")
                    CliOutput.error(traceback.format_exc())
                else:
                    CliOutput.info("Re-run with -vvv for full traceback")
                ctx.exit(ExitCode.GENERAL_ERROR)

    return wrapper  # type: ignore[return-value]


def require_repo_context(func: F) -> F:
    """Ensure command is run in repository context.

    Parameters
    ----------
    func : Callable
        Function to wrap

    Returns
    -------
    Callable
        Wrapped function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        ctx = click.get_current_context()
        aidb_ctx = ctx.obj

        if not aidb_ctx or not hasattr(aidb_ctx, "repo_root"):
            CliOutput.error("This command must be run from within an AIDB repository")
            ctx.exit(ExitCode.CONFIG_ERROR)

        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def validate_languages(func: F) -> F:
    """Validate language parameters.

    Parameters
    ----------
    func : Callable
        Function to wrap

    Returns
    -------
    Callable
        Wrapped function
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        ctx = click.get_current_context()
        supported: list[str] = []
        try:
            if ctx.obj and hasattr(ctx.obj, "build_manager"):
                supported = ctx.obj.build_manager.get_supported_languages()
        except Exception:
            # Fallback to common set
            from aidb_cli.core.constants import SUPPORTED_LANGUAGES

            supported = SUPPORTED_LANGUAGES

        if "language" in kwargs:
            lang = kwargs["language"]
            if isinstance(lang, str) and lang not in supported:
                CliOutput.error(f"Unsupported language: {lang}")
                CliOutput.error(f"Supported languages: {', '.join(supported)}")
                ctx.exit(ExitCode.CONFIG_ERROR)

        if "languages" in kwargs:
            langs = kwargs["languages"]
            if isinstance(langs, (list, tuple)):
                for lang in langs:
                    if lang not in supported:
                        CliOutput.error(f"Unsupported language: {lang}")
                        CliOutput.error(
                            f"Supported languages: {', '.join(supported)}",
                        )
                        ctx.exit(ExitCode.CONFIG_ERROR)

        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]


def common_options(func: F) -> F:
    """Add common CLI options.

    Parameters
    ----------
    func : Callable
        Function to wrap

    Returns
    -------
    Callable
        Wrapped function with common options
    """
    return click.option(
        "--dry-run",
        is_flag=True,
        help="Show what would be done without executing",
    )(func)


def language_option(
    multiple: bool = False,
    required: bool = False,
    help_text: str | None = None,
) -> Callable[[F], F]:
    """Create decorator for language selection options.

    Parameters
    ----------
    multiple : bool
        Allow multiple language selection
    required : bool
        Make language selection required
    help_text : str, optional
        Custom help text

    Returns
    -------
    Callable
        Decorator function
    """
    if help_text is None:
        help_text = "Language(s) to target (choices resolved dynamically)"

    def decorator(func: F) -> F:
        return click.option(
            "--language",
            "-l",
            type=LanguageParamType(include_all=multiple is False),
            multiple=multiple,
            required=required,
            help=help_text,
        )(func)

    return decorator


def force_option(func: F) -> F:
    """Add force option.

    Parameters
    ----------
    func : Callable
        Function to wrap

    Returns
    -------
    Callable
        Wrapped function
    """
    return click.option(
        "--force",
        "-f",
        is_flag=True,
        help="Force operation without confirmation",
    )(func)
