---
myst:
  html_meta:
    description lang=en: JavaScript/TypeScript debugging with AI Debugger MCP - framework support, source maps, and best practices.
---

# JavaScript/TypeScript Debugging Guide

AI Debugger MCP provides comprehensive debugging support for JavaScript and TypeScript applications through Microsoft's vscode-js-debug adapter. This guide covers common framework debugging patterns, source map handling, and the JavaScript ecosystem.

```{include} /_snippets/about-examples-disclaimer.md
```

## Requirements

- **Node.js**: 18+ (22 LTS recommended)
- **Debug Adapter**: vscode-js-debug v1.105.0
- **TypeScript** (optional): ts-node 10.9.2, TypeScript 5.9.3

The adapter is installed automatically when you first debug JavaScript/TypeScript code.

## Framework Support

AI Debugger MCP provides example configurations for popular JavaScript frameworks and test runners.

### Node.js Applications

Debug standalone Node.js applications with full breakpoint and inspection support.

**Example: Debugging a Node.js server**

Your AI assistant will call the MCP tool `session_start` with these parameters:

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "/path/to/server.js",
    "breakpoints": [
        {"file": "/path/to/server.js", "line": 27},
        {"file": "/path/to/routes/api.js", "line": 15},
        {"file": "/path/to/middleware/auth.js", "line": 8}
    ]
}
```

**Launch configuration equivalent:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug Node App",
  "program": "${workspaceFolder}/server.js",
  "skipFiles": ["<node_internals>/**"]
}
```

### Jest Test Framework

Debug Jest tests with proper source mapping and test isolation.

**Example: Debugging Jest tests**

Your AI assistant will call the MCP tool `session_start`:

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "npm",
    "args": ["test", "--", "--runInBand", "--no-coverage"],
    "breakpoints": [
        {"file": "/path/to/src/calculator.js", "line": 15},
        {"file": "/path/to/tests/calculator.test.js", "line": 8}
    ]
}
```

The `--runInBand` flag ensures tests run sequentially in a single process, which is required for debugging. The `--no-coverage` flag disables coverage collection for cleaner debugging.

**Launch configuration equivalent:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Jest Tests",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["test", "--", "--runInBand", "--no-coverage"],
  "console": "integratedTerminal"
}
```

### Mocha Test Framework

Debug Mocha tests with inspector protocol support.

**Example: Debugging Mocha tests**

Your AI assistant will call the MCP tool `session_start`:

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "mocha",
    "args": ["--inspect-brk", "test/**/*.test.js"],
    "breakpoints": [
        {"file": "/path/to/src/services/user.js", "line": 42},
        {"file": "/path/to/test/user.test.js", "line": 23}
    ]
}
```

The `--inspect-brk` flag starts the debugger and breaks before user code starts, allowing you to set breakpoints before execution begins.

**Launch configuration equivalent:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Mocha Tests",
  "runtimeExecutable": "mocha",
  "runtimeArgs": ["--inspect-brk"],
  "args": ["test/**/*.test.js"]
}
```

### Express Framework

Debug Express.js web applications with full support for routes, middleware, and error handlers.

**Example: Debugging an Express server**

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "/path/to/server.js",
    "breakpoints": [
        {"file": "/path/to/routes/index.js", "line": 12},
        {"file": "/path/to/routes/api.js", "line": 25},
        {"file": "/path/to/middleware/auth.js", "line": 8}
    ]
}
```

**Debug Express via npm scripts:**

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "npm",
    "args": ["start"],
    "cwd": "/path/to/express-app",
    "breakpoints": [
        {"file": "/path/to/express-app/routes/api.js", "line": 15}
    ]
}
```

**Launch configuration equivalent:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Express Server",
  "program": "${workspaceFolder}/server.js",
  "skipFiles": ["<node_internals>/**"]
}
```

:::{tip}
**Express debugging tips:**

- Set breakpoints in route handlers to inspect request/response objects
- Debug middleware by setting breakpoints at the start of each middleware function
- Use conditional breakpoints like `req.method === 'POST'` to catch specific requests
- Set breakpoints in error handlers to debug error scenarios
  :::

## Source Maps

Source maps enable debugging transpiled code (TypeScript, Babel, webpack) by mapping compiled JavaScript back to original source files.

### How Source Maps Work

When you debug transpiled code, the debugger needs to translate between:

- **Compiled code**: The actual JavaScript that runs (e.g., `dist/bundle.js`)
- **Source code**: The original files you wrote (e.g., `src/index.ts`)

Source maps (`.map` files) provide this translation, allowing breakpoints in your original source to work correctly.

### Automatic Source Map Detection

AI Debugger MCP enables source maps by default and discovers them through:

1. **Inline source maps**: Embedded in compiled JavaScript files
1. **External source map files**: Separate `.map` files referenced by compiled code
1. **tsconfig.json settings**: TypeScript compiler source map configuration

**Example: TypeScript debugging with source maps**

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "/path/to/src/index.ts",
    "breakpoints": [
        {"file": "/path/to/src/index.ts", "line": 15},
        {"file": "/path/to/src/utils/helper.ts", "line": 8}
    ]
}
```

