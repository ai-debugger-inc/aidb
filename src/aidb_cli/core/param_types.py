"""Dynamic Click ParamTypes with shell completion for AIDB CLI.

Provides runtime-validated, shell-completable parameter types for:
- Languages (from AdapterRegistry/BuildManager)
- Docker suites (from docker-compose.yaml)
- Docker profiles (from docker-compose.yaml)
- Test suites, markers, and patterns
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click
from click import Context
from click.shell_completion import CompletionItem

from aidb_common.io import safe_read_yaml
from aidb_common.io.files import FileOperationError
from aidb_common.repo import detect_repo_root
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = get_cli_logger(__name__)


def _get_repo_root_from_ctx(ctx: Context | None) -> Path:
    try:
        if ctx is not None:
            obj = getattr(ctx, "obj", None)
            if obj is not None and hasattr(obj, "repo_root"):
                return Path(obj.repo_root)
    except Exception as e:
        logger.debug("Failed to get repo_root from context: %s", e)
    return detect_repo_root()


def _load_compose_profiles(repo_root: Path) -> set[str]:
    """Parse compose file and collect all profile tokens from services."""
    from aidb_cli.core.paths import ProjectPaths

    compose_path = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
    profiles: set[str] = set()

    if not compose_path.exists():
        return profiles

    try:
        data = safe_read_yaml(compose_path)
        services = data.get("services", {}) or {}
        for svc in services.values():
            prof = svc.get("profiles")
            if isinstance(prof, list):
                for p in prof:
                    if isinstance(p, str) and p.strip():
                        profiles.add(p.strip())
            elif isinstance(prof, str) and prof.strip():
                profiles.add(prof.strip())
    except FileOperationError as e:
        logger.debug("Failed to parse docker-compose.yaml: %s", e)

    return profiles


def _ordered(items: Iterable[str], order: list[str]) -> list[str]:
    found = [i for i in order if i in items]
    the_rest = sorted([i for i in items if i not in order])
    return found + the_rest


class DynamicChoice(click.ParamType):
    """Dynamic choice parameter type that computes choices at runtime.

    Parameters
    ----------
    provider : Callable[[Context | None], list[str]]
        Function that returns available choices
    extras : list[str] | None, optional
        Additional allowed values beyond provider results
    case_sensitive : bool, default=False
        Whether choice matching is case-sensitive
    max_help_choices : int | None, optional
        Maximum number of choices to show in help text
    """

    name = "dynamic-choice"

    def __init__(
        self,
        provider: Callable[[Context | None], list[str]],
        *,
        extras: list[str] | None = None,
        case_sensitive: bool = False,
        max_help_choices: int | None = None,
    ) -> None:
        self.provider = provider
        self.extras = extras or []
        self.case_sensitive = case_sensitive
        self.max_help_choices = max_help_choices

    def _choices(self, ctx: Context | None) -> list[str]:
        try:
            vals = list(self.provider(ctx))
        except Exception as e:
            logger.debug("DynamicChoice provider failed: %s", e)
            vals = []
        vals = vals + [e for e in self.extras if e not in vals]
        return vals

    def get_metavar(self, param, ctx: Context | None) -> str | None:  # noqa: ARG002
        """Return metavar showing actual choices for help text."""
        try:
            choices = self._choices(ctx)
            if not choices:
                return None

            display_choices = choices
            if self.max_help_choices and len(choices) > self.max_help_choices:
                display_choices = choices[: self.max_help_choices]
                return f"[{('|'.join(display_choices))}|...]"

            return f"[{('|'.join(display_choices))}]"
        except Exception as e:
            logger.debug("DynamicChoice get_metavar failed: %s", e)
            return None

    def convert(self, value: str, param, ctx: Context | None) -> str:
        """Convert and validate the parameter value.

        Parameters
        ----------
        value : str
            The value to convert
        param : Parameter
            The Click parameter
        ctx : Context | None
            The Click context

        Returns
        -------
        str
            The validated value
        """
        choices = self._choices(ctx)
        if not self.case_sensitive:
            lchoices = {c.lower(): c for c in choices}
            if value.lower() in lchoices:
                return lchoices[value.lower()]
        else:
            if value in choices:
                return value
        self.fail(
            f"invalid choice: {value}. (choose from {', '.join(choices)})",
            param,
            ctx,
        )
        # self.fail raises, so execution never reaches here.
        msg = "unreachable"
        raise AssertionError(msg)

    def shell_complete(self, ctx: Context | None, param, incomplete):  # noqa: ARG002
        """Provide shell completion suggestions.

        Parameters
        ----------
        ctx : Context | None
            The Click context
        param : Parameter
            The Click parameter
        incomplete : str
            The incomplete value being completed

        Returns
        -------
        list[CompletionItem]
            List of completion suggestions
        """
        choices = self._choices(ctx)
        if not self.case_sensitive:
            return [
                CompletionItem(c)
                for c in choices
                if c.lower().startswith(incomplete.lower())
            ]
        return [CompletionItem(c) for c in choices if c.startswith(incomplete)]


def _get_languages_from_build_manager(ctx: Context | None) -> list[str] | None:
    """Attempt to get languages from BuildManager in context.

    Parameters
    ----------
    ctx : Context | None
        The Click context

    Returns
    -------
    list[str] | None
        List of languages if successful, None otherwise
    """
    if ctx is None:
        return None

    obj = getattr(ctx, "obj", None)
    if obj is None or not hasattr(obj, "build_manager"):
        return None

    try:
        langs = obj.build_manager.get_supported_languages()
        return list(langs)
    except Exception as e:
        logger.debug("Language provider via BuildManager failed: %s", e)
        return None


def _get_languages_from_registry() -> list[str] | None:
    """Attempt to get languages from AdapterRegistry.

    Returns
    -------
    list[str] | None
        List of languages if successful, None otherwise
    """
    try:
        from aidb.session.adapter_registry import AdapterRegistry

        return AdapterRegistry().get_languages()
    except Exception as e:
        logger.debug("Language provider via AdapterRegistry failed: %s", e)
        return None


def _get_fallback_languages() -> list[str]:
    """Get fallback list of supported languages from constants.

    Returns
    -------
    list[str]
        List of supported languages
    """
    from aidb_cli.core.constants import SUPPORTED_LANGUAGES

    return SUPPORTED_LANGUAGES


class LanguageParamType(DynamicChoice):
    """Parameter type for language selection with dynamic choices."""

    def __init__(self, include_all: bool = False) -> None:
        def provider(ctx: Context | None) -> list[str]:
            langs = _get_languages_from_build_manager(ctx)
            if langs is not None:
                return langs

            langs = _get_languages_from_registry()
            if langs is not None:
                return langs

            return _get_fallback_languages()

        extras = ["all"] if include_all else []
        super().__init__(provider, extras=extras, case_sensitive=False)


class DockerSuiteParamType(DynamicChoice):
    """Parameter type for Docker test suite selection."""

    def __init__(self) -> None:
        from aidb_cli.services.test import TestSuites

        supported = {
            TestSuites.MCP.name,
            "adapters",
        }

        def provider(ctx: Context | None) -> list[str]:
            repo_root = _get_repo_root_from_ctx(ctx)
            profiles = _load_compose_profiles(repo_root)
            # suites are a curated subset
            suites = [p for p in profiles if p in supported]
            if not suites:
                suites = list(supported)
            return _ordered(suites, ["mcp", "adapters"])

        super().__init__(provider, case_sensitive=False)


class DockerProfileParamType(DynamicChoice):
    """Parameter type for Docker profile selection."""

    def __init__(self, include_auto: bool = False) -> None:
        def provider(ctx: Context | None) -> list[str]:
            from aidb_cli.core.constants import DockerProfiles

            repo_root = _get_repo_root_from_ctx(ctx)
            profiles = _load_compose_profiles(repo_root)
            if not profiles:
                profiles = {
                    DockerProfiles.MCP,
                    DockerProfiles.ADAPTERS,
                    DockerProfiles.BASE,
                    DockerProfiles.SHELL,
                }
            return _ordered(
                profiles,
                [
                    DockerProfiles.MCP,
                    DockerProfiles.ADAPTERS,
                    DockerProfiles.BASE,
                    DockerProfiles.SHELL,
                ],
            )

        extras = ["auto"] if include_auto else []
        super().__init__(provider, extras=extras, case_sensitive=False)


class TestSuiteParamType(DynamicChoice):
    """Test suite discovery from both Docker and local tests."""

    def __init__(self) -> None:
        def provider(ctx: Context | None) -> list[str]:
            suites: set[str] = set()

            # Get all suite names from TestSuites registry
            from aidb_cli.services.test import TestSuites

            all_suite_names = [s.name for s in TestSuites.all()]
            suites.update(all_suite_names)

            # Discover local test suites from directory structure
            repo_root = _get_repo_root_from_ctx(ctx)
            test_root = repo_root / "src" / "tests"
            if test_root.exists():
                for path in test_root.iterdir():
                    if path.is_dir() and path.name.startswith("aidb_"):
                        suite_name = path.name.split("aidb_", 1)[1]
                        suites.add(suite_name)

            return _ordered(
                suites,
                ["cli", "shared", "mcp", "adapters", "frameworks"],
            )

        super().__init__(provider, extras=["all"], case_sensitive=False)


def _get_common_markers() -> set[str]:
    """Get the common set of pytest markers.

    Returns
    -------
    set[str]
        Set of common pytest markers
    """
    return {
        "unit",
        "integration",
        "e2e",
        "slow",
        "asyncio",
        "parametrize",
        "skip",
        "skipif",
        "xfail",
    }


def _parse_pytest_ini_markers(pytest_ini: Path) -> set[str]:
    """Parse markers from pytest.ini file.

    Parameters
    ----------
    pytest_ini : Path
        Path to pytest.ini file

    Returns
    -------
    set[str]
        Set of discovered marker names
    """
    markers: set[str] = set()
    if not pytest_ini.exists():
        return markers

    try:
        import configparser

        config = configparser.ConfigParser()
        config.read(pytest_ini)
        if "tool:pytest" in config and "markers" in config["tool:pytest"]:
            marker_lines = config["tool:pytest"]["markers"].splitlines()
            for line in marker_lines:
                if ":" in line:
                    marker_name = line.split(":", 1)[0].strip()
                    if marker_name:
                        markers.add(marker_name)
    except (OSError, ValueError) as e:
        logger.debug("Failed to parse pytest.ini: %s", e)

    return markers


def _extract_marker_names(pytest_markers: list) -> set[str]:
    """Extract marker names from pytest marker list.

    Parameters
    ----------
    pytest_markers : list
        List of marker strings from config

    Returns
    -------
    set[str]
        Set of extracted marker names
    """
    markers: set[str] = set()
    for marker in pytest_markers:
        if isinstance(marker, str) and ":" in marker:
            marker_name = marker.split(":", 1)[0].strip()
            if marker_name:
                markers.add(marker_name)
                logger.debug("Added marker from pyproject.toml: %s", marker_name)
    return markers


def _parse_pyproject_toml_markers(pyproject: Path) -> set[str]:
    """Parse markers from pyproject.toml file.

    Parameters
    ----------
    pyproject : Path
        Path to pyproject.toml file

    Returns
    -------
    set[str]
        Set of discovered marker names
    """
    if not pyproject.exists():
        return set()

    try:
        import tomllib

        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        pytest_markers = (
            data.get("tool", {})
            .get("pytest", {})
            .get("ini_options", {})
            .get("markers", [])
        )
        logger.debug("Found %d markers from pyproject.toml", len(pytest_markers))
        return _extract_marker_names(pytest_markers)
    except ImportError:
        try:
            import tomli

            with pyproject.open("rb") as f:
                data = tomli.load(f)
            pytest_markers = (
                data.get("tool", {})
                .get("pytest", {})
                .get("ini_options", {})
                .get("markers", [])
            )
            logger.debug(
                "Found %d markers from pyproject.toml via tomli",
                len(pytest_markers),
            )
            return _extract_marker_names(pytest_markers)
        except (OSError, ValueError) as e:
            logger.debug("Failed to parse pyproject.toml with tomli: %s", e)
            return set()
    except (OSError, ValueError) as e:
        logger.debug("Failed to parse pyproject.toml with tomllib: %s", e)
        return set()


class TestMarkerParamType(DynamicChoice):
    """Pytest marker discovery from test files."""

    def __init__(self) -> None:
        def provider(ctx: Context | None) -> list[str]:
            markers = _get_common_markers()
            repo_root = _get_repo_root_from_ctx(ctx)

            markers.update(_parse_pytest_ini_markers(repo_root / "pytest.ini"))
            markers.update(_parse_pyproject_toml_markers(repo_root / "pyproject.toml"))

            return _ordered(
                markers,
                ["unit", "integration", "e2e", "slow", "asyncio", "parametrize"],
            )

        super().__init__(provider, case_sensitive=False, max_help_choices=8)


class FlexiblePatternParamType(click.ParamType):
    """Accept any string pattern for pytest -k expressions.

    Unlike the old TestPatternParamType, this accepts any string to support flexible
    test filtering exactly like pytest's -k option.
    """

    name = "pattern"

    def convert(
        self,
        value: str,
        param,  # noqa: ARG002
        ctx: Context | None,  # noqa: ARG002
    ) -> str:
        """Accept any string pattern - no validation needed for flexibility."""
        if value is None:
            return value
        return value

    def get_metavar(self, param, ctx: Context | None) -> str:  # noqa: ARG002
        """Return metavar showing this accepts pytest expressions."""
        return "<pytest_expression>"

    def shell_complete(
        self,
        ctx: Context | None,  # noqa: ARG002
        param,  # noqa: ARG002
        incomplete: str,
    ):
        """Provide shell completion with common patterns."""
        common_patterns = [
            "test_*",
            "*_test",
            "*_unit",
            "*_integration",
            "*_e2e",
            "*_multilang",
            "test_*_real*",
            "*slow*",
            "TestCase*",
        ]

        return [
            CompletionItem(pattern)
            for pattern in common_patterns
            if incomplete.lower() in pattern.lower()
        ]


class TestPatternParamType(FlexiblePatternParamType):
    """Alias for backward compatibility - redirects to FlexiblePatternParamType."""
