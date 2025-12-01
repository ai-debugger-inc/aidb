---
myst:
  html_meta:
    description lang=en: Advanced debugging workflows - common framework examples, remote debugging, multi-session, and advanced breakpoint techniques.
---

# Advanced Workflows

This guide covers advanced debugging scenarios including common framework debugging patterns, remote debugging, multi-session management, and advanced breakpoint techniques.

:::{note}
**About the Examples**: The code examples show MCP tool parameters that your AI assistant will use. These are not Python functions - AI Debugger is an MCP server that communicates via the Model Context Protocol.
:::

## Common Framework Debugging Patterns

The `init` tool provides example configurations for popular frameworks. These templates include typical target files, arguments, and environment variables to help you get started quickly.

### Python Frameworks

#### pytest - Testing Framework

Debug individual tests or entire test suites with precise breakpoint placement:

```python
# Initialize and get pytest example configuration
init(language="python", framework="pytest", workspace_root="/path/to/project")

# Start debugging a specific test
session_start(
    target="pytest",
    args=["-xvs", "tests/test_calculator.py::TestMath::test_division"],
    breakpoints=[
        {
            "file": "/path/to/src/calculator.py",
            "line": 42,
            "condition": "divisor == 0"
        },
        {
            "file": "/path/to/tests/test_calculator.py",
            "line": 15
        }
    ]
)
```


#### Django - Web Framework

Debug Django views, models, and middleware during development:

```python
# Get Django example configuration
init(language="python", framework="django", workspace_root="/path/to/django_project")

# Debug a specific API endpoint
session_start(
    target="python",
    args=["manage.py", "runserver", "8000", "--noreload"],
    env={"DJANGO_SETTINGS_MODULE": "myproject.settings"},
    breakpoints=[
        {
            "file": "/path/to/myapp/views.py",
            "line": 45,
            "condition": "request.user.is_authenticated"
        },
        {
            "file": "/path/to/myapp/models.py",
            "line": 123
        }
    ]
)
```


#### FastAPI - Modern Web Framework

Debug async endpoints and dependency injection:

```python
init(language="python", framework="fastapi", workspace_root="/path/to/api")

session_start(
    target="uvicorn",
    args=["main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
    breakpoints=[
        {
            "file": "/path/to/routers/users.py",
            "line": 32
        },
        {
            "file": "/path/to/services/auth.py",
            "line": 89,
            "condition": "user_id not in cache"
        }
    ]
)
```


#### Flask - Lightweight Web Framework

```python
init(language="python", framework="flask")

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
            "line": 78,
            "condition": "email.endswith('@admin.com')"
        }
    ]
)
```

### JavaScript/TypeScript Frameworks

#### Jest - Testing Framework

Debug React, Vue, or Node.js tests:

```javascript
// Initialize for Jest
init(language="javascript", framework="jest")

// Debug specific test suite
session_start({
    target: "npm",
    args: ["test", "--", "--runInBand", "--no-coverage", "src/__tests__/Calculator.test.js"],
    breakpoints: [
        {
            file: "/path/to/src/utils/calculator.js",
            line: 15,
            condition: "result > 1000"
        },
        {
            file: "/path/to/src/services/api.js",
            line: 42
        }
    ]
})
```


#### Express - Node.js Web Framework

Debug Express routes, middleware, and error handlers:

```javascript
init(language="javascript", framework="express")

session_start({
    target: "node",
    args: ["server.js"],
    env: {
        PORT: "3000",
        NODE_ENV: "development"
    },
    breakpoints: [
        {
            file: "/path/to/routes/users.js",
            line: 23
        },
        {
            file: "/path/to/middleware/auth.js",
            line: 45,
            condition: "!req.headers.authorization"
        }
    ]
})
```



### Java Frameworks

#### JUnit - Testing Framework

Debug Java unit tests with Maven or Gradle:

```java
// Initialize for JUnit
init(language="java", framework="junit")

// Debug specific test method
session_start({
    target: "mvn",
    args: ["test", "-Dtest=UserServiceTest#testUserCreation"],
    breakpoints: [
        {
            file: "/path/to/src/main/java/com/example/service/UserService.java",
            line: 42
        },
        {
            file: "/path/to/src/main/java/com/example/repository/UserRepository.java",
            line: 78,
            condition: "user.getEmail() == null"
        }
    ]
})
```


#### Spring Boot - Enterprise Framework

Debug Spring Boot applications, REST controllers, and services:

