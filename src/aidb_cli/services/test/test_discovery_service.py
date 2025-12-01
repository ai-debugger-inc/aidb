"""Service for test discovery and metadata management."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb_cli.managers.base.service import BaseService
from aidb_common.config import VersionManager
from aidb_common.constants import Language
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


@dataclass
class TestSuiteMetadata:
    """Metadata for a test suite."""

    name: str
    path: Path
    languages: list[str]
    markers: list[str]
    requires_docker: bool
    adapters_required: bool
    default_pattern: str
    dependencies: list[str] | None = None

    def __post_init__(self) -> None:
        if self.dependencies is None:
            self.dependencies = []


class TestDiscoveryService(BaseService):
    """Service for discovering tests and managing test metadata.

    This service handles:
    - Test suite discovery and metadata loading
    - Test file discovery based on patterns
    - Marker-based test filtering
    - Language and suite filtering
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the test discovery service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance
        """
        super().__init__(repo_root, command_executor)
        self._suite_metadata: dict[str, TestSuiteMetadata] = {}
        self.test_root = repo_root / "src" / "tests"
        self._load_suite_metadata()

    def _load_suite_metadata(self) -> None:
        """Load metadata for all test suites based on conventions."""
        if not self.test_root.exists():
            logger.warning("Test root directory not found: %s", self.test_root)
            return

        # Get supported languages from versions.json
        from aidb_cli.core.paths import ProjectPaths

        version_manager = VersionManager(self.repo_root / ProjectPaths.VERSIONS_YAML)
        test_languages = self._extract_test_languages(version_manager)

        # Discover test suites
        for suite_dir in self.test_root.iterdir():
            if suite_dir.is_dir() and suite_dir.name.startswith("aidb_"):
                self._register_suite(suite_dir, test_languages)

        # Register special suites for integration testing
        self._register_special_suites()

    def _extract_test_languages(self, version_manager: VersionManager) -> list[str]:
        """Extract supported test languages from version configuration."""
        try:
            adapters = version_manager.versions.get("adapters", {})
            if adapters:
                return list(adapters.keys())
        except Exception as e:  # Fallback to defaults if adapter loading fails
            logger.debug("Using default languages, couldn't load adapters: %s", e)

        from aidb_cli.core.constants import SUPPORTED_LANGUAGES

        return SUPPORTED_LANGUAGES

    def _register_suite(self, suite_dir: Path, test_languages: list[str]) -> None:
        """Register a test suite with metadata."""
        from aidb_cli.services.test import TestSuites

        suite_name = suite_dir.name.split("aidb_", 1)[1]

        # Get suite definition from registry
        suite_def = TestSuites.get(suite_name)
        if not suite_def:
            logger.debug("Skipping unknown suite: %s", suite_name)
            return

        # Language support
        languages = (
            test_languages if suite_def.is_multilang else [Language.PYTHON.value]
        )

        # Common markers
        markers = ["unit", "integration"]
        if suite_def.is_multilang:
            markers.extend(["e2e", "multilang", "asyncio"])

        self._suite_metadata[suite_name] = TestSuiteMetadata(
            name=suite_def.name,
            path=suite_dir,
            languages=languages,
            markers=markers,
            requires_docker=suite_def.requires_docker,
            adapters_required=suite_def.adapters_required,
            default_pattern="test_*.py",
            dependencies=["adapters"] if suite_def.adapters_required else [],
        )

    def _register_special_suites(self) -> None:
        """Register special test suites that don't follow the aidb_ convention."""
        # Get supported languages from versions.json
        from aidb_cli.core.paths import ProjectPaths
        from aidb_cli.services.test import TestSuites

        version_manager = VersionManager(self.repo_root / ProjectPaths.VERSIONS_YAML)
        test_languages = self._extract_test_languages(version_manager)

        # Register non-aidb_ prefixed suites (ci_cd, frameworks, launch, core)
        # Note: "core" suite maps to "aidb/" directory
        suite_dir_mapping = {
            "ci_cd": "ci_cd",
            "frameworks": "frameworks",
            "launch": "launch",
            "core": "aidb",
        }

        for suite_name, dir_name in suite_dir_mapping.items():
            suite_dir = self.test_root / dir_name
            if suite_dir.exists():
                suite_def = TestSuites.get(suite_name)
                if suite_def:
                    languages = (
                        test_languages
                        if suite_def.is_multilang
                        else [Language.PYTHON.value]
                    )
                    markers = ["unit", "integration"]
                    if suite_def.is_multilang:
                        markers.extend(["e2e", "multilang", "asyncio"])

                    self._suite_metadata[suite_name] = TestSuiteMetadata(
                        name=suite_def.name,
                        path=suite_dir,
                        languages=languages,
                        markers=markers,
                        requires_docker=suite_def.requires_docker,
                        adapters_required=suite_def.adapters_required,
                        default_pattern="test_*.py",
                        dependencies=(
                            ["adapters"] if suite_def.adapters_required else []
                        ),
                    )

        # Register suite-level aggregations
        self._suite_metadata["unit"] = TestSuiteMetadata(
            name="unit",
            path=self.test_root,
            languages=[Language.PYTHON.value],
            markers=["unit"],
            requires_docker=False,
            adapters_required=False,
            default_pattern="test_*.py",
            dependencies=[],
        )

        self._suite_metadata["integration"] = TestSuiteMetadata(
            name="integration",
            path=self.test_root,
            languages=[Language.PYTHON.value],
            markers=["integration"],
            requires_docker=True,
            adapters_required=True,
            default_pattern="test_*.py",
            dependencies=[],
        )

    def get_suite_metadata(self, suite: str) -> TestSuiteMetadata | None:
        """Get metadata for a specific test suite."""
        return self._suite_metadata.get(suite)

    def get_all_suites(self) -> dict[str, TestSuiteMetadata]:
        """Get metadata for all test suites."""
        return self._suite_metadata.copy()

    def discover_tests(
        self,
        suite: str | None = None,
        language: str | None = None,
        marker: str | None = None,
        pattern: str | None = None,
    ) -> dict[str, list[Path]]:
        """Discover tests matching the given criteria.

        Parameters
        ----------
        suite : str, optional
            Test suite to filter by
        language : str, optional
            Language to filter by
        marker : str, optional
            Pytest marker to filter by
        pattern : str, optional
            File pattern to match

        Returns
        -------
        dict[str, list[Path]]
            Dictionary mapping suite names to list of test files
        """
        discovered: dict[str, list[Path]] = {}

        # Filter suites
        suites_to_check: list[str] = list(self._suite_metadata.keys())
        if suite:
            suites_to_check = [suite] if suite in self._suite_metadata else []

        for suite_name in suites_to_check:
            metadata = self._suite_metadata[suite_name]

            # Check language filter
            if language and language != "all" and language not in metadata.languages:
                continue

            # Discover test files
            test_files = self._discover_suite_files(metadata, pattern)

            # Apply marker filter
            if marker and test_files:
                test_files = self._filter_by_marker(test_files, marker)

            if test_files:
                discovered[suite_name] = test_files

        return discovered

    def _discover_suite_files(
        self,
        metadata: TestSuiteMetadata,
        pattern: str | None = None,
    ) -> list[Path]:
        """Discover test files for a suite."""
        pattern_to_use = pattern or metadata.default_pattern

        return list(metadata.path.rglob(pattern_to_use))

    def _filter_by_marker(self, test_files: list[Path], marker: str) -> list[Path]:
        """Filter test files by pytest marker."""
        filtered_files = []
        for test_file in test_files:
            try:
                content = test_file.read_text()
                # Simple marker detection
                if f"@pytest.mark.{marker}" in content or f"mark.{marker}" in content:
                    filtered_files.append(test_file)
            except OSError as e:
                logger.debug("Error reading %s for marker filter: %s", test_file, e)
        return filtered_files

    def get_test_statistics(self, suite: str | None = None) -> dict[str, Any]:
        """Get statistics about discovered tests."""
        discovered = self.discover_tests(suite=suite)
        stats: dict[str, Any] = {
            "total_suites": len(discovered),
            "total_files": sum(len(files) for files in discovered.values()),
            "suites": {},
        }

        for suite_name, files in discovered.items():
            stats["suites"][suite_name] = {
                "file_count": len(files),
                "metadata": self._suite_metadata.get(suite_name),
            }

        return stats
