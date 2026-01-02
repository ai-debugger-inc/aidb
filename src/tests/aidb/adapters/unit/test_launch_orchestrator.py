"""Unit tests for LaunchOrchestrator.

Tests launch orchestration including direct launches, config-based launches, and failure
handling.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aidb.adapters.base.components.launch_orchestrator import LaunchOrchestrator
from aidb.common.errors import AidbError, DebugConnectionError

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_adapter(mock_ctx: MagicMock) -> MagicMock:
    """Create a mock adapter for orchestrator testing."""
    adapter = MagicMock()
    adapter.ctx = mock_ctx
    adapter.session = MagicMock()
    adapter.session.id = "test-session-123"
    adapter.session.resource = MagicMock()
    adapter.session.resource.register_process = MagicMock()
    adapter.config = MagicMock()
    adapter.config.language = "python"
    adapter.adapter_host = "localhost"
    adapter.adapter_port = None
    adapter._build_launch_command = AsyncMock(
        return_value=["python", "-m", "debugpy", "--listen", "5678"],
    )
    adapter._prepare_environment = MagicMock(return_value={"PATH": "/usr/bin"})
    return adapter


@pytest.fixture
def mock_process_manager() -> MagicMock:
    """Create a mock process manager."""
    pm = MagicMock()
    pm.launch_subprocess = AsyncMock()
    pm.wait_for_adapter_ready = AsyncMock()
    pm.log_process_output = AsyncMock()
    return pm


@pytest.fixture
def mock_port_manager() -> MagicMock:
    """Create a mock port manager."""
    pm = MagicMock()
    pm.acquire = AsyncMock(return_value=5678)
    return pm


@pytest.fixture
def launch_orchestrator(
    mock_adapter: MagicMock,
    mock_process_manager: MagicMock,
    mock_port_manager: MagicMock,
    mock_ctx: MagicMock,
) -> LaunchOrchestrator:
    """Create a LaunchOrchestrator instance for testing."""
    return LaunchOrchestrator(
        adapter=mock_adapter,
        process_manager=mock_process_manager,
        port_manager=mock_port_manager,
        ctx=mock_ctx,
    )


@pytest.fixture
def mock_launch_config() -> MagicMock:
    """Create a mock launch configuration."""
    config = MagicMock()
    config.port = None
    config.cwd = None
    config.env = None
    config.to_adapter_args = MagicMock(
        return_value={"target": "test.py", "port": None, "args": []},
    )
    return config


# =============================================================================
# TestLaunchOrchestratorInit
# =============================================================================


class TestLaunchOrchestratorInit:
    """Tests for LaunchOrchestrator initialization."""

    def test_init_sets_adapter(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test initialization sets adapter reference."""
        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
        )

        assert orchestrator.adapter is mock_adapter

    def test_init_sets_session(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test initialization sets session reference."""
        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
        )

        assert orchestrator.session is mock_adapter.session

    def test_init_sets_process_manager(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test initialization sets process manager reference."""
        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
        )

        assert orchestrator.process_manager is mock_process_manager

    def test_init_sets_port_manager(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test initialization sets port manager reference."""
        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
        )

        assert orchestrator.port_manager is mock_port_manager

    def test_init_uses_adapter_ctx_by_default(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test initialization uses adapter's context by default."""
        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
        )

        assert orchestrator.ctx is mock_adapter.ctx

    def test_init_can_use_custom_ctx(
        self,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
        mock_port_manager: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test initialization can use custom context."""
        custom_ctx = MagicMock()

        orchestrator = LaunchOrchestrator(
            adapter=mock_adapter,
            process_manager=mock_process_manager,
            port_manager=mock_port_manager,
            ctx=custom_ctx,
        )

        assert orchestrator.ctx is custom_ctx


# =============================================================================
# TestLaunchOrchestratorLaunch
# =============================================================================


class TestLaunchOrchestratorLaunch:
    """Tests for launch() method."""

    @pytest.mark.asyncio
    async def test_launch_calls_internal_launch(
        self,
        launch_orchestrator: LaunchOrchestrator,
    ) -> None:
        """Test launch delegates to _launch_internal."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with patch.object(
            launch_orchestrator,
            "_launch_internal",
            new_callable=AsyncMock,
            return_value=(mock_proc, 5678),
        ) as mock_internal:
            result = await launch_orchestrator.launch(
                target="test.py",
                port=5678,
                args=["--debug"],
            )

        mock_internal.assert_called_once_with("test.py", 5678, ["--debug"], None)
        assert result == (mock_proc, 5678)


# =============================================================================
# TestLaunchOrchestratorLaunchWithConfig
# =============================================================================


