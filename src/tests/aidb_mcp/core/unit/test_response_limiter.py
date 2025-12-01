"""Tests for ResponseLimiter."""

from typing import Any

import pytest

from aidb_mcp.core.response_limiter import ResponseLimiter


class TestResponseLimiter:
    """Test ResponseLimiter functionality."""

    def test_limits_stack_frames(self):
        """Test stack frame limiting."""
        frames = [{"id": i, "name": f"frame{i}"} for i in range(20)]

        limited, truncated = ResponseLimiter.limit_stack_frames(frames, max_frames=10)

        assert len(limited) == 10
        assert truncated is True
        assert limited[0]["id"] == 0  # First frames kept

    def test_no_truncation_when_under_limit(self):
        """Test no truncation when frames under limit."""
        frames = [{"id": i, "name": f"frame{i}"} for i in range(5)]

        limited, truncated = ResponseLimiter.limit_stack_frames(frames, max_frames=10)

        assert len(limited) == 5
        assert truncated is False
        assert limited == frames

    def test_limits_variables(self):
        """Test variable limiting."""
        variables = [{"name": f"var{i}", "value": str(i)} for i in range(30)]

        limited, truncated = ResponseLimiter.limit_variables(variables, max_vars=20)

        assert len(limited) == 20
        assert truncated is True
        assert limited[0]["name"] == "var0"

    def test_no_variable_truncation_when_under_limit(self):
        """Test no truncation when variables under limit."""
        variables = [{"name": f"var{i}", "value": str(i)} for i in range(10)]

        limited, truncated = ResponseLimiter.limit_variables(variables, max_vars=20)

        assert len(limited) == 10
        assert truncated is False

    def test_limits_code_context(self):
        """Test code context limiting."""
        lines = [(i, f"line {i}") for i in range(1, 21)]

        limited = ResponseLimiter.limit_code_context(
            lines,
            current_line=10,
            context_lines=3,
        )

        # Should get 3 before, current, 3 after = 7 lines
        assert len(limited) == 7
        assert limited[0][0] == 7  # Line 7
        assert limited[3][0] == 10  # Current line in middle
        assert limited[6][0] == 13  # Line 13

    def test_code_context_at_start_of_file(self):
        """Test code context when current line is at start."""
        lines = [(i, f"line {i}") for i in range(1, 21)]

        limited = ResponseLimiter.limit_code_context(
            lines,
            current_line=2,
            context_lines=3,
        )

        # Should get lines 1-5 (3 after, limited by start)
        assert len(limited) == 5
        assert limited[0][0] == 1  # Start of file
        assert limited[1][0] == 2  # Current line

    def test_code_context_at_end_of_file(self):
        """Test code context when current line is at end."""
        lines = [(i, f"line {i}") for i in range(1, 21)]

        limited = ResponseLimiter.limit_code_context(
            lines,
            current_line=19,
            context_lines=3,
        )

        # Should get lines 16-20 (3 before, limited by end)
        assert len(limited) == 5
        assert limited[0][0] == 16
        assert limited[-1][0] == 20  # End of file

    def test_code_context_with_missing_current_line(self):
        """Test code context when current line not found in lines."""
        lines = [(i, f"line {i}") for i in range(1, 11)]

        # Current line 50 doesn't exist in lines
        limited = ResponseLimiter.limit_code_context(
            lines,
            current_line=50,
            context_lines=3,
        )

        # Should return first 7 lines (2*3 + 1)
        assert len(limited) == 7
        assert limited[0][0] == 1

    def test_apply_token_budget_under_limit(self):
        """Test token budget when data is under limit."""
        data = "short text"
        max_tokens = 100

        result, truncated = ResponseLimiter.apply_token_budget(data, max_tokens)

        assert result == data
        assert truncated is False

    def test_apply_token_budget_over_limit(self):
        """Test token budget when data exceeds limit."""
        data = "a" * 1000  # Long string
        max_tokens = 10

        result, truncated = ResponseLimiter.apply_token_budget(data, max_tokens)

        # For now, just indicates truncation (Phase 3 will implement actual truncation)
        assert truncated is True

    def test_default_config_values(self, monkeypatch):
        """Test that defaults from config are used when no explicit limit."""
        from aidb_common.config.runtime import ConfigManager

        # Mock config to return specific values
        monkeypatch.setattr(
            ConfigManager,
            "get_mcp_max_stack_frames",
            lambda self: 5,
        )

        frames = [{"id": i} for i in range(10)]
        limited, truncated = ResponseLimiter.limit_stack_frames(frames)

        assert len(limited) == 5  # Used config default
        assert truncated is True

    def test_explicit_limit_overrides_config(self, monkeypatch):
        """Test that explicit limit overrides config default."""
        from aidb_common.config.runtime import ConfigManager

        # Mock config to return specific value
        monkeypatch.setattr(
            ConfigManager,
            "get_mcp_max_stack_frames",
            lambda self: 5,
        )

        frames = [{"id": i} for i in range(10)]
        limited, truncated = ResponseLimiter.limit_stack_frames(frames, max_frames=8)

        assert len(limited) == 8  # Used explicit value, not config
        assert truncated is True

    def test_empty_frames_list(self):
        """Test limiting with empty frames list."""
        frames: list[dict[str, Any]] = []

        limited, truncated = ResponseLimiter.limit_stack_frames(frames, max_frames=10)

        assert len(limited) == 0
        assert truncated is False

    def test_empty_variables_list(self):
        """Test limiting with empty variables list."""
        variables: list[dict[str, Any]] = []

        limited, truncated = ResponseLimiter.limit_variables(variables, max_vars=20)

        assert len(limited) == 0
        assert truncated is False
