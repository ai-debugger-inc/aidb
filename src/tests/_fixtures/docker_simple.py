"""Simplified Docker fixtures for AIDB test suite."""

__all__ = [
    # Constants
    "IN_DOCKER",
    # Fixtures
    "docker_test_mode",
    "docker_workspace",
    "test_language",
    "test_profile",
    "adapter_version",
    "skip_if_not_docker",
    "skip_if_docker",
    "require_language",
    "docker_helper",
    # Classes
    "DockerTestHelper",
]

import logging
import os
import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Optional

import pytest

logger = logging.getLogger(__name__)

# Check if we're running in Docker test mode
IN_DOCKER = os.environ.get("AIDB_DOCKER_TEST_MODE") == "1"


@pytest.fixture
def docker_test_mode() -> bool:
    """Check if tests are running in Docker container.

    Returns
    -------
    bool
        True if running in Docker test mode
    """
    return IN_DOCKER


@pytest.fixture
def docker_workspace() -> Path | None:
    """Get Docker workspace path if in container.

    Returns
    -------
    Optional[Path]
        Workspace path if in Docker, None otherwise
    """
    if IN_DOCKER:
        return Path("/workspace")
    return None


@pytest.fixture
def test_language() -> str | None:
    """Get current test language from environment.

    Returns
    -------
    Optional[str]
        Language being tested (python, javascript, etc.) or None
    """
    lang = os.environ.get("TEST_LANGUAGE", "all")
    return None if lang == "all" else lang


@pytest.fixture
def test_profile() -> str:
    """Get current test profile.

    Returns
    -------
    str
        Test profile (quick, full, comprehensive)
    """
    return os.environ.get("TEST_PROFILE", "quick")


@pytest.fixture
def adapter_version() -> str:
    """Get adapter version being tested.

    Returns
    -------
    str
        Adapter version or 'default'
    """
    return os.environ.get("TEST_ADAPTER_VERSION", "default")


@pytest.fixture
def skip_if_not_docker(docker_test_mode):
    """Skip test if not running in Docker.

    Parameters
    ----------
    docker_test_mode : bool
        Whether in Docker test mode
    """
    if not docker_test_mode:
        pytest.skip("Test requires Docker environment")


@pytest.fixture
def skip_if_docker(docker_test_mode):
    """Skip test if running in Docker.

    Parameters
    ----------
    docker_test_mode : bool
        Whether in Docker test mode
    """
    if docker_test_mode:
        pytest.skip("Test should not run in Docker")


@pytest.fixture
def require_language(test_language):
    """Require specific language in factory fixture.

    Parameters
    ----------
    test_language : Optional[str]
        Current test language

    Returns
    -------
    callable
        Function to check language requirement
    """

    def _require(lang: str):
        if test_language and test_language != lang:
            pytest.skip(f"Test requires {lang}, currently testing {test_language}")

    return _require


class DockerTestHelper:
    """Simple helper for Docker-aware tests."""

    def __init__(self):
        """Initialize Docker test helper."""
        self.in_docker = IN_DOCKER
        self.workspace = Path("/workspace") if IN_DOCKER else Path.cwd()
        self.test_language = os.environ.get("TEST_LANGUAGE", "all")
        self.test_profile = os.environ.get("TEST_PROFILE", "quick")

    def setup_test_env(self) -> dict[str, str | None]:
        """Set up environment for testing.

        Returns
        -------
        Dict[str, str]
            Original environment variables (for restoration)
        """
        return {}

        # Set up test environment variables if needed
        # (Currently no special setup required since we don't download binaries)

    def restore_environment(self, original_env: dict[str, str | None]) -> None:
        """Restore original environment variables.

        Parameters
        ----------
        original_env : Dict[str, str]
            Original environment to restore
        """
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def get_test_file_path(self, filename: str) -> Path:
        """Get path to test file, accounting for Docker mount.

        Parameters
        ----------
        filename : str
            Name of test file

        Returns
        -------
        Path
            Full path to test file
        """
        if self.in_docker:
            return self.workspace / "src" / "tests" / "fixtures" / "files" / filename
        return Path(__file__).parent / "files" / filename

    def get_adapter_command(self, language: str) -> str:
        """Get debug adapter command for language.

        Parameters
        ----------
        language : str
            Programming language

        Returns
        -------
        str
            Command to run debug adapter
        """
        commands = {
            "python": "python -m debugpy",
            "javascript": "node --inspect",
            "java": "java -agentlib:jdwp=transport=dt_socket,server=y,suspend=n",
            "go": "dlv debug",
            "rust": "rust-lldb",
            "ruby": "rdbg",
            "php": "php -dxdebug.mode=debug",
            "dotnet": "dotnet vsdbg",
        }
        return commands.get(language, "")

    def should_skip_language(self, language: str) -> bool:
        """Check if language should be skipped.

        Parameters
        ----------
        language : str
            Language to check

        Returns
        -------
        bool
            True if should skip
        """
        if self.test_language == "all":
            return False
        return self.test_language != language

    def get_profile_timeout(self) -> int:
        """Get test timeout based on profile.

        Returns
        -------
        int
            Timeout in seconds
        """
        timeouts = {
            "quick": 30,
            "full": 60,
            "comprehensive": 120,
        }
        return timeouts.get(self.test_profile, 30)


@pytest.fixture
def docker_helper() -> DockerTestHelper:
    """Provide Docker test helper.

    Returns
    -------
    DockerTestHelper
        Helper instance
    """
    return DockerTestHelper()


# Markers for Docker tests
def pytest_configure(config):
    """Configure pytest with Docker markers."""
    config.addinivalue_line(
        "markers",
        "docker_only: mark test to run only in Docker environment",
    )
    config.addinivalue_line(
        "markers",
        "skip_docker: mark test to skip in Docker environment",
    )
    config.addinivalue_line(
        "markers",
        "require_language(lang): mark test to run only for specific language",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running (downloads, builds, etc.)",
    )


def pytest_runtest_setup(item):
    """Check Docker markers before running test."""
    # Check docker_only marker
    if item.get_closest_marker("docker_only") and not IN_DOCKER:
        pytest.skip("Test requires Docker environment")

    # Check skip_docker marker
    if item.get_closest_marker("skip_docker") and IN_DOCKER:
        pytest.skip("Test should not run in Docker")

    # Check require_language marker
    marker = item.get_closest_marker("require_language")
    if marker:
        required_lang = marker.args[0]
        current_lang = os.environ.get("TEST_LANGUAGE", "all")
        if current_lang != "all" and current_lang != required_lang:
            pytest.skip(
                f"Test requires {required_lang}, currently testing {current_lang}",
            )
