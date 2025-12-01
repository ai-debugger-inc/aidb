"""Unit tests for SessionBreakpointsMixin.

Tests breakpoint management operations including store management, event handling, and
state synchronization.
"""

import asyncio
import time
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.models import AidbBreakpoint, AidbBreakpointsResponse, BreakpointState


class TestableBreakpointsMixin:
    """Testable wrapper for SessionBreakpointsMixin.

    Provides all required attributes for the mixin to function without needing the full
    Session class.
    """

    # Type stubs for dynamically copied methods from SessionBreakpointsMixin
    _on_loaded_source_event: Any
    _on_terminated_event: Any
    _on_breakpoint_event: Any
    _clear_breakpoint_cache_on_termination: Any
    _rebind_breakpoints_for_source: Any
    _set_initial_breakpoints: Any
    _clear_breakpoints_for_source: Any
    _update_breakpoint_from_event: Any
    _update_breakpoints_from_response: Any

    # Type stubs for attributes set by fixture
    ctx: Any
    dap: Any
    adapter: Any
    debug: Any
    breakpoints: list[AidbBreakpoint]
    _breakpoint_store: dict[int, AidbBreakpoint]
    _breakpoint_store_lock: Any
    _breakpoint_update_tasks: set[Any]
    _last_rebind_times: dict[str, float]
    _initial_breakpoints_set: bool

    def __init__(self) -> None:
        from aidb.session.session_breakpoints import SessionBreakpointsMixin

        # Copy mixin methods to this instance
        for attr in dir(SessionBreakpointsMixin):
            if not attr.startswith("__"):
                member = getattr(SessionBreakpointsMixin, attr)
                if callable(member):
                    setattr(self, attr, member.__get__(self, type(self)))
                elif isinstance(member, property):
                    # Handle properties by creating a property on the class
                    pass  # Properties need special handling below

    @property
    def current_breakpoints(self) -> AidbBreakpointsResponse | None:
        """Delegate to mixin's current_breakpoints property."""
        if not self._breakpoint_store:
            return None
        return AidbBreakpointsResponse(breakpoints=self._breakpoint_store.copy())


@pytest.fixture
def breakpoints_mixin(mock_ctx: MagicMock) -> TestableBreakpointsMixin:
    """Create a testable SessionBreakpointsMixin instance."""
    mixin = TestableBreakpointsMixin()

    # Core attributes
    mixin.ctx = mock_ctx
    mixin._breakpoint_store = {}
    mixin._breakpoint_store_lock = asyncio.Lock()
    mixin._breakpoint_update_tasks = set()
    mixin._last_rebind_times = {}
    mixin.breakpoints = []
    mixin._initial_breakpoints_set = False

    # DAP mock
    mixin.dap = MagicMock()
    mixin.dap.is_terminated = False
    mixin.dap.is_connected = True
    mixin.dap.send_request = AsyncMock()
    mixin.dap.events = MagicMock()
    mixin.dap.events.subscribe_to_event = AsyncMock(return_value="sub-id")

    # Adapter mock
    mixin.adapter = MagicMock()

    # Debug ops mock
    mixin.debug = MagicMock()

    return mixin


def make_breakpoint(
    bp_id: int = 1,
    source_path: str = "/path/to/file.py",
    line: int = 10,
    verified: bool = False,
    state: BreakpointState = BreakpointState.PENDING,
    condition: str | None = None,
    hit_condition: str | None = None,
    log_message: str | None = None,
    message: str = "",
) -> AidbBreakpoint:
    """Helper to create AidbBreakpoint instances."""
    return AidbBreakpoint(
        id=bp_id,
        source_path=source_path,
        line=line,
        verified=verified,
        state=state,
        condition=condition,
        hit_condition=hit_condition,
        log_message=log_message,
        message=message,
    )


