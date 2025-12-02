# Docker-Based Testing Guide

## Quick Start

### 1. Build adapters (required first time)

```bash
./dev-cli adapters build
# or
./dev-cli adapters install-all
```

### 2. Run tests via dev-cli (recommended)

The `dev-cli` handles Docker orchestration and log streaming for you:

```bash
# Run shared integration tests (DebugInterface)
./dev-cli test shared

# Run generated program E2E tests
./dev-cli test generated

# Run all tests
./dev-cli test all
```

### 3. Direct docker-compose usage (alternative)

```bash
cd src/tests/_docker

# Run shared integration tests
docker compose --profile shared up shared-test-runner

# Run generated program tests
docker compose --profile generated up generated-program-test-runner

# Run specific profile
docker compose --profile core up
```

## Test Suites

### Shared Integration Tests (DebugInterface)

Tests the **zero-duplication testing pattern** where a single test runs against both MCP and API interfaces:

```bash
./dev-cli test shared
```

**What it tests:**

- DebugInterface abstraction (APIInterface + MCPInterface)
- Session lifecycle operations
- Breakpoint operations
- Execution control
- Tests run **twice**: once with MCP, once with API

**Test file:** `src/tests/aidb_shared/integration/test_basic_debugging.py`

### Generated Program E2E Tests

Tests using the **45 generated deterministic test programs** across all languages:

```bash
./dev-cli test generated
```

**What it tests:**

- 6 scenarios × 3 languages × 2 interfaces = **36 test variations**
- Scenarios: basic_variables, basic_for_loop, simple_function, basic_while_loop, conditionals, basic_exception
- Languages: Python, JavaScript, Java
- Interfaces: MCP and API

**Test file:** `src/tests/aidb_shared/e2e/test_generated_programs.py`

## Real-Time Log Persistence

Container logs are automatically streamed to `~/.aidb/log/test-container-output.log` in real-time during test execution:

```bash
# Watch logs in real-time while tests run
tail -f ~/.aidb/log/test-container-output.log

# Redirect all output to a file
./dev-cli test run -s shared > /tmp/test-output.log 2>&1

# Logs persist even if containers crash
docker rm -f aidb-shared-test  # Logs already saved!
```

This streaming happens **during execution**, not during cleanup, ensuring logs are never lost.

## Iterative Development

### Run tests interactively

```bash
docker compose run --rm shell

# Inside container:
cd /workspace
pytest src/tests/aidb_shared/integration/ -v -k test_breakpoint
```

### Run specific test file

```bash
docker compose run --rm test-runner \
  pytest src/tests/aidb_shared/integration/test_basic_debugging.py -v
```

### Run with specific language

```bash
docker compose run --rm test-runner \
  pytest src/tests/aidb_shared/ -v -k "python"
```

### Run with custom pytest args

```bash
PYTEST_ADDOPTS="-v -k test_basic_variables --tb=short" ./dev-cli test shared
```

## Troubleshooting

### Adapters not found

**Error**: "Adapters not found in /root/.aidb/adapters/"

**Solution**:

```bash
# Build adapters locally
./dev-cli adapters build

# Verify they exist
ls -la .cache/adapters/

# Should see python/, javascript/, java/
```

### Tests failing with import errors

**Error**: "ModuleNotFoundError: No module named 'aidb'"

**Cause**: Editable install failed in container

**Solution**:

```bash
# Run shell and debug
docker compose run --rm shell

# Inside container, verify install
python -c "import aidb; print(aidb.__file__)"
# Should show: /workspace/src/aidb/__init__.py

# If not, manually install
pip install -e .[test,dev]
```

### Container won't start

**Solution**:

```bash
# Check logs
docker compose logs test-runner

# Check healthcheck status
docker compose ps

# Rebuild if needed
docker compose build test-runner
```

## Performance Tips

### Parallel execution

```bash
PYTEST_PARALLEL=4 docker compose --profile shared up
```

### Skip slow tests

```bash
docker compose run --rm test-runner \
  pytest src/tests/aidb_shared/ -v -m "not slow"
```

### Run only fast unit tests

```bash
docker compose run --rm test-runner \
  pytest src/tests/aidb_shared/integration/ -v -k "lifecycle"
```

## CI Integration

For GitHub Actions, update `.github/workflows/test-parallel.yaml`:

```yaml
test-shared:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v5
    - name: Build adapters
      run: ./dev-cli adapters build
    - name: Run shared tests in Docker
      run: |
        cd src/tests/_docker
        docker compose --profile shared up shared-test-runner
```

## Architecture

### Docker Compose Generation

The `docker-compose.yaml` file is **automatically generated** from templates to support scalability:

**Source files:**

- `docker-compose.base.yaml` - Static services (utilities, etc.)
- `languages.yaml` - Language-specific metadata (adapters, healthchecks, etc.)
- `templates/*.j2` - Jinja2 templates for language services

**Generation:**

- Happens automatically when running `./dev-cli test run`
- Hash-based caching (only regenerates when sources change)
- Manual validation: `./dev-cli docker compose validate`
- Manual regeneration: `./dev-cli docker compose generate`

**Adding a new language:**

1. Add entry to `languages.yaml` (~15 lines)
1. Run `./dev-cli test run` (regenerates automatically)

### Docker Orchestration (via dev-cli)

The `dev-cli` handles:

- Auto-generating docker-compose.yaml if sources changed
- Launching docker-compose with correct profiles
- Streaming logs in real-time
- Setting environment variables (`AIDB_DOCKER_TEST_MODE=1`)
- Cleanup on completion

### Path Resolution (via docker_test_mode fixture)

Tests automatically use correct paths based on environment:

```python
# In Docker: AIDB_DOCKER_TEST_MODE=1
if docker_test_mode:
    base = Path("/workspace/src/tests/_assets/...")
else:
    base = Path(__file__).parent.parent / "_assets/..."
```

### Zero-Duplication Pattern (via DebugInterface)

Write once, test both MCP and API:

```python
@pytest.mark.parametrize("debug_interface", ["mcp", "api"], indirect=True)
async def test_breakpoint(debug_interface):
    # This test runs TWICE: once with MCP, once with API!
    await debug_interface.start_session(program="test.py")
    bp = await debug_interface.set_breakpoint(file="test.py", line=5)
    assert bp["line"] == 5
```

## Service Profiles

The docker-compose configuration uses profiles for selective service execution:

- `shared`: Shared integration tests (DebugInterface)
- `generated` / `e2e`: Generated program E2E tests
- Language profiles: `python`, `javascript`, `java` (framework tests)
- `mcp`: MCP integration tests
- `adapters`: Adapter testing

**Note**: Use `./dev-cli test <profile>` instead of direct docker-compose commands for better UX.
