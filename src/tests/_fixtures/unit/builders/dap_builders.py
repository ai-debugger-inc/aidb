"""Builders for DAP protocol objects.

Provides a fluent builder API for constructing DAP requests, responses, and events with
sensible defaults. This makes test data creation concise while allowing customization of
specific fields.
"""

from __future__ import annotations

from typing import Any

import pytest

from aidb.dap.protocol.base import Request, Response
from aidb.dap.protocol.bodies import (
    BreakpointEventBody,
    ContinueArguments,
    EvaluateArguments,
    ModuleEventBody,
    NextArguments,
    OutputEventBody,
    PauseArguments,
    ProcessEventBody,
    ScopesArguments,
    SetBreakpointsResponseBody,
    SetExceptionBreakpointsArguments,
    StackTraceArguments,
    StepInArguments,
    StepOutArguments,
    StoppedEventBody,
    ThreadEventBody,
    VariablesArguments,
)
from aidb.dap.protocol.events import (
    BreakpointEvent,
    ContinuedEvent,
    InitializedEvent,
    ModuleEvent,
    OutputEvent,
    ProcessEvent,
    StoppedEvent,
    TerminatedEvent,
    ThreadEvent,
)
from aidb.dap.protocol.requests import (
    ContinueRequest,
    EvaluateRequest,
    NextRequest,
    PauseRequest,
    ScopesRequest,
    SetExceptionBreakpointsRequest,
    StackTraceRequest,
    StepInRequest,
    StepOutRequest,
    VariablesRequest,
)
from aidb.dap.protocol.responses import (
    ConfigurationDoneResponse,
    ContinueResponse,
    InitializeResponse,
    LaunchResponse,
    SetBreakpointsResponse,
)
from aidb.dap.protocol.types import Breakpoint, Capabilities, Module, Source


