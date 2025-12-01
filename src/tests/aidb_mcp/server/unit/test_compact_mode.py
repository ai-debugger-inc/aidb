"""Unit tests for compact mode functionality."""

import pytest

from aidb_mcp.responses.execution import ExecuteResponse


class TestCompactModeNextSteps:
    """Test that next_steps are conditionally included based on compact mode."""

    def test_next_steps_included_in_verbose_mode(self, monkeypatch):
        """Test that next_steps are included when verbose mode is enabled."""
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")

        # Clear cached config
        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = ExecuteResponse(
            action="continue",
            stopped=True,
            location="test.py:10",
            stop_reason="breakpoint",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()

        # Should include next_steps
        assert "next_steps" in mcp_response
        assert isinstance(mcp_response["next_steps"], list)
        assert len(mcp_response["next_steps"]) > 0

    def test_next_steps_excluded_by_default(self, monkeypatch):
        """Test that next_steps are excluded by default (compact mode)."""
        # Don't set any env var - compact is default
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        # Clear cached config
        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = ExecuteResponse(
            action="continue",
            stopped=True,
            location="test.py:10",
            stop_reason="breakpoint",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()

        # Should NOT include next_steps
        assert "next_steps" not in mcp_response

    def test_compact_mode_token_savings(self, monkeypatch):
        """Test that compact mode (default) provides significant token savings."""
        import json

        from aidb_mcp.utils.token_estimation import estimate_tokens

        # Test with verbose mode (human-friendly)
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")
        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = ExecuteResponse(
            action="continue",
            stopped=True,
            location="test.py:10",
            stop_reason="breakpoint",
            session_id="test-session",
        )

        verbose_response = response.to_mcp_response()
        verbose_json = json.dumps(verbose_response, indent=2)
        verbose_tokens = estimate_tokens(verbose_json)

        # Test with default (compact mode)
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)
        runtime_module._config_manager = None

        response2 = ExecuteResponse(
            action="continue",
            stopped=True,
            location="test.py:10",
            stop_reason="breakpoint",
            session_id="test-session",
        )

        compact_response = response2.to_mcp_response()
        compact_json = json.dumps(compact_response, separators=(",", ":"))
        compact_tokens = estimate_tokens(compact_json)

        # Compact (default) should be significantly smaller than verbose
        assert compact_tokens is not None
        assert verbose_tokens is not None
        assert compact_tokens < verbose_tokens

        # Should save at least 30% (next_steps + JSON whitespace)
        savings_pct = (1 - (compact_tokens / verbose_tokens)) * 100
        assert savings_pct >= 30, f"Only saved {savings_pct:.1f}%"

    def test_response_without_next_steps_unaffected(self, monkeypatch):
        """Test that responses without next_steps work the same in both modes."""
        from aidb_mcp.responses.base import Response

        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")
        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response_verbose = Response(summary="Test", success=True)
        mcp_verbose = response_verbose.to_mcp_response()

        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)
        runtime_module._config_manager = None

        response_compact = Response(summary="Test", success=True)
        mcp_compact = response_compact.to_mcp_response()

        # Both should not have next_steps (base Response returns None)
        assert "next_steps" not in mcp_verbose
        assert "next_steps" not in mcp_compact
