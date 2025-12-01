"""Shared configuration utilities for AIDB (aidb_common.config).

This package provides:
- runtime: Environment-driven configuration (``config`` singleton)
- project: YAML-based project/user configuration loader
- versions: Centralized version manager for adapters and infrastructure
"""

from .project import load_merged_config
from .runtime import ConfigManager, config
from .versions import VersionManager

__all__ = [
    "ConfigManager",
    "config",
    "load_merged_config",
    "VersionManager",
]
