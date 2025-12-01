# Test Session Isolation

## Overview

AIDB uses session-scoped directories to isolate test runs from each other. This enables:

- Parallel test execution without conflicts
- Historical log preservation for debugging
- Clean separation of container vs local test logs

## Session ID Format

**Pattern:** `{suite}-{YYYYMMDD-HHMMSS}`

**Examples:**

- `python-20251108-143022`
- `mcp-20251108-150315`
- `local-20251108-163045` (for local tests without suite)

## PytestLoggingService

Central service for managing pytest log directories with session isolation.

**Location:** `src/aidb_cli/services/test/pytest_logging_service.py`

**Key methods:**

- `generate_session_id(suite)` - Generate unique session ID
- `create_session_directory(session_id)` - Create session log dir
- `cleanup_all_locations(keep_count=10)` - Clean old sessions

**Usage example:**

```python
from aidb_cli.services/test/pytest_logging_service import PytestLoggingService

service = PytestLoggingService(repo_root, command_executor)

# Generate session ID
session_id = service.generate_session_id("python")  # "python-20251108-143022"

# Create directory
session_dir = service.create_session_directory(session_id)
# Returns: {repo_root}/pytest-logs/python-20251108-143022/

# Cleanup old sessions (keeps 10 most recent)
results = service.cleanup_all_locations()
```

## Container Data Structure

Session-scoped structure for Docker test containers:

```
.cache/container-data/
├── aidb-test-python/
│   └── {session-id}/           # e.g., python-20251108-143022
│       ├── log/                # AIDB application logs
│       │   ├── aidb.log
│       │   ├── adapter_traces/
│       │   └── ...
│       └── pytest/             # Pytest output
│           ├── pytest-captured.log
│           └── test-results.log
├── aidb-test-javascript/
│   └── {session-id}/
│       ├── log/
│       └── pytest/
└── aidb-test-java/
    └── {session-id}/
        ├── log/
        └── pytest/
```

**Environment variables:**

- `PYTEST_SESSION_ID` - Session identifier passed to Docker Compose for volume substitution
- `PYTEST_LOG_DIR` - Container mount point for pytest logs (`/workspace/pytest-logs`)

**Docker volume mounts:** Volume paths use `${PYTEST_SESSION_ID:-latest}` substitution to create session-scoped directories.

- Both `/root/.aidb/log` (AIDB internal logs) and `/workspace/pytest-logs` (pytest output) are session-isolated
- Framework runners and base services use identical session isolation patterns

## Cleanup Strategy

Automatic cleanup runs before each test execution:

- Keeps N most recent sessions (default: 10)
- Cleans both local (`pytest-logs/`) and container (`.cache/container-data/`) locations
- Deletes entire session directory (including log/ and pytest/ subdirs)

**Manual cleanup:**

```bash
rm -rf .cache/container-data/  # All container logs
rm -rf pytest-logs/             # All local logs
```

## Implementation Details

**Session ID Generation:**

- Uses UTC timezone for consistent timestamps
- Format: `{suite}-{YYYYMMDD-HHMMSS}`
- Implemented in `PytestLoggingService.generate_session_id()`

**Cleanup Algorithm:**

1. Find all directories matching session ID pattern (`{suite}-YYYYMMDD-HHMMSS`)
1. Parse timestamps and sort chronologically
1. Delete all except N most recent
1. Skip malformed directories and non-session directories

**Volume Mount Substitution:**

- `PYTEST_SESSION_ID` environment variable set in `TestExecutionService.prepare_test_environment()`
- Docker Compose reads env var for `${PYTEST_SESSION_ID:-latest}` substitution in volume paths
- Default fallback to `latest` if env var not set

## Testing

See `src/tests/aidb_cli/services/unit/test_pytest_logging.py` for comprehensive test examples:

- `test_generate_session_id_with_suite` - Session ID generation
- `test_cleanup_old_sessions_keeps_recent` - Cleanup logic
- `test_cleanup_all_locations_with_session_scoped_structure` - New structure cleanup

## Related

- **Constant:** `EnvVars.PYTEST_SESSION_ID` in `src/aidb_cli/core/constants.py`
- **Path utilities:** `CachePaths.container_data_dir()` in `src/aidb_cli/core/paths.py`
- **Test execution:** `TestExecutionService.prepare_test_environment()` in `src/aidb_cli/services/test/test_execution_service.py`
- **Docker templates:** `src/tests/_docker/templates/framework-test-runner.yaml.j2`
