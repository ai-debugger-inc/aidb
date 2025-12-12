# Java Adapter Patterns (java-debug + JDT LS)

## Overview

**IMPORTANT**: JDT LS is **required** for Java debugging. The Java adapter always uses Eclipse JDT LS.

The Java adapter (`JavaAdapter`) uses **java-debug-server** with **Eclipse JDT Language Server** integration:

- JDT LS provides compilation, classpath resolution, and code intelligence
- java-debug provides DAP debugging capabilities
- LSP-DAP bridge coordinates communication between components

**File**: `src/aidb/adapters/lang/java/java.py`

**Note**: JDT LS is always used for Java debugging - there is no conditional logic.

## Critical Architecture: LSP-DAP Bridge

Java uses an **LSP-DAP bridge pattern** for full IDE-like capabilities:

```
┌──────────────┐
│    Client    │
└──────┬───────┘
       │
┌──────▼──────────┐
│  JavaAdapter    │
└──────┬──────────┘
       │
┌──────▼──────────────────┐
│   JavaLSPDAPBridge      │
├─────────────────────────┤
│  ┌────────────────────┐ │
│  │ Eclipse JDT LS     │ │  LSP for compilation,
│  │ (language server)  │ │  classpath, intelligence
│  └─────────┬──────────┘ │
│            │            │
│  ┌─────────▼──────────┐ │
│  │ java-debug         │ │  DAP for debugging
│  │ (debug adapter)    │ │
│  └────────────────────┘ │
└─────────────────────────┘
```

## Architecture

The Java adapter follows a **component-based architecture** with clear separation of concerns:

```
JavaAdapter (extends DebugAdapter)
├── ProcessManager              - Manage adapter processes (from base)
├── PortManager                 - Acquire debug port (from base)
├── LaunchOrchestrator          - Coordinate launch (from base, delegated)
├── JavaLSPDAPBridge            - High-level LSP-DAP orchestrator
│   ├── LSPClient               - Low-level LSP communication
│   ├── LSPProtocol             - Protocol types & validation
│   ├── LSPMessageHandler       - Message parsing & dispatch
│   ├── LSPInitialization       - Initialization helpers
│   ├── JDTLSProcessManager     - JDT LS process lifecycle
│   ├── WorkspaceManager        - Workspace & project management
│   └── DebugSessionManager     - Debug session delegation
├── JavaToolchain               - Java/javac executable discovery
├── JavaClasspathBuilder        - Classpath construction & utilities
├── JavaBuildSystemDetector     - Maven/Gradle project detection
└── Lifecycle Hooks             - Environment validation, setup, cleanup
    ├── JavaEnvironmentValidator    - Pre-launch environment checks
    ├── JDTLSSetupHooks             - Pre-launch bridge initialization
    ├── JDTLSReadinessHooks         - Post-launch readiness waiting
    └── JDTLSCleanupHooks           - Post-stop cleanup
```

### Component Organization

```
src/aidb/adapters/lang/java/
├── lsp/                        # LSP-related components
│   ├── __init__.py
│   ├── lsp_bridge.py          # High-level orchestrator (366 lines)
│   ├── lsp_client.py          # LSP communication (269 lines)
│   ├── lsp_protocol.py        # Protocol types & validation (288 lines)
│   ├── lsp_message_handler.py # Message routing (446 lines)
│   ├── lsp_initialization.py  # Initialization helpers (90 lines)
│   ├── jdtls_process_manager.py  # Process lifecycle (397 lines)
│   ├── workspace_manager.py   # Workspace & project mgmt (364 lines)
│   └── debug_session_manager.py  # Debug session management (447 lines)
├── hooks/                      # Lifecycle hooks
│   ├── __init__.py
│   └── lifecycle_hooks.py     # 4 hook classes (574 lines)
├── tooling/                    # Java utilities
│   ├── __init__.py
│   ├── java_toolchain.py      # Java/javac discovery
│   ├── classpath_builder.py   # Classpath construction & utilities
│   └── build_system_detector.py  # Maven/Gradle detection
├── java.py                     # Main adapter (698 lines)
├── config.py                   # Configuration classes
├── compilation.py              # Compilation management (legacy)
├── jdtls_project_pool.py       # JDT LS pooling (LRU cache)
├── source_detection.py         # Maven/Gradle source path auto-detection
└── lsp_bridge.py               # Legacy compatibility layer
```

