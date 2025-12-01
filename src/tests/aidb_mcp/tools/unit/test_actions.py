"""Unit tests for MCP tool action helpers.

Tests for actions.py functions:
- validate_action
- get_action_enum
- normalize_action
- ACTION_ALIASES
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestValidateAction:
    """Tests for validate_action function."""

    def test_validate_action_valid_step_action(self) -> None:
        """Test that valid step action passes."""
        from aidb_mcp.tools.actions import StepAction, validate_action

        is_valid, error_msg = validate_action("into", StepAction)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_action_valid_session_action(self) -> None:
        """Test that valid session action passes."""
        from aidb_mcp.tools.actions import SessionAction, validate_action

        is_valid, error_msg = validate_action("start", SessionAction)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_action_valid_breakpoint_action(self) -> None:
        """Test that valid breakpoint action passes."""
        from aidb_mcp.tools.actions import BreakpointAction, validate_action

        is_valid, error_msg = validate_action("set", BreakpointAction)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_action_invalid(self) -> None:
        """Test that invalid action fails."""
        from aidb_mcp.tools.actions import StepAction, validate_action

        is_valid, error_msg = validate_action("invalid_action", StepAction)

        assert is_valid is False
        assert "Valid actions" in error_msg

    def test_validate_action_case_sensitive(self) -> None:
        """Test that validation is case-sensitive."""
        from aidb_mcp.tools.actions import StepAction, validate_action

        # Assuming enum values are lowercase
        is_valid, error_msg = validate_action("INTO", StepAction)

        # This should fail because the enum value is lowercase
        assert is_valid is False

    def test_validate_action_config_action(self) -> None:
        """Test validation with ConfigAction enum."""
        from aidb_mcp.tools.actions import ConfigAction, validate_action

        is_valid, error_msg = validate_action("env", ConfigAction)

        assert is_valid is True
        assert error_msg == ""

    def test_validate_action_variable_action(self) -> None:
        """Test validation with VariableAction enum."""
        from aidb_mcp.tools.actions import VariableAction, validate_action

        is_valid, error_msg = validate_action("get", VariableAction)

        assert is_valid is True
        assert error_msg == ""


class TestGetActionEnum:
    """Tests for get_action_enum function."""

    def test_get_action_enum_valid(self) -> None:
        """Test that valid action returns correct enum."""
        from aidb_mcp.tools.actions import StepAction, get_action_enum

        result = get_action_enum("into", StepAction)

        assert result == StepAction.INTO

    def test_get_action_enum_out(self) -> None:
        """Test getting 'out' step action."""
        from aidb_mcp.tools.actions import StepAction, get_action_enum

        result = get_action_enum("out", StepAction)

        assert result == StepAction.OUT

    def test_get_action_enum_over(self) -> None:
        """Test getting 'over' step action."""
        from aidb_mcp.tools.actions import StepAction, get_action_enum

        result = get_action_enum("over", StepAction)

        assert result == StepAction.OVER

    def test_get_action_enum_invalid_raises(self) -> None:
        """Test that invalid action raises ValueError."""
        from aidb_mcp.tools.actions import StepAction, get_action_enum

        with pytest.raises(ValueError) as exc_info:
            get_action_enum("invalid_action", StepAction)

        assert "Invalid action" in str(exc_info.value)
        assert "Valid actions" in str(exc_info.value)

    def test_get_action_enum_breakpoint(self) -> None:
        """Test getting breakpoint actions."""
        from aidb_mcp.tools.actions import BreakpointAction, get_action_enum

        result = get_action_enum("set", BreakpointAction)

        assert result == BreakpointAction.SET

    def test_get_action_enum_session(self) -> None:
        """Test getting session actions."""
        from aidb_mcp.tools.actions import SessionAction, get_action_enum

        result = get_action_enum("stop", SessionAction)

        assert result == SessionAction.STOP


class TestNormalizeAction:
    """Tests for normalize_action function."""

    def test_normalize_action_no_alias(self) -> None:
        """Test that action without alias is returned as-is (lowercased)."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("start", "session")

        assert result == "start"

    def test_normalize_action_uppercase_lowercased(self) -> None:
        """Test that uppercase action is lowercased."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("START", "session")

        assert result == "start"

    def test_normalize_action_session_begin_alias(self) -> None:
        """Test session 'begin' alias to 'start'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("begin", "session")

        assert result == "start"

    def test_normalize_action_session_terminate_alias(self) -> None:
        """Test session 'terminate' alias to 'stop'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("terminate", "session")

        assert result == "stop"

    def test_normalize_action_session_kill_alias(self) -> None:
        """Test session 'kill' alias to 'stop'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("kill", "session")

        assert result == "stop"

    def test_normalize_action_breakpoint_add_alias(self) -> None:
        """Test breakpoint 'add' alias to 'set'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("add", "breakpoint")

        assert result == "set"

    def test_normalize_action_breakpoint_delete_alias(self) -> None:
        """Test breakpoint 'delete' alias to 'remove'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("delete", "breakpoint")

        assert result == "remove"

    def test_normalize_action_breakpoint_rm_alias(self) -> None:
        """Test breakpoint 'rm' alias to 'remove'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("rm", "breakpoint")

        assert result == "remove"

    def test_normalize_action_variable_read_alias(self) -> None:
        """Test variable 'read' alias to 'get'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("read", "variable")

        assert result == "get"

    def test_normalize_action_variable_write_alias(self) -> None:
        """Test variable 'write' alias to 'set'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("write", "variable")

        assert result == "set"

    def test_normalize_action_variable_modify_alias(self) -> None:
        """Test variable 'modify' alias to 'patch'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("modify", "variable")

        assert result == "patch"

    def test_normalize_action_config_show_alias(self) -> None:
        """Test config 'show' alias to 'list'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("show", "config")

        assert result == "list"

    def test_normalize_action_config_capability_alias(self) -> None:
        """Test config 'capability' alias to 'capabilities'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("capability", "config")

        assert result == "capabilities"

    def test_normalize_action_adapter_install_alias(self) -> None:
        """Test adapter 'install' alias to 'download'."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("install", "adapter")

        assert result == "download"

    def test_normalize_action_unknown_tool(self) -> None:
        """Test that unknown tool returns action as-is."""
        from aidb_mcp.tools.actions import normalize_action

        result = normalize_action("custom_action", "unknown_tool")

        assert result == "custom_action"


class TestActionAliases:
    """Tests for ACTION_ALIASES dictionary."""

    def test_action_aliases_structure(self) -> None:
        """Test that ACTION_ALIASES has expected structure."""
        from aidb_mcp.tools.actions import ACTION_ALIASES

        assert isinstance(ACTION_ALIASES, dict)
        assert "session" in ACTION_ALIASES
        assert "breakpoint" in ACTION_ALIASES
        assert "config" in ACTION_ALIASES
        assert "variable" in ACTION_ALIASES
        assert "adapter" in ACTION_ALIASES

    def test_action_aliases_session_contains_begin(self) -> None:
        """Test that session aliases include 'begin'."""
        from aidb_mcp.tools.actions import ACTION_ALIASES

        assert "begin" in ACTION_ALIASES["session"]
        assert ACTION_ALIASES["session"]["begin"] == "start"

    def test_action_aliases_breakpoint_contains_add(self) -> None:
        """Test that breakpoint aliases include 'add'."""
        from aidb_mcp.tools.actions import ACTION_ALIASES

        assert "add" in ACTION_ALIASES["breakpoint"]
        assert ACTION_ALIASES["breakpoint"]["add"] == "set"


class TestEnumValues:
    """Tests for action enum values."""

    def test_step_action_values(self) -> None:
        """Test StepAction enum values."""
        from aidb_mcp.tools.actions import StepAction

        values = [e.value for e in StepAction]
        assert "into" in values
        assert "over" in values
        assert "out" in values

    def test_session_action_values(self) -> None:
        """Test SessionAction enum values."""
        from aidb_mcp.tools.actions import SessionAction

        values = [e.value for e in SessionAction]
        assert "start" in values
        assert "stop" in values
        assert "status" in values
        assert "list" in values

    def test_breakpoint_action_values(self) -> None:
        """Test BreakpointAction enum values."""
        from aidb_mcp.tools.actions import BreakpointAction

        values = [e.value for e in BreakpointAction]
        assert "set" in values
        assert "remove" in values
        assert "list" in values
        assert "clear_all" in values

    def test_variable_action_values(self) -> None:
        """Test VariableAction enum values."""
        from aidb_mcp.tools.actions import VariableAction

        values = [e.value for e in VariableAction]
        assert "get" in values
        assert "set" in values
        assert "patch" in values

    def test_config_action_values(self) -> None:
        """Test ConfigAction enum values."""
        from aidb_mcp.tools.actions import ConfigAction

        values = [e.value for e in ConfigAction]
        assert "env" in values
        assert "capabilities" in values
