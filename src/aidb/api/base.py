"""Base class for API operations."""

from typing import TYPE_CHECKING, Optional

from aidb.common.validation import (
    validate_frame_id,
    validate_memory_reference,
    validate_port,
    validate_thread_id,
    validate_timeout,
)
from aidb.patterns import Obj
from aidb.session import Session

from .constants import DEFAULT_FRAME_ID, DEFAULT_THREAD_ID

if TYPE_CHECKING:
    from aidb.common import AidbContext


class ValidationMixin:
    """Mixin for common validation patterns across API operations.

    This class provides reusable validation methods for common parameters like
    thread IDs, frame IDs, and other debugging-related values. These methods
    are used throughout the API layer including in dap_utils.py.

    Note: This mixin delegates to the shared validation module to avoid
    duplication with session layer validation.
    """

    @staticmethod
    def validate_thread_id(thread_id: int | None) -> int:
        """Validate and resolve thread ID.

        Parameters
        ----------
        thread_id : int, optional
            AidbThread ID to validate

        Returns
        -------
        int
            Validated thread ID with default if None

        Raises
        ------
        ValueError
            If thread ID is invalid
        """
        return validate_thread_id(thread_id, default=DEFAULT_THREAD_ID)

    @staticmethod
    def validate_frame_id(frame_id: int | None) -> int:
        """Validate and resolve frame ID.

        Parameters
        ----------
        frame_id : int, optional
            Frame ID to validate

        Returns
        -------
        int
            Validated frame ID with default if None

        Raises
        ------
        ValueError
            If frame ID is invalid
        """
        return validate_frame_id(frame_id, default=DEFAULT_FRAME_ID)

    @staticmethod
    def validate_memory_reference(memory_ref: str) -> str:
        """Validate memory reference string.

        Parameters
        ----------
        memory_ref : str
            Memory reference to validate

        Returns
        -------
        str
            Validated memory reference

        Raises
        ------
        ValueError
            If memory reference is invalid
        """
        return validate_memory_reference(memory_ref)

    @staticmethod
    def validate_port(port: int | None) -> int | None:
        """Validate network port number.

        Parameters
        ----------
        port : int, optional
            Port number to validate

        Returns
        -------
        int, optional
            Validated port number

        Raises
        ------
        ValueError
            If port is out of valid range
        """
        return validate_port(port)

    @staticmethod
    def validate_timeout(timeout: int) -> int:
        """Validate timeout value.

        Parameters
        ----------
        timeout : int
            Timeout in milliseconds

        Returns
        -------
        int
            Validated timeout

        Raises
        ------
        ValueError
            If timeout is invalid
        """
        return validate_timeout(timeout)


class APIOperationBase(Obj):
    """Base class for API operation groups.

    Provides common session management functionality for all API operation classes,
    eliminating duplication and ensuring consistent behavior.
    """

    def __init__(self, session: Session, ctx: Optional["AidbContext"] = None):
        """Initialize the API operation base.

        Parameters
        ----------
        session : Session
            Session to use for operations
        ctx : AidbContext, optional
            Application context
        """
        super().__init__(ctx)
        self._root_session = session

    @property
    def session(self) -> Session:
        """Get the active session for operations.

        For languages with child sessions (e.g., JavaScript), returns the active
        child session if it exists. This ensures that validation checks and
        operations use the correct session state.

        This property delegates to the SessionRegistry's resolve_active_session()
        method, which is the single authoritative implementation for session
        resolution.

        Returns
        -------
        Session
            The active session (child if exists, otherwise root)
        """
        return self._root_session.registry.resolve_active_session(self._root_session)
