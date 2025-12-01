"""DAP Protocol - DAP response message classes.

Auto-generated from Debug Adapter Protocol specification. Do not edit
manually."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .base import Response
from .bodies import *  # noqa: F403

if TYPE_CHECKING:
    from .bodies import (
        BreakpointLocationsResponseBody,
        CompletionsResponseBody,
        ContinueResponseBody,
        DataBreakpointInfoResponseBody,
        DisassembleResponseBody,
        ErrorResponseBody,
        EvaluateResponseBody,
        ExceptionInfoResponseBody,
        GotoTargetsResponseBody,
        LoadedSourcesResponseBody,
        LocationsResponseBody,
        ModulesResponseBody,
        ReadMemoryResponseBody,
        RunInTerminalResponseBody,
        ScopesResponseBody,
        SetBreakpointsResponseBody,
        SetDataBreakpointsResponseBody,
        SetExceptionBreakpointsResponseBody,
        SetExpressionResponseBody,
        SetFunctionBreakpointsResponseBody,
        SetInstructionBreakpointsResponseBody,
        SetVariableResponseBody,
        SourceResponseBody,
        StackTraceResponseBody,
        StepInTargetsResponseBody,
        ThreadsResponseBody,
        VariablesResponseBody,
        WriteMemoryResponseBody,
    )
    from .types import Capabilities


@dataclass
class AttachResponse(Response):
    """Response to `attach` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1486



@dataclass
class BreakpointLocationsResponse(Response):
    """Response to `breakpointLocations` request.

    Contains possible locations for source breakpoints.
    """

    # _spec.json#1705

    body: Optional["BreakpointLocationsResponseBody"] = None


@dataclass
class CancelResponse(Response):
    """Response to `cancel` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#234



@dataclass
class CompletionsResponse(Response):
    """Response to `completions` request."""

    # _spec.json#3850

    body: Optional["CompletionsResponseBody"] = None


@dataclass
class ConfigurationDoneResponse(Response):
    """Response to `configurationDone` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1372



@dataclass
class ContinueResponse(Response):
    """Response to `continue` request."""

    # _spec.json#2273

    body: Optional["ContinueResponseBody"] = None


@dataclass
class DataBreakpointInfoResponse(Response):
    """Response to `dataBreakpointInfo` request."""

    # _spec.json#2037

    body: Optional["DataBreakpointInfoResponseBody"] = None


@dataclass
class DisassembleResponse(Response):
    """Response to `disassemble` request."""

    # _spec.json#4176

    body: Optional["DisassembleResponseBody"] = None


@dataclass
class DisconnectResponse(Response):
    """Response to `disconnect` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1593



@dataclass
class ErrorResponse(Response):
    """On error (whenever `success` is false), the body can provide more
    details."""

    # _spec.json#170

    body: Optional["ErrorResponseBody"] = None


@dataclass
class EvaluateResponse(Response):
    """Response to `evaluate` request."""

    # _spec.json#3484

    body: Optional["EvaluateResponseBody"] = None


@dataclass
class ExceptionInfoResponse(Response):
    """Response to `exceptionInfo` request."""

    # _spec.json#3920

    body: Optional["ExceptionInfoResponseBody"] = None


@dataclass
class GotoResponse(Response):
    """Response to `goto` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2682



@dataclass
class GotoTargetsResponse(Response):
    """Response to `gotoTargets` request."""

    # _spec.json#3767

    body: Optional["GotoTargetsResponseBody"] = None


@dataclass
class InitializeResponse(Response):
    """Response to `initialize` request."""

    # _spec.json#1326

    body: Optional["Capabilities"] = None


@dataclass
class LaunchResponse(Response):
    """Response to `launch` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1431



@dataclass
class LoadedSourcesResponse(Response):
    """Response to `loadedSources` request."""

    # _spec.json#3376

    body: Optional["LoadedSourcesResponseBody"] = None


@dataclass
class LocationsResponse(Response):
    """Response to `locations` request."""

    # _spec.json#4243

    body: Optional["LocationsResponseBody"] = None


@dataclass
class ModulesResponse(Response):
    """Response to `modules` request."""

    # _spec.json#3312

    body: Optional["ModulesResponseBody"] = None


@dataclass
class NextResponse(Response):
    """Response to `next` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2345



@dataclass
class PauseResponse(Response):
    """Response to `pause` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2732



@dataclass
class ReadMemoryResponse(Response):
    """Response to `readMemory` request."""

    # _spec.json#4009

    body: Optional["ReadMemoryResponseBody"] = None


@dataclass
class RestartFrameResponse(Response):
    """Response to `restartFrame` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2627



@dataclass
class RestartResponse(Response):
    """Response to `restart` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1539



@dataclass
class ReverseContinueResponse(Response):
    """Response to `reverseContinue` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2577



