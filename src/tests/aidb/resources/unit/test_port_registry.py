"""Unit tests for PortRegistry."""

import socket
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb.resources.ports import PortRegistry


class TestPortRegistryInit:
    """Tests for PortRegistry initialization."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        # Use temp directory for storage paths
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    def test_initialization_sets_session_id(self, mock_ctx: MagicMock) -> None:
        """Test that session_id is stored during initialization."""
        registry = PortRegistry(session_id="test-session", ctx=mock_ctx)

        assert registry._current_session_id == "test-session"

    def test_initialization_without_session_id(self, mock_ctx: MagicMock) -> None:
        """Test initialization without session_id."""
        registry = PortRegistry(ctx=mock_ctx)

        assert registry._current_session_id is None

    def test_singleton_behavior(self, mock_ctx: MagicMock) -> None:
        """Test that PortRegistry follows singleton pattern."""
        registry1 = PortRegistry(session_id="session1", ctx=mock_ctx)
        registry2 = PortRegistry(session_id="session2", ctx=mock_ctx)

        assert registry1 is registry2
        # Second call updates the session_id
        assert registry2._current_session_id == "session2"

    def test_creates_internal_registries(self, mock_ctx: MagicMock) -> None:
        """Test that internal registries are initialized."""
        registry = PortRegistry(ctx=mock_ctx)

        assert isinstance(registry._session_ports, dict)
        assert isinstance(registry._port_to_session, dict)
        assert isinstance(registry._reserved_sockets, dict)

    def test_creates_lock(self, mock_ctx: MagicMock) -> None:
        """Test that thread lock is created."""
        registry = PortRegistry(ctx=mock_ctx)

        # RLock is a factory function, check the type name
        assert type(registry.lock).__name__ == "RLock"


class TestPortRegistryReleaseReservedPort:
    """Tests for PortRegistry.release_reserved_port."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(session_id="test-session", ctx=mock_ctx)

    def test_releases_existing_socket(self, registry: PortRegistry) -> None:
        """Test releasing an existing socket reservation."""
        mock_socket = MagicMock(spec=socket.socket)
        registry._reserved_sockets[7000] = mock_socket

        registry.release_reserved_port(7000)

        assert 7000 not in registry._reserved_sockets
        mock_socket.close.assert_called_once()

    def test_handles_nonexistent_port(self, registry: PortRegistry) -> None:
        """Test releasing a port that doesn't exist."""
        # Should not raise
        registry.release_reserved_port(9999)

        assert 9999 not in registry._reserved_sockets

    def test_handles_socket_close_error(self, registry: PortRegistry) -> None:
        """Test that socket close errors are suppressed."""
        mock_socket = MagicMock(spec=socket.socket)
        mock_socket.close.side_effect = OSError("Close failed")
        registry._reserved_sockets[7000] = mock_socket

        # Should not raise
        registry.release_reserved_port(7000)

        assert 7000 not in registry._reserved_sockets


class TestPortRegistryGetPortCount:
    """Tests for PortRegistry.get_port_count."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(session_id="test-session", ctx=mock_ctx)

    def test_returns_zero_for_empty_session(self, registry: PortRegistry) -> None:
        """Test that empty session returns 0."""
        count = registry.get_port_count("unknown-session")

        assert count == 0

    def test_returns_correct_count(self, registry: PortRegistry) -> None:
        """Test that correct port count is returned."""
        registry._session_ports["session1"] = {7000, 7001, 7002}

        count = registry.get_port_count("session1")

        assert count == 3

    def test_uses_current_session_when_none_provided(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that current session is used when no session_id provided."""
        registry._current_session_id = "test-session"
        registry._session_ports["test-session"] = {8000, 8001}

        count = registry.get_port_count()

        assert count == 2

    def test_returns_zero_when_no_session_id(self, registry: PortRegistry) -> None:
        """Test that 0 is returned when no session_id available."""
        registry._current_session_id = None

        count = registry.get_port_count()

        assert count == 0


class TestPortRegistryCleanupStalePorts:
    """Tests for PortRegistry._cleanup_stale_ports."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_returns_empty_set_for_empty_input(self, registry: PortRegistry) -> None:
        """Test that empty set is returned for empty input."""
        result = registry._cleanup_stale_ports(set())

        assert result == set()

    def test_keeps_ports_in_use(self, registry: PortRegistry) -> None:
        """Test that ports in use are kept."""
        # Create actual socket to simulate port in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

            result = registry._cleanup_stale_ports({port})

            assert port in result
        finally:
            sock.close()

    def test_removes_stale_ports(self, registry: PortRegistry) -> None:
        """Test that stale ports (not in use) are removed."""
        # Find a port that's definitely not in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()  # Close it so it's stale

        result = registry._cleanup_stale_ports({port})

        assert port not in result


class TestPortRegistryCreateBoundSocket:
    """Tests for PortRegistry._create_bound_socket."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_creates_bound_socket(self, registry: PortRegistry) -> None:
        """Test that a socket is created and bound."""
        # Find an available port
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_sock.bind(("127.0.0.1", 0))
        port = temp_sock.getsockname()[1]
        temp_sock.close()

        sock = registry._create_bound_socket(port)

        try:
            assert sock is not None
            assert sock.getsockname()[1] == port
        finally:
            sock.close()

    def test_raises_oserror_when_port_in_use(self, registry: PortRegistry) -> None:
        """Test that OSError is raised when port is in use."""
        # Create a socket that binds to a port
        blocking_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocking_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocking_sock.bind(("127.0.0.1", 0))
        port = blocking_sock.getsockname()[1]
        blocking_sock.listen(1)

        try:
            with pytest.raises(OSError):
                registry._create_bound_socket(port)
        finally:
            blocking_sock.close()


