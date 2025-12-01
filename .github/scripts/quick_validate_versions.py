#!/usr/bin/env python3
"""Quick validation script for version updates in CI/CD.

This script performs essential checks that can run quickly in GitHub Actions to
validate version updates before they're merged.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from packaging import version


def _validate_required_keys(config: dict[str, Any]) -> list[str]:
    """Validate required top-level keys.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []
    required_keys = ["version"]
    for key in required_keys:
        if key not in config:
            errors.append(f"Missing required key: {key}")
    return errors


def _validate_language_config(lang_name: str, lang_config: Any) -> list[str]:
    """Validate a single language configuration.

    Parameters
    ----------
    lang_name : str
        Language name
    lang_config : Any
        Language configuration

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if not isinstance(lang_config, dict):
        errors.append(f"Language {lang_name} config must be a dictionary")
        return errors

    if "supported_versions" not in lang_config:
        errors.append(f"Language {lang_name} missing supported_versions")
        return errors

    versions = lang_config["supported_versions"]
    if not isinstance(versions, list):
        errors.append(f"Language {lang_name} supported_versions must be a list")
        return errors

    # Validate each version entry
    for i, version_info in enumerate(versions):
        version_errors = _validate_version_entry(lang_name, i, version_info)
        errors.extend(version_errors)

    return errors


def _validate_version_entry(lang_name: str, index: int, version_info: Any) -> list[str]:
    """Validate a single version entry.

    Parameters
    ----------
    lang_name : str
        Language name
    index : int
        Version index
    version_info : Any
        Version information

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if not isinstance(version_info, dict):
        errors.append(f"Language {lang_name} version {index} must be a dictionary")
        return errors

    if "version" not in version_info:
        errors.append(f"Language {lang_name} version {index} missing version field")

    # Validate version string format
    version_str = version_info.get("version", "")
    try:
        version.parse(version_str)
    except Exception:
        errors.append(f"Language {lang_name} invalid version format: {version_str}")

    return errors


def validate_config_format(config: dict[str, Any]) -> list[str]:
    """Validate the basic format of the configuration file.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    # Check required top-level keys
    errors.extend(_validate_required_keys(config))

    # Validate languages section
    if "languages" in config:
        for lang_name, lang_config in config["languages"].items():
            errors.extend(_validate_language_config(lang_name, lang_config))

    return errors


def validate_version_consistency(config: dict[str, Any]) -> list[str]:
    """Validate version consistency and tagging.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if "languages" not in config:
        return errors

    for lang_name, lang_config in config["languages"].items():
        versions = lang_config.get("supported_versions", [])

        if not versions:
            continue

        # Check for duplicate versions
        version_strings = [v.get("version", "") for v in versions]
        if len(version_strings) != len(set(version_strings)):
            duplicates = [
                v for v in set(version_strings) if version_strings.count(v) > 1
            ]
            errors.append(f"Language {lang_name} has duplicate versions: {duplicates}")

        # Check latest tag usage
        latest_count = sum(1 for v in versions if "latest" in v.get("tags", []))
        if latest_count > 1:
            errors.append(f"Language {lang_name} has multiple 'latest' tags")
        elif latest_count == 0:
            errors.append(f"Language {lang_name} has no 'latest' tag")

        # Validate version ordering (latest should be highest version)
        try:
            sorted_versions = sorted(
                versions,
                key=lambda x: version.parse(x["version"]),
                reverse=True,
            )
            latest_version = next(
                (v for v in versions if "latest" in v.get("tags", [])),
                None,
            )

            if (
                latest_version
                and sorted_versions
                and latest_version["version"] != sorted_versions[0]["version"]
            ):
                errors.append(
                    f"Language {lang_name} 'latest' tag not on highest version "
                    f"(latest: {latest_version['version']}, highest: {sorted_versions[0]['version']})",
                )
        except Exception as e:
            errors.append(f"Language {lang_name} version sorting failed: {e}")

    return errors