@dataclass
class RunInTerminalResponse(Response):
    """Response to `runInTerminal` request."""

    # _spec.json#1129

    body: Optional["RunInTerminalResponseBody"] = None


@dataclass
class ScopesResponse(Response):
    """Response to `scopes` request."""

    # _spec.json#2868

    body: Optional["ScopesResponseBody"] = None


@dataclass
class SetBreakpointsResponse(Response):
    """Response to `setBreakpoints` request.

    Returned is information about each breakpoint created by this request. This
    includes the actual code location and whether the breakpoint could be
    verified. The breakpoints returned are in the same order as the elements of
    the `breakpoints` (or the deprecated `lines`) array in the arguments.
    """

    # _spec.json#1793

    body: Optional["SetBreakpointsResponseBody"] = None


@dataclass
class SetDataBreakpointsResponse(Response):
    """Response to `setDataBreakpoints` request.

    Returned is information about each breakpoint created by this request.
    """

    # _spec.json#2126

    body: Optional["SetDataBreakpointsResponseBody"] = None


@dataclass
class SetExceptionBreakpointsResponse(Response):
    """Response to `setExceptionBreakpoints` request.

    The response contains an array of `Breakpoint` objects with information
    about each exception breakpoint or filter. The `Breakpoint` objects are in
    the same order as the elements of the `filters`, `filterOptions`,
    `exceptionOptions` arrays given as arguments. If both `filters` and
    `filterOptions` are given, the returned array must start with `filters`
    information first, followed by `filterOptions` information. The `verified`
    property of a `Breakpoint` object signals whether the exception breakpoint
    or filter could be successfully created and whether the condition is valid.
    In case of an error the `message` property explains the problem. The `id`
    property can be used to introduce a unique ID for the exception breakpoint
    or filter so that it can be updated subsequently by sending breakpoint
    events. For backward compatibility both the `breakpoints` array and the
    enclosing `body` are optional. If these elements are missing a client is not
    able to show problems for individual exception breakpoints or filters.
    """

    # _spec.json#1953

    body: Optional["SetExceptionBreakpointsResponseBody"] = None


@dataclass
class SetExpressionResponse(Response):
    """Response to `setExpression` request."""

    # _spec.json#3593

    body: Optional["SetExpressionResponseBody"] = None


@dataclass
class SetFunctionBreakpointsResponse(Response):
    """Response to `setFunctionBreakpoints` request.

    Returned is information about each breakpoint created by this request.
    """

    # _spec.json#1866

    body: Optional["SetFunctionBreakpointsResponseBody"] = None


@dataclass
class SetInstructionBreakpointsResponse(Response):
    """Response to `setInstructionBreakpoints` request."""

    # _spec.json#2199

    body: Optional["SetInstructionBreakpointsResponseBody"] = None


@dataclass
class SetVariableResponse(Response):
    """Response to `setVariable` request."""

    # _spec.json#3042

    body: Optional["SetVariableResponseBody"] = None


@dataclass
class SourceResponse(Response):
    """Response to `source` request."""

    # _spec.json#3137

    body: Optional["SourceResponseBody"] = None


@dataclass
class StackTraceResponse(Response):
    """Response to `stackTrace` request."""

    # _spec.json#2794

    body: Optional["StackTraceResponseBody"] = None


@dataclass
class StartDebuggingResponse(Response):
    """Response to `startDebugging` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1207



@dataclass
class StepBackResponse(Response):
    """Response to `stepBack` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2523



@dataclass
class StepInResponse(Response):
    """Response to `stepIn` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2407



@dataclass
class StepInTargetsResponse(Response):
    """Response to `stepInTargets` request."""

    # _spec.json#3688

    body: Optional["StepInTargetsResponseBody"] = None


@dataclass
class StepOutResponse(Response):
    """Response to `stepOut` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#2465



@dataclass
class TerminateResponse(Response):
    """Response to `terminate` request.

    This is just an acknowledgement, so no body field is required.
    """

    # _spec.json#1639



@dataclass
class TerminateThreadsResponse(Response):
    """Response to `terminateThreads` request.

    This is just an acknowledgement, no body field is required.
    """

    # _spec.json#3261



@dataclass
class ThreadsResponse(Response):
    """Response to `threads` request."""

    # _spec.json#3191

    body: Optional["ThreadsResponseBody"] = None


@dataclass
class VariablesResponse(Response):
    """Response to `variables` request."""

    # _spec.json#2958

    body: Optional["VariablesResponseBody"] = None


@dataclass
class WriteMemoryResponse(Response):
    """Response to `writeMemory` request."""

    # _spec.json#4094

    body: Optional["WriteMemoryResponseBody"] = None
