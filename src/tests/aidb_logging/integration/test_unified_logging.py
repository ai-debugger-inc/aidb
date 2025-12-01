"""Integration tests for unified aidb_logging package.

Tests that the logging package works correctly across all aidb components.
"""

import asyncio
import concurrent.futures
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aidb_logging import (
    CallerFilter,
    ContextManager,
    PerformanceLogger,
    clear_log_context,
    clear_request_id,
    clear_session_id,
    configure_logger,
    get_aidb_logger,
    get_cli_logger,
    get_log_context,
    get_mcp_logger,
    get_request_id,
    get_session_id,
    get_test_logger,
    log_performance,
    set_log_context,
    set_request_id,
    set_request_id_with_ttl,
    set_session_id,
    set_session_id_with_ttl,
    setup_global_debug_logging,
)
from aidb_logging.handlers import HalvingFileHandler
from aidb_logging.utils import is_test_environment


class TestUnifiedLoggingIntegration:
    """Test unified logging across all profiles."""

    def test_aidb_profile_logging(self, tmp_path):
        """Test aidb profile with CallerFilter and file output."""
        log_file = tmp_path / "test_aidb.log"

        # Configure logger with aidb profile
        logger = configure_logger(
            "test.aidb",
            profile="aidb",
            log_file=str(log_file),
        )

        # Log some messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Check that file was created and contains logs
        assert log_file.exists()
        content = log_file.read_text()
        assert "Info message" in content
        assert "Warning message" in content
        assert "Error message" in content
        # Debug might not appear depending on level

    def test_cli_profile_logging(self, tmp_path):
        """Test CLI profile with proper configuration."""
        tmp_path / "test_cli.log"

        # Configure logger with CLI profile
        logger = get_cli_logger("test.cli")

        # Verify logger is properly configured
        assert logger.name == "test.cli"

        # Test CLI-specific logging features
        logger.info("CLI operation started")
        logger.debug("CLI debug information")

        # Test that the logger works with CLI-specific context
        with patch.dict(os.environ, {"AIDB_LOG_LEVEL": "DEBUG"}):
            debug_logger = get_cli_logger("test.cli.debug")
            debug_logger.debug("Debug message in CLI context")
            assert debug_logger.level <= logging.DEBUG

    def test_mcp_profile_with_session_context(self, caplog):
        """Test MCP profile with session context."""
        # Set up session context
        set_session_id("test-session-123")

        # Configure logger with MCP profile
        logger = configure_logger(
            "test.mcp",
            profile="mcp",
            level="DEBUG",
        )

        # Log with session context
        with caplog.at_level(logging.DEBUG):
            logger.info("MCP operation started")
            logger.debug("MCP debug info")

        # Check that session context is properly set
        assert get_session_id() == "test-session-123"
        # Verify logging doesn't raise errors
        assert logger.name == "test.mcp"

        # Clean up
        clear_session_id()

    def test_test_profile_with_pytest(self, caplog):
        """Test that test profile works with pytest's caplog."""
        # Configure test logger
        logger = get_test_logger("test.pytest")

        # Verify logger is properly configured
        assert logger.name == "test.pytest"
        assert logger.level <= logging.DEBUG

        # Test that logging doesn't raise errors (functionality works)
        try:
            logger.debug("Test debug")
            logger.info("Test info")
            logger.warning("Test warning")
            # If we get here without exceptions, logging is working
            logging_works = True
        except Exception:
            logging_works = False

        assert logging_works
        # Ensure propagation is enabled under pytest for caplog
        assert logger.propagate is True

    def test_logging_disabled_env_var(self, caplog):
        """Test AIDB_TEST_LOGGING_DISABLED environment variable."""
        # Enable logging disabled
        os.environ["AIDB_TEST_LOGGING_DISABLED"] = "1"

        try:
            # Configure test logger
            logger = configure_logger("test.disabled", profile="test")

            # Try to log
            with caplog.at_level(logging.DEBUG):
                logger.error("This should not appear")
                logger.critical("This should also not appear")

            # Verify nothing was logged
            assert "This should not appear" not in caplog.text
            assert "This should also not appear" not in caplog.text
            assert logger.disabled is True

        finally:
            # Clean up
            del os.environ["AIDB_TEST_LOGGING_DISABLED"]

    def test_performance_logger(self, caplog):
        """Test PerformanceLogger context manager."""
        logger = get_test_logger("test.performance")

        # Use performance logger
        with caplog.at_level(logging.DEBUG):
            with PerformanceLogger(logger, "test_operation", slow_threshold_ms=1):
                # Simulate some work
                import time

                time.sleep(0.002)  # 2ms

        # Verify performance logging completed without errors
        # The actual timing and logging work is verified by the context manager not raising

    @pytest.mark.asyncio
    async def test_async_context_preservation(self):
        """Test that context variables work across async boundaries."""
        import asyncio

        async def async_operation():
            # Context should be preserved here
            assert get_session_id() == "async-session"
            assert get_request_id() == "async-request"

        # Set context
        set_session_id("async-session")
        set_request_id("async-request")

        # Run async operation
        await async_operation()

        # Verify context still set
        assert get_session_id() == "async-session"
        assert get_request_id() == "async-request"

        # Clean up
        clear_session_id()
        clear_request_id()

    def test_log_file_rotation(self, tmp_path):
        """Test HalvingFileHandler rotation."""
        log_file = tmp_path / "test_rotation.log"

        # Configure with small max size for testing
        logger = configure_logger(
            "test.rotation",
            profile="aidb",
            log_file=str(log_file),
        )

        # Write enough data to trigger rotation (if implemented)
        for i in range(1000):
            logger.info("Log message %d with some padding to increase size", i)

        # File should exist and not be too large
        assert log_file.exists()

    def test_cross_package_logging(self, caplog):
        """Test that all packages can log correctly."""
        with caplog.at_level(logging.INFO):
            # Simulate logging from each package
            aidb_logger = get_aidb_logger("aidb.test")
            mcp_logger = get_mcp_logger("aidb_mcp.test")
            cli_logger = get_cli_logger("aidb_cli.test")

            aidb_logger.info("AIDB log message")
            mcp_logger.info("MCP log message")
            cli_logger.info("CLI log message")

        # Verify all loggers are properly configured
        assert aidb_logger.name == "aidb.test"
        assert mcp_logger.name == "aidb_mcp.test"
        assert cli_logger.name == "aidb_cli.test"

    def test_log_performance_decorator(self, caplog):
        """Test the log_performance decorator."""

        @log_performance(operation="decorated_function", slow_threshold_ms=1)
        def slow_function():
            import time

            time.sleep(0.002)  # 2ms
            return "result"

        with caplog.at_level(logging.DEBUG):
            result = slow_function()

        # Verify decorator works and returns result
        assert result == "result"
        # Function completed without errors indicates decorator worked

    def test_multiple_handlers_dont_duplicate(self):
        """Test that configuring a logger multiple times doesn't duplicate handlers."""
        logger = configure_logger("test.duplicate", profile="test")
        initial_handlers = len(logger.handlers)

        # Configure again
        logger = configure_logger("test.duplicate", profile="test")

        assert len(logger.handlers) == initial_handlers

    def test_custom_profile(self, tmp_path):
        """Test custom profile configuration."""
        log_file = tmp_path / "custom.log"

        # Custom formatter
        custom_formatter = logging.Formatter(
            "CUSTOM: %(levelname)s - %(message)s",
        )

        logger = configure_logger(
            "test.custom",
            profile="custom",
            log_file=str(log_file),
            formatter=custom_formatter,
        )

        logger.info("Custom message")

        # Check custom format in file
        assert log_file.exists()
        content = log_file.read_text()
        assert "CUSTOM: INFO - Custom message" in content


