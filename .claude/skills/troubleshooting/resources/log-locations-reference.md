# Log Locations Reference

Comprehensive guide to log file locations for all AIDB components.

## Quick Reference

**Primary logs:** `~/.aidb/log/`

- `aidb.log` - Main application
- `mcp.log` - MCP server
- `cli.log` - CLI operations
- `adapter_traces/{language}/` - DAP protocol traces

**Test logs:**

- `.cache/container-data/aidb-test-{language}/` - Docker tests
- `pytest-logs/{suite}-{timestamp}/` - Local tests

## System-Wide Logs

All system logs are written to `~/.aidb/log/` directory.

### Main Application Log

**Path:** `~/.aidb/log/aidb.log`

**Content:**

- Session lifecycle (start, stop, cleanup)
- Adapter initialization
- Breakpoint operations
- Variable inspection
- Execution control
- Errors and warnings

**Format:** Structured JSON logs

**Example investigation:**

```bash
# Check for errors
grep -E "(ERROR|CRITICAL)" ~/.aidb/log/aidb.log

# Monitor live
tail -f ~/.aidb/log/aidb.log

# Search for specific session
grep "session_id.*abc123" ~/.aidb/log/aidb.log
```

### MCP Server Log

**Path:** `~/.aidb/log/mcp.log`

**Content:**

- MCP tool invocations
- Server startup/shutdown
- Client connections
- Tool execution results
- Protocol errors

**Format:** Structured JSON logs

**Example investigation:**

```bash
# Check MCP tool errors
grep -i "error" ~/.aidb/log/mcp.log

# Find specific tool invocations
grep "tool_name.*breakpoint" ~/.aidb/log/mcp.log

# Monitor MCP activity
tail -f ~/.aidb/log/mcp.log
```

### CLI Operations Log

**Path:** `~/.aidb/log/cli.log`

**Content:**

- dev-cli command executions
- Service operations (Docker, testing)
- Adapter build operations
- Test orchestration
- Configuration changes

**Format:** Structured JSON logs

**Example investigation:**

```bash
# Check CLI errors
grep "ERROR" ~/.aidb/log/cli.log

# Find specific command execution
grep "command.*test run" ~/.aidb/log/cli.log

# Check adapter builds
grep "adapter.*build" ~/.aidb/log/cli.log
```

## Adapter Traces

DAP protocol message traces for each language adapter.

**Enable with:** `export AIDB_ADAPTER_TRACE=1`

### Python (debugpy)

**Path:** `~/.aidb/log/adapter_traces/python/`

**Files:**

- `python.adapter.log.{N}` - DAP protocol messages
- `python.pydevd.log.{N}` - pydevd internal logging
- `python.server.log.{N}` - Debug server logs

**Content:**

- DAP initialize/attach/launch requests
- Breakpoint set/verify messages
- Stack trace requests
- Variable evaluation
- Step/continue/pause operations

**Example investigation:**

```bash
# Check for DAP errors
grep -i "error" ~/.aidb/log/adapter_traces/python/*.adapter.log

# Find breakpoint verification
grep "setBreakpoints" ~/.aidb/log/adapter_traces/python/*.adapter.log

# Check latest trace
cat ~/.aidb/log/adapter_traces/python/python.adapter.log.1
```

### JavaScript (vscode-js-debug)

**Path:** `~/.aidb/log/adapter_traces/javascript/`

**Files:**

- `javascript.adapter.log.{N}` - DAP protocol messages
- `javascript.cdp.log.{N}` - Chrome DevTools Protocol messages
- `javascript.server.log.{N}` - Debug server logs

**Content:**

- DAP protocol messages
- Child session handling (Node.js subprocesses)
- CDP (Chrome DevTools Protocol) communication
- Source map resolution
- Runtime evaluation

**Example investigation:**

```bash
# Check for DAP errors
grep -i "error" ~/.aidb/log/adapter_traces/javascript/*.adapter.log

# Find child session events
grep "child.*session" ~/.aidb/log/adapter_traces/javascript/*.adapter.log

# Check CDP communication
cat ~/.aidb/log/adapter_traces/javascript/javascript.cdp.log.1
```

### Java (java-debug)

**Path:** `~/.aidb/log/adapter_traces/java/`

**Files:**

