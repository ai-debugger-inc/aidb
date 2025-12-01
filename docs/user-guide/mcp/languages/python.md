---
myst:
  html_meta:
    description lang=en: Python debugging with AI Debugger MCP - framework support, async debugging, and best practices.
---

# Python Debugging Guide

This guide covers Python-specific features and best practices for debugging with AI Debugger MCP.

```{include} /_snippets/about-examples-disclaimer.md
```

## Framework Support

AI Debugger provides example configurations for popular Python frameworks. Use the framework parameter in init to get framework-specific debugging templates.

### pytest

Debug Python tests using pytest with full support for fixtures, parametrized tests, and test discovery.

```{code-block} python
:caption: Debug a specific pytest test with breakpoints
:emphasize-lines: 8

# Get pytest example configuration
init(
    language="python",
    framework="pytest"
)

# Start debugging a specific test
session_start(
    target="pytest",
    args=["-xvs", "tests/test_calculator.py::TestCalculator::test_add"],
    breakpoints=[
        {
            "file": "/path/to/src/calculator.py",
            "line": 15
        }
    ]
)
```

**Debug test fixtures:**

```python
# Set breakpoints in both test and fixture code
session_start(
    target="pytest",
    args=["-xvs", "tests/test_api.py::test_user_creation"],
    breakpoints=[
        {
            "file": "/path/to/tests/conftest.py",
            "line": 42,
            "condition": "user.id == 123"
        },
        {
            "file": "/path/to/tests/test_api.py",
            "line": 78
        }
    ]
)
```

**Debug parametrized tests:**

```python
# Debug specific parameter combinations
session_start(
    target="pytest",
    args=[
        "-xvs",
        "tests/test_math.py::test_operations[add-5-3-8]"
    ],
    breakpoints=[
        {
            "file": "/path/to/tests/test_math.py",
            "line": 25,
            "condition": "operation == 'add'"
        }
    ]
)
```

:::{tip}
**Common pytest debugging patterns:**

- Use `-xvs` flags: `-x` stops on first failure, `-v` verbose, `-s` shows print statements
- Set breakpoints in `conftest.py` to debug fixtures
- Use conditional breakpoints to debug specific parameter values
- Set `PYTEST_CURRENT_TEST` environment variable to identify current test
:::

### Django

Debug Django applications including views, models, middleware, and management commands.

```{code-block} python
:caption: Debug Django views and models with the development server

# Get Django example configuration
init(
    language="python",
    framework="django"
)

# Start Django development server with debugging
session_start(
    target="python",
    args=["manage.py", "runserver", "--noreload"],
    env={
        "DJANGO_SETTINGS_MODULE": "myproject.settings"
    },
    breakpoints=[
        {
            "file": "/path/to/myapp/views.py",
            "line": 25
        },
        {
            "file": "/path/to/myapp/models.py",
            "line": 78
        }
    ]
)
```

:::{important}
**Always use `--noreload` flag** when debugging Django! The auto-reloader creates child processes that break debugger attachment.
:::

**Debug Django models:**

```python
# Set breakpoints in model methods and signals
session_start(
    target="python",
    args=["manage.py", "runserver", "--noreload"],
    breakpoints=[
        {
            "file": "/path/to/myapp/models.py",
            "line": 45,
            "log_message": "User.save() called: {self.username}"
        },
        {
            "file": "/path/to/myapp/signals.py",
            "line": 12
        }
    ]
)
```

**Debug Django management commands:**

```python
# Debug custom management commands
session_start(
    target="python",
    args=["manage.py", "import_data", "--batch-size", "100"],
    breakpoints=[
        {
            "file": "/path/to/myapp/management/commands/import_data.py",
            "line": 34,
            "condition": "batch_count > 5"
        }
    ]
)
```

**Debug Django middleware:**

```python
# Set breakpoints in middleware processing
session_start(
    target="python",
    args=["manage.py", "runserver", "--noreload"],
    breakpoints=[
        {
            "file": "/path/to/myapp/middleware.py",
            "line": 23,
            "condition": "request.user.is_authenticated"
        }
    ]
)
```

**Django debugging tips:**

- Always use `--noreload` flag to prevent the auto-reloader from interfering
- Set `DJANGO_SETTINGS_MODULE` to point to your settings file
- Use `justMyCode=False` to step into Django framework code
- Set breakpoints in `urls.py` to debug URL routing

### Flask

Debug Flask applications including routes, blueprints, and extensions.

**Debug Flask routes:**

```python
# Initialize with Flask framework
init(
    language="python",
    framework="flask"
)

# Start Flask app with debugging
session_start(
    target="python",
    args=["app.py"],
    env={
        "FLASK_APP": "app.py",
        "FLASK_ENV": "development"
    },
    breakpoints=[
        {
            "file": "/path/to/routes/api.py",
            "line": 45
        },
        {
            "file": "/path/to/models/user.py",
            "line": 78
        }
    ]
)
```

