"""Tests for MCP response token budgets.

These tests validate that MCP tool responses stay within expected token budgets.
Token budgets are tighter in compact mode (AIDB_MCP_VERBOSE=0, the default).

Purpose:
- Catch accidental response bloat from code changes
- Document expected response sizes for each tool type
- Ensure agent context efficiency is maintained
"""

import json

import pytest

from aidb_mcp.responses.execution import ExecuteResponse, StepResponse
from aidb_mcp.responses.inspection import InspectResponse
from aidb_mcp.responses.session import SessionStartResponse
from aidb_mcp.utils.token_estimation import estimate_json_tokens


class TestResponseTokenBudgets:
    """Validate response token budgets for key MCP tools.

    Token budgets are approximate and use simple estimation (chars/4). These serve as
    regression guards, not exact measurements.
    """

    @pytest.fixture(autouse=True)
    def setup_compact_mode(self, monkeypatch):
        """Ensure compact mode is active for all tests."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

    def test_session_start_compact_budget(self):
        """Session start response should be under 150 tokens in compact mode.

        Key fields: session_id, mode, language, target, execution_state.
        No next_steps, no verbose guidance.
        """
        response = SessionStartResponse(
            session_id="abc12345-def6-7890-ghij-klmnopqrstuv",
            mode="launch",
            language="python",
            target="main.py",
            breakpoints_set=2,
            is_paused=True,
        )

        mcp_response = response.to_mcp_response()
        tokens = estimate_json_tokens(mcp_response)

        assert tokens is not None
        assert tokens < 150, (
            f"session_start response too large: {tokens} tokens. "
            f"Expected < 150 in compact mode. Response: {json.dumps(mcp_response)[:200]}..."
        )

        # Verify no next_steps in compact mode
        assert "next_steps" not in mcp_response

    def test_step_response_compact_budget(self):
        """Step response should be under 200 tokens in compact mode.

        Key fields: location, stopped, stop_reason, execution_state, code_snapshot.
        """
        code_context = {
            "formatted": "  15 | def process():\n> 16 |     x = compute()\n  17 |     return x",
        }

        response = StepResponse(
            action="over",
            location="main.py:16",
            stopped=True,
            stop_reason="step",
            session_id="test-session-id",
            code_context=code_context,
        )

        mcp_response = response.to_mcp_response()
        tokens = estimate_json_tokens(mcp_response)

        assert tokens is not None
        assert tokens < 200, (
            f"step response too large: {tokens} tokens. Expected < 200 in compact mode."
        )

        # Verify no next_steps in compact mode
        assert "next_steps" not in mcp_response

    def test_execute_response_compact_budget(self):
        """Execute response should be under 200 tokens in compact mode."""
        code_context = {
            "formatted": "  41 | while True:\n> 42 |     data = fetch()\n  43 |     process(data)",
        }

        response = ExecuteResponse(
            action="continue",
            location="worker.py:42",
            stopped=True,
            stop_reason="breakpoint",
            session_id="test-session-id",
            code_context=code_context,
        )

        mcp_response = response.to_mcp_response()
        tokens = estimate_json_tokens(mcp_response)

        assert tokens is not None
        assert tokens < 200, (
            f"execute response too large: {tokens} tokens. "
            f"Expected < 200 in compact mode."
        )

    def test_inspect_locals_compact_budget(self):
        """Inspect locals response should be under 100 tokens for small variable sets.

        Compact format: {"varName": {"v": "value", "t": "type"}}
        """
        response = InspectResponse(
            target="locals",
            session_id="test-session",
            result={
                "x": {"v": "42", "t": "int"},
                "name": {"v": "'hello'", "t": "str"},
                "data": {"v": "[1, 2, 3]", "t": "list", "varRef": 5},
            },
        )

        mcp_response = response.to_mcp_response()
        tokens = estimate_json_tokens(mcp_response)

        assert tokens is not None
        assert tokens < 100, (
            f"inspect locals response too large: {tokens} tokens. "
            f"Expected < 100 for 3 variables in compact mode."
        )


class TestResponseTokenBudgetsVerbose:
    """Validate that verbose mode responses are larger but still bounded."""

    @pytest.fixture(autouse=True)
    def setup_verbose_mode(self, monkeypatch):
        """Enable verbose mode for all tests."""
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

    def test_session_start_verbose_includes_next_steps(self):
        """Session start in verbose mode includes next_steps."""
        response = SessionStartResponse(
            session_id="abc12345-def6-7890-ghij-klmnopqrstuv",
            mode="launch",
            language="python",
            target="main.py",
            breakpoints_set=2,
        )

        mcp_response = response.to_mcp_response()
        tokens = estimate_json_tokens(mcp_response)

        # Verbose mode should include next_steps
        assert "next_steps" in mcp_response
        assert isinstance(mcp_response["next_steps"], list)

        # But still bounded (< 400 tokens even with guidance)
        assert tokens is not None
        assert tokens < 400, (
            f"session_start verbose response too large: {tokens} tokens. "
            f"Expected < 400 even in verbose mode."
        )

    def test_step_verbose_includes_next_steps(self):
        """Step response in verbose mode includes next_steps."""
        response = StepResponse(
            action="over",
            location="main.py:16",
            stopped=True,
            stop_reason="step",
            session_id="test-session-id",
        )

        mcp_response = response.to_mcp_response()

        # Verbose mode should include next_steps
        assert "next_steps" in mcp_response
        assert isinstance(mcp_response["next_steps"], list)


class TestCompactVsVerboseComparison:
    """Compare compact vs verbose response sizes."""

    def test_compact_significantly_smaller_than_verbose(self, monkeypatch):
        """Compact mode responses should be at least 30% smaller than verbose."""
        import aidb_common.config.runtime as runtime_module

        # Measure compact
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)
        runtime_module._config_manager = None

        compact_response = SessionStartResponse(
            session_id="test-session-12345678",
            mode="launch",
            language="python",
            target="main.py",
            breakpoints_set=2,
        ).to_mcp_response()
        compact_tokens = estimate_json_tokens(compact_response)

        # Measure verbose
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")
        runtime_module._config_manager = None

        verbose_response = SessionStartResponse(
            session_id="test-session-12345678",
            mode="launch",
            language="python",
            target="main.py",
            breakpoints_set=2,
        ).to_mcp_response()
        verbose_tokens = estimate_json_tokens(verbose_response)

        assert compact_tokens is not None
        assert verbose_tokens is not None

        # Compact should be at least 30% smaller
        savings_ratio = (verbose_tokens - compact_tokens) / verbose_tokens
        assert savings_ratio >= 0.30, (
            f"Compact mode only {savings_ratio:.1%} smaller than verbose. "
            f"Expected at least 30% savings. "
            f"Compact: {compact_tokens}, Verbose: {verbose_tokens}"
        )
