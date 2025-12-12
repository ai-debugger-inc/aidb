"""Event subscription management utilities for debug sessions."""

from typing import TYPE_CHECKING, cast

from aidb.dap.client.constants import EventType
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.dap.client import DAPClient
    from aidb.interfaces.context import IContext
    from aidb.session import Session


class EventSubscriptionManager(Obj):
    """Manage DAP event subscriptions for debug sessions.

    This class handles subscribing to and managing DAP events including:
    - Breakpoint verification events
    - LoadedSource events for proactive rebinding
    - Terminated events for cache cleanup

    Parameters
    ----------
    session : Session
        The session to manage event subscriptions for
    ctx : IContext, optional
        Application context for logging
    """

    def __init__(
        self,
        session: "Session",
        ctx: "IContext | None" = None,
    ) -> None:
        super().__init__(ctx=ctx)
        self.session = session

    async def setup_breakpoint_event_subscription(self) -> None:
        """Subscribe to breakpoint events for state synchronization.

        This sets up the critical bridge that syncs asynchronous breakpoint
        verification events from the DAP adapter back to session state. Without
        this, breakpoints remain unverified in session state even after the
        adapter confirms verification.

        Sets up subscriptions for:
        - Breakpoint events: Sync breakpoint verification state
        - LoadedSource events: Proactive rebinding when sources load
        - Terminated events: Clear breakpoint cache on session end
        """
        session = cast("Session", self.session)

        # Idempotence check: skip if already subscribed
        if hasattr(session, "_event_subscriptions") and session._event_subscriptions:
            self.ctx.debug(
                "Breakpoint event subscriptions already set up, skipping",
            )
            return

        dap = getattr(session, "dap", None)
        if not dap or not hasattr(dap, "events"):
            self.ctx.debug(
                "Cannot subscribe to breakpoint events: "
                "DAP or events API not available",
            )
            return

        # Initialize tracking dict if not present
        if not hasattr(session, "_event_subscriptions"):
            session._event_subscriptions = {}

        try:
            # Subscribe to breakpoint events
            await self._subscribe_to_breakpoint_events(session, dap)

            # Subscribe to loadedSource events
            await self._subscribe_to_loaded_source_events(session, dap)

            # Subscribe to terminated events
            await self._subscribe_to_terminated_events(session, dap)

        except Exception as e:
            # Non-fatal: breakpoint sync is important but not critical
            self.ctx.warning(
                f"Failed to subscribe to breakpoint events: {e}. "
                "Breakpoint verification state may not update correctly.",
            )

    async def _subscribe_to_breakpoint_events(
        self,
        session: "Session",
        dap: "DAPClient",
    ) -> None:
        """Subscribe to breakpoint verification events.

        Parameters
        ----------
        session : Session
            The session to subscribe for
        dap : DAPClient
            The DAP client with events API
        """
        subscription_id = await dap.events.subscribe_to_event(
            EventType.BREAKPOINT.value,
            session._on_breakpoint_event,
        )
        session._event_subscriptions[EventType.BREAKPOINT.value] = subscription_id
        self.ctx.debug(
            f"Subscribed to breakpoint events for state sync "
            f"(subscription_id={subscription_id})",
        )

    async def _subscribe_to_loaded_source_events(
        self,
        session: "Session",
        dap: "DAPClient",
    ) -> None:
        """Subscribe to loadedSource events for proactive rebinding.

        This accelerates breakpoint verification by re-sending setBreakpoints
        when sources load, rather than waiting for async verification.

        Parameters
        ----------
        session : Session
            The session to subscribe for
        dap : DAPClient
            The DAP client with events API
        """
        loaded_source_key = EventType.LOADED_SOURCE.value
        loadedsource_sub_id = await dap.events.subscribe_to_event(
            loaded_source_key,
            session._on_loaded_source_event,
        )
        session._event_subscriptions[loaded_source_key] = loadedsource_sub_id
        self.ctx.debug(
            f"Subscribed to loadedSource events for proactive rebinding "
            f"(subscription_id={loadedsource_sub_id})",
        )

    async def _subscribe_to_terminated_events(
        self,
        session: "Session",
        dap: "DAPClient",
    ) -> None:
        """Subscribe to terminated events for cache cleanup.

        This prevents returning stale breakpoint data after session ends.

        Parameters
        ----------
        session : Session
            The session to subscribe for
        dap : DAPClient
            The DAP client with events API
        """
        terminated_sub_id = await dap.events.subscribe_to_event(
            EventType.TERMINATED.value,
            session._on_terminated_event,
        )
        session._event_subscriptions[EventType.TERMINATED.value] = terminated_sub_id
        self.ctx.debug(
            f"Subscribed to terminated event for cache cleanup "
            f"(subscription_id={terminated_sub_id})",
        )
