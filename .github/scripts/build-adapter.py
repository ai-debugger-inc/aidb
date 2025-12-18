#!/usr/bin/env python3
"""AIDB Adapter Build Orchestrator.

This is the entry point that uses the modular adapter build system.
"""

import argparse
import json
import sys
from pathlib import Path

# Add the scripts directory to path so we can import the adapters package
sys.path.insert(0, str(Path(__file__).parent))

from adapters import ADAPTER_BUILDERS, get_builder


def main():
    parser = argparse.ArgumentParser(description="Build AIDB debug adapters")
    parser.add_argument("adapter", nargs="?", help="Adapter to build (javascript, java)")
    parser.add_argument("--platform", help="Target platform (linux, darwin, windows)")
    parser.add_argument("--arch", help="Target architecture (x64, arm64)")
    parser.add_argument("--versions-file", default="versions.json",
                       help="Path to versions configuration file")
    parser.add_argument("--list", action="store_true", help="List available adapters")
    parser.add_argument("--validate-only", action="store_true",
                       help="Only validate configuration")

    args = parser.parse_args()

    try:
        # Load versions
        versions_file = Path(args.versions_file)
        if not versions_file.exists():
            print(f"Error: Versions file not found: {versions_file}", file=sys.stderr)
            sys.exit(1)

        with versions_file.open() as f:
            versions = json.load(f)

        # Handle list command
        if args.list:
            print("Available adapters:")
            for adapter in ADAPTER_BUILDERS.keys():
                print(f"  - {adapter}")
            return

        # Handle validate command
        if args.validate_only:
            print("Configuration validation passed")
            return

        # Require adapter argument
        if not args.adapter:
            parser.error("adapter argument is required unless using --list or --validate-only")

        # Determine platform/arch
        if args.platform and args.arch:
            platform_name, arch = args.platform, args.arch
        else:
            # Auto-detect
            import platform
            system = platform.system().lower()
            machine = platform.machine().lower()

            platform_map = {
                "darwin": "darwin",
                "linux": "linux",
                "windows": "windows",
            }
            arch_map = {
                "x86_64": "x64",
                "amd64": "x64",
                "arm64": "arm64",
                "aarch64": "arm64",
            }

            platform_name = platform_map.get(system, system)
            arch = arch_map.get(machine, machine)

        print(f"Building {args.adapter} for {platform_name}-{arch}")

        # Validate platform
        platform_valid = False
        for platform_config in versions.get("platforms", []):
            if (platform_config["platform"] == platform_name and
                platform_config["arch"] == arch):
                platform_valid = True
                break

        if not platform_valid:
            print(f"Error: Unsupported platform: {platform_name}-{arch}", file=sys.stderr)
            sys.exit(1)

        # Build adapter using new modular system
        builder = get_builder(args.adapter, versions, platform_name, arch)
        tarball_path, checksum = builder.build_adapter()

        print("Successfully built adapter:")
        print(f"  File: {tarball_path}")
        print(f"  Checksum: {checksum}")

        # Extract to cache directory for local development
        cache_dir = Path(".cache/adapters") / args.adapter
        cache_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting to cache: {cache_dir}")
        import tarfile
        with tarfile.open(tarball_path, "r:gz") as tar:
            # Extract directly to cache dir, stripping the top-level directory
            for member in tar.getmembers():
                # Skip the top-level directory itself
                parts = member.name.split("/", 1)
                if len(parts) > 1:
                    # Skip macOS resource fork files
                    if not parts[1].startswith("._") and "/._" not in parts[1]:
                        member.name = parts[1]
                        tar.extract(member, cache_dir)

        print(f"Adapter available at: {cache_dir}")

    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
