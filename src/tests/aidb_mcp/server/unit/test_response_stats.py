"""Unit tests for response statistics tracking in MCP server."""

import pytest

from aidb_mcp.core.performance import TraceSpan
from aidb_mcp.core.performance_types import SpanType
from aidb_mcp.server.app import AidbMCPServer


class TestResponseStatsTracking:
    """Test response statistics tracking functionality."""

    @pytest.fixture
    def server(self):
        """Create MCP server instance for testing."""
        return AidbMCPServer()

    @pytest.fixture
    def enable_timing(self, monkeypatch):
        """Enable performance timing for tests."""
        monkeypatch.setenv("AIDB_MCP_TIMING", "1")
        monkeypatch.setenv("AIDB_MCP_TIMING_DETAILED", "1")

    def test_attach_response_stats_with_compact_json(
        self,
        server,
        enable_timing,
        clear_span_history,
    ):
        """Test that response stats are calculated correctly from compact JSON."""
        compact_json = '{"success":true,"data":{"location":"test.py:10"}}'

        with TraceSpan(SpanType.MCP_CALL, "test_operation") as span:
            server._attach_response_stats(span, compact_json)

        assert span is not None
        assert span.response_chars == len(compact_json)
        assert span.response_tokens is not None
        assert span.response_tokens > 0
        assert span.response_size_bytes == len(compact_json.encode("utf-8"))

        # Verify token estimation is reasonable (compact_json is ~54 chars)
        # With simple estimation (chars/4), should be ~13-14 tokens
        assert 10 <= span.response_tokens <= 20

    def test_attach_response_stats_with_pretty_json(
        self,
        server,
        enable_timing,
        clear_span_history,
    ):
        """Test that response stats work with pretty-printed JSON."""
        pretty_json = """{
  "success": true,
  "data": {
    "location": "test.py:10"
  }
}"""

        with TraceSpan(SpanType.MCP_CALL, "test_operation") as span:
            server._attach_response_stats(span, pretty_json)

        assert span is not None
        assert span.response_chars == len(pretty_json)
        assert span.response_tokens is not None
        assert span.response_tokens > 0
        assert span.response_size_bytes == len(pretty_json.encode("utf-8"))

        # Pretty JSON should have more characters than compact
        assert span.response_chars > 54

    def test_attach_response_stats_with_none_span(self, server):
        """Test that method handles None span gracefully."""
        response_text = '{"success":true}'
        # Should not raise any exception
        server._attach_response_stats(None, response_text)

    def test_attach_response_stats_token_accuracy(
        self,
        server,
        enable_timing,
        clear_span_history,
    ):
        """Test that token counting doesn't double-serialize."""
        # This is a regression test for the bug where response_text
        # was wrapped in {"text": ...} causing double-serialization

        response_text = '{"success":true,"summary":"Test","data":{"key":"value"}}'
        expected_chars = len(response_text)

        with TraceSpan(SpanType.MCP_CALL, "test_operation") as span:
            server._attach_response_stats(span, response_text)

        assert span is not None
        # Should count the actual response text, not a wrapped version
        assert span.response_chars == expected_chars

        # If double-serialization occurred, we'd see something like:
        # '{"text":"{\\"success\\":true,...}"}'  which would be much longer
        # Verify we're not seeing that
        assert span.response_chars < expected_chars * 1.5

    def test_attach_response_stats_large_response(
        self,
        server,
        enable_timing,
        clear_span_history,
    ):
        """Test statistics tracking with large response."""
        # Simulate a large response with code snapshot
        large_response = (
            '{"success":true,"data":{"code_snapshot":"'
            + ("x" * 5000)
            + '","location":"test.py:100"}}'
        )

        with TraceSpan(SpanType.MCP_CALL, "test_operation") as span:
            server._attach_response_stats(span, large_response)

        assert span is not None
        assert span.response_chars > 5000
        assert span.response_tokens is not None
        # Simple estimation: ~5000 chars / 4 = ~1250 tokens
        assert span.response_tokens > 1000

    def test_attach_response_stats_unicode(
        self,
        server,
        enable_timing,
        clear_span_history,
    ):
        """Test statistics tracking with unicode content."""
        unicode_json = '{"success":true,"data":{"message":"Hello 世界 🌍"}}'

        with TraceSpan(SpanType.MCP_CALL, "test_operation") as span:
            server._attach_response_stats(span, unicode_json)

        assert span is not None
        assert span.response_chars == len(unicode_json)
        assert span.response_size_bytes == len(unicode_json.encode("utf-8"))
        # UTF-8 bytes should be more than char count due to multibyte chars
        assert span.response_size_bytes > span.response_chars
