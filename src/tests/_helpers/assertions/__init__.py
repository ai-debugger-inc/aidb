"""Custom assertion helpers for AIDB test suite.

This package provides specialized assertions for DAP messages, MCP tools, responses,
state validation, and performance testing.

The package is organized into focused modules:
- dap_assertions: DAP protocol specific assertions
- mcp_assertions: MCP tool response assertions
- response_assertions: Generic response validation
- state_assertions: Session and execution state
- performance_assertions: Performance and timing
- collection_assertions: List and dict validations
- logging_assertions: Log output validation
- eventual_assertions: Async condition assertions
- debug_interface_assertions: Debug interface testing
- helpers: Standalone utility functions
"""

from .collection_assertions import CollectionAssertions
from .dap_assertions import DAPAssertions, ExtendedDAPAssertions
from .debug_interface_assertions import DebugInterfaceAssertions
from .eventual_assertions import EventualAssertions
from .helpers import (
    assert_response_success,
    assert_within_timeout,
    create_assertion_helper,
)
from .logging_assertions import LoggingAssertions
from .mcp_assertions import MCPAssertions
from .performance_assertions import PerformanceAssertions
from .response_assertions import ResponseAssertions
from .state_assertions import StateAssertions

__all__ = [
    # DAP assertions
    "DAPAssertions",
    "ExtendedDAPAssertions",
    # MCP assertions
    "MCPAssertions",
    # Generic response assertions
    "ResponseAssertions",
    # State assertions
    "StateAssertions",
    # Performance assertions
    "PerformanceAssertions",
    # Collection assertions
    "CollectionAssertions",
    # Logging assertions
    "LoggingAssertions",
    # Eventual assertions
    "EventualAssertions",
    # Debug interface assertions
    "DebugInterfaceAssertions",
    # Helper functions
    "create_assertion_helper",
    "assert_response_success",
    "assert_within_timeout",
]
