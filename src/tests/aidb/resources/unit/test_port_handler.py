"""Unit tests for port handling."""

import asyncio
from unittest.mock import MagicMock, patch

import psutil
import pytest

from aidb.common.errors import AidbError
from aidb.resources.ports import DEFAULT_HOST, PortHandler


class TestPortHandlerWaitForPort:
    """Tests for PortHandler._wait_for_port_iteration."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        mock_ctx.error = MagicMock()
        return PortHandler(ctx=mock_ctx)

    @pytest.fixture
    def mock_process(self) -> MagicMock:
        """Create a mock asyncio subprocess."""
        proc = MagicMock(spec=asyncio.subprocess.Process)
        proc.pid = 12345
        proc.returncode = None
        return proc

    @pytest.mark.asyncio
    async def test_returns_true_when_specific_process_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When proc is provided and listening on port, return True."""
        with patch.object(
            port_handler,
            "_check_specific_process_port",
            return_value=True,
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_does_not_fallback_when_proc_provided(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When proc is provided, do NOT fall back to checking all processes.

        This prevents connecting to wrong processes like macOS ControlCenter that may be
        listening on the same port.
        """
        with (
            patch.object(
                port_handler,
                "_check_specific_process_port",
                return_value=False,
            ) as mock_specific,
            patch.object(
                port_handler,
                "_check_all_processes_for_port",
                return_value=True,
            ) as mock_all,
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
            )

        mock_specific.assert_called_once_with(mock_process, 7000)
        mock_all.assert_not_called()
        assert result is False

    @pytest.mark.asyncio
    async def test_uses_all_processes_check_when_no_proc(
        self,
        port_handler: PortHandler,
    ) -> None:
        """When no proc provided, fall back to checking all processes.

        This is the attach mode case where we don't control the process.
        """
        with patch.object(
            port_handler,
            "_check_all_processes_for_port",
            return_value=True,
        ) as mock_all:
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=None,
                attempt=1,
            )

        mock_all.assert_called_once_with(7000)
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_proc_and_no_listener(
        self,
        port_handler: PortHandler,
    ) -> None:
        """When no proc and no process listening, return False."""
        with patch.object(
            port_handler,
            "_check_all_processes_for_port",
            return_value=False,
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=None,
                attempt=1,
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_checks_process_running_on_failure(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When port check fails, verify process is still running."""
        with (
            patch.object(
                port_handler,
                "_check_specific_process_port",
                return_value=False,
            ),
            patch.object(
                port_handler,
                "_check_process_still_running",
            ) as mock_check_running,
        ):
            await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
            )

        mock_check_running.assert_called_once_with(mock_process, 7000)


class TestPortHandlerInit:
    """Tests for PortHandler initialization."""

    def test_default_initialization(self) -> None:
        """Test initialization with default values."""
        mock_ctx = MagicMock()
        handler = PortHandler(ctx=mock_ctx)

        assert handler.host == DEFAULT_HOST
        assert handler.ipv6 is False
        assert handler.timeout == 1.0

    def test_custom_initialization(self) -> None:
        """Test initialization with custom values."""
        mock_ctx = MagicMock()
        handler = PortHandler(
            ctx=mock_ctx,
            host="192.168.1.1",
            ipv6=True,
            timeout=5.0,
        )

        assert handler.host == "192.168.1.1"
        assert handler.ipv6 is True
        assert handler.timeout == 5.0


class TestPortHandlerCheckProcessStillRunning:
    """Tests for PortHandler._check_process_still_running."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        mock_ctx.error = MagicMock()
        return PortHandler(ctx=mock_ctx)

    @pytest.fixture
    def mock_process(self) -> MagicMock:
        """Create a mock asyncio subprocess."""
        proc = MagicMock(spec=asyncio.subprocess.Process)
        proc.pid = 12345
        proc.returncode = None
        return proc

    def test_no_error_when_process_running(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When process is still running (returncode=None), no error raised."""
        mock_process.returncode = None

        # Should not raise
        port_handler._check_process_still_running(mock_process, 7000)

    def test_no_error_when_proc_is_none(
        self,
        port_handler: PortHandler,
    ) -> None:
        """When proc is None, no error raised."""
        # Should not raise
        port_handler._check_process_still_running(None, 7000)

    def test_raises_error_when_process_exited(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When process exited, raise AidbError with details."""
        mock_process.returncode = 1

        with pytest.raises(AidbError) as exc_info:
            port_handler._check_process_still_running(mock_process, 7000)

        error = exc_info.value
        assert "exited prematurely" in str(error)
        assert error.details["port"] == 7000
        assert error.details["exit_code"] == 1
        assert error.details["process_pid"] == 12345
        assert error.recoverable is False

    def test_raises_error_with_zero_exit_code(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Even exit code 0 is premature if we're waiting for port."""
        mock_process.returncode = 0

        with pytest.raises(AidbError) as exc_info:
            port_handler._check_process_still_running(mock_process, 7000)

        assert exc_info.value.details["exit_code"] == 0


class TestPortHandlerCheckSpecificProcessPort:
    """Tests for PortHandler._check_specific_process_port."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        return PortHandler(ctx=mock_ctx)

    @pytest.fixture
    def mock_process(self) -> MagicMock:
        """Create a mock asyncio subprocess."""
        proc = MagicMock(spec=asyncio.subprocess.Process)
        proc.pid = 12345
        return proc

    def test_returns_true_when_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return True when process is listening on the port."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = [mock_conn]

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is True

    def test_returns_false_when_not_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when process is not listening on the port."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 8000  # Different port
        mock_conn.status = psutil.CONN_LISTEN

        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = [mock_conn]
        mock_psutil_process.children.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False

    def test_returns_false_when_no_connections(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when process has no network connections."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = []
        mock_psutil_process.children.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False

    def test_returns_false_when_connection_not_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when connection exists but not in LISTEN state."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_ESTABLISHED  # Not listening

        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = [mock_conn]
        mock_psutil_process.children.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False

    def test_returns_false_when_process_not_found(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when process no longer exists."""
        with patch("psutil.Process", side_effect=psutil.NoSuchProcess(12345)):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False

    def test_returns_false_when_access_denied(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when access to process is denied."""
        with patch("psutil.Process", side_effect=psutil.AccessDenied(12345)):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False

    def test_returns_true_when_child_process_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return True when child process is listening on the port.

        This tests the debugpy case where the adapter subprocess listens on the port,
        not the parent debugpy server process.
        """
        # Parent process has no listening connections
        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = []

        # Child process is listening on the port
        mock_child_conn = MagicMock()
        mock_child_conn.laddr.port = 7000
        mock_child_conn.status = psutil.CONN_LISTEN

        mock_child = MagicMock()
        mock_child.pid = 12346
        mock_child.net_connections.return_value = [mock_child_conn]

        mock_psutil_process.children.return_value = [mock_child]

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is True

    def test_returns_false_when_no_child_listening(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when neither parent nor children are listening."""
        mock_psutil_process = MagicMock()
        mock_psutil_process.net_connections.return_value = []
        mock_psutil_process.children.return_value = []

        with patch("psutil.Process", return_value=mock_psutil_process):
            result = port_handler._check_specific_process_port(mock_process, 7000)

        assert result is False


class TestPortHandlerCheckAllProcessesForPort:
    """Tests for PortHandler._check_all_processes_for_port."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        return PortHandler(ctx=mock_ctx)

    def test_returns_true_when_any_process_listening(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return True when any process is listening on the port."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "some_process"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_all_processes_for_port(7000)

        assert result is True

    def test_returns_false_when_no_process_listening(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False when no process is listening on the port."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 8000  # Different port
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "some_process"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_all_processes_for_port(7000)

        assert result is False

    def test_returns_false_when_no_processes(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False when there are no processes."""
        with patch("psutil.process_iter", return_value=[]):
            result = port_handler._check_all_processes_for_port(7000)

        assert result is False

    def test_handles_process_exceptions_gracefully(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Skip processes that raise exceptions during iteration."""
        # First process raises exception
        mock_process1 = MagicMock()
        mock_process1.net_connections.side_effect = psutil.AccessDenied(111)

        # Second process is listening
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process2 = MagicMock()
        mock_process2.pid = 222
        mock_process2.info = {"pid": 222, "name": "listener"}
        mock_process2.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process1, mock_process2]):
            result = port_handler._check_all_processes_for_port(7000)

        assert result is True

    def test_returns_false_on_iteration_failure(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False if process iteration itself fails."""
        with patch("psutil.process_iter", side_effect=RuntimeError("Failed")):
            result = port_handler._check_all_processes_for_port(7000)

        assert result is False


class TestPortHandlerCheckNamedProcessesForPort:
    """Tests for PortHandler._check_named_processes_for_port."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        return PortHandler(ctx=mock_ctx)

    def test_returns_true_when_named_process_listening(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return True when a process with matching name is listening."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "python"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python", "debugpy"],
            )

        assert result is True

    def test_returns_true_with_case_insensitive_match(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return True when process name matches case-insensitively."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "Python3.11"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is True

    def test_returns_false_when_no_matching_process(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False when no process matches the names."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "node"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python", "debugpy"],
            )

        assert result is False

    def test_returns_false_when_matching_process_not_listening(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False when matching process exists but not listening on port."""
        mock_conn = MagicMock()
        mock_conn.laddr.port = 8000  # Different port
        mock_conn.status = psutil.CONN_LISTEN

        mock_process = MagicMock()
        mock_process.pid = 999
        mock_process.info = {"pid": 999, "name": "python"}
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is False

    def test_returns_false_when_no_processes(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False when there are no processes."""
        with patch("psutil.process_iter", return_value=[]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is False

    def test_handles_process_exceptions_gracefully(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Skip processes that raise exceptions during iteration."""
        # First process raises exception
        mock_process1 = MagicMock()
        mock_process1.info = {"pid": 111, "name": "python"}
        mock_process1.net_connections.side_effect = psutil.AccessDenied(111)

        # Second process is listening
        mock_conn = MagicMock()
        mock_conn.laddr.port = 7000
        mock_conn.status = psutil.CONN_LISTEN

        mock_process2 = MagicMock()
        mock_process2.pid = 222
        mock_process2.info = {"pid": 222, "name": "python"}
        mock_process2.net_connections.return_value = [mock_conn]

        with patch("psutil.process_iter", return_value=[mock_process1, mock_process2]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is True

    def test_returns_false_on_iteration_failure(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return False if process iteration itself fails."""
        with patch("psutil.process_iter", side_effect=RuntimeError("Failed")):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is False

    def test_handles_none_process_name(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Handle processes with None name gracefully."""
        mock_process = MagicMock()
        mock_process.info = {"pid": 999, "name": None}
        mock_process.net_connections.return_value = []

        with patch("psutil.process_iter", return_value=[mock_process]):
            result = port_handler._check_named_processes_for_port(
                7000,
                ["python"],
            )

        assert result is False


class TestPortHandlerDetachedProcessFallback:
    """Tests for detached process fallback in _wait_for_port_iteration."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        mock_ctx.error = MagicMock()
        return PortHandler(ctx=mock_ctx)

    @pytest.fixture
    def mock_process(self) -> MagicMock:
        """Create a mock asyncio subprocess."""
        proc = MagicMock(spec=asyncio.subprocess.Process)
        proc.pid = 12345
        proc.returncode = None
        return proc

    @pytest.mark.asyncio
    async def test_uses_detached_fallback_when_child_check_fails(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When specific process check fails, try detached process fallback."""
        with (
            patch.object(
                port_handler,
                "_check_specific_process_port",
                return_value=False,
            ),
            patch.object(
                port_handler,
                "_check_named_processes_for_port",
                return_value=True,
            ) as mock_named,
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
                detached_process_names=["python", "debugpy"],
            )

        assert result is True
        mock_named.assert_called_once_with(7000, ["python", "debugpy"])

    @pytest.mark.asyncio
    async def test_skips_detached_fallback_when_not_provided(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """When detached_process_names not provided, skip fallback."""
        with (
            patch.object(
                port_handler,
                "_check_specific_process_port",
                return_value=False,
            ),
            patch.object(
                port_handler,
                "_check_named_processes_for_port",
                return_value=True,
            ) as mock_named,
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
                detached_process_names=None,
            )

        assert result is False
        mock_named.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_both_checks_fail(
        self,
        port_handler: PortHandler,
        mock_process: MagicMock,
    ) -> None:
        """Return False when both specific and detached checks fail."""
        with (
            patch.object(
                port_handler,
                "_check_specific_process_port",
                return_value=False,
            ),
            patch.object(
                port_handler,
                "_check_named_processes_for_port",
                return_value=False,
            ),
        ):
            result = await port_handler._wait_for_port_iteration(
                port=7000,
                proc=mock_process,
                attempt=1,
                detached_process_names=["python"],
            )

        assert result is False


class TestPortHandlerWaitForPortTimeout:
    """Tests for PortHandler.wait_for_port timeout behavior."""

    @pytest.fixture
    def port_handler(self) -> PortHandler:
        """Create a PortHandler instance with mocked context."""
        mock_ctx = MagicMock()
        mock_ctx.debug = MagicMock()
        mock_ctx.error = MagicMock()
        return PortHandler(ctx=mock_ctx)

    @pytest.mark.asyncio
    async def test_returns_true_on_immediate_success(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return True immediately when port is already listening."""
        with patch.object(
            port_handler,
            "_wait_for_port_iteration",
            return_value=True,
        ) as mock_iteration:
            result = await port_handler.wait_for_port(port=7000, timeout=10.0)

        assert result is True
        mock_iteration.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_true_after_retries(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Return True when port becomes available after retries."""
        call_count = 0

        async def mock_iteration(port, proc, attempt, detached_process_names=None):
            nonlocal call_count
            call_count += 1
            return call_count >= 3  # Success on 3rd attempt

        with patch.object(
            port_handler,
            "_wait_for_port_iteration",
            side_effect=mock_iteration,
        ):
            result = await port_handler.wait_for_port(port=7000, timeout=10.0)

        assert result is True
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_error_on_timeout(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Raise AidbError when timeout is reached."""
        with patch.object(
            port_handler,
            "_wait_for_port_iteration",
            return_value=False,
        ):
            with pytest.raises(AidbError) as exc_info:
                await port_handler.wait_for_port(port=7000, timeout=0.2)

        error = exc_info.value
        assert "Timed out" in str(error)
        assert error.details["port"] == 7000
        assert error.details["timeout"] == 0.2
        assert error.recoverable is True

    @pytest.mark.asyncio
    async def test_propagates_process_exit_error(
        self,
        port_handler: PortHandler,
    ) -> None:
        """Propagate AidbError from _check_process_still_running."""

        async def mock_iteration(port, proc, attempt, detached_process_names=None):
            msg = "Process exited"
            raise AidbError(msg, recoverable=False)

        with patch.object(
            port_handler,
            "_wait_for_port_iteration",
            side_effect=mock_iteration,
        ):
            with pytest.raises(AidbError) as exc_info:
                await port_handler.wait_for_port(port=7000, timeout=10.0)

        assert "Process exited" in str(exc_info.value)