```java
init(language="java", framework="spring")

session_start({
    target: "java",
    args: ["-jar", "target/app.jar"],
    env: {
        SPRING_PROFILES_ACTIVE: "debug",
        SERVER_PORT: "8080"
    },
    breakpoints: [
        {
            file: "/path/to/src/main/java/com/example/controller/ApiController.java",
            line: 35
        },
        {
            file: "/path/to/src/main/java/com/example/service/BusinessService.java",
            line: 89,
            condition: "result == null"
        }
    ]
})
```


## Remote Debugging

Debug applications running in remote environments, containers, or on different hosts.

### Remote Attach Modes

AI Debugger supports three attachment modes:

1. `launch` - Start and debug a new process (default)
2. `attach` - Attach to a local process by PID
3. `remote_attach` - Attach to a remote debugger server (host:port)

### Docker Container Debugging

#### Python in Docker

**Step 1: Configure the container to expose debugger port**

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install debugpy
RUN pip install debugpy

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Expose application and debugger ports
EXPOSE 8000 5678

# Start with debugpy
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "app.py"]
```

**Step 2: Run container with port mapping**

```bash
docker run -p 8000:8000 -p 5678:5678 myapp:latest
```

**Step 3: Attach debugger with path mappings**

```python
init(language="python", mode="remote_attach")

session_start(
    host="localhost",
    port=5678,
    breakpoints=[
        {
            "file": "/app/services/payment.py",  # Remote path
            "line": 156
        }
    ]
)
```


#### JavaScript/Node.js in Docker

```dockerfile
# Dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000 9229

# Start with Node inspector
CMD ["node", "--inspect=0.0.0.0:9229", "server.js"]
```

```bash
docker run -p 3000:3000 -p 9229:9229 myapp:latest
```

```javascript
init({language: "javascript", mode: "remote_attach"})

session_start({
    host: "localhost",
    port: 9229,
    breakpoints: [
        {
            file: "/app/routes/api.js",
            line: 89
        }
    ]
})
```

#### Java in Docker

```dockerfile
# Dockerfile
FROM eclipse-temurin:17-jre

WORKDIR /app

COPY target/app.jar .

EXPOSE 8080 5005

# Enable JDWP debugging
CMD ["java", "-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:5005", "-jar", "app.jar"]
```

```bash
docker run -p 8080:8080 -p 5005:5005 myapp:latest
```

```java
init({language: "java", mode: "remote_attach"})

session_start({
    host: "localhost",
    port: 5005,
    breakpoints: [
        {
            file: "/app/src/main/java/com/example/controller/ApiController.java",
            line: 45
        }
    ]
})
```

### Remote Server Debugging

#### SSH Tunnel for Secure Remote Debugging

**Scenario:** Debug application on production-like staging server

```bash
# On remote server (staging.example.com)
# Start Python app with debugpy
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client app.py

# On local machine - create SSH tunnel
ssh -L 5678:localhost:5678 user@staging.example.com
```

```python
# Now attach locally as if it were on localhost
init(language="python", mode="remote_attach")

session_start(
    host="localhost",  # Goes through SSH tunnel
    port=5678,
    breakpoints=[
        {
            "file": "/var/www/app/services/billing.py",
            "line": 234,
            "condition": "amount > 10000"  # Only debug large transactions
        }
    ]
)

execute(action="continue", wait_for_stop=True)

# Safe to debug production-like environment
inspect(target="locals")
```

#### Kubernetes Pod Debugging

**Step 1: Forward debugger port from pod**

```bash
# List pods
kubectl get pods

# Forward debugger port
kubectl port-forward pod/api-deployment-abc123 5678:5678
```

**Step 2: Attach debugger**

```python
init(language="python", mode="remote_attach")

session_start(
    host="localhost",
    port=5678,
    breakpoints=[
        {
            "file": "/app/services/api.py",
            "line": 123
        }
    ]
)
```


### Path Mappings

Path mappings are critical when debugging remotely - they translate between local file paths and remote file paths.

:::{note}
**Python with path mappings:**

Currently, path mappings are implicit in Python. The debugger uses the file paths from breakpoint specifications which should match the remote paths.

```python
session_start(
    host="localhost",
    port=5678,
    breakpoints=[
        {
            "file": "/app/services/api.py",  # Use remote path
            "line": 45
        }
    ]
)
```
:::

:::{caution}
**JavaScript with explicit path mappings:**

Not yet fully implemented in MCP layer. Use launch.json for complex path mapping scenarios.
:::

:::{tip}
**Workaround using launch.json:**

For complex path mapping scenarios, create a launch configuration:

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Remote Attach Docker",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}/app",
          "remoteRoot": "/app"
        }
      ]
    }
  ]
}
```

Then reference it in your session:

```python
init(language="python", workspace_root="/path/to/project")

session_start(
    launch_config_name="Remote Attach Docker"
)
```
:::

