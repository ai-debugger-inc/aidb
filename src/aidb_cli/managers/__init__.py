"""Centralized manager classes for AIDB CLI.

This module provides singleton manager classes that consolidate functionality from
various scripts and provide a unified interface for both CLI commands and standalone
script usage.
"""

from aidb_common.repo import detect_repo_root


# Use lazy imports to avoid circular dependencies
def __getattr__(name):
    """Lazy import managers to avoid circular dependencies."""
    if name == "BuildManager":
        from .build import BuildManager

        return BuildManager
    if name == "ConfigManager":
        from .config_manager import ConfigManager

        return ConfigManager
    if name == "TestManager":
        from .test import TestManager

        return TestManager
    if name == "TestOrchestrator":
        from .test import TestOrchestrator

        return TestOrchestrator
    if name == "DockerOrchestrator":
        from .docker import DockerOrchestrator

        return DockerOrchestrator
    if name == "DockerComposeExecutor":
        from .docker import DockerComposeExecutor

        return DockerComposeExecutor
    if name == "ResourceCleaner":
        from aidb_cli.core.cleanup import ResourceCleaner

        return ResourceCleaner
    msg = f"module 'aidb_cli.managers' has no attribute '{name}'"
    raise AttributeError(msg)


__all__ = [
    "BuildManager",
    "ConfigManager",
    "TestManager",
    "TestOrchestrator",
    "DockerOrchestrator",
    "DockerComposeExecutor",
    "ResourceCleaner",
    "detect_repo_root",
]