def validate_eol_dates(config: dict[str, Any]) -> list[str]:
    """Validate end-of-life date formats.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if "languages" not in config:
        return errors

    from datetime import datetime, timezone

    for lang_name, lang_config in config["languages"].items():
        versions = lang_config.get("supported_versions", [])

        for version_info in versions:
            eol_date = version_info.get("end_of_life")
            if not eol_date:
                continue

            # Try to parse EOL date in various formats
            valid_format = False
            for date_format in ["%Y-%m-%d", "%Y-%m", "%Y"]:
                try:
                    datetime.strptime(eol_date, date_format).replace(tzinfo=timezone.utc)
                    valid_format = True
                    break
                except ValueError:
                    continue

            if not valid_format:
                errors.append(
                    f"Language {lang_name} version {version_info['version']} "
                    f"has invalid EOL date format: {eol_date}",
                )

    return errors


def _validate_adapter_version(lang_name: str, adapter_config: dict[str, Any]) -> list[str]:
    """Validate adapter version information.

    Parameters
    ----------
    lang_name : str
        Language name
    adapter_config : Dict[str, Any]
        Adapter configuration

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if "version" not in adapter_config:
        errors.append(f"Language {lang_name} adapter missing version field")
        return errors

    adapter_version = adapter_config["version"]
    if adapter_version != "latest":
        try:
            version.parse(adapter_version)
        except Exception:
            errors.append(
                f"Language {lang_name} adapter has invalid version format: {adapter_version}",
            )

    return errors


def _validate_adapter_min_version(lang_name: str, adapter_config: dict[str, Any]) -> list[str]:
    """Validate adapter minimum version constraint.

    Parameters
    ----------
    lang_name : str
        Language name
    adapter_config : Dict[str, Any]
        Adapter configuration

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []
    min_version = adapter_config.get("min_version")

    if not min_version:
        return errors

    try:
        min_ver = version.parse(min_version)
        adapter_version = adapter_config.get("version", "")

        if adapter_version != "latest":
            current_ver = version.parse(adapter_version)
            if current_ver < min_ver:
                errors.append(
                    f"Language {lang_name} adapter version {adapter_version} "
                    f"is below minimum {min_version}",
                )
    except Exception:
        errors.append(
            f"Language {lang_name} adapter has invalid min_version format: {min_version}",
        )

    return errors


def _validate_single_adapter(lang_name: str, adapter_config: dict[str, Any]) -> list[str]:
    """Validate a single adapter configuration.

    Parameters
    ----------
    lang_name : str
        Language name
    adapter_config : Dict[str, Any]
        Adapter configuration

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    # Check required package field
    if "package" not in adapter_config:
        errors.append(f"Language {lang_name} adapter missing package field")

    # Validate version
    errors.extend(_validate_adapter_version(lang_name, adapter_config))

    # Validate min_version if present
    errors.extend(_validate_adapter_min_version(lang_name, adapter_config))

    return errors


def validate_adapter_configs(config: dict[str, Any]) -> list[str]:
    """Validate adapter configurations.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary

    Returns
    -------
    List[str]
        List of validation errors
    """
    errors: list[str] = []

    if "languages" not in config:
        return errors

    for lang_name, lang_config in config["languages"].items():
        adapter_config = lang_config.get("adapter")
        if adapter_config:
            errors.extend(_validate_single_adapter(lang_name, adapter_config))

    return errors


def main():
    """Run quick validation checks."""
    parser = argparse.ArgumentParser(description="Quick validation for version configs")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to versions.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error on any validation issue",
    )

    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    # Load configuration
    try:
        with Path(args.config).open() as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        sys.exit(1)

    # Run validations
    all_errors = []

    print("Running quick validation checks...")

    errors = validate_config_format(config)
    all_errors.extend(errors)
    print(f"✓ Config format: {len(errors)} errors")

    errors = validate_version_consistency(config)
    all_errors.extend(errors)
    print(f"✓ Version consistency: {len(errors)} errors")

    errors = validate_eol_dates(config)
    all_errors.extend(errors)
    print(f"✓ EOL date formats: {len(errors)} errors")

    errors = validate_adapter_configs(config)
    all_errors.extend(errors)
    print(f"✓ Adapter configs: {len(errors)} errors")

    # Report results
    if all_errors:
        print(f"\n❌ Validation failed with {len(all_errors)} errors:")
        for error in all_errors:
            print(f"  - {error}")

        if args.strict:
            sys.exit(1)
    else:
        print("\n✅ All validations passed!")

    sys.exit(0)


if __name__ == "__main__":
    main()
