"""Auto-loaded fixtures for all unit tests.

This conftest is automatically loaded by pytest for any tests under
the unit test directories. It imports and re-exports all fixtures
from the unit fixture modules.

Usage
-----
Tests can directly use these fixtures without explicit imports:

    def test_something(mock_ctx, mock_transport):
        # mock_ctx and mock_transport are automatically available
        pass

For domain-specific tests, import additional fixtures in the
test module's conftest.py:

    from tests._fixtures.unit.dap import *  # noqa: F401, F403
"""

# Re-export environment variable fixtures
# Re-export adapter component mocks
from tests._fixtures.unit.adapter.config_mapper import (
    MockConfigurationMapper,
    TrackingConfigurationMapper,
    mock_config_mapper,
    mock_config_mapper_functional,
    mock_config_mapper_tracking,
)
from tests._fixtures.unit.adapter.launch_orchestrator import (
    MockLaunchOrchestrator,
    mock_launch_orchestrator,
    mock_launch_orchestrator_failing,
    mock_launch_orchestrator_tracking,
    mock_launch_orchestrator_with_port,
)
from tests._fixtures.unit.adapter.port import (
    MockPortRegistry,
    mock_port_manager,
    mock_port_manager_no_port,
    mock_port_registry,
    mock_port_registry_exhausted,
    mock_port_registry_tracking,
)
from tests._fixtures.unit.adapter.process import (
    mock_asyncio_process,
    mock_asyncio_process_exited,
    mock_asyncio_process_failed,
    mock_process_manager,
    mock_process_manager_running,
)

# Re-export API component mocks
from tests._fixtures.unit.api import (
    mock_adapter_registry,
    mock_breakpoint_converter,
    mock_session,
    mock_session_manager,
    sample_breakpoint_spec,
    sample_breakpoint_specs,
    sample_launch_config,
    sample_launch_config_attach,
)

# Re-export assertions
from tests._fixtures.unit.assertions import UnitAssertions

# Re-export DAP builders
from tests._fixtures.unit.builders.dap_builders import (
    DAPEventBuilder,
    DAPResponseBuilder,
    event_builder,
    response_builder,
)
from tests._fixtures.unit.context import (
    assert_error_logged,
    assert_warning_logged,
    mock_ctx,
    mock_ctx_with_storage,
    null_ctx,
    tmp_storage,
)

# Re-export DAP component mocks
from tests._fixtures.unit.dap.events import (
    MockEventProcessor,
    mock_event_processor,
    mock_event_processor_full,
)
from tests._fixtures.unit.dap.receiver import (
    mock_receiver,
    mock_receiver_error,
    mock_receiver_running,
)
from tests._fixtures.unit.dap.transport import (
    MockTransportRecorder,
    mock_transport,
    mock_transport_disconnected,
    mock_transport_failing,
    mock_transport_recorder,
)
from tests._fixtures.unit.env import env_var_cleanup, set_env

# Re-export MCP component mocks
from tests._fixtures.unit.mcp.config import (
    MockSessionConfig,
    mock_mcp_config,
    mock_session_config,
    mock_session_config_fast,
    patch_mcp_config,
)
from tests._fixtures.unit.mcp.debug_api import (
    mock_debug_api,
    mock_debug_api_no_session_info,
    mock_debug_api_not_started,
    mock_debug_api_reconnect_fails,
    mock_debug_api_stop_fails,
)
from tests._fixtures.unit.mcp.session_context import (
    mock_mcp_session_context,
    mock_mcp_session_context_no_session_info,
    mock_mcp_session_context_not_started,
    mock_mcp_session_context_with_breakpoints,
    mock_mcp_session_context_with_variables,
)
from tests._fixtures.unit.mcp.state import (
    mock_logging_functions,
    multiple_sessions_state,
    populated_session_state,
    reset_mcp_session_state,
)

# Re-export session component mocks
from tests._fixtures.unit.session.child_manager import (
    MockChildSessionManager,
    mock_child_session_manager,
    mock_child_session_manager_failing,
    mock_child_session_manager_tracking,
    mock_child_session_manager_with_child,
)
from tests._fixtures.unit.session.client import (
    MockDAPClientResponder,
    mock_dap_client_disconnected,
    mock_dap_client_for_session,
    mock_dap_client_paused,
    mock_dap_client_responder,
)
from tests._fixtures.unit.session.event_bridge import (
    MockEventBridge,
    mock_event_bridge,
    mock_event_bridge_tracking,
    mock_event_bridge_with_children,
)
from tests._fixtures.unit.session.lifecycle import (
    mock_session_lifecycle,
    mock_session_lifecycle_running,
    mock_session_lifecycle_start_fails,
)
from tests._fixtures.unit.session.registry import (
    MockSessionRegistry,
    mock_child_session_registry,
    mock_session_registry,
    mock_session_registry_full,
    mock_session_registry_with_session,
)
from tests._fixtures.unit.session.state import (
    mock_session_state,
    mock_session_state_error,
    mock_session_state_paused,
    mock_session_state_running,
)

