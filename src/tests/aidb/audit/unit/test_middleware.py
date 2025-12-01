"""Unit tests for audit middleware."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from aidb.audit.middleware import AuditContext, audit_operation
from aidb.common.errors import AidbError, ConfigurationError
from tests._fixtures.audit import mock_audit_logger  # noqa: F401
from tests._helpers.audit import AuditTestMixin


class TestAuditContext(AuditTestMixin):
    """Test AuditContext context manager."""

    @pytest.mark.asyncio
    async def test_context_basic_usage(self, mock_audit_logger):
        """Test basic usage of AuditContext."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="test.component",
                operation="test_operation",
                session_id="session_123",
            ) as context:
                assert context.component == "test.component"
                assert context.operation == "test_operation"
                assert context.session_id == "session_123"
                assert context._start_time is not None

            # Should have logged event on exit
            mock_audit_logger.log.assert_called_once()
            event = mock_audit_logger.log.call_args[0][0]
            assert isinstance(event, AuditEvent)
            assert event.component == "test.component"
            assert event.operation == "test_operation"
            assert event.level == AuditLevel.INFO

    @pytest.mark.asyncio
    async def test_context_with_parameters(self, mock_audit_logger):
        """Test AuditContext with parameters."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="api",
                operation="create_session",
                parameters={"language": "python", "target": "app.py"},
            ) as context:
                if context._event is not None:
                    context._event.parameters["debug_port"] = 5678

            event = mock_audit_logger.log.call_args[0][0]
            assert event.parameters["language"] == "python"
            assert event.parameters["target"] == "app.py"
            assert event.parameters["debug_port"] == 5678

    @pytest.mark.asyncio
    async def test_context_with_result(self, mock_audit_logger):
        """Test AuditContext with result data."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="api",
                operation="execute",
            ) as context:
                # Simulate operation
                context.set_result({"success": True, "data": "output"})

            event = mock_audit_logger.log.call_args[0][0]
            assert event.result["success"] is True
            assert event.result["data"] == "output"
            assert "duration_ms" in event.result

    @pytest.mark.asyncio
    async def test_context_with_metadata(self, mock_audit_logger):
        """Test AuditContext with metadata."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="adapter",
                operation="configure",
                metadata={"adapter": "debugpy", "version": "1.8.0"},
            ) as context:
                context.add_metadata("platform", "linux")

            event = mock_audit_logger.log.call_args[0][0]
            assert event.metadata["adapter"] == "debugpy"
            assert event.metadata["version"] == "1.8.0"
            assert event.metadata["platform"] == "linux"

    @pytest.mark.asyncio
    async def test_context_with_exception(self, mock_audit_logger):
        """Test AuditContext when exception occurs."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            msg = "Test error"
            with pytest.raises(ValueError, match="Test error"):
                async with AuditContext(
                    component="api",
                    operation="failing_op",
                ):
                    raise ValueError(msg)

            # Should log error event
            event = mock_audit_logger.log.call_args[0][0]
            assert event.level == AuditLevel.ERROR
            assert event.error == "Test error"
            assert event.result["success"] is False

    @pytest.mark.asyncio
    async def test_context_duration_tracking(self, mock_audit_logger):
        """Test that context tracks operation duration."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="api",
                operation="timed_op",
            ):
                await asyncio.sleep(0.1)

            event = mock_audit_logger.log.call_args[0][0]
            duration = event.result["duration_ms"]
            assert duration >= 100  # At least 100ms
            assert duration < 200  # But not too long

    @pytest.mark.asyncio
    async def test_context_with_custom_metadata(self, mock_audit_logger):
        """Test AuditContext with custom metadata fields."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="api",
                operation="custom_op",
                metadata={"tier": "PRO", "user": "pro_user"},
            ):
                pass

            event = mock_audit_logger.log.call_args[0][0]
            assert event.metadata["tier"] == "PRO"
            assert event.metadata["user"] == "pro_user"

    @pytest.mark.asyncio
    async def test_context_no_custom_metadata(self, mock_audit_logger):
        """Test AuditContext without custom metadata fields.

        Note: 'user' and 'pid' are system metadata automatically added by
        AuditEvent.__post_init__, so they will always be present. This test
        verifies that *custom* metadata (like 'tier') is not present when
        not explicitly provided.
        """
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="api",
                operation="free_op",
            ):
                pass

            event = mock_audit_logger.log.call_args[0][0]
            # Custom metadata should not be present
            assert "tier" not in event.metadata
            # System metadata (user, pid) is always present via __post_init__
            assert "user" in event.metadata  # OS username from $USER env var
            assert "pid" in event.metadata  # Process ID

    @pytest.mark.asyncio
    async def test_context_nested_usage(self, mock_audit_logger):
        """Test nested AuditContext usage."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            async with AuditContext(
                component="outer",
                operation="outer_op",
            ) as outer:
                outer.set_result({"outer": True})

                async with AuditContext(
                    component="inner",
                    operation="inner_op",
                ) as inner:
                    inner.set_result({"inner": True})

            # Should have logged both events
            assert mock_audit_logger.log.call_count == 2

            # Check both events
            calls = mock_audit_logger.log.call_args_list
            inner_event = calls[0][0][0]
            outer_event = calls[1][0][0]

            assert inner_event.component == "inner"
            assert inner_event.result["inner"] is True

            assert outer_event.component == "outer"
            assert outer_event.result["outer"] is True


class TestAuditOperationDecorator:
    """Test @audit_operation decorator."""

    @pytest.mark.asyncio
    async def test_decorator_on_async_function(self, mock_audit_logger):
        """Test decorator on async function."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="async_func")
            async def async_function(x: int, y: int) -> int:
                await asyncio.sleep(0.01)
                return x + y

            result = await async_function(2, 3)
            assert result == 5

            # Check audit event
            mock_audit_logger.log.assert_called_once()
            event = mock_audit_logger.log.call_args[0][0]
            assert event.component == "test"
            assert event.operation == "async_func"
            assert event.parameters == {"x": 2, "y": 3}
            assert event.result["value"] == 5
            assert event.result["success"] is True

    def test_decorator_on_sync_function(self, mock_audit_logger):
        """Test decorator on sync function."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="sync_func")
            def sync_function(name: str) -> str:
                return f"Hello {name}"

            result = sync_function("World")
            assert result == "Hello World"

            # For sync functions, we convert to async internally
            # The mock should still be called
            mock_audit_logger.log.assert_called_once()
            event = mock_audit_logger.log.call_args[0][0]
            assert event.component == "test"
            assert event.operation == "sync_func"
            assert event.parameters == {"name": "World"}
            assert event.result["value"] == "Hello World"

    @pytest.mark.asyncio
    async def test_decorator_with_exception(self, mock_audit_logger):
        """Test decorator when function raises exception."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="failing_func")
            async def failing_function():
                msg = "Intentional error"
                raise RuntimeError(msg)

            with pytest.raises(RuntimeError):
                await failing_function()

            # Should log error
            event = mock_audit_logger.log.call_args[0][0]
            assert event.level == AuditLevel.ERROR
            assert event.error == "Intentional error"
            assert event.result["success"] is False

    @pytest.mark.asyncio
    async def test_decorator_with_session_id(self, mock_audit_logger):
        """Test decorator extracts session_id from parameters."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="api", operation="session_op")
            async def session_function(session_id: str, data: dict) -> dict:
                return {"processed": True}

            await session_function("session_abc", {"key": "value"})

            event = mock_audit_logger.log.call_args[0][0]
            assert event.session_id == "session_abc"
            assert event.parameters["session_id"] == "session_abc"
            assert event.parameters["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_decorator_with_metadata(self, mock_audit_logger):
        """Test decorator captures component and operation metadata."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(
                component="adapter",
                operation="configure",
            )
            async def configure_adapter(config: dict) -> bool:
                return True

            await configure_adapter({"port": 5678})

            event = mock_audit_logger.log.call_args[0][0]
            assert event.component == "adapter"
            assert event.operation == "configure"
            assert event.parameters["config"] == {"port": 5678}

    @pytest.mark.asyncio
    async def test_decorator_with_level(self, mock_audit_logger):
        """Test decorator with custom audit level."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(
                component="debug",
                operation="trace",
                level=AuditLevel.DEBUG,
            )
            async def debug_function():
                return "debug output"

            await debug_function()

            event = mock_audit_logger.log.call_args[0][0]
            assert event.level == AuditLevel.DEBUG

    @pytest.mark.asyncio
    async def test_decorator_on_method(self, mock_audit_logger):
        """Test decorator on class method."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            class TestClass:
                @audit_operation(component="class", operation="method")
                async def async_method(self, value: int) -> int:
                    return value * 2

                @audit_operation(component="class", operation="sync_method")
                def sync_method(self, value: int) -> int:
                    return value + 1

            obj = TestClass()

            # Test async method
            result = await obj.async_method(5)
            assert result == 10

            event = mock_audit_logger.log.call_args_list[0][0][0]
            assert event.component == "class"
            assert event.operation == "method"
            assert event.parameters == {"value": 5}
            assert event.result["value"] == 10

            # Test sync method
            result = obj.sync_method(5)
            assert result == 6

            event = mock_audit_logger.log.call_args_list[1][0][0]
            assert event.component == "class"
            assert event.operation == "sync_method"
            assert event.parameters == {"value": 5}
            assert event.result["value"] == 6

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_attributes(self):
        """Test that decorator preserves function attributes."""

        @audit_operation(component="test", operation="preserved")
        async def documented_function(x: int) -> int:
            """This is a documented function."""
            return x * 2

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."

    @pytest.mark.asyncio
    async def test_decorator_with_complex_parameters(self, mock_audit_logger):
        """Test decorator with complex parameter types."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="complex")
            async def complex_function(
                data: dict[str, Any],
                items: list,
                *args,
                flag: bool = True,
                **kwargs,
            ) -> dict:
                return {"processed": True}

            await complex_function(
                {"key": "value"},
                [1, 2, 3],
                "extra_arg",
                flag=False,
                extra_kwarg="test",
            )

            event = mock_audit_logger.log.call_args[0][0]
            assert event.parameters["data"] == {"key": "value"}
            assert event.parameters["items"] == [1, 2, 3]
            assert event.parameters["args"] == ("extra_arg",)
            assert event.parameters["flag"] is False
            assert event.parameters["kwargs"] == {"extra_kwarg": "test"}

    @pytest.mark.asyncio
    async def test_decorator_performance_tracking(self, mock_audit_logger):
        """Test that decorator tracks performance metrics."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="perf", operation="slow_op")
            async def slow_operation():
                await asyncio.sleep(0.1)
                return "done"

            start = time.time()
            await slow_operation()
            elapsed = time.time() - start

            event = mock_audit_logger.log.call_args[0][0]
            duration = event.result["duration_ms"]

            # Check duration is reasonable
            assert duration >= 100  # At least 100ms
            assert duration < elapsed * 1000 + 50  # Not much more than actual

    @pytest.mark.asyncio
    async def test_decorator_with_generator(self, mock_audit_logger):
        """Test decorator on generator function."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="generator")
            async def async_generator(n: int):
                for i in range(n):
                    yield i

            # Consume generator
            result = []
            async for value in async_generator(3):
                result.append(value)

            assert result == [0, 1, 2]

            # Should still log the operation
            event = mock_audit_logger.log.call_args[0][0]
            assert event.component == "test"
            assert event.operation == "generator"
            assert event.parameters == {"n": 3}

    @pytest.mark.asyncio
    async def test_decorator_with_none_return(self, mock_audit_logger):
        """Test decorator with functions that return None."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):

            @audit_operation(component="test", operation="void_func")
            async def void_function(value: int) -> None:
                # Do something but return nothing
                pass

            result = await void_function(42)
            assert result is None

            event = mock_audit_logger.log.call_args[0][0]
            assert "value" not in event.result  # None results don't add value key
            assert event.result["success"] is True

    @pytest.mark.asyncio
    async def test_decorator_chain(self, mock_audit_logger):
        """Test multiple decorators on same function."""
        with patch(
            "aidb.audit.middleware.get_audit_logger",
            return_value=mock_audit_logger,
        ):
            call_count = 0

            def count_calls(func):
                async def wrapper(*args, **kwargs):
                    nonlocal call_count
                    call_count += 1
                    return await func(*args, **kwargs)

                return wrapper

            @count_calls
            @audit_operation(component="test", operation="chained")
            async def chained_function():
                return "result"

            result = await chained_function()
            assert result == "result"
            assert call_count == 1

            # Audit should still work
            mock_audit_logger.log.assert_called_once()