class DAPRequestBuilder:
    """Builder for DAP request objects.

    Provides static factory methods for creating common DAP requests
    with sensible defaults. Use for creating test requests without
    needing to specify all fields.

    Examples
    --------
    >>> request = DAPRequestBuilder.next_request(thread_id=1)
    >>> step_in = DAPRequestBuilder.step_in_request(thread_id=1, target_id=5)
    """

    _seq_counter: int = 1

    @classmethod
    def _next_seq(cls) -> int:
        """Get next sequence number."""
        seq = cls._seq_counter
        cls._seq_counter += 1
        return seq

    @classmethod
    def reset_seq(cls) -> None:
        """Reset sequence counter (call in test fixtures)."""
        cls._seq_counter = 1

    @staticmethod
    def next_request(
        thread_id: int = 1,
        single_thread: bool | None = None,
        granularity: str | None = None,
    ) -> NextRequest:
        """Create a NextRequest (step over).

        Parameters
        ----------
        thread_id : int
            Thread to step
        single_thread : bool | None
            If True, don't resume other threads
        granularity : str | None
            Stepping granularity: "statement", "line", "instruction"
        """
        return NextRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=NextArguments(
                threadId=thread_id,
                singleThread=single_thread,
                granularity=granularity,
            ),
        )

    @staticmethod
    def step_in_request(
        thread_id: int = 1,
        target_id: int | None = None,
        single_thread: bool | None = None,
        granularity: str | None = None,
    ) -> StepInRequest:
        """Create a StepInRequest.

        Parameters
        ----------
        thread_id : int
            Thread to step
        target_id : int | None
            Target to step into (for step into target)
        single_thread : bool | None
            If True, don't resume other threads
        granularity : str | None
            Stepping granularity
        """
        return StepInRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=StepInArguments(
                threadId=thread_id,
                targetId=target_id,
                singleThread=single_thread,
                granularity=granularity,
            ),
        )

    @staticmethod
    def step_out_request(
        thread_id: int = 1,
        single_thread: bool | None = None,
        granularity: str | None = None,
    ) -> StepOutRequest:
        """Create a StepOutRequest.

        Parameters
        ----------
        thread_id : int
            Thread to step
        single_thread : bool | None
            If True, don't resume other threads
        granularity : str | None
            Stepping granularity
        """
        return StepOutRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=StepOutArguments(
                threadId=thread_id,
                singleThread=single_thread,
                granularity=granularity,
            ),
        )

    @staticmethod
    def continue_request(
        thread_id: int = 1,
        single_thread: bool | None = None,
    ) -> ContinueRequest:
        """Create a ContinueRequest.

        Parameters
        ----------
        thread_id : int
            Thread to continue
        single_thread : bool | None
            If True, only continue the specified thread
        """
        return ContinueRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=ContinueArguments(
                threadId=thread_id,
                singleThread=single_thread,
            ),
        )

    @staticmethod
    def pause_request(thread_id: int = 1) -> PauseRequest:
        """Create a PauseRequest.

        Parameters
        ----------
        thread_id : int
            Thread to pause
        """
        return PauseRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=PauseArguments(threadId=thread_id),
        )

    @staticmethod
    def stack_trace_request(
        thread_id: int = 1,
        start_frame: int | None = None,
        levels: int | None = None,
    ) -> StackTraceRequest:
        """Create a StackTraceRequest.

        Parameters
        ----------
        thread_id : int
            Thread to get stack trace for
        start_frame : int | None
            First frame index (0 if not specified)
        levels : int | None
            Max frames to return (all if not specified)
        """
        return StackTraceRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=StackTraceArguments(
                threadId=thread_id,
                startFrame=start_frame,
                levels=levels,
            ),
        )

    @staticmethod
    def scopes_request(frame_id: int = 0) -> ScopesRequest:
        """Create a ScopesRequest.

        Parameters
        ----------
        frame_id : int
            Stack frame to get scopes for
        """
        return ScopesRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=ScopesArguments(frameId=frame_id),
        )

    @staticmethod
    def variables_request(
        variables_reference: int = 1,
        filter_type: str | None = None,
        start: int | None = None,
        count: int | None = None,
    ) -> VariablesRequest:
        """Create a VariablesRequest.

        Parameters
        ----------
        variables_reference : int
            Variable container reference
        filter_type : str | None
            "indexed" or "named" to filter children
        start : int | None
            Start index for indexed variables
        count : int | None
            Number of variables to return
        """
        return VariablesRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=VariablesArguments(
                variablesReference=variables_reference,
                filter=filter_type,
                start=start,
                count=count,
            ),
        )

    @staticmethod
    def evaluate_request(
        expression: str,
        frame_id: int | None = None,
        context: str | None = None,
    ) -> EvaluateRequest:
        """Create an EvaluateRequest.

        Parameters
        ----------
        expression : str
            Expression to evaluate
        frame_id : int | None
            Stack frame for evaluation context
        context : str | None
            Context: "watch", "repl", "hover", "clipboard"
        """
        return EvaluateRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=EvaluateArguments(
                expression=expression,
                frameId=frame_id,
                context=context,
            ),
        )

    @staticmethod
    def set_exception_breakpoints_request(
        filters: list[str] | None = None,
    ) -> SetExceptionBreakpointsRequest:
        """Create a SetExceptionBreakpointsRequest.

        Parameters
        ----------
        filters : list[str] | None
            Exception filter IDs (e.g., ["uncaught", "raised"])
        """
        if filters is None:
            filters = []
        return SetExceptionBreakpointsRequest(
            seq=DAPRequestBuilder._next_seq(),
            arguments=SetExceptionBreakpointsArguments(filters=filters),
        )


