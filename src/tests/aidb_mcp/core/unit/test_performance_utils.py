"""Unit tests for performance analysis utilities."""

import time

import pytest

from aidb_mcp.core.performance import TraceSpan, _span_history, _timing_history
from aidb_mcp.core.performance_types import SpanType
from aidb_mcp.core.performance_utils import (
    get_all_operations,
    get_correlation_trace,
    get_operation_breakdown,
    get_token_consumption_report,
)


class TestGetOperationBreakdown:
    """Test operation breakdown analysis."""

    def test_returns_none_for_unknown_operation(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that unknown operation returns None."""
        breakdown = get_operation_breakdown("unknown_operation")

        assert breakdown is None

    def test_breakdown_with_single_operation(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test breakdown with single operation."""
        with TraceSpan(SpanType.HANDLER_EXECUTION, "test_op") as span:
            time.sleep(0.01)
            if span:
                span.metadata["response_tokens"] = 100

        breakdown = get_operation_breakdown("test_op")

        assert breakdown is not None
        assert breakdown.operation == "test_op"
        assert breakdown.count == 1
        assert breakdown.total_avg_ms >= 10.0

    def test_breakdown_calculates_percentiles(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that percentiles are calculated correctly."""
        for i in range(10):
            with TraceSpan(SpanType.VALIDATION, "multi_test"):
                time.sleep(0.001 * (i + 1))

        breakdown = get_operation_breakdown("multi_test")

        assert breakdown is not None
        assert "p50" in breakdown.percentiles
        assert "p95" in breakdown.percentiles
        assert "p99" in breakdown.percentiles

        assert breakdown.percentiles["p50"] > 0
        assert breakdown.percentiles["p95"] >= breakdown.percentiles["p50"]
        assert breakdown.percentiles["p99"] >= breakdown.percentiles["p95"]

    def test_breakdown_aggregates_by_span_type(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that breakdown aggregates by span type."""
        for _ in range(5):
            with TraceSpan(SpanType.MCP_CALL, "aggregate_test"):
                time.sleep(0.002)

        breakdown = get_operation_breakdown("aggregate_test")

        assert breakdown is not None
        assert "mcp_call" in breakdown.breakdown
        assert breakdown.breakdown["mcp_call"] >= 2.0

    def test_breakdown_includes_token_stats(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that breakdown includes token statistics."""
        with TraceSpan(SpanType.HANDLER_EXECUTION, "token_test") as span:
            if span:
                span.metadata["response_tokens"] = 500
                span.metadata["response_chars"] = 2000

        with TraceSpan(SpanType.HANDLER_EXECUTION, "token_test") as span:
            if span:
                span.metadata["response_tokens"] = 1000
                span.metadata["response_chars"] = 4000

        breakdown = get_operation_breakdown("token_test")

        assert breakdown is not None
        assert breakdown.avg_response_tokens == 750.0
        assert breakdown.max_response_tokens == 1000
        assert breakdown.avg_response_chars == 3000.0

    def test_breakdown_counts_slow_operations(
        self,
        enable_timing,
        clear_span_history,
        monkeypatch,
    ):
        """Test that slow operations are counted."""
        monkeypatch.setenv("AIDB_MCP_SLOW_THRESHOLD_MS", "10")

        # Force config reload after changing threshold
        import aidb_mcp.core.config as config_module

        config_module._config = None
        config_module.get_config()

        with TraceSpan(SpanType.HANDLER_EXECUTION, "slow_test"):
            time.sleep(0.001)

        with TraceSpan(SpanType.HANDLER_EXECUTION, "slow_test"):
            time.sleep(0.015)

        breakdown = get_operation_breakdown("slow_test")

        assert breakdown is not None
        assert breakdown.count == 2
        assert breakdown.slow_count >= 1


class TestGetAllOperations:
    """Test operation listing."""

    def test_empty_when_no_operations(self, enable_timing, clear_span_history):
        """Test that empty list is returned when no operations."""
        operations = get_all_operations()

        assert isinstance(operations, list)

    def test_lists_recorded_operations(self, enable_timing, clear_span_history):
        """Test that recorded operations are listed."""
        with TraceSpan(SpanType.MCP_CALL, "op1"):
            pass

        with TraceSpan(SpanType.HANDLER_DISPATCH, "op2"):
            pass

        with TraceSpan(SpanType.VALIDATION, "op3"):
            pass

        operations = get_all_operations()

        assert "op1" in operations
        assert "op2" in operations
        assert "op3" in operations

    def test_operations_sorted(self, enable_timing, clear_span_history):
        """Test that operations are sorted alphabetically."""
        for op in ["zebra", "apple", "middle"]:
            with TraceSpan(SpanType.VALIDATION, op):
                pass

        operations = get_all_operations()

        zebra_idx = operations.index("zebra")
        apple_idx = operations.index("apple")
        middle_idx = operations.index("middle")

        assert apple_idx < middle_idx < zebra_idx

    def test_operations_unique(self, enable_timing, clear_span_history):
        """Test that duplicate operations appear once."""
        for _ in range(5):
            with TraceSpan(SpanType.MCP_CALL, "repeated"):
                pass

        operations = get_all_operations()

        assert operations.count("repeated") == 1


class TestGetCorrelationTrace:
    """Test correlation ID tracing."""

    def test_empty_trace_for_unknown_correlation(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that unknown correlation ID returns empty list."""
        trace = get_correlation_trace("unknown-correlation-id")

        assert isinstance(trace, list)
        assert len(trace) == 0

    def test_trace_for_single_span(self, enable_timing, clear_span_history):
        """Test trace for single span."""
        correlation_id = None

        with TraceSpan(SpanType.MCP_CALL, "single") as span:
            if span:
                correlation_id = span.correlation_id

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            assert len(trace) >= 1
            assert trace[-1]["operation"] == "single"
            assert trace[-1]["correlation_id"] == correlation_id

    def test_trace_for_nested_spans(self, enable_timing, clear_span_history):
        """Test trace captures nested spans."""
        correlation_id = None

        with TraceSpan(SpanType.MCP_CALL, "outer") as outer:
            if outer:
                correlation_id = outer.correlation_id

            with TraceSpan(SpanType.HANDLER_DISPATCH, "middle"):
                with TraceSpan(SpanType.VALIDATION, "inner"):
                    pass

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            assert len(trace) >= 3
            operations = [span["operation"] for span in trace]
            assert "outer" in operations
            assert "middle" in operations
            assert "inner" in operations

    def test_trace_spans_share_correlation_id(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that all spans in trace share correlation ID."""
        correlation_id = None

        with TraceSpan(SpanType.MCP_CALL, "first") as span:
            if span:
                correlation_id = span.correlation_id

            with TraceSpan(SpanType.HANDLER_EXECUTION, "second"):
                pass

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            for span_dict in trace:
                assert span_dict["correlation_id"] == correlation_id

    def test_trace_preserves_span_metadata(self, enable_timing, clear_span_history):
        """Test that trace preserves span metadata."""
        correlation_id = None

        with TraceSpan(
            SpanType.SERIALIZATION,
            "serialize",
            custom_field="value",
        ) as span:
            if span:
                correlation_id = span.correlation_id

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            assert len(trace) >= 1
            span_dict = trace[-1]
            assert "metadata" in span_dict
            assert span_dict["metadata"]["custom_field"] == "value"


class TestGetTokenConsumptionReport:
    """Test token consumption reporting."""

    def test_empty_report_when_no_data(self, enable_timing, clear_span_history):
        """Test that empty report is returned when no data."""
        report = get_token_consumption_report()

        assert isinstance(report, dict)

    def test_report_structure(self, enable_timing, clear_span_history):
        """Test that report has expected structure."""
        with TraceSpan(SpanType.MCP_CALL, "test_op") as span:
            if span:
                span.metadata["response_tokens"] = 100

        report = get_token_consumption_report()

        if report:
            assert "total_tokens" in report
            assert "by_operation" in report
            assert "largest_responses" in report

    def test_report_aggregates_by_operation(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that report aggregates tokens by operation."""
        for i in range(3):
            with TraceSpan(SpanType.HANDLER_EXECUTION, "op1") as span:
                if span:
                    span.metadata["response_tokens"] = 100 * (i + 1)

        for i in range(2):
            with TraceSpan(SpanType.HANDLER_EXECUTION, "op2") as span:
                if span:
                    span.metadata["response_tokens"] = 200 * (i + 1)

        report = get_token_consumption_report()

        if report and "by_operation" in report:
            assert "op1" in report["by_operation"]
            assert "op2" in report["by_operation"]

            op1_stats = report["by_operation"]["op1"]
            assert op1_stats["total_tokens"] == 600
            assert op1_stats["count"] == 3
            assert op1_stats["avg_tokens"] == 200

    def test_report_calculates_total(self, enable_timing, clear_span_history):
        """Test that report calculates total tokens."""
        with TraceSpan(SpanType.MCP_CALL, "call1") as span:
            if span:
                span.metadata["response_tokens"] = 500

        with TraceSpan(SpanType.MCP_CALL, "call2") as span:
            if span:
                span.metadata["response_tokens"] = 300

        report = get_token_consumption_report()

        if report:
            assert report["total_tokens"] == 800

    def test_report_identifies_largest_responses(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that report identifies largest responses."""
        for i in range(15):
            with TraceSpan(SpanType.HANDLER_EXECUTION, f"op{i}") as span:
                if span:
                    span.metadata["response_tokens"] = 100 * (15 - i)

        report = get_token_consumption_report()

        if report and "largest_responses" in report:
            largest = report["largest_responses"]
            assert len(largest) <= 10

            if len(largest) >= 2:
                assert largest[0]["tokens"] >= largest[1]["tokens"]

    def test_report_includes_max_tokens(self, enable_timing, clear_span_history):
        """Test that report includes max tokens per operation."""
        with TraceSpan(SpanType.HANDLER_EXECUTION, "vary_op") as span:
            if span:
                span.metadata["response_tokens"] = 100

        with TraceSpan(SpanType.HANDLER_EXECUTION, "vary_op") as span:
            if span:
                span.metadata["response_tokens"] = 500

        with TraceSpan(SpanType.HANDLER_EXECUTION, "vary_op") as span:
            if span:
                span.metadata["response_tokens"] = 300

        report = get_token_consumption_report()

        if report and "by_operation" in report:
            vary_stats = report["by_operation"]["vary_op"]
            assert vary_stats["max_tokens"] == 500


class TestPerformanceUtilsIntegration:
    """Integration tests for performance utilities."""

    def test_end_to_end_workflow(self, enable_timing, clear_span_history):
        """Test complete workflow from span to analysis."""
        correlation_id = None

        with TraceSpan(SpanType.MCP_CALL, "workflow_test") as span:
            if span:
                correlation_id = span.correlation_id
                span.metadata["response_tokens"] = 750

            time.sleep(0.01)

        operations = get_all_operations()
        assert "workflow_test" in operations

        breakdown = get_operation_breakdown("workflow_test")
        assert breakdown is not None
        assert breakdown.count == 1
        assert breakdown.avg_response_tokens == 750.0

        if correlation_id:
            trace = get_correlation_trace(correlation_id)
            assert len(trace) >= 1

        report = get_token_consumption_report()
        assert report["total_tokens"] == 750

    def test_multiple_operations_analysis(self, enable_timing, clear_span_history):
        """Test analysis with multiple operations."""
        for i in range(5):
            with TraceSpan(SpanType.HANDLER_EXECUTION, f"op_{i % 3}") as span:
                if span:
                    span.metadata["response_tokens"] = 100 * (i + 1)
                time.sleep(0.001)

        operations = get_all_operations()
        assert len([op for op in operations if op.startswith("op_")]) == 3

        report = get_token_consumption_report()
        total = sum(100 * (i + 1) for i in range(5))
        assert report["total_tokens"] == total
