# AIDB Troubleshooting Guide

**Purpose:** General troubleshooting guide for diagnosing AIDB issues across all components

This skill provides investigation workflows, log locations, common failure modes, and diagnostic commands for debugging AIDB.

## Related Skills

When troubleshooting specific components:

- **adapter-development** - Adapter-specific debugging
- **testing-strategy** - Test-specific debugging
- **ci-cd-workflows** - CI/CD pipeline debugging
- **mcp-tools-development** - MCP server debugging
- **dev-cli-development** - CLI command debugging

## Quick Start

When encountering AIDB issues:

1. **Reproduce** - Establish consistent reproduction
1. **Check Logs** - Start with `~/.aidb/log/aidb.log`
1. **Search Errors** - `grep -r "ERROR" ~/.aidb/log/`
1. **Identify Pattern** - Match to common failure mode
1. **Apply Fix** - Use component-specific guidance

For detailed investigation workflow, see [Investigation Workflow](resources/investigation-workflow.md).

## Resource Files

- **[Investigation Workflow](resources/investigation-workflow.md)** - Step-by-step triage playbook
- **[Log Locations Reference](resources/log-locations-reference.md)** - Where to find logs for each component
- **[Common Failure Modes](resources/common-failure-modes.md)** - Port conflicts, timeouts, permissions, etc.
- **[Environment Variables](resources/environment-variables.md)** - Debug env vars (AIDB_LOG_LEVEL, etc.)
- **[Diagnostic Commands](resources/diagnostic-commands.md)** - Command playbooks for investigation

## When to Use This Skill

Use this skill when:

1. Debugging AIDB behavior across any component
1. Investigating errors, crashes, or unexpected behavior
1. Performing root cause analysis (RCA)
1. Need to check logs or enable tracing
1. Unsure which component is causing the issue

**For component-specific implementation details**, route to the appropriate skill:

- Adapter issues → adapter-development
- Test failures → testing-strategy
- CI/CD failures → ci-cd-workflows

## Common Scenarios

### "AIDB is not working"

1. Check `~/.aidb/log/aidb.log` for errors
1. Check adapter installation: `ls ~/.aidb/adapters/`
1. See [Common Failure Modes](resources/common-failure-modes.md)

### "Session timeout"

1. Check adapter logs in `~/.aidb/log/adapter_traces/{language}/`
1. Enable tracing: `export AIDB_ADAPTER_TRACE=1`
1. Verify target file exists and is accessible
1. See timeout section in [Common Failure Modes](resources/common-failure-modes.md)

### "Port conflict"

1. Check if port in use: `lsof -i :PORT`
1. Kill process or configure different port
1. See port conflict section in [Common Failure Modes](resources/common-failure-modes.md)

## Environment Variables for Debugging

See [Environment Variables](resources/environment-variables.md) for complete reference.

**Quick reference:**

- `AIDB_LOG_LEVEL=DEBUG` - Verbose logging
- `AIDB_LOG_LEVEL=TRACE` - Maximum verbosity (includes DAP/LSP protocol payloads)
- `AIDB_ADAPTER_TRACE=1` - DAP protocol wire traces (separate files)
- `AIDB_CONSOLE_LOGGING=1` - Force console output
- `AIDB_DEBUG=1` - General debug mode

**Note:** `TRACE` level includes full JSON payloads for DAP/LSP messages and receiver timing metrics.

## Log Locations Quick Reference

See [Log Locations Reference](resources/log-locations-reference.md) for complete paths.

**System logs:** `~/.aidb/log/`

- `aidb.log` - Main application
- `mcp.log` - MCP server
- `cli.log` - CLI operations
- `adapter_traces/{language}/` - DAP protocol traces

**Test logs:**

- `.cache/container-data/aidb-test-{language}/` - Docker tests
- `pytest-logs/{suite}-{timestamp}/` - Local tests

## Routing to Component Skills

This skill provides general troubleshooting. For component-specific guidance:

**Adapter Issues:**

- Adapter not found → adapter-development
- Breakpoints not working → adapter-development
- Launch failures → adapter-development

**Test Issues:**

- Test failures → testing-strategy
- Test environment setup → testing-strategy
- Test debugging → testing-strategy

**CI/CD Issues:**

- Workflow failures → ci-cd-workflows
- Build failures → ci-cd-workflows
- Matrix configuration → ci-cd-workflows

**MCP Issues:**

- Tool errors → mcp-tools-development
- Response formatting → mcp-tools-development

**CLI Issues:**

- Command errors → dev-cli-development
- Service failures → dev-cli-development