**Debug Flask blueprints:**

```python
# Set breakpoints in blueprint routes
session_start(
    target="python",
    args=["app.py"],
    breakpoints=[
        {
            "file": "/path/to/blueprints/auth.py",
            "line": 34,
            "condition": "user.role == 'admin'"
        },
        {
            "file": "/path/to/blueprints/api.py",
            "line": 56
        }
    ]
)
```

**Debug Flask extensions:**

```python
# Debug Flask-SQLAlchemy, Flask-Login, etc.
session_start(
    target="python",
    args=["app.py"],
    breakpoints=[
        {
            "file": "/path/to/extensions.py",
            "line": 12
        },
        {
            "file": "/path/to/utils/auth.py",
            "line": 23
        }
    ]
)
```

:::{tip}
**Flask debugging tips:**

- Set `FLASK_ENV=development` for better error messages
- Use `justMyCode=True` to skip Flask internals
- Set breakpoints in `before_request` and `after_request` handlers
- Debug template rendering with `jinja=True` configuration
:::

### FastAPI

Debug asynchronous FastAPI applications including endpoints, dependencies, and WebSockets.

**Debug FastAPI endpoints:**

```python
# Initialize with FastAPI framework
init(
    language="python",
    framework="fastapi"
)

# Start FastAPI with uvicorn
session_start(
    target="uvicorn",
    args=["main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
    breakpoints=[
        {
            "file": "/path/to/routers/users.py",
            "line": 32
        },
        {
            "file": "/path/to/core/database.py",
            "line": 15
        }
    ]
)
```

**Debug async endpoints:**

```python
# Set breakpoints in async functions
session_start(
    target="uvicorn",
    args=["main:app", "--reload"],
    breakpoints=[
        {
            "file": "/path/to/services/async_service.py",
            "line": 45,
            "log_message": "Processing request: {request_id}"
        }
    ]
)

# Step through async code
step(action="into")  # Step into async function
inspect(target="locals")  # Inspect async context
```

**Debug FastAPI dependencies:**

```python
# Set breakpoints in dependency injection functions
session_start(
    target="uvicorn",
    args=["main:app", "--reload"],
    breakpoints=[
        {
            "file": "/path/to/dependencies.py",
            "line": 23,
            "condition": "token is None"
        },
        {
            "file": "/path/to/routers/auth.py",
            "line": 67
        }
    ]
)
```

**Debug WebSockets:**

```python
# Debug WebSocket connections
session_start(
    target="uvicorn",
    args=["main:app", "--reload"],
    breakpoints=[
        {
            "file": "/path/to/websockets/chat.py",
            "line": 34,
            "log_message": "WebSocket message: {message}"
        }
    ]
)
```

:::{tip}
**FastAPI debugging tips:**

- Use `--reload` for development but be aware it may interfere with debugging
- Set `PYTHONASYNCIODEBUG=1` for async debugging details
- Use logpoints instead of breakpoints for high-frequency async operations
- Debug Pydantic validation with breakpoints in model validators
:::

## Virtual Environments

AI Debugger supports Python virtual environments.

### Virtual Environment Detection

:::{note}
The debugger automatically searches for virtual environments in common locations:

- `.venv/`
- `venv/`
- `env/`
- `.env/` (directory, not the config file)

No special configuration needed for standard virtual environment setups!
:::

```{code-block} python
:caption: Automatic virtual environment detection

# No special configuration needed
session_start(
    target="python",
    args=["main.py"]
)
```

### Explicit Python Interpreter

You can specify a custom Python interpreter either directly via parameters or through VS Code launch.json.

**Option 1: Direct parameter (via launch.json reference)**

```:json:.vscode/launch.json
{
  "type": "python",
  "request": "launch",
  "name": "Custom Python",
  "program": "${workspaceFolder}/main.py",
  "python": "/path/to/.venv/bin/python"
}
```

Then use the configuration:

```python
# Reference the launch configuration
session_start(
    launch_config_name="Custom Python"
)
```

**Note**: The `python_path` parameter is supported via launch.json configurations. Direct parameter usage is not currently exposed in the MCP interface - use launch.json for custom interpreter paths.

### Environment Variables from .env Files

Load environment variables from `.env` files via VS Code launch.json:

**Create launch.json configuration**

```:json:.vscode/launch.json
{
  "type": "python",
  "request": "launch",
  "name": "Python with .env",
  "program": "${workspaceFolder}/main.py",
  "envFile": "${workspaceFolder}/.env"
}
```

Then use the configuration:

