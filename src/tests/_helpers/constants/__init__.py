"""Test constants and enums for AIDB test suite.

This package provides centralized constants and enums used across tests to ensure
consistency and reduce magic numbers/strings.
"""

from aidb_common.constants import Language
from tests._helpers.constants.defaults import (
    DEFAULT_TEST_LANGUAGES,
    DockerConfig,
    ErrorMessage,
    LanguageTestHelpers,
    TestData,
    TestPattern,
    get_default_config,
    get_test_file_content,
)
from tests._helpers.constants.enums import (
    AdapterState,
    DebugInterfaceType,
    LogLevel,
    MCPResponseCode,
    MCPTool,
    StopReason,
    TerminationReason,
    TestMarker,
)
from tests._helpers.constants.environment import (
    EnvVar,
    get_container_multiplier,
    is_running_in_container,
)
from tests._helpers.constants.paths import (
    FRAMEWORK_APPS_ROOT,
    TESTS_ROOT,
    get_framework_app_path,
)
from tests._helpers.constants.ports import DebugPorts, PortRanges
from tests._helpers.constants.timeouts import TestLimits, TestTimeouts

__all__ = [
    # Re-export Language from aidb_common
    "Language",
    # Enums
    "DebugInterfaceType",
    "LogLevel",
    "StopReason",
    "TerminationReason",
    "TestMarker",
    "AdapterState",
    "MCPTool",
    "MCPResponseCode",
    # Timeouts
    "TestTimeouts",
    "TestLimits",
    # Paths
    "TESTS_ROOT",
    "FRAMEWORK_APPS_ROOT",
    "get_framework_app_path",
    # Ports
    "DebugPorts",
    "PortRanges",
    # Defaults
    "DEFAULT_TEST_LANGUAGES",
    "LanguageTestHelpers",
    "TestPattern",
    "ErrorMessage",
    "DockerConfig",
    "TestData",
    "get_default_config",
    "get_test_file_content",
    # Environment
    "EnvVar",
    "is_running_in_container",
    "get_container_multiplier",
]
