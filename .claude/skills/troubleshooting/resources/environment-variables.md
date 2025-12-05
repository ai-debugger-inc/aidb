# Environment Variables

AIDB environment variables for debugging and configuration.

## Quick Reference

**Debug:**

```bash
export AIDB_LOG_LEVEL=DEBUG           # Verbose logging
export AIDB_ADAPTER_TRACE=1           # DAP protocol traces
export AIDB_CONSOLE_LOGGING=1         # Console output
```

**Testing:**

```bash
export AIDB_TEST_MODE=1               # Enable test mode
```

## Log Control

### AIDB_LOG_LEVEL

Control application log verbosity.

**Values:** `TRACE` (ultra-verbose), `DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`

```bash
export AIDB_LOG_LEVEL=DEBUG  # Verbose for troubleshooting
export AIDB_LOG_LEVEL=TRACE  # Protocol-level details (DAP/LSP payloads)
```

**Use TRACE for:**

- Full DAP protocol JSON payloads
- Full LSP message JSON payloads
- Receiver timing metrics
- Orphan process scanning details

### AIDB_NO_FILE_LOGGING

Disable file logging (console only).

**Values:** `1` (disabled), unset (enabled, default)

```bash
export AIDB_NO_FILE_LOGGING=1  # CI/CD environments
```

### AIDB_CONSOLE_LOGGING

Force console output in addition to file.

**Values:** `1` (enabled), unset (disabled, default)

```bash
export AIDB_CONSOLE_LOGGING=1  # Live monitoring
```

### AIDB_MCP_LOG_LEVEL

MCP server log verbosity (separate from main app).

**Values:** Same as `AIDB_LOG_LEVEL`
**Default:** Inherits from `AIDB_LOG_LEVEL`

```bash
export AIDB_MCP_LOG_LEVEL=DEBUG  # MCP-specific debugging
```

## Tracing

### AIDB_ADAPTER_TRACE

Enable DAP protocol message tracing.

**Values:** `1` (enabled), unset (disabled, default)

**CRITICAL:** Set BEFORE starting session.

```bash
export AIDB_ADAPTER_TRACE=1
# Run operation
cat ~/.aidb/log/adapter_traces/{language}/*.adapter.log.1
```

**Output:** `~/.aidb/log/adapter_traces/{language}/`

**Use for:** Breakpoints not working, protocol errors, adapter crashes

### AIDB_DAP_REQUEST_WAIT_TIMEOUT

Timeout for DAP requests (seconds).

**Default:** `30`

```bash
export AIDB_DAP_REQUEST_WAIT_TIMEOUT=60  # Slow operations
```

## Testing

### AIDB_TEST_MODE

Enable test mode behaviors.

**Values:** `1` (enabled), unset (disabled)

```bash
export AIDB_TEST_MODE=1
```

### AIDB_DOCKER_TEST_MODE

Indicate Docker test environment (auto-set by dev-cli).

**Values:** `1` (enabled), unset (disabled)

**Automatically set by:** `./dev-cli test run`

### AIDB_TEST_JAVA_LSP_POOL

Enable JDT LS pooling for faster Java tests.

**Values:** `1` (enabled), unset (disabled)

```bash
export AIDB_TEST_JAVA_LSP_POOL=1  # Faster Java test execution
```

**Tradeoff:** Potential state leakage (worth it for speed)

### AIDB_TEST_ENV

Marker that tests are running.

**Automatically set by pytest fixtures.**

## Audit Logging

### AIDB_AUDIT_LOG

Enable audit logging (compliance/security).

**Values:** `1` (enabled), unset (disabled)

```bash
export AIDB_AUDIT_LOG=1
```

### AIDB_AUDIT_LOG_PATH

Audit log location.

**Default:** `~/.aidb/audit/`

```bash
export AIDB_AUDIT_LOG_PATH=/var/log/aidb/audit/
```

### AIDB_AUDIT_LOG_MB