class TestLaunchOrchestratorLaunchWithConfig:
    """Tests for launch_with_config() method."""

    @pytest.mark.asyncio
    async def test_launch_with_config_delegates(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test launch_with_config delegates to _launch_with_config."""
        mock_proc = MagicMock()

        with patch.object(
            launch_orchestrator,
            "_launch_with_config",
            new_callable=AsyncMock,
            return_value=(mock_proc, 5678),
        ) as mock_internal:
            result = await launch_orchestrator.launch_with_config(
                launch_config=mock_launch_config,
                port=5678,
                workspace_root="/workspace",
            )

        mock_internal.assert_called_once_with(mock_launch_config, 5678, "/workspace")
        assert result == (mock_proc, 5678)


# =============================================================================
# TestLaunchOrchestratorLaunchWithConfigInternal
# =============================================================================


class TestLaunchOrchestratorLaunchWithConfigInternal:
    """Tests for _launch_with_config() method."""

    @pytest.mark.asyncio
    async def test_converts_config_to_adapter_args(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test converts launch config to adapter args."""
        mock_proc = MagicMock()

        with patch.object(
            launch_orchestrator,
            "_launch_internal",
            new_callable=AsyncMock,
            return_value=(mock_proc, 5678),
        ):
            await launch_orchestrator._launch_with_config(
                mock_launch_config,
                workspace_root="/workspace",
            )

        mock_launch_config.to_adapter_args.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_port_from_adapter_args(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test uses port from adapter_args if returned by to_adapter_args."""
        # to_adapter_args returns port
        mock_launch_config.to_adapter_args.return_value = {
            "target": "test.py",
            "port": 9999,
        }
        mock_proc = MagicMock()

        with patch.object(
            launch_orchestrator,
            "_launch_internal",
            new_callable=AsyncMock,
            return_value=(mock_proc, 9999),
        ) as mock_internal:
            await launch_orchestrator._launch_with_config(mock_launch_config)

        # Port from adapter_args should be passed
        mock_internal.assert_called_once()
        call_args = mock_internal.call_args
        assert call_args.kwargs.get("port") == 9999

    @pytest.mark.asyncio
    async def test_overrides_port_from_parameter(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test parameter port overrides config port."""
        mock_launch_config.port = 9999
        mock_launch_config.to_adapter_args.return_value = {"target": "test.py"}
        mock_proc = MagicMock()

        with patch.object(
            launch_orchestrator,
            "_launch_internal",
            new_callable=AsyncMock,
            return_value=(mock_proc, 5678),
        ) as mock_internal:
            await launch_orchestrator._launch_with_config(
                mock_launch_config,
                port=5678,
            )

        # Parameter port should override
        call_args = mock_internal.call_args[0]
        assert 5678 in call_args or mock_internal.call_args[1].get("port") == 5678

    @pytest.mark.asyncio
    async def test_changes_cwd_if_specified(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test changes working directory if cwd specified."""
        mock_launch_config.cwd = "/custom/path"
        mock_proc = MagicMock()

        with (
            patch("os.chdir") as mock_chdir,
            patch.object(
                launch_orchestrator,
                "_launch_internal",
                new_callable=AsyncMock,
                return_value=(mock_proc, 5678),
            ),
        ):
            await launch_orchestrator._launch_with_config(mock_launch_config)

        mock_chdir.assert_called_once_with("/custom/path")

    @pytest.mark.asyncio
    async def test_updates_env_if_specified(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_launch_config: MagicMock,
    ) -> None:
        """Test updates environment if env specified."""
        mock_launch_config.env = {"CUSTOM_VAR": "value"}
        mock_proc = MagicMock()

        with (
            patch.dict("os.environ", {}, clear=False),
            patch.object(
                launch_orchestrator,
                "_launch_internal",
                new_callable=AsyncMock,
                return_value=(mock_proc, 5678),
            ),
        ):
            await launch_orchestrator._launch_with_config(mock_launch_config)


# =============================================================================
# TestLaunchOrchestratorLaunchInternal
# =============================================================================


class TestLaunchOrchestratorLaunchInternal:
    """Tests for _launch_internal() method."""

    @pytest.mark.asyncio
    async def test_acquires_port(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_port_manager: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test acquires port via port manager."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")

        mock_port_manager.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_requested_port(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_port_manager: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test uses requested port if available."""
        mock_port_manager.acquire.return_value = 9999
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            result = await launch_orchestrator._launch_internal(
                "test.py",
                port=9999,
            )

        mock_port_manager.acquire.assert_called_once_with(requested_port=9999)
        assert result[1] == 9999

    @pytest.mark.asyncio
    async def test_raises_on_port_acquisition_failure(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_port_manager: MagicMock,
    ) -> None:
        """Test raises when port acquisition fails."""
        mock_port_manager.acquire.side_effect = AidbError("No ports available")

        with pytest.raises(AidbError, match="No ports available"):
            await launch_orchestrator._launch_internal("test.py")

    @pytest.mark.asyncio
    async def test_updates_adapter_port(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test updates adapter's adapter_port."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")

        assert mock_adapter.adapter_port == 5678

    @pytest.mark.asyncio
    async def test_builds_launch_command(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test builds launch command via adapter."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal(
                "test.py",
                args=["--arg1"],
            )

        mock_adapter._build_launch_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_launches_subprocess(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """Test launches subprocess via process manager."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")

        mock_process_manager.launch_subprocess.assert_called_once()
        call_kwargs = mock_process_manager.launch_subprocess.call_args[1]
        assert call_kwargs["session_id"] == "test-session-123"
        assert call_kwargs["language"] == "python"

    @pytest.mark.asyncio
    async def test_registers_process_with_resource_manager(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
        mock_adapter: MagicMock,
    ) -> None:
        """Test registers process with resource manager."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")

        mock_adapter.session.resource.register_process.assert_called_once_with(
            mock_proc,
        )

    @pytest.mark.asyncio
    async def test_waits_for_adapter_ready(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test waits for adapter to be ready."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")

        mock_process_manager.wait_for_adapter_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_process_and_port(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test returns launched process and port."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            result = await launch_orchestrator._launch_internal("test.py")

        assert result == (mock_proc, 5678)

    @pytest.mark.asyncio
    async def test_handles_wait_failure(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test handles failure during wait for adapter."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc
        mock_process_manager.wait_for_adapter_ready.side_effect = TimeoutError(
            "Timed out",
        )

        with (
            patch(
                "aidb.resources.ports.PortRegistry",
            ) as mock_registry,
            patch.object(
                launch_orchestrator,
                "_handle_launch_failure",
                new_callable=AsyncMock,
            ),
            pytest.raises(DebugConnectionError),
        ):
            mock_registry.return_value.release_reserved_port = MagicMock()
            await launch_orchestrator._launch_internal("test.py")


# =============================================================================
# TestLaunchOrchestratorHandleLaunchFailure
# =============================================================================


class TestLaunchOrchestratorHandleLaunchFailure:
    """Tests for _handle_launch_failure() method."""

    @pytest.mark.asyncio
    async def test_logs_error_with_timing(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_ctx: MagicMock,
    ) -> None:
        """Test logs error with wait timing."""
        start_time = time.monotonic()
        error = TimeoutError("Connection timed out")

        await launch_orchestrator._handle_launch_failure(error, start_time)

        mock_ctx.error.assert_called()

    @pytest.mark.asyncio
    async def test_logs_process_output(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test logs process output on failure."""
        start_time = time.monotonic()
        error = TimeoutError("Connection timed out")

        await launch_orchestrator._handle_launch_failure(error, start_time)

        mock_process_manager.log_process_output.assert_called_once()


# =============================================================================
# TestLaunchOrchestratorLogLaunchInfo
# =============================================================================


class TestLaunchOrchestratorLogLaunchInfo:
    """Tests for _log_launch_info() method."""

    def test_logs_command(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_ctx: MagicMock,
    ) -> None:
        """Test logs launch command."""
        cmd = ["python", "-m", "debugpy"]
        env = {"PATH": "/usr/bin"}

        launch_orchestrator._log_launch_info(cmd, env)

        mock_ctx.debug.assert_called()

    def test_filters_environment_variables(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_ctx: MagicMock,
    ) -> None:
        """Test filters relevant environment variables."""
        cmd = ["python", "-m", "debugpy"]
        env = {
            "PATH": "/usr/bin",
            "PYTHONPATH": "/lib",
            "VIRTUAL_ENV": "/venv",
            "DEBUG_MODE": "true",
            "UNRELATED": "value",
        }

        launch_orchestrator._log_launch_info(cmd, env)

        # Should have been called with debug info
        assert mock_ctx.debug.call_count >= 2


# =============================================================================
# TestLaunchOrchestratorSkipResourceRegistration
# =============================================================================


class TestLaunchOrchestratorNoResourceManager:
    """Tests for launch when session has no resource manager."""

    @pytest.mark.asyncio
    async def test_skips_registration_without_resource_manager(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test skips process registration when no resource manager."""
        mock_adapter.session.resource = None
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            result = await launch_orchestrator._launch_internal("test.py")

        assert result == (mock_proc, 5678)

    @pytest.mark.asyncio
    async def test_handles_session_without_resource_attr(
        self,
        launch_orchestrator: LaunchOrchestrator,
        mock_adapter: MagicMock,
        mock_process_manager: MagicMock,
    ) -> None:
        """Test handles session without resource attribute."""
        del mock_adapter.session.resource  # Remove attribute
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_process_manager.launch_subprocess.return_value = mock_proc

        with patch(
            "aidb.resources.ports.PortRegistry",
        ) as mock_registry:
            mock_registry.return_value.release_reserved_port = MagicMock()
            result = await launch_orchestrator._launch_internal("test.py")

        assert result == (mock_proc, 5678)
