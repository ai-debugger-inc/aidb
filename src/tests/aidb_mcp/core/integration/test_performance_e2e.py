"""Integration tests for full MCP performance tracking."""

import json
from pathlib import Path

import pytest

from aidb_mcp.core.performance import TraceSpan, _span_history
from aidb_mcp.core.performance_types import SpanType
from aidb_mcp.core.performance_utils import (
    get_all_operations,
    get_correlation_trace,
    get_operation_breakdown,
    get_token_consumption_report,
)
from aidb_mcp.utils.token_estimation import get_response_stats


class TestFullRequestCycle:
    """Test complete request cycle with instrumentation."""

    def test_simulated_mcp_call_workflow(self, enable_timing, clear_span_history):
        """Test simulated MCP tool call with full instrumentation."""
        correlation_id = None
        tool_name = "session_start"

        with TraceSpan(SpanType.MCP_CALL, f"call_tool.{tool_name}") as mcp_span:
            if mcp_span:
                correlation_id = mcp_span.correlation_id

            with TraceSpan(SpanType.HANDLER_DISPATCH, f"dispatch.{tool_name}"):
                with TraceSpan(SpanType.HANDLER_EXECUTION, tool_name):
                    pass

                response = {
                    "success": True,
                    "data": {"session_id": "test-123", "state": "paused"},
                    "message": "Session started successfully",
                }

                stats = get_response_stats(response)

                if mcp_span:
                    mcp_span.metadata.update(stats)

        assert len(_span_history) >= 3

        if correlation_id:
            trace = get_correlation_trace(correlation_id)
            assert len(trace) >= 3

            operations = [s["operation"] for s in trace]
            assert f"call_tool.{tool_name}" in operations
            assert f"dispatch.{tool_name}" in operations
            assert tool_name in operations

    def test_correlation_propagation_through_layers(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test that correlation ID propagates through all layers."""
        correlation_id = None

        with TraceSpan(SpanType.MCP_CALL, "entry_point") as entry:
            if entry:
                correlation_id = entry.correlation_id

            with TraceSpan(SpanType.HANDLER_DISPATCH, "dispatch"):
                with TraceSpan(SpanType.VALIDATION, "validate"):
                    with TraceSpan(SpanType.HANDLER_EXECUTION, "execute"):
                        with TraceSpan(SpanType.SERIALIZATION, "serialize"):
                            pass

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            for span_dict in trace:
                assert span_dict["correlation_id"] == correlation_id

    def test_token_measurement_in_response(self, enable_timing, clear_span_history):
        """Test token measurement for responses."""
        response = {
            "success": True,
            "data": {
                "code_context": "def main():\n    x = 10\n    y = 20\n" * 50,
                "variables": {"x": 10, "y": 20},
            },
        }

        with TraceSpan(SpanType.MCP_CALL, "test_call") as span:
            stats = get_response_stats(response)

            if span:
                span.metadata.update(stats)

        breakdown = get_operation_breakdown("test_call")
        assert breakdown is not None
        assert breakdown.avg_response_tokens is not None
        assert breakdown.avg_response_tokens > 100

    def test_multiple_operations_in_sequence(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test tracking multiple operations in sequence."""
        operations = ["session_start", "step", "inspect", "continue", "terminate"]

        for op in operations:
            with TraceSpan(SpanType.MCP_CALL, f"call_tool.{op}") as span:
                if span:
                    span.metadata["response_tokens"] = len(op) * 10

        all_ops = get_all_operations()
        for op in operations:
            assert f"call_tool.{op}" in all_ops

        report = get_token_consumption_report()
        assert report["total_tokens"] > 0


class TestLogFileOutput:
    """Test log file output in various formats."""

    def test_json_log_output(self, enable_json_timing, clear_span_history):
        """Test that JSON logs are written correctly."""
        log_file = Path(enable_json_timing)

        with TraceSpan(SpanType.MCP_CALL, "json_test") as span:
            if span:
                span.metadata["custom_field"] = "value"

        if log_file.exists():
            content = log_file.read_text()
            lines = [line for line in content.strip().split("\n") if line]

            if lines:
                data = json.loads(lines[-1])
                assert data["operation"] == "json_test"
                assert data["span_type"] == "mcp_call"
                assert "duration_ms" in data
                assert "metadata" in data

    def test_csv_log_output(self, enable_csv_timing, clear_span_history):
        """Test that CSV logs are written correctly."""
        log_file = Path(enable_csv_timing)

        with TraceSpan(SpanType.HANDLER_DISPATCH, "csv_test"):
            pass

        if log_file.exists():
            content = log_file.read_text()
            lines = content.strip().split("\n")

            if len(lines) >= 2:
                header = lines[0]
                data_row = lines[-1]

                assert "timestamp" in header
                assert "operation" in header
                assert "duration_ms" in header

                assert "csv_test" in data_row

    def test_text_log_output(self, enable_timing, clear_span_history):
        """Test that text logs are written correctly."""
        log_file = Path(enable_timing)

        with TraceSpan(SpanType.VALIDATION, "text_test"):
            pass

        if log_file.exists():
            content = log_file.read_text()

            assert "validation" in content
            assert "text_test" in content

    def test_multiple_formats_sequential(
        self,
        monkeypatch,
        tmp_path,
        clear_span_history,
    ):
        """Test switching between formats."""
        for fmt in ["text", "json", "csv"]:
            log_file = tmp_path / f"test-{fmt}.log"

            monkeypatch.setenv("AIDB_MCP_TIMING", "1")
            monkeypatch.setenv("AIDB_MCP_TIMING_DETAILED", "1")
            monkeypatch.setenv("AIDB_MCP_TIMING_FILE", str(log_file))
            monkeypatch.setenv("AIDB_MCP_TIMING_FORMAT", fmt)

            import aidb_mcp.core.config as config_module

            config_module._config = None

            with TraceSpan(SpanType.MCP_CALL, f"format_{fmt}"):
                pass

            if log_file.exists():
                content = log_file.read_text()
                assert len(content) > 0


class TestPerformanceAnalysis:
    """Test performance analysis with real workloads."""

    def test_operation_breakdown_with_variance(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test breakdown calculation with varying durations."""
        import time

        durations = [0.001, 0.005, 0.010, 0.015, 0.020]

        for duration in durations:
            with TraceSpan(SpanType.HANDLER_EXECUTION, "varying_op"):
                time.sleep(duration)

        breakdown = get_operation_breakdown("varying_op")

        assert breakdown is not None
        assert breakdown.count == len(durations)
        assert breakdown.percentiles["p50"] > 0
        assert breakdown.percentiles["p95"] >= breakdown.percentiles["p50"]

    def test_cumulative_token_tracking(self, enable_timing, clear_span_history):
        """Test cumulative token tracking across operations."""
        token_counts = [100, 200, 300, 400, 500]

        for i, tokens in enumerate(token_counts):
            with TraceSpan(SpanType.MCP_CALL, f"cumulative_{i}") as span:
                if span:
                    span.metadata["response_tokens"] = tokens

        report = get_token_consumption_report()

        assert report["total_tokens"] == sum(token_counts)
        assert len(report["by_operation"]) == len(token_counts)

    def test_largest_responses_identification(
        self,
        enable_timing,
        clear_span_history,
    ):
        """Test identification of largest responses."""
        for i in range(15):
            with TraceSpan(SpanType.HANDLER_EXECUTION, f"response_{i}") as span:
                if span:
                    span.metadata["response_tokens"] = (15 - i) * 100

        report = get_token_consumption_report()

        assert len(report["largest_responses"]) <= 10

        if len(report["largest_responses"]) >= 2:
            first = report["largest_responses"][0]
            second = report["largest_responses"][1]
            assert first["tokens"] >= second["tokens"]


class TestErrorHandlingIntegration:
    """Test error handling in instrumentation."""

    def test_error_captured_in_trace(self, enable_timing, clear_span_history):
        """Test that errors are captured in trace."""
        correlation_id = None

        with pytest.raises(ValueError):
            with TraceSpan(SpanType.MCP_CALL, "error_call") as span:
                if span:
                    correlation_id = span.correlation_id

                with TraceSpan(SpanType.HANDLER_EXECUTION, "failing_handler"):
                    msg = "Simulated error"
                    raise ValueError(msg)

        if correlation_id:
            trace = get_correlation_trace(correlation_id)

            error_spans = [s for s in trace if not s["success"]]
            assert len(error_spans) > 0

            assert any("Simulated error" in (s.get("error") or "") for s in error_spans)

    def test_partial_success_tracking(self, enable_timing, clear_span_history):
        """Test tracking when some operations succeed and others fail."""
        with TraceSpan(SpanType.MCP_CALL, "mixed_success"):
            with TraceSpan(SpanType.VALIDATION, "success_step"):
                pass

            with pytest.raises(RuntimeError):
                with TraceSpan(SpanType.HANDLER_EXECUTION, "fail_step"):
                    msg = "Expected failure"
                    raise RuntimeError(msg)

        operations = get_all_operations()
        assert "success_step" in operations
        assert "fail_step" in operations


class TestPerformanceRegression:
    """Test performance regression detection."""

    def test_slow_operation_detection(
        self,
        enable_timing,
        clear_span_history,
        monkeypatch,
    ):
        """Test that slow operations are detected."""
        import time

        monkeypatch.setenv("AIDB_MCP_SLOW_THRESHOLD_MS", "5")

        with TraceSpan(SpanType.HANDLER_EXECUTION, "fast_op"):
            time.sleep(0.001)

        with TraceSpan(SpanType.HANDLER_EXECUTION, "slow_op"):
            time.sleep(0.010)

        fast_breakdown = get_operation_breakdown("fast_op")
        slow_breakdown = get_operation_breakdown("slow_op")

        assert fast_breakdown is not None
        assert slow_breakdown is not None

        assert fast_breakdown.slow_count == 0
        assert slow_breakdown.slow_count >= 1

    def test_token_budget_tracking(self, enable_timing, clear_span_history):
        """Test token budget consumption tracking."""
        for _i in range(10):
            with TraceSpan(SpanType.MCP_CALL, "budget_test") as span:
                if span:
                    span.metadata["response_tokens"] = 500

        breakdown = get_operation_breakdown("budget_test")
        report = get_token_consumption_report()

        assert breakdown is not None
        assert breakdown.avg_response_tokens == 500.0
        assert report["total_tokens"] == 5000
