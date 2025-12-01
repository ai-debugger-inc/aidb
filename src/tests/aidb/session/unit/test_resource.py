"""Unit tests for ResourceManager.

Tests resource management including process registration, port acquisition, cleanup
operations, and lifecycle management.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock Session for resource manager tests."""
    session = MagicMock()
    session.id = "test-session-123"
    session.language = "python"
    session.adapter = MagicMock()
    session.adapter.config = MagicMock()
    session.adapter.config.process_termination_timeout = 1.0
    session.adapter._port = 5678
    session.adapter._attached_pid = None
    session.adapter._proc = None
    return session


@pytest.fixture
def resource_manager(mock_session: MagicMock, mock_ctx: MagicMock):
    """Create a ResourceManager instance for testing."""
    with patch("aidb.resources.pids.ProcessRegistry") as mock_proc_reg:
        with patch("aidb.resources.ports.PortRegistry") as mock_port_reg:
            mock_proc_instance = MagicMock()
            mock_port_instance = MagicMock()
            mock_proc_reg.return_value = mock_proc_instance
            mock_port_reg.return_value = mock_port_instance

            from aidb.session.resource import ResourceManager

            manager = ResourceManager(session=mock_session, ctx=mock_ctx)
            # Replace with mocks after initialization
            manager._process_registry = mock_proc_instance
            manager._port_registry = mock_port_instance
            return manager