# Export all for convenient wildcard imports
__all__ = [
    # Environment
    "env_var_cleanup",
    "set_env",
    # Context
    "mock_ctx",
    "null_ctx",
    "tmp_storage",
    "mock_ctx_with_storage",
    "assert_error_logged",
    "assert_warning_logged",
    # Assertions
    "UnitAssertions",
    # Builders
    "DAPResponseBuilder",
    "DAPEventBuilder",
    "response_builder",
    "event_builder",
    # DAP Transport
    "mock_transport",
    "mock_transport_disconnected",
    "mock_transport_failing",
    "mock_transport_recorder",
    "MockTransportRecorder",
    # DAP Receiver
    "mock_receiver",
    "mock_receiver_running",
    "mock_receiver_error",
    # DAP Events
    "mock_event_processor",
    "mock_event_processor_full",
    "MockEventProcessor",
    # Session State
    "mock_session_state",
    "mock_session_state_running",
    "mock_session_state_paused",
    "mock_session_state_error",
    # Session Lifecycle
    "mock_session_lifecycle",
    "mock_session_lifecycle_running",
    "mock_session_lifecycle_start_fails",
    # Session Client
    "mock_dap_client_for_session",
    "mock_dap_client_paused",
    "mock_dap_client_disconnected",
    "mock_dap_client_responder",
    "MockDAPClientResponder",
    # Session Registry
    "mock_session_registry",
    "mock_session_registry_with_session",
    "mock_session_registry_full",
    "mock_child_session_registry",
    "MockSessionRegistry",
    # Session Child Manager
    "mock_child_session_manager",
    "mock_child_session_manager_with_child",
    "mock_child_session_manager_failing",
    "mock_child_session_manager_tracking",
    "MockChildSessionManager",
    # Session Event Bridge
    "mock_event_bridge",
    "mock_event_bridge_with_children",
    "mock_event_bridge_tracking",
    "MockEventBridge",
    # Adapter Process
    "mock_asyncio_process",
    "mock_asyncio_process_exited",
    "mock_asyncio_process_failed",
    "mock_process_manager",
    "mock_process_manager_running",
    # Adapter Port
    "mock_port_manager",
    "mock_port_manager_no_port",
    "mock_port_registry",
    "mock_port_registry_exhausted",
    "mock_port_registry_tracking",
    "MockPortRegistry",
    # Adapter Launch Orchestrator
    "mock_launch_orchestrator",
    "mock_launch_orchestrator_with_port",
    "mock_launch_orchestrator_failing",
    "mock_launch_orchestrator_tracking",
    "MockLaunchOrchestrator",
    # Adapter Config Mapper
    "mock_config_mapper",
    "mock_config_mapper_tracking",
    "mock_config_mapper_functional",
    "MockConfigurationMapper",
    "TrackingConfigurationMapper",
    # MCP Debug API
    "mock_debug_api",
    "mock_debug_api_not_started",
    "mock_debug_api_no_session_info",
    "mock_debug_api_stop_fails",
    "mock_debug_api_reconnect_fails",
    # MCP Session Context
    "mock_mcp_session_context",
    "mock_mcp_session_context_not_started",
    "mock_mcp_session_context_no_session_info",
    "mock_mcp_session_context_with_breakpoints",
    "mock_mcp_session_context_with_variables",
    # MCP Config
    "MockSessionConfig",
    "mock_session_config",
    "mock_session_config_fast",
    "mock_mcp_config",
    "patch_mcp_config",
    # MCP State
    "reset_mcp_session_state",
    "populated_session_state",
    "multiple_sessions_state",
    "mock_logging_functions",
    # API
    "mock_adapter_registry",
    "mock_breakpoint_converter",
    "mock_session",
    "mock_session_manager",
    "sample_breakpoint_spec",
    "sample_breakpoint_specs",
    "sample_launch_config",
    "sample_launch_config_attach",
]
