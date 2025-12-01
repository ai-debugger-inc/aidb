# Discovery Catalog

Quick reference for finding existing constants, enums, and utilities in AIDB.

**Rule:** Check here BEFORE adding any magic strings, numbers, or reimplementing utilities.

______________________________________________________________________

## Constants Files (8 total)

| File                           | Purpose  | Key Constants                                   |
| ------------------------------ | -------- | ----------------------------------------------- |
| `aidb_common/constants.py`     | Shared   | Language enum, AIDB_HOME_DIR, domains           |
| `aidb/adapters/constants.py`   | Adapters | Platform/arch mappings                          |
| `aidb/dap/client/constants.py` | DAP      | MessageType, EventType, CommandType, StopReason |
| `aidb/api/constants.py`        | API      | Timeouts (seconds), defaults, contexts          |
| `aidb/audit/constants.py`      | Audit    | Sensitive fields, masking patterns              |
| `aidb_cli/core/constants.py`   | CLI      | Icons, exit codes, Docker profiles              |
| `aidb_mcp/core/constants.py`   | MCP      | Tool names, actions, response formats           |
| `tests/_helpers/constants.py`  | Tests    | Ports, timeouts, markers, patterns              |

______________________________________________________________________

## Key Enums (101+ total)

### Core Language

```python
from aidb_common.constants import Language  # PYTHON, JAVASCRIPT, JAVA
```

### DAP Protocol

```python
from aidb.dap.client.constants import (
    MessageType,   # REQUEST, RESPONSE, EVENT
    EventType,     # STOPPED, CONTINUED, TERMINATED, OUTPUT, ...
    CommandType,   # INITIALIZE, LAUNCH, CONTINUE, NEXT, ...
    StopReason,    # BREAKPOINT, STEP, EXCEPTION, PAUSE
)
```

### MCP Tools

```python
from aidb_mcp.core.constants import (
    SessionAction,      # START, STOP, RESTART, STATUS, LIST
    BreakpointAction,   # SET, REMOVE, LIST, CLEAR_ALL
    InspectTarget,      # LOCALS, GLOBALS, STACK, THREADS
    ExecutionAction,    # RUN, CONTINUE
    StepAction,         # INTO, OVER, OUT
    VariableAction,     # GET, SET, PATCH
)
```

### CLI

```python
from aidb_cli.core.constants import LogLevel, ExitCode, Icons, DockerProfiles
```

______________________________________________________________________

## Timeout Constants

**Location:** `aidb/api/constants.py`

```python
# Polling/short waits
EVENT_POLL_TIMEOUT_S = 0.1
MEDIUM_SLEEP_S = 0.5

# Standard operations
DISCONNECT_TIMEOUT_S = 2.0
CONNECTION_TIMEOUT_S = 5.0
DEFAULT_WAIT_TIMEOUT_S = 5.0
STACK_TRACE_TIMEOUT_S = 10.0

# Long operations
MAX_PROCESS_WAIT_TIME_S = 15.0

# Backoff
INITIAL_RETRY_DELAY_S = 0.5
BACKOFF_MULTIPLIER = 2.0
```

______________________________________________________________________

## Utility Packages

| Need               | Package                  | Key Functions                                                |
| ------------------ | ------------------------ | ------------------------------------------------------------ |
| Read/write JSON    | `aidb_common.io`         | `safe_read_json`, `safe_write_json`                          |
| Read/write YAML    | `aidb_common.io`         | `safe_read_yaml`, `safe_write_yaml`                          |
| Atomic writes      | `aidb_common.io`         | `atomic_write`                                               |
| File hashing       | `aidb_common.io`         | `compute_files_hash`, `compute_pattern_hash`                 |
| Path normalization | `aidb_common.path`       | `normalize_path`                                             |
| AIDB directories   | `aidb_common.path`       | `get_aidb_home`, `get_aidb_log_dir`, `get_aidb_adapters_dir` |
| Env vars (typed)   | `aidb_common.env`        | `read_str`, `read_bool`, `read_int`, `read_path`, `read_url` |
| Env validation     | `aidb_common.validation` | `validate_required_vars`, `validate_mutex_vars`              |
| Configuration      | `aidb_common.config`     | `ConfigManager`, `VersionManager`                            |
| Language detection | `aidb_common.discovery`  | `get_language_from_file`, `is_language_supported`            |

**Detailed documentation:** See docstrings in `src/aidb_common/` modules

______________________________________________________________________

## Discovery Commands

```bash
# Find constant usage
grep -r "CONSTANT_NAME" src --include="*.py"

# Find all constants files
find src -name "constants.py"

# Find all enums
grep -r "class.*Enum" src --include="*.py" -l

# Search for specific value
grep -r "5678" src --include="*.py"
```

______________________________________________________________________

## Import Patterns

```python
# ✅ GOOD: Import from package level
from aidb_common.io import safe_read_json
from aidb_common.path import normalize_path
from aidb_common.env import read_bool

# ❌ BAD: Import from internal modules
from aidb_common.io.files import safe_read_json  # Wrong
```

______________________________________________________________________

## When to Create NEW Constants

Only create NEW constants when:

1. **Truly new concept** - Not covered by existing constants
1. **Used 2+ times** - Will be reused
1. **Proper location** - Adding to the RIGHT constants file
1. **Following patterns** - Matches existing naming conventions
