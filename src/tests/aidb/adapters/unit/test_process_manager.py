"""Unit tests for ProcessManager.

Tests process lifecycle management including launching, stopping, orphan cleanup, and
property accessors.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from aidb.adapters.base.components.process_manager import ProcessManager
from aidb.common.errors import DebugAdapterError, DebugConnectionError
from aidb.resources.process_tags import ProcessTags

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def process_manager(mock_ctx: MagicMock) -> ProcessManager:
    """Create a ProcessManager instance for testing."""
    return ProcessManager(ctx=mock_ctx, adapter_host="localhost")


@pytest.fixture
def process_manager_with_config(mock_ctx: MagicMock) -> ProcessManager:
    """Create a ProcessManager with config for timeout testing."""
    config = MagicMock()
    config.process_manager_timeout = 2.0
    return ProcessManager(ctx=mock_ctx, adapter_host="localhost", config=config)


@pytest.fixture
def mock_psutil_process() -> MagicMock:
    """Create a mock psutil.Process."""
    proc = MagicMock(spec=psutil.Process)
    proc.pid = 12345
    proc.children = MagicMock(return_value=[])
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = MagicMock()
    proc.is_running = MagicMock(return_value=True)
    proc.environ = MagicMock(return_value={})
    proc.info = {
        "pid": 12345,
        "ppid": 1,
        "cmdline": ["python", "test.py"],
        "create_time": 0,
    }
    return proc


@pytest.fixture
def mock_child_process() -> MagicMock:
    """Create a mock child psutil.Process."""
    child = MagicMock(spec=psutil.Process)
    child.pid = 12346
    child.terminate = MagicMock()
    child.kill = MagicMock()
    child.is_running = MagicMock(return_value=True)
    return child


# =============================================================================
# TestProcessManagerInit
# =============================================================================


class TestProcessManagerInit:
    """Tests for ProcessManager initialization."""

    def test_init_defaults(self, mock_ctx: MagicMock) -> None:
        """Test initialization with default values."""
        pm = ProcessManager(ctx=mock_ctx)

        assert pm.adapter_host == "localhost"
        assert pm.config is None
        assert pm._proc is None
        assert pm._attached_pid is None
        assert pm._output_capture is None

    def test_init_with_custom_host(self, mock_ctx: MagicMock) -> None:
        """Test initialization with custom host."""
        pm = ProcessManager(ctx=mock_ctx, adapter_host="127.0.0.1")

        assert pm.adapter_host == "127.0.0.1"

    def test_init_with_config(self, mock_ctx: MagicMock) -> None:
        """Test initialization with config."""
        config = MagicMock()
        config.process_manager_timeout = 5.0
        pm = ProcessManager(ctx=mock_ctx, config=config)

        assert pm.config is config


# =============================================================================
# TestProcessManagerProperties
# =============================================================================


class TestProcessManagerProperties:
    """Tests for ProcessManager properties."""

    def test_pid_returns_none_when_no_process(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test pid returns None when no process is running."""
        assert process_manager.pid is None

    def test_pid_returns_attached_pid_when_set(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test pid returns attached PID when set."""
        process_manager._attached_pid = 9999

        assert process_manager.pid == 9999

    def test_pid_returns_proc_pid_when_process_running(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test pid returns process PID when running."""
        process_manager._proc = mock_asyncio_process

        assert process_manager.pid == 12345

    def test_pid_prefers_attached_pid_over_proc(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test attached PID takes precedence over proc PID."""
        process_manager._attached_pid = 9999
        process_manager._proc = mock_asyncio_process

        assert process_manager.pid == 9999

    def test_is_alive_returns_false_when_no_process(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test is_alive returns False when no process."""
        assert process_manager.is_alive is False

    def test_is_alive_returns_true_when_process_running(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test is_alive returns True when process is running."""
        mock_asyncio_process.returncode = None
        process_manager._proc = mock_asyncio_process

        assert process_manager.is_alive is True

    def test_is_alive_returns_false_when_process_exited(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process_exited: MagicMock,
    ) -> None:
        """Test is_alive returns False when process has exited."""
        process_manager._proc = mock_asyncio_process_exited

        assert process_manager.is_alive is False


# =============================================================================
# TestProcessManagerLaunchSubprocess
# =============================================================================


class TestProcessManagerLaunchSubprocess:
    """Tests for launch_subprocess method."""

    @pytest.mark.asyncio
    async def test_launch_subprocess_success(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test successful subprocess launch."""
        mock_output_capture = MagicMock()
        mock_output_capture.start_capture_async = AsyncMock()

        with (
            patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=mock_asyncio_process,
            ) as mock_create,
            patch(
                "aidb.adapters.base.components.process_manager.AdapterOutputCapture",
                return_value=mock_output_capture,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await process_manager.launch_subprocess(
                cmd=["python", "-m", "debugpy"],
                env={"PATH": "/usr/bin"},
                session_id="test-session",
                language="python",
            )

        assert result is mock_asyncio_process
        assert process_manager._proc is mock_asyncio_process
        mock_create.assert_called_once()
        mock_output_capture.start_capture_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_launch_subprocess_injects_process_tags(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test that launch injects AIDB process tags into environment."""
        captured_env = {}

        async def capture_env(*args, **kwargs):
            captured_env.update(kwargs.get("env", {}))
            return mock_asyncio_process

        mock_output_capture = MagicMock()
        mock_output_capture.start_capture_async = AsyncMock()

        with (
            patch("asyncio.create_subprocess_exec", side_effect=capture_env),
            patch(
                "aidb.adapters.base.components.process_manager.AdapterOutputCapture",
                return_value=mock_output_capture,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await process_manager.launch_subprocess(
                cmd=["python", "-m", "debugpy"],
                env={"EXISTING": "value"},
                session_id="session-123",
                language="python",
                process_type="adapter",
            )

        assert captured_env[ProcessTags.OWNER] == ProcessTags.OWNER_VALUE
        assert captured_env[ProcessTags.SESSION_ID] == "session-123"
        assert captured_env[ProcessTags.PROCESS_TYPE] == "adapter"
        assert captured_env[ProcessTags.LANGUAGE] == "python"
        assert ProcessTags.START_TIME in captured_env
        assert captured_env["EXISTING"] == "value"

    @pytest.mark.asyncio
    async def test_launch_subprocess_raises_on_immediate_exit(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process_failed: MagicMock,
    ) -> None:
        """Test that launch raises when process exits immediately."""
        with (
            patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=mock_asyncio_process_failed,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(DebugAdapterError, match="exited immediately"),
        ):
            await process_manager.launch_subprocess(
                cmd=["python", "bad_script.py"],
                env={},
                session_id="test-session",
                language="python",
            )

    @pytest.mark.asyncio
    async def test_launch_subprocess_with_custom_kwargs(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test launch with additional kwargs."""
        mock_output_capture = MagicMock()
        mock_output_capture.start_capture_async = AsyncMock()

        with (
            patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
                return_value=mock_asyncio_process,
            ) as mock_create,
            patch(
                "aidb.adapters.base.components.process_manager.AdapterOutputCapture",
                return_value=mock_output_capture,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await process_manager.launch_subprocess(
                cmd=["python", "test.py"],
                env={},
                session_id="test",
                language="python",
                kwargs={"cwd": "/tmp"},
            )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"


# =============================================================================
# TestProcessManagerWaitForAdapterReady
# =============================================================================


class TestProcessManagerWaitForAdapterReady:
    """Tests for wait_for_adapter_ready method."""

    @pytest.mark.asyncio
    async def test_wait_raises_when_no_process(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test that wait raises when no process is set."""
        with pytest.raises(DebugAdapterError, match="No process to wait for"):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic(),
            )

    @pytest.mark.asyncio
    async def test_wait_success_on_first_attempt(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test successful wait on first attempt."""
        process_manager._proc = mock_asyncio_process

        mock_port_handler = MagicMock()
        mock_port_handler.wait_for_port = AsyncMock(return_value=True)

        with patch(
            "aidb.adapters.base.components.process_manager.PortHandler",
            return_value=mock_port_handler,
        ):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic(),
            )

        mock_port_handler.wait_for_port.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_retries_on_failure(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test that wait retries on port not ready."""
        process_manager._proc = mock_asyncio_process

        mock_port_handler = MagicMock()
        mock_port_handler.wait_for_port = AsyncMock(
            side_effect=[False, False, True],
        )

        with (
            patch(
                "aidb.adapters.base.components.process_manager.PortHandler",
                return_value=mock_port_handler,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic(),
                max_retries=3,
            )

        assert mock_port_handler.wait_for_port.call_count == 3

    @pytest.mark.asyncio
    async def test_wait_raises_on_max_retries_exhausted(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test that wait raises after max retries exhausted."""
        process_manager._proc = mock_asyncio_process

        mock_port_handler = MagicMock()
        mock_port_handler.wait_for_port = AsyncMock(return_value=False)

        with (
            patch(
                "aidb.adapters.base.components.process_manager.PortHandler",
                return_value=mock_port_handler,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(DebugConnectionError, match="Failed to connect"),
        ):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic(),
                max_retries=2,
            )

    @pytest.mark.asyncio
    async def test_wait_raises_on_process_exit(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test that wait raises when process exits during wait."""
        mock_asyncio_process.returncode = 1
        process_manager._proc = mock_asyncio_process
        process_manager._proc.communicate = AsyncMock(return_value=(b"", b"error"))

        mock_port_handler = MagicMock()
        mock_port_handler.wait_for_port = AsyncMock(return_value=False)

        with (
            patch(
                "aidb.adapters.base.components.process_manager.PortHandler",
                return_value=mock_port_handler,
            ),
            pytest.raises(DebugConnectionError, match="exited with code"),
        ):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic(),
            )

    @pytest.mark.asyncio
    async def test_wait_raises_on_total_timeout(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test that wait raises when total time exceeds max."""
        process_manager._proc = mock_asyncio_process

        mock_port_handler = MagicMock()
        mock_port_handler.wait_for_port = AsyncMock(return_value=False)

        with (
            patch(
                "aidb.adapters.base.components.process_manager.PortHandler",
                return_value=mock_port_handler,
            ),
            pytest.raises(DebugConnectionError, match="Timeout waiting for port"),
        ):
            await process_manager.wait_for_adapter_ready(
                port=5678,
                start_time=time.monotonic() - 100,  # Already past max time
                max_total_time=1.0,
            )


# =============================================================================
# TestProcessManagerStop
# =============================================================================


class TestProcessManagerStop:
    """Tests for stop method."""

    @pytest.mark.asyncio
    async def test_stop_with_no_process(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test stop when no process is running."""
        await process_manager.stop()

        assert process_manager._proc is None
        assert process_manager._attached_pid is None

    @pytest.mark.asyncio
    async def test_stop_terminates_process(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test stop terminates the running process."""
        process_manager._proc = mock_asyncio_process

        mock_psutil = MagicMock(spec=psutil.Process)
        mock_psutil.children = MagicMock(return_value=[])

        with (
            patch("psutil.Process", return_value=mock_psutil),
            patch(
                "aidb_common.io.subprocess.close_subprocess_transports",
                new_callable=AsyncMock,
            ),
        ):
            await process_manager.stop()

        mock_asyncio_process.terminate.assert_called_once()
        assert process_manager._proc is None

    @pytest.mark.asyncio
    async def test_stop_terminates_children_first(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
        mock_child_process: MagicMock,
    ) -> None:
        """Test stop terminates child processes before parent."""
        process_manager._proc = mock_asyncio_process

        mock_psutil = MagicMock(spec=psutil.Process)
        mock_psutil.children = MagicMock(return_value=[mock_child_process])

        with (
            patch("psutil.Process", return_value=mock_psutil),
            patch(
                "aidb_common.io.subprocess.close_subprocess_transports",
                new_callable=AsyncMock,
            ),
        ):
            await process_manager.stop()

        mock_child_process.terminate.assert_called_once()
        mock_asyncio_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_force_kills_on_timeout(
        self,
        process_manager_with_config: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test stop force kills when terminate times out."""
        mock_asyncio_process.wait = AsyncMock(side_effect=asyncio.TimeoutError())
        process_manager_with_config._proc = mock_asyncio_process

        mock_psutil = MagicMock(spec=psutil.Process)
        mock_psutil.children = MagicMock(return_value=[])

        with (
            patch("psutil.Process", return_value=mock_psutil),
            patch(
                "aidb_common.io.subprocess.close_subprocess_transports",
                new_callable=AsyncMock,
            ),
        ):
            await process_manager_with_config.stop()

        mock_asyncio_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_process_already_gone(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test stop handles process already terminated."""
        process_manager._proc = mock_asyncio_process

        with patch(
            "psutil.Process",
            side_effect=psutil.NoSuchProcess(12345),
        ):
            await process_manager.stop()

        assert process_manager._proc is None

    @pytest.mark.asyncio
    async def test_stop_clears_output_capture(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test stop clears output capture."""
        mock_output = MagicMock()
        mock_output.stop_capture_async = AsyncMock()
        mock_output.get_captured_output = MagicMock(return_value=("stdout", "stderr"))
        process_manager._output_capture = mock_output

        await process_manager.stop()

        mock_output.stop_capture_async.assert_called_once()
        assert process_manager._output_capture is None

    @pytest.mark.asyncio
    async def test_stop_kills_attached_pid(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test stop kills attached PID separately."""
        process_manager._attached_pid = 9999

        with (
            patch("os.kill") as mock_kill,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # First call succeeds (SIGTERM), second call (check) raises (process dead)
            mock_kill.side_effect = [None, OSError("No such process")]

            await process_manager.stop()

        mock_kill.assert_called()
        assert process_manager._attached_pid is None


# =============================================================================
# TestProcessManagerTerminateChildProcesses
# =============================================================================


class TestProcessManagerTerminateChildProcesses:
    """Tests for _terminate_child_processes method."""

    def test_terminates_all_children(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test all children are terminated."""
        child2 = MagicMock(spec=psutil.Process)
        child2.pid = 12347

        process_manager._terminate_child_processes([mock_child_process, child2])

        mock_child_process.terminate.assert_called_once()
        child2.terminate.assert_called_once()

    def test_handles_no_such_process(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test handles NoSuchProcess exception."""
        mock_child_process.terminate.side_effect = psutil.NoSuchProcess(12346)

        process_manager._terminate_child_processes([mock_child_process])

    def test_handles_access_denied(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test handles AccessDenied exception."""
        mock_child_process.terminate.side_effect = psutil.AccessDenied(12346)

        process_manager._terminate_child_processes([mock_child_process])


# =============================================================================
# TestProcessManagerKillRemainingChildren
# =============================================================================


class TestProcessManagerKillRemainingChildren:
    """Tests for _kill_remaining_children method."""

    def test_kills_running_children(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test kills children that are still running."""
        mock_child_process.is_running.return_value = True

        process_manager._kill_remaining_children([mock_child_process])

        mock_child_process.kill.assert_called_once()

    def test_skips_dead_children(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test skips children that are no longer running."""
        mock_child_process.is_running.return_value = False

        process_manager._kill_remaining_children([mock_child_process])

        mock_child_process.kill.assert_not_called()

    def test_handles_kill_errors(
        self,
        process_manager: ProcessManager,
        mock_child_process: MagicMock,
    ) -> None:
        """Test handles errors during kill."""
        mock_child_process.is_running.return_value = True
        mock_child_process.kill.side_effect = psutil.NoSuchProcess(12346)

        process_manager._kill_remaining_children([mock_child_process])


# =============================================================================
# TestProcessManagerAttachPid
# =============================================================================


class TestProcessManagerAttachPid:
    """Tests for attach_pid method."""

    def test_attach_pid_sets_attached_pid(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test attach_pid sets the attached PID."""
        process_manager.attach_pid(9999)

        assert process_manager._attached_pid == 9999
        assert process_manager.pid == 9999

    def test_attach_pid_logs_debug_message(
        self,
        process_manager: ProcessManager,
        mock_ctx: MagicMock,
    ) -> None:
        """Test attach_pid logs debug message."""
        process_manager.attach_pid(9999)

        mock_ctx.debug.assert_called()


# =============================================================================
# TestProcessManagerLogProcessOutput
# =============================================================================


class TestProcessManagerLogProcessOutput:
    """Tests for log_process_output method."""

    @pytest.mark.asyncio
    async def test_log_output_does_nothing_without_process(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test log_process_output does nothing when no process."""
        await process_manager.log_process_output()

    @pytest.mark.asyncio
    async def test_log_output_logs_stdout_and_stderr(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test log_process_output logs both streams."""
        mock_asyncio_process.communicate = AsyncMock(
            return_value=(b"stdout content", b"stderr content"),
        )
        process_manager._proc = mock_asyncio_process

        await process_manager.log_process_output()

        assert mock_ctx.debug.call_count >= 2

    @pytest.mark.asyncio
    async def test_log_output_handles_timeout(
        self,
        process_manager: ProcessManager,
        mock_asyncio_process: MagicMock,
    ) -> None:
        """Test log_process_output handles timeout."""
        mock_asyncio_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        process_manager._proc = mock_asyncio_process

        await process_manager.log_process_output()


# =============================================================================
# TestProcessManagerGetCapturedOutput
# =============================================================================


class TestProcessManagerGetCapturedOutput:
    """Tests for get_captured_output method."""

    def test_returns_none_without_output_capture(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test returns None when no output capture."""
        assert process_manager.get_captured_output() is None

    def test_returns_captured_output(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test returns captured output when available."""
        mock_capture = MagicMock()
        mock_capture.get_captured_output.return_value = ("stdout", "stderr")
        process_manager._output_capture = mock_capture

        result = process_manager.get_captured_output()

        assert result == ("stdout", "stderr")


# =============================================================================
# TestProcessManagerOrphanCleanup
# =============================================================================


class TestProcessManagerOrphanCleanup:
    """Tests for orphan process cleanup methods."""

    def test_cleanup_orphaned_processes_returns_stats(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test cleanup returns statistics."""
        with patch.object(
            process_manager,
            "_find_orphaned_processes",
            return_value=[],
        ):
            stats = process_manager.cleanup_orphaned_processes("debugpy")

        assert "scanned" in stats
        assert "matched" in stats
        assert "killed" in stats
        assert "elapsed_ms" in stats

    def test_cleanup_orphaned_processes_terminates_found_orphans(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test cleanup terminates found orphan processes."""
        with (
            patch.object(
                process_manager,
                "_find_orphaned_processes",
                return_value=[mock_psutil_process],
            ),
            patch.object(process_manager, "_terminate_process_gracefully") as mock_term,
        ):
            stats = process_manager.cleanup_orphaned_processes("debugpy")

        mock_term.assert_called_once_with(mock_psutil_process)
        assert stats["killed"] == 1

    def test_cleanup_handles_exception(
        self,
        process_manager: ProcessManager,
        mock_ctx: MagicMock,
    ) -> None:
        """Test cleanup handles exceptions gracefully."""
        with patch.object(
            process_manager,
            "_find_orphaned_processes",
            side_effect=RuntimeError("Test error"),
        ):
            stats = process_manager.cleanup_orphaned_processes("debugpy")

        mock_ctx.warning.assert_called()
        assert stats["killed"] == 0


# =============================================================================
# TestProcessManagerHasAidbTag
# =============================================================================


class TestProcessManagerHasAidbTag:
    """Tests for _has_aidb_tag method."""

    def test_returns_true_when_tag_present(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns True when AIDB tag is present."""
        mock_psutil_process.environ.return_value = {
            ProcessTags.OWNER: ProcessTags.OWNER_VALUE,
        }

        assert process_manager._has_aidb_tag(mock_psutil_process) is True

    def test_returns_false_when_tag_missing(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when AIDB tag is missing."""
        mock_psutil_process.environ.return_value = {}

        assert process_manager._has_aidb_tag(mock_psutil_process) is False

    def test_returns_false_when_tag_wrong_value(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when tag has wrong value."""
        mock_psutil_process.environ.return_value = {
            ProcessTags.OWNER: "wrong-value",
        }

        assert process_manager._has_aidb_tag(mock_psutil_process) is False

    def test_returns_false_on_exception(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when exception occurs."""
        mock_psutil_process.environ.side_effect = psutil.AccessDenied(12345)

        assert process_manager._has_aidb_tag(mock_psutil_process) is False


# =============================================================================
# TestProcessManagerIsParentMissing
# =============================================================================


class TestProcessManagerIsParentMissing:
    """Tests for _is_parent_missing method."""

    def test_returns_true_when_ppid_is_1(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns True when parent is init (ppid=1)."""
        mock_psutil_process.info = {"ppid": 1}

        assert process_manager._is_parent_missing(mock_psutil_process) is True

    def test_returns_false_when_parent_exists(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when parent exists and is running."""
        mock_psutil_process.info = {"ppid": 1000}

        mock_parent = MagicMock()
        mock_parent.is_running.return_value = True

        with patch("psutil.Process", return_value=mock_parent):
            assert process_manager._is_parent_missing(mock_psutil_process) is False

    def test_returns_true_when_parent_not_running(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns True when parent is not running."""
        mock_psutil_process.info = {"ppid": 1000}

        mock_parent = MagicMock()
        mock_parent.is_running.return_value = False

        with patch("psutil.Process", return_value=mock_parent):
            assert process_manager._is_parent_missing(mock_psutil_process) is True

    def test_returns_true_when_parent_not_found(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns True when parent process not found."""
        mock_psutil_process.info = {"ppid": 1000}

        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(1000)):
            assert process_manager._is_parent_missing(mock_psutil_process) is True


# =============================================================================
# TestProcessManagerShouldConsiderOrphan
# =============================================================================


class TestProcessManagerShouldConsiderOrphan:
    """Tests for _should_consider_orphan method."""

    def test_returns_false_when_pid_registered(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when PID is registered."""
        mock_psutil_process.info = {
            "pid": 12345,
            "cmdline": ["python", "debugpy"],
            "create_time": 0,
        }

        result = process_manager._should_consider_orphan(
            proc=mock_psutil_process,
            pattern="debugpy",
            min_age_seconds=60,
            current_time=time.time(),
            registered_pids={12345},  # PID is registered
            tags_only=False,
        )

        assert result is False

    def test_returns_false_when_pattern_not_matched(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when pattern doesn't match."""
        mock_psutil_process.info = {
            "pid": 12345,
            "cmdline": ["python", "other_script.py"],
            "create_time": 0,
        }

        result = process_manager._should_consider_orphan(
            proc=mock_psutil_process,
            pattern="debugpy",
            min_age_seconds=60,
            current_time=time.time(),
            registered_pids=set(),
            tags_only=False,
        )

        assert result is False

    def test_returns_false_when_too_young(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when process is too young."""
        current = time.time()
        mock_psutil_process.info = {
            "pid": 12345,
            "ppid": 1,
            "cmdline": ["python", "debugpy"],
            "create_time": current - 30,  # 30 seconds old
        }

        result = process_manager._should_consider_orphan(
            proc=mock_psutil_process,
            pattern="debugpy",
            min_age_seconds=60,  # Require 60 seconds
            current_time=current,
            registered_pids=set(),
            tags_only=False,
        )

        assert result is False

    def test_returns_false_when_tags_required_but_missing(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns False when tags required but missing."""
        current = time.time()
        mock_psutil_process.info = {
            "pid": 12345,
            "ppid": 1,
            "cmdline": ["python", "debugpy"],
            "create_time": current - 120,
        }
        mock_psutil_process.environ.return_value = {}

        result = process_manager._should_consider_orphan(
            proc=mock_psutil_process,
            pattern="debugpy",
            min_age_seconds=60,
            current_time=current,
            registered_pids=set(),
            tags_only=True,  # Require tags
        )

        assert result is False

    def test_returns_true_for_valid_orphan(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test returns True for valid orphan process."""
        current = time.time()
        mock_psutil_process.info = {
            "pid": 12345,
            "ppid": 1,
            "cmdline": ["python", "debugpy"],
            "create_time": current - 120,
        }

        result = process_manager._should_consider_orphan(
            proc=mock_psutil_process,
            pattern="debugpy",
            min_age_seconds=60,
            current_time=current,
            registered_pids=set(),
            tags_only=False,
        )

        assert result is True


# =============================================================================
# TestProcessManagerFindOrphanedProcesses
# =============================================================================


class TestProcessManagerFindOrphanedProcesses:
    """Tests for _find_orphaned_processes method."""

    def test_returns_empty_list_when_no_orphans(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test returns empty list when no orphans found."""
        with (
            patch("psutil.process_iter", return_value=[]),
            patch(
                "aidb.resources.pids.ProcessRegistry",
            ) as mock_registry_class,
            patch("aidb_common.env.reader.read_bool", return_value=True),
        ):
            mock_registry_class.return_value.get_all_registered_pids.return_value = (
                set()
            )

            orphans = process_manager._find_orphaned_processes(
                pattern="debugpy",
                min_age_seconds=60,
            )

        assert orphans == []

    def test_finds_matching_orphans(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test finds processes matching orphan criteria."""
        current = time.time()
        mock_psutil_process.info = {
            "pid": 12345,
            "ppid": 1,
            "cmdline": ["python", "debugpy"],
            "create_time": current - 120,
        }
        mock_psutil_process.environ.return_value = {
            ProcessTags.OWNER: ProcessTags.OWNER_VALUE,
        }

        with (
            patch("psutil.process_iter", return_value=[mock_psutil_process]),
            patch(
                "aidb.resources.pids.ProcessRegistry",
            ) as mock_registry_class,
            patch("aidb_common.env.reader.read_bool", return_value=True),
        ):
            mock_registry_class.return_value.get_all_registered_pids.return_value = (
                set()
            )

            orphans = process_manager._find_orphaned_processes(
                pattern="debugpy",
                min_age_seconds=60,
            )

        assert len(orphans) == 1
        assert orphans[0] is mock_psutil_process

    def test_respects_max_scan_time(
        self,
        process_manager: ProcessManager,
        mock_ctx: MagicMock,
    ) -> None:
        """Test stops scanning when max_scan_ms exceeded."""

        def slow_iterator():
            while True:
                yield MagicMock()

        with (
            patch("psutil.process_iter", return_value=slow_iterator()),
            patch(
                "aidb.resources.pids.ProcessRegistry",
            ) as mock_registry_class,
            patch("aidb_common.env.reader.read_bool", return_value=True),
            patch(
                "time.monotonic", side_effect=[0, 0, 0.1, 0.2]
            ),  # Simulate time passing
        ):
            mock_registry_class.return_value.get_all_registered_pids.return_value = (
                set()
            )

            stats: dict = {"scanned": 0, "matched": 0}
            process_manager._find_orphaned_processes(
                pattern="debugpy",
                min_age_seconds=60,
                max_scan_ms=50,  # 50ms limit
                stats=stats,
            )

        mock_ctx.warning.assert_called()

    def test_updates_stats_dict(
        self,
        process_manager: ProcessManager,
    ) -> None:
        """Test updates provided stats dictionary."""
        with (
            patch("psutil.process_iter", return_value=[]),
            patch(
                "aidb.resources.pids.ProcessRegistry",
            ) as mock_registry_class,
            patch("aidb_common.env.reader.read_bool", return_value=True),
        ):
            mock_registry_class.return_value.get_all_registered_pids.return_value = (
                set()
            )

            stats: dict = {"scanned": 0, "matched": 0}
            process_manager._find_orphaned_processes(
                pattern="debugpy",
                min_age_seconds=60,
                stats=stats,
            )

        assert "scanned" in stats


# =============================================================================
# TestProcessManagerTerminateProcessGracefully
# =============================================================================


class TestProcessManagerTerminateProcessGracefully:
    """Tests for _terminate_process_gracefully method."""

    def test_terminates_process(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test terminates process gracefully."""
        process_manager._terminate_process_gracefully(mock_psutil_process)

        mock_psutil_process.terminate.assert_called_once()
        mock_psutil_process.wait.assert_called_once_with(timeout=5)

    def test_force_kills_on_timeout(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
    ) -> None:
        """Test force kills when terminate times out."""
        mock_psutil_process.wait.side_effect = psutil.TimeoutExpired(5)

        process_manager._terminate_process_gracefully(mock_psutil_process)

        mock_psutil_process.kill.assert_called_once()

    def test_handles_exception(
        self,
        process_manager: ProcessManager,
        mock_psutil_process: MagicMock,
        mock_ctx: MagicMock,
    ) -> None:
        """Test handles exceptions during termination."""
        mock_psutil_process.terminate.side_effect = RuntimeError("Test error")

        process_manager._terminate_process_gracefully(mock_psutil_process)

        mock_ctx.warning.assert_called()
