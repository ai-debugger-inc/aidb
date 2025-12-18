"""Execution control service operations."""

import asyncio
from typing import TYPE_CHECKING, cast

from aidb.common.capabilities import DAPCapability, OperationName
from aidb.common.constants import (
    CHILD_SESSION_WAIT_TIMEOUT_S,
    EVENT_POLL_TIMEOUT_S,
    MEDIUM_SLEEP_S,
    PROCESS_WAIT_TIMEOUT_S,
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
from aidb.dap.protocol.responses import RestartResponse, TerminateResponse
from aidb.models import (
    AidbStopResponse,
    ExecutionStateResponse,
    StartResponse,
)
from aidb.service.decorators import requires_capability
from aidb_common.io import is_event_loop_error

from ..base import BaseServiceComponent
from ..stack import StackService

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import ContinueResponse
    from aidb.interfaces import IContext
    from aidb.session import Session


class ExecutionControl(BaseServiceComponent):
    """Execution control service operations.

    Provides methods for controlling program execution: continue, pause,
    restart, stop, and goto operations.
    """

    def __init__(self, session: "Session", ctx: "IContext | None" = None) -> None:
        """Initialize execution control service.

        Parameters
        ----------
        session : Session
            Debug session instance
        ctx : IContext, optional
            Application context
        """
        super().__init__(session, ctx)

    async def _probe_callstack_for_paused_state(
        self,
    ) -> ExecutionStateResponse | None:
        """Probe callstack to detect paused state when event wasn't received.

        Returns
        -------
        ExecutionStateResponse | None
            Response if paused state detected, None otherwise
        """
        try:
            thread_id = await self.get_current_thread_id()
            # Create StackService to call callstack directly (avoids session.debug)
            stack_service = StackService(self.session, self.ctx)
            stack_response = await stack_service.callstack(thread_id=thread_id)

            if not (stack_response.success and stack_response.frames):
                return None

            top = stack_response.frames[0]
            from aidb.models import ExecutionState, SessionStatus, StopReason

            exec_state = ExecutionState(
                status=SessionStatus.PAUSED,
                running=False,
                paused=True,
                stop_reason=StopReason.UNKNOWN,
                thread_id=thread_id,
                frame_id=top.id,
                current_file=top.source.path if top.source else None,
                current_line=top.line,
            )
            self.ctx.debug(
                f"continue: Fallback detected paused state via callstack; "
                f"line={exec_state.current_line} file={exec_state.current_file}",
            )
            return ExecutionStateResponse(success=True, execution_state=exec_state)
        except Exception as probe_err:
            self.ctx.debug(f"continue: Fallback callstack probe failed: {probe_err}")
            return None

    async def _handle_continue_wait_result(
        self,
        result: str,
    ) -> ExecutionStateResponse | None:
        """Handle the result of waiting for stop/terminated event.

        Parameters
        ----------
        result : str
            Result from wait_for_stopped_or_terminated_async

        Returns
        -------
        ExecutionStateResponse | None
            Response if a final state was determined, None to fall through
        """
        if result == "stopped":
            self.ctx.debug("continue: Taking _build_stopped_execution_state path")
            return await self._build_stopped_execution_state()

        if result == "terminated":
            return self._build_terminated_state()

        if result == "timeout":
            self.ctx.debug("continue: Got timeout, checking if session terminated...")

            if self.session.dap.is_terminated:
                return self._build_terminated_state()

            probed_response = await self._probe_callstack_for_paused_state()
            if probed_response:
                return probed_response

        return None

    async def continue_(
        self,
        request: ContinueRequest,
        wait_for_stop: bool = False,
    ) -> ExecutionStateResponse:
        """Continue execution until the next breakpoint.

        Parameters
        ----------
        request : ContinueRequest
            DAP request specifying thread to continue
        wait_for_stop : bool
            If True, wait for a stopped event after continue

        Returns
        -------
        ExecutionStateResponse
            Current execution state after continuing
        """
        self.ctx.debug(f"continue_: Session status = {self.session.status}")
        thread_id = request.arguments.threadId if request.arguments else "None"

        self.ctx.debug(f"continue_: Sending continue request with threadId={thread_id}")
        response = await self.session.dap.send_request(request)
        self.ctx.debug(f"continue_: Got response: {response}")

        if wait_for_stop:
            if self.ctx.is_debug_enabled():
                self.ctx.debug(
                    "continue: waiting for stop/terminate event (edge-triggered)",
                )

            try:
                result = await self.session.events.wait_for_stopped_or_terminated_async(
                    timeout=STACK_TRACE_TIMEOUT_S,
                    edge_triggered=True,
                )
            except DebugTimeoutError:
                result = "timeout"

            if self.ctx.is_debug_enabled():
                self.ctx.debug(f"continue: wait completed with result={result}")

            wait_response = await self._handle_continue_wait_result(result)
            if wait_response:
                return wait_response

        self.ctx.debug(
            f"continue: Falling through to from_dap() path, "
            f"wait_for_stop={wait_for_stop}",
        )
        response.ensure_success()
        return ExecutionStateResponse.from_dap(cast("ContinueResponse", response))

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
        from aidb.dap.protocol.responses import PauseResponse

        response = await self._send_and_ensure(request, PauseResponse)
        return ExecutionStateResponse.from_dap(response)

    @requires_capability(DAPCapability.GOTO_TARGETS, OperationName.JUMP)
    async def goto(self, request: GotoRequest) -> ExecutionStateResponse:
        """Jump to a specific location in the target.

        Parameters
        ----------
        request : GotoRequest
            DAP request containing target location and thread information

        Returns
        -------
        ExecutionStateResponse
            Current execution state after jumping
        """
        from aidb.dap.protocol.responses import GotoResponse

        response = await self._send_and_ensure(request, GotoResponse)
        return ExecutionStateResponse.from_dap(response)

    @requires_capability(DAPCapability.RESTART, OperationName.RESTART)
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
        await self._send_and_ensure(request, RestartResponse)

    async def start(
        self,
        auto_wait: bool | None = None,
        wait_timeout: float = 5.0,
    ) -> StartResponse:
        """Post-initialization start operations.

        This method is called AFTER the session has been fully initialized.
        It handles any post-initialization tasks specific to execution control.

        Parameters
        ----------
        auto_wait : bool, optional
            Whether to automatically wait for the first stop event.
            If None, will auto-wait only if breakpoints are set.
        wait_timeout : float, optional
            Timeout in seconds for auto-wait

        Returns
        -------
        StartResponse
            Response containing session startup status
        """
        try:
            has_breakpoints = bool(getattr(self.session, "breakpoints", None))

            if hasattr(self.session, "_set_initial_breakpoints"):
                await self.session._set_initial_breakpoints()

            # For JavaScript adapters, wait for child session
            if (
                hasattr(self._session, "adapter")
                and self._session.adapter
                and hasattr(self._session.adapter, "requires_child_session_wait")
                and self._session.adapter.requires_child_session_wait
            ):
                await self._wait_for_child_session(timeout=CHILD_SESSION_WAIT_TIMEOUT_S)

            should_wait = auto_wait if auto_wait is not None else has_breakpoints

            if should_wait:
                try:
                    result = (
                        await self.session.events.wait_for_stopped_or_terminated_async(
                            timeout=wait_timeout,
                        )
                    )
                    self.ctx.debug(f"post-start auto-wait result: {result}")
                except Exception as wait_error:
                    self.ctx.debug(
                        f"post-start auto-wait error (non-fatal): {wait_error}",
                    )

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

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Raises
        ------
        TimeoutError
            If child session isn't created within timeout
        """
        self.ctx.info(
            f"Waiting for child session creation for parent {self._session.id}",
        )

        start_time = asyncio.get_event_loop().time()
        while True:
            if self._session.child_session_ids:
                child_id = self._session.child_session_ids[0]
                self.ctx.info(
                    f"Child session {child_id} created for parent {self._session.id}",
                )
                await asyncio.sleep(MEDIUM_SLEEP_S)
                return

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                msg = (
                    f"Timeout waiting for child session creation "
                    f"after {timeout}s for parent {self._session.id}"
                )
                self.ctx.error(msg)
                raise TimeoutError(msg)

            await asyncio.sleep(EVENT_POLL_TIMEOUT_S)

    async def stop(self) -> AidbStopResponse:
        """Stop the debug session.

        Returns
        -------
        AidbStopResponse
            Response containing session termination status
        """
        try:
            await self._send_terminate_request()
            dap_error = await self._disconnect_dap_client()
            adapter_error = await self._stop_adapter()

            if dap_error:
                raise dap_error
            if adapter_error:
                raise adapter_error

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

    async def _send_terminate_request(self) -> None:
        """Send terminate request if supported."""
        if self.session.dap.is_terminated:
            self.ctx.debug("Session already terminated, skipping terminate request")
            return

        if not self.session.supports_terminate():
            return

        request = TerminateRequest(seq=0)
        try:
            timeout = self.session.adapter.config.terminate_request_timeout
            await self._send_and_ensure(request, TerminateResponse, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.ctx.debug(
                "Terminate request timed out or cancelled - session already terminated",
            )
        except Exception as e:
            if self.session.dap.is_terminated:
                self.ctx.debug(f"Terminate request failed but session terminated: {e}")
            else:
                self.ctx.warning(f"Terminate request failed: {e}")

    async def _disconnect_dap_client(self) -> Exception | None:
        """Disconnect DAP client, returning any non-event-loop error."""
        if not (hasattr(self.session, "dap") and self.session.dap):
            return None

        try:
            await self._perform_dap_disconnect()
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"DAP disconnect skipped (event loop mismatch): {e}")
            else:
                return e
        return None

    async def _perform_dap_disconnect(self) -> None:
        """Perform the appropriate DAP disconnect based on adapter type."""
        adapter = getattr(self.session, "adapter", None)

        if adapter and getattr(adapter, "prefers_transport_only_disconnect", False):
            await self.session.dap.disconnect(
                skip_request=True,
                receiver_stop_timeout=PROCESS_WAIT_TIMEOUT_S,
            )
        elif adapter and not adapter.should_send_disconnect_request:
            self.ctx.debug("Adapter pooled - sending non-terminating disconnect")
            try:
                await self.session.dap.disconnect(
                    terminate_debuggee=False,
                    suspend_debuggee=False,
                    skip_request=False,
                )
            except Exception as e:
                self.ctx.debug(f"Non-terminating disconnect failed: {e}, closing only")
                await self.session.dap.disconnect(skip_request=True)
        else:
            await self.session.dap.disconnect()

    async def _stop_adapter(self) -> Exception | None:
        """Stop adapter, returning any non-event-loop error."""
        adapter = getattr(self.session, "adapter", None)
        if not (adapter and hasattr(adapter, "stop")):
            return None

        try:
            await self.session.adapter.stop()
        except RuntimeError as e:
            if is_event_loop_error(e):
                self.ctx.debug(f"Adapter stop skipped (event loop mismatch): {e}")
            else:
                return e
        return None

    def get_output(self, clear: bool = True) -> list[dict]:
        """Get program output (stdout/stderr) from the debug session.

        Parameters
        ----------
        clear : bool
            If True, clear the output buffer after retrieving

        Returns
        -------
        list[dict]
            List of output entries with 'category' and 'output' fields
        """
        return self.session.get_output(clear=clear)
