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
