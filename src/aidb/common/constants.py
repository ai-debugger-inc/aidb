"""Constants shared across the AIDB codebase."""

from aidb_common.env import reader

# Timeout values (in milliseconds)
DEFAULT_TIMEOUT_MS = 10000
MAX_TIMEOUT_MS = 60000
MIN_TIMEOUT_MS = 1000

# Session limits
MAX_CONCURRENT_SESSIONS = 10

# Default host and port
DEFAULT_ADAPTER_HOST = "localhost"
DEFAULT_NODE_DEBUG_PORT = 9229  # Standard Node.js --inspect port
DEFAULT_PYTHON_DEBUG_PORT = 5678  # Standard debugpy --listen port
DEFAULT_JAVA_DEBUG_PORT = 5005  # Standard JDWP debug port
DEFAULT_VSCODE_BRIDGE_PORT = 42042  # VS Code extension bridge port

# AidbThread and frame defaults
DEFAULT_THREAD_ID = 1
DEFAULT_FRAME_ID = 0

# Step operation defaults
DEFAULT_STEP_GRANULARITY = "line"
DEFAULT_WAIT_FOR_STOP = True

# Memory operation defaults
DEFAULT_MEMORY_OFFSET = 0
DEFAULT_MEMORY_COUNT = 256
DEFAULT_ALLOW_PARTIAL_MEMORY = False

# Disassemble defaults
DEFAULT_INSTRUCTION_COUNT = 10
DEFAULT_RESOLVE_SYMBOLS = True

# Evaluation contexts
EVALUATION_CONTEXT_REPL = "repl"
EVALUATION_CONTEXT_WATCH = "watch"
EVALUATION_CONTEXT_HOVER = "hover"

# Task execution status
TASK_STATUS_SUCCESS = "success"
TASK_STATUS_ERROR = "error"

# Breakpoint validation messages
BREAKPOINT_VALIDATION_DISABLE_MSG = (
    "To disable validation, set AIDB_VALIDATE_BREAKPOINTS=false"
)

# Breakpoint verification timeouts (in seconds)
DEFAULT_BREAKPOINT_VERIFICATION_TIMEOUT_S = 2.0
EVENT_POLL_TIMEOUT_S = 0.1
POLL_SLEEP_INTERVAL_S = 0.05
MAX_JITTER_S = 0.05

# Connection and network timeouts (in seconds)
CONNECTION_TIMEOUT_S = 5.0
RECONNECTION_TIMEOUT_S = 5.0
DISCONNECT_TIMEOUT_S = reader.read_float("AIDB_DISCONNECT_TIMEOUT_S", 2.0) or 2.0
RECEIVER_STOP_TIMEOUT_S = 2.0

# Async operation sleep intervals (in seconds)
SHORT_SLEEP_S = 0.1
MEDIUM_SLEEP_S = 0.5
LONG_WAIT_S = 2.0
DEFAULT_WAIT_TIMEOUT_S = 5.0
STACK_TRACE_TIMEOUT_S = 10.0
MAX_PROCESS_WAIT_TIME_S = 15.0

# Retry and backoff configuration
INITIAL_RETRY_DELAY_S = 0.5
MAX_RETRY_DELAY_S = 2.0
BACKOFF_MULTIPLIER = 2.0

# Process management timeouts (in seconds)
PROCESS_CLEANUP_MIN_AGE_S = 5.0
PROCESS_TERMINATE_TIMEOUT_S = 2.0
PROCESS_STARTUP_DELAY_S = 0.1
PROCESS_WAIT_TIMEOUT_S = 0.5

# Orphan process cleanup time budgets (in milliseconds)
ORPHAN_SCAN_PRE_LAUNCH_MS = 500.0  # Pre-launch: fast, bounded scan
ORPHAN_SCAN_POST_STOP_MS = 1000.0  # Post-stop: more generous budget

# Variable scope names
SCOPE_LOCALS = "locals"
SCOPE_LOCAL = "local"
SCOPE_GLOBALS = "globals"
SCOPE_GLOBAL = "global"

# Log/display truncation lengths
LOG_EXPRESSION_PREVIEW_LENGTH = 100  # Characters to show in log messages

# Audit logging constants
AUDIT_QUEUE_MAX_SIZE = 1000  # Max pending audit events in queue
AUDIT_INIT_TIMEOUT_S = 2.0  # Normal initialization timeout
AUDIT_INIT_TIMEOUT_TEST_S = 0.5  # Shorter timeout for test environments
AUDIT_FLUSH_TIMEOUT_S = 5.0  # Timeout for flush operations
AUDIT_SHUTDOWN_TIMEOUT_S = 5.0  # Timeout for shutdown
AUDIT_WORKER_TIMEOUT_S = 1.0  # Worker loop poll timeout
AUDIT_MAX_PENDING_EVENTS = 10000  # Safety limit for shutdown event processing
AUDIT_SINGLETON_RESET_TIMEOUT_S = 3.0  # Timeout for singleton reset