```python
# Reference the launch configuration
session_start(
    launch_config_name="Python with .env"
)
```

**Note**: The `env_file` parameter is supported via launch.json configurations. Direct parameter usage is not currently exposed in the MCP interface - use launch.json for loading .env files.

**Example .env file:**

```bash
DATABASE_URL=postgresql://localhost/mydb
API_KEY=your-api-key-here
DEBUG=True
```

### Multiple Python Versions

Debug with different Python versions using launch.json configurations:

**Create multiple configurations in `.vscode/launch.json`:**

```:json:.vscode/launch.json
{
  "configurations": [
    {
      "type": "python",
      "request": "launch",
      "name": "Python 3.12",
      "program": "${workspaceFolder}/main.py",
      "python": "/usr/local/bin/python3.12"
    },
    {
      "type": "python",
      "request": "launch",
      "name": "Python 3.11",
      "program": "${workspaceFolder}/main.py",
      "python": "/usr/local/bin/python3.11"
    }
  ]
}
```

**Use them:**

```python
# Python 3.12
session_start(launch_config_name="Python 3.12")

# Python 3.11
session_start(launch_config_name="Python 3.11")
```

### Virtual Environment Tips

- Virtual environments are detected automatically in common locations (`.venv/`, `venv/`, `env/`)
- For non-standard Python installations, create a launch.json with custom `python` path
- Environment variables from `.env` files (via `envFile` in launch.json) override system environment
- Use `cwd` parameter in session_start to set working directory

## Async/Await Debugging

Python's async/await syntax requires special debugging techniques.

### Basic Async Debugging

**Debug async functions:**

```python
# Enable async debugging
session_start(
    target="python",
    args=["async_script.py"],
    env={
        "PYTHONASYNCIODEBUG": "1"
    },
    breakpoints=[
        {
            "file": "/path/to/async_script.py",
            "line": 25
        }
    ]
)
```

**Example async code:**

```python
# async_script.py
import asyncio

async def fetch_data(url):
    # Set breakpoint here (line 25)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def main():
    result = await fetch_data("https://api.example.com/data")
    print(result)

asyncio.run(main())
```

### Stepping Through Async Code

```python
# Step into async function
step(action="into")

# Inspect async context
inspect(target="locals")

# Continue to next await
execute(action="continue")
```

### Debugging Event Loops

**Monitor event loop state:**

```python
# Set breakpoint in event loop
breakpoint(
    action="set",
    location="/path/to/async_app.py:45",
    log_message="Event loop tasks: {len(asyncio.all_tasks())}"
)

# Inspect running tasks
variable(
    action="get",
    expression="asyncio.all_tasks()"
)
```

### Concurrent Async Operations

**Debug multiple concurrent tasks:**

```python
# Example: Debug concurrent API calls
# Set breakpoints with conditions to track specific tasks
breakpoint(
    action="set",
    location="/path/to/worker.py:34",
    condition="task_id == 'user-123'"
)

# Use logpoints for high-frequency async operations
breakpoint(
    action="set",
    location="/path/to/processor.py:56",
    log_message="Processing item {item_id} at {time.time()}"
)
```

### Debugging Async Generators

```python
# Debug async generators
session_start(
    target="python",
    args=["stream_processor.py"],
    breakpoints=[
        {
            "file": "/path/to/stream_processor.py",
            "line": 23,
            "condition": "count > 100"
        }
    ]
)

# Step through async iteration
step(action="over")  # Next iteration
inspect(
    target="expression",
    expression="current_value"
)
```

### Async/Await Best Practices

**Use logpoints for async operations:**

Breakpoints can slow down async code significantly. Use logpoints for monitoring:

```python
breakpoint(
    action="set",
    location="/path/to/async_handler.py:67",
    log_message="Request {request_id} processed in {elapsed_time}ms"
)
```

**Conditional breakpoints for async debugging:**

Only pause when specific conditions occur:

```python
breakpoint(
    action="set",
    location="/path/to/async_worker.py:45",
    condition="response.status_code != 200"
)
```

**Enable async debugging mode:**

Always set `PYTHONASYNCIODEBUG` for better async error messages:

```python
env={
    "PYTHONASYNCIODEBUG": "1"
}
```

## Common Patterns

### Just My Code vs. All Code

Control whether to debug only your code or include library code:

```python
# Debug only your code (default)
init(
    language="python",
    framework="pytest"
)

session_start(
    target="python",
    args=["main.py"]
)
```

**To debug library code, use VS Code launch.json:**

```json
{
    "type": "python",
    "request": "launch",
    "name": "Debug with Libraries",
    "program": "${workspaceFolder}/main.py",
    "justMyCode": false
}
```

Then reference it:

```python
session_start(
    launch_config_name="Debug with Libraries"
)
```