The debugger automatically:

- Detects `.ts` file extension
- Checks for `tsconfig.json` configuration
- Uses ts-node if available to run TypeScript directly
- Maps breakpoints to compiled JavaScript locations

### Source Map Configuration

Configure source maps via VS Code launch.json:

**Create launch.json configuration**

```:json:.vscode/launch.json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug Webpack App",
  "program": "${workspaceFolder}/dist/bundle.js",
  "sourceMaps": true,
  "outFiles": [
    "${workspaceFolder}/dist/**/*.js",
    "!**/node_modules/**"
  ]
}
```

Then use the configuration:

```python
# MCP tool: session_start
{
    "language": "javascript",
    "launch_config_name": "Debug Webpack App",
    "breakpoints": [
        {"file": "/path/to/src/app.ts", "line": 42}
    ]
}
```

**Note**: The `source_maps` and `out_files` parameters are supported via launch.json configurations. Source maps are enabled by default in the JavaScript adapter, but complex build setups (webpack, parcel, etc.) should use launch.json for explicit configuration.

### Source Map Path Overrides

For complex build configurations (webpack, parcel, etc.), you may need path overrides:

```python
# The JavaScript adapter automatically configures common path overrides:
# - webpack:///./~/* -> ${workspaceFolder}/node_modules/*
# - webpack:///*/* -> /*
# - webpack://?:*/* -> ${workspaceFolder}/*
# - meteor://💻app/* -> ${workspaceFolder}/*
# - turbopack://[project]/* -> ${workspaceFolder}/*
```

These overrides help the debugger find your source files when bundlers use special URL schemes.

## Minified Code Debugging

:::{warning}
**Minified code debugging requires column-level breakpoints** for precise placement. Without source maps, debugging minified code can be extremely challenging!
:::

### Column Breakpoints

When debugging minified code, multiple statements may exist on a single line. Use column breakpoints to target specific expressions:

```python

# Set column breakpoint in minified code
breakpoint(
    action="set",
    location="/path/to/dist/bundle.min.js:1:2847"  # line:column format
)

# Or use the full breakpoint specification

session_start(
    language="javascript",
    target="/path/to/dist/bundle.min.js",
    breakpoints=[
        {
            "file": "/path/to/dist/bundle.min.js",
            "line": 1,
            "column": 2847  # Precise column position
        }
    ]
)
```

:::{tip}
**How to find column numbers:**

1. **With source maps**: Set breakpoints in source files, they'll map to correct columns automatically
1. **Without source maps**: Use browser DevTools to find column positions, then use those in your debug session
1. **Programmatically**: Parse the minified file to find function/statement boundaries
   :::

:::{important}
**Debugging Minified Code Best Practices:**

1. **Always use source maps when available** - Even for production debugging
1. **Enable source map generation in your build** - Configure webpack/babel/tsc to generate `.map` files
1. **Keep source maps secure** - Don't deploy them to production unless needed for debugging
1. **Use smart stepping via launch.json** - Skip over library code automatically (see Step Filtering section)
   :::

## Common Patterns

### Conditional Breakpoints

Break only when specific conditions are met:

```python

session_start(
    language="javascript",
    target="/path/to/server.js",
    breakpoints=[
        {
            "file": "/path/to/routes/api.js",
            "line": 15,
            "condition": "req.method === 'POST' && req.body.userId > 1000"
        }
    ]
)
```

JavaScript supports full expression evaluation in conditions, including:

- Variable comparisons: `x > 10`
- String matching: `username.includes('admin')`
- Complex logic: `(a && b) || (c && d)`
- Function calls: `isValid(data)`

### Hit Count Breakpoints

Control breakpoint triggering based on hit count:

```python

session_start(
    language="javascript",
    target="/path/to/app.js",
    breakpoints=[
        {
            "file": "/path/to/utils/processor.js",
            "line": 42,
            "hit_condition": ">5"  # Break after 5th hit
        },
        {
            "file": "/path/to/lib/validator.js",
            "line": 18,
            "hit_condition": "%10"  # Break every 10th hit
        }
    ]
)
```

:::{note}
**Supported hit condition operators:**

- `5` or `==5`: Break on exactly the 5th hit
- `>5`: Break after more than 5 hits
- `>=5`: Break on 5th hit and beyond
- `<5`: Break before 5th hit
- `<=5`: Break on hits 1 through 5
- `%5`: Break every 5th hit (modulo)
  :::

### Logpoints

Log messages without pausing execution:

```python

session_start(
    language="javascript",
    target="/path/to/app.js",
    breakpoints=[
        {
            "file": "/path/to/services/api.js",
            "line": 28,
            "log_message": "API called with userId: {req.body.userId}, timestamp: {Date.now()}"
        }
    ]
)
```

:::{tip}
**Logpoints are extremely useful for:**

- **Production debugging**: Add logging without redeploying
- **Performance monitoring**: Log timing information
- **Trace analysis**: Follow execution flow without stopping
  :::

### Async/Await Debugging

JavaScript's async debugging supports full async stack traces:

```python

# Start debugging async code
session_start(
    language="javascript",
    target="/path/to/async-app.js",
    breakpoints=[
        {"file": "/path/to/async-app.js", "line": 15}
    ]
)

# Inspect async stacks when stopped at breakpoint
stack_info = inspect(
    target="stack",
    detailed=True
)

# stack_info will show:
# - Current async frame
# - Async parent frames
# - Promise chain
```

**Launch configuration with async stacks:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug Async App",
  "program": "${workspaceFolder}/async-app.js",
  "showAsyncStacks": true  // Enable async stack traces (default: true)
}
```

### Environment Variables

Pass environment variables for debugging:

```python

# Inline environment variables
session_start(
    language="javascript",
    target="/path/to/app.js",
    env={
        "NODE_ENV": "development",
        "DEBUG": "app:*",
        "DATABASE_URL": "postgresql://localhost/testdb"
    }
)
```

**Note**: To load environment variables from a `.env` file, use a VS Code launch.json configuration with the `envFile` property.

### npm/yarn Script Debugging

Debug applications run through package.json scripts:

```python

# Debug npm script
session_start(
    language="javascript",
    target="npm",
    args=["run", "dev"],  # Runs the "dev" script from package.json
    cwd="/path/to/project",
    breakpoints=[
        {"file": "/path/to/project/src/index.js", "line": 10}
    ]
)

# Debug yarn script
session_start(
    language="javascript",
    target="yarn",
    args=["start"],
    cwd="/path/to/project"
)
```

### Runtime Version Selection

To debug with specific Node.js versions, configure a VS Code launch.json with the `runtimeExecutable` property:

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug with Node 18",
  "program": "${workspaceFolder}/app.js",
  "runtimeExecutable": "/path/to/node18/bin/node"
}
```

Then reference it:

```python
session_start(
    language="javascript",
    launch_config_name="Debug with Node 18"
)
```

### Step Filtering

Skip over code you don't want to debug using VS Code launch.json:

```:json:.vscode/launch.json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug with Filtering",
  "program": "${workspaceFolder}/app.js",
  "skipFiles": [
    "<node_internals>/**",
    "**/node_modules/**",
    "**/dist/vendor*.js"
  ]
}
```

Then use the configuration:

```python
session_start(
    language="javascript",
    launch_config_name="Debug with Filtering",
    breakpoints=[
        {"file": "/path/to/app.js", "line": 15}
    ]
)
```

The `<node_internals>/**` pattern is special and skips Node.js built-in modules like `fs`, `http`, etc.

**Note**: The `skip_files` parameter is supported via launch.json configurations. Direct parameter usage is not currently exposed in the MCP interface - use launch.json for step filtering.

### Remote Debugging

Attach to Node.js processes started with `--inspect`:

:::{note}
**Understanding Attach Mode**

Attach mode connects to an **already-running** Node.js process. This is different from launch mode, which starts a new process for you.

**When to use attach:**

- Production debugging (process is already running)
- Long-running servers
- Debugging without restarting the application

**When to use launch:**

- Development workflows
- Running tests
- Starting fresh debug sessions
  :::

**Requirements for attach mode:**

1. Target process must already be running
1. Process must be started with `--inspect` or `--inspect-brk` flag
1. Debugger port must be accessible (default: 9229)