class TestResourceManagerProcess:
    """Tests for process management."""

    def test_register_process_returns_pid(
        self,
        resource_manager,
        mock_ctx: MagicMock,
    ) -> None:
        """register_process returns PID of registered process."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.pid = 12345

        resource_manager._process_registry.register_process.return_value = 12345

        result = resource_manager.register_process(mock_proc)

        assert result == 12345

    def test_register_process_uses_process_group(
        self,
        resource_manager,
    ) -> None:
        """register_process passes process group flag to registry."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)

        resource_manager.register_process(mock_proc, use_process_group=True)

        resource_manager._process_registry.register_process.assert_called_once_with(
            "test-session-123",
            mock_proc,
            True,
        )

    def test_register_process_without_process_group(
        self,
        resource_manager,
    ) -> None:
        """register_process can disable process group tracking."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)

        resource_manager.register_process(mock_proc, use_process_group=False)

        resource_manager._process_registry.register_process.assert_called_once_with(
            "test-session-123",
            mock_proc,
            False,
        )

    def test_get_process_count_returns_count(
        self,
        resource_manager,
    ) -> None:
        """get_process_count returns number of registered processes."""
        resource_manager._process_registry.get_process_count.return_value = 3

        result = resource_manager.get_process_count()

        assert result == 3
        resource_manager._process_registry.get_process_count.assert_called_once_with(
            "test-session-123"
        )

    def test_get_process_count_returns_zero_when_empty(
        self,
        resource_manager,
    ) -> None:
        """get_process_count returns 0 when no processes registered."""
        resource_manager._process_registry.get_process_count.return_value = 0

        result = resource_manager.get_process_count()

        assert result == 0


class TestResourceManagerPort:
    """Tests for port management."""

    @pytest.mark.asyncio
    async def test_acquire_port_returns_port(
        self,
        resource_manager,
    ) -> None:
        """acquire_port returns acquired port number."""
        resource_manager._port_registry.acquire_port = AsyncMock(return_value=5678)

        with patch("aidb.session.adapter_registry.AdapterRegistry") as mock_registry:
            mock_config = MagicMock()
            mock_config.default_dap_port = 5678
            mock_config.fallback_port_ranges = [(5680, 5700)]
            mock_registry.return_value.__getitem__.return_value = mock_config

            result = await resource_manager.acquire_port()

        assert result == 5678

    @pytest.mark.asyncio
    async def test_acquire_port_with_start_port(
        self,
        resource_manager,
    ) -> None:
        """acquire_port uses start_port as preferred port."""
        resource_manager._port_registry.acquire_port = AsyncMock(return_value=9999)

        with patch("aidb.session.adapter_registry.AdapterRegistry") as mock_registry:
            mock_config = MagicMock()
            mock_config.default_dap_port = 5678
            mock_config.fallback_port_ranges = [(5680, 5700)]
            mock_registry.return_value.__getitem__.return_value = mock_config

            result = await resource_manager.acquire_port(start_port=9999)

        assert result == 9999

    @pytest.mark.asyncio
    async def test_acquire_port_raises_timeout_error(
        self,
        resource_manager,
        mock_ctx: MagicMock,
    ) -> None:
        """acquire_port raises TimeoutError after 30s timeout."""

        async def slow_acquire(*args, **kwargs):
            await asyncio.sleep(100)

        resource_manager._port_registry.acquire_port = slow_acquire

        with patch("aidb.session.adapter_registry.AdapterRegistry") as mock_registry:
            mock_config = MagicMock()
            mock_config.default_dap_port = 5678
            mock_config.fallback_port_ranges = [(5680, 5700)]
            mock_registry.return_value.__getitem__.return_value = mock_config

            # Use a shorter timeout for testing
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                with pytest.raises(TimeoutError, match="Port acquisition timed out"):
                    await resource_manager.acquire_port()

    def test_release_port_removes_port(
        self,
        resource_manager,
    ) -> None:
        """release_port releases port from registry."""
        result = resource_manager.release_port(5678)

        resource_manager._port_registry.release_port.assert_called_once_with(
            5678, session_id="test-session-123"
        )
        assert result == "test-session-123"

    def test_get_port_count_returns_count(
        self,
        resource_manager,
    ) -> None:
        """get_port_count returns number of registered ports."""
        resource_manager._port_registry.get_port_count.return_value = 2

        result = resource_manager.get_port_count()

        assert result == 2
        resource_manager._port_registry.get_port_count.assert_called_once_with(
            session_id="test-session-123"
        )


class TestResourceManagerCleanup:
    """Tests for cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_all_resources_terminates_processes(
        self,
        resource_manager,
    ) -> None:
        """cleanup_all_resources terminates session processes."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(3, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = [
            5678,
            5679,
        ]

        result = await resource_manager.cleanup_all_resources()

        assert result["terminated_processes"] == 3
        assert result["failed_processes"] == 0
        resource_manager._process_registry.terminate_session_processes.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_all_resources_releases_ports(
        self,
        resource_manager,
    ) -> None:
        """cleanup_all_resources releases session ports."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = [
            5678,
            5679,
            5680,
        ]

        result = await resource_manager.cleanup_all_resources()

        assert result["released_ports"] == 3
        resource_manager._port_registry.release_session_ports.assert_called_once_with(
            session_id="test-session-123"
        )

    @pytest.mark.asyncio
    async def test_cleanup_all_resources_returns_summary(
        self,
        resource_manager,
    ) -> None:
        """cleanup_all_resources returns complete summary."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(2, 1)
        )
        resource_manager._port_registry.release_session_ports.return_value = [5678]

        result = await resource_manager.cleanup_all_resources()

        assert result["session_id"] == "test-session-123"
        assert result["terminated_processes"] == 2
        assert result["failed_processes"] == 1
        assert result["released_ports"] == 1

    @pytest.mark.asyncio
    async def test_comprehensive_cleanup_with_fallback_includes_standard(
        self,
        resource_manager,
    ) -> None:
        """comprehensive_cleanup_with_fallback includes standard cleanup."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(1, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        with patch.object(
            resource_manager, "cleanup_main_process", new_callable=AsyncMock
        ) as mock_main:
            mock_main.return_value = True

            result = await resource_manager.comprehensive_cleanup_with_fallback()

        assert result["comprehensive_cleanup"] is True
        assert "terminated_processes" in result

    @pytest.mark.asyncio
    async def test_comprehensive_cleanup_with_main_process(
        self,
        resource_manager,
    ) -> None:
        """comprehensive_cleanup_with_fallback cleans up main process."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        mock_main_proc = MagicMock(spec=asyncio.subprocess.Process)

        with patch.object(
            resource_manager, "cleanup_main_process", new_callable=AsyncMock
        ) as mock_cleanup:
            mock_cleanup.return_value = True

            result = await resource_manager.comprehensive_cleanup_with_fallback(
                main_proc=mock_main_proc
            )

        assert result["main_process_cleanup_successful"] is True
        mock_cleanup.assert_called_once_with(mock_main_proc)

    @pytest.mark.asyncio
    async def test_comprehensive_cleanup_with_attached_pid(
        self,
        resource_manager,
    ) -> None:
        """comprehensive_cleanup_with_fallback terminates process group."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        with patch.object(
            resource_manager, "terminate_process_group", new_callable=AsyncMock
        ) as mock_term:
            mock_term.return_value = True

            result = await resource_manager.comprehensive_cleanup_with_fallback(
                attached_pid=12345
            )

        assert result["process_group_cleanup_attempted"] is True
        mock_term.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_terminate_processes_by_pattern_finds_processes(
        self,
        resource_manager,
    ) -> None:
        """terminate_processes_by_pattern finds matching processes."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 12345,
            "name": "python",
            "cmdline": ["python", "debugpy", "--listen", "5678"],
        }
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("psutil.process_iter", return_value=[mock_proc]):
            with patch.object(
                resource_manager, "_terminate_single_process", new_callable=AsyncMock
            ) as mock_term:
                mock_term.return_value = 1

                result = await resource_manager.terminate_processes_by_pattern(
                    port=5678,
                    process_pattern="debugpy",
                )

        assert result == 1

    @pytest.mark.asyncio
    async def test_terminate_processes_by_pattern_returns_zero_without_port(
        self,
        resource_manager,
    ) -> None:
        """terminate_processes_by_pattern returns 0 without port."""
        result = await resource_manager.terminate_processes_by_pattern(
            port=None,
            process_pattern="debugpy",
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_terminate_process_group_terminates_group(
        self,
        resource_manager,
    ) -> None:
        """terminate_process_group terminates process group."""
        with patch.object(
            resource_manager, "_try_terminate_process_group", new_callable=AsyncMock
        ) as mock_group:
            mock_group.return_value = True

            result = await resource_manager.terminate_process_group(12345)

        assert result is True

    @pytest.mark.asyncio
    async def test_terminate_process_group_returns_false_without_pid(
        self,
        resource_manager,
    ) -> None:
        """terminate_process_group returns False without PID."""
        result = await resource_manager.terminate_process_group(0)

        assert result is False

    @pytest.mark.asyncio
    async def test_terminate_process_group_fallback_to_direct(
        self,
        resource_manager,
    ) -> None:
        """terminate_process_group falls back to direct termination."""
        with patch.object(
            resource_manager, "_try_terminate_process_group", new_callable=AsyncMock
        ) as mock_group:
            mock_group.return_value = False

            with patch.object(
                resource_manager,
                "_try_terminate_process_directly",
                new_callable=AsyncMock,
            ) as mock_direct:
                mock_direct.return_value = True

                result = await resource_manager.terminate_process_group(12345)

        assert result is True
        mock_direct.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_cleanup_main_process_terminates_gracefully(
        self,
        resource_manager,
    ) -> None:
        """cleanup_main_process terminates process gracefully."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.returncode = None
        mock_proc.pid = 12345
        mock_proc.terminate = MagicMock()
        mock_proc.wait = AsyncMock()

        result = await resource_manager.cleanup_main_process(mock_proc)

        assert result is True
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_main_process_returns_true_if_already_terminated(
        self,
        resource_manager,
    ) -> None:
        """cleanup_main_process returns True if process already terminated."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.returncode = 0  # Already terminated

        result = await resource_manager.cleanup_main_process(mock_proc)

        assert result is True

    @pytest.mark.asyncio
    async def test_cleanup_main_process_force_kills_on_timeout(
        self,
        resource_manager,
    ) -> None:
        """cleanup_main_process force kills if terminate times out."""
        mock_proc = MagicMock(spec=asyncio.subprocess.Process)
        mock_proc.returncode = None
        mock_proc.pid = 12345
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()

        # First wait (after terminate) times out, second wait (after kill) succeeds
        call_count = 0

        async def wait_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            mock_proc.returncode = -9  # Killed

        mock_proc.wait = wait_side_effect

        result = await resource_manager.cleanup_main_process(mock_proc)

        assert result is True
        mock_proc.kill.assert_called_once()


class TestResourceManagerLifecycle:
    """Tests for IResourceLifecycle implementation."""

    @pytest.mark.asyncio
    async def test_acquire_resources_sets_flag(
        self,
        resource_manager,
    ) -> None:
        """acquire_resources sets _resources_acquired flag."""
        assert resource_manager._resources_acquired is False

        await resource_manager.acquire_resources()

        assert resource_manager._resources_acquired is True

    @pytest.mark.asyncio
    async def test_acquire_resources_idempotent(
        self,
        resource_manager,
        mock_ctx: MagicMock,
    ) -> None:
        """acquire_resources is idempotent."""
        await resource_manager.acquire_resources()
        await resource_manager.acquire_resources()

        assert resource_manager._resources_acquired is True

    @pytest.mark.asyncio
    async def test_release_resources_returns_summary(
        self,
        resource_manager,
    ) -> None:
        """release_resources returns cleanup summary."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(1, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = [5678]

        result = await resource_manager.release_resources()

        assert result["session_id"] == "test-session-123"
        assert result["terminated_processes"] == 1
        assert result["released_ports"] == 1

    @pytest.mark.asyncio
    async def test_release_resources_marks_completed(
        self,
        resource_manager,
    ) -> None:
        """release_resources sets _cleanup_completed flag."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        await resource_manager.release_resources()

        assert resource_manager._cleanup_completed is True

    @pytest.mark.asyncio
    async def test_release_resources_idempotent(
        self,
        resource_manager,
    ) -> None:
        """release_resources is idempotent."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        await resource_manager.release_resources()
        result = await resource_manager.release_resources()

        assert result["status"] == "already_cleaned"

    def test_get_resource_state_returns_dict(
        self,
        resource_manager,
    ) -> None:
        """get_resource_state returns resource state dict."""
        resource_manager._process_registry.get_process_count.return_value = 2
        resource_manager._port_registry.get_port_count.return_value = 1

        result = resource_manager.get_resource_state()

        assert result["session_id"] == "test-session-123"
        assert result["resources_acquired"] is False
        assert result["cleanup_completed"] is False
        assert result["process_count"] == 2
        assert result["port_count"] == 1
        assert result["health_status"] == "healthy"

    def test_get_resource_state_shows_cleaned_status(
        self,
        resource_manager,
    ) -> None:
        """get_resource_state shows 'cleaned' status after cleanup."""
        resource_manager._cleanup_completed = True
        resource_manager._process_registry.get_process_count.return_value = 0
        resource_manager._port_registry.get_port_count.return_value = 0

        result = resource_manager.get_resource_state()

        assert result["health_status"] == "cleaned"

    @pytest.mark.asyncio
    async def test_resource_scope_context_manager(
        self,
        resource_manager,
    ) -> None:
        """resource_scope acquires and releases resources."""
        resource_manager._process_registry.terminate_session_processes = AsyncMock(
            return_value=(0, 0)
        )
        resource_manager._port_registry.release_session_ports.return_value = []

        async with resource_manager.resource_scope():
            assert resource_manager._resources_acquired is True

        assert resource_manager._cleanup_completed is True

    def test_get_resource_usage_returns_stats(
        self,
        resource_manager,
    ) -> None:
        """get_resource_usage returns resource usage statistics."""
        resource_manager._process_registry.get_process_count.return_value = 3
        resource_manager._port_registry.get_port_count.return_value = 2

        result = resource_manager.get_resource_usage()

        assert result["session_id"] == "test-session-123"
        assert result["process_count"] == 3
        assert result["port_count"] == 2
        assert result["total_resources"] == 5