- `java.adapter.log.{N}` - DAP protocol messages
- `java.jdtls.log.{N}` - JDT Language Server logs
- `java.jdi.log.{N}` - Java Debug Interface logs
- `java.server.log.{N}` - Debug server logs

**Content:**

- DAP protocol messages
- JDT LS communication
- Classpath resolution
- Source location mapping
- JDI (Java Debug Interface) operations

**Example investigation:**

```bash
# Check for DAP errors
grep -i "error" ~/.aidb/log/adapter_traces/java/*.adapter.log

# Check classpath issues
grep "classpath" ~/.aidb/log/adapter_traces/java/java.jdtls.log.1

# Check JDI communication
cat ~/.aidb/log/adapter_traces/java/java.jdi.log.1
```

### Trace File Rotation

Adapter traces use numbered rotation:

- `.log.1` - Most recent
- `.log.2` - Previous
- `.log.3` - Older
- etc.

Always check `.log.1` for latest activity.

## Test Logs

### Docker Test Environment

**Location:** `.cache/container-data/aidb-test-{language}/{session-id}/`

**Session-scoped structure per language:**

```
.cache/container-data/aidb-test-python/
└── {session-id}/                # e.g., python-20251108-143022
    ├── log/
    │   ├── adapter_traces/
    │   │   └── python/          # Adapter DAP traces
    │   ├── aidb.log             # Main AIDB logs
    │   ├── cli.log              # CLI command logs
    │   └── mcp.log              # MCP server logs
    └── pytest/
        ├── pytest-captured.log  # Full test output with tracebacks
        └── test-results.log     # Test pass/fail summary
```

**Session ID Format:** `{suite}-{YYYYMMDD-HHMMSS}`

- Example: `python-20251108-143022`
- Enables isolated logs per test run
- Prevents log interference between parallel/consecutive runs

**Key files:**

- `pytest/pytest-captured.log` - Full test output, tracebacks
- `pytest/test-results.log` - Summary of pass/fail
- `log/aidb.log` - AIDB operations during tests
- `log/adapter_traces/{language}/` - DAP protocol traces

**Example investigation:**

```bash
# Find latest session
LATEST=$(ls -t .cache/container-data/aidb-test-python/ | head -1)

# Check test failures (latest session)
cat .cache/container-data/aidb-test-python/$LATEST/pytest/test-results.log | grep "FAILED"

# Or use wildcard for latest
cat .cache/container-data/aidb-test-python/python-*/pytest/test-results.log | grep "FAILED" | tail -20

# Get full traceback (specific session)
cat .cache/container-data/aidb-test-python/python-20251108-143022/pytest/pytest-captured.log | grep -A 50 "AssertionError"

# Check AIDB errors during tests
grep "ERROR" .cache/container-data/aidb-test-python/python-20251108-143022/log/aidb.log

# Check adapter communication
cat .cache/container-data/aidb-test-python/python-20251108-143022/log/adapter_traces/python/python.adapter.log.1
```

**Persistence:**

- Last 10 sessions preserved automatically
- Older sessions cleaned before each test run
- Useful for comparing across runs or debugging intermittent issues
- Manual cleanup: `rm -rf .cache/container-data/`

### Local Test Execution

**Primary location:** `pytest-logs/{suite}-{timestamp}/`

**Structure:**

```
pytest-logs/frameworks-20250104-143022/
├── pytest-captured.log          # Full test output
└── test-results.log            # Pass/fail summary
```

**Application logs:** `~/.aidb/log/`

- `aidb.log` - Main application
- `adapter_traces/{language}/` - DAP traces
- `mcp.log` - MCP server (if testing MCP)

**Example investigation:**

```bash
# Find latest test run
ls -lt pytest-logs/

# Check failures
cat pytest-logs/frameworks-*/test-results.log | grep "FAILED"

# Get full output
cat pytest-logs/frameworks-*/pytest-captured.log

# Check application logs
cat ~/.aidb/log/aidb.log | grep -E "(ERROR|CRITICAL)"

# Check adapter traces
cat ~/.aidb/log/adapter_traces/python/*.adapter.log.1
```

**Note:** Logs created per test run with timestamp.

## CI/CD Logs

For complete GitHub Actions guidance, see **ci-cd-workflows** skill.

**Quick reference:**

