"""Project/user YAML configuration loading for AIDB CLI.

This module provides helpers to locate, load, and deep-merge configuration from
user (~/.config/aidb/config.yaml) and project (.aidb.yaml) files. It also applies
sensible defaults used across the CLI toolchain.

Note: This is a CLI-only module. The core aidb package does not depend on PyYAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aidb_cli.core.yaml import YamlOperationError, safe_read_yaml
from aidb_common.path import get_aidb_adapters_dir


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge two dictionaries in place and return ``base``.

    Values from ``override`` take precedence. Nested dicts are merged
    recursively; other values are replaced.
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def default_config(repo_root: Path) -> dict[str, Any]:
    """Return the shared default configuration structure."""
    return {
        "defaults": {
            "verbose": False,
            "log_level": "INFO",
            "env": "dev",
        },
        "adapters": {
            "auto_build": True,
            "cache_dir": str(get_aidb_adapters_dir()),
            "languages": {
                "python": {"enabled": True},
                "javascript": {"enabled": True},
                "java": {"enabled": True},
            },
        },
        "docker": {
            "compose_file": str(repo_root / "src/tests/_docker/docker-compose.yaml"),
            "auto_build": True,
        },
        "test": {
            "auto_install_deps": True,
            "pytest_args": "-v --tb=short",
        },
    }


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file with tolerant fallback.

    Preserves previous behavior of returning an empty dict when the file is missing,
    unreadable, or not a mapping at the top level.
    """
    try:
        if not path.exists():
            return {}
        data = safe_read_yaml(path) or {}
        return data if isinstance(data, dict) else {}
    except YamlOperationError:
        # Maintain prior tolerance by returning an empty config on errors
        return {}


def get_user_config_path() -> Path:
    """Get path to user-level AIDB configuration file."""
    return Path.home() / ".config" / "aidb" / "config.yaml"


def get_project_config_path(repo_root: Path) -> Path:
    """Get path to project-level AIDB configuration file."""
    return repo_root / ".aidb.yaml"


def load_merged_config(repo_root: Path) -> dict[str, Any]:
    """Load default + user + project YAML config into a single dict."""
    cfg = default_config(repo_root)

    user_cfg = load_yaml(get_user_config_path())
    if user_cfg:
        deep_merge(cfg, user_cfg)

    project_cfg = load_yaml(get_project_config_path(repo_root))
    if project_cfg:
        deep_merge(cfg, project_cfg)

    return cfg
