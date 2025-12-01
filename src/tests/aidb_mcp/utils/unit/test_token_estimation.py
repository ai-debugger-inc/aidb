"""Unit tests for token estimation utilities."""

import json

import pytest

from aidb_mcp.core.performance_types import TokenEstimationMethod
from aidb_mcp.utils.token_estimation import (
    analyze_response_field_sizes,
    estimate_json_tokens,
    estimate_tokens,
    get_response_stats,
    get_top_context_consumers,
)


class TestEstimateTokens:
    """Test token estimation function."""

    def test_simple_estimation(self):
        """Test simple token estimation (chars/4)."""
        text = "Hello world! " * 100
        tokens = estimate_tokens(text, method="simple")

        assert tokens is not None
        assert tokens > 0
        assert tokens == len(text) // 4

    def test_disabled_estimation(self):
        """Test that disabled method returns None."""
        text = "Hello world!"
        tokens = estimate_tokens(text, method="disabled")

        assert tokens is None

    def test_none_text(self):
        """Test that None text returns None."""
        tokens = estimate_tokens(None, method="simple")

        assert tokens is None

    def test_empty_text(self):
        """Test estimation with empty text."""
        tokens = estimate_tokens("", method="simple")

        assert tokens is not None
        assert tokens == 0

    def test_simple_is_reasonable(self):
        """Test that simple estimation produces reasonable results."""
        text = "This is a test sentence with multiple words."
        tokens = estimate_tokens(text, method="simple")

        assert tokens is not None
        assert 5 < tokens < 20

    def test_long_text_estimation(self):
        """Test estimation with long text."""
        text = "word " * 1000
        tokens = estimate_tokens(text, method="simple")

        assert tokens is not None
        assert tokens > 1000


class TestGetResponseStats:
    """Test response statistics function."""

    def test_stats_with_sample_response(self, sample_response):
        """Test stats calculation with sample response."""
        stats = get_response_stats(sample_response)

        assert "response_chars" in stats
        assert "response_tokens" in stats
        assert "response_size_bytes" in stats

        assert stats["response_chars"] > 0
        assert stats["response_tokens"] > 0
        assert stats["response_size_bytes"] > 0

    def test_chars_equals_json_length(self, sample_response):
        """Test that char count equals JSON string length."""
        stats = get_response_stats(sample_response)
        json_str = json.dumps(sample_response, separators=(",", ":"))

        assert stats["response_chars"] == len(json_str)

    def test_bytes_equals_utf8_size(self, sample_response):
        """Test that byte size equals UTF-8 encoded size."""
        stats = get_response_stats(sample_response)
        json_str = json.dumps(sample_response, separators=(",", ":"))

        assert stats["response_size_bytes"] == len(json_str.encode("utf-8"))

    def test_token_estimate_reasonable(self, sample_response):
        """Test that token estimate is reasonable fraction of chars."""
        stats = get_response_stats(sample_response)

        assert stats["response_tokens"] is not None
        assert stats["response_tokens"] <= stats["response_chars"]
        assert stats["response_tokens"] > stats["response_chars"] // 5

    def test_empty_response(self):
        """Test stats with minimal response."""
        response: dict[str, str] = {}
        stats = get_response_stats(response)

        assert stats["response_chars"] == 2
        assert stats["response_tokens"] == 0

    def test_large_response(self, large_response):
        """Test stats with large response."""
        stats = get_response_stats(large_response)

        assert stats["response_chars"] > 10000
        assert stats["response_tokens"] > 2500


class TestAnalyzeResponseFieldSizes:
    """Test field-level analysis function."""

    def test_field_breakdown(self, sample_response):
        """Test that fields are analyzed correctly."""
        breakdown = analyze_response_field_sizes(sample_response)

        assert "success" in breakdown
        assert "data" in breakdown
        assert "message" in breakdown
        assert "next_steps" in breakdown

    def test_field_has_all_metrics(self, sample_response):
        """Test that each field has chars, tokens, bytes."""
        breakdown = analyze_response_field_sizes(sample_response)

        for _field_name, metrics in breakdown.items():
            assert "chars" in metrics
            assert "tokens" in metrics
            assert "bytes" in metrics

    def test_large_field_identified(self, sample_response):
        """Test that large field (code_context) has highest count."""
        breakdown = analyze_response_field_sizes(sample_response)

        data_size = breakdown["data"]["tokens"]
        message_size = breakdown["message"]["tokens"]

        assert data_size > message_size

    def test_field_tokens_sum_less_than_total(self, sample_response):
        """Test that field tokens sum is less than total (overhead)."""
        breakdown = analyze_response_field_sizes(sample_response)
        stats = get_response_stats(sample_response)

        field_token_sum = sum(metrics["tokens"] for metrics in breakdown.values())
        total_tokens = stats["response_tokens"]

        assert field_token_sum is not None
        assert total_tokens is not None
        assert field_token_sum < total_tokens

    def test_none_values_skipped(self):
        """Test that None values are skipped in analysis."""
        response = {
            "data": {"value": 42},
            "error": None,
            "warning": None,
        }

        breakdown = analyze_response_field_sizes(response)

        assert "data" in breakdown
        assert "error" not in breakdown
        assert "warning" not in breakdown