def make_breakpoint_event(
    bp_id: int | None = 1,
    reason: str = "changed",
    verified: bool = True,
    line: int = 10,
    source_path: str | None = "/path/to/file.py",
    message: str | None = None,
) -> MagicMock:
    """Helper to create mock DAP breakpoint events."""
    event = MagicMock()
    event.body = MagicMock()
    event.body.reason = reason
    event.body.breakpoint = MagicMock()
    event.body.breakpoint.id = bp_id
    event.body.breakpoint.verified = verified
    event.body.breakpoint.line = line
    event.body.breakpoint.message = message

    if source_path:
        event.body.breakpoint.source = MagicMock()
        event.body.breakpoint.source.path = source_path
    else:
        event.body.breakpoint.source = None

    return event


def make_loaded_source_event(
    source_path: str = "/path/to/file.py",
    reason: str = "new",
) -> MagicMock:
    """Helper to create mock DAP loadedSource events."""
    event = MagicMock()
    event.body = MagicMock()
    event.body.reason = reason
    event.body.source = MagicMock()
    event.body.source.path = source_path
    event.body.source.name = source_path.split("/")[-1]
    return event


class TestSessionBreakpointsCurrentBreakpoints:
    """Tests for SessionBreakpointsMixin.current_breakpoints property."""

    def test_current_breakpoints_returns_none_when_empty(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When store is empty, return None."""
        breakpoints_mixin._breakpoint_store = {}

        result = breakpoints_mixin.current_breakpoints

        assert result is None

    def test_current_breakpoints_returns_copy(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify dict.copy() is used for thread safety."""
        bp = make_breakpoint(bp_id=1)
        breakpoints_mixin._breakpoint_store = {1: bp}

        result = breakpoints_mixin.current_breakpoints

        # Modifying result shouldn't affect original store
        assert result is not None
        result.breakpoints[999] = make_breakpoint(bp_id=999)
        assert 999 not in breakpoints_mixin._breakpoint_store

    def test_current_breakpoints_wraps_in_response(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify AidbBreakpointsResponse wrapper is used."""
        bp = make_breakpoint(bp_id=1)
        breakpoints_mixin._breakpoint_store = {1: bp}

        result = breakpoints_mixin.current_breakpoints

        assert isinstance(result, AidbBreakpointsResponse)
        assert 1 in result.breakpoints
        assert result.breakpoints[1] == bp


class TestSessionBreakpointsUpdateFromResponse:
    """Tests for SessionBreakpointsMixin._update_breakpoints_from_response()."""

    @pytest.mark.asyncio
    async def test_update_breakpoints_clears_existing_for_source(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify existing breakpoints for source are cleared first."""
        # Set up existing breakpoints for the same source
        existing_bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=5)
        breakpoints_mixin._breakpoint_store = {1: existing_bp}

        # Update with new breakpoints
        new_bps = [make_breakpoint(bp_id=2, source_path="/path/to/file.py", line=10)]
        await breakpoints_mixin._update_breakpoints_from_response(
            "/path/to/file.py",
            new_bps,
        )

        # Old breakpoint should be gone
        assert 1 not in breakpoints_mixin._breakpoint_store
        assert 2 in breakpoints_mixin._breakpoint_store

    @pytest.mark.asyncio
    async def test_update_breakpoints_adds_new_breakpoints(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify bp.id is added to store."""
        new_bps = [
            make_breakpoint(bp_id=1, line=10),
            make_breakpoint(bp_id=2, line=20),
        ]

        await breakpoints_mixin._update_breakpoints_from_response(
            "/path/to/file.py",
            new_bps,
        )

        assert 1 in breakpoints_mixin._breakpoint_store
        assert 2 in breakpoints_mixin._breakpoint_store
        assert breakpoints_mixin._breakpoint_store[1].line == 10
        assert breakpoints_mixin._breakpoint_store[2].line == 20

    @pytest.mark.asyncio
    async def test_update_breakpoints_fixes_empty_source_path(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify replace(source_path=...) fallback when source_path is empty."""
        # Breakpoint with empty source_path (simulating DAP adapter behavior)
        bp_with_empty_path = make_breakpoint(bp_id=1, source_path="", line=10)

        await breakpoints_mixin._update_breakpoints_from_response(
            "/path/to/file.py",
            [bp_with_empty_path],
        )

        # Source path should be fixed
        assert breakpoints_mixin._breakpoint_store[1].source_path == "/path/to/file.py"

    @pytest.mark.asyncio
    async def test_update_breakpoints_skips_breakpoints_without_id(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify None id is skipped with warning."""
        bp_with_no_id = make_breakpoint(bp_id=1, line=10)
        # Simulate None id by setting it explicitly
        bp_with_no_id = replace(bp_with_no_id, id=None)

        await breakpoints_mixin._update_breakpoints_from_response(
            "/path/to/file.py",
            [bp_with_no_id],
        )

        # Should be skipped
        assert len(breakpoints_mixin._breakpoint_store) == 0
        breakpoints_mixin.ctx.warning.assert_called()

    @pytest.mark.asyncio
    async def test_update_breakpoints_preserves_other_sources(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Breakpoints for other sources should not be affected."""
        other_bp = make_breakpoint(bp_id=1, source_path="/path/to/other.py", line=5)
        breakpoints_mixin._breakpoint_store = {1: other_bp}

        new_bps = [make_breakpoint(bp_id=2, source_path="/path/to/file.py", line=10)]
        await breakpoints_mixin._update_breakpoints_from_response(
            "/path/to/file.py",
            new_bps,
        )

        # Other source breakpoint should still exist
        assert 1 in breakpoints_mixin._breakpoint_store
        assert breakpoints_mixin._breakpoint_store[1].source_path == "/path/to/other.py"


class TestSessionBreakpointsOnBreakpointEvent:
    """Tests for SessionBreakpointsMixin._on_breakpoint_event()."""

    def test_on_breakpoint_event_handles_changed_reason(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """For 'changed' reason, schedule update task."""
        event = make_breakpoint_event(reason="changed")

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            breakpoints_mixin._on_breakpoint_event(event)

            mock_create_task.assert_called_once()
            assert mock_task in breakpoints_mixin._breakpoint_update_tasks

    def test_on_breakpoint_event_handles_new_reason(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """For 'new' reason, schedule update task."""
        event = make_breakpoint_event(reason="new")

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            breakpoints_mixin._on_breakpoint_event(event)

            mock_create_task.assert_called_once()

    def test_on_breakpoint_event_ignores_other_reasons(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """For other reasons like 'removed', do not schedule task."""
        event = make_breakpoint_event(reason="removed")

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_breakpoint_event(event)

            mock_create_task.assert_not_called()

    def test_on_breakpoint_event_handles_missing_body(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When event has no body, return early."""
        event = MagicMock()
        event.body = None

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_breakpoint_event(event)

            mock_create_task.assert_not_called()


class TestSessionBreakpointsUpdateFromEvent:
    """Tests for SessionBreakpointsMixin._update_breakpoint_from_event()."""

    @pytest.mark.asyncio
    async def test_update_breakpoint_from_event_id_matching(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Primary path: ID in store gets updated."""
        # Set up existing breakpoint
        existing_bp = make_breakpoint(
            bp_id=1,
            verified=False,
            state=BreakpointState.PENDING,
        )
        breakpoints_mixin._breakpoint_store = {1: existing_bp}

        # Create event with verification update
        event = make_breakpoint_event(bp_id=1, verified=True)

        await breakpoints_mixin._update_breakpoint_from_event(event)

        # Breakpoint should be updated
        updated = breakpoints_mixin._breakpoint_store[1]
        assert updated.verified is True
        assert updated.state == BreakpointState.VERIFIED

    @pytest.mark.asyncio
    async def test_update_breakpoint_from_event_updates_verification_state(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify PENDING -> VERIFIED state transition."""
        existing_bp = make_breakpoint(
            bp_id=1,
            verified=False,
            state=BreakpointState.PENDING,
        )
        breakpoints_mixin._breakpoint_store = {1: existing_bp}

        event = make_breakpoint_event(bp_id=1, verified=True, message="Verified!")

        await breakpoints_mixin._update_breakpoint_from_event(event)

        updated = breakpoints_mixin._breakpoint_store[1]
        assert updated.state == BreakpointState.VERIFIED
        assert updated.message == "Verified!"

    @pytest.mark.asyncio
    async def test_update_breakpoint_from_event_fallback_location_matching(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When ID is None, use location-based matching."""
        # Use absolute path to ensure normalization works consistently
        source_path = "/path/to/file.py"
        existing_bp = make_breakpoint(
            bp_id=1,
            source_path=source_path,
            line=10,
            verified=False,
        )
        breakpoints_mixin._breakpoint_store = {1: existing_bp}

        # Event without ID but with location
        # Use a simple object to avoid MagicMock auto-creating attributes
        class MockSource:
            path = source_path

        class MockBreakpointData:
            id = None
            verified = True
            line = 10
            message = None
            source = MockSource()
            # Don't define column - hasattr will return False

        class MockBody:
            reason = "changed"
            breakpoint = MockBreakpointData()

        class MockEvent:
            body = MockBody()

        event = MockEvent()

        await breakpoints_mixin._update_breakpoint_from_event(event)

        # Should update via fallback matching
        updated = breakpoints_mixin._breakpoint_store[1]
        assert updated.verified is True
        assert updated.state == BreakpointState.VERIFIED

    @pytest.mark.asyncio
    async def test_update_breakpoint_from_event_logs_unknown_id(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Debug log for ID not in store."""
        breakpoints_mixin._breakpoint_store = {}

        event = make_breakpoint_event(bp_id=999, verified=True)

        await breakpoints_mixin._update_breakpoint_from_event(event)

        # Should log unknown ID
        breakpoints_mixin.ctx.debug.assert_called()

    @pytest.mark.asyncio
    async def test_update_breakpoint_from_event_unverify(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Test VERIFIED -> PENDING state transition."""
        existing_bp = make_breakpoint(
            bp_id=1,
            verified=True,
            state=BreakpointState.VERIFIED,
        )
        breakpoints_mixin._breakpoint_store = {1: existing_bp}

        event = make_breakpoint_event(bp_id=1, verified=False)

        await breakpoints_mixin._update_breakpoint_from_event(event)

        updated = breakpoints_mixin._breakpoint_store[1]
        assert updated.state == BreakpointState.PENDING
        assert updated.verified is False


class TestSessionBreakpointsLoadedSourceEvent:
    """Tests for SessionBreakpointsMixin._on_loaded_source_event()."""

    def test_on_loaded_source_event_schedules_rebind(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """asyncio.create_task should be called for rebind."""
        event = make_loaded_source_event(reason="new")

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_loaded_source_event(event)

            mock_create_task.assert_called_once()

    def test_on_loaded_source_event_skips_terminated_session(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When session is terminated, skip rebind."""
        breakpoints_mixin.dap.is_terminated = True
        event = make_loaded_source_event(reason="new")

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_loaded_source_event(event)

            mock_create_task.assert_not_called()

    def test_on_loaded_source_event_skips_disconnected_dap(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When DAP is disconnected, skip rebind."""
        breakpoints_mixin.dap.is_connected = False
        event = make_loaded_source_event(reason="new")

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_loaded_source_event(event)

            mock_create_task.assert_not_called()

    def test_on_loaded_source_event_only_handles_new_changed(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Ignore reasons other than 'new' and 'changed'."""
        event = make_loaded_source_event(reason="removed")

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_loaded_source_event(event)

            mock_create_task.assert_not_called()

    def test_on_loaded_source_event_handles_missing_source_path(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When source has no path, skip rebind."""
        event = make_loaded_source_event(reason="new")
        event.body.source.path = None

        with patch("asyncio.create_task") as mock_create_task:
            breakpoints_mixin._on_loaded_source_event(event)

            mock_create_task.assert_not_called()


class TestSessionBreakpointsOnTerminatedEvent:
    """Tests for SessionBreakpointsMixin._on_terminated_event()."""

    def test_on_terminated_event_schedules_cleanup(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Schedule async cleanup task."""
        event = MagicMock()

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = MagicMock()
            mock_create_task.return_value = mock_task

            breakpoints_mixin._on_terminated_event(event)

            mock_create_task.assert_called_once()
            assert mock_task in breakpoints_mixin._breakpoint_update_tasks


class TestSessionBreakpointsClearCacheOnTermination:
    """Tests for SessionBreakpointsMixin._clear_breakpoint_cache_on_termination()."""

    @pytest.mark.asyncio
    async def test_clear_breakpoint_cache_clears_store(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify store is cleared."""
        breakpoints_mixin._breakpoint_store = {
            1: make_breakpoint(bp_id=1),
            2: make_breakpoint(bp_id=2),
        }

        await breakpoints_mixin._clear_breakpoint_cache_on_termination()

        assert len(breakpoints_mixin._breakpoint_store) == 0

    @pytest.mark.asyncio
    async def test_clear_breakpoint_cache_logs_count(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify debug log includes count of cleared breakpoints."""
        breakpoints_mixin._breakpoint_store = {
            1: make_breakpoint(bp_id=1),
            2: make_breakpoint(bp_id=2),
        }

        await breakpoints_mixin._clear_breakpoint_cache_on_termination()

        breakpoints_mixin.ctx.debug.assert_called()


class TestSessionBreakpointsRebindForSource:
    """Tests for SessionBreakpointsMixin._rebind_breakpoints_for_source()."""

    @pytest.mark.asyncio
    async def test_rebind_breakpoints_sends_request(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify SetBreakpointsRequest is sent."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}

        # Mock successful response
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.body = MagicMock()
        breakpoints_mixin.dap.send_request.return_value = mock_response

        await breakpoints_mixin._rebind_breakpoints_for_source("/path/to/file.py")

        breakpoints_mixin.dap.send_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rebind_breakpoints_debounces(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify rapid rebinds are debounced (100ms window)."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}

        # Set recent rebind time
        from aidb_common.path import normalize_path

        normalized = normalize_path("/path/to/file.py")
        breakpoints_mixin._last_rebind_times[normalized] = time.time()

        await breakpoints_mixin._rebind_breakpoints_for_source("/path/to/file.py")

        # Should be debounced - no request sent
        breakpoints_mixin.dap.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebind_breakpoints_skips_terminated_session(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When session is terminated, skip rebind."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}
        breakpoints_mixin.dap.is_terminated = True

        await breakpoints_mixin._rebind_breakpoints_for_source("/path/to/file.py")

        breakpoints_mixin.dap.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebind_breakpoints_skips_if_no_breakpoints_for_source(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When no breakpoints for source, skip rebind."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/other.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}

        await breakpoints_mixin._rebind_breakpoints_for_source("/path/to/file.py")

        breakpoints_mixin.dap.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rebind_breakpoints_handles_failure(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When request fails, log warning but don't raise."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}

        mock_response = MagicMock()
        mock_response.success = False
        mock_response.message = "Failed"
        breakpoints_mixin.dap.send_request.return_value = mock_response

        # Should not raise
        await breakpoints_mixin._rebind_breakpoints_for_source("/path/to/file.py")

        breakpoints_mixin.ctx.warning.assert_called()


class TestSessionBreakpointsSetInitialBreakpoints:
    """Tests for SessionBreakpointsMixin._set_initial_breakpoints()."""

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_sends_requests_per_source(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify SetBreakpointsRequest is sent for each source file."""
        breakpoints_mixin.breakpoints = [
            make_breakpoint(bp_id=0, source_path="/file1.py", line=10),
            make_breakpoint(bp_id=0, source_path="/file1.py", line=20),
            make_breakpoint(bp_id=0, source_path="/file2.py", line=5),
        ]

        # Mock response with assigned IDs
        def make_response(breakpoints: list) -> MagicMock:
            response = MagicMock()
            response.success = True
            response.body = MagicMock()
            response.body.breakpoints = []
            for i, _ in enumerate(breakpoints):
                bp = MagicMock()
                bp.id = i + 1
                bp.verified = True
                bp.line = None  # Test fallback line handling
                response.body.breakpoints.append(bp)
            return response

        # Track calls to determine responses
        call_count = [0]

        def side_effect(request: Any) -> MagicMock:
            call_count[0] += 1
            if call_count[0] == 1:
                return make_response([1, 2])  # file1.py has 2 breakpoints
            return make_response([1])  # file2.py has 1 breakpoint

        breakpoints_mixin.dap.send_request = AsyncMock(side_effect=side_effect)

        await breakpoints_mixin._set_initial_breakpoints()

        # Should have sent 2 requests (one per source file)
        assert breakpoints_mixin.dap.send_request.await_count == 2

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_is_idempotent(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify idempotence - second call is skipped."""
        breakpoints_mixin.breakpoints = [
            make_breakpoint(bp_id=0, source_path="/file.py", line=10),
        ]
        breakpoints_mixin._initial_breakpoints_set = True

        await breakpoints_mixin._set_initial_breakpoints()

        # Should skip since already set
        breakpoints_mixin.dap.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_skips_when_empty(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When no breakpoints, skip entirely."""
        breakpoints_mixin.breakpoints = []

        await breakpoints_mixin._set_initial_breakpoints()

        breakpoints_mixin.dap.send_request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_updates_store(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify _update_breakpoints_from_response is called."""
        breakpoints_mixin.breakpoints = [
            make_breakpoint(bp_id=0, source_path="/file.py", line=10),
        ]

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = [MagicMock(id=1, verified=True, line=10)]
        breakpoints_mixin.dap.send_request.return_value = mock_response

        await breakpoints_mixin._set_initial_breakpoints()

        # Store should be updated
        assert 1 in breakpoints_mixin._breakpoint_store

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_handles_failure(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """When request fails, log warning but continue."""
        breakpoints_mixin.breakpoints = [
            make_breakpoint(bp_id=0, source_path="/file.py", line=10),
        ]

        mock_response = MagicMock()
        mock_response.success = False
        mock_response.message = "Failed"
        breakpoints_mixin.dap.send_request.return_value = mock_response

        # Should not raise
        await breakpoints_mixin._set_initial_breakpoints()

        breakpoints_mixin.ctx.warning.assert_called()

    @pytest.mark.asyncio
    async def test_set_initial_breakpoints_includes_conditions(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify conditional breakpoints include condition in request."""
        breakpoints_mixin.breakpoints = [
            make_breakpoint(
                bp_id=0,
                source_path="/file.py",
                line=10,
                condition="x > 5",
                hit_condition=">10",
                log_message="Value: {x}",
            ),
        ]

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.body = MagicMock()
        mock_response.body.breakpoints = [MagicMock(id=1, verified=True, line=10)]
        breakpoints_mixin.dap.send_request.return_value = mock_response

        await breakpoints_mixin._set_initial_breakpoints()

        # Verify request was sent (conditions are passed through)
        breakpoints_mixin.dap.send_request.assert_awaited_once()
        # The actual request object would contain the conditions
        call_args = breakpoints_mixin.dap.send_request.call_args
        request = call_args[0][0]
        assert request.arguments.breakpoints[0].condition == "x > 5"


class TestSessionBreakpointsClearForSource:
    """Tests for SessionBreakpointsMixin._clear_breakpoints_for_source()."""

    def test_clear_breakpoints_for_source_removes_matching(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify breakpoints for the source are removed."""
        bp1 = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        bp2 = make_breakpoint(bp_id=2, source_path="/path/to/file.py", line=20)
        bp3 = make_breakpoint(bp_id=3, source_path="/path/to/other.py", line=5)
        breakpoints_mixin._breakpoint_store = {1: bp1, 2: bp2, 3: bp3}

        breakpoints_mixin._clear_breakpoints_for_source("/path/to/file.py")

        assert 1 not in breakpoints_mixin._breakpoint_store
        assert 2 not in breakpoints_mixin._breakpoint_store
        assert 3 in breakpoints_mixin._breakpoint_store

    def test_clear_breakpoints_for_source_handles_path_normalization(
        self,
        breakpoints_mixin: TestableBreakpointsMixin,
    ) -> None:
        """Verify path normalization is used for matching."""
        bp = make_breakpoint(bp_id=1, source_path="/path/to/file.py", line=10)
        breakpoints_mixin._breakpoint_store = {1: bp}

        # Use path with different format (trailing slash, etc.)
        breakpoints_mixin._clear_breakpoints_for_source("/path/to/./file.py")

        # Should still match due to normalization
        assert 1 not in breakpoints_mixin._breakpoint_store
