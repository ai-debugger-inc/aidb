# Investigation Workflow

Standard triage playbook for diagnosing AIDB issues across all components.

## Quick Reference

When AIDB behaves unexpectedly:

1. **Reproduce** - Establish consistent reproduction
1. **Check Logs** - Start with appropriate log locations
1. **Search Errors** - grep for error patterns
1. **Identify Failure Mode** - Match to common pattern
1. **Isolate Root Cause** - Binary search to minimal case
1. **Fix and Validate** - Apply fix, test, verify logs

## Step 1: Reproduce

**Goal:** Establish consistent reproduction before investigating.

### Questions to Answer

- Can you reproduce the issue consistently?
- What's the minimal reproduction case?
- Does it happen in all environments (local, Docker, CI)?
- What triggers the failure?

### Actions

1. Document exact steps to reproduce
1. Try to reduce to minimal case
1. Note any environmental differences
1. Check if issue is intermittent or consistent

**Example:**

```bash
# Test reproduction in different environments
# Local
pytest src/tests/specific_test.py::test_name

# Docker
./dev-cli test run -t src/tests/specific_test.py::test_name

# With debug logging
AIDB_LOG_LEVEL=DEBUG pytest src/tests/specific_test.py::test_name
```

## Step 2: Check Logs

**Goal:** Gather evidence from appropriate log locations.

**CRITICAL:** Check logs BEFORE attempting fixes. Test output alone is insufficient.

### System Logs

Start with the main AIDB log:

```bash
# Main application log
tail -f ~/.aidb/log/aidb.log

# Or for specific component
tail -f ~/.aidb/log/mcp.log      # MCP server
tail -f ~/.aidb/log/cli.log      # CLI operations
```

### Adapter Traces

If issue involves debugging sessions:

```bash
# Enable adapter tracing
export AIDB_ADAPTER_TRACE=1

# Check adapter logs (after reproduction)
cat ~/.aidb/log/adapter_traces/python/*.adapter.log
cat ~/.aidb/log/adapter_traces/javascript/*.adapter.log
cat ~/.aidb/log/adapter_traces/java/*.adapter.log
```

### Test Logs

If investigating test failures:

**Docker tests:**

```bash
cat .cache/container-data/aidb-test-{language}/{session-id}/pytest/pytest-captured.log
cat .cache/container-data/aidb-test-{language}/{session-id}/log/aidb.log
```

**Local tests:**

```bash
cat pytest-logs/{suite}-{timestamp}/pytest-captured.log
```

For complete log locations, see [Log Locations Reference](log-locations-reference.md).

### Enable Debug Logging

If initial logs are insufficient:

```bash
# Enable verbose logging
export AIDB_LOG_LEVEL=DEBUG

# Enable console output (in addition to file)
export AIDB_CONSOLE_LOGGING=1

# Enable adapter protocol traces
export AIDB_ADAPTER_TRACE=1

# Then reproduce the issue
```

For all debug variables, see [Environment Variables](environment-variables.md).

## Step 3: Search for Errors

**Goal:** Find error patterns in logs.

### Common Search Patterns

```bash
# Search all logs for errors
grep -r "ERROR" ~/.aidb/log/
grep -r "CRITICAL" ~/.aidb/log/
grep -r "Exception" ~/.aidb/log/
grep -r "Traceback" ~/.aidb/log/

# Search specific component
grep -i "error" ~/.aidb/log/aidb.log
grep -i "failed" ~/.aidb/log/adapter_traces/python/*.adapter.log

# With context (10 lines before/after)
grep -A 10 -B 10 "ERROR" ~/.aidb/log/aidb.log
```

### What to Look For

- **Stack traces** - Full error context
- **Error codes** - Specific failure reasons
- **Timing information** - When errors occurred
- **State transitions** - What was happening before failure
- **DAP protocol messages** - Request/response mismatches

For more diagnostic commands, see [Diagnostic Commands](diagnostic-commands.md).

## Step 4: Identify Failure Mode

**Goal:** Match observed behavior to known patterns.

### Common Failure Modes

1. **Port Conflicts**

   - Log evidence: "Address already in use"
   - Diagnosis: `lsof -i :PORT`

1. **Timeout Issues**

   - Log evidence: "Timed out waiting for..."
   - Diagnosis: Check adapter state, network

1. **DAP Protocol Errors**

   - Log evidence: "Invalid response", "Unexpected message"
   - Diagnosis: Enable `AIDB_ADAPTER_TRACE=1`

1. **Session Initialization Failures**

   - Log evidence: "Failed to initialize session"
   - Diagnosis: Check paths, permissions, classpath

1. **Adapter Not Found**

   - Log evidence: "Adapter binary not found"
   - Diagnosis: `ls ~/.aidb/adapters/`

1. **Permission Errors**

   - Log evidence: "Permission denied"
   - Diagnosis: `ls -la`, check owner

For detailed diagnosis and solutions, see [Common Failure Modes](common-failure-modes.md).

## Step 5: Isolate Root Cause

