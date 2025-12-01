"""Reusable adapter metadata helper for consistent metadata.json generation.

This module provides utilities for creating uniform metadata.json files across
all adapter builds, ensuring consistency and enabling version compatibility
tracking.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class AdapterMetadata:
    """Structured adapter metadata container.

    Attributes
    ----------
    adapter_name : str
        Name of the adapter (e.g., "javascript", "java")
    adapter_version : str
        Version of the upstream adapter (from versions.yaml)
    aidb_version : str
        Version of aidb that built this adapter
    platform : str
        Target platform (e.g., "darwin", "linux", "windows", "universal")
    arch : str
        Target architecture (e.g., "x64", "arm64")
    build_date : str
        ISO timestamp when adapter was built
    binary_identifier : str
        Filename of the main adapter binary (e.g., "dapDebugServer.js")
    repo : str
        Source repository for the adapter (e.g., "microsoft/vscode-js-debug")
    """
    adapter_name: str
    adapter_version: str
    aidb_version: str
    platform: str
    arch: str
    build_date: str
    binary_identifier: str
    repo: str


def get_project_root() -> Path:
    """Find the project root directory containing versions.yaml.

    Returns
    -------
    Path
        Path to the project root directory

    Raises
    ------
    FileNotFoundError
        If versions.yaml cannot be found
    """
    current = Path(__file__)

    # Walk up the directory tree looking for versions.yaml
    for parent in current.parents:
        versions_file = parent / "versions.yaml"
        if versions_file.exists():
            return parent

    raise FileNotFoundError("Could not locate project root with versions.yaml")


def load_versions_config() -> dict:
    """Load versions.yaml configuration.

    Returns
    -------
    dict[str, Any]
        Parsed versions.yaml content

    Raises
    ------
    FileNotFoundError
        If versions.yaml cannot be found
    yaml.YAMLError
        If versions.yaml cannot be parsed
    """
    project_root = get_project_root()
    versions_file = project_root / "versions.yaml"

    with open(versions_file) as f:
        return yaml.safe_load(f)


def create_metadata(
    adapter_name: str,
    platform: str,
    arch: str,
    binary_identifier: Optional[str] = None,
) -> AdapterMetadata:
    """Create adapter metadata from versions.yaml and runtime info.

    Parameters
    ----------
    adapter_name : str
        Name of the adapter (must exist in versions.yaml)
    platform : str
        Target platform (e.g., "darwin", "linux", "windows", "universal")
    arch : str
        Target architecture (e.g., "x64", "arm64")
    binary_identifier : str, optional
        Override the binary identifier from config

    Returns
    -------
    AdapterMetadata
        Structured metadata for the adapter

    Raises
    ------
    KeyError
        If adapter not found in versions.yaml
    ValueError
        If required configuration is missing
    """
    versions = load_versions_config()

    # Get adapter configuration
    adapter_config = versions.get("adapters", {}).get(adapter_name)
    if not adapter_config:
        raise KeyError(f"Adapter '{adapter_name}' not found in versions.yaml")

    # Get adapter version and repo
    adapter_version = adapter_config.get("version")
    repo = adapter_config.get("repo")

    if not adapter_version:
        raise ValueError(f"No version specified for adapter '{adapter_name}'")
    if not repo:
        raise ValueError(f"No repo specified for adapter '{adapter_name}'")

    # Get AIDB version
    aidb_version = versions.get("version", "0.0.0")

    # Use provided binary_identifier or try to get from adapter registry
    if not binary_identifier:
        # Try to get binary_identifier from adapter config
        try:
            # Import here to avoid circular dependencies and allow use in build scripts
            import sys
            from pathlib import Path

            # Add the project src path to allow imports
            project_root = get_project_root()
            src_path = project_root / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from aidb.session.adapter_registry import AdapterRegistry

            # Create registry and try to get adapter config
            registry = AdapterRegistry()
            adapter_config = registry.get_adapter_config(adapter_name)
            binary_identifier = adapter_config.binary_identifier

            if not binary_identifier:
                raise ValueError(
                    f"Adapter '{adapter_name}' config has no binary_identifier"
                )

        except Exception:
            # Fallback: if registry isn't available (e.g., during build),
            # use hardcoded defaults as last resort
            default_binaries = {
                "javascript": "dapDebugServer.js",
                "java": "java-debug.jar",
            }
            binary_identifier = default_binaries.get(adapter_name)
            if not binary_identifier:
                raise ValueError(
                    f"No binary_identifier provided and cannot infer for adapter '{adapter_name}'"
                )

    # Generate build timestamp
    build_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    return AdapterMetadata(
        adapter_name=adapter_name,
        adapter_version=str(adapter_version),
        aidb_version=str(aidb_version),
        platform=platform,
        arch=arch,
        build_date=build_date,
        binary_identifier=binary_identifier,
        repo=repo,
    )


def write_metadata_json(metadata: AdapterMetadata, output_path: Path) -> None:
    """Write adapter metadata to a JSON file.

    Parameters
    ----------
    metadata : AdapterMetadata
        Structured metadata to write
    output_path : Path
        Path where to write metadata.json
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert dataclass to dict and write as JSON
    metadata_dict = asdict(metadata)
    with open(output_path, "w") as f:
        json.dump(metadata_dict, f, indent=2)


def create_and_write_metadata(
    adapter_name: str,
    platform: str,
    arch: str,
    output_directory: Path,
    binary_identifier: Optional[str] = None,
) -> AdapterMetadata:
    """Convenience function to create and write metadata.json in one step.

    Parameters
    ----------
    adapter_name : str
        Name of the adapter (must exist in versions.yaml)
    platform : str
        Target platform (e.g., "darwin", "linux", "windows", "universal")
    arch : str
        Target architecture (e.g., "x64", "arm64")
    output_directory : Path
        Directory where to write metadata.json
    binary_identifier : str, optional
        Override the binary identifier from config

    Returns
    -------
    AdapterMetadata
        The created metadata for reference
    """
    metadata = create_metadata(adapter_name, platform, arch, binary_identifier)
    metadata_path = output_directory / "metadata.json"
    write_metadata_json(metadata, metadata_path)

    print(f"Created metadata.json for {adapter_name} adapter")
    print(f"  Adapter version: {metadata.adapter_version}")
    print(f"  AIDB version: {metadata.aidb_version}")
    print(f"  Platform: {metadata.platform}-{metadata.arch}")
    print(f"  Binary: {metadata.binary_identifier}")

    return metadata