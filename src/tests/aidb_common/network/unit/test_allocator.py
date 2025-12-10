"""Unit tests for CrossProcessPortAllocator.

Tests atomic cross-process port allocation with file locking, socket binding
verification, and lease-based cleanup.
"""

import errno
import fcntl
import json
import os
import socket
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb_common.network.allocator import (
    DEFAULT_LEASE_TIMEOUT_S,
    DEFAULT_LOCK_FILE,
    DEFAULT_PORT_RANGE_SIZE,
    DEFAULT_PORT_RANGE_START,
    DEFAULT_REGISTRY_DIR,
    DEFAULT_REGISTRY_FILE,
    LOCK_TIMEOUT_S,
    CrossProcessPortAllocator,
    allocate_port,
    get_allocator,
    release_port,
)


class TestCrossProcessPortAllocatorInit:
    """Tests for CrossProcessPortAllocator initialization."""

    def test_init_creates_registry_directory(self, tmp_path: Path) -> None:
        """Initialization creates registry directory if it doesn't exist."""
        registry_dir = tmp_path / "new_registry"
        assert not registry_dir.exists()

        CrossProcessPortAllocator(registry_dir=registry_dir)

        assert registry_dir.exists()
        assert registry_dir.is_dir()

    def test_init_with_custom_registry_dir(self, tmp_path: Path) -> None:
        """Custom registry directory is used for registry and lock files."""
        registry_dir = tmp_path / "custom"
        allocator = CrossProcessPortAllocator(registry_dir=registry_dir)

        assert allocator.registry_dir == registry_dir
        assert allocator.registry_file == registry_dir / DEFAULT_REGISTRY_FILE
        assert allocator.lock_file == registry_dir / DEFAULT_LOCK_FILE

    def test_init_with_custom_lease_timeout(self, tmp_path: Path) -> None:
        """Custom lease timeout is stored correctly."""
        allocator = CrossProcessPortAllocator(
            registry_dir=tmp_path,
            lease_timeout=60.0,
        )

        assert allocator.lease_timeout == 60.0

    def test_init_uses_default_lease_timeout(self, tmp_path: Path) -> None:
        """Default lease timeout is used when not specified."""
        allocator = CrossProcessPortAllocator(registry_dir=tmp_path)

        assert allocator.lease_timeout == DEFAULT_LEASE_TIMEOUT_S

    def test_init_handles_existing_directory(self, temp_registry_dir: Path) -> None:
        """Initialization succeeds when directory already exists."""
        assert temp_registry_dir.exists()

        allocator = CrossProcessPortAllocator(registry_dir=temp_registry_dir)

        assert allocator.registry_dir == temp_registry_dir