## Key Configuration Options

```python
@dataclass
class JavaAdapterConfig(AdapterConfig):
    """Java adapter configuration."""

    jdk_home: str | None = None          # JDK installation path
    classpath: list[str] = field(default_factory=list)
    module_path: list[str] = field(default_factory=list)
    vmargs: list[str] = field(default_factory=list)
    projectName: str = ""                # Project for evaluation context
    jdtls_workspace: str | None = None   # Workspace directory
    auto_compile: bool = True            # Auto-compile .java files

    # Default project name for single files (JDT LS is required for Java debugging)
    DEFAULT_PROJECT_NAME: ClassVar[str] = "jdt.ls-java-project"
```

## JDT LS Pooling Pattern

**Critical optimization**: JDT LS is memory-intensive and slow to start (8-9 seconds). The Java adapter uses per-project pooling by default (controlled by `AIDB_JAVA_LSP_POOL` env var):

```python
# Check for per-project JDT LS pool
use_pool = reader.read_bool("AIDB_JAVA_LSP_POOL", True)

if use_pool:
    from aidb.adapters.lang.java.jdtls_project_pool import (
        get_jdtls_project_pool,
    )

    pool = await get_jdtls_project_pool(ctx=self.ctx)
    bridge = await pool.get_or_start_bridge(
        project_path=project_path,
        project_name=proj_name,
        jdtls_path=jdtls_path,
        java_debug_jar=java_debug_jar,
        java_command=java_command,
        workspace_folders=workspace_folders,
    )
    self._lsp_dap_bridge = bridge
else:
    # Start standalone JDT LS (no pooling)
    await self._lsp_dap_bridge.start(
        project_root,
        session_id=self.session.id,
        workspace_folders=workspace_folders,
    )
```

## Launch Flow

Java delegates to tooling components:

1. **Compilation**: JavaCompilationManager compiles `.java` → `.class` if needed
1. **Pre-launch hooks**: Environment validation, workspace setup, bridge initialization
1. **Toolchain**: JavaToolchain locates Java/javac executables
1. **Classpath**: JavaClasspathBuilder constructs classpath from target + config
1. **Bridge**: JavaLSPDAPBridge starts debug session via JDT LS
1. **Return**: Returns dummy process + DAP port (JDT LS manages actual Java process)

## Lifecycle Hooks Registration

The Java adapter uses **dedicated hook classes** for organized lifecycle management:

