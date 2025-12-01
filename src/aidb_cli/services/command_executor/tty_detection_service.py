"""Service for detecting TTY and CI environment."""

import os
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import click

from aidb_common.env import read_bool
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class TtyDetectionService:
    """Service for detecting TTY and CI/CD environments.

    This service determines whether the execution environment supports interactive
    features like ANSI colors and streaming output.
    """

    def __init__(self, ctx: Optional["click.Context"] = None) -> None:
        """Initialize the TTY detection service.

        Parameters
        ----------
        ctx : click.Context | None, optional
            CLI context for accessing centralized environment
        """
        self.ctx = ctx
        self._is_ci: bool | None = None
        self._is_tty: bool | None = None
        self._supports_ansi: bool | None = None
        # Use centralized environment if available
        if ctx and hasattr(ctx.obj, "resolved_env"):
            self._env = ctx.obj.resolved_env
        else:
            self._env = None

    @property
    def is_ci(self) -> bool:
        """Check if running in CI/CD environment.

        Returns
        -------
        bool
            True if running in CI/CD environment
        """
        if self._is_ci is None:
            self._is_ci = self._detect_ci_environment()
        return self._is_ci

    @property
    def is_tty(self) -> bool:
        """Check if stdout is a TTY.

        Returns
        -------
        bool
            True if stdout is a TTY
        """
        if self._is_tty is None:
            self._is_tty = sys.stdout.isatty()
        return self._is_tty

    @property
    def supports_ansi(self) -> bool:
        """Check if environment supports ANSI escape codes.

        Returns
        -------
        bool
            True if ANSI codes are supported
        """
        if self._supports_ansi is None:
            from aidb_cli.core.constants import EnvVars

            # Allow forcing ANSI via env var
            force_ansi = read_bool(EnvVars.CLI_FORCE_ANSI, False)
            self._supports_ansi = self.is_tty or force_ansi
        return self._supports_ansi

    def should_stream(self, verbose: bool = False) -> bool:
        """Determine if output should be streamed.

        Parameters
        ----------
        verbose : bool, optional
            Whether verbose mode is enabled

        Returns
        -------
        bool
            True if output should be streamed
        """
        from aidb_cli.core.constants import EnvVars

        # Force streaming can override other settings
        force_streaming = read_bool(EnvVars.CLI_FORCE_STREAMING, False)
        if force_streaming:
            logger.debug(
                "Forced streaming enabled via %s",
                EnvVars.CLI_FORCE_STREAMING,
            )
            return True

        # Never stream in CI environments (too noisy)
        if self.is_ci:
            logger.debug("Streaming disabled: CI environment detected")
            return False

        # Stream if we have a TTY (both verbose and non-verbose modes)
        stream = self.is_tty
        mode = "verbose" if verbose else "normal"
        logger.debug(
            "Streaming %s: TTY=%s, mode=%s",
            "enabled" if stream else "disabled",
            self.is_tty,
            mode,
        )
        return stream

    def should_stream_for_verbosity(
        self,
        verbose: bool = False,
        verbose_debug: bool = False,
    ) -> bool:
        """Determine if output should be streamed based on verbosity level.

        This method implements the verbosity-aware streaming behavior:
        - No verbose flags: No streaming (only click echoes visible)
        - -v or -vvv: Enable 10-line rolling window for debug output

        Parameters
        ----------
        verbose : bool, optional
            Whether -v verbose mode is enabled
        verbose_debug : bool, optional
            Whether -vvv verbose debug mode is enabled

        Returns
        -------
        bool
            True if streaming should be enabled for the given verbosity level
        """
        # Never stream in CI environments regardless of verbosity
        if self.is_ci:
            logger.debug("Streaming disabled: CI environment detected")
            return False

        # No verbose flags: no streaming (only user-facing click echoes)
        if not verbose and not verbose_debug:
            logger.debug("Streaming disabled: no verbose flags")
            return False

        # -v or -vvv: enable streaming if we have TTY capability
        if verbose or verbose_debug:
            stream = self.is_tty
            mode = "verbose_debug" if verbose_debug else "verbose"
            logger.debug(
                "Verbosity-aware streaming %s: TTY=%s, mode=%s",
                "enabled" if stream else "disabled",
                self.is_tty,
                mode,
            )
            return stream

        return False

    def _detect_ci_environment(self) -> bool:
        """Detect if running in CI/CD environment.

        Returns
        -------
        bool
            True if CI environment detected
        """
        ci_env_vars = [
            "CI",  # Generic CI indicator
            "GITHUB_ACTIONS",  # GitHub Actions
            "GITLAB_CI",  # GitLab CI
            "JENKINS_HOME",  # Jenkins
            "CIRCLECI",  # CircleCI
            "TRAVIS",  # Travis CI
            "BUILDKITE",  # Buildkite
            "DRONE",  # Drone
            "TEAMCITY_VERSION",  # TeamCity
            "TF_BUILD",  # Azure DevOps
        ]

        # Use centralized environment if available, otherwise fall back to os.environ
        env_to_check = self._env if self._env else os.environ

        for var in ci_env_vars:
            if env_to_check.get(var):
                logger.debug("CI environment detected via %s", var)
                return True

        # Additional GitHub Actions specific check
        if env_to_check.get("GITHUB_WORKFLOW"):
            logger.debug("CI environment detected via GITHUB_WORKFLOW")
            return True

        logger.debug("No CI environment detected")
        return False

    def get_terminal_width(self, fallback: int = 80) -> int:
        """Get terminal width for formatting.

        Parameters
        ----------
        fallback : int, optional
            Fallback width if cannot determine

        Returns
        -------
        int
            Terminal width in columns
        """
        try:
            import shutil

            size = shutil.get_terminal_size(fallback=(fallback, 24))
            return size.columns
        except Exception:  # Fallback if terminal size unavailable
            return fallback