class TestCrossProcessPortAllocatorLock:
    """Tests for the _lock context manager."""

    def test_lock_acquires_exclusive_lock(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Lock acquires exclusive non-blocking lock via fcntl.flock."""
        with patch("fcntl.flock") as mock_flock:
            with allocator._lock():
                pass

            # First call should be LOCK_EX | LOCK_NB
            first_call = mock_flock.call_args_list[0]
            assert first_call[0][1] == fcntl.LOCK_EX | fcntl.LOCK_NB

    def test_lock_releases_on_exit(self, allocator: CrossProcessPortAllocator) -> None:
        """Lock is released with LOCK_UN when context exits."""
        with patch("fcntl.flock") as mock_flock:
            with allocator._lock():
                pass

            # Last call should be LOCK_UN
            last_call = mock_flock.call_args_list[-1]
            assert last_call[0][1] == fcntl.LOCK_UN

    def test_lock_releases_on_exception(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Lock is released even when exception occurs in context."""
        with patch("fcntl.flock") as mock_flock:
            with pytest.raises(ValueError, match="test error"):
                with allocator._lock():
                    msg = "test error"
                    raise ValueError(msg)

            # Should still have LOCK_UN call
            last_call = mock_flock.call_args_list[-1]
            assert last_call[0][1] == fcntl.LOCK_UN

    def test_lock_timeout_raises_error(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """TimeoutError raised when lock cannot be acquired within timeout."""

        def always_blocked(*args):
            err = OSError()
            err.errno = errno.EWOULDBLOCK
            raise err

        # Need enough return values for all monotonic() calls in the loop
        time_values = [0.0] + [LOCK_TIMEOUT_S + 1.0] * 10

        with (
            patch("fcntl.flock", side_effect=always_blocked),
            patch("time.monotonic", side_effect=time_values),
            patch("time.sleep"),
        ):
            with pytest.raises(TimeoutError, match="lock timeout"):
                with allocator._lock():
                    pass

    def test_lock_retries_on_ewouldblock(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Lock retries when EWOULDBLOCK errno is received."""
        call_count = 0

        def fail_then_succeed(*args):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                err = OSError()
                err.errno = errno.EWOULDBLOCK
                raise err
            # Success on third try (or unlock)

        with (
            patch("fcntl.flock", side_effect=fail_then_succeed),
            patch("time.monotonic", return_value=0.0),
            patch("time.sleep"),
        ):
            with allocator._lock():
                pass

        # Should have retried (3 acquire attempts + 1 unlock)
        assert call_count >= 3


class TestCrossProcessPortAllocatorBindCheck:
    """Tests for _is_port_bindable method."""

    def _create_mock_socket(self, bind_succeeds: bool = True) -> MagicMock:
        """Create a mock socket that works as a context manager.

        Parameters
        ----------
        bind_succeeds : bool
            Whether bind() should succeed or raise OSError

        Returns
        -------
        MagicMock
            Mock socket configured as context manager
        """
        mock_socket = MagicMock()
        mock_socket.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket.__exit__ = MagicMock(return_value=False)
        if not bind_succeeds:
            mock_socket.bind.side_effect = OSError("Address in use")
        return mock_socket

    def test_is_port_bindable_success(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Returns True when socket binding succeeds."""
        ipv4_socket = self._create_mock_socket(bind_succeeds=True)
        ipv6_socket = self._create_mock_socket(bind_succeeds=True)

        with patch("socket.socket", side_effect=[ipv4_socket, ipv6_socket]):
            result = allocator._is_port_bindable(8000)

        assert result is True
        ipv4_socket.bind.assert_called_once_with(("127.0.0.1", 8000))

    def test_is_port_bindable_failure(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Returns False when socket binding fails."""
        mock_socket = self._create_mock_socket(bind_succeeds=False)

        with patch("socket.socket", return_value=mock_socket):
            result = allocator._is_port_bindable(8000)

        assert result is False

    def test_is_port_bindable_ipv6_check(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Checks IPv6 binding for localhost addresses."""
        ipv4_socket = self._create_mock_socket(bind_succeeds=True)
        ipv6_socket = self._create_mock_socket(bind_succeeds=True)

        with patch("socket.socket", side_effect=[ipv4_socket, ipv6_socket]):
            result = allocator._is_port_bindable(8000, host="127.0.0.1")

        assert result is True
        # Both IPv4 and IPv6 sockets should be bound
        ipv4_socket.bind.assert_called_once_with(("127.0.0.1", 8000))
        ipv6_socket.bind.assert_called_once_with(("::1", 8000))

    def test_is_port_bindable_skips_ipv6_for_custom_host(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Skips IPv6 check for non-localhost hosts."""
        socket_calls = []

        def track_socket(family, *args, **kwargs):
            socket_calls.append(family)
            return self._create_mock_socket(bind_succeeds=True)

        with patch("socket.socket", side_effect=track_socket):
            result = allocator._is_port_bindable(8000, host="192.168.1.1")

        assert result is True
        # Should only check IPv4
        assert socket.AF_INET in socket_calls
        assert socket.AF_INET6 not in socket_calls

    def test_is_port_bindable_ipv6_failure(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Returns False when IPv6 bind fails even if IPv4 succeeds."""
        ipv4_socket = self._create_mock_socket(bind_succeeds=True)
        ipv6_socket = self._create_mock_socket(bind_succeeds=False)

        with patch("socket.socket", side_effect=[ipv4_socket, ipv6_socket]):
            result = allocator._is_port_bindable(8000, host="127.0.0.1")

        assert result is False


class TestCrossProcessPortAllocatorAllocate:
    """Tests for allocate method."""

    def test_allocate_returns_preferred_port(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Allocate returns preferred port when available."""
        with patch.object(allocator, "_is_port_bindable", return_value=True):
            port = allocator.allocate(preferred=9000)

        assert port == 9000

    def test_allocate_falls_back_to_range(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Allocate uses range when preferred port unavailable."""

        def bindable_check(port, host="127.0.0.1"):
            return port != 9000  # Preferred not bindable

        with patch.object(allocator, "_is_port_bindable", side_effect=bindable_check):
            port = allocator.allocate(
                preferred=9000,
                range_start=10000,
                range_size=10,
            )

        assert port == 10000

    def test_allocate_skips_leased_ports(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Allocate skips ports already in registry."""
        # Pre-populate registry with leases
        registry_data = {
            "10000": {"pid": 1234, "timestamp": time.time()},
            "10001": {"pid": 1234, "timestamp": time.time()},
        }
        allocator.registry_file.write_text(json.dumps(registry_data))

        with patch.object(allocator, "_is_port_bindable", return_value=True):
            port = allocator.allocate(range_start=10000, range_size=10)

        assert port == 10002

    def test_allocate_skips_non_bindable_ports(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Allocate skips ports that fail binding check."""

        def bindable_check(port, host="127.0.0.1"):
            return port >= 10005  # First 5 ports not bindable

        with patch.object(allocator, "_is_port_bindable", side_effect=bindable_check):
            port = allocator.allocate(range_start=10000, range_size=10)

        assert port == 10005

    def test_allocate_records_lease(self, allocator: CrossProcessPortAllocator) -> None:
        """Allocate records lease with pid and timestamp."""
        with (
            patch.object(allocator, "_is_port_bindable", return_value=True),
            patch("time.time", return_value=1234567890.0),
            patch("os.getpid", return_value=9999),
        ):
            port = allocator.allocate(range_start=10000, range_size=10)

        registry = json.loads(allocator.registry_file.read_text())
        assert str(port) in registry
        assert registry[str(port)]["pid"] == 9999
        assert registry[str(port)]["timestamp"] == 1234567890.0

    def test_allocate_raises_on_exhaustion(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """RuntimeError raised when no ports available in range."""
        with patch.object(allocator, "_is_port_bindable", return_value=False):
            with pytest.raises(RuntimeError, match="No available ports"):
                allocator.allocate(range_start=10000, range_size=5)


class TestCrossProcessPortAllocatorRelease:
    """Tests for release method."""

    def test_release_removes_from_registry(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Release removes port entry from registry."""
        registry_data = {"10000": {"pid": 1234, "timestamp": time.time()}}
        allocator.registry_file.write_text(json.dumps(registry_data))

        allocator.release(10000)

        registry = json.loads(allocator.registry_file.read_text())
        assert "10000" not in registry

    def test_release_nonexistent_port_no_error(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Releasing nonexistent port doesn't raise error."""
        allocator.registry_file.write_text("{}")

        # Should not raise
        allocator.release(99999)

    def test_release_saves_registry(self, allocator: CrossProcessPortAllocator) -> None:
        """Release writes updated registry to file."""
        registry_data = {
            "10000": {"pid": 1234, "timestamp": time.time()},
            "10001": {"pid": 1234, "timestamp": time.time()},
        }
        allocator.registry_file.write_text(json.dumps(registry_data))

        allocator.release(10000)

        registry = json.loads(allocator.registry_file.read_text())
        assert "10000" not in registry
        assert "10001" in registry


class TestCrossProcessPortAllocatorRegistryIO:
    """Tests for _load and _save methods."""

    def test_load_returns_empty_for_missing_file(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Load returns empty dict when file doesn't exist."""
        assert not allocator.registry_file.exists()

        result = allocator._load()

        assert result == {}

    def test_load_parses_valid_json(self, allocator: CrossProcessPortAllocator) -> None:
        """Load correctly parses valid JSON registry."""
        registry_data = {"10000": {"pid": 1234, "timestamp": 1234567890.0}}
        allocator.registry_file.write_text(json.dumps(registry_data))

        result = allocator._load()

        assert result == registry_data

    def test_load_handles_malformed_json(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Load returns empty dict on JSON parse error."""
        allocator.registry_file.write_text("{invalid json")

        result = allocator._load()

        assert result == {}

    def test_load_handles_empty_file(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Load returns empty dict for empty file."""
        allocator.registry_file.write_text("")

        result = allocator._load()

        assert result == {}

    def test_save_writes_indented_json(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Save writes JSON with indent=2 formatting."""
        registry_data = {"10000": {"pid": 1234, "timestamp": 1234567890.0}}

        allocator._save(registry_data)

        content = allocator.registry_file.read_text()
        assert "  " in content  # Has indentation
        loaded = json.loads(content)
        assert loaded == registry_data


class TestCrossProcessPortAllocatorCleanup:
    """Tests for _cleanup_stale method."""

    def test_cleanup_stale_removes_old_leases(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Cleanup removes leases older than lease_timeout."""
        old_time = time.time() - allocator.lease_timeout - 100
        registry = {
            "10000": {"pid": 1234, "timestamp": old_time},
        }

        allocator._cleanup_stale(registry)

        assert "10000" not in registry

    def test_cleanup_stale_keeps_recent_leases(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Cleanup preserves leases within timeout."""
        recent_time = time.time() - 10  # 10 seconds ago
        registry = {
            "10000": {"pid": 1234, "timestamp": recent_time},
        }

        allocator._cleanup_stale(registry)

        assert "10000" in registry

    def test_cleanup_stale_handles_missing_timestamp(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Cleanup treats missing timestamp as expired (timestamp=0)."""
        registry = {
            "10000": {"pid": 1234},  # No timestamp
        }

        allocator._cleanup_stale(registry)

        assert "10000" not in registry

    def test_cleanup_stale_mixed_leases(
        self, allocator: CrossProcessPortAllocator
    ) -> None:
        """Cleanup correctly handles mix of old and recent leases."""
        old_time = time.time() - allocator.lease_timeout - 100
        recent_time = time.time() - 10

        registry = {
            "10000": {"pid": 1234, "timestamp": old_time},
            "10001": {"pid": 1234, "timestamp": recent_time},
            "10002": {"pid": 1234, "timestamp": old_time},
        }

        allocator._cleanup_stale(registry)

        assert "10000" not in registry
        assert "10001" in registry
        assert "10002" not in registry


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_allocator_returns_singleton(self, tmp_path: Path) -> None:
        """get_allocator returns same instance on multiple calls."""
        with patch("aidb_common.network.allocator.DEFAULT_REGISTRY_DIR", tmp_path):
            allocator1 = get_allocator()
            allocator2 = get_allocator()

        assert allocator1 is allocator2

    def test_get_allocator_with_custom_registry_dir(self, tmp_path: Path) -> None:
        """get_allocator uses custom registry_dir on first call."""
        allocator = get_allocator(registry_dir=tmp_path)

        assert allocator.registry_dir == tmp_path

    def test_allocate_port_delegates_to_allocator(self, tmp_path: Path) -> None:
        """allocate_port calls get_allocator().allocate()."""
        with patch("aidb_common.network.allocator.DEFAULT_REGISTRY_DIR", tmp_path):
            mock_allocator = MagicMock()
            mock_allocator.allocate.return_value = 12345

            with patch(
                "aidb_common.network.allocator.get_allocator",
                return_value=mock_allocator,
            ):
                result = allocate_port(preferred=9000, range_start=10000)

            mock_allocator.allocate.assert_called_once_with(
                9000, 10000, 1000, "127.0.0.1"
            )
            assert result == 12345

    def test_release_port_delegates_to_allocator(self, tmp_path: Path) -> None:
        """release_port calls get_allocator().release()."""
        with patch("aidb_common.network.allocator.DEFAULT_REGISTRY_DIR", tmp_path):
            mock_allocator = MagicMock()

            with patch(
                "aidb_common.network.allocator.get_allocator",
                return_value=mock_allocator,
            ):
                release_port(12345)

            mock_allocator.release.assert_called_once_with(12345)