**Example workflow:**

```bash
# Terminal 1: Start your app with debugging enabled
node --inspect=9229 app.js
```

```python
# Terminal 2: Attach debugger to the running process
session_start(
    language="javascript",
    mode="remote_attach",
    host="localhost",
    port=9229
)
```

**Common attach scenarios:**

- **Local development**: Attach to `localhost:9229`
- **Docker container**: Forward port and attach to `localhost:9229`
- **Remote server**: SSH tunnel or attach to `remote-host:9229` (if port exposed)

## TypeScript-Specific Features

### Direct TypeScript Execution

Debug TypeScript without pre-compilation using ts-node. The adapter automatically detects `.ts` files and uses ts-node if available:

```python
session_start(
    language="javascript",
    target="/path/to/src/app.ts",
    breakpoints=[
        {"file": "/path/to/src/app.ts", "line": 15},
        {"file": "/path/to/src/utils/helper.ts", "line": 8}
    ]
)
```

For custom ts-node configuration, use a VS Code launch.json:

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug TypeScript",
  "program": "${workspaceFolder}/src/app.ts",
  "runtimeArgs": ["--require", "ts-node/register"],
  "console": "integratedTerminal"
}
```

Requirements:

- `ts-node` installed: `npm install -g ts-node typescript`
- `tsconfig.json` configured with `"sourceMap": true`

### TypeScript Configuration Detection

The debugger automatically detects and uses your TypeScript configuration:

```typescript
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "sourceMap": true,  // Required for debugging
    "outDir": "./dist"
  }
}
```

When debugging, the adapter:

1. Reads `tsconfig.json` from project root
1. Applies compiler options for source map resolution
1. Configures outFiles pattern based on outDir
1. Maps source paths correctly

### TypeScript Decorator Debugging

Debug TypeScript decorators and metadata using a VS Code launch.json configuration:

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Debug with Decorators",
  "program": "${workspaceFolder}/src/app.ts",
  "runtimeArgs": ["--require", "ts-node/register", "--experimental-decorators"]
}
```

Then reference it:

```python
session_start(
    language="javascript",
    launch_config_name="Debug with Decorators",
    breakpoints=[
        {"file": "/path/to/src/decorators/logger.ts", "line": 10}
    ]
)
```

## Child Session Architecture

JavaScript debugging uses a **parent-child session pattern** to handle subprocess debugging. Understanding this architecture is important for debugging complex Node.js applications that spawn child processes.

### How Child Sessions Work

When you launch a debug session, the vscode-js-debug adapter creates:

1. **Parent Session**: Manages the initial process launch and coordinates debugging
1. **Child Session(s)**: Created automatically for each spawned subprocess that needs debugging

This architecture is used for:

- Worker threads
- Child processes spawned via `child_process.fork()`
- Subprocess debugging in general

### Breakpoint Behavior

Breakpoints are automatically transferred from the parent session to child sessions:

- When a child session starts, breakpoints set via the parent are automatically applied
- You don't need to re-set breakpoints for child processes
- The adapter handles the coordination between parent and child sessions

### Practical Implications

:::{note}
**For most debugging scenarios, child sessions are transparent** - you don't need to manage them manually. The adapter handles session coordination automatically.

**When it matters:**

- Debugging worker threads or forked processes
- Complex multi-process Node.js applications
- Microservices running locally
  :::

Example scenario with worker threads:

```python
# MCP tool: session_start
{
    "language": "javascript",
    "target": "/path/to/main.js",  # Main file spawns workers
    "breakpoints": [
        {"file": "/path/to/main.js", "line": 15},
        {"file": "/path/to/worker.js", "line": 8}  # Breakpoint in worker file
    ]
}
```

When `main.js` spawns a worker from `worker.js`, the breakpoint at line 8 in the worker file will be hit automatically - the adapter creates a child session for the worker and transfers the breakpoint.

## Performance Tips

### Reduce Startup Time

1. **Use targeted breakpoints:** Set breakpoints only where needed instead of stepping through code

1. **Limit outFiles patterns:** Be specific about where to look for source maps in launch.json