```python
def _register_java_hooks(self) -> None:
    """Register Java-specific lifecycle hooks using dedicated hook classes."""
    from aidb.adapters.lang.java.hooks.lifecycle_hooks import (
        JavaEnvironmentValidator,
        JDTLSCleanupHooks,
        JDTLSReadinessHooks,
        JDTLSSetupHooks,
    )

    # Pre-launch: Environment validation
    env_validator = JavaEnvironmentValidator(self, self.ctx)
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        env_validator.validate_java_environment,
        priority=90,  # Very high priority - validate environment first
    )
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        env_validator.validate_java_target,
        priority=85,  # High priority - validate target early
    )

    # Pre-launch: JDT LS setup
    setup_hooks = JDTLSSetupHooks(self, self.ctx)
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        setup_hooks.prepare_jdtls_workspace,
        priority=80,  # Set up workspace before bridge
    )
    self.register_hook(
        LifecycleHook.PRE_LAUNCH,
        setup_hooks.initialize_lsp_dap_bridge,
        priority=70,  # Initialize bridge before launch
    )

    # Post-launch: JDT LS readiness
    readiness_hooks = JDTLSReadinessHooks(self, self.ctx)
    self.register_hook(
        LifecycleHook.POST_LAUNCH,
        readiness_hooks.wait_for_jdtls_ready,
        priority=20,  # Wait for JDT LS after launch
    )
    self.register_hook(
        LifecycleHook.POST_LAUNCH,
        readiness_hooks.enable_trace_logging,
        priority=15,  # Enable trace after JDT LS is ready
    )

    # Post-stop: Cleanup
    cleanup_hooks = JDTLSCleanupHooks(self, self.ctx)
    self.register_hook(
        LifecycleHook.POST_STOP,
        cleanup_hooks.collect_eclipse_logs,
        priority=10,  # Collect logs after stop
    )
    self.register_hook(
        LifecycleHook.POST_STOP,
        cleanup_hooks.cleanup_lsp_dap_bridge,
        priority=20,  # Clean up bridge first
    )
    self.register_hook(
        LifecycleHook.POST_STOP,
        cleanup_hooks.cleanup_jdtls_workspace,
        priority=10,  # Clean up workspace last
    )
```

### Hook Class Responsibilities

**JavaEnvironmentValidator** (`hooks/lifecycle_hooks.py`):

- Validates Java and javac availability (uses JavaToolchain)
- Validates target file exists and has correct extension
- Runs at priority 90/85 (very high) to fail fast on environment issues

**JDTLSSetupHooks** (`hooks/lifecycle_hooks.py`):

- Prepares JDT LS workspace directory
- Initializes LSP-DAP bridge (with or without pooling)
- Runs at priority 80/70 to set up infrastructure before launch

**JDTLSReadinessHooks** (`hooks/lifecycle_hooks.py`):

- Waits for JDT LS to be fully initialized
- Enables trace logging if configured
- Runs at priority 20/15 after launch completes

**JDTLSCleanupHooks** (`hooks/lifecycle_hooks.py`):

- Collects Eclipse/JDT LS logs for debugging
- Cleans up LSP-DAP bridge (respects pooling)
- Cleans up workspace directories
- Runs at priority 10/20 after session stops

## Component Responsibilities Summary

**JavaToolchain**: Discovers Java/javac executables from config, JAVA_HOME, or PATH

**JavaClasspathBuilder**: Constructs classpath from target directory + configured paths + temp compile directory. Extracts main class from `.java`, `.class`, or `.jar` files. Provides utilities for flattening JDT LS classpaths, adding target/classes, and adding test-classes for JUnit.

**JavaBuildSystemDetector**: Detects Maven/Gradle project roots by walking up directory tree looking for `pom.xml`, `build.gradle`, or `build.gradle.kts`. Provides fallback resolution (workspace_root → cwd → target).

**WorkspaceManager** (LSP component): Manages JDT LS workspace directories. Creates temp workspace if not specified. Handles workspace folder registration.

**DebugSessionManager** (LSP component): Delegates debug session start/attach requests to java-debug server. Builds DAP launch configurations with main class, classpath, vmArgs, projectName.

## Remote Attach & Pooled Bridge Cleanup

**Remote JVM**: Delegates to `bridge.attach_to_remote()` with host, port, timeout, projectName. Returns `(None, dap_port)`.

**Pooled Bridge Cleanup**: JDTLSCleanupHooks checks if bridge is pooled before stopping. Pooled bridges are shared across sessions and must not be stopped - only the reference is cleared.

## Usage Patterns

**Basic .java file**: Auto-compiles to .class, sets breakpoints
**Pre-compiled .class**: Requires main_class and classpath
**JAR file**: Requires main_class (reads from manifest if not provided)
**Remote attach**: Uses host, port (JDWP), projectName
**VS Code launch.json**: Supports mainClass, projectName, classPaths, vmArgs, args with variable substitution

## Reusable Code Reference

### Base Classes

