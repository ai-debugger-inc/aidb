"""Constants for the API subpackage."""

from aidb_common.env import reader

# Timeout values (in milliseconds)
DEFAULT_TIMEOUT_MS = 10000
MAX_TIMEOUT_MS = 60000
MIN_TIMEOUT_MS = 1000

# Session limits
MAX_CONCURRENT_SESSIONS = 10

# Default host and port
DEFAULT_ADAPTER_HOST = "localhost"

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
