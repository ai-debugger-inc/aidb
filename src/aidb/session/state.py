"""Session state management component."""

from typing import TYPE_CHECKING, Optional

from aidb.models import SessionStatus, StartRequestType
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.client import DAPClient
    from aidb.interfaces import IContext
    from aidb.session import Session


class SessionState(Obj):
    """Manages session state and status tracking.

    This component handles:
    - Status computation based on DAP state
    - Error tracking
    - Initialization state
    - Status queries
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None):
        """Initialize session state manager.

        Parameters
        ----------
        session : Session
            The session this state manager belongs to
        ctx : IContext, optional
            Application context for logging
        """
        super().__init__(ctx)
        self.session = session
        self._error: Exception | None = None
        self._initialized = False

    def set_error(self, error: Exception) -> None:
        """Set error state for the session.

        Parameters
        ----------
        error : Exception
            The error that occurred
        """
        self._error = error

    def clear_error(self) -> None:
        """Clear error state."""
        self._error = None

    def set_initialized(self, initialized: bool) -> None:
        """Set initialization state.

        Parameters
        ----------
        initialized : bool
            Whether the session is initialized
        """
        self._initialized = initialized

    def is_initialized(self) -> bool:
        """Check if session is initialized.

        Returns
        -------
        bool
            True if session is initialized
        """
        return self._initialized

    def has_error(self) -> bool:
        """Check if session has an error.

        Returns
        -------
        bool
            True if session has an error
        """
        return self._error is not None

    def get_error(self) -> Exception | None:
        """Get the current error if any.

        Returns
        -------
        Optional[Exception]
            The error or None
        """
        return self._error

    def get_status(self) -> SessionStatus:
        """Get the current session status.

        Computes status based on:
        - Error state
        - Initialization state
        - DAP connection state
        - Adapter process state

        Returns
        -------
        SessionStatus
            The current session status
        """
        # Error state takes precedence
        if self._error:
            return SessionStatus.ERROR

        # Not yet initialized
        if not self._initialized:
            return SessionStatus.INITIALIZED

        # Try to get status from DAP if available
        if hasattr(self.session, "connector") and self.session.connector._dap:
            try:
                dap: DAPClient = self.session.connector._dap

                # For child sessions, prioritize stopped state over connection checks
                # Child sessions share parent's adapter but have their own DAP client
                is_child = hasattr(self.session, "is_child") and self.session.is_child

                if is_child:
                    # Child session: Check stopped state first
                    dap_is_stopped = hasattr(dap, "is_stopped") and dap.is_stopped
                    dap_is_terminated = (
                        hasattr(dap, "is_terminated") and dap.is_terminated
                    )

                    if dap_is_stopped:
                        return SessionStatus.PAUSED

                    # Then check if explicitly terminated
                    if dap_is_terminated:
                        return SessionStatus.TERMINATED

                    # Child sessions are running if not stopped/terminated
                    return SessionStatus.RUNNING

                # Parent/standalone session: Prioritize DAP stopped state over health
                # This ensures sessions stopped at breakpoints are correctly
                # reported as PAUSED even if adapter health checks fail
                # (e.g., Java's dummy process pattern)
                dap_is_stopped = dap.is_stopped if hasattr(dap, "is_stopped") else None
                dap_is_terminated = (
                    dap.is_terminated if hasattr(dap, "is_terminated") else None
                )
                dap_is_connected = (
                    dap.is_connected if hasattr(dap, "is_connected") else None
                )

                # Check if stopped/paused - prioritize over adapter health checks
                # If DAP reports stopped, session is paused regardless of health
                if dap_is_stopped:
                    return SessionStatus.PAUSED

                # Now check health only if not stopped
                # Check if the session has terminated via DAP
                if dap_is_terminated:
                    return SessionStatus.TERMINATED

                # Check if we're connected to DAP
                if dap_is_connected is not None and not dap_is_connected:
                    return SessionStatus.TERMINATED

                # Check if the adapter process is still running
                # Note: Some adapters (e.g., Java with LSP-DAP bridge) may use
                # dummy processes, so this is less reliable than DAP state
                #
                # Skip this check for remote attach sessions - they connect to
                # an external process and don't have a local adapter process
                is_remote_attach = (
                    hasattr(self.session, "start_request_type")
                    and self.session.start_request_type == StartRequestType.ATTACH
                    and hasattr(self.session, "_attach_params")
                    and self.session._attach_params
                    and self.session._attach_params.get("host")
                )
                if not is_remote_attach:
                    adapter_is_alive = (
                        self.session.adapter.is_alive
                        if hasattr(self.session, "adapter")
                        and self.session.adapter
                        and hasattr(self.session.adapter, "is_alive")
                        else None
                    )
                    if adapter_is_alive is not None and not adapter_is_alive:
                        return SessionStatus.TERMINATED

                # If we have a valid DAP connection and not stopped, we're running
                return SessionStatus.RUNNING

            except Exception as e:
                self.session.ctx.debug(f"Error checking session status: {e}")
                # Fall back to basic status

        # Default status based on initialization state
        if self._initialized:
            return SessionStatus.RUNNING
        return SessionStatus.INITIALIZED

    def is_paused(self) -> bool:
        """Check if the session is currently paused/stopped.

        Returns
        -------
        bool
            True if the session is paused at a breakpoint or stop point
        """
        return self.get_status() == SessionStatus.PAUSED

    def is_running(self) -> bool:
        """Check if the session is currently running.

        Returns
        -------
        bool
            True if the session is running
        """
        return self.get_status() == SessionStatus.RUNNING

    def is_terminated(self) -> bool:
        """Check if the session has terminated.

        Returns
        -------
        bool
            True if the session has terminated
        """
        return self.get_status() == SessionStatus.TERMINATED
