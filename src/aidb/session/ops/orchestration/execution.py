"""Execution control orchestration operations."""

import asyncio
from typing import TYPE_CHECKING, Optional, cast

from aidb.api.constants import (
    DEFAULT_WAIT_TIMEOUT_S,
    EVENT_POLL_TIMEOUT_S,
    MEDIUM_SLEEP_S,
    STACK_TRACE_TIMEOUT_S,
)
from aidb.common.errors import DebugTimeoutError
from aidb.dap.protocol.bodies import RestartArguments
from aidb.dap.protocol.requests import (
    ContinueRequest,
    GotoRequest,
    PauseRequest,
    RestartRequest,
    TerminateRequest,
)
from aidb.models import (
    AidbStopResponse,
    ExecutionStateResponse,
    StartResponse,
)

from ..base import SessionOperationsMixin
from ..decorators import requires_capability
from ..instrumentation import instrument_step
from .decorators import clears_frame_cache

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Response
    from aidb.dap.protocol.responses import (
        ContinueResponse,
        GotoResponse,
        PauseResponse,
    )
    from aidb.interfaces import IContext
    from aidb.session import Session


async def _build_stopped_execution_state(session_ops) -> ExecutionStateResponse:
    """Build ExecutionStateResponse for stopped state.

    This helper method creates a proper ExecutionStateResponse when execution
    has stopped at a breakpoint, step, or other stop reason. It extracts the
    stop reason from the DAP event processor and gets current position info.

    Parameters
    ----------
    session_ops : SessionOperationsMixin
        The operations mixin with access to session and context

    Returns
    -------
    ExecutionStateResponse
        Response with proper stopped state information
    """
    from aidb.models import ExecutionState, SessionStatus, StopReason

    # Debug: Log which session we're using
    resolved_session = session_ops.session
    session_ops.ctx.debug(
        f"_build_stopped_execution_state: parent_session={session_ops._session.id}, "
        f"resolved_session={resolved_session.id}, "
        f"is_child={resolved_session.is_child}, "
        f"has_child_sessions={bool(session_ops._session.child_session_ids)}",
    )

    # Get stop reason from DAP event processor
    # Try the last stopped event first (most reliable), then fall back to state
    event_processor = session_ops.session.dap._event_processor
    stop_reason_str = None

    # Check if we have a last stopped event with reason info
    if hasattr(event_processor, "_last_stopped_event"):
        last_stopped = event_processor._last_stopped_event
        if last_stopped and hasattr(last_stopped, "body") and last_stopped.body:
            stop_reason_str = getattr(last_stopped.body, "reason", None)

    # Fall back to state if event doesn't have reason
    if stop_reason_str is None:
        stop_reason_str = getattr(event_processor._state, "stop_reason", None)

    # Handle None explicitly (no reason available)
    if stop_reason_str is None:
        stop_reason_str = "unknown"

    # Map DAP stop reasons to our StopReason enum
    stop_reason_map = {
        "breakpoint": StopReason.BREAKPOINT,
        "step": StopReason.STEP,
        "pause": StopReason.PAUSE,
        "exception": StopReason.EXCEPTION,
        "entry": StopReason.ENTRY,
        "exit": StopReason.EXIT,
    }
    stop_reason = stop_reason_map.get(stop_reason_str, StopReason.UNKNOWN)

    # Get current thread and position info
    thread_id = await session_ops.get_current_thread_id()
    session_ops.ctx.debug(
        f"_build_stopped_execution_state: thread_id={thread_id}, "
        f"stop_reason={stop_reason}",
    )

    # Try to get current file/line from stack trace
    current_file = None
    current_line = None
    try:
        # Get call stack to find current position
        stack_response = await session_ops.session.debug.callstack(thread_id=thread_id)
        frame_count = len(stack_response.frames) if stack_response.frames else 0
        session_ops.ctx.debug(
            f"Call stack result: success={stack_response.success}, "
            f"frames_count={frame_count}",
        )
        if stack_response.success and stack_response.top_frame:
            top_frame = stack_response.top_frame
            session_ops.ctx.debug(
                f"Top frame: line={top_frame.source.line}, "
                f"path={top_frame.source.path}",
            )
            if top_frame.source and top_frame.source.path:
                current_file = top_frame.source.path
                current_line = top_frame.source.line
    except Exception as e:
        session_ops.ctx.debug(f"Could not get call stack for position: {e}")

    exec_state = ExecutionState(
        status=SessionStatus.PAUSED,
        running=False,
        paused=True,
        stop_reason=stop_reason,
        thread_id=thread_id,
        current_file=current_file,
        current_line=current_line,
        terminated=False,
    )

    return ExecutionStateResponse(success=True, execution_state=exec_state)