class TestGetTopContextConsumers:
    """Test identification of largest responses."""

    def test_top_consumers_sorted(self, sample_response, small_response):
        """Test that top consumers are sorted by token count."""
        responses = [small_response, sample_response]

        top = get_top_context_consumers(responses, top_n=2)

        assert len(top) == 2
        first_tokens = top[0]["stats"]["response_tokens"]
        second_tokens = top[1]["stats"]["response_tokens"]

        assert first_tokens is not None
        assert second_tokens is not None
        assert first_tokens >= second_tokens

    def test_top_n_limit(self, sample_response, large_response, small_response):
        """Test that only top_n results are returned."""
        responses = [sample_response, large_response, small_response] * 5

        top = get_top_context_consumers(responses, top_n=3)

        assert len(top) == 3

    def test_result_structure(self, sample_response):
        """Test that result has expected structure."""
        responses = [sample_response]

        top = get_top_context_consumers(responses, top_n=1)

        assert len(top) == 1
        result = top[0]

        assert "response" in result
        assert "stats" in result
        assert "field_breakdown" in result

        assert result["stats"]["response_tokens"] is not None
        assert len(result["field_breakdown"]) > 0

    def test_empty_list(self):
        """Test with empty response list."""
        top = get_top_context_consumers([], top_n=10)

        assert len(top) == 0

    def test_identifies_largest(self, sample_response, large_response, small_response):
        """Test that largest response is identified correctly."""
        responses = [small_response, sample_response, large_response]

        top = get_top_context_consumers(responses, top_n=1)

        assert len(top) == 1
        largest = top[0]

        large_stats = get_response_stats(large_response)
        assert largest["stats"]["response_tokens"] == large_stats["response_tokens"]


class TestEstimateJsonTokens:
    """Test JSON token estimation."""

    def test_dict_estimation(self):
        """Test token estimation for dictionary."""
        data = {"key1": "value1", "key2": "value2"}
        tokens = estimate_json_tokens(data)

        assert tokens is not None
        assert tokens > 0

    def test_list_estimation(self):
        """Test token estimation for list."""
        data = ["item1", "item2", "item3"]
        tokens = estimate_json_tokens(data)

        assert tokens is not None
        assert tokens > 0

    def test_nested_structure(self):
        """Test estimation with nested structures."""
        data = {
            "outer": {
                "inner": {
                    "deep": ["a", "b", "c"],
                },
            },
        }
        tokens = estimate_json_tokens(data)

        assert tokens is not None
        assert tokens > 5

    def test_large_structure(self, large_response):
        """Test estimation with large structure."""
        tokens = estimate_json_tokens(large_response)

        assert tokens is not None
        assert tokens > 2000

    def test_string_estimation(self):
        """Test that string can be estimated."""
        tokens = estimate_json_tokens("simple string")

        assert tokens is not None
        assert tokens > 0

    def test_number_estimation(self):
        """Test that number can be estimated."""
        tokens = estimate_json_tokens(42)

        assert tokens is not None
        assert tokens >= 0


class TestTokenEstimationIntegration:
    """Integration tests for token estimation."""

    def test_estimate_matches_stats(self, sample_response):
        """Test that estimate_tokens matches get_response_stats."""
        stats = get_response_stats(sample_response)
        json_str = json.dumps(sample_response, separators=(",", ":"))
        direct_tokens = estimate_tokens(json_str, method="simple")

        assert stats["response_tokens"] == direct_tokens

    def test_field_breakdown_sum_reasonable(self, sample_response):
        """Test that field breakdown sum is reasonable."""
        breakdown = analyze_response_field_sizes(sample_response)
        json_tokens = estimate_json_tokens(sample_response)

        field_sum = sum(metrics["tokens"] for metrics in breakdown.values())

        assert field_sum is not None
        assert json_tokens is not None
        assert abs(field_sum - json_tokens) < json_tokens * 0.2

    def test_consistent_across_calls(self, sample_response):
        """Test that estimation is consistent across calls."""
        tokens1 = estimate_json_tokens(sample_response)
        tokens2 = estimate_json_tokens(sample_response)

        assert tokens1 == tokens2

    def test_larger_response_more_tokens(
        self,
        small_response,
        sample_response,
        large_response,
    ):
        """Test that larger responses have more tokens."""
        small_tokens = estimate_json_tokens(small_response)
        sample_tokens = estimate_json_tokens(sample_response)
        large_tokens = estimate_json_tokens(large_response)

        assert small_tokens is not None
        assert sample_tokens is not None
        assert large_tokens is not None

        assert small_tokens < sample_tokens < large_tokens
