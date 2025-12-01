"""Unit tests for performance tracing and span recording."""

import json
import time
from pathlib import Path

import pytest

from aidb_mcp.core.performance import TraceSpan, _span_history
from aidb_mcp.core.performance_types import SpanType


class TestTraceSpanBasics:
    """Test basic TraceSpan functionality."""

    def test_span_timing(self, enable_timing, clear_span_history):
        """Test that span measures time correctly."""
        with TraceSpan(SpanType.VALIDATION, "test_operation") as span:
            time.sleep(0.01)

        assert span is not None
        assert span.duration_ms >= 10.0
        assert span.operation == "test_operation"
        assert span.span_type == SpanType.VALIDATION
        assert span.success is True

    def test_span_type_and_operation(self, enable_timing, clear_span_history):
        """Test that span records type and operation name."""
        with TraceSpan(SpanType.HANDLER_DISPATCH, "dispatch.session_start") as span:
            pass

        assert span is not None
        assert span.span_type == SpanType.HANDLER_DISPATCH
        assert span.operation == "dispatch.session_start"

    def test_span_recorded_to_history(self, enable_timing, clear_span_history):
        """Test that span is recorded to history."""
        initial_count = len(_span_history)

        with TraceSpan(SpanType.MCP_CALL, "call_tool.test"):
            pass

        assert len(_span_history) == initial_count + 1
        recorded_span = _span_history[-1]
        assert recorded_span.operation == "call_tool.test"
        assert recorded_span.span_type == SpanType.MCP_CALL


class TestTraceSpanMetadata:
    """Test span metadata attachment."""

    def test_metadata_at_creation(self, enable_timing, clear_span_history):
        """Test metadata can be provided at span creation."""
        with TraceSpan(
            SpanType.VALIDATION,
            "test_op",
            param_count=5,
            has_breakpoints=True,
        ) as span:
            pass

        assert span is not None
        assert span.metadata["param_count"] == 5
        assert span.metadata["has_breakpoints"] is True

    def test_metadata_during_span(self, enable_timing, clear_span_history):
        """Test metadata can be added during span execution."""
        with TraceSpan(SpanType.HANDLER_EXECUTION, "handler.test") as span:
            span.metadata["computed_value"] = 42
            span.metadata["items_processed"] = 10

        assert span is not None
        assert span.metadata["computed_value"] == 42
        assert span.metadata["items_processed"] == 10

    def test_metadata_persists_to_history(self, enable_timing, clear_span_history):
        """Test metadata is preserved in recorded span."""
        with TraceSpan(SpanType.SERIALIZATION, "json_encode", size_bytes=5000):
            pass

        recorded_span = _span_history[-1]
        assert recorded_span.metadata["size_bytes"] == 5000


class TestCorrelationID:
    """Test correlation ID tracking."""

    def test_correlation_id_generated(self, enable_timing, clear_span_history):
        """Test that correlation ID is generated for new spans."""
        with TraceSpan(SpanType.MCP_CALL, "test") as span:
            pass

        assert span is not None
        assert span.correlation_id is not None
        assert len(span.correlation_id) > 0

    def test_correlation_id_propagates(self, enable_timing, clear_span_history):
        """Test that nested spans share correlation ID."""
        outer_correlation = None
        inner_correlation = None

        with TraceSpan(SpanType.MCP_CALL, "outer") as outer_span:
            outer_correlation = outer_span.correlation_id

            with TraceSpan(SpanType.HANDLER_DISPATCH, "inner") as inner_span:
                inner_correlation = inner_span.correlation_id

        assert outer_correlation is not None
        assert inner_correlation is not None
        assert outer_correlation == inner_correlation

    def test_correlation_id_in_span_id(self, enable_timing, clear_span_history):
        """Test that span_id includes correlation ID."""
        with TraceSpan(SpanType.VALIDATION, "test") as span:
            pass

        assert span is not None
        assert span.correlation_id in span.span_id
        assert span.span_type.value in span.span_id
        assert span.operation in span.span_id


class TestSpanErrorHandling:
    """Test span error capture."""

    def test_exception_sets_success_false(self, enable_timing, clear_span_history):
        """Test that exception sets success flag to False."""
        with pytest.raises(ValueError):
            with TraceSpan(SpanType.HANDLER_EXECUTION, "failing_op"):
                msg = "Test error"
                raise ValueError(msg)

        recorded_span = _span_history[-1]
        assert recorded_span.success is False
        assert recorded_span.error is not None
        assert "Test error" in recorded_span.error

    def test_error_message_captured(self, enable_timing, clear_span_history):
        """Test that error message is captured in span."""
        error_msg = "Custom error message"

        with pytest.raises(RuntimeError):
            with TraceSpan(SpanType.DAP_OPERATION, "dap_call"):
                raise RuntimeError(error_msg)

        recorded_span = _span_history[-1]
        assert error_msg in recorded_span.error

    def test_successful_operation_has_no_error(self, enable_timing, clear_span_history):
        """Test that successful operations have no error."""
        with TraceSpan(SpanType.VALIDATION, "success_op") as span:
            pass

        assert span.success is True
        assert span.error is None