### Subprocess Debugging

Debug child processes spawned by multiprocessing or subprocess:

```python
# Enable subprocess debugging
session_start(
    target="python",
    args=["multiprocess_app.py"],
    env={
        "PYDEVD_USE_MULTIPROCESSING": "True"
    }
)
```

**Example multiprocessing code:**

```python
# multiprocess_app.py
from multiprocessing import Process

def worker(task_id):
    # Breakpoints work in child processes
    result = process_task(task_id)
    return result

if __name__ == "__main__":
    processes = [Process(target=worker, args=(i,)) for i in range(4)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()
```

### Advanced Breakpoint Examples

Conditional breakpoints, logpoints, and hit conditions are covered in detail in the [Advanced Workflows](../advanced-workflows.md#advanced-breakpoint-techniques) guide.


### Module vs. Script Execution

**Run Python scripts:**

```python
# Execute a .py file directly
session_start(
    target="script.py",
    args=["--arg1", "value1"]
)
```

**Run Python modules:**

```python
# Use the module name as target (framework-aware)
session_start(
    target="pytest",
    args=["-xvs", "tests/"]
)

# For custom modules, use -m via args
session_start(
    target="python",
    args=["-m", "mymodule", "--config", "prod.yaml"]
)
```

**Note**: The `module` parameter (to treat target as a Python module) is supported via launch.json configurations. For direct MCP usage, use the `-m` flag in args as shown above or use framework-aware targets like `pytest`.


### Remote Debugging

**Debug Python running in Docker:**

```python
# Attach to Python process in container
session_start(
    host="localhost",
    port=5678
)
```

**Start remote debugging in your code:**

```python
# In your Docker container or remote machine
import debugpy

debugpy.listen(("0.0.0.0", 5678))
debugpy.wait_for_client()

# Your application code here
```

**Docker Compose example:**

```yaml
# docker-compose.yaml
services:
  app:
    build: .
    ports:
      - "5678:5678"  # Debugger port
      - "8000:8000"  # App port
    environment:
      - PYTHONUNBUFFERED=1
```

### Exception Handling

**Break on exceptions:**

```python
# Subscribe to exception events
session_start(
    target="python",
    args=["main.py"],
    subscribe_events=["exception"]
)

# Set conditional breakpoint on error path
breakpoint(
    action="set",
    location="/path/to/handler.py:45",
    condition="isinstance(error, ValueError)"
)
```


## Common Pitfalls and Solutions

### Issue: Virtual Environment Not Detected

**Problem:** Debugger uses wrong Python interpreter.

**Solution:** Create a launch.json configuration:

```:json:.vscode/launch.json
{
  "type": "python",
  "request": "launch",
  "name": "Debug with venv",
  "program": "${workspaceFolder}/main.py",
  "python": "${workspaceFolder}/.venv/bin/python"
}
```

Then use it:

```python
session_start(launch_config_name="Debug with venv")
```

### Issue: Breakpoints Not Hit

**Problem:** Breakpoints in library code are skipped.

**Solution:** Disable `justMyCode` in launch.json:

```json
{
    "justMyCode": false
}
```

### Issue: Django Auto-Reloader Interferes

**Problem:** Django's auto-reloader breaks debugging.

**Solution:** Always use `--noreload`:

```python
session_start(
    target="python",
    args=["manage.py", "runserver", "--noreload"]
)
```

### Issue: Async Code Never Reaches Breakpoint

**Problem:** Async function completes before breakpoint check.

**Solution:** Use logpoints instead of breakpoints:

```python
breakpoint(
    action="set",
    location="/path/to/async_handler.py:45",
    log_message="Handler called with {args}"
)
```

### Issue: Import Errors in Tests

**Problem:** Module import fails during test debugging.

**Solution:** Set `PYTHONPATH` and `cwd`:

```python
session_start(
    target="pytest",
    args=["-xvs", "tests/"],
    cwd="${workspace_root}",
    env={
        "PYTHONPATH": "${workspace_root}/src"
    }
)
```

## Advanced Patterns

### Debug with Poetry

Poetry projects are automatically detected if a `.venv` folder exists in the workspace. No special configuration needed.

### Debug with Pipenv

Pipenv projects are automatically detected if a `.venv` folder exists in the workspace. No special configuration needed.

## Python Debugging Limitations

:::{note}
**Python has full debugging support with no significant limitations:**

✅ All hit condition modes supported (`>`, `>=`, `=`, `<`, `<=`, `%`, exact)
✅ All debugging features fully functional
✅ Conditional breakpoints, logpoints, and advanced breakpoint features work perfectly
✅ Both launch and attach modes fully supported

For general limitations across all languages, see [Known Limitations](../core-concepts.md#known-limitations).
:::