- GitHub Actions UI for workflow runs
- Job output in workflow summary
- Step logs for detailed output
- **Test log artifacts** (automatically uploaded on all test runs)

**Test Log Artifacts** (New as of 2025):

All test jobs automatically upload comprehensive logs as GitHub artifacts:

**Artifact naming:**

- `test-logs-cli`, `test-logs-mcp`, `test-logs-core`, etc.
- One artifact per test suite
- Overwrites on each run (only most recent logs retained)

**Artifact contents:**

- `pytest-logs/{session-id}/` - Pytest captured logs and test results
- `.cache/container-data/{container}/{session-id}/` - Docker container logs
- `.aidb/log/` - CLI and container output logs
- `test-output.log` - Full test execution output with pytest summary

**Retrieval:**

```bash
# List artifacts for a specific run
gh run view {run-id}

# Download specific suite logs
gh run download {run-id} -n test-logs-cli

# Download all test logs
gh run download {run-id} -p "test-logs-*"
```

**Retention:** 7 days (automatic cleanup)

**When to use:**

- CI test failures (logs preserved even after runner cleanup)
- Comparing test output across runs
- Debugging flaky tests in CI
- Accessing full pytest summary when job summary is truncated (>100 lines)

## Component-Specific Log Analysis

### When to Route to Component Skills

**Adapter logs** → **adapter-development**

- Breakpoint verification issues
- DAP protocol errors
- Launch/attach failures
- Language-specific debugging

**Test logs** → **testing-strategy**

- Test environment setup
- Framework test debugging
- DebugInterface issues
- Pytest-specific problems

**CI logs** → **ci-cd-workflows**

- Workflow failures
- Build errors
- Matrix configuration
- Runner issues

**MCP logs** → **mcp-tools-development**

- Tool invocation errors
- Response formatting
- Protocol compliance

**CLI logs** → **dev-cli-development**

- Command failures
- Service errors
- Docker issues

## Log Configuration

### Environment Variables

**Log Level:**

```bash
export AIDB_LOG_LEVEL=DEBUG    # Verbose logging
export AIDB_LOG_LEVEL=INFO     # Normal (default)
export AIDB_LOG_LEVEL=WARNING  # Warnings only
export AIDB_LOG_LEVEL=ERROR    # Errors only
```

**Log Output:**

```bash
export AIDB_NO_FILE_LOGGING=1  # Disable file logs
export AIDB_CONSOLE_LOGGING=1  # Force console output
```

**Adapter Tracing:**

```bash
export AIDB_ADAPTER_TRACE=1    # Enable DAP protocol traces
```

For complete environment variables, see [Environment Variables](environment-variables.md).

### Log Formats

All AIDB logs use **structured JSON format**:

```json
{
  "timestamp": "2025-01-04T14:30:22.123Z",
  "level": "INFO",
  "component": "session_manager",
  "message": "Session started successfully",
  "session_id": "abc123",
  "language": "python"
}
```

**Benefits:**

- Easy to parse programmatically
- Searchable by field
- Consistent across components

## Common Log Investigation Patterns

### Finding Session Errors

```bash
# All errors for a session
grep "session_id.*abc123" ~/.aidb/log/aidb.log | grep ERROR

# Session lifecycle
grep "session_id.*abc123" ~/.aidb/log/aidb.log | grep -E "(started|stopped|failed)"
```

### Finding Adapter Issues

```bash
# Adapter initialization
grep "adapter.*initialize" ~/.aidb/log/aidb.log

# DAP protocol errors
grep -i "dap.*error" ~/.aidb/log/adapter_traces/*/*.adapter.log.1

# Breakpoint verification
grep "breakpoint.*verified" ~/.aidb/log/adapter_traces/*/*.adapter.log.1
```

### Finding Test Failures

```bash
# Docker tests
cat .cache/container-data/aidb-test-{language}/{session-id}/pytest/pytest-captured.log | grep -A 20 "FAILED"

# Local tests
cat pytest-logs/*/pytest-captured.log | grep -A 20 "AssertionError"
```

### Live Monitoring

```bash
# Watch main log
tail -f ~/.aidb/log/aidb.log

# Watch specific component
tail -f ~/.aidb/log/mcp.log

# Watch adapter traces (after enabling AIDB_ADAPTER_TRACE=1)
tail -f ~/.aidb/log/adapter_traces/python/python.adapter.log.1
```
