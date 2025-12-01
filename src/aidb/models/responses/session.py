"""Session-related response models."""

from dataclasses import dataclass
from typing import Union

from aidb.dap.protocol.responses import (
    AttachResponse,
    InitializeResponse,
    LaunchResponse,
)

from ..base import OperationResponse
from ..entities.session import ExecutionState, SessionInfo, SessionStatus


@dataclass(frozen=True)
class StartResponse(OperationResponse):
    """Response from starting a debug session."""

    success: bool = False
    session_info: SessionInfo | None = None
    message: str | None = None
    error_code: str | None = None

    @classmethod
    def from_dap(
        cls,
        dap_response: Union["InitializeResponse", "LaunchResponse", "AttachResponse"],
        session_id: str,
        target: str,
        language: str,
    ) -> "StartResponse":
        """Create StartResponse from DAP initialization response.

        Parameters
        ----------
        dap_response : Union[InitializeResponse, LaunchResponse, AttachResponse]
            The DAP initialization response to convert
        session_id : str
            The session ID
        target : str
            The debug target
        language : str
            The programming language

        Returns
        -------
        StartResponse
            The converted start response
        """
        status = cls._determine_session_status(dap_response)
        pid = cls._extract_process_id(dap_response)
        session_info = SessionInfo(
            id=session_id,
            status=status,
            target=target,
            language=language,
            pid=pid,
        )
        success, message, error_code = cls._extract_response_fields(dap_response)

        return cls(
            session_info=session_info,
            success=success,
            message=message,
            error_code=error_code,
        )

    @staticmethod
    def _determine_session_status(
        dap_response: Union["InitializeResponse", "LaunchResponse", "AttachResponse"],
    ) -> SessionStatus:
        """Determine session status from DAP response type."""
        if isinstance(dap_response, InitializeResponse):
            return SessionStatus.INITIALIZING
        if isinstance(dap_response, LaunchResponse | AttachResponse):
            return SessionStatus.RUNNING
        return SessionStatus.INITIALIZING

    @staticmethod
    def _extract_process_id(
        dap_response: Union["InitializeResponse", "LaunchResponse", "AttachResponse"],
    ) -> int | None:
        """Extract process ID from DAP response if available."""
        if (
            hasattr(dap_response, "body")
            and dap_response.body
            and hasattr(dap_response.body, "processId")
        ):
            return dap_response.body.processId
        return None

    @staticmethod
    def _extract_response_fields(
        dap_response: Union["InitializeResponse", "LaunchResponse", "AttachResponse"],
    ) -> tuple[bool, str | None, str | None]:
        """Extract success, message, and error_code from DAP response."""
        return OperationResponse.extract_response_fields(dap_response)


@dataclass(frozen=True)
class StatusResponse(OperationResponse):
    """Response from querying debug session status."""

    session_info: SessionInfo | None = None
    execution_state: ExecutionState | None = None
