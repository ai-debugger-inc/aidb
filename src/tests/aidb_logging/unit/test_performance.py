"""Tests for aidb_logging.performance module."""

import logging
import time

import pytest

from aidb_logging.performance import (
    PerformanceLogger,
    PerformanceTracker,
    TimedOperation,
    log_performance,
)


class TestPerformanceLogger:
    """Tests for PerformanceLogger context manager."""

    def test_logs_operation_start(self, clean_logger: logging.Logger, caplog):
        """Test that operation start is logged."""
        with caplog.at_level(logging.DEBUG, logger=clean_logger.name):
            with PerformanceLogger(clean_logger, "test_operation"):
                pass

        assert any(
            "Starting test_operation" in record.message for record in caplog.records
        )

    def test_logs_successful_completion(self, clean_logger: logging.Logger, caplog):
        """Test that successful completion is logged."""
        with caplog.at_level(logging.DEBUG, logger=clean_logger.name):
            with PerformanceLogger(clean_logger, "test_operation"):
                time.sleep(0.01)

        completion_logs = [
            r for r in caplog.records if "completed" in r.message.lower()
        ]
        assert len(completion_logs) > 0

    def test_logs_error_on_exception(self, clean_logger: logging.Logger, caplog):
        """Test that errors are logged on exception."""
        msg = "test error"
        with caplog.at_level(logging.ERROR, logger=clean_logger.name):
            try:
                with PerformanceLogger(clean_logger, "test_operation"):
                    raise ValueError(msg)
            except ValueError:
                pass

        error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_logs) > 0
        assert any("failed" in r.message.lower() for r in error_logs)

    def test_uses_debug_level_for_fast_operations(
        self,
        clean_logger: logging.Logger,
        caplog,
    ):
        """Test that fast operations use DEBUG level."""
        with caplog.at_level(logging.DEBUG, logger=clean_logger.name):
            with PerformanceLogger(
                clean_logger,
                "fast_operation",
                slow_threshold_ms=1000,
            ):
                time.sleep(0.01)

        completion_logs = [
            r
            for r in caplog.records
            if "completed" in r.message.lower() and r.levelno == logging.DEBUG
        ]
        assert len(completion_logs) > 0

    def test_uses_warning_level_for_very_slow_operations(
        self,
        clean_logger: logging.Logger,
        caplog,
    ):
        """Test that very slow operations use WARNING level."""
        with caplog.at_level(logging.WARNING, logger=clean_logger.name):
            with PerformanceLogger(
                clean_logger,
                "slow_operation",
                slow_threshold_ms=5,
                very_slow_threshold_ms=10,
            ):
                time.sleep(0.02)

        warning_logs = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_logs) > 0

    def test_includes_context_in_logs(self, clean_logger: logging.Logger, caplog):
        """Test that context is included in logs."""
        with caplog.at_level(logging.DEBUG, logger=clean_logger.name):
            with PerformanceLogger(
                clean_logger,
                "test_operation",
                custom_key="custom_value",
            ):
                pass

        assert any(
            hasattr(record, "custom_key") and record.custom_key == "custom_value"
            for record in caplog.records
        )


class TestLogPerformanceDecorator:
    """Tests for log_performance decorator."""

    def test_decorates_function(self, clean_logger: logging.Logger, caplog):
        """Test that decorator works on functions."""

        @log_performance()
        def test_function():
            time.sleep(0.01)
            return "result"

        with caplog.at_level(logging.DEBUG):
            result = test_function()

        assert result == "result"
        assert any("completed" in record.message.lower() for record in caplog.records)

    def test_uses_custom_operation_name(self, clean_logger: logging.Logger, caplog):
        """Test that custom operation name is used."""

        @log_performance(operation="custom_operation")
        def test_function():
            pass

        with caplog.at_level(logging.DEBUG):
            test_function()

        assert any("custom_operation" in record.message for record in caplog.records)

    def test_uses_function_name_by_default(self, caplog):
        """Test that function name is used by default."""

        @log_performance()
        def my_test_function():
            pass

        with caplog.at_level(logging.DEBUG):
            my_test_function()

        assert any("my_test_function" in record.message for record in caplog.records)

    def test_respects_slow_threshold(self, caplog):
        """Test that slow threshold is respected."""

        @log_performance(slow_threshold_ms=5)
        def slow_function():
            time.sleep(0.01)

        with caplog.at_level(logging.INFO):
            slow_function()

        info_logs = [r for r in caplog.records if r.levelno >= logging.INFO]
        assert len(info_logs) > 0


