"""Test suite definitions and registry."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SuiteDefinition:
    """Test suite definition with metadata.

    Parameters
    ----------
    name : str
        Suite name
    path : str
        Relative path from src/tests/
    is_multilang : bool
        Whether suite requires multi-language execution
    requires_docker : bool
        Whether suite requires Docker environment
    adapters_required : bool
        Whether suite requires debug adapters
    profile : str | None
        Docker profile to use (None for local-only suites)
    description : str
        Suite description
    coverage_module : str
        Python module name for coverage reporting (e.g., aidb, aidb_cli)
    """

    name: str
    path: str
    is_multilang: bool
    requires_docker: bool
    adapters_required: bool
    profile: str | None
    description: str
    coverage_module: str = "aidb"  # Default to core module


class TestSuites:
    """Centralized test suite definitions."""

    # Multi-language suites (require parallel lang-specific containers)
    SHARED = SuiteDefinition(
        name="shared",
        path="aidb_shared/",
        is_multilang=True,
        requires_docker=True,
        adapters_required=True,
        profile="base",
        description="Shared integration tests across all languages",
    )

    MCP = SuiteDefinition(
        name="mcp",
        path="aidb_mcp/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile=None,
        description="MCP server unit and integration tests",
        coverage_module="aidb_mcp",
    )

    FRAMEWORKS = SuiteDefinition(
        name="frameworks",
        path="frameworks/",
        is_multilang=True,
        requires_docker=True,
        adapters_required=True,
        profile="frameworks",
        description="Framework-specific debugging tests",
    )

    LAUNCH = SuiteDefinition(
        name="launch",
        path="launch/",
        is_multilang=True,
        requires_docker=True,
        adapters_required=True,
        profile="launch",
        description="Launch configuration parsing tests across all languages",
    )

    # Python-only suites
    CORE = SuiteDefinition(
        name="core",
        path="aidb/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=True,
        profile="base",
        description="Core aidb package tests (API, DAP, session)",
    )

    CLI = SuiteDefinition(
        name="cli",
        path="aidb_cli/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile="base",
        description="CLI tool tests",
        coverage_module="aidb_cli",
    )

    COMMON = SuiteDefinition(
        name="common",
        path="aidb_common/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile="base",
        description="Common utilities tests",
        coverage_module="aidb_common",
    )

    LOGGING = SuiteDefinition(
        name="logging",
        path="aidb_logging/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile="base",
        description="Logging framework tests",
        coverage_module="aidb_logging",
    )

    CI_CD = SuiteDefinition(
        name="ci_cd",
        path="ci_cd/",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile="base",
        description="CI/CD workflow and script tests",
        coverage_module="aidb_cli",  # CI/CD tests focus on CLI infrastructure
    )

    BASE = SuiteDefinition(
        name="base",
        path="",
        is_multilang=False,
        requires_docker=False,
        adapters_required=False,
        profile="base",
        description="All Python-only tests (CLI, common, logging, core)",
    )

    @classmethod
    def get(cls, name: str) -> SuiteDefinition | None:
        """Get suite definition by name.

        Parameters
        ----------
        name : str
            Suite name

        Returns
        -------
        SuiteDefinition or None
            Suite definition if found
        """
        for attr in dir(cls):
            if not attr.startswith("_") and attr.isupper():
                suite = getattr(cls, attr)
                if isinstance(suite, SuiteDefinition) and suite.name == name:
                    return suite
        return None

    @classmethod
    def get_multilang_suites(cls) -> list[SuiteDefinition]:
        """Get all multi-language suites.

        Returns
        -------
        list[SuiteDefinition]
            List of multi-language suite definitions
        """
        return [s for s in cls.all() if s.is_multilang]

    @classmethod
    def get_python_only_suites(cls) -> list[SuiteDefinition]:
        """Get all Python-only suites.

        Returns
        -------
        list[SuiteDefinition]
            List of Python-only suite definitions
        """
        return [s for s in cls.all() if not s.is_multilang]

    @classmethod
    def all(cls) -> list[SuiteDefinition]:
        """Get all suite definitions.

        Returns
        -------
        list[SuiteDefinition]
            List of all suite definitions
        """
        suites = []
        for attr in dir(cls):
            if not attr.startswith("_") and attr.isupper():
                suite = getattr(cls, attr)
                if isinstance(suite, SuiteDefinition):
                    suites.append(suite)
        return suites
