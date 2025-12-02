#!/usr/bin/env python3
"""Generate adapter manifest.json from versions.json.

This script creates a manifest.json file that describes all available adapters
and their supported platforms. It reads configuration from versions.json and
generates a consolidated manifest for release artifacts.

Usage:
    python generate_manifest.py --version 0.0.4 --output consolidated-adapters/manifest.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metadata import load_versions_config


def generate_manifest(version: str, versions_config: dict[str, Any]) -> dict[str, Any]:
    """Generate adapter manifest from versions.json configuration.

    Parameters
    ----------
    version : str
        The AIDB version for this manifest
    versions_config : dict[str, Any]
        Parsed versions.json content

    Returns
    -------
    dict[str, Any]
        Manifest dictionary ready for JSON serialization
    """
    manifest: dict[str, Any] = {
        "version": version,
        "build_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adapters": {},
    }

    # Platforms are defined at root level, not per-adapter
    all_platforms = versions_config.get("platforms", [])

    for adapter_name, adapter_config in versions_config.get("adapters", {}).items():
        if not adapter_config.get("enabled", True):
            continue

        # Check if adapter is universal (platform-independent like Java JARs)
        if adapter_config.get("universal", False):
            platforms = ["universal"]
        else:
            # Non-universal adapters are built for all platforms
            platforms = [f"{p['platform']}-{p['arch']}" for p in all_platforms]

        manifest["adapters"][adapter_name] = {
            "version": adapter_config["version"],
            "platforms": platforms,
        }

    return manifest


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate adapter manifest.json from versions.json",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="AIDB version for the manifest",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for manifest.json",
    )
    parser.add_argument(
        "--versions-file",
        type=Path,
        default=None,
        help="Path to versions.json (default: auto-detect from project root)",
    )

    args = parser.parse_args()

    # Load versions.json
    if args.versions_file:
        with args.versions_file.open() as f:
            versions_config = json.load(f)
    else:
        versions_config = load_versions_config()

    # Generate manifest
    manifest = generate_manifest(args.version, versions_config)

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Write manifest
    with args.output.open("w") as f:
        json.dump(manifest, f, indent=2)

    print("Generated manifest:")
    print(json.dumps(manifest, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