**Goal:** Reduce problem to minimal case for clear diagnosis.

### Binary Search Technique

Remove complexity until failure disappears:

1. Start with full failing scenario
1. Remove half the features/configuration
1. Does it still fail?
   - Yes → Problem in remaining half
   - No → Problem in removed half
1. Repeat until minimal case found

### Comparative Analysis

What's different between working and failing?

- Environment variables
- Configuration files
- Adapter versions
- Target program complexity
- Network/ports
- File permissions

### Example: Isolating Breakpoint Issue

```bash
# Full scenario fails
AIDB_LOG_LEVEL=DEBUG python test_complex_breakpoints.py

# Try minimal case
AIDB_LOG_LEVEL=DEBUG python test_simple_breakpoint.py

# If minimal case works, add complexity incrementally:
# - Add conditional breakpoints
# - Add multiple breakpoints
# - Add complex expressions
# Until failure reappears
```

## Step 6: Fix and Validate

**Goal:** Apply fix and verify it resolves the issue.

### Apply Fix

Based on root cause identified:

1. Implement fix
1. Document what was changed and why
1. Consider if fix applies to other components

### Test Minimal Case

```bash
# Verify minimal reproduction now passes
pytest src/tests/minimal_test.py -v

# Check logs show success
grep -i "error" ~/.aidb/log/aidb.log  # Should be empty
```

### Test Full Scenario

```bash
# Verify original failing scenario now passes
pytest src/tests/full_test.py -v

# Or run full test suite
./dev-cli test run -m unit
```

### Verify Logs

Confirm logs show expected behavior:

```bash
# Check for success indicators
grep "Session started successfully" ~/.aidb/log/aidb.log
grep "Breakpoint verified" ~/.aidb/log/adapter_traces/python/*.adapter.log

# Ensure no errors
grep -i "error" ~/.aidb/log/aidb.log  # Should be empty
```

## When to Route to Component Skills

### Adapter Issues

If investigation reveals adapter-specific problems:

- Breakpoints not working → **adapter-development**
- Adapter launch failures → **adapter-development**
- DAP protocol incompatibility → **adapter-development**
- Language-specific debugging → **adapter-development**

### Test Issues

If investigation is test-specific:

- Test environment setup → **testing-strategy**
- Test framework issues → **testing-strategy**
- DebugInterface debugging → **testing-strategy**
- Pytest-specific problems → **testing-strategy**

### CI/CD Issues

If investigation is CI-specific:

- Workflow failures → **ci-cd-workflows**
- Build failures → **ci-cd-workflows**
- Matrix configuration → **ci-cd-workflows**
- Runner issues → **ci-cd-workflows**

### MCP Issues

If investigation is MCP-specific:

- Tool invocation errors → **mcp-tools-development**
- Response formatting → **mcp-tools-development**
- Protocol compliance → **mcp-tools-development**

### CLI Issues

If investigation is CLI-specific:

- Command failures → **dev-cli-development**
- Service errors → **dev-cli-development**
- Docker issues → **dev-cli-development**

## Examples

### Example 1: Port Conflict

**Symptom:** AIDB session fails to start

**Investigation:**

```bash
# Step 1: Reproduce
pytest test_session.py -v  # Fails consistently

# Step 2: Check logs
tail ~/.aidb/log/adapter_traces/python/*.adapter.log
# Shows: "Address already in use: port 5678"

# Step 3: Search errors
grep "Address already in use" ~/.aidb/log/adapter_traces/python/*.adapter.log

# Step 4: Identify pattern → Port conflict

# Step 5: Isolate
lsof -i :5678  # Shows old debugpy process

# Step 6: Fix
kill -9 <PID>
pytest test_session.py -v  # Now passes
```

**Routing:** Port conflicts are general (covered here). If adapter-specific port configuration needed → adapter-development

### Example 2: Test Failure Investigation

**Symptom:** Test fails with "AssertionError: expected 'stopped', got 'running'"

**Investigation:**

```bash
# Step 1: Reproduce
./dev-cli test run -t test_breakpoint.py  # Fails

# Step 2: Check logs (Docker test)
cat .cache/container-data/aidb-test-python/pytest/pytest-captured.log | grep -A 50 "AssertionError"
cat .cache/container-data/aidb-test-python/log/adapter_traces/python/*.adapter.log

# Step 3: Search
# Found: Breakpoint never verified in DAP trace

# Step 4: Identify pattern → Breakpoint not working

# Step 5: Isolate → Adapter issue

# Step 6: Route to adapter-development skill for breakpoint debugging
```

**Routing:** Initial investigation general (here), breakpoint-specific debugging → adapter-development

## Critical Reminders

**NEVER skip logs** - Test output alone is insufficient for diagnosis

**Enable debug logging** - `AIDB_LOG_LEVEL=DEBUG` provides critical context

**Check adapter traces** - `AIDB_ADAPTER_TRACE=1` reveals protocol issues

**Reproduce consistently** - Intermittent issues require pattern recognition

**Document findings** - Leave breadcrumbs for future debugging
