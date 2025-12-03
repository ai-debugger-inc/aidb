#!/usr/bin/env python3
"""Extract adapter build configuration from versions.json.

This script reads adapter build dependencies from versions.json and writes them
to either GITHUB_OUTPUT (for step outputs) or GITHUB_ENV (for environment variables).

Usage:
    # Write to GITHUB_OUTPUT (default)
    python extract_build_config.py --adapter javascript

    # Write to GITHUB_ENV
    python extract_build_config.py --adapter java --output-mode env

    # Explicit versions file
    python extract_build_config.py --adapter python --versions-file versions.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

from metadata import load_versions_config


def extract_build_config(
    adapter: str,
    versions_config: dict,
    output_mode: str = "output",
) -> dict[str, str]:
    """Extract build configuration for an adapter.

    Parameters
    ----------
    adapter : str
        Adapter name (javascript, java, python)
    versions_config : dict
        Parsed versions.json content
    output_mode : str
        Either "output" (GITHUB_OUTPUT) or "env" (GITHUB_ENV)

    Returns
    -------
    dict[str, str]
        Key-value pairs to write to GitHub Actions
    """
    config = versions_config.get("adapters", {}).get(adapter)
    if not config:
        print(f"::error::Adapter '{adapter}' not found in versions.json")
        sys.exit(1)

    build_deps = config.get("build_deps", {})
    outputs: dict[str, str] = {}

    # Use uppercase for env vars, lowercase for step outputs
    use_uppercase = output_mode == "env"

    if adapter == "javascript":
        node_version = build_deps.get("node_version", "18")
        key = "NODE_VERSION" if use_uppercase else "node_version"
        outputs[key] = node_version

    elif adapter == "java":
        java_version = build_deps.get("java_version", "21")
        java_distribution = build_deps.get("java_distribution", "temurin")
        maven_opts = build_deps.get("maven_opts", "")

        if use_uppercase:
            outputs["JAVA_VERSION"] = java_version
            outputs["JAVA_DISTRIBUTION"] = java_distribution
            outputs["MAVEN_OPTS"] = maven_opts
        else:
            outputs["java_version"] = java_version
            outputs["java_distribution"] = java_distribution
            outputs["maven_opts"] = maven_opts

    elif adapter == "python":
        python_version = build_deps.get("python_version", "3.12")
        key = "PYTHON_VERSION" if use_uppercase else "python_version"
        outputs[key] = python_version

    return outputs


def write_github_outputs(outputs: dict[str, str], output_mode: str) -> None:
    """Write outputs to GitHub Actions output or environment file.

    Parameters
    ----------
    outputs : dict[str, str]
        Key-value pairs to write
    output_mode : str
        Either "output" (GITHUB_OUTPUT) or "env" (GITHUB_ENV)
    """
    env_var = "GITHUB_OUTPUT" if output_mode == "output" else "GITHUB_ENV"
    github_file = os.environ.get(env_var)

    if not github_file:
        # Not running in GitHub Actions - just print
        print(f"Would write to ${env_var}:")
        for key, value in outputs.items():
            print(f"  {key}={value}")
        return

    with Path(github_file).open("a") as f:
        for key, value in outputs.items():
            f.write(f"{key}={value}\n")

    # Also print for visibility in logs
    print("Extracted build config for adapter:")
    for key, value in outputs.items():
        print(f"  {key}={value}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract adapter build configuration from versions.json",
    )
    parser.add_argument(
        "--adapter",
        required=True,
        choices=["javascript", "java", "python"],
        help="Adapter to extract configuration for",
    )
    parser.add_argument(
        "--output-mode",
        choices=["output", "env"],
        default="output",
        help="Write to GITHUB_OUTPUT (output) or GITHUB_ENV (env). Default: output",
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

    # Extract config
    outputs = extract_build_config(args.adapter, versions_config, args.output_mode)

    # Write outputs
    write_github_outputs(outputs, args.output_mode)

    return 0


if __name__ == "__main__":
    sys.exit(main())
