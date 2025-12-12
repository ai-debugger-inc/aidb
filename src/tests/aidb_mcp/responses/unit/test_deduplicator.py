"""Tests for ResponseDeduplicator."""

from typing import Any

import pytest

from aidb_mcp.responses.deduplicator import ResponseDeduplicator


class TestResponseDeduplicator:
    """Test ResponseDeduplicator functionality."""

    def test_removes_duplicate_execution_state(self):
        """Test removal of duplicate execution state fields."""
        response = {
            "data": {
                "is_paused": True,
                "state": "paused",
                "execution_state": {"status": "paused"},
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Duplicates removed
        assert "is_paused" not in result["data"]
        assert "state" not in result["data"]
        # Canonical kept
        assert result["data"]["execution_state"]["status"] == "paused"

    def test_removes_empty_children(self):
        """Test removal of empty children dict."""
        response = {
            "data": {
                "variables": {
                    "n": {
                        "value": "5",
                        "has_children": False,
                        "children": {},
                    },
                },
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Empty children omitted
        assert "children" not in result["data"]["variables"]["n"]
        # Other fields kept
        assert result["data"]["variables"]["n"]["value"] == "5"

    def test_preserves_meaningful_nulls(self):
        """Test that semantically meaningful nulls are preserved."""
        response = {
            "data": {
                "execution_state": {
                    "stop_reason": None,  # Meaningful: "not stopped"
                },
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # This null has meaning, should be kept
        assert "stop_reason" in result["data"]["execution_state"]
        assert result["data"]["execution_state"]["stop_reason"] is None

    def test_removes_code_context_lines_array(self):
        """Test removal of redundant code_context.lines field.

        The lines array duplicates the formatted string but is less readable. We keep
        the formatted string for better readability while saving tokens.
        """
        response = {
            "data": {
                "stack": [
                    {
                        "id": 1,
                        "name": "calculate_factorial",
                        "code_context": {
                            "lines": [
                                [4, "def calculate_factorial(n: int) -> int:"],
                                [5, '    """Calculate factorial of n."""'],
                                [6, "    if n <= 1:"],
                            ],
                            "current_line": 6,
                            "formatted": (
                                "File: /path/to/file.py\n"
                                " 4  def calculate_factorial(n: int) -> int:\n"
                                ' 5      """Calculate factorial of n."""\n'
                                " 6→     if n <= 1:\n"
                            ),
                        },
                    },
                ],
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Lines array removed (redundant)
        code_context = result["data"]["stack"][0]["code_context"]
        assert "lines" not in code_context

        # Formatted string preserved (canonical, more readable)
        assert "formatted" in code_context
        assert code_context["current_line"] == 6
        assert "def calculate_factorial" in code_context["formatted"]

        # Token savings: ~300-400 characters per code_context

    def test_removes_empty_locals(self):
        """Test removal of empty locals dict from stack frames."""
        response = {
            "data": {
                "stack": [
                    {
                        "id": 1,
                        "name": "main",
                        "locals": {},  # Empty
                    },
                ],
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Empty locals omitted
        assert "locals" not in result["data"]["stack"][0]
        # Other fields kept
        assert result["data"]["stack"][0]["name"] == "main"

    def test_removes_null_error_field(self):
        """Test removal of null error field on success."""
        response = {"data": {"result": "5", "error": None}}

        result = ResponseDeduplicator.deduplicate(response)

        # Null error omitted
        assert "error" not in result["data"]
        # Result kept
        assert result["data"]["result"] == "5"

    def test_removes_empty_string_module(self):
        """Test removal of empty/null module field."""
        response = {
            "data": {
                "frame": {
                    "name": "calculate",
                    "module": None,
                },
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Null module omitted
        assert "module" not in result["data"]["frame"]
        # Name kept
        assert result["data"]["frame"]["name"] == "calculate"

    def test_nested_structure_deduplication(self):
        """Test removal of duplicates in nested structures."""
        response = {
            "data": {
                "stop_reason": "step",
                "detailed_status": "stopped_after_step",
                "execution_state": {"stop_reason": "step"},
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Top-level duplicate removed
        assert "stop_reason" not in result["data"]
        # Canonical version in execution_state kept
        assert result["data"]["execution_state"]["stop_reason"] == "step"

    def test_preserves_data_when_no_canonical_exists(self):
        """Test that fields are kept if canonical field doesn't exist."""
        response = {
            "data": {
                "is_paused": True,
                "state": "paused",
                # No execution_state field
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Without canonical field, duplicates are kept
        assert "is_paused" in result["data"]
        assert "state" in result["data"]

    def test_handles_list_of_dicts(self):
        """Test deduplication works on lists of dictionaries."""
        response: dict[str, Any] = {
            "data": {
                "items": [
                    {"value": "1", "children": {}, "error": None},
                    {"value": "2", "children": {}, "error": None},
                ],
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # Empty fields removed from all list items
        for item in result["data"]["items"]:
            assert "children" not in item
            assert "error" not in item
            assert "value" in item

    def test_compact_mode_required(self, monkeypatch):
        """Test that deduplication only happens in compact mode."""
        # Mock verbose mode (not compact)
        from aidb_common.config.runtime import ConfigManager

        monkeypatch.setattr(ConfigManager, "is_mcp_verbose", lambda _: True)

        response = {
            "data": {
                "is_paused": True,
                "execution_state": {"status": "paused"},
                "children": {},
            },
        }

        result = ResponseDeduplicator.deduplicate(response)

        # In verbose mode, nothing removed
        assert "is_paused" in result["data"]
        assert "children" in result["data"]

    def test_preserves_top_level_data_key_even_when_empty(self):
        """Test that top-level data key is preserved even when empty.

        MCP protocol requires the data field. The deduplicator should not remove it even
        if all nested fields are empty/null.
        """
        response = {
            "success": True,
            "summary": "Test operation",
            "data": {},  # Empty data dict
        }

        result = ResponseDeduplicator.deduplicate(response)

        # data key must be preserved for MCP protocol compliance
        assert "data" in result
        assert result["data"] == {}
        assert result["success"] is True
        assert result["summary"] == "Test operation"
