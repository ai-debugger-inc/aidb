"""Complete MCP tool registry with agent-optimized interface.

Architecture:
- Context Discovery (1 tool) - Entry point for debugging assistance
- Intent-Based Workflows (1 tool) - What you want to achieve
- Enhanced Direct Control (7 tools) - Fine-grained control when needed
- Advanced Operations (2 tools) - Specialized scenarios
- Adapter Management Tools (1 tool) - Download/install/list debug adapters
"""

from __future__ import annotations

from mcp.types import Tool, ToolAnnotations

from ..core.constants import (
    DetailLevel,
    LaunchMode,
    NotificationEventType,
    ParamName,
    ToolName,
)
from ..utils.tool_helpers import create_language_param_schema
from .actions import (
    AdapterAction,
    BreakpointAction,
    ConfigAction,
    ExecutionAction,
    InspectTarget,
    SessionAction,
    StepAction,
    VariableAction,
)
from .icons import get_tool_icon


def get_all_mcp_tools() -> list[Tool]:
    """Get the complete set of 12 agent-optimized MCP tools.

    Returns
    -------
    List[Tool]
        Complete tool definitions optimized for agent cognitive simplicity
    """
    tools = []

    # ===== CONTEXT DISCOVERY (1 tool) =====
    # Entry point for debugging assistance - ALWAYS CALL THIS FIRST!

    # Context-aware debugging assistant
    tools.append(
        Tool(
            name=ToolName.INIT,
            title="Initialize Debugging Context",
            description=(
                "🚀 **REQUIRED FIRST STEP** - Initialize debugging context and get "
                "language-specific examples.\n\n"
                "This is the mandatory entry point for debugging. You MUST call this "
                "before any other debugging operation. It provides:\n"
                "- Language-specific examples (Python, JavaScript, TypeScript, Java)\n"
                "- Framework-aware patterns (pytest, jest, django, spring, etc.)\n"
                "- Workspace-aware configuration discovery\n"
                "- Clear usage examples with exact syntax\n\n"
            ),
            icons=get_tool_icon(ToolName.INIT),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.LANGUAGE: create_language_param_schema(),
                    "mode": {
                        "type": "string",
                        "enum": [mode.value for mode in LaunchMode],
                        "description": (
                            f"Debug mode: '{LaunchMode.LAUNCH.value}' (start new "
                            "process), "
                            f"'{LaunchMode.ATTACH.value}' (attach to PID), "
                            f"'{LaunchMode.REMOTE_ATTACH.value}' (attach to "
                            "host:port). "
                            f"Default: {LaunchMode.LAUNCH.value}"
                        ),
                    },
                    ParamName.FRAMEWORK: {
                        "type": "string",
                        "description": (
                            "Optional framework (pytest, jest, django, spring, etc.)"
                        ),
                    },
                    ParamName.WORKSPACE_ROOT: {
                        "type": "string",
                        "description": (
                            "Root directory of the workspace for discovering "
                            "launch.json and project context"
                        ),
                    },
                    ParamName.WORKSPACE_ROOTS: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Multiple workspace roots for multi-root workspaces "
                            "(e.g., microservices). Use this instead of workspace_root "
                            "when debugging across multiple projects."
                        ),
                    },
                    ParamName.LAUNCH_CONFIG_NAME: {
                        "type": "string",
                        "description": (
                            "Name of VS Code launch configuration to reference"
                        ),
                    },
                    ParamName.VERBOSE: {
                        "type": "boolean",
                        "description": (
                            "Include educational content (key concepts, examples). "
                            "Default: false for concise responses"
                        ),
                    },
                },
                "required": ["language"],
            },
        ),
    )

    # ===== INTENT-BASED WORKFLOWS (1 tool) =====
    # What you want to achieve

    # Session Creation and Startup
    tools.append(
        Tool(
            name=ToolName.SESSION_START,
            title="Start Debug Session",
            description=(
                "🚀 Create and start a debug session "
                "(requires init to be called first).\n\n"
                "Supports launch/attach modes for debugging.\n"
            ),
            icons=get_tool_icon(ToolName.SESSION_START),
            annotations=ToolAnnotations(
                destructiveHint=False,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.TARGET: {
                        "type": "string",
                        "description": (
                            "ENTRYPOINT file/exec that starts execution and triggers "
                            "the codepath you want to debug. This is NOT where you set "
                            "breakpoints - use the 'breakpoints' parameter for those. "
                            "Example: target='main.py' starts app, breakpoints can be "
                            "in utils/helper.py, models/user.py, etc."
                        ),
                    },
                    ParamName.PID: {
                        "type": "integer",
                        "description": (
                            "Process ID to attach to (for local attach mode)"
                        ),
                    },
                    ParamName.HOST: {
                        "type": "string",
                        "description": ("Host to connect to (for remote attach mode)"),
                    },
                    ParamName.PORT: {
                        "type": "integer",
                        "description": ("Port to connect to (for remote attach mode)"),
                    },
                    ParamName.LANGUAGE: create_language_param_schema(),
                    ParamName.BREAKPOINTS: {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string", "description": "File path"},
                                "line": {
                                    "type": "integer",
                                    "description": "Line number",
                                },
                                "condition": {
                                    "type": "string",
                                    "description": "Optional condition (e.g., 'x > 5')",
                                },
                                "hit_condition": {
                                    "type": "string",
                                    "description": (
                                        "Optional hit condition (e.g., '>5' or '%10')"
                                    ),
                                },
                                "log_message": {
                                    "type": "string",
                                    "description": (
                                        "Optional log message instead of pausing"
                                    ),
                                },
                            },
                            "required": ["file", "line"],
                        },
                        "description": (
                            "Initial breakpoints as objects with 'file' and 'line' "
                            "fields. Can be in ANY files, often DIFFERENT from the "
                            "target. The target starts execution, breakpoints pause "
                            "where you want to debug. Ex: [{'file': 'src/models/"
                            "user.py', 'line': 42}, {'file': 'utils/validator.py', "
                            "'line': 15, 'condition': 'x > 0'}]"
                        ),
                    },
                    ParamName.ARGS: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": ("Command line arguments (for launch mode)"),
                    },
                    ParamName.ENV: {
                        "type": "object",
                        "description": "Environment variables (for launch mode)",
                    },
                    ParamName.CWD: {
                        "type": "string",
                        "description": "Working directory (for launch mode)",
                    },
                    ParamName.LAUNCH_CONFIG_NAME: {
                        "type": "string",
                        "description": "VS Code launch configuration name",
                    },
                    ParamName.WORKSPACE_ROOT: {
                        "type": "string",
                        "description": "Workspace root directory",
                    },
                    ParamName.SOURCE_PATHS: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Additional source directories for resolving file paths. "
                            "Used for remote debugging where debug adapter returns "
                            "paths that don't exist locally (e.g., JAR-internal paths "
                            "like 'trino-main.jar!/io/trino/Foo.java'). Each path "
                            "should be a local directory containing source files."
                        ),
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": (
                            "Optional session ID (generated if not provided)"
                        ),
                    },
                    ParamName.SUBSCRIBE_EVENTS: {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                e.value
                                for e in NotificationEventType
                                if e.value != "terminated"
                            ],
                        },
                        "description": (
                            "Events to subscribe to for notifications. "
                            f"'{NotificationEventType.TERMINATED.value}' and "
                            f"'{NotificationEventType.BREAKPOINT.value}' are always "
                            "auto-subscribed. "
                            f"Options: '{NotificationEventType.EXCEPTION.value}' "
                            "(any exception occurred)"
                        ),
                    },
                },
            },
        ),
    )

    # ===== ENHANCED DIRECT CONTROL (7 tools) =====
    # Fine-grained control when needed

    # Enhanced Execution Control (with jump capabilities)
    tools.append(
        Tool(
            name=ToolName.EXECUTE,
            title="Execute Program",
            description=(
                "Execute the program with different actions and capabilities.\n\n"
                "Actions:\n"
                f"- '{ExecutionAction.RUN.value}': Start execution from beginning\n"
                f"- '{ExecutionAction.CONTINUE.value}': Continue from current position "
                "(default)\n\n"
                "Enhanced features:\n"
                "- Smart execution until specific conditions\n"
                "- Output collection and analysis\n"
                "- Automatic breakpoint management"
            ),
            icons=get_tool_icon(ToolName.EXECUTE),
            annotations=ToolAnnotations(
                destructiveHint=False,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [mode.value for mode in ExecutionAction],
                        "description": "Execution action",
                        "default": ExecutionAction.CONTINUE.value,
                    },
                    ParamName.UNTIL: {
                        "type": "string",
                        "description": "Execute until this location (``file:line``)",
                    },
                    ParamName.JUMP_TARGET: {
                        "type": "string",
                        "description": (
                            "Jump to this location (``file:line``) - for jump action"
                        ),
                    },
                    ParamName.WAIT_FOR_STOP: {
                        "type": "boolean",
                        "description": (
                            "Wait for breakpoint/stop event. Auto-enabled when "
                            "breakpoints exist (default: auto)"
                        ),
                    },
                    ParamName.COLLECT_OUTPUT: {
                        "type": "boolean",
                        "description": "Collect program output",
                        "default": True,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Step Control
    tools.append(
        Tool(
            name=ToolName.STEP,
            title="Step Through Code",
            description=(
                "Step through code execution.\n\n"
                "Actions:\n"
                f"- '{StepAction.OVER.value}': Execute line without entering "
                "functions (default)\n"
                f"- '{StepAction.INTO.value}': Enter function calls\n"
                f"- '{StepAction.OUT.value}': Complete current function"
            ),
            icons=get_tool_icon(ToolName.STEP),
            annotations=ToolAnnotations(
                destructiveHint=False,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [mode.value for mode in StepAction],
                        "description": "Step action",
                        "default": StepAction.OVER.value,
                    },
                    ParamName.COUNT: {
                        "type": "integer",
                        "description": "Number of steps",
                        "default": 1,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Inspection
    tools.append(
        Tool(
            name=ToolName.INSPECT,
            title="Inspect Program State",
            description=(
                "Inspect program state during debugging.\n\n"
                "Available modes:\n"
                f"- '{InspectTarget.LOCALS.value}': Local variables (default)\n"
                f"- '{InspectTarget.GLOBALS.value}': Global variables\n"
                f"- '{InspectTarget.STACK.value}': Call stack with frames\n"
                f"- '{InspectTarget.THREADS.value}': All thread states\n"
                f"- '{InspectTarget.EXPRESSION.value}': Evaluate specific expression\n"
                f"- '{InspectTarget.ALL.value}': Complete state snapshot"
            ),
            icons=get_tool_icon(ToolName.INSPECT),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.TARGET: {
                        "type": "string",
                        "enum": [target.value for target in InspectTarget],
                        "description": "What to inspect",
                        "default": InspectTarget.LOCALS.value,
                    },
                    ParamName.EXPRESSION: {
                        "type": "string",
                        "description": "Expression to evaluate",
                    },
                    ParamName.FRAME: {
                        "type": "integer",
                        "description": "Stack frame to inspect (0 = current)",
                        "default": 0,
                    },
                    ParamName.DETAILED: {
                        "type": "boolean",
                        "description": "Include detailed information",
                        "default": False,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Breakpoint Management
    tools.append(
        Tool(
            name=ToolName.BREAKPOINT,
            title="Manage Breakpoints",
            description=(
                "Manage breakpoints. Supports conditions (condition='x>5'), "
                "hit counts (hit_condition='>3' to skip first 3 hits), "
                "and logpoints (log_message='val={x}').\n\n"
                "Actions:\n"
                f"- '{BreakpointAction.SET.value}': Set a breakpoint (default)\n"
                f"- '{BreakpointAction.REMOVE.value}': Remove a breakpoint\n"
                f"- '{BreakpointAction.LIST.value}': List all breakpoints\n"
                f"- '{BreakpointAction.CLEAR_ALL.value}': Remove all breakpoints\n"
                f"- '{BreakpointAction.WATCH.value}': Set watchpoint (Java only)\n"
                f"- '{BreakpointAction.UNWATCH.value}': Remove watchpoint (Java only)"
            ),
            icons=get_tool_icon(ToolName.BREAKPOINT),
            annotations=ToolAnnotations(
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [action.value for action in BreakpointAction],
                        "description": "Breakpoint action",
                        "default": BreakpointAction.SET.value,
                    },
                    ParamName.LOCATION: {
                        "type": "string",
                        "description": (
                            "Breakpoint location (``file:line`` or "
                            "``file:line:column``)"
                        ),
                    },
                    ParamName.COLUMN: {
                        "type": "integer",
                        "description": (
                            "Column number for precise breakpoint placement "
                            "(for minified code)"
                        ),
                    },
                    ParamName.CONDITION: {
                        "type": "string",
                        "description": "Conditional expression (e.g., 'x > 10')",
                    },
                    ParamName.HIT_CONDITION: {
                        "type": "string",
                        "description": (
                            "Hit count condition (e.g., '> 5' to break after 5 hits)"
                        ),
                    },
                    ParamName.LOG_MESSAGE: {
                        "type": "string",
                        "description": "Log message instead of pausing (logpoint)",
                    },
                    ParamName.NAME: {
                        "type": "string",
                        "description": (
                            "Variable name for watch action (e.g., 'user.email')"
                        ),
                    },
                    ParamName.ACCESS_TYPE: {
                        "type": "string",
                        "enum": ["read", "write", "readWrite"],
                        "default": "write",
                        "description": (
                            "Access type for watch action: "
                            "'read', 'write', or 'readWrite'"
                        ),
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Enhanced Variable Management (with patch/fix capabilities)
    tools.append(
        Tool(
            name=ToolName.VARIABLE,
            title="Variable Operations",
            description=(
                "Enhanced variable operations with live patching capabilities.\n\n"
                + "Actions:\n"
                + f"- '{VariableAction.GET.value}': Evaluate expression (default)\n"
                + f"- '{VariableAction.SET.value}': Set variable value\n"
                + (
                    f"- '{VariableAction.PATCH.value}': Live code patching for "
                    "rapid iteration (replaces aidb.fix)\n\n"
                )
                + "Examples:\n"
                + "- variable('get', expression='user.name')\n"
                + "- variable('set', name='debug_mode', value='True')\n"
                + (
                    "- variable('patch', name='calculate_tax', "
                    "code='return amount * 0.08')"
                )
            ),
            icons=get_tool_icon(ToolName.VARIABLE),
            annotations=ToolAnnotations(
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [action.value for action in VariableAction],
                        "description": "Variable operation type",
                        "default": VariableAction.GET.value,
                    },
                    ParamName.EXPRESSION: {
                        "type": "string",
                        "description": "Expression to evaluate (for 'get' action)",
                    },
                    ParamName.NAME: {
                        "type": "string",
                        "description": (
                            "Variable/function name (for 'set'/'patch' actions)"
                        ),
                    },
                    ParamName.VALUE: {
                        "type": "string",
                        "description": "New value (for 'set' action)",
                    },
                    ParamName.CODE: {
                        "type": "string",
                        "description": "New code (for 'patch' action)",
                    },
                    ParamName.FRAME: {
                        "type": "integer",
                        "description": "Stack frame context (0 = current)",
                        "default": 0,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Session Management (consolidated)
    tools.append(
        Tool(
            name=ToolName.SESSION,
            title="Session Management",
            description=(
                "Comprehensive session lifecycle management.\n\n"
                "**Actions:**\n"
                f"• `{SessionAction.STATUS.value}`: "
                "Show current session status (default)\n"
                f"• `{SessionAction.LIST.value}`: List all active sessions\n"
                f"• `{SessionAction.STOP.value}`: Stop current/specified session\n"
                f"• `{SessionAction.RESTART.value}`: "
                "Restart session with same configuration\n"
                f"• `{SessionAction.SWITCH.value}`: Switch to different session"
            ),
            icons=get_tool_icon(ToolName.SESSION),
            annotations=ToolAnnotations(
                destructiveHint=True,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [action.value for action in SessionAction],
                        "description": "Session management action",
                        "default": SessionAction.STATUS.value,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Target session ID (for stop/restart/switch)",
                    },
                    ParamName.KEEP_BREAKPOINTS: {
                        "type": "boolean",
                        "description": "Keep existing breakpoints on restart",
                        "default": True,
                    },
                },
            },
        ),
    )

    # Configuration & Environment (with capabilities integration)
    tools.append(
        Tool(
            name=ToolName.CONFIG,
            title="Configuration & Environment",
            description=(
                "Configuration and environment management.\n\n"
                "**Actions:**\n"
                f"• `{ConfigAction.SHOW.value}`: "
                "Show current configuration (default)\n"
                f"• `{ConfigAction.ENV.value}`: Show/set environment variables\n"
                f"• `{ConfigAction.LAUNCH.value}`: "
                "Discover and manage VS Code launch.json configurations\n"
                f"• `{ConfigAction.CAPABILITIES.value}`: "
                "Show debugging capabilities for languages "
                "(replaces aidb.capabilities)\n"
                f"• `{ConfigAction.ADAPTERS.value}`: "
                "Check debug adapter installation status\n\n"
                "**Examples:**\n"
                f"• config('{ConfigAction.ENV.value}') - "
                "Show AIDB_* environment variables\n"
                f"• config('{ConfigAction.LAUNCH.value}') - "
                "List available launch configurations\n"
                f"• config('{ConfigAction.ADAPTERS.value}') - "
                "Show installed debug adapters\n"
                f"• config('{ConfigAction.CAPABILITIES.value}', "
                "language='python') - Python debugging features"
            ),
            icons=get_tool_icon(ToolName.CONFIG),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [action.value for action in ConfigAction],
                        "description": "Configuration action",
                        "default": ConfigAction.SHOW.value,
                    },
                    ParamName.KEY: {
                        "type": "string",
                        "description": "Environment variable key (for env action)",
                    },
                    ParamName.VALUE: {
                        "type": "string",
                        "description": "Environment variable value (for env action)",
                    },
                    ParamName.LANGUAGE: create_language_param_schema(),
                    ParamName.CONFIG_NAME: {
                        "type": "string",
                        "description": "Launch configuration name (for launch action)",
                    },
                },
            },
        ),
    )

    # ===== ADVANCED OPERATIONS (2 tools) =====
    # Specialized scenarios

    # Context & State Awareness
    tools.append(
        Tool(
            name=ToolName.CONTEXT,
            title="Get Debugging Context",
            description=(
                "Rich debugging context and intelligent next-step suggestions.\n\n"
                "Provides:\n"
                "- Current debugging state and session memory\n"
                "- Recent operations and their outcomes\n"
                "- Intelligent next-step recommendations\n"
                "- Cross-tool workflow suggestions\n"
                "- Debugging history and patterns"
            ),
            icons=get_tool_icon(ToolName.CONTEXT),
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.DETAIL_LEVEL: {
                        "type": "string",
                        "enum": [level.value for level in DetailLevel],
                        "description": "Level of context detail",
                        "default": DetailLevel.DETAILED.value,
                    },
                    ParamName.INCLUDE_SUGGESTIONS: {
                        "type": "boolean",
                        "description": "Include next-step suggestions",
                        "default": True,
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
            },
        ),
    )

    # Temporary Breakpoints
    tools.append(
        Tool(
            name=ToolName.RUN_UNTIL,
            title="Run Until Location",
            description=(
                "Run until a specific location with temporary breakpoints.\n\n"
                + (
                    "Sets one-time breakpoints that are automatically removed "
                    "after being hit.\n"
                )
                + (
                    "Useful for quickly running to specific locations without "
                    "permanent breakpoints.\n\n"
                )
                + "Enhanced features:\n"
                "- Multiple target locations\n"
                "- Conditional temporary breakpoints\n"
                "- Automatic cleanup"
            ),
            icons=get_tool_icon(ToolName.RUN_UNTIL),
            annotations=ToolAnnotations(
                destructiveHint=False,
                openWorldHint=False,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.LOCATION: {
                        "type": "string",
                        "description": (
                            "Primary target location (file.py:line or line number)"
                        ),
                    },
                    ParamName.ALTERNATIVE_LOCATIONS: {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative locations to stop at",
                    },
                    ParamName.CONDITION: {
                        "type": "string",
                        "description": "Optional condition for temporary breakpoint",
                    },
                    ParamName.SESSION_ID: {
                        "type": "string",
                        "description": "Optional session ID",
                    },
                },
                "required": ["location"],
            },
        ),
    )

    # ===== ADAPTER MANAGEMENT TOOL (1 tool) =====
    # Consolidated adapter management with action-based dispatch

    # Adapter Management
    tools.append(
        Tool(
            name=ToolName.ADAPTER,
            title="Manage Debug Adapters",
            description=(
                "Consolidated adapter management with action-based operations\n\n"
                "**Actions:**\n"
                f"• `{AdapterAction.DOWNLOAD.value}`: "
                "Download and install a specific language adapter "
                "(requires language)\n"
                f"• `{AdapterAction.DOWNLOAD_ALL.value}`: "
                "Download and install all available adapters (language ignored)\n"
                f"• `{AdapterAction.LIST.value}`: "
                "List installed adapters and status (language optional)\n\n"
                "**Management:**\n"
                "Downloads debug adapters from GitHub releases to ~/.aidb/adapters/. "
                "Versions match current project. "
                "Validates language support dynamically.\n\n"
                "**Aliases:** install→download, install_all→download_all, "
                "status/show→list\n\n"
                "**Usage:** Install missing adapters when encountering "
                "AdapterNotFoundError messages."
            ),
            icons=get_tool_icon(ToolName.ADAPTER),
            annotations=ToolAnnotations(
                destructiveHint=True,
                idempotentHint=True,
                openWorldHint=True,
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    ParamName.ACTION: {
                        "type": "string",
                        "enum": [action.value for action in AdapterAction],
                        "description": "Adapter management action",
                        "default": AdapterAction.LIST.value,
                    },
                    ParamName.LANGUAGE: create_language_param_schema(),
                    ParamName.VERSION: {
                        "type": "string",
                        "description": (
                            "Specific version to download (download action only). "
                            "Defaults to latest version matching current project"
                        ),
                    },
                    ParamName.FORCE: {
                        "type": "boolean",
                        "description": (
                            "Force re-download if already installed "
                            "(download/download_all actions). "
                            "Use when adapters need updating or are corrupted"
                        ),
                        "default": False,
                    },
                },
            },
        ),
    )

    return tools
