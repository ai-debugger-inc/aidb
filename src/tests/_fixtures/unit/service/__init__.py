"""Service unit test fixtures.

Re-exports all fixtures from service-specific modules for convenient wildcard imports.
"""

from tests._fixtures.unit.service.breakpoints import (
    mock_adapter_registry,
    mock_breakpoint_converter,
    sample_breakpoint_spec,
    sample_breakpoint_specs,
)
from tests._fixtures.unit.service.launch_config import (
    sample_launch_config,
    sample_launch_config_attach,
)
from tests._fixtures.unit.service.session import (
    mock_session,
    mock_session_manager,
)

__all__ = [
    "mock_adapter_registry",
    "mock_breakpoint_converter",
    "mock_session",
    "mock_session_manager",
    "sample_breakpoint_spec",
    "sample_breakpoint_specs",
    "sample_launch_config",
    "sample_launch_config_attach",
]
