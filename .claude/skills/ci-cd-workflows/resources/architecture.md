# Workflow Architecture

Core CI/CD workflow organization, patterns, and reusable components.

**Actual workflow files:** `.github/workflows/` | **Actions:** `.github/actions/`

## Workflow Organization

**Release** (`release-*.yaml`): `release-pr.yaml` (PR-based pipeline), `release-publish.yaml` (merge publishes)

**Testing** (`test-*.yaml`): `test-parallel.yaml` (main orchestrator, 10-15 min), `build-test-deps.yaml` (path-filtered builds)

**Adapters** (`adapter-*.yaml`): `adapter-build.yaml` (multi-platform), `adapter-build-act.yaml` (local dev)

**Maintenance** (`maintenance-*.yaml`): Version updates (weekly), Dependabot auto-merge

**Reusable**: `load-versions.yaml`, `test-suite.yaml`, `test-frameworks.yaml`, `build-adapters.yaml`, `build-docker.yaml`

## Key Patterns

### Job Dependencies

```yaml
# Sequential: build → test → deploy
test:
  needs: build

# Parallel with convergence: a,b,c → summary
summary:
  needs: [test-a, test-b, test-c]

# Diamond: setup → (a,b parallel) → integrate
build-a:
  needs: setup
integrate:
  needs: [build-a, build-b]
```

### Conditional Execution

- **Branch:** `if: github.ref == 'refs/heads/main'`
- **Event:** `if: github.event_name == 'pull_request'`
- **Combined:** `if: github.ref == 'refs/heads/main' && github.event_name == 'push'`

### Path Filters

`build-test-deps.yaml` triggers only on: `src/aidb/adapters/**`, `src/tests/_docker/**`, `.github/workflows/build-*.yaml`

Saves 5-10 min by skipping unnecessary builds.

### Dynamic Matrix

Generate from config file (single source of truth):

```yaml
generate-matrix:
  outputs:
    matrix: ${{ steps.generate.outputs.matrix }}
  steps:
    - run: echo "matrix=$(python .github/scripts/generate_matrix.py)" >> $GITHUB_OUTPUT

test:
  strategy:
    matrix: ${{ fromJSON(needs.generate-matrix.outputs.matrix) }}
```

### Timeout Guardrails

| Tier   | Minutes | Use Case                           |
| ------ | ------- | ---------------------------------- |
| Fast   | 5       | Validation, artifact consolidation |
| Medium | 15      | Builds, uploads, wait operations   |
| Build  | 20      | Multi-platform adapter builds      |
| Test   | 60      | Test suites, framework tests       |

## Reusable Workflows

### load-versions.yaml

Loads infrastructure versions from `versions.json` - eliminates hardcoding.

**Outputs:**

- `python-version`, `node-version`, `java-version`, `java-distribution` - Infrastructure versions
- `adapter-languages` - Comma-separated list (e.g., "python,javascript,java")
- `adapter-languages-json` - JSON array for matrix usage (e.g., `["python","javascript","java"]`)

```yaml
load-versions:
  uses: ./.github/workflows/load-versions.yaml

# Use in downstream jobs
downstream:
  needs: load-versions
  strategy:
    matrix:
      language: ${{ fromJson(needs.load-versions.outputs.adapter-languages-json) }}
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ needs.load-versions.outputs.python-version }}
```

### test-suite.yaml

Generic test runner for standard suites.

**Inputs:** `suite`, `suite-name`, `python-version`, `needs-adapters`, `needs-docker`, `skip-coverage`

```yaml
test-shared:
  uses: ./.github/workflows/test-suite.yaml
  with:
    suite: shared
    suite-name: Shared Tests
    python-version: ${{ needs.load-versions.outputs.python-version }}
    needs-adapters: true
    needs-docker: true
```

### build-adapters.yaml / build-docker.yaml

Build debug adapters and Docker images for testing. Require `python-version` input.

## Composite Actions

Located in `.github/actions/`:

| Action                    | Purpose                              |
| ------------------------- | ------------------------------------ |
| `setup-aidb-env`          | Checkout, Python setup, install deps |
| `setup-multi-lang`        | Node.js and Java setup               |
| `download-test-artifacts` | Conditional artifact download        |
| `run-aidb-tests`          | Execute tests, upload coverage       |

## Cross-Workflow Dependencies

GitHub workflows run independently. AIDB uses custom scripts for coordination:

### wait_for_check.py

Polls GitHub Checks API to wait for prerequisite check completion.

```yaml
- run: |
    python3 .github/scripts/wait_for_check.py \
      --ref ${{ github.event.pull_request.head.sha }} \
      --check-name "prerequisite-job" \
      --timeout 600
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### download_artifact.py

Downloads artifacts from other workflow runs.

```yaml
- run: |
    python3 .github/scripts/download_artifact.py \
      --workflow adapter-build.yaml \
      --commit ${{ github.sha }} \
      --name adapter-artifacts-all \
      --path /tmp/artifacts/
```

Both scripts use stdlib only (no dependencies), handle errors gracefully, and avoid third-party actions for security.

## Caching

**Dependency caching:** Built into `actions/setup-python@v5` with `cache: 'pip'`

**Docker layer caching:** Via `docker/build-push-action@v5` with `cache-from: type=gha`

**Custom caching:**

```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/adapters
    key: adapters-${{ hashFiles('versions.json') }}
```

## Secrets Management

```yaml
# Pass all secrets to reusable workflow
uses: ./.github/workflows/test.yaml
secrets: inherit

# Or explicit
secrets:
  api-token: ${{ secrets.API_TOKEN }}
```

## Error Handling

- `continue-on-error: true` - Step can fail without failing job
- `if: failure()` - Run only on failure
- `if: always()` - Run regardless of outcome

## Bootstrap Python Strategy

- **Python 3.11** - CI tooling (most workflows)
- **Python 3.10** - Release workflow (max PyPI compatibility)
- **Python 3.12** - Runtime tests (from `versions.json`)

## References

- `.github/workflows/` - Workflow definitions
- `.github/actions/` - Composite actions
- `.github/scripts/` - CI/CD scripts
- `versions.json` - Infrastructure versions
- `docs/developer-guide/ci-cd.md` - Complete documentation
