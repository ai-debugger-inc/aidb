#!/usr/bin/env python3
"""CLI entry point for adapter build system."""

import argparse
import sys
from pathlib import Path

import yaml

from .registry import get_builder, list_adapters


def load_versions(versions_file: Path) -> dict:
    """Load and validate versions.yaml configuration.

    Parameters
    ----------
    versions_file : Path
        Path to versions.yaml file

    Returns
    -------
    dict
        Versions configuration

    Raises
    ------
    FileNotFoundError
        If versions file doesn't exist
    """
    if not versions_file.exists():
        raise FileNotFoundError(f"Versions file not found: {versions_file}")

    with open(versions_file) as f:
        versions = yaml.safe_load(f)

    # Validate required sections
    required_sections = ["adapters", "platforms"]
    for section in required_sections:
        if section not in versions:
            raise ValueError(
                f"Missing required section '{section}' in {versions_file}"
            )

    return versions


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build AIDB debug adapters"
    )

    # Adapter argument (positional)
    parser.add_argument(
        "adapter",
        nargs="?",
        help=f"Adapter to build ({', '.join(list_adapters())})"
    )

    # Platform and architecture
    parser.add_argument(
        "--platform",
        help="Target platform (linux, darwin, windows)"
    )
    parser.add_argument(
        "--arch",
        help="Target architecture (x64, arm64)"
    )

    # Versions file
    parser.add_argument(
        "--versions-file",
        default="versions.yaml",
        help="Path to versions configuration file"
    )

    # Actions
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available adapters"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate configuration"
    )

    args = parser.parse_args()

    try:
        # Load versions configuration
        versions_file = Path(args.versions_file)
        versions = load_versions(versions_file)

        # Handle list action
        if args.list:
            print("Available adapters:")
            for adapter in list_adapters():
                if adapter in versions.get("adapters", {}):
                    version = versions["adapters"][adapter].get("version", "unknown")
                    print(f"  - {adapter} (version: {version})")
                else:
                    print(f"  - {adapter} (not configured)")
            return 0

        # Handle validate action
        if args.validate_only:
            print("Configuration validation passed")
            return 0

        # Require adapter for build
        if not args.adapter:
            parser.error(
                "adapter argument is required unless using --list or --validate-only"
            )

        # Get platform/arch
        if args.platform and args.arch:
            platform_name = args.platform
            arch = args.arch
        else:
            # Auto-detect current platform
            import platform
            system = platform.system().lower()
            machine = platform.machine().lower()

            platform_map = {
                "darwin": "darwin",
                "linux": "linux",
                "windows": "windows"
            }
            arch_map = {
                "x86_64": "x64",
                "amd64": "x64",
                "arm64": "arm64",
                "aarch64": "arm64"
            }

            platform_name = platform_map.get(system, system)
            arch = arch_map.get(machine, machine)

        print(f"Building {args.adapter} for {platform_name}-{arch}")

        # Get builder and build
        builder = get_builder(args.adapter, versions, platform_name, arch)
        tarball_path, checksum = builder.build_adapter()

        print(f"\nSuccessfully built adapter:")
        print(f"  File: {tarball_path}")
        print(f"  Checksum: {checksum}")

        return 0

    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())