1. **Configure step filtering via launch.json:**

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "Optimized Debug",
  "program": "${workspaceFolder}/app.js",
  "skipFiles": ["<node_internals>/**", "**/node_modules/**"],
  "showAsyncStacks": false
}
```

### Memory-Efficient Debugging

For large applications, configure JVM arguments via launch.json:

```json
{
  "type": "pwa-node",
  "request": "launch",
  "name": "High Memory Debug",
  "program": "${workspaceFolder}/app.js",
  "runtimeArgs": ["--max-old-space-size=4096"],
  "skipFiles": ["**/node_modules/**"]
}
```

Then reference it:

```python
session_start(
    language="javascript",
    launch_config_name="High Memory Debug"
)
```

## Troubleshooting

### Breakpoints Not Binding

:::{warning}
**Symptom:** Breakpoints show as unverified (gray) or are skipped
:::

**Solutions:**

1. **Enable source maps via launch.json:**

   ```json
   {
     "type": "pwa-node",
     "request": "launch",
     "name": "Debug with Source Maps",
     "program": "${workspaceFolder}/dist/app.js",
     "sourceMaps": true,
     "outFiles": ["${workspaceFolder}/dist/**/*.js"]
   }
   ```

   Then use: `session_start(launch_config_name="Debug with Source Maps")`

1. **Verify file paths are absolute:**

   ```python
   # Use absolute paths for breakpoints
   breakpoints=[{"file": "/absolute/path/to/file.js", "line": 15}]
   ```

1. **Ensure source maps are generated** by your build tool (webpack, tsc, etc.)

### Source Maps Not Working

:::{warning}
**Symptom:** Breakpoints set in source files don't work, or debugger shows compiled code
:::

**Solutions:**

1. **Verify source map generation:**

   ```bash
   # Check if .map files exist
   ls dist/*.map
   ```

1. **Check tsconfig.json:**

   ```json
   {
     "compilerOptions": {
       "sourceMap": true,
       "inlineSources": true
     }
   }
   ```

1. **Use pauseForSourceMap via launch.json:**

   ```json
   {
     "type": "pwa-node",
     "request": "launch",
     "name": "Debug with Source Map Wait",
     "program": "${workspaceFolder}/app.js",
     "pauseForSourceMap": true
   }
   ```

### Cannot Connect to Debugger

:::{warning}
**Symptom:** Session fails to start or connect
:::

**Solutions:**

1. **Check port availability (for attach mode):**

   ```python
   # For attach mode, specify a different port
   session_start(
       language="javascript",
       mode="remote_attach",
       host="localhost",
       port=9230  # Use non-default port
   )
   ```

   **Note**: The `port` parameter is only used in attach mode, not launch mode.

1. **Verify Node.js installation:**

   ```bash
   node --version  # Should print version number
   which node      # Should print path to node
   ```

1. **Check for conflicting processes:**

   ```bash
   # Kill any existing debugger processes
   pkill -f "node.*--inspect"
   ```

### TypeScript Compilation Errors

**Symptom:** TypeScript files fail to run during debugging

**Solutions:**

1. **Install ts-node:**

   ```bash
   npm install -g ts-node typescript
   ```

1. **Fix tsconfig.json errors:**

   ```bash
   # Validate tsconfig.json
   npx tsc --noEmit
   ```

1. **Use pre-compiled JavaScript with launch.json:**

   Configure source maps in launch.json and debug the compiled output:

   ```python
   # Debug compiled output using launch config with sourceMaps enabled
   session_start(
       language="javascript",
       launch_config_name="Debug Compiled JS"
   )
   ```

## JavaScript/TypeScript Debugging Limitations

:::{note}
**Understanding JavaScript/TypeScript Debugging Modes:**

**Attach mode** connects to an already-running Node.js process:

- ℹ️ Process must be started with `--inspect` or `--inspect-brk` flag
- ℹ️ Best for production debugging, long-running servers, debugging without restart
- ✅ All debugging features supported (breakpoints, stepping, inspection, etc.)

**Launch mode** starts a new process for you:

- ✅ Best for development, running tests, fresh debug sessions
- ✅ No manual setup required

**All debugging features work in both modes:**

- ✅ Conditional breakpoints with all hit condition modes (`>`, `>=`, `=`, `<`, `<=`, `%`, exact)
- ✅ Logpoints with template syntax
- ✅ Source maps (TypeScript, minified code)
- ✅ All stepping operations (into, over, out)
- ✅ Variable inspection and modification

For general debugging concepts, see [Known Limitations](../core-concepts.md#known-limitations).
:::

## See Also

- [Core Concepts](../core-concepts.md) - Understanding session lifecycle and breakpoint management
- [Advanced Workflows](../advanced-workflows.md) - Complex debugging scenarios
- [Python Debugging Guide](python.md) - Python-specific debugging features
- [Java Debugging Guide](java.md) - Java-specific debugging features
