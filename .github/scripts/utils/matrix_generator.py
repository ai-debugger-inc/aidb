#!/usr/bin/env python3
"""Generate workflow matrix from versions.json.

This script generates the build matrix for both ACT and GHA workflows
from the central versions.json configuration file.
"""

import argparse
import json
import sys
from pathlib import Path


def load_versions(versions_file: str = "versions.json") -> dict:
    """Load versions configuration file.

    Parameters
    ----------
    versions_file : str
        Path to versions.json file

    Returns
    -------
    dict
        Parsed versions configuration
    """
    versions_path = Path(versions_file)
    if not versions_path.exists():
        print(f"Error: {versions_file} not found", file=sys.stderr)
        sys.exit(1)

    with versions_path.open() as f:
        return json.load(f)


def generate_matrix(workflow_type: str = "gha", versions_file: str = "versions.json") -> dict:
    """Generate workflow matrix from versions.json.

    Parameters
    ----------
    workflow_type : str
        Type of workflow ('act' or 'gha')
    versions_file : str
        Path to versions.json file

    Returns
    -------
    dict
        Matrix configuration for GitHub Actions
    """
    versions = load_versions(versions_file)

    # Start with basic matrix structure
    matrix = {
        "include": [],
    }

    # Get adapter configurations
    adapters = versions.get("adapters", {})

    # Get global platforms configuration
    global_platforms = versions.get("platforms", [])

    # Process each adapter
    for adapter_name, adapter_config in adapters.items():
        if not adapter_config.get("enabled", True):
            continue

        # Special handling for Java - it's universal
        if adapter_name == "java":
            # Java builds once for all platforms (universal binary)
            matrix["include"].append({
                "adapter": "java",
                "platform": "linux",
                "arch": "x64",
                "os": "ubuntu-latest" if workflow_type == "gha" else "ubuntu-latest",
            })
        else:
            # Use adapter-specific platforms if defined, otherwise use global platforms
            supported_platforms = adapter_config.get("platforms", global_platforms)

            # For ACT: only build for host platform
            if workflow_type == "act":
                import os
                import platform as py_platform

                # Check if we should use host platform (set via --use-host-platform flag)
                # Uses AIDB_ prefixed environment variables from centralized manager
                use_host = os.getenv("AIDB_USE_HOST_PLATFORM", "").lower() == "1"

                if use_host:
                    # Use actual host platform from centralized environment
                    host_platform = os.getenv("AIDB_BUILD_PLATFORM", "linux")
                    host_arch = os.getenv("AIDB_BUILD_ARCH", "x64")
                else:
                    # Default: detect container platform (which will be linux in ACT)
                    system = py_platform.system().lower()
                    machine = py_platform.machine().lower()

                    platform_map = {"darwin": "darwin", "linux": "linux", "windows": "windows"}
                    arch_map = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}

                    host_platform = platform_map.get(system, "linux")
                    host_arch = arch_map.get(machine, "x64")

                # Find matching platform entry
                for platform_entry in supported_platforms:
                    if (platform_entry["platform"] == host_platform and
                        platform_entry["arch"] == host_arch):
                        matrix["include"].append({
                            "adapter": adapter_name,
                            "platform": host_platform,
                            "arch": host_arch,
                            "os": "ubuntu-latest",
                        })
                        break
            else:
                # GHA: build for all platforms
                for platform_entry in supported_platforms:
                    os = platform_entry.get("os", "ubuntu-latest")
                    matrix["include"].append({
                        "adapter": adapter_name,
                        "platform": platform_entry["platform"],
                        "arch": platform_entry["arch"],
                        "os": os,
                    })

    return matrix


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate workflow matrix from versions.json",
    )
    parser.add_argument(
        "--workflow",
        choices=["act", "gha"],
        default="gha",
        help="Workflow type (act for local, gha for GitHub Actions)",
    )
    parser.add_argument(
        "--versions-file",
        default="versions.json",
        help="Path to versions.json file",
    )
    parser.add_argument(
        "--format",
        choices=["json", "github"],
        default="json",
        help="Output format (json or github for GITHUB_OUTPUT)",
    )

    args = parser.parse_args()

    try:
        matrix = generate_matrix(args.workflow, args.versions_file)

        if args.format == "github":
            # Format for GitHub Actions output
            matrix_json = json.dumps(matrix, separators=(",", ":"))
            print(f"matrix={matrix_json}")
        else:
            # Pretty print JSON
            print(json.dumps(matrix, indent=2))

    except Exception as e:
        print(f"Error generating matrix: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