- `DebugAdapter` - `src/aidb/adapters/base/adapter.py`
- `AdapterConfig` - `src/aidb/adapters/base/config.py`
- `Obj` - `src/aidb/patterns/base.py` (base class for all components)

### Java-Specific Components

**Main Adapter**:

- `JavaAdapter` - `src/aidb/adapters/lang/java/java.py`
- `JavaAdapterConfig` - `src/aidb/adapters/lang/java/config.py`
- `JavaLaunchConfig` - `src/aidb/adapters/lang/java/config.py`

**LSP Components** (`src/aidb/adapters/lang/java/lsp/`):

- `JavaLSPDAPBridge` - `lsp_bridge.py` - High-level LSP-DAP orchestrator
- `LSPClient` - `lsp_client.py` - Low-level LSP communication
- `LSPProtocol` - `lsp_protocol.py` - Protocol types & validation
- `LSPMessageHandler` - `lsp_message_handler.py` - Message parsing & dispatch
- `LSPInitialization` - `lsp_initialization.py` - Initialization helpers
- `JDTLSProcessManager` - `jdtls_process_manager.py` - Process lifecycle
- `WorkspaceManager` - `workspace_manager.py` - Workspace & project mgmt
- `DebugSessionManager` - `debug_session_manager.py` - Debug session delegation

**Hook Components** (`src/aidb/adapters/lang/java/hooks/`):

- `JavaEnvironmentValidator` - `lifecycle_hooks.py` - Environment validation
- `JDTLSSetupHooks` - `lifecycle_hooks.py` - Pre-launch setup
- `JDTLSReadinessHooks` - `lifecycle_hooks.py` - Post-launch readiness
- `JDTLSCleanupHooks` - `lifecycle_hooks.py` - Post-stop cleanup

**Tooling Components** (`src/aidb/adapters/lang/java/tooling/`):

- `JavaToolchain` - `java_toolchain.py` - Java/javac executable discovery
- `JavaClasspathBuilder` - `classpath_builder.py` - Classpath construction, flattening, test-classes
- `JavaBuildSystemDetector` - `build_system_detector.py` - Maven/Gradle project root detection

**Source Path Detection**:

- `detect_java_source_paths()` - `source_detection.py` - Auto-detect Maven/Gradle source paths
  - Recursively scans for `pom.xml`, `build.gradle`, `build.gradle.kts`
  - Collects standard source dirs: `src/main/java`, `src/test/java`, `src/main/kotlin`, etc.
  - Used by MCP session start for automatic source path resolution in remote debugging

**Legacy/Compatibility**:

- `JavaCompilationManager` - `compilation.py` - Compilation management
- `JDTLSProjectPool` - `jdtls_project_pool.py` - JDT LS pooling (LRU cache)

### Shared Utilities

- `close_subprocess_transports()` - `src/aidb_common/io/subprocess.py`
  - Closes all subprocess transports (stdin/stdout/stderr) to prevent ResourceWarnings
  - Called automatically by ProcessManager.stop() and Java adapter cleanup hooks
  - Use when managing custom async subprocesses outside standard components
- `ProcessTags` - `src/aidb/resources/process_tags.py`
  - Process tagging for orphan detection and cleanup
  - Used by JDTLSProcessManager to tag JDT LS processes

## Common Pitfalls

1. **Missing JDK_HOME** - JDK (not JRE) required for javac
1. **Missing projectName** - Required for JDT LS evaluation context
1. **Wrong classpath** - Must include compiled .class directory
1. **Pooled bridge cleanup** - Never stop pooled bridges (shared across sessions)
1. **Slow startup** - Use JDT LS pooling (8-9s → instant, enabled by default)
1. **Pass .java not .class to bridge** - Source needed for source mapping

______________________________________________________________________

**See also**: [Adapter Development Main Skill](../SKILL.md) | [Python Patterns](python-adapter-patterns.md) | [JavaScript Patterns](javascript-adapter-patterns.md)
