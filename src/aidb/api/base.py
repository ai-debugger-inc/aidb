"""Base class for API operations."""

from typing import TYPE_CHECKING, Optional

from aidb.patterns import Obj
from aidb.session import Session

if TYPE_CHECKING:
    from aidb.common import AidbContext


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
