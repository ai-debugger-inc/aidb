"""Request/response handler for DAP client.

This module manages the core request/response flow, including request tracking, sequence
numbering, and response correlation.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Optional

from aidb.common.constants import DEFAULT_REQUEST_TIMEOUT_S
from aidb_common.config import config

if TYPE_CHECKING:
    from aidb.dap.client.events import EventProcessor

from aidb.common.errors import (
    DebugConnectionError,
    DebugSessionLostError,
    DebugTimeoutError,
)
from aidb.dap.client.constants import CommandType
from aidb.dap.protocol.base import Request, Response
from aidb.dap.response import ResponseRegistry
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

if TYPE_CHECKING:
    from .retry import DAPRetryManager
    from .transport import DAPTransport


class RequestHandler(Obj):
    """Handles DAP request/response processing.

    This class manages the core request/response flow, including:
    - Sequence number generation
    - Request serialization
    - Response correlation
    - Timeout handling
    """

    def __init__(
        self,
        transport: "DAPTransport",
        ctx: Optional["IContext"] = None,
        retry_manager: Optional["DAPRetryManager"] = None,
    ):
        """Initialize the request handler.

        Parameters
        ----------
        transport : DAPTransport
            Transport layer for sending/receiving messages
        ctx : IContext, optional
            Application context for logging
        retry_manager : DAPRetryManager, optional
            Manager for retry logic
        """
        super().__init__(ctx)
        self.transport = transport
        self.retry_manager = retry_manager

        # Request tracking
        self._seq = 0
        self._pending_requests: dict[int, asyncio.Future[Response]] = {}

        # Request serialization (prevent race conditions)
        self._request_semaphore = asyncio.Semaphore(1)

        # Get timeout from ConfigManager (default 2 seconds)
        self.DEFAULT_WAIT_TIMEOUT = config.get_dap_request_timeout()

        # Response registry for type conversion
        self._response_registry = ResponseRegistry()

        # Event processor reference (set later via set_event_processor)
        self._event_processor: EventProcessor | None = None

    def set_event_processor(self, event_processor: "EventProcessor") -> None:
        """Set the event processor reference.

        Parameters
        ----------
        event_processor : EventProcessor
            The event processor to use for terminated event listening
        """
        self._event_processor = event_processor

    async def get_next_seq(self) -> int:
        """Get the next sequence number for a request.

        Returns
        -------
        int
            The next sequence number
        """
        async with self.async_lock:
            self._seq += 1
            return self._seq

    async def send_request(
        self,
        request: Request,
        timeout: float | None = None,
        is_retry: bool = False,
    ) -> Response:
        """Send a DAP request and wait for response.

        Parameters
        ----------
        request : Request
            The typed DAP request object to send
        timeout : float, optional
            Response timeout in seconds (default: 30)
        is_retry : bool
            Whether this is a retry attempt

        Returns
        -------
        Response
            The typed DAP response

        Raises
        ------
        DebugTimeoutError
            If response not received within timeout
        DebugConnectionError
            If not connected or connection lost
        """
        if timeout is None:
            timeout = DEFAULT_REQUEST_TIMEOUT_S

        return await self._send_request_core(
            request=request,
            timeout=timeout,
            is_retry=is_retry,
        )

    async def send_request_no_wait(self, request: Request) -> int:
        """Send a DAP request without waiting for response.

        Parameters
        ----------
        request : Request
            The typed DAP request object to send

        Returns
        -------
        int
            The sequence number of the sent request

        Raises
        ------
        DebugConnectionError
            If not connected
        """
        if not self.transport.is_connected():
            msg = "Not connected to DAP adapter"
            raise DebugConnectionError(msg)

        # Get sequence number and update request
        seq = await self.get_next_seq()
        request.seq = seq

        # Create future but don't wait
        future: asyncio.Future[Response] = asyncio.Future()
        async with self.async_lock:
            self._pending_requests[seq] = future

        # Send without waiting
        await self.transport.send_message(request)
        self.ctx.debug(f"Sent {request.command} request (seq={seq}) without waiting")

        return seq

    async def wait_for_response(self, seq: int, timeout: float = 15.0) -> Response:
        """Wait for a specific response by sequence number.

        Parameters
        ----------
        seq : int
            The sequence number to wait for
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        Response
            The response with matching sequence number

        Raises
        ------
        DebugTimeoutError
            If response not received within timeout
        """
        # Get the future for this request
        async with self.async_lock:
            future = self._pending_requests.get(seq)
            if not future:
                msg = f"No pending request with seq={seq}"
                raise ValueError(msg)

        # Wait for the future to complete
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            # NOW remove it from pending after we've retrieved the result
            async with self.async_lock:
                self._pending_requests.pop(seq, None)
            return response
        except asyncio.TimeoutError as e:
            msg = f"Timeout waiting for response to request seq={seq}"
            raise DebugTimeoutError(msg) from e

    async def handle_response(self, message: dict[str, Any]) -> None:
        """Handle a response message from the adapter.

        Parameters
        ----------
        message : dict
            The response message
        """
        seq = message.get("request_seq")
        if seq is None:
            self.ctx.debug("Response without request_seq (likely event)")
            return

        # Convert to typed Response. Be defensive for evaluate responses where
        # some adapters omit fields on errors or special cases.
        try:
            cmd = message.get("command")
            body = message.get("body") or {}
            success = bool(message.get("success", True))

            if cmd == CommandType.EVALUATE.value:
                # If evaluate failed or required fields are missing, fall back
                # to generic Response to avoid constructor errors from the
                # typed dataclass expecting present fields.
                if not success or not (
                    isinstance(body, dict)
                    and ("result" in body and "variablesReference" in body)
                ):
                    response = Response.from_dict(message)
                else:
                    response = self._response_registry.create_response(message)
            else:
                response = self._response_registry.create_response(message)
        except Exception as e:
            self.ctx.error(f"Failed to create response object: {e}")
            response = Response.from_dict(message)

        # Complete the pending future (but DON'T remove it yet -
        # wait_for_response will do that)
        async with self.async_lock:
            future = self._pending_requests.get(seq)
            if future:
                if not future.done():
                    future.set_result(response)
            else:
                self.ctx.debug(f"Received response for unknown seq={seq}")

    async def clear_pending_requests(self, error: Exception | None = None) -> None:
        """Clear all pending requests, optionally with an error.

        Parameters
        ----------
        error : Exception, optional
            Error to set on all pending requests
        """
        async with self.async_lock:
            for future in self._pending_requests.values():
                if not future.done():  # Only modify if not already completed
                    if error:
                        future.set_exception(error)
                    else:
                        future.cancel()
            self._pending_requests.clear()

    async def _cleanup_pending_request(self, seq: int) -> None:
        """Clean up a pending request.

        Parameters
        ----------
        seq : int
            Sequence number of request to clean up
        """
        async with self.async_lock:
            self._pending_requests.pop(seq, None)

    async def _should_retry(self, request: Request, is_retry: bool) -> bool:
        """Check if request should be retried.

        Parameters
        ----------
        request : Request
            The request that failed
        is_retry : bool
            Whether this is already a retry

        Returns
        -------
        bool
            True if should retry
        """
        # Never retry if already retried once
        if is_retry or not self.retry_manager:
            return False

        # Do not retry if the session has terminated or the transport is disconnected
        try:
            if self._event_processor and getattr(
                self._event_processor._state,
                "terminated",
                False,
            ):
                self.ctx.debug(
                    f"Not retrying {request.command}: session terminated",
                )
                return False
        except Exception:
            # Best-effort: if state check fails, fall through to other guards
            pass

        if not self.transport.is_connected():
            self.ctx.debug(
                f"Not retrying {request.command}: transport disconnected",
            )
            return False

        retry_config = self.retry_manager.get_retry_config(request.command, None)
        return retry_config is not None

    async def _wait_for_response(
        self,
        future: asyncio.Future[Response],
        request: Request,
        seq: int,
        timeout: float,
    ) -> Response:
        """Wait for and log a response.

        Parameters
        ----------
        future : asyncio.Future[Response]
            Future to wait on
        request : Request
            The request that was sent
        seq : int
            Request sequence number
        timeout : float
            Timeout in seconds

        Returns
        -------
        Response
            The response

        Raises
        ------
        asyncio.TimeoutError
            If timeout occurs
        """
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.CancelledError:
            # Futures may be cancelled during teardown when the transport closes
            # or when a terminated event triggers pending request cleanup. Treat
            # disconnect/terminate requests as successfully acknowledged in that case
            # to avoid bubbling cancellation into test teardown.
            cmd = getattr(request, "command", "")
            if cmd in (CommandType.DISCONNECT.value, CommandType.TERMINATE.value):
                return Response(
                    seq=0,
                    request_seq=seq,
                    success=True,
                    command=cmd,
                    message="Request cancelled during teardown; treating as success",
                )
            raise

        # Log response
        if response.success:
            self.ctx.debug(
                f"Request {seq} ({request.command}) completed successfully",
            )
        else:
            # Failed evaluate/setExpression are expected (undefined vars, syntax errors)
            if request.command in [
                CommandType.EVALUATE.value,
                CommandType.SET_EXPRESSION.value,
            ]:
                self.ctx.debug(
                    f"Request {seq} ({request.command}) failed: {response.message}",
                )
            else:
                self.ctx.warning(
                    f"Request {seq} ({request.command}) failed: {response.message}",
                )

        return response

    async def _send_request_core(
        self,
        request: Request,
        timeout: float = 30.0,
        is_retry: bool = False,
    ) -> Response:
        """Core implementation of request sending with all safety checks.

        This is the main workhorse method that handles:
        - Connection validation
        - Request serialization
        - Retry logic
        - Timeout handling
        - Error recovery

        Parameters
        ----------
        request : Request
            The request to send
        timeout : float
            Response timeout
        is_retry : bool
            Whether this is a retry attempt

        Returns
        -------
        Response
            The response from the adapter

        Raises
        ------
        DebugTimeoutError
            If response not received within timeout
        DebugConnectionError
            If connection issues occur
        """
        if not self.transport.is_connected():
            msg = "Not connected to DAP adapter"
            raise DebugConnectionError(msg)

        # Serialize request sending to prevent race conditions
        async with self._request_semaphore:
            # Get sequence number and update request
            seq = await self.get_next_seq()
            request.seq = seq

            # Create future for response
            future: asyncio.Future[Response] = asyncio.Future()
            async with self.async_lock:
                self._pending_requests[seq] = future

            # Send the request (transport expects Request object, not dict)
            try:
                await self.transport.send_message(request)
                self.ctx.debug(f"Sent request {seq}: {request.command}")
            except Exception as e:
                # Remove from pending if send fails
                await self._cleanup_pending_request(seq)
                msg = f"Failed to send request: {e}"
                raise DebugConnectionError(msg) from e

            # Wait for response
            try:
                return await self._wait_for_response(future, request, seq, timeout)

            except asyncio.TimeoutError as timeout_err:
                # Clean up on timeout
                await self._cleanup_pending_request(seq)

                # Retry if configured
                if await self._should_retry(request, is_retry):
                    self.ctx.info(f"Retrying {request.command} after timeout")
                    return await self._send_request_core(
                        request=request,
                        timeout=timeout,
                        is_retry=True,
                    )

                msg = (
                    f"Timeout waiting for response to {request.command} "
                    f"(seq={seq}) after {timeout}s"
                )
                raise DebugTimeoutError(msg) from timeout_err

            except Exception as e:
                # Clean up on error
                await self._cleanup_pending_request(seq)

                # Check if it's a connection error
                if isinstance(e, DebugConnectionError | DebugSessionLostError):
                    raise

                # Retry if configured
                if await self._should_retry(request, is_retry):
                    self.ctx.info(f"Retrying {request.command} after error: {e}")
                    return await self._send_request_core(
                        request=request,
                        timeout=timeout,
                        is_retry=True,
                    )

                msg = f"Request failed: {e}"
                raise DebugConnectionError(msg) from e

    async def send_request_and_wait_for_event(
        self,
        request: Request,
        event_type: str,
        event_processor,  # Will be EventProcessor type
        timeout: float | None = None,
        event_timeout: float = 5.0,
    ) -> Response:
        """Send a DAP request and wait for a specific event.

        This method is useful for operations like continue/step that need to
        wait for a "stopped" event to know the operation is complete.

        Parameters
        ----------
        request : Request
            The typed DAP request object to send
        event_type : str
            Event type to wait for (e.g., "stopped", "terminated")
        event_processor : EventProcessor
            Event processor to check for events
        timeout : float, optional
            Response timeout for the request (defaults to 30 seconds)
        event_timeout : float
            Timeout for waiting for the event (defaults to 5 seconds)

        Returns
        -------
        Response
            The typed DAP response

        Raises
        ------
        DebugTimeoutError
            If response or event not received within timeout
        DebugConnectionError
            If not connected or connection lost
        """
        # Clear any previous event state for this type before sending request
        event_processor._event_received[event_type].clear()

        # Send the request
        response = await self.send_request(request, timeout)

        # Only wait for event if the request was successful
        if response.success:
            # Wait for the expected event
            try:
                await asyncio.wait_for(
                    event_processor._event_received[event_type].wait(),
                    timeout=event_timeout,
                )
            except asyncio.TimeoutError:
                self.ctx.warning(
                    f"Event '{event_type}' not received "
                    f"within {event_timeout}s after {request.command}",
                )

        return response

    async def _prepare_execution_request(
        self,
        request: Request,
    ) -> tuple[int, asyncio.Future, asyncio.Future | None, asyncio.Future | None]:
        """Prepare execution request for sending.

        Parameters
        ----------
        request : Request
            The request to prepare

        Returns
        -------
        tuple[int, asyncio.Future, asyncio.Future | None, asyncio.Future | None]
            Sequence number, response future, optional terminated future, optional stopped future
        """
        # Get sequence number and update request
        seq = await self.get_next_seq()
        request.seq = seq

        # Create future for response
        response_future: asyncio.Future[Response] = asyncio.Future()
        async with self.async_lock:
            self._pending_requests[seq] = response_future

        # Register listeners for terminated and stopped events if we have event processor
        terminated_future = None
        stopped_future = None
        if self._event_processor:
            self.ctx.debug(
                f"Registering stopped/terminated listeners for continue request (seq={seq})",
            )
            terminated_future = self._event_processor.register_terminated_listener()
            stopped_future = self._event_processor.register_stopped_listener()
            self.ctx.debug(
                f"Listeners registered: stopped={stopped_future is not None}, "
                f"terminated={terminated_future is not None}",
            )
        else:
            self.ctx.warning(
                f"No event processor available for execution request (seq={seq}) - "
                f"stopped/terminated events will not be handled!",
            )

        return seq, response_future, terminated_future, stopped_future

    async def _send_execution_request_message(
        self,
        request: Request,
        seq: int,
    ) -> None:
        """Send the execution request message.

        Parameters
        ----------
        request : Request
            The request to send
        seq : int
            Sequence number

        Raises
        ------
        DebugConnectionError
            If send fails
        """
        try:
            await self.transport.send_message(request)
            self.ctx.debug(f"Sent execution request {seq}: {request.command}")
        except Exception as e:
            # Remove from pending if send fails
            async with self.async_lock:
                self._pending_requests.pop(seq, None)
            msg = f"Failed to send request: {e}"
            raise DebugConnectionError(msg) from e

    async def _wait_for_execution_response(
        self,
        response_future: asyncio.Future,
        terminated_future: asyncio.Future | None,
        stopped_future: asyncio.Future | None,
        request: Request,
        seq: int,
        timeout: float,
    ) -> Response:
        """Wait for execution response, termination, or stopped event.

        Parameters
        ----------
        response_future : asyncio.Future
            Future for the response
        terminated_future : asyncio.Future | None
            Optional future for termination event
        stopped_future : asyncio.Future | None
            Optional future for stopped event
        request : Request
            Original request
        seq : int
            Sequence number
        timeout : float
            Timeout in seconds

        Returns
        -------
        Response
            The response or synthetic response for terminated/stopped

        Raises
        ------
        DebugTimeoutError
            If timeout occurs
        """
        # NOTE: For execution requests (continue, next, stepIn, etc.), we ONLY wait
        # for stopped or terminated events, NOT the response. The DAP spec doesn't
        # guarantee response timing for continue (unlike step commands), and adapters
        # may delay/never send the response if execution stops immediately at another
        # breakpoint. The response itself is meaningless - we care about execution state.
        futures = []
        if terminated_future:
            futures.append(terminated_future)
        if stopped_future:
            futures.append(stopped_future)

        # Fallback: if no event futures registered, wait for response
        # (shouldn't happen for execution requests, but provides safety net)
        if not futures:
            futures.append(response_future)

        self.ctx.debug(
            f"Waiting for execution response (seq={seq}): "
            f"{len(futures)} futures "
            f"({'terminated' if terminated_future else 'no-terminated'} + "
            f"{'stopped' if stopped_future else 'no-stopped'}"
            f"{' + response-fallback' if not terminated_future and not stopped_future else ''}), "
            f"timeout={timeout}s",
        )

        # Wait for EITHER response OR terminated event OR stopped event
        done, pending = await asyncio.wait(
            futures,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        self.ctx.debug(
            f"Wait completed (seq={seq}): {len(done)} completed, {len(pending)} pending",
        )

        # Cancel pending futures
        for future in pending:
            future.cancel()

        # Handle the result
        if not done:
            msg = (
                f"Timeout waiting for response to {request.command} "
                f"(seq={seq}) after {timeout}s"
            )
            raise DebugTimeoutError(msg)

        completed = done.pop()

        # Clean up the request from pending
        async with self.async_lock:
            self._pending_requests.pop(seq, None)

        if completed == response_future:
            # Got the actual response
            response = completed.result()
            if response.success:
                self.ctx.debug(
                    f"Execution request {seq} ({request.command}) "
                    f"completed successfully",
                )
            else:
                self.ctx.warning(
                    f"Execution request {seq} ({request.command}) "
                    f"failed: {response.message}",
                )
            return response

        if completed == terminated_future:
            # Terminated event occurred - create synthetic success response
            self.ctx.debug(
                f"Execution request {seq} ({request.command}) terminated - "
                f"creating synthetic response",
            )
            return self._create_terminated_response(request)

        # Stopped event occurred - create synthetic success response
        self.ctx.debug(
            f"Execution request {seq} ({request.command}) stopped at breakpoint - "
            f"creating synthetic response",
        )
        return self._create_stopped_response(request)

    async def _handle_execution_error(
        self,
        e: Exception,
        seq: int,
        request: Request,
        timeout: float,
    ) -> None:
        """Handle errors during execution request.

        Parameters
        ----------
        e : Exception
            The exception that occurred
        seq : int
            Sequence number
        request : Request
            The request that failed
        timeout : float
            The timeout value

        Raises
        ------
        DebugTimeoutError | DebugConnectionError | DebugSessionLostError
            Re-raises appropriate error
        """
        # Clean up on error
        async with self.async_lock:
            self._pending_requests.pop(seq, None)

        if isinstance(e, asyncio.TimeoutError):
            msg = (
                f"Timeout waiting for response to {request.command} "
                f"(seq={seq}) after {timeout}s"
            )
            raise DebugTimeoutError(msg) from e

        if isinstance(e, DebugConnectionError | DebugSessionLostError):
            raise

        msg = f"Execution request failed: {e}"
        raise DebugConnectionError(msg) from e

    async def send_execution_request(
        self,
        request: Request,
        timeout: float = 30.0,
    ) -> Response:
        """Send an execution request with termination-aware handling.

        For execution commands (continue, step, etc.), a terminated event
        can serve as an implicit successful response if the program ends.

        Parameters
        ----------
        request : Request
            The execution request to send
        timeout : float
            Maximum time to wait for response or termination

        Returns
        -------
        Response
            Either the actual response or a synthetic success response if terminated

        Raises
        ------
        DebugTimeoutError
            If neither response nor termination occurs within timeout
        """
        if not self.transport.is_connected():
            msg = "Not connected to DAP adapter"
            raise DebugConnectionError(msg)

        # Special-case: 'continue' should not block waiting for a response.
        # Many adapters may emit a stopped event immediately for consecutive breakpoints
        # but defer the actual continue response until later. Waiting here can deadlock
        # the flow and cause a 30s timeout. We send and return immediately; callers
        # (e.g., ExecutionOperations.continue_) are responsible for waiting for
        # stopped/terminated events to reflect final state.
        try:
            from aidb.dap.protocol.requests import ContinueRequest  # type: ignore
        except Exception:  # pragma: no cover - defensive import guard
            ContinueRequest = None  # type: ignore

        if (ContinueRequest is not None and isinstance(request, ContinueRequest)) or (
            getattr(request, "command", "") == "continue"
        ):
            # Assign sequence and send without registering a pending future
            seq = await self.get_next_seq()
            request.seq = seq
            await self._send_execution_request_message(request, seq)

            # Return a synthetic immediate success response; the caller will
            # perform event-based waiting for the real stop/terminate outcome.
            return Response(
                seq=0,
                request_seq=seq,
                success=True,
                command=request.command,
                message="Continue sent",
            )

        # Serialize request sending to prevent race conditions
        async with self._request_semaphore:
            # Prepare request
            (
                seq,
                response_future,
                terminated_future,
                stopped_future,
            ) = await self._prepare_execution_request(request)

            # Send request
            await self._send_execution_request_message(request, seq)

            # Wait for response
            try:
                return await self._wait_for_execution_response(
                    response_future,
                    terminated_future,
                    stopped_future,
                    request,
                    seq,
                    timeout,
                )
            except Exception as e:
                await self._handle_execution_error(e, seq, request, timeout)

    def _create_terminated_response(self, request: Request) -> Response:
        """Create a synthetic success response for terminated session.

        Parameters
        ----------
        request : Request
            The original request

        Returns
        -------
        Response
            A synthetic success response appropriate for the request type
        """
        # Create synthetic response using base Response class
        return Response(
            seq=0,  # Synthetic response sequence
            request_seq=request.seq,
            success=True,
            command=request.command,
            message="Session terminated",
        )

    def _create_stopped_response(self, request: Request) -> Response:
        """Create a synthetic success response for stopped event.

        Parameters
        ----------
        request : Request
            The original request

        Returns
        -------
        Response
            A synthetic success response for stopped event
        """
        # Create synthetic response using base Response class
        return Response(
            seq=0,  # Synthetic response sequence
            request_seq=request.seq,
            success=True,
            command=request.command,
            message="Execution stopped",
        )

    def initialize_sequence(self) -> None:
        """Initialize sequence numbering.

        Called during connection setup to ensure sequence starts at 1.
        """
        if self._seq == 0:
            self._seq = 1

    async def clear_all_pending_requests(self) -> None:
        """Clear all pending requests and cancel their futures.

        Used during disconnect to clean up outstanding requests.
        """
        async with self.async_lock:
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()

    async def get_pending_request_count(self) -> int:
        """Get the number of pending requests.

        Returns
        -------
        int
            Number of requests awaiting responses
        """
        async with self.async_lock:
            return len(self._pending_requests)

    async def get_current_sequence(self) -> int:
        """Get the current sequence number.

        Returns
        -------
        int
            Current sequence number
        """
        async with self.async_lock:
            return self._seq