class DAPResponseBuilder:
    """Builder for DAP response objects.

    Provides a fluent API for constructing Response objects with
    reasonable defaults that can be overridden as needed.

    Examples
    --------
    >>> builder = DAPResponseBuilder()
    >>> response = builder.with_command("initialize").with_success(True).build()
    >>> error_response = builder.with_command("launch").with_error("Failed").build()
    """

    def __init__(self) -> None:
        """Initialize builder with default values."""
        self._seq: int = 1
        self._request_seq: int = 1
        self._success: bool = True
        self._command: str = "unknown"
        self._body: dict[str, Any] | None = None
        self._message: str | None = None

    def with_seq(self, seq: int) -> DAPResponseBuilder:
        """Set the sequence number."""
        self._seq = seq
        return self

    def with_request_seq(self, request_seq: int) -> DAPResponseBuilder:
        """Set the request sequence number this responds to."""
        self._request_seq = request_seq
        return self

    def with_command(self, command: str) -> DAPResponseBuilder:
        """Set the command name."""
        self._command = command
        return self

    def with_success(self, success: bool) -> DAPResponseBuilder:
        """Set success status."""
        self._success = success
        return self

    def with_body(self, body: dict[str, Any]) -> DAPResponseBuilder:
        """Set the response body."""
        self._body = body
        return self

    def with_error(self, message: str) -> DAPResponseBuilder:
        """Mark as error response with given message."""
        self._success = False
        self._message = message
        return self

    def build(self) -> Response:
        """Build the Response object."""
        return Response(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command=self._command,
            body=self._body,
            message=self._message,
        )

    def build_initialize(
        self,
        supports_configuration_done: bool = True,
        supports_conditional_breakpoints: bool = True,
    ) -> InitializeResponse:
        """Build an InitializeResponse with capabilities."""
        capabilities = Capabilities(
            supportsConfigurationDoneRequest=supports_configuration_done,
            supportsConditionalBreakpoints=supports_conditional_breakpoints,
        )
        return InitializeResponse(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command="initialize",
            body=capabilities,
            message=self._message,
        )

    def build_launch(self) -> LaunchResponse:
        """Build a LaunchResponse (acknowledgement)."""
        return LaunchResponse(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command="launch",
            message=self._message,
        )

    def build_configuration_done(self) -> ConfigurationDoneResponse:
        """Build a ConfigurationDoneResponse (acknowledgement)."""
        return ConfigurationDoneResponse(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command="configurationDone",
            message=self._message,
        )

    def build_continue(self, all_threads_continued: bool = True) -> ContinueResponse:
        """Build a ContinueResponse."""
        from aidb.dap.protocol.bodies import ContinueResponseBody

        return ContinueResponse(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command="continue",
            body=ContinueResponseBody(allThreadsContinued=all_threads_continued),
            message=self._message,
        )

    def build_set_breakpoints(
        self,
        breakpoints: list[Breakpoint] | None = None,
    ) -> SetBreakpointsResponse:
        """Build a SetBreakpointsResponse."""
        if breakpoints is None:
            breakpoints = [Breakpoint(verified=True, id=1, line=10)]

        return SetBreakpointsResponse(
            seq=self._seq,
            request_seq=self._request_seq,
            success=self._success,
            command="setBreakpoints",
            body=SetBreakpointsResponseBody(breakpoints=breakpoints),
            message=self._message,
        )