## Multi-Session Debugging

Debug multiple programs simultaneously, perfect for microservices, distributed systems, or parallel test execution.

### Managing Multiple Sessions

Each debugging session has a unique session ID. When you start a new session, it becomes the default session. To interact with older sessions, explicitly pass the session_id.

#### Basic Multi-Session Pattern

```python
# Initialize once
init(language="python")

# Start first session
session1_info = session_start(
    target="python",
    args=["service1.py"],
    breakpoints=[{"file": "/app/service1.py", "line": 45}]
)
session1_id = session1_info["session_id"]

# Start second session - this becomes the new default
session2_info = session_start(
    target="python",
    args=["service2.py"],
    breakpoints=[{"file": "/app/service2.py", "line": 89}]
)
session2_id = session2_info["session_id"]

# Interact with second session (current default)
execute(action="continue", wait_for_stop=True)
inspect(target="locals")

# Interact with first session - MUST pass session_id
execute(action="continue", session_id=session1_id, wait_for_stop=True)
inspect(target="locals", session_id=session1_id)

# List all active sessions
session(action="list")
```

### Microservices Debugging Pattern


### Session Management Strategies

#### Strategy 1: Explicit Session IDs (Recommended)

Always store and pass session IDs explicitly:

```python
# Track all session IDs
sessions = {}

# Start sessions
sessions["frontend"] = session_start(...)["session_id"]
sessions["backend"] = session_start(...)["session_id"]
sessions["worker"] = session_start(...)["session_id"]

# Always use explicit IDs
execute(action="continue", session_id=sessions["frontend"])
inspect(target="locals", session_id=sessions["backend"])
breakpoint(action="set", location="worker.py:45", session_id=sessions["worker"])
```

#### Strategy 2: Context Manager Pattern (Conceptual)

```python
# Conceptual pattern - helps organize multi-session code
class SessionContext:
    def __init__(self, session_id):
        self.session_id = session_id

    async def execute(self, **kwargs):
        return await execute(session_id=self.session_id, **kwargs)

    async def inspect(self, **kwargs):
        return await inspect(session_id=self.session_id, **kwargs)

    async def step(self, **kwargs):
        return await step(session_id=self.session_id, **kwargs)

# Use it
api_ctx = SessionContext(api_session["session_id"])
db_ctx = SessionContext(db_session["session_id"])

await api_ctx.execute(action="continue", wait_for_stop=True)
await db_ctx.inspect(target="locals")
```

### Parallel Test Debugging

Debug multiple test suites simultaneously:

```python
init(language="python", framework="pytest")

# Start test suite 1
unit_tests = session_start(
    target="pytest",
    args=["tests/unit", "-xvs"],
    breakpoints=[
        {"file": "/app/src/calculator.py", "line": 45}
    ]
)

# Start test suite 2
integration_tests = session_start(
    target="pytest",
    args=["tests/integration", "-xvs"],
    breakpoints=[
        {"file": "/app/src/api_client.py", "line": 123}
    ]
)

# Monitor both
execute(action="continue", session_id=unit_tests["session_id"])
execute(action="continue", session_id=integration_tests["session_id"])
```

## Advanced Breakpoint Techniques

Master sophisticated breakpoint strategies for complex debugging scenarios.

### Conditional Breakpoints

Break only when specific conditions are met, essential for debugging large datasets and loops.

#### Basic Conditional Breakpoints

```python
# Break only when user is admin
breakpoint(
    action="set",
    location="/app/views.py:45",
    condition="user.role == 'admin'"
)

# Break on null/None values
breakpoint(
    action="set",
    location="/app/service.py:89",
    condition="result is None"
)

# Break on specific IDs
breakpoint(
    action="set",
    location="/app/handlers.py:123",
    condition="customer_id == '550e8400-e29b-41d4-a716-446655440000'"
)
```

#### Complex Conditions

```python
# Multiple conditions
breakpoint(
    action="set",
    location="/app/payment.py:156",
    condition="amount > 1000 and currency == 'USD' and not is_verified"
)

# String operations
breakpoint(
    action="set",
    location="/app/auth.py:67",
    condition="email.endswith('@admin.com') or email.startswith('support+')"
)

# Collection operations
breakpoint(
    action="set",
    location="/app/processor.py:234",
    condition="len(items) > 100 or any(item.price > 500 for item in items)"
)

# Nested attribute access
breakpoint(
    action="set",
    location="/app/models.py:89",
    condition="user.profile.settings.notifications_enabled == False"
)
```


### Hit Count Breakpoints

Break only after a breakpoint has been hit a certain number of times - perfect for debugging loops and iterative processes.

#### Hit Count Operators

