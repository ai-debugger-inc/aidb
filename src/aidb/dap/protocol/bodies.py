"""DAP Protocol - DAP message body and arguments classes.

Auto-generated from Debug Adapter Protocol specification. Do not edit
manually."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from .base import (
    DAPDataclass,
    OperationEventBody,
    OperationResponseBody,
)
from .types import *  # noqa: F403

if TYPE_CHECKING:
    from .types import (
        Breakpoint,
        BreakpointLocation,
        Capabilities,
        CompletionItem,
        DataBreakpoint,
        DataBreakpointAccessType,
        DisassembledInstruction,
        ExceptionBreakMode,
        ExceptionDetails,
        ExceptionFilterOptions,
        ExceptionOptions,
        FunctionBreakpoint,
        GotoTarget,
        InstructionBreakpoint,
        InvalidatedAreas,
        Message,
        Module,
        Scope,
        Source,
        SourceBreakpoint,
        StackFrame,
        StackFrameFormat,
        StepInTarget,
        SteppingGranularity,
        Thread,
        ValueFormat,
        Variable,
        VariablePresentationHint,
    )


@dataclass
class AttachRequestArguments(DAPDataclass):
    """Arguments for `attach` request. Additional attributes are implementation
    specific.

    Attributes
    ----------
    __restart : Optional[Union[List[Any], bool, int, float, Dict[str, Any],
    str]]
        Arbitrary data from the previous, restarted session. The data is sent as
        the `restart` attribute of the `terminated` event. The client should
        leave the data intact.

    """

    # _spec.json#1468

    __restart: list[Any] | bool | int | float | dict[str, Any] | str | None = None


@dataclass
class BreakpointEventBody(OperationEventBody):
    """('Event body for BreakpointEvent.',)."""

    # _spec.json#597

    breakpoint: "Breakpoint"
    reason: str


@dataclass
class BreakpointLocationsArguments(DAPDataclass):
    """Arguments for `breakpointLocations` request.

    Attributes
    ----------
    source : Source
        The source location of the breakpoints; either `source.path` or
        `source.sourceReference` must be specified.

    line : int
        Start line of range to search possible breakpoint locations in. If only
        the line is specified, the request returns all possible locations in
        that line.

    column : Optional[int]
        Start position within `line` to search possible breakpoint locations in.
        It is measured in UTF-16 code units and the client capability
        `columnsStartAt1` determines whether it is 0- or 1-based. If no column
        is given, the first position in the start line is assumed.

    endLine : Optional[int]
        End line of range to search possible breakpoint locations in. If no end
        line is given, then the end line is assumed to be the start line.

    endColumn : Optional[int]
        End position within `endLine` to search possible breakpoint locations
        in. It is measured in UTF-16 code units and the client capability
        `columnsStartAt1` determines whether it is 0- or 1-based. If no end
        column is given, the last position in the end line is assumed.

    """

    # _spec.json#1675

    line: int
    source: "Source"
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None


@dataclass
class BreakpointLocationsResponseBody(OperationResponseBody):
    """('Response body for BreakpointLocationsResponse.',)."""

    # _spec.json#1705

    breakpoints: list["BreakpointLocation"]


@dataclass
class CancelArguments(DAPDataclass):
    """Arguments for `cancel` request.

    Attributes
    ----------
    requestId : Optional[int]
        The ID (attribute `seq`) of the request to cancel. If missing no request
        is cancelled. Both a `requestId` and a `progressId` can be specified in
        one request.

    progressId : Optional[str]
        The ID (attribute `progressId`) of the progress to cancel. If missing no
        progress is cancelled. Both a `requestId` and a `progressId` can be
        specified in one request.

    """

    # _spec.json#220

    progressId: str | None = None
    requestId: int | None = None


@dataclass
class CapabilitiesEventBody(OperationEventBody):
    """('Event body for CapabilitiesEvent.',)."""

    # _spec.json#793

    capabilities: "Capabilities"


@dataclass
class CompletionsArguments(DAPDataclass):
    """Arguments for `completions` request.

    Attributes
    ----------
    frameId : Optional[int]
        Returns completions in the scope of this stack frame. If not specified,
        the completions are returned for the global scope.

    text : str
        One or more source lines. Typically this is the text users have typed
        into the debug console before they asked for completion.

    column : int
        The position within `text` for which to determine the completion
        proposals. It is measured in UTF-16 code units and the client capability
        `columnsStartAt1` determines whether it is 0- or 1-based.

    line : Optional[int]
        A line for which to determine the completion proposals. If missing the
        first line of the text is assumed.

    """

    # _spec.json#3824

    column: int
    text: str
    frameId: int | None = None
    line: int | None = None


@dataclass
class CompletionsResponseBody(OperationResponseBody):
    """('Response body for CompletionsResponse.',)."""

    # _spec.json#3850

    targets: list["CompletionItem"]


@dataclass
class ConfigurationDoneArguments(DAPDataclass):
    """Arguments for `configurationDone` request."""

    # _spec.json#1368



@dataclass
class ContinueArguments(DAPDataclass):
    """Arguments for `continue` request.

    Attributes
    ----------
    threadId : int
        Specifies the active thread. If the debug adapter supports single thread
        execution (see `supportsSingleThreadExecutionRequests`) and the argument
        `singleThread` is true, only the thread with this ID is resumed.

    singleThread : Optional[bool]
        If this flag is true, execution is resumed only for the thread with
        given `threadId`.

    """

    # _spec.json#2256

    threadId: int
    singleThread: bool | None = None


@dataclass
class ContinueResponseBody(OperationResponseBody):
    """('Response body for ContinueResponse.',)."""

    # _spec.json#2273

    allThreadsContinued: bool | None = None


@dataclass
class ContinuedEventBody(OperationEventBody):
    """('Event body for ContinuedEvent.',)."""

    # _spec.json#341

    threadId: int
    allThreadsContinued: bool | None = None


@dataclass
class DataBreakpointInfoArguments(DAPDataclass):
    """Arguments for `dataBreakpointInfo` request.

    Attributes
    ----------
    variablesReference : Optional[int]
        Reference to the variable container if the data breakpoint is requested
        for a child of the container. The `variablesReference` must have been
        obtained in the current suspended state. See 'Lifetime of Object
        References' in the Overview section for details.

    name : str
        The name of the variable's child to obtain data breakpoint information
        for. If `variablesReference` isn't specified, this can be an expression,
        or an address if `asAddress` is also true.

    frameId : Optional[int]
        When `name` is an expression, evaluate it in the scope of this stack
        frame. If not specified, the expression is evaluated in the global
        scope. When `variablesReference` is specified, this property has no
        effect.

    bytes : Optional[int]
        If specified, a debug adapter should return information for the range of
        memory extending `bytes` number of bytes from the address or variable
        specified by `name`. Breakpoints set using the resulting data ID should
        pause on data access anywhere within that range. Clients may set this
        property only if the `supportsDataBreakpointBytes` capability is true.

    asAddress : Optional[bool]
        If `true`, the `name` is a memory address and the debugger should
        interpret it as a decimal value, or hex value if it is prefixed with
        `0x`. Clients may set this property only if the
        `supportsDataBreakpointBytes` capability is true.

    mode : Optional[str]
        The mode of the desired breakpoint. If defined, this must be one of the
        `breakpointModes` the debug adapter advertised in its `Capabilities`.

    """

    # _spec.json#2004

    name: str
    asAddress: bool | None = None
    bytes: int | None = None
    frameId: int | None = None
    mode: str | None = None
    variablesReference: int | None = None


@dataclass
class DataBreakpointInfoResponseBody(OperationResponseBody):
    """('Response body for DataBreakpointInfoResponse.',)."""

    # _spec.json#2037

    dataId: str | None
    description: str
    accessTypes: list["DataBreakpointAccessType"] | None = None
    canPersist: bool | None = None


@dataclass
class DisassembleArguments(DAPDataclass):
    """Arguments for `disassemble` request.

    Attributes
    ----------
    memoryReference : str
        Memory reference to the base location containing the instructions to
        disassemble.

    offset : Optional[int]
        Offset (in bytes) to be applied to the reference location before
        disassembling. Can be negative.

    instructionOffset : Optional[int]
        Offset (in instructions) to be applied after the byte offset (if any)
        before disassembling. Can be negative.

    instructionCount : int
        Number of instructions to disassemble starting at the specified location
        and offset. An adapter must return exactly this number of instructions -
        any unavailable instructions should be replaced with an
        implementation-defined 'invalid instruction' value.

    resolveSymbols : Optional[bool]
        If true, the adapter should attempt to resolve memory addresses and
        other values to symbolic names.

    """

    # _spec.json#4146

    instructionCount: int
    memoryReference: str
    instructionOffset: int | None = None
    offset: int | None = None
    resolveSymbols: bool | None = None


@dataclass
class DisassembleResponseBody(OperationResponseBody):
    """('Response body for DisassembleResponse.',)."""

    # _spec.json#4176

    instructions: list["DisassembledInstruction"]


@dataclass
class DisconnectArguments(DAPDataclass):
    """Arguments for `disconnect` request.

    Attributes
    ----------
    restart : Optional[bool]
        A value of true indicates that this `disconnect` request is part of a
        restart sequence.

    terminateDebuggee : Optional[bool]
        Indicates whether the debuggee should be terminated when the debugger is
        disconnected. If unspecified, the debug adapter is free to do whatever
        it thinks is best. The attribute is only honored by a debug adapter if
        the corresponding capability `supportTerminateDebuggee` is true.

    suspendDebuggee : Optional[bool]
        Indicates whether the debuggee should stay suspended when the debugger
        is disconnected. If unspecified, the debuggee should resume execution.
        The attribute is only honored by a debug adapter if the corresponding
        capability `supportSuspendDebuggee` is true.

    """

    # _spec.json#1575

    restart: bool | None = None
    suspendDebuggee: bool | None = None
    terminateDebuggee: bool | None = None


@dataclass
class ErrorResponseBody(OperationResponseBody):
    """('Response body for ErrorResponse.',)."""

    # _spec.json#170

    error: Optional["Message"] = None


@dataclass
class EvaluateArguments(DAPDataclass):
    """Arguments for `evaluate` request.

    Attributes
    ----------
    expression : str
        The expression to evaluate.

    frameId : Optional[int]
        Evaluate the expression in the scope of this stack frame. If not
        specified, the expression is evaluated in the global scope.

    line : Optional[int]
        The contextual line where the expression should be evaluated. In the
        'hover' context, this should be set to the start of the expression being
        hovered.

    column : Optional[int]
        The contextual column where the expression should be evaluated. This may
        be provided if `line` is also provided. It is measured in UTF-16 code
        units and the client capability `columnsStartAt1` determines whether it
        is 0- or 1-based.

    source : Optional[Source]
        The contextual source in which the `line` is found. This must be
        provided if `line` is provided.

    context : Optional[str]
        The context in which the evaluate request is used.

    format : Optional[ValueFormat]
        Specifies details on how to format the result. The attribute is only
        honored by a debug adapter if the corresponding capability
        `supportsValueFormattingOptions` is true.

    """

    # _spec.json#3433

    expression: str
    column: int | None = None
    context: str | None = None
    format: Optional["ValueFormat"] = None
    frameId: int | None = None
    line: int | None = None
    source: Optional["Source"] = None


@dataclass
class EvaluateResponseBody(OperationResponseBody):
    """('Response body for EvaluateResponse.',)."""

    # _spec.json#3484

    result: str
    variablesReference: int
    indexedVariables: int | None = None
    memoryReference: str | None = None
    namedVariables: int | None = None
    presentationHint: Optional["VariablePresentationHint"] = None
    type: str | None = None
    valueLocationReference: int | None = None


@dataclass
class ExceptionInfoArguments(DAPDataclass):
    """Arguments for `exceptionInfo` request.

    Attributes
    ----------
    threadId : int
        Thread for which exception information should be retrieved.

    """

    # _spec.json#3907

    threadId: int


@dataclass
class ExceptionInfoResponseBody(OperationResponseBody):
    """('Response body for ExceptionInfoResponse.',)."""

    # _spec.json#3920

    breakMode: "ExceptionBreakMode"
    exceptionId: str
    description: str | None = None
    details: Optional["ExceptionDetails"] = None


@dataclass
class ExitedEventBody(OperationEventBody):
    """('Event body for ExitedEvent.',)."""

    # _spec.json#380

    exitCode: int


@dataclass
class GotoArguments(DAPDataclass):
    """Arguments for `goto` request.

    Attributes
    ----------
    threadId : int
        Set the goto target for this thread.

    targetId : int
        The location where the debuggee will continue to run.

    """

    # _spec.json#2664

    targetId: int
    threadId: int


@dataclass
class GotoTargetsArguments(DAPDataclass):
    """Arguments for `gotoTargets` request.

    Attributes
    ----------
    source : Source
        The source location for which the goto targets are determined.

    line : int
        The line location for which the goto targets are determined.

    column : Optional[int]
        The position within `line` for which the goto targets are determined. It
        is measured in UTF-16 code units and the client capability
        `columnsStartAt1` determines whether it is 0- or 1-based.

    """

    # _spec.json#3745

    line: int
    source: "Source"
    column: int | None = None


@dataclass
class GotoTargetsResponseBody(OperationResponseBody):
    """('Response body for GotoTargetsResponse.',)."""

    # _spec.json#3767

    targets: list["GotoTarget"]


@dataclass
class InitializeRequestArguments(DAPDataclass):
    """Arguments for `initialize` request.

    Attributes
    ----------
    clientID : Optional[str]
        The ID of the client using this adapter.

    clientName : Optional[str]
        The human-readable name of the client using this adapter.

    adapterID : str
        The ID of the debug adapter.

    locale : Optional[str]
        The ISO-639 locale of the client using this adapter, e.g. en-US or
        de-CH.

    linesStartAt1 : Optional[bool]
        If true all line numbers are 1-based (default).

    columnsStartAt1 : Optional[bool]
        If true all column numbers are 1-based (default).

    pathFormat : Optional[str]
        Determines in what format paths are specified. The default is `path`,
        which is the native format.

    supportsVariableType : Optional[bool]
        Client supports the `type` attribute for variables.

    supportsVariablePaging : Optional[bool]
        Client supports the paging of variables.

    supportsRunInTerminalRequest : Optional[bool]
        Client supports the `runInTerminal` request.

    supportsMemoryReferences : Optional[bool]
        Client supports memory references.

    supportsProgressReporting : Optional[bool]
        Client supports progress reporting.

    supportsInvalidatedEvent : Optional[bool]
        Client supports the `invalidated` event.

    supportsMemoryEvent : Optional[bool]
        Client supports the `memory` event.

    supportsArgsCanBeInterpretedByShell : Optional[bool]
        Client supports the `argsCanBeInterpretedByShell` attribute on the
        `runInTerminal` request.

    supportsStartDebuggingRequest : Optional[bool]
        Client supports the `startDebugging` request.

    supportsANSIStyling : Optional[bool]
        The client will interpret ANSI escape sequences in the display of
        `OutputEvent.output` and `Variable.value` fields when
        `Capabilities.supportsANSIStyling` is also enabled.

    """

    # _spec.json#1245

    adapterID: str
    clientID: str | None = None
    clientName: str | None = None
    columnsStartAt1: bool | None = None
    linesStartAt1: bool | None = None
    locale: str | None = None
    pathFormat: str | None = None
    supportsANSIStyling: bool | None = None
    supportsArgsCanBeInterpretedByShell: bool | None = None
    supportsInvalidatedEvent: bool | None = None
    supportsMemoryEvent: bool | None = None
    supportsMemoryReferences: bool | None = None
    supportsProgressReporting: bool | None = None
    supportsRunInTerminalRequest: bool | None = None
    supportsStartDebuggingRequest: bool | None = None
    supportsVariablePaging: bool | None = None
    supportsVariableType: bool | None = None


@dataclass
class InvalidatedEventBody(OperationEventBody):
    """('Event body for InvalidatedEvent.',)."""

    # _spec.json#966

    areas: list["InvalidatedAreas"] | None = None
    stackFrameId: int | None = None
    threadId: int | None = None


@dataclass
class LaunchRequestArguments(DAPDataclass):
    """Arguments for `launch` request. Additional attributes are implementation
    specific.

    Attributes
    ----------
    noDebug : Optional[bool]
        If true, the launch request should launch the program without enabling
        debugging.

    __restart : Optional[Union[List[Any], bool, int, float, Dict[str, Any],
    str]]
        Arbitrary data from the previous, restarted session. The data is sent as
        the `restart` attribute of the `terminated` event. The client should
        leave the data intact.

    """

    # _spec.json#1409

    __restart: list[Any] | bool | int | float | dict[str, Any] | str | None = None
    noDebug: bool | None = None


@dataclass
class LoadedSourceEventBody(OperationEventBody):
    """('Event body for LoadedSourceEvent.',)."""

    # _spec.json#687

    reason: str
    source: "Source"


@dataclass
class LoadedSourcesArguments(DAPDataclass):
    """Arguments for `loadedSources` request."""

    # _spec.json#3372



@dataclass
class LoadedSourcesResponseBody(OperationResponseBody):
    """('Response body for LoadedSourcesResponse.',)."""

    # _spec.json#3376

    sources: list["Source"]


@dataclass
class LocationsArguments(DAPDataclass):
    """Arguments for `locations` request.

    Attributes
    ----------
    locationReference : int
        Location reference to resolve.

    """

    # _spec.json#4230

    locationReference: int


@dataclass
class LocationsResponseBody(OperationResponseBody):
    """('Response body for LocationsResponse.',)."""

    # _spec.json#4243

    line: int
    source: "Source"
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None


@dataclass
class MemoryEventBody(OperationEventBody):
    """('Event body for MemoryEvent.',)."""

    # _spec.json#1009

    count: int
    memoryReference: str
    offset: int


@dataclass
class ModuleEventBody(OperationEventBody):
    """('Event body for ModuleEvent.',)."""

    # _spec.json#642

    module: "Module"
    reason: str


@dataclass
class ModulesArguments(DAPDataclass):
    """Arguments for `modules` request.

    Attributes
    ----------
    startModule : Optional[int]
        The index of the first module to return; if omitted modules start at 0.

    moduleCount : Optional[int]
        The number of modules to return. If `moduleCount` is not specified or 0,
        all modules are returned.

    """

    # _spec.json#3298

    moduleCount: int | None = None
    startModule: int | None = None


@dataclass
class ModulesResponseBody(OperationResponseBody):
    """('Response body for ModulesResponse.',)."""

    # _spec.json#3312

    modules: list["Module"]
    totalModules: int | None = None


@dataclass
class NextArguments(DAPDataclass):
    """Arguments for `next` request.

    Attributes
    ----------
    threadId : int
        Specifies the thread for which to resume execution for one step (of the
        given granularity).

    singleThread : Optional[bool]
        If this flag is true, all other suspended threads are not resumed.

    granularity : Optional[SteppingGranularity]
        Stepping granularity. If no granularity is specified, a granularity of
        `statement` is assumed.

    """

    # _spec.json#2324

    threadId: int
    granularity: Optional["SteppingGranularity"] = None
    singleThread: bool | None = None


@dataclass
class OutputEventBody(OperationEventBody):
    """('Event body for OutputEvent.',)."""

    # _spec.json#498

    output: str
    category: str | None = None
    column: int | None = None
    data: list[Any] | bool | int | float | dict[str, Any] | str | None = None
    group: str | None = None
    line: int | None = None
    locationReference: int | None = None
    source: Optional["Source"] = None
    variablesReference: int | None = None


@dataclass
class PauseArguments(DAPDataclass):
    """Arguments for `pause` request.

    Attributes
    ----------
    threadId : int
        Pause execution for this thread.

    """

    # _spec.json#2719

    threadId: int


@dataclass
class ProcessEventBody(OperationEventBody):
    """('Event body for ProcessEvent.',)."""

    # _spec.json#732

    name: str
    isLocalProcess: bool | None = None
    pointerSize: int | None = None
    startMethod: str | None = None
    systemProcessId: int | None = None


@dataclass
class ProgressEndEventBody(OperationEventBody):
    """('Event body for ProgressEndEvent.',)."""

    # _spec.json#927

    progressId: str
    message: str | None = None


@dataclass
class ProgressStartEventBody(OperationEventBody):
    """('Event body for ProgressStartEvent.',)."""

    # _spec.json#828

    progressId: str
    title: str
    cancellable: bool | None = None
    message: str | None = None
    percentage: float | None = None
    requestId: int | None = None


@dataclass
class ProgressUpdateEventBody(OperationEventBody):
    """('Event body for ProgressUpdateEvent.',)."""

    # _spec.json#884

    progressId: str
    message: str | None = None
    percentage: float | None = None


@dataclass
class ReadMemoryArguments(DAPDataclass):
    """Arguments for `readMemory` request.

    Attributes
    ----------
    memoryReference : str
        Memory reference to the base location from which data should be read.

    offset : Optional[int]
        Offset (in bytes) to be applied to the reference location before reading
        data. Can be negative.

    count : int
        Number of bytes to read at the specified location and offset.

    """

    # _spec.json#3987

    count: int
    memoryReference: str
    offset: int | None = None


@dataclass
class ReadMemoryResponseBody(OperationResponseBody):
    """('Response body for ReadMemoryResponse.',)."""

    # _spec.json#4009

    address: str
    data: str | None = None
    unreadableBytes: int | None = None


@dataclass
class RestartArguments(DAPDataclass):
    """Arguments for `restart` request.

    Attributes
    ----------
    arguments : Optional[Dict[str, Any]]
        The latest version of the `launch` or `attach` configuration.

    """

    # _spec.json#1522

    arguments: dict[str, Any] | None = None


@dataclass
class RestartFrameArguments(DAPDataclass):
    """Arguments for `restartFrame` request.

    Attributes
    ----------
    frameId : int
        Restart the stack frame identified by `frameId`. The `frameId` must have
        been obtained in the current suspended state. See 'Lifetime of Object
        References' in the Overview section for details.

    """

    # _spec.json#2614

    frameId: int


@dataclass
class ReverseContinueArguments(DAPDataclass):
    """Arguments for `reverseContinue` request.

    Attributes
    ----------
    threadId : int
        Specifies the active thread. If the debug adapter supports single thread
        execution (see `supportsSingleThreadExecutionRequests`) and the
        `singleThread` argument is true, only the thread with this ID is
        resumed.

    singleThread : Optional[bool]
        If this flag is true, backward execution is resumed only for the thread
        with given `threadId`.

    """

    # _spec.json#2560

    threadId: int
    singleThread: bool | None = None


@dataclass
class RunInTerminalRequestArguments(DAPDataclass):
    """Arguments for `runInTerminal` request.

    Attributes
    ----------
    kind : Optional[str]
        What kind of terminal to launch. Defaults to `integrated` if not
        specified.

    title : Optional[str]
        Title of the terminal.

    cwd : str
        Working directory for the command. For non-empty, valid paths this
        typically results in execution of a change directory command.

    args : List[str]
        List of arguments. The first argument is the command to run.

    env : Optional[Dict[str, Any]]
        Environment key-value pairs that are added to or removed from the
        default environment.

    argsCanBeInterpretedByShell : Optional[bool]
        This property should only be set if the corresponding capability
        `supportsArgsCanBeInterpretedByShell` is true. If the client uses an
        intermediary shell to launch the application, then the client must not
        attempt to escape characters with special meanings for the shell. The
        user is fully responsible for escaping as needed and that arguments
        using special characters may not be portable across shells.

    """

    # _spec.json#1081

    args: list[str]
    cwd: str
    argsCanBeInterpretedByShell: bool | None = None
    env: dict[str, Any] | None = None
    kind: str | None = None
    title: str | None = None


@dataclass
class RunInTerminalResponseBody(OperationResponseBody):
    """('Response body for RunInTerminalResponse.',)."""

    # _spec.json#1129

    processId: int | None = None
    shellProcessId: int | None = None


@dataclass
class ScopesArguments(DAPDataclass):
    """Arguments for `scopes` request.

    Attributes
    ----------
    frameId : int
        Retrieve the scopes for the stack frame identified by `frameId`. The
        `frameId` must have been obtained in the current suspended state. See
        'Lifetime of Object References' in the Overview section for details.

    """

    # _spec.json#2855

    frameId: int


@dataclass
class ScopesResponseBody(OperationResponseBody):
    """('Response body for ScopesResponse.',)."""

    # _spec.json#2868

    scopes: list["Scope"]


@dataclass
class SetBreakpointsArguments(DAPDataclass):
    """Arguments for `setBreakpoints` request.

    Attributes
    ----------
    source : Source
        The source location of the breakpoints; either `source.path` or
        `source.sourceReference` must be specified.

    breakpoints : Optional[List[SourceBreakpoint]]
        The code locations of the breakpoints.

    lines : Optional[List[int]]
        Deprecated: The code locations of the breakpoints.

    sourceModified : Optional[bool]
        A value of true indicates that the underlying source has been modified
        which results in new breakpoint locations.

    """

    # _spec.json#1762

    source: "Source"
    breakpoints: list["SourceBreakpoint"] | None = None
    lines: list[int] | None = None
    sourceModified: bool | None = None


@dataclass
class SetBreakpointsResponseBody(OperationResponseBody):
    """('Response body for SetBreakpointsResponse.',)."""

    # _spec.json#1793

    breakpoints: list["Breakpoint"]


@dataclass
class SetDataBreakpointsArguments(DAPDataclass):
    """Arguments for `setDataBreakpoints` request.

    Attributes
    ----------
    breakpoints : List[DataBreakpoint]
        The contents of this array replaces all existing data breakpoints. An
        empty array clears all data breakpoints.

    """

    # _spec.json#2110

    breakpoints: list["DataBreakpoint"]


@dataclass
class SetDataBreakpointsResponseBody(OperationResponseBody):
    """('Response body for SetDataBreakpointsResponse.',)."""

    # _spec.json#2126

    breakpoints: list["Breakpoint"]


@dataclass
class SetExceptionBreakpointsArguments(DAPDataclass):
    """Arguments for `setExceptionBreakpoints` request.

    Attributes
    ----------
    filters : List[str]
        Set of exception filters specified by their ID. The set of all possible
        exception filters is defined by the `exceptionBreakpointFilters`
        capability. The `filter` and `filterOptions` sets are additive.

    filterOptions : Optional[List[ExceptionFilterOptions]]
        Set of exception filters and their options. The set of all possible
        exception filters is defined by the `exceptionBreakpointFilters`
        capability. This attribute is only honored by a debug adapter if the
        corresponding capability `supportsExceptionFilterOptions` is true. The
        `filter` and `filterOptions` sets are additive.

    exceptionOptions : Optional[List[ExceptionOptions]]
        Configuration options for selected exceptions. The attribute is only
        honored by a debug adapter if the corresponding capability
        `supportsExceptionOptions` is true.

    """

    # _spec.json#1923

    filters: list[str]
    exceptionOptions: list["ExceptionOptions"] | None = None
    filterOptions: list["ExceptionFilterOptions"] | None = None


@dataclass
class SetExceptionBreakpointsResponseBody(OperationResponseBody):
    """('Response body for SetExceptionBreakpointsResponse.',)."""

    # _spec.json#1953

    breakpoints: list["Breakpoint"] | None = None


@dataclass
class SetExpressionArguments(DAPDataclass):
    """Arguments for `setExpression` request.

    Attributes
    ----------
    expression : str
        The l-value expression to assign to.

    value : str
        The value expression to assign to the l-value expression.

    frameId : Optional[int]
        Evaluate the expressions in the scope of this stack frame. If not
        specified, the expressions are evaluated in the global scope.

    format : Optional[ValueFormat]
        Specifies how the resulting value should be formatted.

    """

    # _spec.json#3567

    expression: str
    value: str
    format: Optional["ValueFormat"] = None
    frameId: int | None = None


@dataclass
class SetExpressionResponseBody(OperationResponseBody):
    """('Response body for SetExpressionResponse.',)."""

    # _spec.json#3593

    value: str
    indexedVariables: int | None = None
    memoryReference: str | None = None
    namedVariables: int | None = None
    presentationHint: Optional["VariablePresentationHint"] = None
    type: str | None = None
    valueLocationReference: int | None = None
    variablesReference: int | None = None


@dataclass
class SetFunctionBreakpointsArguments(DAPDataclass):
    """Arguments for `setFunctionBreakpoints` request.

    Attributes
    ----------
    breakpoints : List[FunctionBreakpoint]
        The function names of the breakpoints.

    """

    # _spec.json#1850

    breakpoints: list["FunctionBreakpoint"]


@dataclass
class SetFunctionBreakpointsResponseBody(OperationResponseBody):
    """('Response body for SetFunctionBreakpointsResponse.',)."""

    # _spec.json#1866

    breakpoints: list["Breakpoint"]


@dataclass
class SetInstructionBreakpointsArguments(DAPDataclass):
    """Arguments for `setInstructionBreakpoints` request.

    Attributes
    ----------
    breakpoints : List[InstructionBreakpoint]
        The instruction references of the breakpoints

    """

    # _spec.json#2183

    breakpoints: list["InstructionBreakpoint"]


@dataclass
class SetInstructionBreakpointsResponseBody(OperationResponseBody):
    """('Response body for SetInstructionBreakpointsResponse.',)."""

    # _spec.json#2199

    breakpoints: list["Breakpoint"]


@dataclass
class SetVariableArguments(DAPDataclass):
    """Arguments for `setVariable` request.

    Attributes
    ----------
    variablesReference : int
        The reference of the variable container. The `variablesReference` must
        have been obtained in the current suspended state. See 'Lifetime of
        Object References' in the Overview section for details.

    name : str
        The name of the variable in the container.

    value : str
        The value of the variable.

    format : Optional[ValueFormat]
        Specifies details on how to format the response value.

    """

    # _spec.json#3015

    name: str
    value: str
    variablesReference: int
    format: Optional["ValueFormat"] = None


@dataclass
class SetVariableResponseBody(OperationResponseBody):
    """('Response body for SetVariableResponse.',)."""

    # _spec.json#3042

    value: str
    indexedVariables: int | None = None
    memoryReference: str | None = None
    namedVariables: int | None = None
    type: str | None = None
    valueLocationReference: int | None = None
    variablesReference: int | None = None


@dataclass
class SourceArguments(DAPDataclass):
    """Arguments for `source` request.

    Attributes
    ----------
    source : Optional[Source]
        Specifies the source content to load. Either `source.path` or
        `source.sourceReference` must be specified.

    sourceReference : int
        The reference to the source. This is the same as
        `source.sourceReference`. This is provided for backward compatibility
        since old clients do not understand the `source` attribute.

    """

    # _spec.json#3120

    sourceReference: int
    source: Optional["Source"] = None


@dataclass
class SourceResponseBody(OperationResponseBody):
    """('Response body for SourceResponse.',)."""

    # _spec.json#3137

    content: str
    mimeType: str | None = None


@dataclass
class StackTraceArguments(DAPDataclass):
    """Arguments for `stackTrace` request.

    Attributes
    ----------
    threadId : int
        Retrieve the stacktrace for this thread.

    startFrame : Optional[int]
        The index of the first frame to return; if omitted frames start at 0.

    levels : Optional[int]
        The maximum number of frames to return. If levels is not specified or 0,
        all frames are returned.

    format : Optional[StackFrameFormat]
        Specifies details on how to format the returned `StackFrame.name`. The
        debug adapter may format requested details in any way that would make
        sense to a developer. The attribute is only honored by a debug adapter
        if the corresponding capability `supportsValueFormattingOptions` is
        true.

    """

    # _spec.json#2769

    threadId: int
    format: Optional["StackFrameFormat"] = None
    levels: int | None = None
    startFrame: int | None = None


@dataclass
class StackTraceResponseBody(OperationResponseBody):
    """('Response body for StackTraceResponse.',)."""

    # _spec.json#2794

    stackFrames: list["StackFrame"]
    totalFrames: int | None = None


@dataclass
class StartDebuggingRequestArguments(DAPDataclass):
    """Arguments for `startDebugging` request.

    Attributes
    ----------
    configuration : Dict[str, Any]
        Arguments passed to the new debug session. The arguments must only
        contain properties understood by the `launch` or `attach` requests of
        the debug adapter and they must not contain any client-specific
        properties (e.g. `type`) or client-specific features (e.g. substitutable
        'variables').

    request : str
        Indicates whether the new debug session should be started with a
        `launch` or `attach` request.

    """

    # _spec.json#1184

    configuration: dict[str, Any]
    request: str


@dataclass
class StepBackArguments(DAPDataclass):
    """Arguments for `stepBack` request.

    Attributes
    ----------
    threadId : int
        Specifies the thread for which to resume execution for one step
        backwards (of the given granularity).

    singleThread : Optional[bool]
        If this flag is true, all other suspended threads are not resumed.

    granularity : Optional[SteppingGranularity]
        Stepping granularity to step. If no granularity is specified, a
        granularity of `statement` is assumed.

    """

    # _spec.json#2502

    threadId: int
    granularity: Optional["SteppingGranularity"] = None
    singleThread: bool | None = None


@dataclass
class StepInArguments(DAPDataclass):
    """Arguments for `stepIn` request.

    Attributes
    ----------
    threadId : int
        Specifies the thread for which to resume execution for one step-into (of
        the given granularity).

    singleThread : Optional[bool]
        If this flag is true, all other suspended threads are not resumed.

    targetId : Optional[int]
        Id of the target to step into.

    granularity : Optional[SteppingGranularity]
        Stepping granularity. If no granularity is specified, a granularity of
        `statement` is assumed.

    """

    # _spec.json#2382

    threadId: int
    granularity: Optional["SteppingGranularity"] = None
    singleThread: bool | None = None
    targetId: int | None = None


@dataclass
class StepInTargetsArguments(DAPDataclass):
    """Arguments for `stepInTargets` request.

    Attributes
    ----------
    frameId : int
        The stack frame for which to retrieve the possible step-in targets.

    """

    # _spec.json#3675

    frameId: int


@dataclass
class StepInTargetsResponseBody(OperationResponseBody):
    """('Response body for StepInTargetsResponse.',)."""

    # _spec.json#3688

    targets: list["StepInTarget"]


@dataclass
class StepOutArguments(DAPDataclass):
    """Arguments for `stepOut` request.

    Attributes
    ----------
    threadId : int
        Specifies the thread for which to resume execution for one step-out (of
        the given granularity).

    singleThread : Optional[bool]
        If this flag is true, all other suspended threads are not resumed.

    granularity : Optional[SteppingGranularity]
        Stepping granularity. If no granularity is specified, a granularity of
        `statement` is assumed.

    """

    # _spec.json#2444

    threadId: int
    granularity: Optional["SteppingGranularity"] = None
    singleThread: bool | None = None


@dataclass
class StoppedEventBody(OperationEventBody):
    """('Event body for StoppedEvent.',)."""

    # _spec.json#268

    reason: str
    allThreadsStopped: bool | None = None
    description: str | None = None
    hitBreakpointIds: list[int] | None = None
    preserveFocusHint: bool | None = None
    text: str | None = None
    threadId: int | None = None


@dataclass
class TerminateArguments(DAPDataclass):
    """Arguments for `terminate` request.

    Attributes
    ----------
    restart : Optional[bool]
        A value of true indicates that this `terminate` request is part of a
        restart sequence.

    """

    # _spec.json#1629

    restart: bool | None = None


@dataclass
class TerminateThreadsArguments(DAPDataclass):
    """Arguments for `terminateThreads` request.

    Attributes
    ----------
    threadIds : Optional[List[int]]
        Ids of threads to be terminated.

    """

    # _spec.json#3248

    threadIds: list[int] | None = None


@dataclass
class TerminatedEventBody(OperationEventBody):
    """('Event body for TerminatedEvent.',)."""

    # _spec.json#415

    restart: list[Any] | bool | int | float | dict[str, Any] | str | None = None


@dataclass
class ThreadEventBody(OperationEventBody):
    """('Event body for ThreadEvent.',)."""

    # _spec.json#454

    reason: str
    threadId: int


@dataclass
class ThreadsResponseBody(OperationResponseBody):
    """('Response body for ThreadsResponse.',)."""

    # _spec.json#3191

    threads: list["Thread"]


@dataclass
class VariablesArguments(DAPDataclass):
    """Arguments for `variables` request.

    Attributes
    ----------
    variablesReference : int
        The variable for which to retrieve its children. The
        `variablesReference` must have been obtained in the current suspended
        state. See 'Lifetime of Object References' in the Overview section for
        details.

    filter : Optional[str]
        Filter to limit the child variables to either named or indexed. If
        omitted, both types are fetched.

    start : Optional[int]
        The index of the first variable to return; if omitted children start at
        0. The attribute is only honored by a debug adapter if the corresponding
        capability `supportsVariablePaging` is true.

    count : Optional[int]
        The number of variables to return. If count is missing or 0, all
        variables are returned. The attribute is only honored by a debug adapter
        if the corresponding capability `supportsVariablePaging` is true.

    format : Optional[ValueFormat]
        Specifies details on how to format the Variable values. The attribute is
        only honored by a debug adapter if the corresponding capability
        `supportsValueFormattingOptions` is true.

    """

    # _spec.json#2925

    variablesReference: int
    count: int | None = None
    filter: str | None = None
    format: Optional["ValueFormat"] = None
    start: int | None = None


@dataclass
class VariablesResponseBody(OperationResponseBody):
    """('Response body for VariablesResponse.',)."""

    # _spec.json#2958

    variables: list["Variable"]


@dataclass
class WriteMemoryArguments(DAPDataclass):
    """Arguments for `writeMemory` request.

    Attributes
    ----------
    memoryReference : str
        Memory reference to the base location to which data should be written.

    offset : Optional[int]
        Offset (in bytes) to be applied to the reference location before writing
        data. Can be negative.

    allowPartial : Optional[bool]
        Property to control partial writes. If true, the debug adapter should
        attempt to write memory even if the entire memory region is not
        writable. In such a case the debug adapter should stop after hitting the
        first byte of memory that cannot be written and return the number of
        bytes written in the response via the `offset` and `bytesWritten`
        properties. If false or missing, a debug adapter should attempt to
        verify the region is writable before writing, and fail the response if
        it is not.

    data : str
        Bytes to write, encoded using base64.

    """

    # _spec.json#4068

    data: str
    memoryReference: str
    allowPartial: bool | None = None
    offset: int | None = None


@dataclass
class WriteMemoryResponseBody(OperationResponseBody):
    """('Response body for WriteMemoryResponse.',)."""

    # _spec.json#4094

    bytesWritten: int | None = None
    offset: int | None = None