class DAPEventBuilder:
    """Builder and factory for DAP event objects.

    Provides static factory methods for creating common events
    with sensible defaults. Use for creating test events without
    needing to specify all fields.

    Examples
    --------
    >>> event = DAPEventBuilder.stopped_event(reason="breakpoint", thread_id=1)
    >>> bp_event = DAPEventBuilder.breakpoint_event(verified=True, line=42)
    """

    _seq_counter: int = 1

    @classmethod
    def _next_seq(cls) -> int:
        """Get next sequence number."""
        seq = cls._seq_counter
        cls._seq_counter += 1
        return seq

    @classmethod
    def reset_seq(cls) -> None:
        """Reset sequence counter (call in test fixtures)."""
        cls._seq_counter = 1

    @staticmethod
    def initialized_event() -> InitializedEvent:
        """Create an InitializedEvent."""
        return InitializedEvent(seq=DAPEventBuilder._next_seq())

    @staticmethod
    def stopped_event(
        reason: str = "breakpoint",
        thread_id: int = 1,
        all_threads_stopped: bool = True,
        hit_breakpoint_ids: list[int] | None = None,
        description: str | None = None,
        seq: int | None = None,
    ) -> StoppedEvent:
        """Create a StoppedEvent.

        Parameters
        ----------
        reason : str
            Stop reason: "breakpoint", "step", "pause", "exception", etc.
        thread_id : int
            Thread that stopped
        all_threads_stopped : bool
            Whether all threads stopped
        hit_breakpoint_ids : list[int] | None
            IDs of breakpoints that triggered the stop
        description : str | None
            Human-readable description
        seq : int | None
            Optional sequence number (auto-generated if not provided)
        """
        return StoppedEvent(
            seq=seq if seq is not None else DAPEventBuilder._next_seq(),
            body=StoppedEventBody(
                reason=reason,
                threadId=thread_id,
                allThreadsStopped=all_threads_stopped,
                hitBreakpointIds=hit_breakpoint_ids,
                description=description,
            ),
        )

    @staticmethod
    def breakpoint_event(
        breakpoint_id: int = 1,
        verified: bool = True,
        line: int = 10,
        reason: str = "changed",
        message: str | None = None,
    ) -> BreakpointEvent:
        """Create a BreakpointEvent.

        Parameters
        ----------
        breakpoint_id : int
            ID of the breakpoint
        verified : bool
            Whether breakpoint is verified
        line : int
            Line number
        reason : str
            Reason: "changed", "new", "removed"
        message : str | None
            Optional message (often for unverified breakpoints)
        """
        return BreakpointEvent(
            seq=DAPEventBuilder._next_seq(),
            body=BreakpointEventBody(
                reason=reason,
                breakpoint=Breakpoint(
                    id=breakpoint_id,
                    verified=verified,
                    line=line,
                    message=message,
                ),
            ),
        )

    @staticmethod
    def continued_event(
        thread_id: int = 1,
        all_threads_continued: bool = True,
        seq: int | None = None,
    ) -> ContinuedEvent:
        """Create a ContinuedEvent."""
        from aidb.dap.protocol.bodies import ContinuedEventBody

        return ContinuedEvent(
            seq=seq if seq is not None else DAPEventBuilder._next_seq(),
            body=ContinuedEventBody(
                threadId=thread_id,
                allThreadsContinued=all_threads_continued,
            ),
        )

    @staticmethod
    def terminated_event(restart: bool | None = None) -> TerminatedEvent:
        """Create a TerminatedEvent."""
        from aidb.dap.protocol.bodies import TerminatedEventBody

        body = TerminatedEventBody(restart=restart) if restart is not None else None
        return TerminatedEvent(
            seq=DAPEventBuilder._next_seq(),
            body=body,
        )

    @staticmethod
    def thread_event(
        thread_id: int = 1,
        reason: str = "started",
    ) -> ThreadEvent:
        """Create a ThreadEvent.

        Parameters
        ----------
        thread_id : int
            ID of the thread
        reason : str
            "started" or "exited"
        """
        return ThreadEvent(
            seq=DAPEventBuilder._next_seq(),
            body=ThreadEventBody(
                threadId=thread_id,
                reason=reason,
            ),
        )

    @staticmethod
    def output_event(
        output: str,
        category: str = "stdout",
        source: Source | None = None,
        line: int | None = None,
    ) -> OutputEvent:
        """Create an OutputEvent.

        Parameters
        ----------
        output : str
            Output text
        category : str
            "console", "stdout", "stderr", "telemetry"
        source : Source | None
            Source location
        line : int | None
            Line number in source
        """
        return OutputEvent(
            seq=DAPEventBuilder._next_seq(),
            body=OutputEventBody(
                output=output,
                category=category,
                source=source,
                line=line,
            ),
        )

    @staticmethod
    def process_event(
        name: str = "test_program",
        system_process_id: int | None = None,
        is_local_process: bool = True,
        start_method: str = "launch",
    ) -> ProcessEvent:
        """Create a ProcessEvent.

        Parameters
        ----------
        name : str
            Process name
        system_process_id : int | None
            OS process ID
        is_local_process : bool
            Whether process is local
        start_method : str
            "launch", "attach", "attachForSuspendedLaunch"
        """
        return ProcessEvent(
            seq=DAPEventBuilder._next_seq(),
            body=ProcessEventBody(
                name=name,
                systemProcessId=system_process_id,
                isLocalProcess=is_local_process,
                startMethod=start_method,
            ),
        )

    @staticmethod
    def module_event(
        module_id: int | str = 1,
        module_name: str = "test_module",
        reason: str = "new",
        path: str | None = None,
    ) -> ModuleEvent:
        """Create a ModuleEvent.

        Parameters
        ----------
        module_id : int | str
            Module identifier
        module_name : str
            Module name
        reason : str
            "new", "changed", "removed"
        path : str | None
            Path to module file
        """
        return ModuleEvent(
            seq=DAPEventBuilder._next_seq(),
            body=ModuleEventBody(
                reason=reason,
                module=Module(
                    id=module_id,
                    name=module_name,
                    path=path,
                ),
            ),
        )


@pytest.fixture
def request_builder() -> type[DAPRequestBuilder]:
    """Fixture providing the request builder class.

    Returns the class itself since all methods are static/class methods. Resets sequence
    counter for test isolation.
    """
    DAPRequestBuilder.reset_seq()
    return DAPRequestBuilder


@pytest.fixture
def response_builder() -> DAPResponseBuilder:
    """Fixture providing a fresh response builder."""
    return DAPResponseBuilder()


@pytest.fixture
def event_builder() -> type[DAPEventBuilder]:
    """Fixture providing the event builder class.

    Returns the class itself since all methods are static/class methods. Resets sequence
    counter for test isolation.
    """
    DAPEventBuilder.reset_seq()
    return DAPEventBuilder
