"""Shared fixtures for CI/CD tests."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

# Add paths for importing CI scripts (must be at module level for import resolution)
sys.path.insert(0, str(Path(__file__).parent / "unit"))
_scripts_path = Path(__file__).parent.parent.parent.parent / ".github" / "scripts"
if str(_scripts_path) not in sys.path:
    sys.path.insert(0, str(_scripts_path))


@pytest.fixture
def repo_root():
    """Return repository root path."""
    return Path(__file__).parent.parent.parent.parent


@pytest.fixture
def github_dir(repo_root):
    """Return .github directory path."""
    return repo_root / ".github"


@pytest.fixture
def scripts_dir(github_dir):
    """Return .github/scripts directory path."""
    return github_dir / "scripts"


@pytest.fixture
def workflows_dir(github_dir):
    """Return .github/workflows directory path."""
    return github_dir / "workflows"


@pytest.fixture
def versions_json(repo_root):
    """Load versions.json configuration."""
    versions_path = repo_root / "versions.json"
    with versions_path.open() as f:
        return json.load(f)


@pytest.fixture
def testing_config_yaml(github_dir):
    """Load testing-config.yaml configuration."""
    config_path = github_dir / "testing-config.yaml"
    with config_path.open() as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_capability_data():
    """Mock adapter capability data."""
    return {
        "adapters": {
            "python": {
                "supports_conditional_breakpoints": True,
                "supports_logpoints": True,
                "supports_hit_condition": True,
                "default_port": 5678,
            },
            "javascript": {
                "supports_conditional_breakpoints": True,
                "supports_logpoints": True,
                "supports_hit_condition": False,
                "default_port": 9229,
            },
            "java": {
                "supports_conditional_breakpoints": True,
                "supports_logpoints": False,
                "supports_hit_condition": True,
                "default_port": 5005,
            },
        },
    }


@pytest.fixture
def mock_release_data():
    """Mock GitHub release data with dynamic dates.

    Returns release data with dates relative to now:
    - v1.8.0: 30 days ago (within typical lookback window)
    - v1.7.0: 60 days ago (outside short lookback windows)
    - v1.9.0-beta: 15 days ago (recent prerelease)
    """
    now = datetime.now(timezone.utc)

    return [
        {
            "tag_name": "v1.8.0",
            "published_at": (now - timedelta(days=30)).isoformat(),
            "prerelease": False,
            "draft": False,
            "body": "Added support for conditional breakpoints with complex expressions",
            "html_url": "https://github.com/microsoft/debugpy/releases/tag/v1.8.0",
        },
        {
            "tag_name": "v1.7.0",
            "published_at": (now - timedelta(days=60)).isoformat(),
            "prerelease": False,
            "draft": False,
            "body": "Bug fixes and performance improvements",
            "html_url": "https://github.com/microsoft/debugpy/releases/tag/v1.7.0",
        },
        {
            "tag_name": "v1.9.0-beta",
            "published_at": (now - timedelta(days=15)).isoformat(),
            "prerelease": True,
            "draft": False,
            "body": "Beta release with experimental features",
            "html_url": "https://github.com/microsoft/debugpy/releases/tag/v1.9.0-beta",
        },
    ]


@pytest.fixture
def mock_anthropic_response():
    """Mock Anthropic API response."""
    return {
        "new_features_detected": [
            {
                "feature": "Enhanced conditional breakpoint expressions",
                "severity": "medium",
                "description": "Adapter now supports more complex conditional expressions",
                "recommendation": "Consider updating AIDB to support enhanced expressions",
                "affected_version": "v1.8.0",
            },
        ],
        "deprecated_features": [],
        "breaking_changes": [],
    }


@pytest.fixture
def mock_github_api_rate_limit(responses):
    """Mock GitHub API rate limit endpoint."""
    import responses as responses_lib

    responses_lib.add(
        responses_lib.GET,
        "https://api.github.com/rate_limit",
        json={"resources": {"core": {"remaining": 100, "reset": 9999999999}}},
        status=200,
    )


@pytest.fixture
def mock_ci_environment(monkeypatch):
    """Set up mock CI environment variables."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-12345")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("CI", "true")
    return
    # Cleanup handled by monkeypatch


@pytest.fixture
def temp_versions_json(tmp_path):
    """Create a temporary versions.json file for testing."""
    versions_file = tmp_path / "versions.json"
    config = {
        "version": "1.0.0",
        "infrastructure": {
            "python": {"version": "3.11.0"},
            "node": {"version": "20.0.0"},
            "java": {"version": "21.0.0"},
        },
        "adapters": {
            "python": {"version": "1.8.0", "debugpy_version": "1.8.0"},
            "javascript": {"version": "1.85.0"},
            "java": {"version": "0.50.0"},
        },
    }

    with versions_file.open("w") as f:
        json.dump(config, f, indent=2)

    return versions_file


@pytest.fixture
def mock_version_info():
    """Mock version information from endoflife.date API."""
    return {
        "version": "3.12.1",
        "type": "stable",
        "end_of_life": "2028-10-31",
        "notes": "Latest stable version",
    }


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for HTTP tests."""
    from unittest.mock import patch

    with patch("requests.get") as mock:
        yield mock


@pytest.fixture
def mock_source_class():
    """Create a generic mock source class instance."""
    from unittest.mock import Mock

    mock_class = Mock()
    mock_instance = mock_class.return_value
    mock_instance.fetch_latest_version.return_value = "1.2.3"
    return mock_class


@pytest.fixture
def mock_checker_stack():
    """Mock all checkers and loader for orchestrator tests.

    Returns a dict with mocked classes and instances.
    This eliminates the need for 6 @patch decorators in orchestrator tests.

    Usage:
        def test_something(self, mock_checker_stack):
            # Access instances for setting return values
            mock_checker_stack['loader'].load.return_value = {...}
            mock_checker_stack['infra'].check_updates.return_value = {...}

            # Access classes for assertion (e.g., checking if initialized)
            mock_checker_stack['infra_class'].assert_called_once()
    """
    from unittest.mock import Mock, patch

    # Start all patches
    loader_patch = patch("version_management.orchestrator.ConfigLoader")
    infra_patch = patch("version_management.orchestrator.InfrastructureChecker")
    adapter_patch = patch("version_management.orchestrator.AdapterChecker")
    package_patch = patch("version_management.orchestrator.PackageChecker")
    validator_patch = patch("version_management.orchestrator.DebugpySyncValidator")

    mock_loader_class = loader_patch.start()
    mock_infra_class = infra_patch.start()
    mock_adapter_class = adapter_patch.start()
    mock_package_class = package_patch.start()
    mock_validator_class = validator_patch.start()

    # Create return instances
    instances = {
        "loader": Mock(),
        "infra": Mock(),
        "adapter": Mock(),
        "package": Mock(),
        "validator": Mock(),
        # Also expose class mocks for assertions
        "loader_class": mock_loader_class,
        "infra_class": mock_infra_class,
        "adapter_class": mock_adapter_class,
        "package_class": mock_package_class,
        "validator_class": mock_validator_class,
    }

    # Set up class mocks to return instances
    mock_loader_class.return_value = instances["loader"]
    mock_infra_class.return_value = instances["infra"]
    mock_adapter_class.return_value = instances["adapter"]
    mock_package_class.return_value = instances["package"]
    mock_validator_class.return_value = instances["validator"]

    # Also make the loader.load static method accessible
    mock_loader_class.load = instances["loader"].load

    yield instances

    # Cleanup
    loader_patch.stop()
    infra_patch.stop()
    adapter_patch.stop()
    package_patch.stop()
    validator_patch.stop()
