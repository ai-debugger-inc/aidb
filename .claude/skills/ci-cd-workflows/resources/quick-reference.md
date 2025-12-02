# CI/CD Quick Reference

Commands, file locations, and links for CI/CD operations.

## Common Commands

### Local Testing

```bash
./dev-cli test run --suite {shared|cli|mcp|core|launch|frameworks}
./dev-cli test run -t "path/to/test.py"
./dev-cli test run -s frameworks -l python
./dev-cli test run -s ci_cd -m "not slow"
```

### Adapter Builds

```bash
./dev-cli adapters build --local
./dev-cli adapters build --local --use-host-platform
./dev-cli adapters build --local --language python
```

### Validation

```bash
actionlint .github/workflows/**/*.yaml
```

### GitHub CLI

```bash
gh run list --status=failure --limit 10
gh run view <run-id>
gh run watch <run-id>
gh run download <run-id> -n test-logs-{suite}
gh workflow run test-parallel.yaml -f debug_logging=true
gh cache list
gh cache delete <cache-id>
```

### act (Local CI)

```bash
act -l                              # List workflows
act -j test-shared                  # Run specific job
act push -j build                   # With event
act -W .github/workflows/test-parallel.yaml
```

## Key Files

| File                          | Purpose                                                        |
| ----------------------------- | -------------------------------------------------------------- |
| `versions.json`               | Infrastructure versions (Python, Node, Java), adapter versions |
| `.github/testing-config.yaml` | Framework test configuration                                   |
| `.github/dependabot.yaml`     | Dependabot configuration                                       |
| `.actrc`                      | Local CI configuration                                         |

## Workflow Files

| Workflow               | Trigger            | Purpose                       |
| ---------------------- | ------------------ | ----------------------------- |
| `test-parallel.yaml`   | push/PR to main    | Main test orchestrator        |
| `release-pr.yaml`      | PR from release/\* | Release pipeline              |
| `release-publish.yaml` | PR merge           | Publish draft release         |
| `adapter-build.yaml`   | release:published  | Multi-platform adapter builds |
| `build-test-deps.yaml` | path-filtered      | Adapter/Docker builds         |
| `load-versions.yaml`   | reusable           | Version loading               |
| `test-suite.yaml`      | reusable           | Generic test runner           |
| `pypi-publish.yaml`    | reusable           | Idempotent PyPI upload        |

## Composite Actions

Located in `.github/actions/`:

| Action                    | Purpose                       |
| ------------------------- | ----------------------------- |
| `setup-aidb-env`          | Python setup, install deps    |
| `setup-multi-lang`        | Node.js + Java setup          |
| `download-test-artifacts` | Conditional artifact download |
| `run-aidb-tests`          | Execute tests + coverage      |
| `extract-version`         | Parse release branch version  |
| `smoke-test`              | PyPI package verification     |
| `pypi-upload`             | Idempotent PyPI upload        |

## CI Scripts

Located in `.github/scripts/`:

| Script                       | Purpose                      |
| ---------------------------- | ---------------------------- |
| `format_job_summary.py`      | Auto-detect test results     |
| `format_test_summary.py`     | Format pytest output         |
| `build-adapter.py`           | Adapter build orchestrator   |
| `aggregate_flakes_report.py` | Aggregate flaky test reports |

## Version Management

- `versions.json` - Infrastructure & adapter versions (updated manually)
- `pyproject.toml` - App dependencies (Dependabot PRs)

**Dependabot branch flow:**

```
Dependabot PR → dependabot-updates (auto-merge) → release/X.Y.Z → main
```

## Workflow Triggers

| Event                      | Workflow             |
| -------------------------- | -------------------- |
| Push to main/develop       | test-parallel.yaml   |
| PR to main                 | test-parallel.yaml   |
| PR from release/\* to main | release-pr.yaml      |
| PR merge from release/\*   | release-publish.yaml |
| release:published          | adapter-build.yaml   |

## Debug Logging

Enable trace-level logs:

```bash
gh workflow run test-parallel.yaml -f debug_logging=true
```

Sets: `AIDB_LOG_LEVEL=TRACE`, `AIDB_ADAPTER_TRACE=1`, `AIDB_CONSOLE_LOGGING=1`

## Artifact Locations

**Test logs:** `gh run download <run-id> -n test-logs-{suite}`

Contents:

- `pytest-logs/` - Full pytest output
- `.cache/container-data/` - Docker/adapter logs
- `aidb-logs/` - Core library logs

## Complete Documentation

- `docs/developer-guide/ci-cd.md` - Complete CI/CD reference
