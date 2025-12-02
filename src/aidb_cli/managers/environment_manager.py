"""Centralized environment resolution and management for CLI commands.

This module provides a single source of truth for environment variable resolution
throughout the CLI application. Environment variables are resolved once at CLI entry and
made available via the Click context object.
"""

import os
from pathlib import Path

from aidb_cli.core.constants import ProjectNames
from aidb_common.config import VersionManager
from aidb_common.env.resolver import resolve_env_template
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class EnvironmentManager:
    """Centralized environment resolution and management.

    This class provides a single source of truth for environment variables
    throughout the CLI. It resolves environment variables once at startup
    and provides methods to update them as needed.

    Resolution Order:
    1. System environment variables (base)
    2. .env.test template (project defaults)
    3. Command-specific updates (user overrides via update() method)

    Attributes
    ----------
    repo_root : Path
        Repository root directory
    _resolved_env : dict[str, str]
        The resolved environment variables
    _env_test_file : Path
        Path to .env.test template file
    _version_manager : VersionManager | None
        Version manager for Docker build args
    """

    def __init__(self, repo_root: Path) -> None:
        """Initialize the environment manager.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        """
        self.repo_root = repo_root
        self._resolved_env: dict[str, str] = {}
        self._env_test_file = repo_root / ".env.test"
        self._version_manager: VersionManager | None = None
        self._update_history: list[dict[str, str]] = []

        # Resolve environment immediately upon initialization
        self.resolve()

    def resolve(self) -> dict[str, str]:
        """Resolve the complete environment.

        This method should be called once at CLI startup to establish
        the base environment. Subsequent modifications should use update().

        Returns
        -------
        dict[str, str]
            The resolved environment variables
        """
        logger.debug("Starting centralized environment resolution")

        # 1. Start with system environment
        env = dict(os.environ)
        logger.debug("Loaded %s system environment variables", len(env))

        # 2. Parse and merge .env.test template if it exists
        if self._env_test_file.exists():
            try:
                template_vars = resolve_env_template(self._env_test_file, strict=False)
                logger.debug("Loaded %s variables from .env.test", len(template_vars))
                env.update(template_vars)
            except (OSError, ValueError, KeyError) as e:
                logger.warning("Could not parse .env.test: %s", e)

        # 3. Add essential defaults that should always be present
        essential_defaults = self._get_essential_defaults()
        for key, value in essential_defaults.items():
            if key not in env:
                env[key] = value
                logger.debug("Added essential default: %s=%s", key, value)

        # 4. Add version manager Docker build args if available
        version_manager = self._get_version_manager()
        if version_manager:
            docker_args = version_manager.get_docker_build_args()
            env.update(docker_args)
            logger.debug(
                "Added %s Docker build args from version manager",
                len(docker_args),
            )

        # 5. Validate critical environment variables
        self._validate_environment(env)

        # Store the resolved environment
        self._resolved_env = env

        # Log summary of resolved environment
        self._log_environment_summary()

        return self._resolved_env

    def get_environment(self) -> dict[str, str]:
        """Get the current resolved environment.

        Returns
        -------
        dict[str, str]
            The current environment variables
        """
        if not self._resolved_env:
            self.resolve()
        return self._resolved_env.copy()

    def update(self, updates: dict[str, str], source: str = "command") -> None:
        """Update the resolved environment with new values.

        This method should be used by commands to add or override
        environment variables after initial resolution.

        Parameters
        ----------
        updates : dict[str, str]
            Environment variables to add or update
        source : str
            Source of the update for logging purposes
        """
        if not updates:
            return

        logger.debug("Updating environment from %s: %s", source, list(updates.keys()))

        # Track the update for debugging
        self._update_history.append(
            {
                "source": source,
                **updates,
            },
        )

        # Apply updates
        for key, value in updates.items():
            old_value = self._resolved_env.get(key)
            self._resolved_env[key] = str(value)

            if old_value != value:
                if old_value is None:
                    logger.debug("  %s: (not set) -> %s", key, value)
                else:
                    logger.debug("  %s: %s -> %s", key, old_value, value)

    def _get_essential_defaults(self) -> dict[str, str]:
        """Get essential default values that should always be present.

        Returns
        -------
        dict[str, str]
            Essential default environment variables
        """
        return {
            "REPO_ROOT": str(self.repo_root),
            "COMPOSE_PROJECT_NAME": ProjectNames.TEST_PROJECT,
            # Note: We intentionally do NOT set defaults for TEST_PATTERN
            # or PYTEST_ADDOPTS here - those should come from commands
        }

    def _get_version_manager(self) -> VersionManager | None:
        """Get or create the version manager.

        Returns
        -------
        VersionManager | None
            Version manager instance or None if not available
        """
        if self._version_manager is None:
            try:
                from aidb_cli.core.paths import ProjectPaths

                versions_file = self.repo_root / ProjectPaths.VERSIONS_YAML
                if versions_file.exists():
                    self._version_manager = VersionManager(versions_file)
                    logger.debug("Loaded version manager from %s", versions_file)
            except (OSError, ValueError) as e:
                logger.debug("Could not load version manager: %s", e)

        return self._version_manager

    def _validate_environment(self, env: dict[str, str]) -> None:
        """Validate and ensure critical environment variables are present.

        Parameters
        ----------
        env : dict[str, str]
            Environment to validate (modified in place)
        """
        # Ensure critical system variables are present
        critical_system = ["PATH", "HOME", "USER"]
        for var in critical_system:
            if var not in env:
                value = os.environ.get(var, "")
                if value:
                    env[var] = value
                    logger.debug("Restored critical system variable: %s", var)

        # Ensure REPO_ROOT is always set
        if "REPO_ROOT" not in env:
            env["REPO_ROOT"] = str(self.repo_root)
            logger.warning("REPO_ROOT was missing - added to environment")

    def _log_environment_summary(self) -> None:
        """Log a summary of the resolved environment for debugging."""
        total = len(self._resolved_env)

        # Count variables by prefix
        from aidb_cli.core.constants import ENV_VAR_PREFIXES

        summary = {}
        for prefix in ENV_VAR_PREFIXES:
            count = sum(1 for k in self._resolved_env if k.startswith(prefix))
            if count > 0:
                summary[prefix] = count

        logger.debug("Environment resolved: %s total variables", total)
        for prefix, count in summary.items():
            logger.debug("  %s*: %s variables", prefix, count)

        # Log specific important variables
        important_vars = ["REPO_ROOT", "TEST_SUITE", "TEST_PATTERN", "PYTEST_ADDOPTS"]
        for var in important_vars:
            value = self._resolved_env.get(var, "(not set)")
            if var in ["TEST_PATTERN", "PYTEST_ADDOPTS"] and value:
                logger.debug("  %s=%s", var, value)

    def get_update_history(self) -> list[dict[str, str]]:
        """Get the history of environment updates.

        Useful for debugging to see what updates were applied and when.

        Returns
        -------
        list[dict[str, str]]
            List of update records with source and variables
        """
        return self._update_history.copy()

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean environment variable.

        Uses the same parsing logic as aidb_common.env.reader.

        Parameters
        ----------
        key : str
            Environment variable name
        default : bool
            Default value if not set

        Returns
        -------
        bool
            Parsed boolean value
        """
        value = self._resolved_env.get(key)
        if value is None:
            return default

        # Use the same logic as reader.read_bool
        value_lower = value.lower().strip()
        if value_lower in {"1", "true", "yes", "on", "y", "t"}:
            return True
        if value_lower in {"0", "false", "no", "off", "n", "f"}:
            return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer environment variable.

        Uses the same parsing logic as aidb_common.env.reader.

        Parameters
        ----------
        key : str
            Environment variable name
        default : int
            Default value if not set

        Returns
        -------
        int
            Parsed integer value
        """
        value = self._resolved_env.get(key)
        if value is None:
            return default

        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get a string environment variable.

        Parameters
        ----------
        key : str
            Environment variable name
        default : str
            Default value if not set

        Returns
        -------
        str
            String value
        """
        return self._resolved_env.get(key, default)

    def get_list(self, key: str, default: list | None = None) -> list:
        """Get a list environment variable.

        Uses the same parsing logic as aidb_common.env.reader.
        Splits on commas by default.

        Parameters
        ----------
        key : str
            Environment variable name
        default : list | None
            Default value if not set

        Returns
        -------
        list
            Parsed list value
        """
        value = self._resolved_env.get(key)
        if value is None:
            return default or []

        # Use the same logic as reader.read_list
        # Split on commas and strip whitespace
        if not value.strip():
            return default or []

        items = [item.strip() for item in value.split(",")]
        return [item for item in items if item]

    def validate_test_pattern(self, pattern: str | None) -> str | None:
        """Validate TEST_PATTERN format.

        Ensures the pattern is a valid pytest pattern.

        Parameters
        ----------
        pattern : str | None
            Pattern to validate

        Returns
        -------
        str | None
            Validated pattern or None if invalid
        """
        if not pattern:
            return None

        # Basic validation - ensure it's not malformed
        # Patterns can be:
        # - test file paths: tests/test_foo.py
        # - test patterns: test_*.py
        # - test functions: test_foo.py::TestClass::test_method
        # - keywords: -k "test_foo or test_bar"

        # Remove leading/trailing whitespace
        pattern = pattern.strip()

        # Check for common mistakes
        if pattern.startswith("--"):
            logger.warning("TEST_PATTERN appears to contain pytest args: %s", pattern)
            return None

        return pattern

    def validate_pytest_addopts(self, args: str | None) -> list[str]:
        """Validate and parse PYTEST_ADDOPTS.

        Ensures pytest arguments are properly formatted.

        Parameters
        ----------
        args : str | None
            Arguments string to validate

        Returns
        -------
        list[str]
            Parsed and validated arguments
        """
        if not args:
            return []

        # Split arguments preserving quoted strings
        import shlex

        try:
            parsed = shlex.split(args)
        except ValueError as e:
            logger.warning("Invalid PYTEST_ADDOPTS format: %s", e)
            return []

        # Validate no dangerous arguments
        dangerous = ["--rootdir", "--cache-clear", "--looponfail"]
        filtered = []
        for arg in parsed:
            if any(arg.startswith(d) for d in dangerous):
                logger.warning("Potentially dangerous pytest arg filtered: %s", arg)
            else:
                filtered.append(arg)

        return filtered

    def validate_test_suite(self, suite: str | None) -> str | None:
        """Validate TEST_SUITE value.

        Ensures the suite name is valid.

        Parameters
        ----------
        suite : str | None
            Suite name to validate

        Returns
        -------
        str | None
            Validated suite name or None if invalid
        """
        if not suite:
            return None

        # Known valid suites (extend as needed)
        valid_suites = [
            "cli",
            "mcp",
            "adapters",
            "logging",
            "common",
            "integration",
            "unit",
            "all",
        ]

        suite = suite.lower().strip()
        if suite not in valid_suites:
            logger.warning(
                "Unknown TEST_SUITE: %s, valid options: %s",
                suite,
                valid_suites,
            )
            return None

        return suite

    def export_for_subprocess(self) -> dict[str, str]:
        """Export environment for subprocess execution.

        Returns a copy of the resolved environment suitable for
        passing to subprocess.run() or similar.

        Returns
        -------
        dict[str, str]
            Environment variables for subprocess
        """
        # Return a copy with all values as strings
        return {k: str(v) for k, v in self._resolved_env.items()}

    def _mask_sensitive_value(self, key: str, value: str) -> str:
        """Mask sensitive environment variable values.

        Parameters
        ----------
        key : str
            Environment variable name
        value : str
            Environment variable value

        Returns
        -------
        str
            Masked value if sensitive, original value otherwise
        """
        sensitive_keys = ["SECRET", "KEY", "TOKEN", "PASSWORD"]
        if any(s in key for s in sensitive_keys):
            return "***MASKED***"
        return value

    def _collect_all_variables(self) -> list[str]:
        """Collect all environment variables for display.

        Returns
        -------
        list[str]
            Formatted variable lines
        """
        lines = ["All variables:"]
        for key in sorted(self._resolved_env.keys()):
            value = self._resolved_env[key]
            value = self._mask_sensitive_value(key, value)
            lines.append(f"  {key}={value}")
        return lines

    def _collect_relevant_variables(self) -> list[str]:
        """Collect only relevant environment variables for display.

        Returns
        -------
        list[str]
            Formatted variable lines
        """
        from aidb_cli.core.constants import ENV_VAR_PREFIXES

        lines = ["Relevant variables:"]

        for prefix in ENV_VAR_PREFIXES:
            prefix_vars = {
                k: v for k, v in self._resolved_env.items() if k.startswith(prefix)
            }
            if prefix_vars:
                lines.append(f"\n{prefix}* variables:")
                for key in sorted(prefix_vars.keys()):
                    value = prefix_vars[key]
                    value = self._mask_sensitive_value(key, value)
                    lines.append(f"  {key}={value}")

        # Always show REPO_ROOT
        if "REPO_ROOT" in self._resolved_env:
            lines.append(f"\nREPO_ROOT={self._resolved_env['REPO_ROOT']}")

        return lines

    def _format_update_history(self) -> list[str]:
        """Format update history for display.

        Returns
        -------
        list[str]
            Formatted history lines
        """
        if not self._update_history:
            return []

        lines = ["\n=== Update History ==="]
        for i, update in enumerate(self._update_history, 1):
            source = update.get("source", "unknown")
            lines.append(f"\n{i}. Update from {source}:")
            for key, value in update.items():
                if key != "source":
                    lines.append(f"   {key}={value}")

        return lines

    def debug_dump(self, show_all: bool = False) -> str:
        """Generate a debug dump of the environment.

        Parameters
        ----------
        show_all : bool
            If True, show all variables. If False, only show relevant ones.

        Returns
        -------
        str
            Formatted debug output
        """
        lines = ["=== Environment Manager Debug Dump ==="]
        lines.append(f"Total variables: {len(self._resolved_env)}")
        lines.append("")

        if show_all:
            lines.extend(self._collect_all_variables())
        else:
            lines.extend(self._collect_relevant_variables())

        lines.extend(self._format_update_history())

        return "\n".join(lines)
