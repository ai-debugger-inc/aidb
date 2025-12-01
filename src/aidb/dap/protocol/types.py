"""DAP Protocol - DAP data type classes and enums.

Auto-generated from Debug Adapter Protocol specification. Do not edit
manually."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .base import DAPDataclass, OperationResponseBody


@dataclass
class Breakpoint(DAPDataclass):
    """Information about a breakpoint created in `setBreakpoints`,
    `setFunctionBreakpoints`, `setInstructionBreakpoints`, or
    `setDataBreakpoints` requests."""

    # _spec.json#5121

    verified: bool
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None
    id: int | None = None
    instructionReference: str | None = None
    line: int | None = None
    message: str | None = None
    offset: int | None = None
    reason: str | None = None
    source: Optional["Source"] = None


@dataclass
class BreakpointLocation(DAPDataclass):
    """Properties of a breakpoint location returned from the
    `breakpointLocations` request."""

    # _spec.json#4979

    line: int
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None


@dataclass
class BreakpointMode(DAPDataclass):
    """A `BreakpointMode` is provided as a option when setting breakpoints on
    sources or instructions."""

    # _spec.json#5588

    appliesTo: list["BreakpointModeApplicability"]
    label: str
    mode: str
    description: str | None = None


@dataclass
class BreakpointModeApplicability(DAPDataclass):
    """Describes one or more type of breakpoint a `BreakpointMode` applies to.

    This is a non-exhaustive enumeration and may expand as future breakpoint
    types are added.
    """

    # _spec.json#5618



@dataclass
class Capabilities(OperationResponseBody):
    """Information about the capabilities of a debug adapter."""

    # _spec.json#4285

    additionalModuleColumns: list["ColumnDescriptor"] | None = None
    breakpointModes: list["BreakpointMode"] | None = None
    completionTriggerCharacters: list[str] | None = None
    exceptionBreakpointFilters: list["ExceptionBreakpointsFilter"] | None = None
    supportSuspendDebuggee: bool | None = None
    supportTerminateDebuggee: bool | None = None
    supportedChecksumAlgorithms: list["ChecksumAlgorithm"] | None = None
    supportsANSIStyling: bool | None = None
    supportsBreakpointLocationsRequest: bool | None = None
    supportsCancelRequest: bool | None = None
    supportsClipboardContext: bool | None = None
    supportsCompletionsRequest: bool | None = None
    supportsConditionalBreakpoints: bool | None = None
    supportsConfigurationDoneRequest: bool | None = None
    supportsDataBreakpointBytes: bool | None = None
    supportsDataBreakpoints: bool | None = None
    supportsDebuggerProperties: bool | None = None
    supportsDelayedStackTraceLoading: bool | None = None
    supportsDisassembleRequest: bool | None = None
    supportsEvaluateForHovers: bool | None = None
    supportsExceptionFilterOptions: bool | None = None
    supportsExceptionInfoRequest: bool | None = None
    supportsExceptionOptions: bool | None = None
    supportsFunctionBreakpoints: bool | None = None
    supportsGotoTargetsRequest: bool | None = None
    supportsHitConditionalBreakpoints: bool | None = None
    supportsInstructionBreakpoints: bool | None = None
    supportsLoadedSourcesRequest: bool | None = None
    supportsLogPoints: bool | None = None
    supportsModulesRequest: bool | None = None
    supportsReadMemoryRequest: bool | None = None
    supportsRestartFrame: bool | None = None
    supportsRestartRequest: bool | None = None
    supportsSetExpression: bool | None = None
    supportsSetVariable: bool | None = None
    supportsSingleThreadExecutionRequests: bool | None = None
    supportsStepBack: bool | None = None
    supportsStepInTargetsRequest: bool | None = None
    supportsSteppingGranularity: bool | None = None
    supportsTerminateDebuggee: bool | None = None
    supportsTerminateRequest: bool | None = None
    supportsTerminateThreadsRequest: bool | None = None
    supportsValueFormattingOptions: bool | None = None
    supportsWriteMemoryRequest: bool | None = None


@dataclass
class Checksum(DAPDataclass):
    """The checksum of an item calculated by the specified algorithm."""

    # _spec.json#5345

    algorithm: "ChecksumAlgorithm"
    checksum: str


class ChecksumAlgorithm(str, Enum):
    """Names of checksum algorithms that may be supported by a debug adapter."""

    # _spec.json#5335

    M_D5 = "MD5"
    S_H_A1 = "SHA1"
    S_H_A256 = "SHA256"
    TIMESTAMP = "timestamp"


@dataclass
class ColumnDescriptor(DAPDataclass):
    """A `ColumnDescriptor` specifies what module attribute to show in a column
    of the modules view, how to format it, and what the column's label should
    be.

    It is only used if the underlying UI actually supports this level of
    customization.
    """

    # _spec.json#4604

    attributeName: str
    label: str
    format: str | None = None
    type: str | None = None
    width: int | None = None


@dataclass
class CompletionItem(DAPDataclass):
    """`CompletionItems` are the suggestions returned from the `completions`
    request."""

    # _spec.json#5265

    label: str
    detail: str | None = None
    length: int | None = None
    selectionLength: int | None = None
    selectionStart: int | None = None
    sortText: str | None = None
    start: int | None = None
    text: str | None = None
    type: Optional["CompletionItemType"] = None


class CompletionItemType(str, Enum):
    """Some predefined types for the CompletionItem.

    Please note that not all clients have specific icons for all of them.
    """

    # _spec.json#5310

    METHOD = "method"
    FUNCTION = "function"
    CONSTRUCTOR = "constructor"
    FIELD = "field"
    VARIABLE = "variable"
    CLASS = "class"
    INTERFACE = "interface"
    MODULE = "module"
    PROPERTY = "property"
    UNIT = "unit"
    VALUE = "value"
    ENUM = "enum"
    KEYWORD = "keyword"
    SNIPPET = "snippet"
    TEXT = "text"
    COLOR = "color"
    FILE = "file"
    REFERENCE = "reference"
    CUSTOMCOLOR = "customcolor"


@dataclass
class DataBreakpoint(DAPDataclass):
    """Properties of a data breakpoint passed to the `setDataBreakpoints`
    request."""

    # _spec.json#5067

    dataId: str
    accessType: Optional["DataBreakpointAccessType"] = None
    condition: str | None = None
    hitCondition: str | None = None


class DataBreakpointAccessType(str, Enum):
    """This enumeration defines all possible access types for data
    breakpoints."""

    # _spec.json#5058

    READ = "read"
    WRITE = "write"
    READ_WRITE = "readWrite"


@dataclass
class DisassembledInstruction(DAPDataclass):
    """Represents a single disassembled instruction."""

    # _spec.json#5518

    address: str
    instruction: str
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None
    instructionBytes: str | None = None
    line: int | None = None
    location: Optional["Source"] = None
    presentationHint: str | None = None
    symbol: str | None = None


class ExceptionBreakMode(str, Enum):
    """This enumeration defines all possible conditions when a thrown exception
    should result in a break.

    never: never breaks, always: always breaks, unhandled: breaks when exception
    unhandled, userUnhandled: breaks if the exception is not handled by user
    code.
    """

    # _spec.json#5455

    NEVER = "never"
    ALWAYS = "always"
    UNHANDLED = "unhandled"
    USER_UNHANDLED = "userUnhandled"


@dataclass
class ExceptionBreakpointsFilter(DAPDataclass):
    """An `ExceptionBreakpointsFilter` is shown in the UI as an filter option
    for configuring how exceptions are dealt with."""

    # _spec.json#4475

    filter: str
    label: str
    conditionDescription: str | None = None
    default: bool | None = None
    description: str | None = None
    supportsCondition: bool | None = None


@dataclass
class ExceptionDetails(DAPDataclass):
    """Detailed information about an exception that has occurred."""

    # _spec.json#5485

    evaluateName: str | None = None
    fullTypeName: str | None = None
    innerException: list["ExceptionDetails"] | None = None
    message: str | None = None
    stackTrace: str | None = None
    typeName: str | None = None


@dataclass
class ExceptionFilterOptions(DAPDataclass):
    """An `ExceptionFilterOptions` is used to specify an exception filter
    together with a condition for the `setExceptionBreakpoints` request."""

    # _spec.json#5414

    filterId: str
    condition: str | None = None
    mode: str | None = None


@dataclass
class ExceptionOptions(DAPDataclass):
    """An `ExceptionOptions` assigns configuration options to a set of
    exceptions."""

    # _spec.json#5435

    breakMode: "ExceptionBreakMode"
    path: list["ExceptionPathSegment"] | None = None


@dataclass
class ExceptionPathSegment(DAPDataclass):
    """An `ExceptionPathSegment` represents a segment in a path that is used to
    match leafs or nodes in a tree of exceptions.

    If a segment consists of more than one name, it matches the names provided
    if `negate` is false or missing, or it matches anything except the names
    provided if `negate` is true.
    """

    # _spec.json#5465

    names: list[str]
    negate: bool | None = None


@dataclass
class FunctionBreakpoint(DAPDataclass):
    """Properties of a breakpoint passed to the `setFunctionBreakpoints`
    request."""

    # _spec.json#5037

    name: str
    condition: str | None = None
    hitCondition: str | None = None


@dataclass
class GotoTarget(DAPDataclass):
    """A `GotoTarget` describes a code location that can be used as a target in
    the `goto` request.

    The possible goto targets can be determined via the `gotoTargets` request.
    """

    # _spec.json#5226

    id: int
    label: str
    line: int
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None
    instructionPointerReference: str | None = None


@dataclass
class InstructionBreakpoint(DAPDataclass):
    """Properties of a breakpoint passed to the `setInstructionBreakpoints`
    request."""

    # _spec.json#5092

    instructionReference: str
    condition: str | None = None
    hitCondition: str | None = None
    mode: str | None = None
    offset: int | None = None


@dataclass
class InvalidatedAreas(DAPDataclass):
    """Logical areas that can be invalidated by the `invalidated` event."""

    # _spec.json#5572



@dataclass
class Message(DAPDataclass):
    """A structured message object.

    Used to return errors from requests.
    """

    # _spec.json#4509

    format: str
    id: int
    sendTelemetry: bool | None = None
    showUser: bool | None = None
    url: str | None = None
    urlLabel: str | None = None
    variables: dict[str, Any] | None = None


@dataclass
class Module(DAPDataclass):
    """A Module object represents a row in the modules view.

    The `id` attribute identifies a module in the modules view and is used in a
    `module` event for identifying a module for adding, updating or deleting.
    The `name` attribute is used to minimally render the module in the UI.
    Additional attributes can be added to the module. They show up in the module
    view if they have a corresponding `ColumnDescriptor`. To avoid an
    unnecessary proliferation of additional attributes with similar semantics
    but different names, we recommend to re-use attributes from the
    'recommended' list below first, and only introduce new attributes if nothing
    appropriate could be found.
    """

    # _spec.json#4551

    id: int | str
    name: str
    addressRange: str | None = None
    dateTimeStamp: str | None = None
    isOptimized: bool | None = None
    isUserCode: bool | None = None
    path: str | None = None
    symbolFilePath: str | None = None
    symbolStatus: str | None = None
    version: str | None = None


@dataclass
class Scope(DAPDataclass):
    """A `Scope` is a named container for variables.

    Optionally a scope can map to a source or a range within a source.
    """

    # _spec.json#4779

    expensive: bool
    name: str
    variablesReference: int
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None
    indexedVariables: int | None = None
    line: int | None = None
    namedVariables: int | None = None
    presentationHint: str | None = None
    source: Optional["Source"] = None


@dataclass
class Source(DAPDataclass):
    """A `Source` is a descriptor for source code.

    It is returned from the debug adapter as part of a `StackFrame` and it is
    used by clients when specifying breakpoints.
    """

    # _spec.json#4658

    adapterData: list[Any] | bool | int | float | dict[str, Any] | str | None = (
        None
    )
    checksums: list["Checksum"] | None = None
    name: str | None = None
    origin: str | None = None
    path: str | None = None
    presentationHint: str | None = None
    sourceReference: int | None = None
    sources: list["Source"] | None = None


@dataclass
class SourceBreakpoint(DAPDataclass):
    """Properties of a breakpoint or logpoint passed to the `setBreakpoints`
    request."""

    # _spec.json#5004

    line: int
    column: int | None = None
    condition: str | None = None
    hitCondition: str | None = None
    logMessage: str | None = None
    mode: str | None = None


@dataclass
class StackFrame(DAPDataclass):
    """A Stackframe contains the source location."""

    # _spec.json#4715

    column: int
    id: int
    line: int
    name: str
    canRestart: bool | None = None
    endColumn: int | None = None
    endLine: int | None = None
    instructionPointerReference: str | None = None
    moduleId: int | str | None = None
    presentationHint: str | None = None
    source: Optional["Source"] = None


@dataclass
class StepInTarget(DAPDataclass):
    """A `StepInTarget` can be used in the `stepIn` request and determines into
    which single target the `stepIn` request should step."""

    # _spec.json#5192

    id: int
    label: str
    column: int | None = None
    endColumn: int | None = None
    endLine: int | None = None
    line: int | None = None


class SteppingGranularity(str, Enum):
    """The granularity of one 'step' in the stepping requests `next`, `stepIn`,
    `stepOut`, and `stepBack`."""

    # _spec.json#5178

    STATEMENT = "statement"
    LINE = "line"
    INSTRUCTION = "instruction"


@dataclass
class Thread(DAPDataclass):
    """A Thread."""

    # _spec.json#4640

    id: int
    name: str


@dataclass
class ValueFormat(DAPDataclass):
    """Provides formatting information for a value."""

    # _spec.json#5363

    hex: bool | None = None


@dataclass
class StackFrameFormat(ValueFormat):
    """Provides formatting information for a stack frame."""

    # _spec.json#5373

    includeAll: bool | None = None
    line: bool | None = None
    module: bool | None = None
    parameterNames: bool | None = None
    parameterTypes: bool | None = None
    parameterValues: bool | None = None
    parameters: bool | None = None


@dataclass
class Variable(DAPDataclass):
    """A Variable is a name/value pair.

    The `type` attribute is shown if space permits or when hovering over the
    variable's name. The `kind` attribute is used to render additional
    properties of the variable, e.g. different icons can be used to indicate
    that a variable is public or private. If the value is structured (has
    children), a handle is provided to retrieve the children with the
    `variables` request. If the number of named or indexed children is large,
    the numbers should be returned via the `namedVariables` and
    `indexedVariables` attributes. The client can use this information to
    present the children in a paged UI and fetch them in chunks.
    """

    # _spec.json#4846

    name: str
    value: str
    variablesReference: int
    declarationLocationReference: int | None = None
    evaluateName: str | None = None
    indexedVariables: int | None = None
    memoryReference: str | None = None
    namedVariables: int | None = None
    presentationHint: Optional["VariablePresentationHint"] = None
    type: str | None = None
    valueLocationReference: int | None = None


@dataclass
class VariablePresentationHint(DAPDataclass):
    """Properties of a variable that can be used to determine how to render the
    variable in the UI."""

    # _spec.json#4901

    attributes: list[str] | None = None
    kind: str | None = None
    lazy: bool | None = None
    visibility: str | None = None