# Port allocation constants
PORT_CLEANUP_MIN_INTERVAL_S = 5.0  # Min seconds between cleanup operations
PORT_FALLBACK_RANGE_SIZE = 100  # Number of ports in each fallback range
PORT_ALLOCATION_MAX_ATTEMPTS = 200  # Max port allocation attempts
PORT_LOCK_MAX_RETRIES = 10  # Max retries for acquiring port lock
PORT_INIT_CLEANUP_MAX_WAIT_S = 0.5  # Max wait during init cleanup

# DAP receiver constants
MAX_CONSECUTIVE_FAILURES = 5  # Max failures before stopping receiver

# Time constants
SECONDS_PER_DAY = 86400  # Seconds in a day (for dummy process sleep)

# DAP initialization sequence timeouts (in seconds)
INIT_WAIT_FOR_INITIALIZED_S = 5.0  # Standard wait for initialized event
INIT_WAIT_FOR_INITIALIZED_JAVA_S = 30.0  # Java needs longer for JDT LS
INIT_CONFIGURATION_DONE_S = 5.0  # Standard configuration done timeout
INIT_CONFIGURATION_DONE_JAVA_S = 15.0  # Java needs longer
INIT_WAIT_FOR_PLUGIN_READY_S = 20.0  # Java plugin ready timeout
INIT_WAIT_FOR_LAUNCH_RESPONSE_S = 10.0  # Wait for launch response

# LSP operation timeouts (in seconds)
LSP_SHUTDOWN_TIMEOUT_S = 5.0  # LSP shutdown request timeout
LSP_SERVICE_READY_TIMEOUT_S = 60.0  # Wait for JDT LS ServiceReady
LSP_EXECUTE_COMMAND_TIMEOUT_S = 10.0  # Execute command timeout
LSP_HEALTH_CHECK_TIMEOUT_S = 2.0  # Quick health check timeout
LSP_MAVEN_IMPORT_TIMEOUT_S = 10.0  # Maven/Gradle import progress timeout
LSP_PROJECT_IMPORT_TIMEOUT_S = 50.0  # Project import polling timeout

# Network download timeouts (in seconds)
DOWNLOAD_TIMEOUT_S = 30.0  # Timeout for downloading files

# Child session timeouts (in seconds)
CHILD_SESSION_WAIT_TIMEOUT_S = 10.0  # Wait for child session creation

# DAP request timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT_S = 30.0  # Default timeout for DAP requests
INIT_REQUEST_TIMEOUT_S = 20.0  # Timeout for initialize request

# Process communication timeouts (in seconds)
PROCESS_COMMUNICATE_TIMEOUT_S = 5.0  # Process communicate() timeout
PROCESS_CLEANUP_TIMEOUT_S = 2.0  # Cleanup operations timeout

# Event queue timeouts (in seconds)
EVENT_QUEUE_POLL_TIMEOUT_S = 0.1  # Event queue get timeout

# MCP server timeouts (in seconds)
MCP_SERVER_TIMEOUT_S = 300.0  # MCP server operation timeout

# Syntax validation timeouts (in seconds)
SYNTAX_VALIDATION_TIMEOUT_S = 5.0  # Quick syntax check
SYNTAX_VALIDATION_EXTENDED_TIMEOUT_S = 10.0  # Extended syntax validation

# Thread join timeouts (in seconds)
THREAD_JOIN_TIMEOUT_S = 2.0  # Standard thread join timeout

# Java compilation timeout (in seconds)
JAVA_COMPILATION_TIMEOUT_S = 30.0

# Transport receive timeout (in seconds)
RECEIVE_POLL_TIMEOUT_S = 1.0  # Network receive buffer poll timeout

# Command check timeouts (in seconds)
COMMAND_CHECK_TIMEOUT_S = 2.0  # Version/availability command checks

# Extension installation timeouts (in seconds)
EXTENSION_LIST_TIMEOUT_S = 5.0  # List installed extensions
EXTENSION_INSTALL_TIMEOUT_S = 30.0  # Install extension from marketplace/VSIX

# Launch configuration adapter argument keys
ADAPTER_ARG_TARGET = "target"
ADAPTER_ARG_PROGRAM = "program"
ADAPTER_ARG_ARGS = "args"
