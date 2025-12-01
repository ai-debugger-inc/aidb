# Adapter Layer Architecture

**Layer Purpose:** Language-specific debug adapter implementations providing consistent debugging interfaces for Python, JavaScript, and Java through component delegation.

**Location:** `src/aidb/adapters/`

**Note:** This document focuses on architecture. For deep implementation patterns, see the `adapter-development` skill.

______________________________________________________________________

## Quick Reference

**Looking for:**

- Adapter structure → [Section 1: DebugAdapter Base Class](#1-debugadapter-base-class)
- Core components → [Section 2: Component Architecture](#2-component-architecture)
- Extension system → [Section 3: Lifecycle Hooks System](#3-lifecycle-hooks-system)
- Language patterns → [Section 4: Language Adapters](#4-language-adapters)
- Configuration → [Section 5: Configuration Management](#5-configuration-management)
- Design patterns → [Section 6: Key Design Patterns](#6-key-design-patterns)

______________________________________________________________________

## 1. DebugAdapter Base Class

### 1.1 Component Delegation Architecture

**Location:** `src/aidb/adapters/base/adapter.py`

**What:** Abstract base class for all language-specific debug adapters (Python, JavaScript, Java).

**Why Component Delegation?**

**Problem:** Monolithic "God Object" adapters become unmaintainable (1000+ lines, tight coupling, difficult testing).

**Solution:** Delegate responsibilities to focused components with single responsibilities.

**Architecture:**

```
DebugAdapter (abstract base)
  ├── ProcessManager     - Process lifecycle (launch, monitor, stop, cleanup)
  ├── PortManager        - Port allocation (acquire, release, track)
  ├── LaunchOrchestrator - Launch sequence coordination (hooks, port, process, verify)
  └── Auxiliary Components (lazy-initialized)
      ├── AdapterTraceLogManager    - Trace log management
      ├── AdapterOutputCapture      - Stdout/stderr capture
      └── AdapterBinaryLocator      - Binary discovery
```

### 1.2 Core Component Access

**Pattern:** Adapter delegates operations to components via composition

| Component              | Access Pattern                                               | Key Operations                                                                              |
| ---------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| **ProcessManager**     | `adapter.pid`, `adapter.is_alive`, `adapter.captured_output` | `launch_subprocess()`, `stop()`, `wait_for_adapter_ready()`, `cleanup_orphaned_processes()` |
| **PortManager**        | `adapter.port`                                               | `acquire(port)`, `release()`                                                                |
| **LaunchOrchestrator** | `adapter._launch_orchestrator`                               | `launch(target, port, args)`, `launch_with_config(launch_config, port, workspace_root)`     |

### 1.3 Auxiliary Components (Lazy-Initialized)

**Pattern:** Create on first access via properties to avoid unnecessary initialization

- **AdapterTraceLogManager:** `adapter.trace_manager` - Trace log management
- **AdapterOutputCapture:** `adapter.output_capture` - Stdout/stderr capture
- **AdapterBinaryLocator:** `adapter.adapter_locator` - Binary discovery

### 1.4 Abstract Methods (Must Override)

**Language adapters MUST implement:**

**`_build_launch_command(target, adapter_host, adapter_port, args)`**

- Build adapter-specific command array
- Example (Python): `["python", "-m", "debugpy", "--listen", "host:port", target]`
- Example (Java): Raises `NotImplementedError` (uses JDT LS bridge instead)

**`_add_adapter_specific_vars(env)`**

- Add language-specific environment variables
- Example (Python): `env["DEBUGPY_LOG_DIR"] = self.log_dir`
- Example (JavaScript): `env["NODE_OPTIONS"] = "--enable-source-maps"`

**`_get_process_name_pattern()`**

- Pattern for orphan process detection
- Example (Python): `"debugpy"`
- Example (Java): `"jdtls"`

### 1.5 Template Methods (Can Override)

**`_prepare_environment()`** - Multi-step environment preparation

```python
def _prepare_environment(self) -> dict[str, str]:
    env = self._load_base_environment()  # Step 1: Base env
    env = self._add_trace_configuration(env)  # Step 2: Trace config
    return self._add_adapter_specific_vars(env)  # Step 3: Language-specific
```

**`get_launch_configuration()`** - DAP launch request configuration

- Returns dict for DAP `LaunchRequest`
- Language-specific fields (e.g., `justMyCode` for Python)

**`get_trace_config()`** - Trace logging configuration

- Returns dict for adapter trace settings
- Controls verbosity, output location

______________________________________________________________________

## 2. Component Architecture

### 2.1 ProcessManager

**Location:** `src/aidb/adapters/base/components/process_manager.py`

**Responsibilities:**

- **Launch:** Spawns subprocess with tagged environment variables (`AIDB_OWNER`, `AIDB_SESSION_ID`, `AIDB_PROCESS_TYPE`), registers with `ResourceManager`, captures stdout/stderr
- **Monitor:** Polls port with exponential backoff (30s Java, 10s Python/JS), checks liveness, uses config-specific timeouts
- **Stop:** Graceful SIGTERM → forceful SIGKILL, recursive child termination via `psutil`, handles zombies
- **Orphan Cleanup:** Time-budgeted scan (5s min age), matches by environment variables, cross-references active sessions

**Key Features:** Process tagging for safe orphan detection, adaptive timeouts per language, recursive child management, async output capture to circular buffers

### 2.2 PortManager

**Location:** `src/aidb/adapters/base/components/port_manager.py`

**Responsibilities:**

- **Acquire:** Tries requested port, falls back to language ranges (Python: 6000-7000, JS: 9230-9800, Java: 5006-5020), registers with global `PortRegistry`
- **Release:** Returns port to pool, deregisters from `PortRegistry`
- **Track:** Property access via `port_manager.port`

**Integration:** Delegates to session's `ResourceManager` (see `resource-management.md`)

### 2.3 LaunchOrchestrator

**Location:** `src/aidb/adapters/base/components/launch_orchestrator.py`

**Orchestrates launch sequence:** PRE_LAUNCH hooks → acquire port → build command → prepare environment → launch subprocess → wait for ready → POST_LAUNCH hooks → return (process, port)

**VS Code Integration:** Resolves `launch.json` configurations, supports variable substitution (`${workspaceFolder}`, `${file}`), merges with adapter defaults via `launch_with_config()`

**Error Handling:** Centralized failure logging, port release on failure, process cleanup on failure

______________________________________________________________________

## 3. Lifecycle Hooks System

### 3.1 Hook Types

**Location:** `src/aidb/adapters/base/hooks.py`

**What:** Enum defining lifecycle extension points for adapters.

**Hook Types:**

**Initialization:**

- `PRE_INITIALIZE` / `POST_INITIALIZE`

**Launch/Attach:**

- `PRE_LAUNCH` / `POST_LAUNCH`
- `PRE_ATTACH` / `POST_ATTACH`

**Breakpoints:**

- `PRE_SET_BREAKPOINTS` / `POST_SET_BREAKPOINTS`

**Configuration:**

- `PRE_CONFIGURATION_DONE` / `POST_CONFIGURATION_DONE`

**Process Lifecycle:**

- `PRE_STOP` / `POST_STOP`
- `PRE_CLEANUP` / `POST_CLEANUP`

**Custom:**

- `CUSTOM` - Adapter-specific hooks

### 3.2 Priority System

**Execution Order:** Lower priority values execute first (0-100 scale)

**Common Priorities:**

- `90-100` - Critical validation (blocks on failure)
- `70-80` - High priority (setup, early validation)
- `50` - Default priority
- `20-30` - Post-operation delays/waits
- `10` - Low priority (cleanup, logging)

**Example:**

```python
# Execute in order: validate (90) → setup (50) → log (10)
self.register_hook(LifecycleHook.PRE_LAUNCH, self._validate_target, priority=90)
self.register_hook(LifecycleHook.PRE_LAUNCH, self._setup_trace, priority=50)
self.register_hook(LifecycleHook.PRE_LAUNCH, self._log_launch, priority=10)
```

### 3.3 HookContext Object

**What:** Context object passed to all hook callbacks.

**Fields:**

- `adapter` - The adapter instance
- `session` - The debug session
- `data` - Hook-specific data (mutable dictionary)
- `cancelled` - Set to `True` to cancel operation
- `result` - Override operation result (error message when cancelled)

**Cancellation Pattern:**

```python
def _validate_target_hook(self, context: HookContext) -> None:
    target = context.data.get("target")
    if not Path(target).exists():
        context.cancelled = True
        context.result = f"Target not found: {target}"
        return
```

### 3.4 Hook Registration

**Pattern:** Register during adapter initialization

```python
def __init__(self, session, ctx=None, config=None, **kwargs):
    super().__init__(session, ctx, config, **kwargs)
    self._register_my_hooks()

def _register_my_hooks(self):
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        self._validate_environment,
        priority=90
    )
    self.register_hook(
        LifecycleHook.POST_LAUNCH,
        self._wait_for_ready,
        priority=20
    )
```

______________________________________________________________________

## 4. Language Adapters

**Pattern:** All adapters use hooks and initialization sequences defined in config.

### Language-Specific Characteristics

| Aspect              | Python (debugpy)                                                                     | JavaScript (vscode-js-debug)                                                    | Java (JDT LS + java-debug)                                          |
| ------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Architecture**    | Direct debugpy adapter                                                               | Parent-child sessions                                                           | LSP-DAP bridge                                                      |
| **Unique Features** | Module mode (`-m pytest`), framework flags (Django/Flask), transport-only disconnect | Source maps, child DAP connections, breakpoint transfer via `__pendingTargetId` | JDT LS pooling, auto-compile, Maven/Gradle detection, dummy process |
| **Init Sequence**   | Attach BEFORE initialized event                                                      | Child sets own breakpoints after parent setup                                   | Extended timeouts (30s init, 10s BP verification)                   |
| **Timeouts**        | 10s ready, 0.5s process                                                              | 10s ready, 0.5s process                                                         | 30s ready, 2s process                                               |
| **Hit Conditions**  | All modes supported                                                                  | All modes supported                                                             | EXACT only (no operators)                                           |
| **Default Port**    | 5678                                                                                 | 9229                                                                            | 5005                                                                |

### Key Implementation Details

**Python (`src/aidb/adapters/lang/python/python.py`):**

- Launch: `["python", "-m", "debugpy", "--listen", "host:port", "--wait-for-client", target, *args]`
- Lifecycle hooks: trace setup (priority 90), orphan cleanup (priority 85), wait for debugpy (priority 20)
- Trace management: `PythonTraceManager` consolidates per-PID debugpy logs with rotation (last 5 files, 10MB size control)

**JavaScript (`src/aidb/adapters/lang/javascript/javascript.py`):**

- Launch: `["node", "/path/to/dapDebugServer.js", "9229"]` (single server handles parent + all children)
- Parent-child pattern: Parent spawns children via `startDebugging` reverse request, each child creates separate DAP connection to same adapter server
- TypeScript support: Auto-detect `.ts` files, check for `ts-node`, comprehensive source map configuration

**Java (`src/aidb/adapters/lang/java/java.py`):**

- Launch: Compile → Start JDT LS (or get from `JDTLSProjectPool`) → Open file → Resolve classpath → Start debug session → Create dummy process
- Bridge management: `JavaLSPDAPBridge` manages JDT LS lifecycle, pooled instances skip DAP disconnect to avoid freeze
- Compilation: `JavaCompilationManager` auto-compiles `.java` to `.class` if `auto_compile=True`

**For detailed implementation patterns:** See `adapter-development` skill.

______________________________________________________________________

## 5. Configuration Management

**Location:** `src/aidb/adapters/base/config.py`

**AdapterConfig (Base):** Dataclass defining language, ports, timeouts, file extensions, and capability declarations.

**Key Method:** `get_initialization_sequence()` returns ordered `InitializationOp` list (language-specific).

**Language-Specific Configs:**

- **PythonAdapterConfig (`src/aidb/adapters/lang/python/config.py`):** Framework flags (django, flask, pytest), debugging options (justMyCode, subProcess), all hit conditions supported
- **JavaScriptAdapterConfig (`src/aidb/adapters/lang/javascript/config.py`):** Adapter type (pwa-node/chrome/msedge), source maps, child session coordination, all hit conditions supported
- **JavaAdapterConfig (`src/aidb/adapters/lang/java/config.py`):** JDK/JDT LS paths, auto-compile, classpath/vmargs, EXACT hit condition only

**For full field reference:** See implementation files in `src/aidb/adapters/lang/*/config.py`

______________________________________________________________________

## 6. Key Design Patterns

### 6.1 Component Delegation

**Problem:** Monolithic adapter classes (1000+ lines, tight coupling)
**Solution:** Delegate to focused components (`ProcessManager`, `PortManager`, `LaunchOrchestrator`)
**Benefit:** Independent testing, modification, understanding

### 6.2 Lazy Initialization

**Problem:** Not all utilities needed for every operation
**Solution:** Create auxiliary components on first access via properties
**Benefit:** Avoids unnecessary initialization, reduces memory usage

### 6.3 Priority-Based Hooks

**Problem:** Multiple concerns at same lifecycle point
**Solution:** Hook system with priority-based execution (90=validate, 50=setup, 10=log)
**Benefit:** Independent concerns without method overrides

### 6.4 Template Method

**Problem:** Environment preparation has common + language-specific steps
**Solution:** Base class defines algorithm (`_prepare_environment()`), subclasses override steps (`_add_adapter_specific_vars()`)
**Benefit:** Reuses common logic, customizes specific steps

______________________________________________________________________

## Quick Reference

**Language Quirks:**

- **Python:** Module mode, attach before initialized, transport-only disconnect
- **JavaScript:** Parent-child sessions, separate child DAP, breakpoint transfer
- **Java:** LSP-DAP bridge, JDT LS pool, compilation manager, dummy process

**Hook Priorities:** 90-100 (validate), 70-80 (setup), 50 (default), 20-30 (post-op), 10 (cleanup/log)

**Key Files:** Base adapter (`adapter.py`), components (`process_manager.py`, `port_manager.py`, `launch_orchestrator.py`), hooks (`hooks.py`), language adapters (`python/python.py`, `javascript/javascript.py`, `java/java.py`)

**For Deep Dives:** See `adapter-development` skill for implementation patterns and HOW-TO guides.
