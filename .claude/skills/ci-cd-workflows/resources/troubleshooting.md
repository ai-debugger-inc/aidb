# CI/CD Troubleshooting

Systematic diagnosis and resolution of CI/CD workflow issues.

## Investigation Workflow

### 1. Identify the Failure

- Which workflow/job/step failed?
- One-time or recurring?
- Recent changes?

**Where:** GitHub Actions UI → Failed run → Job summary → Step logs

### 2. Check Recent Changes

```bash
git log --oneline --follow .github/workflows/
git log --oneline versions.json
gh run view <run-id>
```

### 3. Reproduce Locally

```bash
./dev-cli test run --suite {suite}
./dev-cli adapters build --local
```

### 4. Analyze Logs

Look for: Error messages, stack traces, warnings before failure, dependency failures, network timeouts, permission errors.

### 5. Test Incrementally

```bash
./dev-cli test run --suite shared
./dev-cli test run -t "path/to/test.py"
./dev-cli test run --suite frameworks -p "*flask*"
```

## Common Issues

### Workflow Not Triggering

**Causes:** Trigger conditions not met, path filters exclude files, branch mismatch, workflow disabled, syntax error

```bash
gh workflow list
gh workflow enable "Workflow Name"
```

### Test Failures (CI vs Local)

**Causes:** Environment differences, missing adapters/Docker, race conditions, resource constraints

```bash
AIDB_LOG_LEVEL=DEBUG AIDB_ADAPTER_TRACE=1 ./dev-cli test run --suite shared
ls -la .cache/adapters/
docker images | grep aidb
```

### Adapter Build Failures

**Causes:** Upstream unavailable, version not found, platform incompatibility

```bash
curl -I https://github.com/microsoft/debugpy/releases/tag/v1.8.0
./dev-cli adapters build --local --language python
```

### Version Loading Failures

**Causes:** versions.json syntax error, missing fields, invalid structure

```bash
python -c "import json; json.load(open('versions.json'))"
```

### Docker Build Failures

**Causes:** Dockerfile errors, missing base image, network timeout, disk space

**Note:** Docker and adapter builds have automatic retry (3 attempts, 30s delay) via `.github/actions/retry-command` to handle transient network failures.

```bash
docker build -f src/tests/_docker/Dockerfile .
docker system prune -a
df -h
```

### Framework Test Failures

**Causes:** Test file naming (`test_*.py`), wrong directory, Docker/runtime issues

```bash
./dev-cli test run -s frameworks --collect-only
./dev-cli test run -s frameworks -l python
```

### Permission Errors

Check workflow permissions:

```yaml
permissions:
  contents: write
  packages: write
  pull-requests: write
```

Verify secrets: `GITHUB_TOKEN`, `PYPI_TOKEN`

### Caching Issues

```bash
gh cache list
gh cache delete <cache-id>
```

Force new cache by incrementing key version: `key: pip-v2-${{ hashFiles(...) }}`

### Artifact Issues

**Causes:** Path incorrect, name conflicts, size limit (2GB/file, 10GB total)

```bash
ls -lh dist/
du -sh dist/
```

### Timeout Issues

Set explicit timeouts:

```yaml
jobs:
  test:
    timeout-minutes: 30
    steps:
      - timeout-minutes: 15
        run: ./dev-cli test run
```

## Debugging Techniques

### Enable Debug Logging

Set repository secrets: `ACTIONS_STEP_DEBUG=true`, `ACTIONS_RUNNER_DEBUG=true`

### Add Debug Steps

```yaml
- name: Debug
  run: |
    echo "Python: $(python --version)"
    echo "PWD: $(pwd)"
    ls -la
```

### Use act for Local Testing

```bash
act -W .github/workflows/test-parallel.yaml
act -v -W .github/workflows/test-parallel.yaml
```

### Git Bisect

```bash
git bisect start
git bisect bad HEAD
git bisect good <last-good-commit>
```

## Performance Issues

**Symptoms:** Longer workflow times, queue times, resource exhaustion

```bash
gh run list --workflow=test-parallel.yaml --limit 10
```

**Optimization:** Increase parallelization, improve caching, reduce matrix, use path filtering

## Prevention

**Do:**

- Test locally with act
- Validate config before commit
- Pin action versions
- Add timeouts
- Keep workflows DRY

**Don't:**

- Hardcode values
- Skip validation
- Use `latest` tags
- Merge untested workflows

## Getting Help

**Tools:** `gh` CLI, `act`, `./dev-cli`

**Docs:** `docs/developer-guide/ci-cd.md`

**Issue template:**

```
Workflow: test-parallel.yaml
Run ID: https://github.com/.../actions/runs/12345
Error: [error message]
Recent changes: [what changed]
```