class TestPortRegistryCheckCleanupRateLimit:
    """Tests for PortRegistry._check_cleanup_rate_limit."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_first_call_allowed(self, registry: PortRegistry) -> None:
        """Test that first cleanup call is allowed."""
        registry._last_cleanup_time = 0.0
        registry._cleanup_in_progress = False

        result = registry._check_cleanup_rate_limit(100.0)

        assert result is True
        assert registry._cleanup_in_progress is True

    def test_blocked_when_cleanup_in_progress(self, registry: PortRegistry) -> None:
        """Test that cleanup is blocked when already in progress."""
        registry._cleanup_in_progress = True

        result = registry._check_cleanup_rate_limit(100.0)

        assert result is False

    def test_blocked_within_rate_limit_interval(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that cleanup is blocked within rate limit interval."""
        registry._last_cleanup_time = 100.0
        registry._cleanup_min_interval = 5.0
        registry._cleanup_in_progress = False

        # Only 2 seconds have passed
        result = registry._check_cleanup_rate_limit(102.0)

        assert result is False

    def test_allowed_after_rate_limit_interval(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that cleanup is allowed after rate limit interval."""
        registry._last_cleanup_time = 100.0
        registry._cleanup_min_interval = 5.0
        registry._cleanup_in_progress = False

        # 10 seconds have passed
        result = registry._check_cleanup_rate_limit(110.0)

        assert result is True


class TestPortRegistryOptimisticTryAcquire:
    """Tests for PortRegistry._optimistic_try_acquire."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_successful_acquisition(self, registry: PortRegistry) -> None:
        """Test successful port acquisition."""
        # Find an available port
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_sock.bind(("127.0.0.1", 0))
        port = temp_sock.getsockname()[1]
        temp_sock.close()

        result = registry._optimistic_try_acquire(port, "test-session")

        assert result is True
        assert port in registry._port_to_session
        assert registry._port_to_session[port] == "test-session"
        assert port in registry._session_ports["test-session"]
        assert port in registry._reserved_sockets

        # Clean up
        registry._reserved_sockets[port].close()

    def test_fails_when_already_allocated_in_process(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that acquisition fails if port already allocated in-process."""
        registry._port_to_session[7000] = "other-session"

        result = registry._optimistic_try_acquire(7000, "test-session")

        assert result is False

    def test_fails_when_port_in_use(self, registry: PortRegistry) -> None:
        """Test that acquisition fails when port is in use by another process."""
        # Create a socket that binds to a port
        blocking_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocking_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocking_sock.bind(("127.0.0.1", 0))
        port = blocking_sock.getsockname()[1]
        blocking_sock.listen(1)

        try:
            result = registry._optimistic_try_acquire(port, "test-session")

            assert result is False
            assert port not in registry._port_to_session
        finally:
            blocking_sock.close()


class TestPortRegistryFindActivePorts:
    """Tests for PortRegistry._find_active_ports."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_returns_empty_for_empty_input(self, registry: PortRegistry) -> None:
        """Test that empty set is returned for empty input."""
        result = registry._find_active_ports(set())

        assert result == set()

    def test_identifies_active_port(self, registry: PortRegistry) -> None:
        """Test that active ports are identified."""
        # Create actual socket to simulate port in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.listen(1)

            result = registry._find_active_ports({port})

            assert port in result
        finally:
            sock.close()

    def test_excludes_inactive_port(self, registry: PortRegistry) -> None:
        """Test that inactive ports are excluded."""
        # Find a port that's not in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        result = registry._find_active_ports({port})

        assert port not in result


class TestPortRegistryPerformCleanup:
    """Tests for PortRegistry._perform_cleanup."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton state before each test."""
        PortRegistry._instance = None

    @pytest.fixture
    def mock_ctx(self) -> MagicMock:
        """Create a mock context."""
        ctx = MagicMock()
        ctx.debug = MagicMock()
        ctx.info = MagicMock()
        ctx.warning = MagicMock()
        temp_dir = tempfile.mkdtemp()
        ctx.get_storage_path = lambda *args: Path(temp_dir) / "/".join(args)
        return ctx

    @pytest.fixture
    def registry(self, mock_ctx: MagicMock) -> PortRegistry:
        """Create a PortRegistry instance."""
        return PortRegistry(ctx=mock_ctx)

    def test_returns_zero_when_no_cleanup_needed(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that 0 is returned when no cleanup is needed."""
        allocated = {7000, 7001, 7002}
        active = {7000, 7001, 7002}  # All active

        result = registry._perform_cleanup(allocated, active)

        assert result == 0

    def test_returns_count_of_cleaned_ports(self, registry: PortRegistry) -> None:
        """Test that correct cleanup count is returned."""
        allocated = {7000, 7001, 7002, 7003, 7004}
        active = {7000, 7001}  # Only 2 active, 3 stale

        with patch.object(registry, "_write_cross_process_registry"):
            result = registry._perform_cleanup(allocated, active)

        assert result == 3

    def test_writes_to_registry_when_cleanup_performed(
        self,
        registry: PortRegistry,
    ) -> None:
        """Test that registry is updated when cleanup is performed."""
        allocated = {7000, 7001, 7002}
        active = {7000}

        with patch.object(registry, "_write_cross_process_registry") as mock_write:
            registry._perform_cleanup(allocated, active)

        mock_write.assert_called_once_with(active)
