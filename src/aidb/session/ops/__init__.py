"""Session debug operations subpackage."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session

from .initialization import InitializationMixin
from .introspection_mixin import IntrospectionMixin
from .orchestration_mixin import OrchestrationMixin


class SessionDebugOperations(
    OrchestrationMixin,
    IntrospectionMixin,
    InitializationMixin,
):
    """Complete debugging operations interface.

    Combines all operation mixins into a single class that provides the same
    interface as the original monolithic implementation.

    Mixins provide:
        - OrchestrationMixin: Execution control (breakpoints, stepping,
          start/stop) + BaseOperations
        - IntrospectionMixin: State inspection (variables, evaluation, call
          stack) + BaseOperations
        - InitializationMixin: DAP sequence handling + BaseOperations

    All mixins inherit from BaseOperations which provides shared state and
    utilities (thread/frame tracking, response mappers, session reference).
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize debugger operations with all mixins.

        Parameters
        ----------
        session : Session
            The session that owns this debugger operations
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        # Initialize the base operations (which all mixins depend on)
        super().__init__(session, ctx)


__all__ = [
    "SessionDebugOperations",
    "OrchestrationMixin",
    "IntrospectionMixin",
    "InitializationMixin",
]
