"""Unit tests for DAP retry logic.

Tests the retry configuration, error classification, delay calculation, and retry
manager functionality.
"""

import pytest

from aidb.common.errors import (
    DebugConnectionError,
    DebugSessionLostError,
    DebugTimeoutError,
)
from aidb.dap.client.retry import (
    DAPRetryManager,
    RetryConfig,
    RetryStrategy,
    calculate_delay,
    is_retryable_error,
)


class TestRetryStrategy:
    """Tests for RetryStrategy enum."""

    def test_strategy_none_value(self):
        """RetryStrategy.NONE has correct value."""
        assert RetryStrategy.NONE.value == "none"

    def test_strategy_exponential_value(self):
        """RetryStrategy.EXPONENTIAL has correct value."""
        assert RetryStrategy.EXPONENTIAL.value == "exponential"

    def test_strategy_linear_value(self):
        """RetryStrategy.LINEAR has correct value."""
        assert RetryStrategy.LINEAR.value == "linear"


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_config_defaults(self):
        """RetryConfig has sensible defaults."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.strategy == RetryStrategy.EXPONENTIAL
        assert config.initial_delay == 0.1
        assert config.max_delay == 2.0
        assert config.backoff_factor == 2.0

    def test_config_custom_values(self):
        """RetryConfig accepts custom values."""
        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.LINEAR,
            initial_delay=0.5,
            max_delay=10.0,
            backoff_factor=3.0,
        )

        assert config.max_attempts == 5
        assert config.strategy == RetryStrategy.LINEAR
        assert config.initial_delay == 0.5
        assert config.max_delay == 10.0
        assert config.backoff_factor == 3.0


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_timeout_error_retryable(self):
        """DebugTimeoutError is retryable."""
        error = DebugTimeoutError("Operation timed out")

        assert is_retryable_error(error) is True

    def test_connection_error_retryable(self):
        """DebugConnectionError is retryable."""
        error = DebugConnectionError("Connection refused")

        assert is_retryable_error(error) is True

    def test_session_lost_error_not_retryable(self):
        """DebugSessionLostError is not retryable."""
        error = DebugSessionLostError("Session terminated")

        assert is_retryable_error(error) is False

    def test_connection_message_retryable(self):
        """Error with 'connection' in message is retryable."""
        error = RuntimeError("connection reset by peer")

        assert is_retryable_error(error) is True

    def test_timeout_message_retryable(self):
        """Error with 'timeout' in message is retryable."""
        error = RuntimeError("Read timeout exceeded")

        assert is_retryable_error(error) is True

    def test_adapter_not_ready_retryable(self):
        """Error with 'adapter not ready' is retryable."""
        error = RuntimeError("Adapter not ready yet")

        assert is_retryable_error(error) is True

    def test_handshake_error_retryable(self):
        """Error with 'handshake' is retryable."""
        error = RuntimeError("Handshake failed")

        assert is_retryable_error(error) is True

    def test_session_lost_message_not_retryable(self):
        """Error with 'session lost' is not retryable."""
        error = RuntimeError("Session lost unexpectedly")

        assert is_retryable_error(error) is False

    def test_terminated_message_not_retryable(self):
        """Error with 'terminated' is not retryable."""
        error = RuntimeError("Process terminated")

        assert is_retryable_error(error) is False

    def test_invalid_session_message_not_retryable(self):
        """Error with 'invalid session' is not retryable."""
        error = RuntimeError("Invalid session ID")

        assert is_retryable_error(error) is False

    def test_unknown_error_not_retryable(self):
        """Unknown errors default to not retryable."""
        error = RuntimeError("Something unexpected happened")

        assert is_retryable_error(error) is False


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_delay_none_strategy(self):
        """NONE strategy returns zero delay."""
        config = RetryConfig(strategy=RetryStrategy.NONE)

        assert calculate_delay(0, config) == 0
        assert calculate_delay(1, config) == 0
        assert calculate_delay(5, config) == 0

    def test_delay_linear_strategy(self):
        """LINEAR strategy returns linear delay."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            initial_delay=0.1,
            max_delay=2.0,
        )

        assert calculate_delay(0, config) == pytest.approx(0.1)
        assert calculate_delay(1, config) == pytest.approx(0.2)
        assert calculate_delay(2, config) == pytest.approx(0.3)

    def test_delay_exponential_strategy(self):
        """EXPONENTIAL strategy returns exponential delay."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            initial_delay=0.1,
            backoff_factor=2.0,
            max_delay=10.0,
        )

        assert calculate_delay(0, config) == 0.1
        assert calculate_delay(1, config) == 0.2
        assert calculate_delay(2, config) == 0.4
        assert calculate_delay(3, config) == 0.8

    def test_delay_capped_by_max(self):
        """Delay is capped at max_delay."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            initial_delay=1.0,
            backoff_factor=10.0,
            max_delay=5.0,
        )

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 5.0
        assert calculate_delay(2, config) == 5.0


