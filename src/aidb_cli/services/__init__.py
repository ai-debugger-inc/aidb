"""CLI Services module.

This module provides services for the AIDB CLI. Services are organized into logical
subpackages but can be imported directly for backward compatibility.
"""

from aidb_cli.services.command_executor import CommandExecutor


# For backward compatibility, import services when specifically requested
def __getattr__(name):
    """Lazy import services to avoid circular dependencies."""
    # Docker services
    if name == "DockerContextService":
        from aidb_cli.services.docker import DockerContextService

        return DockerContextService
    if name == "DockerHealthService":
        from aidb_cli.services.docker import DockerHealthService

        return DockerHealthService
    if name == "DockerLoggingService":
        from aidb_cli.services.docker import DockerLoggingService

        return DockerLoggingService
    if name == "ServiceDependencyService":
        from aidb_cli.services.docker import ServiceDependencyService

        return ServiceDependencyService
    # Test services
    if name == "TestDiscoveryService":
        from aidb_cli.services.test import TestDiscoveryService

        return TestDiscoveryService
    if name == "TestExecutionService":
        from aidb_cli.services.test import TestExecutionService

        return TestExecutionService
    if name == "TestReportingService":
        from aidb_cli.services.test import TestReportingService

        return TestReportingService
    # Adapter services
    if name == "AdapterService":
        from aidb_cli.services.adapter import AdapterService

        return AdapterService
    # Build services
    if name == "DownloadService":
        from aidb_cli.services.build import DownloadService

        return DownloadService
    msg = f"module 'aidb_cli.services' has no attribute '{name}'"
    raise AttributeError(msg)


__all__ = [
    # Command execution
    "CommandExecutor",
    # Docker services
    "DockerContextService",
    "DockerHealthService",
    "DockerLoggingService",
    "ServiceDependencyService",
    # Test services
    "TestDiscoveryService",
    "TestExecutionService",
    "TestReportingService",
    # Adapter services
    "AdapterService",
    # Build services
    "DownloadService",
]
