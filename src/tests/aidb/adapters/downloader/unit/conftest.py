"""Fixtures for adapter downloader unit tests."""

import json
import tarfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Import shared unit test fixtures
from tests._fixtures.unit.context import mock_ctx  # noqa: F401


@pytest.fixture
def mock_versions_config() -> dict[str, Any]:
    """Sample versions.json content."""
    return {
        "version": "0.0.5",
        "adapters": {
            "python": {
                "version": "1.8.16",
                "repo": "microsoft/debugpy",
                "universal": False,
            },
            "javascript": {
                "version": "1.96.0",
                "repo": "microsoft/vscode-js-debug",
                "universal": False,
            },
            "java": {
                "version": "0.58.1",
                "repo": "microsoft/java-debug",
                "universal": True,
            },
        },
    }


@pytest.fixture
def mock_release_manifest() -> dict[str, Any]:
    """Sample manifest.json from GitHub release."""
    return {
        "release_version": "0.0.5",
        "adapters": {
            "python": {
                "version": "1.8.16",
                "platforms": ["darwin-arm64", "darwin-x64", "linux-x64"],
            },
            "javascript": {
                "version": "1.96.0",
                "platforms": ["darwin-arm64", "darwin-x64", "linux-x64"],
            },
            "java": {
                "version": "0.58.1",
                "platforms": ["universal"],
            },
        },
    }


@pytest.fixture
def tmp_install_dir(tmp_path: Path) -> Path:
    """Temporary directory for adapter installation."""
    install_dir = tmp_path / "adapters"
    install_dir.mkdir(parents=True, exist_ok=True)
    return install_dir


@pytest.fixture
def sample_metadata() -> dict[str, Any]:
    """Sample adapter metadata.json content."""
    return {
        "adapter_name": "python",
        "adapter_version": "1.8.16",
        "aidb_version": "0.0.5",
        "platform": "darwin",
        "arch": "arm64",
        "binary_identifier": "debugpy",
        "repo": "microsoft/debugpy",
    }


@pytest.fixture
def sample_tarball(tmp_path: Path, sample_metadata: dict[str, Any]) -> Path:
    """Create a real tarball with valid metadata.json for extraction tests."""
    # Create content directory
    content_dir = tmp_path / "tarball_content"
    content_dir.mkdir()

    # Write metadata.json
    metadata_file = content_dir / "metadata.json"
    metadata_file.write_text(json.dumps(sample_metadata))

    # Create a dummy file to simulate adapter binary
    dummy_bin = content_dir / "debugpy"
    dummy_bin.write_text("dummy binary content")

    # Create tarball
    tarball_path = tmp_path / "adapter.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(metadata_file, arcname="metadata.json")
        tar.add(dummy_bin, arcname="debugpy")

    return tarball_path


@pytest.fixture
def sample_tarball_nested(tmp_path: Path, sample_metadata: dict[str, Any]) -> Path:
    """Create a tarball with nested directory structure."""
    # Create content directory with nesting
    content_dir = tmp_path / "tarball_content_nested" / "python-1.8.16"
    content_dir.mkdir(parents=True)

    # Write metadata.json inside nested dir
    metadata_file = content_dir / "metadata.json"
    metadata_file.write_text(json.dumps(sample_metadata))

    # Create tarball with nested structure
    tarball_path = tmp_path / "adapter_nested.tar.gz"
    with tarfile.open(tarball_path, "w:gz") as tar:
        tar.add(content_dir.parent, arcname="python-1.8.16")

    return tarball_path


@pytest.fixture
def mock_adapter_class() -> MagicMock:
    """Mock adapter class for registry."""
    mock_class = MagicMock()
    mock_class.__name__ = "PythonAdapter"
    return mock_class


@pytest.fixture
def mock_urlopen_response() -> MagicMock:
    """Mock response for urlopen context manager."""
    mock_response = MagicMock()
    mock_response.read.return_value = b"mock tarball content"
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


@pytest.fixture
def mock_urlopen_json_response(mock_release_manifest: dict[str, Any]) -> MagicMock:
    """Mock JSON response for urlopen (manifest fetch)."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_release_manifest).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response