class TestDAPRetryManagerOperations:
    """Tests for DAPRetryManager operation classification."""

    def test_idempotent_operations(self):
        """Verify idempotent operations."""
        idempotent_ops = [
            "setBreakpoints",
            "threads",
            "stackTrace",
            "scopes",
            "variables",
            "source",
            "initialize",
            "configurationDone",
        ]

        for op in idempotent_ops:
            assert op in DAPRetryManager.IDEMPOTENT_OPERATIONS

    def test_non_retryable_operations(self):
        """Verify non-retryable operations."""
        non_retryable_ops = [
            "continue",
            "next",
            "stepIn",
            "stepOut",
            "launch",
            "attach",
            "disconnect",
            "terminate",
            "setVariable",
        ]

        for op in non_retryable_ops:
            assert op in DAPRetryManager.NON_RETRYABLE_OPERATIONS


class TestDAPRetryManagerGetConfig:
    """Tests for DAPRetryManager.get_retry_config."""

    def test_non_retryable_returns_none(self):
        """Non-retryable operations return None."""
        assert DAPRetryManager.get_retry_config("continue") is None
        assert DAPRetryManager.get_retry_config("next") is None
        assert DAPRetryManager.get_retry_config("stepIn") is None

    def test_idempotent_returns_config(self):
        """Idempotent operations return config."""
        config = DAPRetryManager.get_retry_config("threads")

        assert config is not None
        assert isinstance(config, RetryConfig)
        assert config.max_attempts == 3

    def test_initialize_aggressive_retry(self):
        """Initialize has aggressive retry config."""
        config = DAPRetryManager.get_retry_config("initialize")

        assert config is not None
        assert config.max_attempts == 5
        assert config.initial_delay == 0.2
        assert config.max_delay == 3.0

    def test_configuration_done_aggressive_retry(self):
        """ConfigurationDone has aggressive retry config."""
        config = DAPRetryManager.get_retry_config("configurationDone")

        assert config is not None
        assert config.max_attempts == 5

    def test_evaluate_watch_context_retryable(self):
        """Evaluate in watch context is retryable."""
        context = {"context": "watch"}
        config = DAPRetryManager.get_retry_config("evaluate", context)

        assert config is not None

    def test_evaluate_hover_context_retryable(self):
        """Evaluate in hover context is retryable."""
        context = {"context": "hover"}
        config = DAPRetryManager.get_retry_config("evaluate", context)

        assert config is not None

    def test_evaluate_repl_context_not_retryable(self):
        """Evaluate in repl context is not retryable."""
        context = {"context": "repl"}
        config = DAPRetryManager.get_retry_config("evaluate", context)

        assert config is None

    def test_unknown_operation_returns_none(self):
        """Unknown operations return None."""
        config = DAPRetryManager.get_retry_config("unknownCommand")

        assert config is None


class TestRetryConfigBoundary:
    """Tests for RetryConfig boundary conditions."""

    def test_config_zero_attempts(self):
        """Config with zero max_attempts."""
        config = RetryConfig(max_attempts=0)

        assert config.max_attempts == 0

    def test_config_single_attempt(self):
        """Config with single max_attempt."""
        config = RetryConfig(max_attempts=1)

        assert config.max_attempts == 1

    def test_config_zero_delay(self):
        """Config with zero initial delay."""
        config = RetryConfig(initial_delay=0)

        assert config.initial_delay == 0
        assert calculate_delay(0, config) == 0

    def test_config_negative_backoff(self):
        """Config with fractional backoff (reduces delay)."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            initial_delay=1.0,
            backoff_factor=0.5,
            max_delay=10.0,
        )

        assert calculate_delay(0, config) == 1.0
        assert calculate_delay(1, config) == 0.5
        assert calculate_delay(2, config) == 0.25