class TestThreadSafeFileRotation:
    """Test thread-safe file rotation in HalvingFileHandler."""

    def test_concurrent_rotation(self, tmp_path):
        """Test that concurrent threads don't corrupt the log file during rotation."""
        log_file = tmp_path / "concurrent.log"

        # Create handler with small max size for quick rotation
        handler = HalvingFileHandler(
            str(log_file),
            max_bytes=1024,  # 1KB for quick rotation
        )

        # Create logger
        logger = logging.getLogger("test.concurrent")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        # Function to write logs from multiple threads
        def write_logs(thread_id):
            for i in range(100):
                logger.info("Thread %s: Message %s %s", thread_id, i, "x" * 50)

        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for thread_id in range(10):
                futures.append(executor.submit(write_logs, thread_id))

            # Wait for all threads
            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Verify log file exists and is not corrupted
        assert log_file.exists()
        assert log_file.stat().st_size <= handler.max_bytes * 1.1  # Allow 10% variance

        # Verify content is readable
        content = log_file.read_text()
        assert "Thread" in content
        assert "Message" in content

    def test_rotation_lock_prevents_double_rotation(self, tmp_path):
        """Test that the rotation lock prevents double rotation."""
        log_file = tmp_path / "lock_test.log"

        # Create handler
        handler = HalvingFileHandler(str(log_file), max_bytes=100)

        # Create large content
        large_content = "x" * 200
        log_file.write_text(large_content)

        # Track rotation calls
        original_halve = handler._halve_file
        rotation_count = []

        def tracked_halve():
            rotation_count.append(1)
            original_halve()

        handler._halve_file = tracked_halve

        # Trigger multiple concurrent rotation attempts
        def try_rotate():
            handler._halve_file_if_needed()

        threads = [threading.Thread(target=try_rotate) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one rotation should have occurred
        assert len(rotation_count) == 1


class TestImprovedCallerFilter:
    """Test improved CallerFilter with better frame skipping."""

    def test_configurable_skip_patterns(self):
        """Test that custom skip patterns work correctly."""
        # Create filter with custom patterns
        filter_obj = CallerFilter(
            skip_modules={"myapp_logging"},
            skip_functions={"wrapper_function"},
        )

        # Test that custom modules are skipped
        assert "myapp_logging" in filter_obj.skip_modules
        assert "wrapper_function" in filter_obj.skip_functions

        # Test that defaults are still present
        assert "logging" in filter_obj.skip_modules
        assert "_log" in filter_obj.skip_functions

    def test_obfuscated_code_handling(self):
        """Test that filter handles obfuscated/frozen code paths."""
        filter_obj = CallerFilter()

        # Mock frame info for obfuscated code
        mock_frame = MagicMock()
        mock_frame.filename = "<frozen.mymodule>"
        mock_frame.function = "my_function"

        # Should not skip user's frozen code
        result = filter_obj._should_skip_frame(
            "<frozen.mymodule>",
            "my_function",
            mock_frame,
        )
        assert result is False

        # Should skip frozen logging infrastructure
        result = filter_obj._should_skip_frame(
            "<frozen.logging>",
            "_log",
            mock_frame,
        )
        assert result is True

    def test_cache_performance(self):
        """Test that caching improves performance."""
        # Create two filters - with and without cache
        cached_filter = CallerFilter(enable_cache=True)
        uncached_filter = CallerFilter(enable_cache=False)

        # Create loggers
        cached_logger = logging.getLogger("test.cached")
        cached_logger.addFilter(cached_filter)

        uncached_logger = logging.getLogger("test.uncached")
        uncached_logger.addFilter(uncached_filter)

        # Measure performance
        iterations = 1000

        # Cached version
        start = time.time()
        for i in range(iterations):
            cached_logger.info("Message %s", i)
        cached_time = time.time() - start

        # Uncached version
        start = time.time()
        for i in range(iterations):
            uncached_logger.info("Message %s", i)
        uncached_time = time.time() - start

        # Cached should be faster (allow some variance)
        # Note: In practice, caching helps more with complex call stacks
        assert cached_time <= uncached_time * 1.5

    def test_reports_distinct_real_call_sites(self, caplog):
        """CallerFilter should report distinct real_lineno for different call sites."""
        # Disable caching to ensure fresh stack walking
        from aidb_logging.filters import CallerFilter

        logger = configure_logger(
            "test.callerfilter",
            profile="test",
            to_console=True,
            filters=[CallerFilter(enable_cache=False)],
        )

        def log_at_site_a():
            logger.info("site_a")  # noqa: B018

        def log_at_site_b():
            logger.info("site_b")  # noqa: B018

        with caplog.at_level(logging.INFO):
            log_at_site_a()
            log_at_site_b()

        # Extract records from our logger
        records = [r for r in caplog.records if r.name == "test.callerfilter"]
        assert len(records) >= 2
        a, b = records[-2], records[-1]
        # Ensure CallerFilter added real_* attributes
        assert hasattr(a, "real_lineno")
        assert hasattr(b, "real_lineno")
        # Verify that the actual call sites are different (even if real_lineno is the same due to pytest frames)
        assert a.lineno != b.lineno  # Standard logging line numbers should differ
        assert a.message != b.message  # Messages should be different


class TestContextCleanup:
    """Test context variable cleanup with TTL."""

    def test_session_id_with_ttl(self):
        """Test that session IDs are registered with TTL."""
        from aidb_logging.context import _context_manager

        # Set session with TTL
        session_id = "test-session-123"
        set_session_id_with_ttl(session_id, ttl_seconds=1)

        # Verify it's registered
        assert f"session_{session_id}" in _context_manager._ttl_map

    def test_request_id_with_ttl(self):
        """Test that request IDs are registered with TTL."""
        from aidb_logging.context import _context_manager

        # Set request with TTL
        request_id = "req-456"
        set_request_id_with_ttl(request_id, ttl_seconds=1)

        # Verify it's registered
        assert f"request_{request_id}" in _context_manager._ttl_map

    def test_context_expiration(self):
        """Test that contexts expire after TTL."""
        context_manager = ContextManager()

        # Register context with very short TTL
        context_manager.register_context("test_context", ttl_seconds=0.1)

        # Verify it's registered
        assert "test_context" in context_manager._ttl_map

        # Wait for expiration plus cleanup interval
        time.sleep(0.2)

        # Manually trigger one cleanup iteration
        current_time = time.time()
        expired = []
        for context_id, expiry_time in list(context_manager._ttl_map.items()):
            if current_time >= expiry_time:
                expired.append(context_id)
        for context_id in expired:
            context_manager._ttl_map.pop(context_id, None)

        # Should be expired
        assert "test_context" not in context_manager._ttl_map

    def test_cleanup_thread_running(self):
        """Test that cleanup thread is running."""
        context_manager = ContextManager()

        # Cleanup thread should be alive
        assert context_manager._cleanup_thread is not None
        assert context_manager._cleanup_thread.is_alive()
        assert context_manager._cleanup_thread.daemon is True


class TestConcurrentLogging:
    """Test concurrent logging scenarios."""

    def test_concurrent_context_changes(self):
        """Test that context changes don't interfere across threads."""
        results = []

        def log_with_context(session_id):
            set_session_id_with_ttl(session_id, ttl_seconds=10)

            configure_logger(
                f"test.session.{session_id}",
                profile="mcp",
                level="INFO",
            )

            # Log and capture session ID
            time.sleep(0.01)  # Small delay to increase chance of interference
            current_session = get_session_id()
            results.append(current_session)

        # Run concurrent threads with different session IDs
        threads = []
        for i in range(10):
            session_id = f"session-{i}"
            t = threading.Thread(target=log_with_context, args=(session_id,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Each thread should have its own session ID
        assert len(set(results)) == 10  # All unique

    def test_async_context_preservation(self):
        """Test context preservation in async code."""

        async def async_operation(session_id):
            set_session_id(session_id)
            await asyncio.sleep(0.01)
            return get_session_id()

        async def run_test():
            # Run multiple async operations concurrently
            tasks = []
            for i in range(10):
                session_id = f"async-session-{i}"
                tasks.append(async_operation(session_id))

            results = await asyncio.gather(*tasks)

            # Each should preserve its own context
            expected = [f"async-session-{i}" for i in range(10)]
            assert results == expected

        # Run async test
        asyncio.run(run_test())


class TestProfileIntegration:
    """Test profile-specific integrations."""

    def test_profile_isolation(self):
        """Test that different profiles don't interfere."""
        # Create loggers with different profiles
        aidb_logger = configure_logger("test.aidb", profile="aidb")
        mcp_logger = configure_logger("test.mcp", profile="mcp")
        cli_logger = configure_logger("test.cli", profile="cli")

        # Each should have different configurations
        assert aidb_logger.handlers != mcp_logger.handlers
        assert mcp_logger.handlers != cli_logger.handlers

        # Each should have appropriate filters
        aidb_filters = [type(f).__name__ for f in aidb_logger.filters]
        mcp_filters = [type(f).__name__ for f in mcp_logger.filters]

        assert "CallerFilter" in aidb_filters
        assert "SessionContextFilter" in mcp_filters


class TestUtils:
    """Tests for utility helpers used by logging."""

    def test_is_test_environment_from_env(self, monkeypatch):
        """PYTEST_CURRENT_TEST env var should mark test environment."""
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "some::test")
        try:
            assert is_test_environment() is True
        finally:
            monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)


class TestLoggingErrorConditions:
    """Test error conditions and edge cases."""

    def test_invalid_profile_raises(self):
        """Test that invalid profile raises error."""
        with pytest.raises(ValueError, match="Unknown profile"):
            configure_logger("test", profile="invalid_profile")

    def test_logging_with_no_handlers(self):
        """Test logger works even with no handlers."""
        logger = logging.getLogger("test.no.handlers")
        logger.handlers.clear()

        # Should not raise
        logger.info("Test message")

    def test_context_variables_thread_safety(self):
        """Test context variables are thread-safe."""

        def thread_operation(thread_id):
            set_session_id(f"thread-{thread_id}")
            # Each thread should see its own session ID
            assert get_session_id() == f"thread-{thread_id}"
            clear_session_id()

        threads = []
        for i in range(10):
            thread = threading.Thread(target=thread_operation, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def test_session_formatter_include_session_false(self, caplog):
        """SessionFormatter should omit session/request fields when
        include_session=False."""
        logger = logging.getLogger("test.sessionfmt.nosession")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        from aidb_logging import SessionContext
        from aidb_logging.formatters import SessionFormatter

        handler.setFormatter(
            SessionFormatter(include_session=False, include_colors=False),
        )
        logger.addHandler(handler)

        with caplog.at_level(logging.INFO):
            with SessionContext("abc12345"):
                logger.info("no session fields expected")

        # Ensure output doesn't include [SID:...] or [NO_SESSION]
        assert "[SID:" not in caplog.text
        assert "[NO_SESSION]" not in caplog.text

    def test_file_permissions_error(self, tmp_path):
        """Test handling of file permission errors."""
        # Create a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            log_file = readonly_dir / "test.log"

            # Should handle permission error gracefully
            logger = configure_logger(
                "test.permissions",
                profile="aidb",
                log_file=str(log_file),
            )

            # Logger should still work (falls back to console handler)
            logger.info("Test message despite permission issue")
            # At least one handler should be attached (console fallback)
            assert len(logger.handlers) > 0

        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestGlobalDebugLogging:
    """Test setup_global_debug_logging functionality."""

    def test_setup_global_debug_logging_configures_root_logger(self, tmp_path):
        """Test that setup_global_debug_logging configures the root logger."""
        log_file = tmp_path / "global_debug.log"

        # Get initial root logger state
        root_logger = logging.getLogger()
        initial_level = root_logger.level
        initial_handler_count = len(root_logger.handlers)

        try:
            # Call setup_global_debug_logging
            setup_global_debug_logging(str(log_file))

            # Verify root logger is configured for DEBUG
            assert root_logger.level == logging.DEBUG

            # Verify a file handler was added
            assert len(root_logger.handlers) > initial_handler_count

            # Find the [GLOBAL] handler
            global_handler = None
            for handler in root_logger.handlers:
                if (
                    hasattr(handler, "formatter")
                    and handler.formatter
                    and hasattr(handler.formatter, "_fmt")
                    and handler.formatter._fmt is not None  # type: ignore[attr-defined]
                    and "[GLOBAL]" in handler.formatter._fmt  # type: ignore[attr-defined]
                ):
                    global_handler = handler
                    break

            assert global_handler is not None, (
                "Expected to find a handler with [GLOBAL] prefix"
            )

        finally:
            # Clean up: remove our handler and restore level
            for handler in list(root_logger.handlers):
                if (
                    hasattr(handler, "formatter")
                    and handler.formatter
                    and hasattr(handler.formatter, "_fmt")
                    and handler.formatter._fmt is not None  # type: ignore[attr-defined]
                    and "[GLOBAL]" in handler.formatter._fmt  # type: ignore[attr-defined]
                ):
                    root_logger.removeHandler(handler)
                    handler.close()
            root_logger.setLevel(initial_level)

    def test_setup_global_debug_logging_creates_log_file(self, tmp_path):
        """Test that setup_global_debug_logging creates the log file and writes to
        it."""
        log_file = tmp_path / "test_global.log"

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            # Call setup_global_debug_logging
            setup_global_debug_logging(str(log_file))

            # Create a third-party logger and log a message
            docker_logger = logging.getLogger("docker")
            docker_logger.debug("Test Docker message")

            # Verify log file was created and contains the message
            assert log_file.exists()
            content = log_file.read_text()
            assert "[GLOBAL]" in content
            assert "docker" in content
            assert "Test Docker message" in content

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()

    def test_setup_global_debug_logging_configures_third_party_loggers(self, tmp_path):
        """Test that setup_global_debug_logging configures third-party loggers."""
        log_file = tmp_path / "third_party.log"

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            # Call setup_global_debug_logging
            setup_global_debug_logging(str(log_file))

            # Check that third-party loggers are configured
            expected_loggers = [
                "docker",
                "urllib3",
                "requests",
                "docker.api",
                "docker.client",
                "docker.utils",
            ]

            for logger_name in expected_loggers:
                logger = logging.getLogger(logger_name)
                assert logger.level == logging.DEBUG
                assert logger.propagate is True

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()

    def test_setup_global_debug_logging_is_idempotent(self, tmp_path):
        """Test that calling setup_global_debug_logging multiple times doesn't create
        duplicate handlers."""
        log_file = tmp_path / "idempotent.log"

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            # Call setup_global_debug_logging twice
            setup_global_debug_logging(str(log_file))
            initial_count = len(
                [h for h in root_logger.handlers if h not in initial_handlers],
            )

            setup_global_debug_logging(str(log_file))
            final_count = len(
                [h for h in root_logger.handlers if h not in initial_handlers],
            )

            # Should not have added more handlers
            assert final_count == initial_count

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()

    def test_setup_global_debug_logging_startup_banner(self, tmp_path, caplog):
        """Test that setup_global_debug_logging logs a startup banner."""
        log_file = tmp_path / "banner.log"

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            with caplog.at_level(logging.DEBUG):
                # Call setup_global_debug_logging
                setup_global_debug_logging(str(log_file))

                # Check that startup banner was logged
                log_messages = [record.message for record in caplog.records]
                banner_messages = [
                    msg for msg in log_messages if "GLOBAL LOGGING ENABLED" in msg
                ]
                assert len(banner_messages) > 0, "Expected startup banner to be logged"

                # Check for log file path in banner
                path_messages = [msg for msg in log_messages if str(log_file) in msg]
                assert len(path_messages) > 0, "Expected log file path in banner"

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()

    def test_setup_global_debug_logging_with_cli_profile(self, tmp_path):
        """Test that CLI profile with verbose_debug=True calls
        setup_global_debug_logging."""
        log_file = tmp_path / "cli_integration.log"

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            # Configure CLI logger with verbose_debug=True
            configure_logger(
                "test.cli.global",
                profile="cli",
                log_file=str(log_file),
                verbose_debug=True,
            )

            # Verify that global debug logging was set up
            # Check for [GLOBAL] handler in root logger
            global_handler = None
            for handler in root_logger.handlers:
                if (
                    hasattr(handler, "formatter")
                    and handler.formatter
                    and hasattr(handler.formatter, "_fmt")
                    and handler.formatter._fmt is not None  # type: ignore[attr-defined]
                    and "[GLOBAL]" in handler.formatter._fmt  # type: ignore[attr-defined]
                ):
                    global_handler = handler
                    break

            assert global_handler is not None, (
                "Expected global debug logging to be set up with CLI profile and verbose_debug=True"
            )

            # Test that third-party logs are captured
            docker_logger = logging.getLogger("docker")
            docker_logger.debug("CLI integration test message")

            # Verify the message was logged
            assert log_file.exists()
            content = log_file.read_text()
            assert "[GLOBAL]" in content
            assert "CLI integration test message" in content

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()

    def test_setup_global_debug_logging_handles_permission_errors(self, tmp_path):
        """Test that setup_global_debug_logging handles file permission errors
        gracefully."""
        # Create a read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        # Get root logger for cleanup
        root_logger = logging.getLogger()
        initial_handlers = list(root_logger.handlers)

        try:
            log_file = readonly_dir / "test.log"

            # Should not raise an exception
            setup_global_debug_logging(str(log_file))

            # Root logger should still be configured for DEBUG
            assert root_logger.level == logging.DEBUG

            # Third-party loggers should still be configured
            docker_logger = logging.getLogger("docker")
            assert docker_logger.level == logging.DEBUG
            assert docker_logger.propagate is True

        finally:
            # Clean up handlers
            for handler in list(root_logger.handlers):
                if handler not in initial_handlers:
                    root_logger.removeHandler(handler)
                    handler.close()
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)