class TestTimedOperation:
    """Tests for TimedOperation class."""

    def test_starts_timing(self):
        """Test that timing starts."""
        timer = TimedOperation("test")
        timer.start()

        assert timer.start_time is not None
        assert timer.end_time is None
        assert timer.duration_ms is None

    def test_stops_timing(self):
        """Test that timing stops and returns duration."""
        timer = TimedOperation("test")
        timer.start()
        time.sleep(0.01)
        duration = timer.stop()

        assert duration > 0
        assert timer.end_time is not None
        assert timer.duration_ms == duration

    def test_raises_error_if_not_started(self):
        """Test that error is raised if not started."""
        timer = TimedOperation("test")

        with pytest.raises(RuntimeError, match="was not started"):
            timer.stop()

    def test_resets_timer(self):
        """Test that timer resets."""
        timer = TimedOperation("test")
        timer.start()
        time.sleep(0.01)
        timer.stop()

        timer.reset()

        assert timer.start_time is None
        assert timer.end_time is None
        assert timer.duration_ms is None

    def test_string_representation_not_started(self):
        """Test string representation when not started."""
        timer = TimedOperation("test")
        assert "not started" in str(timer)

    def test_string_representation_running(self):
        """Test string representation when running."""
        timer = TimedOperation("test")
        timer.start()
        assert "running" in str(timer)

    def test_string_representation_completed(self):
        """Test string representation when completed."""
        timer = TimedOperation("test")
        timer.start()
        time.sleep(0.01)
        timer.stop()
        result = str(timer)
        assert "test:" in result
        assert "ms" in result


class TestPerformanceTracker:
    """Tests for PerformanceTracker class."""

    def test_tracks_multiple_operations(self):
        """Test that multiple operations can be tracked."""
        tracker = PerformanceTracker()

        tracker.start("operation1")
        time.sleep(0.01)
        duration1 = tracker.stop("operation1")

        tracker.start("operation2")
        time.sleep(0.01)
        duration2 = tracker.stop("operation2")

        assert duration1 > 0
        assert duration2 > 0
        assert tracker.get_duration("operation1") == duration1
        assert tracker.get_duration("operation2") == duration2

    def test_starts_total_timer_automatically(self):
        """Test that total timer starts automatically."""
        tracker = PerformanceTracker()

        tracker.start("operation1")
        assert tracker.total_timer.start_time is not None

    def test_raises_error_for_unstarted_operation(self):
        """Test that error is raised for unstarted operation."""
        tracker = PerformanceTracker()

        with pytest.raises(KeyError, match="was not started"):
            tracker.stop("unstarted")

    def test_logs_summary(self, clean_logger: logging.Logger, caplog):
        """Test that summary is logged."""
        tracker = PerformanceTracker(logger=clean_logger)

        tracker.start("op1")
        time.sleep(0.01)
        tracker.stop("op1")

        tracker.start("op2")
        time.sleep(0.01)
        tracker.stop("op2")

        with caplog.at_level(logging.INFO, logger=clean_logger.name):
            tracker.log_summary()

        assert any("Performance summary" in record.message for record in caplog.records)
        assert any("op1" in record.message for record in caplog.records)
        assert any("op2" in record.message for record in caplog.records)

    def test_resets_all_timers(self):
        """Test that all timers are reset."""
        tracker = PerformanceTracker()

        tracker.start("op1")
        tracker.stop("op1")

        tracker.reset()

        assert len(tracker.operations) == 0
        assert tracker.total_timer.start_time is None

    def test_returns_none_for_uncompleted_operation(self):
        """Test that None is returned for uncompleted operation."""
        tracker = PerformanceTracker()

        tracker.start("op1")
        assert tracker.get_duration("op1") is None

    def test_includes_total_in_summary(self, clean_logger: logging.Logger, caplog):
        """Test that total is included in summary."""
        tracker = PerformanceTracker(logger=clean_logger)

        tracker.start("op1")
        time.sleep(0.01)
        tracker.stop("op1")

        with caplog.at_level(logging.INFO, logger=clean_logger.name):
            tracker.log_summary()

        assert any("total=" in record.message for record in caplog.records)
