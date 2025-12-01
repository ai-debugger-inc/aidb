# Debugging Test Failures

**CRITICAL:** Check logs BEFORE attempting fixes. Test output alone is insufficient.

______________________________________________________________________

## Log Locations

### Docker Tests (shared, frameworks, launch)

```bash
# Container logs
docker logs aidb-python-test
docker logs aidb-javascript-test
docker logs aidb-java-test

# AIDB logs inside container
docker exec aidb-python-test cat /root/.aidb/log/aidb.log

# Adapter trace logs
docker exec aidb-python-test ls -la /root/.aidb/log/
```

### Local Tests (cli, mcp, core)

```bash
# AIDB logs
cat ~/.aidb/log/aidb.log

# Adapter-specific logs
ls -la ~/.aidb/log/
```

______________________________________________________________________

## Investigation Workflow

1. **Read the error message** - What operation failed?
1. **Check test logs** - What was the last successful step?
1. **Check AIDB logs** - DAP message traces, adapter errors
1. **Check adapter logs** - debugpy/vscode-js-debug/java-debug output
1. **Reproduce locally** - Run single test with `-xvs`

```bash
# Single test with verbose output
./dev-cli test run -t "path/to/test.py::TestClass::test_method" -xvs

# With debug logging
AIDB_LOG_LEVEL=DEBUG ./dev-cli test run -t "test_file.py" -xvs
```

______________________________________________________________________

## Common Failure Patterns

### Timeout Waiting for Stopped Event

**Symptom:** `TimeoutError: Timeout waiting for stopped event`

**Causes:**

1. Breakpoint not verified (check `verified: true`)
1. Program exited before hitting breakpoint
1. Wrong line number for breakpoint

**Debug:**

```bash
grep -i "breakpoint" ~/.aidb/log/aidb.log
grep -i "stopped" ~/.aidb/log/aidb.log
```

### Port Already in Use

**Symptom:** `OSError: Address already in use`

**Fix:**

```bash
# Find and kill process
lsof -i :5678
kill -9 <PID>

# Or cleanup all AIDB processes
pkill -f debugpy
pkill -f node.*dapDebugServer
```

### Session Not Started

**Symptom:** `AssertionError: Session not active`

**Causes:**

1. Adapter failed to launch
1. DAP connection timeout
1. Missing dependencies

**Debug:**

```bash
# Check adapter process
ps aux | grep debugpy
ps aux | grep node.*debug
```

### Variable Not Found

**Symptom:** `KeyError: 'x'` when accessing variables

**Causes:**

1. Wrong scope (locals vs globals)
1. Variable not in frame
1. Program not paused at expected location

**Debug:**

```bash
# Check current position
grep -i "stopped.*line" ~/.aidb/log/aidb.log
```

______________________________________________________________________

## Useful Commands

```bash
# Grep for errors
grep -i "error\|exception\|failed" ~/.aidb/log/aidb.log

# Watch log in real-time
tail -f ~/.aidb/log/aidb.log

# Check DAP message flow
grep -E "sendRequest|onResponse|onEvent" ~/.aidb/log/aidb.log

# Check session state
grep -i "sessionstate\|status" ~/.aidb/log/aidb.log
```

______________________________________________________________________

## CI Failures

For CI-specific troubleshooting (GitHub Actions, artifacts, job logs), use the **ci-cd-workflows** skill's troubleshooting guide.

```bash
# Download CI artifacts
gh run download <run-id> -n test-logs-{suite}

# View CI logs
gh run view <run-id> --log
```