Hit conditions support several operators:

- `== N` or just `N` - Break on the Nth hit
- `> N` - Break after more than N hits
- `>= N` - Break after N or more hits
- `% N` - Break every Nth hit (modulo)

:::{important}
**Language Support:**

- Python: `==`, `>`, `>=`, `<`, `<=`, `%`
- JavaScript: `==`, `>`, `>=`, `<`, `<=`, `%`
- Java: Plain integers only (e.g., `"5"` for exactly the 5th hit). No operators supported.
:::

```python
# Break on the 100th iteration
breakpoint(
    action="set",
    location="/app/loop.py:45",
    hit_condition="== 100"
)

# Break after 1000 iterations (to skip initialization phase)
breakpoint(
    action="set",
    location="/app/processor.py:89",
    hit_condition="> 1000"
)

# Break every 500th iteration (sample every 500 items)
breakpoint(
    action="set",
    location="/app/batch.py:123",
    hit_condition="% 500"
)
```


### Logpoints

Log messages without stopping execution - perfect for production debugging and understanding control flow.

#### Basic Logpoints

```python
# Log without stopping
breakpoint(
    action="set",
    location="/app/service.py:45",
    log_message="Processing user {user_id} at {datetime.now()}"
)

# Log variable values
breakpoint(
    action="set",
    location="/app/api.py:89",
    log_message="Request: {request.method} {request.path}, Status: {response.status_code}"
)

# Log complex expressions
breakpoint(
    action="set",
    location="/app/processor.py:123",
    log_message="Items processed: {len(results)}, Errors: {sum(1 for r in results if r.error)}"
)
```


### Combining Conditions and Hit Counts

Combine conditional breakpoints with hit counts for maximum precision.

```python
# Break on 100th occurrence of error condition
breakpoint(
    action="set",
    location="/app/processor.py:156",
    condition="result.status == 'error'",
    hit_condition="== 100"
)

# Log every 500th successful transaction, break on errors
breakpoint(
    action="set",
    location="/app/payment.py:234",
    condition="amount > 0 and status == 'success'",
    hit_condition="% 500",
    log_message="Transaction {transaction_id}: ${amount}"
)

# But also break immediately on any failed transaction
breakpoint(
    action="set",
    location="/app/payment.py:234",
    condition="status == 'failed'"
)
```


### Column-Level Breakpoints

For minified code or precise breakpoint placement on lines with multiple statements.

```python
# Break at specific column in minified JavaScript
breakpoint(
    action="set",
    location="/app/bundle.min.js:1",
    column=45678
)

# Alternative: use file:line:column format
breakpoint(
    action="set",
    location="/app/bundle.min.js:1:45678"
)
```


### Breakpoint Management

```python
# List all breakpoints
breakpoint(action="list")

# Remove specific breakpoint
breakpoint(action="remove", location="/app/service.py:45")

# Clear all breakpoints
breakpoint(action="clear_all")

# Verify breakpoint status
bp_list = breakpoint(action="list")
for bp in bp_list["breakpoints"]:
    print(f"Breakpoint at {bp['location']}: verified={bp.get('verified', False)}")
```

## Best Practices

### Framework Debugging

1. **Use framework-specific configurations** - Let `init()` detect your framework for optimized settings
1. **Set breakpoints in business logic, not framework code** - Debug your code, not Django's internals
1. **Use `--noreload` flags** - Prevent auto-reloading during debugging sessions
1. **Check launch.json first** - Existing VS Code configurations can be reused

### Remote Debugging

1. **Use SSH tunnels for production** - Never expose debugger ports to the internet
1. **Always use conditional breakpoints in production** - Minimize impact on running services
1. **Prefer logpoints over breakpoints** - Gather data without stopping execution
1. **Use path mappings correctly** - Remote paths must match container/server paths
1. **Clean up sessions** - Always stop remote debugging sessions when done

### Multi-Session Debugging

1. **Store session IDs explicitly** - Don't rely on default session behavior
1. **Use descriptive session tracking** - `sessions = {"api": id1, "worker": id2}`
1. **Clean up in reverse order** - Stop sessions in reverse of creation order
1. **Monitor resource usage** - Multiple debug sessions consume memory and CPU

### Advanced Breakpoints

1. **Start with logpoints** - Gather data without interrupting execution
1. **Add conditions to reduce noise** - `condition="user_id == target_id"`
1. **Use hit counts for sampling** - `hit_condition="% 1000"` in tight loops
1. **Combine techniques** - Conditional + hit count + logpoint for maximum control
1. **Test conditions before deploying** - Ensure your condition syntax is valid
1. **Check language support** - Not all hit condition modes work in all languages