class TestResourceManagerHelpers:
    """Tests for helper methods."""

    def test_should_terminate_process_matches_pattern_and_port(
        self,
        resource_manager,
    ) -> None:
        """_should_terminate_process matches pattern and port."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "cmdline": ["python", "-m", "debugpy", "--listen", "5678"],
        }

        result = resource_manager._should_terminate_process(mock_proc, 5678, "debugpy")

        assert result is True

    def test_should_terminate_process_returns_false_without_pattern(
        self,
        resource_manager,
    ) -> None:
        """_should_terminate_process returns False without pattern match."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "cmdline": ["python", "script.py", "--listen", "5678"],
        }

        result = resource_manager._should_terminate_process(mock_proc, 5678, "debugpy")

        assert result is False

    def test_should_terminate_process_returns_false_without_port(
        self,
        resource_manager,
    ) -> None:
        """_should_terminate_process returns False without port match."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "cmdline": ["python", "-m", "debugpy", "--listen", "9999"],
        }

        result = resource_manager._should_terminate_process(mock_proc, 5678, "debugpy")

        assert result is False

    def test_should_terminate_process_returns_false_for_empty_cmdline(
        self,
        resource_manager,
    ) -> None:
        """_should_terminate_process returns False for empty cmdline."""
        mock_proc = MagicMock()
        mock_proc.info = {"cmdline": None}

        result = resource_manager._should_terminate_process(mock_proc, 5678, "debugpy")

        assert result is False

    def test_get_session_resource_usage_returns_stats(
        self,
        resource_manager,
    ) -> None:
        """get_session_resource_usage returns usage statistics."""
        resource_manager._process_registry.get_process_count.return_value = 1
        resource_manager._port_registry.get_port_count.return_value = 1

        result = resource_manager.get_session_resource_usage()

        assert result["session_id"] == "test-session-123"
        assert result["process_count"] == 1

    def test_get_session_resource_usage_handles_error(
        self,
        resource_manager,
    ) -> None:
        """get_session_resource_usage handles errors gracefully."""
        resource_manager._process_registry.get_process_count.side_effect = RuntimeError(
            "Test error"
        )

        result = resource_manager.get_session_resource_usage()

        assert result["session_id"] == "test-session-123"
        assert "error" in result
        assert result["process_count"] == -1
