"""AidbBreakpoint management for debug sessions."""

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from aidb_common.path import normalize_path

if TYPE_CHECKING:
    from aidb.dap.protocol.base import Event
    from aidb.dap.protocol.events import BreakpointEvent, LoadedSourceEvent
    from aidb.interfaces import IContext
from aidb.dap.protocol.bodies import SetBreakpointsArguments
from aidb.dap.protocol.requests import SetBreakpointsRequest
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.models import AidbBreakpoint, AidbBreakpointsResponse, BreakpointState


class SessionBreakpointsMixin:
    """Mixin for breakpoint management operations."""

    # Type hints for attributes from main Session class
    ctx: "IContext"
    _breakpoint_store: dict[int, AidbBreakpoint]
    _breakpoint_store_lock: asyncio.Lock
    _breakpoint_update_tasks: set[asyncio.Task]
    breakpoints: list[AidbBreakpoint]
    dap: Any
    adapter: Any
    debug: Any
    _last_rebind_times: dict[str, float]

    @property
    def current_breakpoints(self) -> AidbBreakpointsResponse | None:
        """Get current breakpoints from the internal store.

        Returns a snapshot copy of the breakpoint store to avoid race conditions
        with concurrent modifications from event handlers.

        Returns
        -------
        Optional[AidbBreakpointsResponse]
            Current breakpoints or None if none are set
        """
        if not self._breakpoint_store:
            return None
        # Return a copy to avoid race conditions during iteration
        # dict.copy() is atomic in CPython, writes are protected by lock
        return AidbBreakpointsResponse(breakpoints=self._breakpoint_store.copy())

    @property
    def breakpoint_count(self) -> int:
        """Get the number of breakpoints currently in the store.

        Returns
        -------
        int
            Number of breakpoints in the internal store
        """
        return len(self._breakpoint_store)

    async def _update_breakpoints_from_response(
        self,
        source_path: str,
        response_breakpoints: list[AidbBreakpoint],
    ) -> None:
        """Update internal breakpoint store from a SetBreakpoints response.

        Protected by _breakpoint_store_lock to prevent race conditions with
        concurrent event handlers.

        Parameters
        ----------
        source_path : str
            Path to the source file
        response_breakpoints : List[AidbBreakpoint]
            Breakpoints returned from the debug adapter
        """
        async with self._breakpoint_store_lock:
            self.ctx.debug(
                f"_update_breakpoints_from_response: Updating {source_path} with "
                f"{len(response_breakpoints)} breakpoint(s)",
            )
            self.ctx.debug(
                f"_update_breakpoints_from_response: Store before update has "
                f"{len(self._breakpoint_store)} breakpoint(s): "
                f"{list(self._breakpoint_store.keys())}",
            )

            # Clear existing breakpoints for this source
            self._clear_breakpoints_for_source(source_path)
            self.ctx.debug(
                f"_update_breakpoints_from_response: After clearing {source_path}, "
                f"store has {len(self._breakpoint_store)} breakpoint(s)",
            )

            # Add new breakpoints to the store
            for bp in response_breakpoints:
                if bp.id is not None:
                    # If breakpoint source_path is empty, use provided source_path
                    # Handles DAP adapters without source in responses
                    if not bp.source_path:
                        bp = replace(bp, source_path=source_path)
                        self.ctx.debug(
                            f"_update_breakpoints_from_response: "
                            f"Fixed empty source_path for bp.id={bp.id}, "
                            f"using {source_path}",
                        )

                    self._breakpoint_store[bp.id] = bp
                    self.ctx.debug(
                        f"_update_breakpoints_from_response: Added breakpoint "
                        f"id={bp.id} at {bp.source_path}:{bp.line}",
                    )
                else:
                    self.ctx.warning(
                        f"_update_breakpoints_from_response: Skipping breakpoint with "
                        f"None id at {bp.source_path}:{bp.line}",
                    )

            self.ctx.debug(
                f"_update_breakpoints_from_response: Store after update has "
                f"{len(self._breakpoint_store)} breakpoint(s): "
                f"{list(self._breakpoint_store.keys())}",
            )

    def _clear_breakpoints_for_source(self, source_path: str) -> None:
        """Clear all breakpoints for a specific source file.

        Parameters
        ----------
        source_path : str
            Path to the source file
        """
        normalized = normalize_path(source_path)
        to_remove = [
            bp_id
            for bp_id, bp in self._breakpoint_store.items()
            if normalize_path(bp.source_path) == normalized
        ]
        for bp_id in to_remove:
            del self._breakpoint_store[bp_id]

    def _on_breakpoint_event(self, event: "Event") -> None:
        """Sync breakpoint state from DAP breakpoint events.

        When the adapter sends breakpoint events (reason='changed'), update
        our internal store with the latest verification status. This is the
        critical bridge that synchronizes asynchronous breakpoint verification
        from the adapter back to session state.

        Event handlers must be synchronous, so we schedule the lock-protected
        update as a background task.

        Parameters
        ----------
        event : Event
            The DAP breakpoint event
        """
        breakpoint_event = cast("BreakpointEvent", event)
        if not breakpoint_event.body:
            return

        reason = breakpoint_event.body.reason
        bp_from_adapter = breakpoint_event.body.breakpoint

        bp_verified = (
            bp_from_adapter.verified if hasattr(bp_from_adapter, "verified") else "N/A"
        )
        self.ctx.debug(
            f"_on_breakpoint_event: reason={reason}, "
            f"id={bp_from_adapter.id if bp_from_adapter.id else 'None'}, "
            f"verified={bp_verified}",
        )

        # Only sync on 'changed' events (verification updates)
        # Also handle 'new' in case adapter sends verification via new event
        if reason in ("changed", "new"):
            # Schedule lock-protected update as background task
            import asyncio

            task = asyncio.create_task(self._update_breakpoint_from_event(event))
            self._breakpoint_update_tasks.add(task)
            task.add_done_callback(lambda t: self._breakpoint_update_tasks.discard(t))

    async def _update_breakpoint_from_event(self, event: "Event") -> None:
        """Update breakpoint store from event (lock-protected).

        This is called as a background task from _on_breakpoint_event to ensure
        the event handler remains synchronous while the store update is protected
        by the async lock.

        Parameters
        ----------
        event : Event
            The DAP breakpoint event
        """
        breakpoint_event = cast("BreakpointEvent", event)
        bp_from_adapter = breakpoint_event.body.breakpoint

        async with self._breakpoint_store_lock:
            # Primary path: ID-based matching
            if bp_from_adapter.id and bp_from_adapter.id in self._breakpoint_store:
                stored_bp = self._breakpoint_store[bp_from_adapter.id]

                # Create updated immutable breakpoint with new verification state
                updated_bp = replace(
                    stored_bp,
                    verified=(
                        bp_from_adapter.verified
                        if hasattr(bp_from_adapter, "verified")
                        else stored_bp.verified
                    ),
                    state=(
                        BreakpointState.VERIFIED
                        if (
                            hasattr(bp_from_adapter, "verified")
                            and bp_from_adapter.verified
                        )
                        else BreakpointState.PENDING
                    ),
                    message=(
                        bp_from_adapter.message
                        if (
                            hasattr(bp_from_adapter, "message")
                            and bp_from_adapter.message
                        )
                        else stored_bp.message
                    ),
                )

                self._breakpoint_store[bp_from_adapter.id] = updated_bp

                self.ctx.debug(
                    f"Synced breakpoint {bp_from_adapter.id} verification: "
                    f"verified={updated_bp.verified}, "
                    f"state={updated_bp.state.name}",
                )

            # Fallback path: location-based matching when ID is missing
            elif (
                not bp_from_adapter.id
                and hasattr(bp_from_adapter, "source")
                and bp_from_adapter.source
                and hasattr(bp_from_adapter.source, "path")
                and bp_from_adapter.source.path
                and hasattr(bp_from_adapter, "line")
                and bp_from_adapter.line
            ):
                source_path = normalize_path(bp_from_adapter.source.path)
                line = bp_from_adapter.line
                column = (
                    bp_from_adapter.column
                    if hasattr(bp_from_adapter, "column")
                    else None
                )

                self.ctx.debug(
                    f"Breakpoint event has no ID, using fallback matching: "
                    f"{source_path}:{line}:{column}",
                )

                # Find matching breakpoint in store by location
                matched = False
                for bp_id, stored_bp in self._breakpoint_store.items():
                    if (
                        normalize_path(stored_bp.source_path) == source_path
                        and stored_bp.line == line
                        and (column is None or stored_bp.column == column)
                    ):
                        # Update this breakpoint
                        updated_bp = replace(
                            stored_bp,
                            verified=(
                                bp_from_adapter.verified
                                if hasattr(bp_from_adapter, "verified")
                                else stored_bp.verified
                            ),
                            state=(
                                BreakpointState.VERIFIED
                                if (
                                    hasattr(bp_from_adapter, "verified")
                                    and bp_from_adapter.verified
                                )
                                else BreakpointState.PENDING
                            ),
                            message=(
                                bp_from_adapter.message
                                if (
                                    hasattr(bp_from_adapter, "message")
                                    and bp_from_adapter.message
                                )
                                else stored_bp.message
                            ),
                        )
                        self._breakpoint_store[bp_id] = updated_bp
                        self.ctx.debug(
                            f"Synced breakpoint {bp_id} (fallback match): "
                            f"verified={updated_bp.verified}, "
                            f"state={updated_bp.state.name}",
                        )
                        matched = True
                        break

                if not matched:
                    self.ctx.debug(
                        f"No breakpoint found matching location "
                        f"{source_path}:{line} "
                        f"(store has: {list(self._breakpoint_store.keys())})",
                    )

            elif bp_from_adapter.id:
                self.ctx.debug(
                    f"Received breakpoint event for unknown ID "
                    f"{bp_from_adapter.id} "
                    f"(store has: {list(self._breakpoint_store.keys())})",
                )

    def _on_loaded_source_event(self, event: "Event") -> None:
        """Handle loadedSource events to trigger proactive breakpoint rebinding.

        When a source file is loaded, immediately re-send setBreakpoints to
        accelerate verification. This is much faster than waiting for the
        adapter's asynchronous verification.

        Parameters
        ----------
        event : Event
            The DAP loadedSource event
        """
        # Skip if session already terminated or not connected
        try:
            if hasattr(self, "dap"):
                if getattr(self.dap, "is_terminated", False):
                    self.ctx.debug("Skipping loadedSource handling: session terminated")
                    return
                if hasattr(self.dap, "is_connected") and not self.dap.is_connected:
                    self.ctx.debug("Skipping loadedSource handling: DAP not connected")
                    return
        except Exception as e:
            # Best-effort guard; continue if checks not available
            self.ctx.debug(f"Guard check failed, proceeding anyway: {e}")

        loaded_event = cast("LoadedSourceEvent", event)
        if not loaded_event.body or not loaded_event.body.source:
            return

        source = loaded_event.body.source
        reason = loaded_event.body.reason

        # Only rebind on 'new' or 'changed' sources
        if reason not in ("new", "changed"):
            return

        if not source.path:
            self.ctx.debug(
                f"LoadedSource event has no path, skipping rebind: {source.name}",
            )
            return

        self.ctx.debug(
            f"Source loaded ({reason}): {source.path} - "
            "checking for breakpoints to rebind",
        )

        # Schedule rebinding asynchronously (can't await in event handler)
        import asyncio

        asyncio.create_task(self._rebind_breakpoints_for_source(source.path))

    def _on_terminated_event(self, event: "Event") -> None:  # noqa: ARG002
        """Handle session termination event.

        Note: We intentionally do NOT clear the breakpoint cache on termination.
        Breakpoint state represents what was set during the session and remains
        valid information even after the debug target exits. The cache is only
        cleared on explicit session cleanup/destroy.

        Parameters
        ----------
        event : Event
            The DAP terminated event (unused but required for event handler signature)
        """
        # Log termination but preserve breakpoint state
        self.ctx.debug(
            f"Session terminated, preserving {len(self._breakpoint_store)} "
            "breakpoint(s) in cache",
        )

    async def _rebind_breakpoints_for_source(self, source_path: str) -> None:
        """Re-send setBreakpoints for a specific source to accelerate verification.

        This is called when a loadedSource event arrives, triggering immediate
        breakpoint binding without waiting for the adapter's async verification.
        This significantly reduces the verification delay (from ~2s to ~10ms).

        Parameters
        ----------
        source_path : str
            Path to the source file that was just loaded
        """
        from aidb_common.path import normalize_path

        normalized_path = normalize_path(source_path)

        # Debounce check: skip if we rebinded this source recently (within 100ms)
        # This prevents rapid duplicate rebinds when loadedSource fires multiple
        # times for the same file (e.g., "new" followed by "changed" events)
        if not hasattr(self, "_last_rebind_times"):
            self._last_rebind_times = {}

        import time

        now = time.time()
        last_rebind = self._last_rebind_times.get(normalized_path, 0)
        if now - last_rebind < 0.1:  # 100ms debounce window
            self.ctx.debug(
                f"Skipping rebind for {source_path} (debounced: "
                f"{int((now - last_rebind) * 1000)}ms since last rebind)",
            )
            return

        self._last_rebind_times[normalized_path] = now

        # Guard: do not attempt rebind if session is terminated or disconnected
        try:
            if hasattr(self, "dap"):
                if getattr(self.dap, "is_terminated", False):
                    self.ctx.debug(
                        f"Skipping rebind for {source_path}: session terminated",
                    )
                    return
                if hasattr(self.dap, "is_connected") and not self.dap.is_connected:
                    self.ctx.debug(
                        f"Skipping rebind for {source_path}: DAP not connected",
                    )
                    return
        except Exception as e:
            # Best-effort guard; continue if checks not available
            self.ctx.debug(f"Rebind guard check failed, proceeding anyway: {e}")

        # Find all breakpoints for this source in the store
        # Use current_breakpoints property to get thread-safe copy
        current_bps = self.current_breakpoints
        if not current_bps:
            self.ctx.debug(
                f"No breakpoints in store for rebinding: {source_path}",
            )
            return

        breakpoints_to_rebind = [
            bp
            for bp in current_bps.breakpoints.values()
            if normalize_path(bp.source_path) == normalized_path
        ]

        if not breakpoints_to_rebind:
            self.ctx.debug(
                f"No breakpoints to rebind for loaded source: {source_path}",
            )
            return

        self.ctx.debug(
            f"Re-binding {len(breakpoints_to_rebind)} breakpoint(s) "
            f"for loaded source: {source_path}",
        )

        # Create DAP breakpoints from our stored breakpoints
        source = Source(path=source_path)
        source_breakpoints_dap = [
            SourceBreakpoint(
                line=bp.line,
                condition=bp.condition if bp.condition else None,
                hitCondition=bp.hit_condition if bp.hit_condition else None,
                logMessage=bp.log_message if bp.log_message else None,
            )
            for bp in breakpoints_to_rebind
        ]

        args = SetBreakpointsArguments(
            source=source,
            breakpoints=source_breakpoints_dap,
        )
        request = SetBreakpointsRequest(seq=0, arguments=args)

        try:
            # Send the rebind request
            response = await self.dap.send_request(request)
            if response.success:
                self.ctx.debug(
                    f"Successfully re-bound breakpoints for {source_path}: "
                    f"{response.body}",
                )
                # The response will trigger breakpoint events that update our store
            else:
                self.ctx.warning(
                    f"Failed to re-bind breakpoints for {source_path}: "
                    f"{response.message}",
                )
        except Exception as e:
            # Non-fatal: rebinding is an optimization, not critical
            self.ctx.warning(f"Error re-binding breakpoints for {source_path}: {e}")

    async def _set_initial_breakpoints(self) -> None:
        """Set initial breakpoints for the session.

        This method is called after the session is initialized and the adapter is
        connected. It groups breakpoints by source file and sends SetBreakpoints
        requests for each file.

        This method is idempotent - it tracks whether initial breakpoints have
        already been set and skips duplicate calls. This prevents issues with
        pooled LSP/DAP adapters where rapid-fire breakpoint setting can corrupt
        internal request/response tracking state.
        """
        if not self.breakpoints:
            return

        if getattr(self, "_initial_breakpoints_set", False):
            return

        # Group breakpoints by source file
        breakpoints_by_source: dict[str, list[AidbBreakpoint]] = {}
        for bp in self.breakpoints:
            source_path = bp.source_path
            if source_path not in breakpoints_by_source:
                breakpoints_by_source[source_path] = []
            breakpoints_by_source[source_path].append(bp)

        # Set breakpoints for each source file
        for source_path, source_breakpoints in breakpoints_by_source.items():
            self.ctx.debug(
                f"Setting {len(source_breakpoints)} breakpoints in {source_path}",
            )

            # Create SetBreakpointsRequest for this source file
            source = Source(path=source_path)
            source_breakpoints_dap = [
                SourceBreakpoint(
                    line=bp.line,
                    condition=bp.condition,
                    hitCondition=bp.hit_condition,
                    logMessage=bp.log_message,
                )
                for bp in source_breakpoints
            ]

            args = SetBreakpointsArguments(
                source=source,
                breakpoints=source_breakpoints_dap,
            )
            request = SetBreakpointsRequest(seq=0, arguments=args)

            try:
                # Send the request via the DAP client
                response = await self.dap.send_request(request)
                if response.success:
                    self.ctx.debug(
                        f"Successfully set breakpoints in {source_path}: "
                        f"{response.body}",
                    )
                    # Update internal store with response
                    if response.body and hasattr(response.body, "breakpoints"):
                        response_bps: list[AidbBreakpoint] = []
                        for bp_data in response.body.breakpoints:
                            # Convert DAP Breakpoint to AidbBreakpoint
                            # Use original breakpoint line if DAP doesn't return it
                            has_line = (
                                hasattr(bp_data, "line") and bp_data.line is not None
                            )
                            has_orig = len(response_bps) < len(source_breakpoints)
                            bp_line = (
                                bp_data.line
                                if has_line
                                else source_breakpoints[len(response_bps)].line
                                if has_orig
                                else 0
                            )
                            has_id = hasattr(bp_data, "id") and bp_data.id is not None
                            aidb_bp = AidbBreakpoint(
                                id=(bp_data.id if has_id else 0),
                                source_path=source_path,
                                line=bp_line,
                                verified=(
                                    bp_data.verified
                                    if hasattr(bp_data, "verified")
                                    else False
                                ),
                                state=(
                                    BreakpointState.VERIFIED
                                    if (
                                        hasattr(bp_data, "verified")
                                        and bp_data.verified
                                    )
                                    else BreakpointState.PENDING
                                ),
                                message=(
                                    bp_data.message
                                    if hasattr(bp_data, "message")
                                    else ""
                                ),
                            )
                            response_bps.append(aidb_bp)
                        await self._update_breakpoints_from_response(
                            source_path,
                            response_bps,
                        )
                        # Verify store was populated for debugging race conditions
                        if not self._breakpoint_store:
                            self.ctx.warning(
                                f"Breakpoint store empty after setting "
                                f"{len(response_bps)} breakpoints in {source_path}",
                            )
                else:
                    self.ctx.warning(
                        f"Failed to set breakpoints in {source_path}: "
                        f"{response.message}",
                    )
            except Exception as e:
                self.ctx.error(f"Error setting breakpoints in {source_path}: {e}")

        self._initial_breakpoints_set = True