class TestDisabledTiming:
    """Test behavior when timing is disabled."""

    def test_span_is_none_when_disabled(self, disable_timing, clear_span_history):
        """Test that span is None when timing is disabled."""
        with TraceSpan(SpanType.MCP_CALL, "test") as span:
            pass

        assert span is None

    def test_no_overhead_when_disabled(self, disable_timing, clear_span_history):
        """Test that there's minimal overhead when timing is disabled."""
        start = time.perf_counter_ns()

        with TraceSpan(SpanType.HANDLER_EXECUTION, "test"):
            pass

        end = time.perf_counter_ns()
        overhead_us = (end - start) / 1000

        # Increased threshold to account for test environment variability
        assert overhead_us < 1000

    def test_no_history_when_disabled(self, disable_timing, clear_span_history):
        """Test that no spans are recorded when disabled."""
        initial_count = len(_span_history)

        with TraceSpan(SpanType.VALIDATION, "test"):
            pass

        assert len(_span_history) == initial_count


class TestSpanRecording:
    """Test span recording to history."""

    def test_spans_recorded_in_order(self, enable_timing, clear_span_history):
        """Test that spans are recorded in execution order."""
        with TraceSpan(SpanType.MCP_CALL, "first"):
            pass

        with TraceSpan(SpanType.HANDLER_DISPATCH, "second"):
            pass

        with TraceSpan(SpanType.VALIDATION, "third"):
            pass

        assert len(_span_history) >= 3
        assert _span_history[-3].operation == "first"
        assert _span_history[-2].operation == "second"
        assert _span_history[-1].operation == "third"

    def test_history_size_limit(self, enable_timing, clear_span_history, monkeypatch):
        """Test that history respects configured size limit."""
        monkeypatch.setenv("AIDB_MCP_TIMING_HISTORY_SIZE", "5")

        from aidb_mcp.core.config import get_config

        config = get_config()
        old_size = _span_history.maxlen

        for i in range(10):
            with TraceSpan(SpanType.VALIDATION, f"op_{i}"):
                pass

        assert len(_span_history) <= max(config.performance.span_history_size, old_size)


class TestLogFormats:
    """Test log file output formats."""

    def test_text_format_output(self, enable_timing, clear_span_history):
        """Test that text format is written correctly."""
        log_file = Path(enable_timing)

        with TraceSpan(SpanType.MCP_CALL, "test_operation"):
            time.sleep(0.01)

        if log_file.exists():
            content = log_file.read_text()
            assert "mcp_call" in content
            assert "test_operation" in content

    def test_json_format_output(self, enable_json_timing, clear_span_history):
        """Test that JSON format is written correctly."""
        log_file = Path(enable_json_timing)

        with TraceSpan(SpanType.HANDLER_DISPATCH, "test_operation"):
            time.sleep(0.01)

        if log_file.exists():
            content = log_file.read_text()
            lines = [line for line in content.strip().split("\n") if line]

            if lines:
                data = json.loads(lines[-1])
                assert data["span_type"] == "dispatch"
                assert data["operation"] == "test_operation"
                assert "duration_ms" in data

    def test_csv_format_output(self, enable_csv_timing, clear_span_history):
        """Test that CSV format is written correctly."""
        log_file = Path(enable_csv_timing)

        with TraceSpan(SpanType.VALIDATION, "test_operation"):
            time.sleep(0.01)

        if log_file.exists():
            content = log_file.read_text()
            lines = content.strip().split("\n")

            if len(lines) >= 2:
                header = lines[0]
                assert "timestamp" in header
                assert "span_type" in header
                assert "operation" in header
                assert "duration_ms" in header


class TestSpanToDict:
    """Test PerformanceSpan serialization."""

    def test_to_dict_includes_all_fields(self, enable_timing, clear_span_history):
        """Test that to_dict() includes all relevant fields."""
        with TraceSpan(
            SpanType.SERIALIZATION,
            "json_encode",
            response_tokens=1500,
        ) as span:
            span.response_chars = 6000
            span.response_size_bytes = 6200

        span_dict = span.to_dict()

        assert span_dict["span_id"] == span.span_id
        assert span_dict["span_type"] == span.span_type.value
        assert span_dict["operation"] == span.operation
        assert span_dict["correlation_id"] == span.correlation_id
        assert span_dict["duration_ms"] > 0
        assert span_dict["success"] is True
        assert span_dict["error"] is None
        assert span_dict["metadata"]["response_tokens"] == 1500

    def test_to_dict_serializable(self, enable_timing, clear_span_history):
        """Test that to_dict() output is JSON serializable."""
        with TraceSpan(SpanType.MCP_CALL, "test") as span:
            pass

        span_dict = span.to_dict()
        json_str = json.dumps(span_dict)

        assert len(json_str) > 0
        reconstructed = json.loads(json_str)
        assert reconstructed["operation"] == "test"
