# Test Orchestration

Parallel test execution architecture and test suite organization.

**Main orchestrator:** `.github/workflows/test-parallel.yaml`

## Performance

- Wall-clock time: 10-15 minutes
- 50% faster than sequential
- Up to 10 parallel runners

## Execution Flow

```
load-versions (1 min)
    ↓
build-adapters + build-docker (parallel, 8-10 min)
    ↓
test suites (parallel): shared, cli, mcp, core, launch, frameworks
    ↓
summary (1 min)
```

## Test Suites

| Suite          | Purpose                              | Artifacts         | Time   |
| -------------- | ------------------------------------ | ----------------- | ------ |
| **shared**     | Language-agnostic debug fundamentals | Adapters + Docker | 5 min  |
| **cli**        | dev-cli commands and services        | None              | 4 min  |
| **mcp**        | MCP server and tool handlers         | Adapters + Docker | 6 min  |
| **core**       | Core API, DAP client, session mgmt   | Adapters          | 5 min  |
| **launch**     | VS Code launch.json integration      | Adapters + Docker | 4 min  |
| **common**     | Common utilities (path, config, env) | None              | 2 min  |
| **logging**    | Structured logging framework         | None              | 2 min  |
| **frameworks** | Flask, Express, Spring Boot, etc.    | Adapters + Docker | varies |

## Language-Grouped Framework Tests

Frameworks grouped by language (matches local dev-cli execution):

- **Python:** django, flask, fastapi, pytest
- **JavaScript:** express, jest
- **Java:** junit, springboot

Each runs: `./dev-cli test run -s frameworks -l {language}`

## Matrix Strategy

Language-specific suites use matrix for DRY:

```yaml
test-shared:
  strategy:
    matrix:
      language: [python, javascript, java]
```

Jobs display as: `test-shared (python)`, `test-shared (javascript)`, etc.

## Debug Logging

All workflows support `debug_logging` input:

```yaml
env:
  AIDB_LOG_LEVEL: ${{ (inputs.debug_logging == true) && 'TRACE' || 'INFO' }}
  AIDB_ADAPTER_TRACE: ${{ (inputs.debug_logging == true) && '1' || '0' }}
```

Trigger via: `gh workflow run test-parallel.yaml -f debug_logging=true`

## Adding New Suites

1. Add to dev-cli `src/aidb_cli/services/test/suites.py`
1. Add job to `test-parallel.yaml`:
   ```yaml
   test-new-suite:
     needs: [load-versions, build-adapters]
     uses: ./.github/workflows/test-suite.yaml
     with:
       suite: new-suite
       suite-name: New Suite Description
       python-version: ${{ needs.load-versions.outputs.python-version }}
       needs-adapters: true
   ```
1. Add to summary job `needs` array

## Caching

- **pip/npm/maven:** Cached via setup actions
- **Docker:** Layer caching via buildx + GitHub Actions cache
- **Adapters:** Keyed by `versions.yaml` hash

## Auto-Detecting Summary

Script `.github/scripts/format_job_summary.py` parses `${{ toJson(needs) }}` to auto-detect results. Generates markdown table, exits with failure if any job failed.

## References

- `.github/workflows/test-parallel.yaml` - Main orchestrator
- `.github/workflows/test-suite.yaml` - Reusable test runner
- `.github/workflows/test-frameworks.yaml` - Framework tests
- `.github/testing-config.yaml` - Framework configuration
- `docs/developer-guide/ci-cd.md` - Complete CI/CD reference