class ExecutionOperations(SessionOperationsMixin):
    """Execution control orchestration operations."""

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize execution operations.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

    @instrument_step("continue")
    @clears_frame_cache
    async def continue_(
        self,
        request: ContinueRequest,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Continue execution until the next breakpoint.

        Parameters
        ----------
        request : ContinueRequest
            DAP request specifying thread to continue and execution options
        wait_for_stop : bool
            If True, wait for a stopped event after continue (default: False)

        Returns
        -------
        ExecutionStateResponse
            Current execution state after continuing
        """
        # Debug logging
        self.ctx.debug(f"continue_: Session status = {self.session.status}")
        thread_id = request.arguments.threadId if request.arguments else "None"

        # Always send the continue request to resume execution, even if already stopped.
        # The is_dap_stopped() check was causing continue to be skipped when hitting
        # breakpoints in loops, preventing advancement to subsequent iterations.
        self.ctx.debug(f"continue_: Sending continue request with threadId={thread_id}")
        response = await self.session.dap.send_request(request)
        self.ctx.debug(f"continue_: Got response: {response}")

        if wait_for_stop:
            # Log wait start if debug enabled
            if self.ctx.is_debug_enabled():
                self.ctx.debug(
                    "continue: waiting for stop/terminate event (edge-triggered)",
                )

            try:
                # Use edge-triggered mode to wait for NEXT event, not stale state
                result = await self.session.events.wait_for_stopped_or_terminated_async(
                    timeout=STACK_TRACE_TIMEOUT_S,
                    edge_triggered=True,
                )
            except DebugTimeoutError:
                # Timeout waiting for stop - program may have run to completion
                # without hitting breakpoints
                result = "timeout"

            # Log wait result if debug enabled
            if self.ctx.is_debug_enabled():
                self.ctx.debug(f"continue: wait completed with result={result}")
                is_stopped = result == "stopped"
                self.ctx.debug(
                    f"continue: result type={type(result)}, "
                    f"result==`stopped`: {is_stopped}",
                )

            # If we waited for stop and got a stop/terminate, return the actual state
            if result == "stopped":
                # Build proper stopped state response
                self.ctx.debug("continue: Taking _build_stopped_execution_state path")
                return await _build_stopped_execution_state(self)
            if result == "timeout":
                self.ctx.debug(
                    "continue: Got timeout, checking if session terminated...",
                )
                # If session terminated, return terminated state immediately.
                if self.session.dap.is_terminated:
                    # Program terminated without hitting breakpoints
                    from aidb.models import ExecutionState, SessionStatus, StopReason

                    exec_state = ExecutionState(
                        status=SessionStatus.TERMINATED,
                        running=False,
                        paused=False,
                        stop_reason=StopReason.EXIT,
                        terminated=True,
                    )

                    return ExecutionStateResponse(
                        success=True,
                        execution_state=exec_state,
                    )
                # Otherwise, probe callstack to detect a paused state in cases
                # where adapters delay the stopped event until after continue response.
                try:
                    thread_id_probe = await self.get_current_thread_id()
                    stack_response = await self.session.debug.callstack(
                        thread_id=thread_id_probe,
                    )
                    if stack_response.success and stack_response.frames:
                        top = stack_response.frames[0]
                        from aidb.models import (
                            ExecutionState,
                            SessionStatus,
                            StopReason,
                        )

                        exec_state = ExecutionState(
                            status=SessionStatus.PAUSED,
                            running=False,
                            paused=True,
                            stop_reason=StopReason.UNKNOWN,
                            thread_id=thread_id_probe,
                            frame_id=top.id,
                            current_file=top.source.path if top.source else None,
                            current_line=top.line,
                        )
                        self.ctx.debug(
                            "continue: Fallback detected paused state via callstack; "
                            f"line={exec_state.current_line} "
                            f"file={exec_state.current_file}",
                        )
                        return ExecutionStateResponse(
                            success=True,
                            execution_state=exec_state,
                        )
                except Exception as probe_err:
                    self.ctx.debug(
                        f"continue: Fallback callstack probe failed: {probe_err}",
                    )
                # Otherwise fall through to return running state
            elif result == "terminated":
                # Build ExecutionState for terminated state
                from aidb.models import ExecutionState, SessionStatus, StopReason

                exec_state = ExecutionState(
                    status=SessionStatus.TERMINATED,
                    running=False,
                    paused=False,
                    stop_reason=StopReason.EXIT,
                    terminated=True,
                )

                return ExecutionStateResponse(success=True, execution_state=exec_state)

        # Fall through to default response (no location info)
        self.ctx.debug(
            f"continue: Falling through to from_dap() path, "
            f"wait_for_stop={wait_for_stop}",
        )
        response.ensure_success()
        return ExecutionStateResponse.from_dap(cast("ContinueResponse", response))

    @clears_frame_cache
    async def pause(self, request: PauseRequest) -> ExecutionStateResponse:
        """Pause the execution.

        Parameters
        ----------
        request : PauseRequest
            DAP request specifying which thread to pause

        Returns
        -------
        ExecutionStateResponse
            Current execution state after pausing
        """
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        return ExecutionStateResponse.from_dap(cast("PauseResponse", response))

    @requires_capability("supportsGotoTargetsRequest", "jump to location")
    @clears_frame_cache
    async def goto(self, request: GotoRequest) -> ExecutionStateResponse:
        """Jump to a specific location in the target.

        Parameters
        ----------
        request : GotoRequest
            DAP request containing target location and thread information

        Returns
        -------
        ExecutionStateResponse
            Current execution state after jumping to the target location
        """
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()
        return ExecutionStateResponse.from_dap(cast("GotoResponse", response))

    @requires_capability("supportsRestartRequest", "restart")
    @clears_frame_cache
    async def restart(self, arguments: RestartArguments | None = None) -> None:
        """Restart the current debug session.

        Parameters
        ----------
        arguments : RestartArguments, optional
            Optional restart arguments specifying new configuration
        """
        request = RestartRequest(
            seq=await self.session.dap.get_next_seq(),
            arguments=arguments,
        )
        response: Response = await self.session.dap.send_request(request)
        response.ensure_success()

    async def start(  # noqa: C901
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Post-initialization start operations.

        This method is called AFTER the session has been fully initialized
        by SessionLifecycleMixin. It handles any post-initialization tasks
        that are specific to execution control.

        Note: All initialization (adapter launch, DAP connection, handshake)
        is handled by SessionLifecycleMixin.start().

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event after starting.
            If None (default), will auto-wait only if breakpoints are set.
        wait_timeout : float, optional
            Timeout in seconds for auto-wait, default 5.0

        Returns
        -------
        StartResponse
            Response containing session startup status and information
        """
        try:
            # Check if we have breakpoints before setting them
            has_breakpoints = bool(getattr(self.session, "breakpoints", None))

            # Set initial breakpoints if they weren't already set during initialization
            # This handles edge cases where breakpoints are added after session creation
            # (e.g., for child sessions that inherit breakpoints from parent)
            # The _set_initial_breakpoints() method is idempotent and will skip if
            # already called, preventing issues with pooled adapters
            if hasattr(self.session, "_set_initial_breakpoints"):
                await self.session._set_initial_breakpoints()

            # For adapters that require child session creation (e.g., JavaScript),
            # wait for the child to be created and initialized before proceeding
            # Note: Use self._session (root) not self.session (auto-resolving) to check
            # adapter requirements, since we're checking if we need to wait for a child
            if (
                hasattr(self._session, "adapter")
                and self._session.adapter
                and hasattr(self._session.adapter, "requires_child_session_wait")
                and self._session.adapter.requires_child_session_wait
            ):
                await self._wait_for_child_session(timeout=10.0)

            # If initial breakpoints were set, wait briefly for the first stop so
            # the session begins in a paused state. This avoids races where tests
            # immediately issue a continue before the first breakpoint stop has
            # been delivered.
            if has_breakpoints:
                try:
                    result = (
                        await self.session.events.wait_for_stopped_or_terminated_async(
                            timeout=DEFAULT_WAIT_TIMEOUT_S,
                        )
                    )
                    self.ctx.debug(
                        f"post-start auto-wait result: {result}",
                    )
                except Exception as wait_error:
                    self.ctx.debug(
                        f"post-start auto-wait error (non-fatal): {wait_error}",
                    )
            #     else:
            #         self.ctx.debug(
            #             "Session is paused after initialization (not at breakpoint), "
            #             "sending initial continue to start execution",
            #         )
            #         try:
            #             # Get current thread ID for the continue request
            #             thread_id = await self.get_current_thread_id()
            #
            #             # Create and send continue request
            #             from aidb.dap.protocol.bodies import ContinueArguments
            #             from aidb.dap.protocol.requests import ContinueRequest
            #
            #             continue_args = ContinueArguments(threadId=thread_id)
            #             continue_request = ContinueRequest(
            #                 seq=await self.session.dap.get_next_seq(),
            #                 arguments=continue_args,
            #             )
            #
            #             # If we have breakpoints, send continue WITH wait_for_stop
            #             # to ensure we wait for the first breakpoint hit
            #             if has_breakpoints:
            #                 self.ctx.debug(
            #                     "Sending continue with wait_for_stop=True "
            #                     "to wait for first breakpoint hit",
            #                 )
            #                 await self.continue_(continue_request, wait_for_stop=True)
            #                 sent_continue_with_wait = True
            #                 self.ctx.debug(
            #                     "Continue completed - session stopped at breakpoint",
            #                 )
            #             else:
            #                 # No breakpoints - send continue without waiting
            #                 await self.session.dap.send_request(continue_request)
            #                 self.ctx.debug("Initial continue sent successfully")
            #
            #         except Exception as e:
            #             self.ctx.warning(f"Failed to send initial continue: {e}")
            #             # Don't fail the start operation - continue with normal flow
            #
            # # Determine auto-wait behavior
            # if auto_wait is None:
            #     # Default: auto-wait if breakpoints are set
            #     auto_wait = has_breakpoints
            #     if auto_wait:
            #         self.ctx.debug(
            #             "Auto-waiting for stop event since breakpoints are set",
            #         )
            #
            # # Auto-wait for first breakpoint hit if requested
            # # Skip if we already waited via continue_ above
            # if auto_wait and not sent_continue_with_wait:
            #     # Check if already paused at breakpoint
            #     if self.session.is_paused():
            #         current_stop_reason = (
            #             self.session.dap.get_stop_reason()
            #             if hasattr(self.session.dap, "get_stop_reason")
            #             else None
            #         )
            #         if current_stop_reason == "breakpoint":
            #             self.ctx.debug(
            #                 "Already paused at breakpoint, skipping auto-wait",
            #             )
            #         else:
            #             # Paused but not at breakpoint - wait for breakpoint
            #             self.ctx.debug(
            #                 f"Waiting for stop event (timeout={wait_timeout}s)",
            #             )
            #             try:
            #                 await self.session.wait_for_stop(timeout=wait_timeout)
            #                 self.ctx.debug("Successfully stopped at breakpoint")
            #             except Exception as wait_error:
            #                 self.ctx.warning(
            #                     f"Auto-wait timed out or failed: {wait_error}. "
            #                     "Program may not have hit a breakpoint.",
            #                 )
            #     else:
            #         # Not paused - wait for stop
            #         self.ctx.debug(f"Waiting for stop event (timeout={wait_timeout}s)")
            #         try:
            #             await self.session.wait_for_stop(timeout=wait_timeout)
            #             self.ctx.debug("Successfully stopped at breakpoint")
            #         except Exception as wait_error:
            #             self.ctx.warning(
            #                 f"Auto-wait timed out or failed: {wait_error}. "
            #                 "Program may not have hit a breakpoint.",
            #             )

            return StartResponse(
                success=True,
                message="Debug session started successfully",
                session_info=self.session.info,
            )

        except Exception as e:
            self.ctx.error(f"Failed in post-initialization: {e}")
            return StartResponse(
                success=False,
                message=f"Failed in post-initialization: {e}",
                session_info=self.session.info,
            )

    async def _wait_for_child_session(self, timeout: float = 10.0) -> None:
        """Wait for child session to be created and initialized.

        For adapters like JavaScript that create child sessions asynchronously
        via startDebugging reverse requests, this waits until the child session
        is registered before continuing. The session property will then
        automatically resolve to the child for all operations.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Raises
        ------
        TimeoutError
            If child session isn't created within timeout
        """
        import asyncio

        self.ctx.info(
            f"Waiting for child session creation for parent {self._session.id}",
        )

        start_time = asyncio.get_event_loop().time()
        while True:
            # Check if a child session has been registered
            if self._session.child_session_ids:
                child_id = self._session.child_session_ids[0]
                self.ctx.info(
                    f"Child session {child_id} created for parent {self._session.id}",
                )
                # Give the child a moment to complete initialization
                # The session property will handle resolution automatically
                await asyncio.sleep(MEDIUM_SLEEP_S)
                return

            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                msg = (
                    f"Timeout waiting for child session creation "
                    f"after {timeout}s for parent {self._session.id}"
                )
                self.ctx.error(msg)
                raise TimeoutError(msg)

            # Wait a bit before checking again
            await asyncio.sleep(EVENT_POLL_TIMEOUT_S)

    async def stop(self) -> AidbStopResponse:
        """Stop the debug session.

        Returns
        -------
        AidbStopResponse
            Response containing session termination status
        """
        try:
            # Send terminate request if supported and not already terminated
            if self.session.supports_terminate() and not self.session.dap.is_terminated:
                request = TerminateRequest(seq=0)  # seq will be set by client
                try:
                    # Use adapter-specific timeout (Java: 5s, Python/JS: 1s)
                    timeout = self.session.adapter.config.terminate_request_timeout
                    response = await self.session.dap.send_request(
                        request,
                        timeout=timeout,
                    )
                    response.ensure_success()
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    # Timeout or cancellation - session already terminated
                    # CancelledError: Session terminated, cancelled pending requests
                    # TimeoutError: Terminated event arrived, flag not yet updated
                    self.ctx.debug(
                        "Terminate request timed out or cancelled - "
                        "session already terminated",
                    )
                except Exception as e:
                    # If terminate request fails but session is already
                    # terminated, ignore
                    if self.session.dap.is_terminated:
                        self.ctx.debug(
                            "Terminate request failed but session already "
                            f"terminated: {e}",
                        )
                    else:
                        self.ctx.warning(f"Terminate request failed: {e}")
            elif self.session.dap.is_terminated:
                self.ctx.debug("Session already terminated, skipping terminate request")

            # Disconnect DAP client
            if hasattr(self.session, "dap") and self.session.dap:
                # Adapter indicates transport-only disconnect preference (e.g., Python/JS)
                if (
                    hasattr(self.session, "adapter")
                    and self.session.adapter
                    and getattr(
                        self.session.adapter,
                        "prefers_transport_only_disconnect",
                        False,
                    )
                ):
                    await self.session.dap.disconnect(
                        skip_request=True,
                        receiver_stop_timeout=0.5,
                    )
                # Check if adapter wants to skip DisconnectRequest (pooled servers)
                elif (
                    hasattr(self.session, "adapter")
                    and self.session.adapter
                    and not self.session.adapter.should_send_disconnect_request
                ):
                    # For pooled adapters (Java), send a non-terminating
                    # DisconnectRequest to let the server finalize state,
                    # then close the transport. This avoids the java-debug
                    # deadlock we saw with terminateDebuggee=True while also
                    # preventing LSP startDebugSession timeouts on reuse.
                    self.ctx.debug(
                        "Adapter pooled - sending non-terminating DisconnectRequest",
                    )
                    try:
                        await self.session.dap.disconnect(
                            terminate_debuggee=False,
                            suspend_debuggee=False,
                            skip_request=False,
                        )
                    except Exception as e:
                        # Non-fatal; fall back to closing transport only
                        self.ctx.debug(
                            f"Non-terminating DisconnectRequest failed: {e}, "
                            "closing transport only",
                        )
                        await self.session.dap.disconnect(skip_request=True)
                else:
                    await self.session.dap.disconnect()

            # Stop adapter (terminates process and releases resources)
            if hasattr(self.session, "adapter") and hasattr(
                self.session.adapter,
                "stop",
            ):
                await self.session.adapter.stop()

            return AidbStopResponse(
                success=True,
                message="Debug session stopped successfully",
            )

        except Exception as e:
            self.ctx.error(f"Failed to stop debug session: {e}")
            return AidbStopResponse(
                success=False,
                message=f"Failed to stop: {e}",
            )
