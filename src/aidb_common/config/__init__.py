"""Shared configuration utilities for AIDB (aidb_common.config).

This package provides:
- runtime: Environment-driven configuration (``config`` singleton)
- versions: Centralized version manager for adapters and infrastructure
"""

from .runtime import ConfigManager, config
from .versions import VersionManager

__all__ = [
    "ConfigManager",
    "config",
    "VersionManager",
]
