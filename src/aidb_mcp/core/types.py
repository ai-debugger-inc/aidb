"""Type definitions for common MCP dictionary patterns.

This module provides TypedDict definitions to improve type safety and IDE support
throughout the MCP codebase without changing runtime behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypedDict, runtime_checkable

if TYPE_CHECKING:
    from enum import Enum


class ToolAction(TypedDict, total=False):
    """Type definition for tool action suggestions in next steps.

    Attributes
    ----------
    tool : str
        The tool name (typically from ToolName enum)
    description : str
        Brief description of what the action does
    when : str
        When to use this action (e.g., "immediately", "to verify")
    params_example : Dict[str, Any]
        Example parameters for the tool
    tip : str, optional
        Additional helpful tip or context
    reason : str, optional
        Why this action is suggested
    """

    tool: str
    description: str
    when: str
    params_example: dict[str, Any]
    tip: str  # Optional field
    reason: str  # Optional field


class OperationContext(TypedDict, total=False):
    """Context for MCP operations.

    Attributes
    ----------
    operation : str
        The operation being performed
    target : str, optional
        Target of the operation
    action : str, optional
        Specific action within the operation
    """

    operation: str
    target: str  # Optional
    action: str  # Optional


class ErrorContext(TypedDict, total=False):
    """Context information for error responses.

    Attributes
    ----------
    operation : str, optional
        The operation that failed
    target : str, optional
        Target that caused the error
    available_tools : List[str], optional
        List of available tools for recovery
    session_id : str, optional
        Session ID if relevant
    error_type : str, optional
        Type or category of error
    details : Any, optional
        Additional details about the error
    """

    operation: str
    target: str
    available_tools: list[str]
    session_id: str
    error_type: str
    details: Any
    # Additional optional context keys used by handlers
    language: str
    download_url_attempted: bool
    manual_instructions_available: bool
    failed_count: int
    total_count: int
    invalid_input: str
    tool_name: str
    cancelled: bool


class SessionInfo(TypedDict, total=False):
    """Session state information.

    Attributes
    ----------
    session_id : str
        Unique session identifier
    status : str
        Current session status
    current_position : Optional[Dict[str, Any]]
        Current execution position
    breakpoints_set : list[BreakpointSpec]
        List of active breakpoints
    suggested_tools : List[str]
        Suggested tools for current state
    language : str, optional
        Programming language of the session
    target : str, optional
        Debug target (file, process, etc.)
    pid : int, optional
        Process ID if applicable
    """

    session_id: str
    status: str
    current_position: dict[str, Any] | None
    breakpoints_set: list[BreakpointSpec]
    suggested_tools: list[str]
    language: str
    target: str
    pid: int


class BreakpointSpec(TypedDict, total=False):
    """Unified breakpoint specification schema for MCP layer.

    This TypedDict defines the standard format for all breakpoint specifications
    in the MCP layer. Must be compatible with the core aidb BreakpointSpec.

    Attributes
    ----------
    file : str
        Path to the source file (absolute or relative).
        Required field.
    line : int
        Line number for the breakpoint (1-based).
        Required field.
    column : int, optional
        Column number for precise placement in minified code (1-based).
    condition : str, optional
        Conditional expression that must evaluate to true to trigger the breakpoint.
        Example: "x > 5 and y < 10"
    hit_condition : str, optional
        Expression controlling how many hits are required to trigger.
        Examples: "5" (exactly 5 hits), ">5" (more than 5), "%5" (every 5th hit)
    log_message : str, optional
        Message to log instead of pausing execution (creates a logpoint).
        Can include expressions in curly braces: "x = {x}, y = {y}"
    """

    file: str
    line: int
    column: int | None
    condition: str | None
    hit_condition: str | None
    log_message: str | None


class InspectionData(TypedDict, total=False):
    """Data returned from inspection operations.

    Attributes
    ----------
    locals : Dict[str, Any], optional
        Local variables
    globals : Dict[str, Any], optional
        Global variables
    expression : str, optional
        Evaluated expression
    result : Any, optional
        Result of expression evaluation
    stack : List[Dict[str, Any]], optional
        Call stack frames
    threads : List[Dict[str, Any]], optional
        Thread information
    """

    locals: dict[str, Any]
    globals: dict[str, Any]
    expression: str
    result: Any
    stack: list[dict[str, Any]]
    threads: list[dict[str, Any]]


class ExecutionState(TypedDict, total=False):
    """Current execution state.

    Attributes
    ----------
    execution_paused : bool
        Whether execution is paused
    current_location : Optional[Dict[str, Any]]
        Current code location
    thread_count : int
        Number of active threads
    ready_for_commands : bool
        Whether debugger can accept commands
    stop_reason : str, optional
        Reason for current pause
    """

    execution_paused: bool
    current_location: dict[str, Any] | None
    thread_count: int
    ready_for_commands: bool
    stop_reason: str


class ToolParams(TypedDict, total=False):
    """Generic tool parameters.

    This is a base type for tool parameters. Specific tools should define more specific
    parameter types.
    """

    action: str
    target: str
    location: str
    expression: str
    name: str
    value: Any
    line: int
    condition: str


class VariableValue(TypedDict, total=False):
    """Structured representation of a debugger variable.

    Attributes
    ----------
    name : str
        Variable name
    value : str | int | float | bool | None
        Variable value (primitive types or stringified complex types)
    type : str, optional
        Type name of the variable
    evaluateName : str, optional
        Expression to re-evaluate this variable
    variablesReference : int, optional
        Reference ID for child variables (0 if no children)
    namedVariables : int, optional
        Number of named child variables
    indexedVariables : int, optional
        Number of indexed child variables
    """

    name: str
    value: str | int | float | bool | None
    type: str
    evaluateName: str
    variablesReference: int
    namedVariables: int
    indexedVariables: int


class VariableList(TypedDict, total=False):
    """List of variables with optional truncation metadata.

    Attributes
    ----------
    variables : list[VariableValue]
        List of variable values
    truncated : bool, optional
        Whether the list was truncated
    total_variables : int, optional
        Total number of variables before truncation
    showing_variables : int, optional
        Number of variables shown after truncation
    """

    variables: list[VariableValue]
    truncated: bool
    total_variables: int
    showing_variables: int


class StackFrameDict(TypedDict, total=False):
    """Stack frame representation.

    Attributes
    ----------
    level : int
        Stack frame level (0 is current frame)
    function : str
        Function or method name
    file : str | None
        Source file path
    line : int
        Line number in source file
    column : int, optional
        Column number in source file
    locals : dict[str, Any], optional
        Local variables in this frame
    """

    level: int
    function: str
    file: str | None
    line: int
    column: int
    locals: dict[str, Any]


class StackFrameList(TypedDict, total=False):
    """Stack frames with optional truncation metadata.

    Attributes
    ----------
    frames : list[StackFrameDict]
        List of stack frames
    truncated : bool, optional
        Whether the list was truncated
    total_frames : int, optional
        Total number of frames before truncation
    showing_frames : int, optional
        Number of frames shown after truncation
    """

    frames: list[StackFrameDict]
    truncated: bool
    total_frames: int
    showing_frames: int


class ThreadInfo(TypedDict, total=False):
    """Thread information.

    Attributes
    ----------
    id : int
        Thread ID
    name : str
        Thread name
    """

    id: int
    name: str


class LocationDict(TypedDict, total=False):
    """Source location information.

    Attributes
    ----------
    file : str | None
        File path
    line : int
        Line number
    function : str
        Function or method name
    frame_id : int, optional
        Stack frame ID
    """

    file: str | None
    line: int
    function: str
    frame_id: int


class ExecutionHistoryEntry(TypedDict, total=False):
    """Record of an execution step.

    Attributes
    ----------
    action : str
        The action performed (step, continue, etc.)
    timestamp : str
        ISO format timestamp
    file : str | None
        File where action occurred
    line : int | None
        Line number where action occurred
    thread : int | None
        Thread ID where action occurred
    """

    action: str
    timestamp: str
    file: str | None
    line: int | None
    thread: int | None


InspectionResult: TypeAlias = (
    list[VariableValue]
    | VariableList
    | list[StackFrameDict]
    | StackFrameList
    | list[ThreadInfo]
    | dict[str, Any]
    | str
    | int
    | float
    | bool
    | None
)

MCPResponse: TypeAlias = dict[str, Any]


@runtime_checkable
class DebugAdapterConfig(Protocol):
    """Protocol for debug adapter configurations.

    This protocol defines the interface that all adapter configurations must provide.
    Used in starters/base.py to avoid circular imports and provide type safety.
    """

    language: str
    adapter_id: str
    adapter_port: int
    file_extensions: list[str]
    supported_frameworks: list[str]
    framework_examples: list[str]

    def get_initialization_sequence(self) -> list[Any]:
        """Get the DAP initialization sequence for this adapter.

        Returns
        -------
        list[Any]
            The ordered list of operations to perform during initialization
        """
        ...


@runtime_checkable
class EnumClass(Protocol):
    """Protocol for Enum classes used in action validation.

    This protocol allows type-safe validation of action strings against Enum classes
    without requiring a concrete Enum type.
    """

    @property
    def value(self) -> str:
        """Get the enum value.

        Returns
        -------
        str
            The enum value
        """
        ...


@runtime_checkable
class SessionProtocol(Protocol):
    """Protocol for session objects with status.

    Used in helpers.py not_paused() function to access session status.
    """

    @property
    def status(self) -> Enum:
        """Get the session status.

        Returns
        -------
        Enum
            The session status enum value
        """
        ...
