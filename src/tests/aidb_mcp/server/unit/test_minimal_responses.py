"""Test that responses are minimal with no redundancy (Phase 2)."""

import pytest

from aidb_mcp.responses.execution import ExecuteResponse, StepResponse
from aidb_mcp.responses.session import SessionStartResponse


class TestMinimalExecutionState:
    """Verify execution_state has minimal fields only."""

    def test_execution_state_no_redundant_fields(self, monkeypatch):
        """Verify execution_state contains only essential fields."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = StepResponse(
            action="over",
            location="test.py:17",
            stopped=True,
            stop_reason="step",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()
        exec_state = mcp_response["data"]["execution_state"]

        # Should have these essential fields
        assert "status" in exec_state
        assert "breakpoints_active" in exec_state
        assert "stop_reason" in exec_state

        # Should NOT have redundant fields
        assert "session_state" not in exec_state, (
            "session_state is redundant with status"
        )
        assert "next_action_guidance" not in exec_state, (
            "guidance is redundant with next_steps"
        )
        assert "current_location" not in exec_state, "location is in data.location"

    def test_location_in_top_level_data(self, monkeypatch):
        """Verify location is in top-level data, not duplicated in execution_state."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = ExecuteResponse(
            action="continue",
            location="test.py:42",
            stopped=True,
            stop_reason="breakpoint",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()

        # Location should be at top level
        assert mcp_response["data"]["location"] == "test.py:42"

        # But NOT in execution_state
        exec_state = mcp_response["data"]["execution_state"]
        assert "current_location" not in exec_state


class TestMinimalCodeSnapshot:
    """Verify code_snapshot has minimal fields only."""

    def test_code_snapshot_only_formatted_text(self, monkeypatch):
        """Verify code_snapshot contains only formatted text, no file/line."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        code_context = {
            "formatted": "  15 | def main():\n> 16 |     x = 5\n  17 |     return x",
        }

        response = StepResponse(
            action="over",
            location="test.py:16",
            stopped=True,
            stop_reason="step",
            session_id="test-session",
            code_context=code_context,
        )

        mcp_response = response.to_mcp_response()

        # Should have code_snapshot
        assert "code_snapshot" in mcp_response["data"]
        snapshot = mcp_response["data"]["code_snapshot"]

        # Should only have formatted field
        assert "formatted" in snapshot
        assert snapshot["formatted"] == code_context["formatted"]

        # Should NOT have redundant file/line fields
        assert "file" not in snapshot, "file duplicates data.location"
        assert "line" not in snapshot, "line duplicates data.location"

    def test_code_snapshot_absent_when_no_context(self, monkeypatch):
        """Verify code_snapshot is not included when no code_context."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = StepResponse(
            action="over",
            location="test.py:16",
            stopped=True,
            stop_reason="step",
            session_id="test-session",
            code_context=None,
        )

        mcp_response = response.to_mcp_response()

        # Should NOT have code_snapshot when no context
        assert "code_snapshot" not in mcp_response["data"]


class TestNextStepsInclusion:
    """Verify next_steps inclusion logic for different response types."""

    def test_session_start_excludes_next_steps_in_compact_mode(self, monkeypatch):
        """Verify session_start excludes next_steps in compact mode.

        Agents learn from schema descriptions, not response payloads. next_steps is
        redundant for AI agents.
        """
        # Compact mode (default)
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = SessionStartResponse(
            session_id="test-session",
            mode="launch",
            language="python",
            target="test.py",
            breakpoints_set=1,
        )

        mcp_response = response.to_mcp_response()

        # Session start should NOT include next_steps in compact mode
        assert "next_steps" not in mcp_response

    def test_step_excludes_next_steps_in_compact_mode(self, monkeypatch):
        """Verify step excludes next_steps in compact mode."""
        monkeypatch.delenv("AIDB_MCP_VERBOSE", raising=False)

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = StepResponse(
            action="over",
            location="test.py:17",
            stopped=True,
            stop_reason="step",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()

        # Step should NOT include next_steps in compact mode
        assert "next_steps" not in mcp_response

    def test_session_start_includes_next_steps_in_verbose_mode(self, monkeypatch):
        """Verify session_start includes next_steps in verbose mode."""
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = SessionStartResponse(
            session_id="test-session",
            mode="launch",
            language="python",
            target="test.py",
            breakpoints_set=1,
        )

        mcp_response = response.to_mcp_response()

        # Session start SHOULD include next_steps in verbose mode
        assert "next_steps" in mcp_response
        assert isinstance(mcp_response["next_steps"], list)
        assert len(mcp_response["next_steps"]) > 0

    def test_step_includes_next_steps_in_verbose_mode(self, monkeypatch):
        """Verify step includes next_steps in verbose mode."""
        monkeypatch.setenv("AIDB_MCP_VERBOSE", "1")

        import aidb_common.config.runtime as runtime_module

        runtime_module._config_manager = None

        response = StepResponse(
            action="over",
            location="test.py:17",
            stopped=True,
            stop_reason="step",
            session_id="test-session",
        )

        mcp_response = response.to_mcp_response()

        # Step SHOULD include next_steps in verbose mode
        assert "next_steps" in mcp_response
        assert isinstance(mcp_response["next_steps"], list)