Max file size (MB) before rotation.

**Default:** `10`

### AIDB_AUDIT_LOG_RETENTION_DAYS

Log retention period.

**Default:** `90`

### AIDB_AUDIT_LEVEL

Audit log verbosity.

**Default:** `INFO`

### AIDB_AUDIT_LOG_DAP

Include DAP protocol in audit log (very verbose).

**Values:** `1` (enabled), unset (disabled)

## MCP Configuration

### AIDB_MCP_MAX_SESSIONS

Maximum concurrent debug sessions.

**Default:** `10`

```bash
export AIDB_MCP_MAX_SESSIONS=20
```

### AIDB_MCP_MAX_BREAKPOINTS

Maximum breakpoints per session.

**Default:** `100`

### AIDB_MCP_OPERATION_TIMEOUT

Default timeout for MCP operations (seconds).

**Default:** `30`

### AIDB_MCP_SERVER_NAME

MCP server name.

**Default:** `ai-debugger`

### AIDB_MCP_EVENT_MONITORING

Enable MCP event monitoring/logging.

**Values:** `1` (enabled), unset (disabled)

## Language-Specific

### AIDB_JAVA_AUTO_COMPILE

Automatically compile Java files before debugging.

**Values:** `1` (enabled), unset (disabled)

```bash
export AIDB_JAVA_AUTO_COMPILE=1  # Slower startup, auto-compile
```

## Miscellaneous

### AIDB_DISABLE_TELEMETRY

Disable telemetry collection.

**Values:** `1` (disabled), unset (enabled)

```bash
export AIDB_DISABLE_TELEMETRY=1  # Privacy/offline
```

## Common Combinations

**Full debug mode:**

```bash
export AIDB_LOG_LEVEL=DEBUG
export AIDB_ADAPTER_TRACE=1
export AIDB_CONSOLE_LOGGING=1
export AIDB_MCP_LOG_LEVEL=DEBUG
```

**Test execution:**

```bash
export AIDB_TEST_MODE=1
export AIDB_LOG_LEVEL=INFO
```

**Java tests (fast):**

```bash
export AIDB_TEST_JAVA_LSP_POOL=1
export AIDB_LOG_LEVEL=DEBUG
```

**Adapter debugging:**

```bash
export AIDB_LOG_LEVEL=DEBUG
export AIDB_ADAPTER_TRACE=1
export AIDB_CONSOLE_LOGGING=1
```

**DAP protocol debugging:**

```bash
export AIDB_LOG_LEVEL=TRACE      # Enable protocol-level logging
export AIDB_ADAPTER_TRACE=1      # Enable DAP wire traces
export AIDB_CONSOLE_LOGGING=1    # Show in console
```

**CI/CD:**

```bash
export AIDB_LOG_LEVEL=INFO
export AIDB_NO_FILE_LOGGING=1
export AIDB_DISABLE_TELEMETRY=1
```

**Production:**

```bash
export AIDB_LOG_LEVEL=INFO
export AIDB_AUDIT_LOG=1
```

## Troubleshooting

**Variable not taking effect:**

```bash
# Verify set
echo $AIDB_LOG_LEVEL

# All AIDB variables
env | grep AIDB_
```

**Restart required:** Variables must be set before process starts.

**Conflicts:** Some override others (e.g., `AIDB_NO_FILE_LOGGING=1` disables file logging regardless).

**Persistence:**

```bash
# Temporary (current shell)
export AIDB_LOG_LEVEL=DEBUG

# Persistent (add to ~/.bashrc or ~/.zshrc)
echo 'export AIDB_LOG_LEVEL=DEBUG' >> ~/.bashrc
source ~/.bashrc
```

## Related Resources

- [Log Locations Reference](log-locations-reference.md) - Where logs are written
- [Investigation Workflow](investigation-workflow.md) - When to use debug vars
- [Diagnostic Commands](diagnostic-commands.md) - Verify variables
