"""Test helpers package.

This package contains helper utilities and assertion functions for AIDB testing.
"""

# Assertion helpers
from .assertions import (
    CollectionAssertions,
    DAPAssertions,
    DebugInterfaceAssertions,
    EventualAssertions,
    ExtendedDAPAssertions,
    LoggingAssertions,
    MCPAssertions,
    PerformanceAssertions,
    ResponseAssertions,
    StateAssertions,
    assert_response_success,
    assert_within_timeout,
    create_assertion_helper,
)

# Constants and enums
from .constants import (
    AdapterState,
    DebugPorts,
    DockerConfig,
    EnvVar,
    ErrorMessage,
    Language,
    LogLevel,
    MCPResponseCode,
    MCPTool,
    PortRanges,
    StopReason,
    TestMarker,
    TestPattern,
    TestTimeouts,
    get_default_config,
    get_test_file_content,
)

# Logging capture utilities
from .logging_capture import (
    LogCapture,
    LogCaptureHandler,
    LogRecord,
    MultiLoggerCapture,
    assert_log_contains,
    assert_no_errors,
    capture_logs,
    get_session_logs,
)

# Test helper mixins
from .mixins import (
    DebugSessionMixin,
    FileTestMixin,
    ValidationMixin,
)

# Mock objects and factories
from .mocks import (
    MockAdapter,
    MockDAPClient,
    MockMCPServer,
    MockNotification,
    MockNotificationHandler,
    MockProcess,
    MockSessionManager,
    MockToolCall,
    MockToolHandler,
    create_failing_dap_client,
    create_mock_debugging_context,
    create_mock_mcp_context,
    create_mock_mcp_server,
    create_python_adapter,
    create_session_manager_with_active_session,
    create_successful_dap_client,
)

# Port management utilities
from .ports import (
    MockPortRegistry,
    TestPortManager,
    create_mock_port_registry,
    isolated_ports,
)

# Base test classes
from .pytest_base import (
    PytestAsyncBase,
    PytestBase,
)
from .pytest_mcp import (
    PytestMCPBase,
)

# Docker utilities (conditional import)
try:
    from .docker_utils import DockerContainerManager, DockerTestHelper  # type: ignore

    _docker_available = True
except ImportError:
    _docker_available = False
    DockerTestHelper = None  # type: ignore
    DockerContainerManager = None  # type: ignore

__all__ = [
    # Assertion classes
    "DAPAssertions",
    "ResponseAssertions",
    "StateAssertions",
    "PerformanceAssertions",
    "MCPAssertions",
    "ExtendedDAPAssertions",
    "CollectionAssertions",
    "LoggingAssertions",
    "EventualAssertions",
    "DebugInterfaceAssertions",
    # Assertion functions
    "assert_response_success",
    "assert_within_timeout",
    "create_assertion_helper",
    # Constants
    "DebugPorts",
    "PortRanges",
    "LogLevel",
    "StopReason",
    "TestTimeouts",
    "TestMarker",
    "Language",
    "AdapterState",
    "MCPTool",
    "MCPResponseCode",
    "TestPattern",
    "EnvVar",
    "ErrorMessage",
    "DockerConfig",
    "get_default_config",
    "get_test_file_content",
    # Logging
    "LogRecord",
    "LogCapture",
    "LogCaptureHandler",
    "MultiLoggerCapture",
    "capture_logs",
    "assert_no_errors",
    "assert_log_contains",
    "get_session_logs",
    # Mocks
    "MockDAPClient",
    "MockAdapter",
    "MockSessionManager",
    "MockProcess",
    "MockToolCall",
    "MockNotification",
    "MockMCPServer",
    "MockNotificationHandler",
    "MockToolHandler",
    "create_successful_dap_client",
    "create_failing_dap_client",
    "create_python_adapter",
    "create_session_manager_with_active_session",
    "create_mock_debugging_context",
    "create_mock_mcp_server",
    "create_mock_mcp_context",
    # Port management
    "TestPortManager",
    "MockPortRegistry",
    "isolated_ports",
    "create_mock_port_registry",
    # Base classes
    "PytestBase",
    "PytestAsyncBase",
    "PytestMCPBase",
    # Mixins
    "DebugSessionMixin",
    "FileTestMixin",
    "ValidationMixin",
    # Docker (conditional)
    "DockerTestHelper",
    "DockerContainerManager",
]

# Add docker availability flag
__all__.append("_docker_available")
