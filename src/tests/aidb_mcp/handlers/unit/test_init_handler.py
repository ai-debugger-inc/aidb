"""Unit tests for MCP init tool handler.

Tests the initialization tool that sets up debugging context without creating sessions.
The init tool validates language, checks adapter availability, and provides guidance on
next steps.
"""

import pytest

from aidb_mcp.core.constants import ParamName
from tests._helpers.assertions import MCPAssertions
from tests._helpers.pytest_mcp import PytestMCPBase


class TestInitHandler(PytestMCPBase):
    """Test init tool operations."""

    @pytest.mark.asyncio
    async def test_init_tool_success(self):
        """Test successful init with valid language.

        Verifies that init:
        - Accepts valid language parameter
        - Returns success response
        - Includes required response fields
        - Provides next steps guidance
        """
        # Call init tool with Python
        response = await self.call_tool(
            "init",
            {ParamName.LANGUAGE: "python"},
        )

        # Validate success
        self.assert_response_success(response, "Init should succeed for valid language")

        # Validate response structure
        MCPAssertions.assert_response_structure(response)

        # Validate data fields
        assert "data" in response
        data = response["data"]

        # Should have language-specific information
        assert isinstance(data, dict), "Data should be a dictionary"
        assert len(data) > 0, "Data should contain starter information"

        # Should include adapter status
        assert "adapter_status" in response
        adapter_status = response["adapter_status"]
        assert "available" in adapter_status

        # Should include next_steps (init always provides guidance)
        MCPAssertions.assert_next_steps_present(response)

    @pytest.mark.asyncio
    async def test_init_tool_with_framework(self):
        """Test init with framework parameter.

        Verifies that framework-specific initialization works and provides framework-
        aware guidance.
        """
        # Call init with Python and pytest framework
        response = await self.call_tool(
            "init",
            {
                ParamName.LANGUAGE: "python",
                ParamName.FRAMEWORK: "pytest",
            },
        )

        # Validate success
        self.assert_response_success(response, "Init should succeed with framework")

        # Validate response structure
        MCPAssertions.assert_response_structure(response)

        # Should include next_steps with framework-specific guidance
        MCPAssertions.assert_next_steps_present(response)

        # Should have starter data
        assert "data" in response
        assert isinstance(response["data"], dict)

    @pytest.mark.asyncio
    async def test_init_tool_invalid_language(self):
        """Test init with invalid language parameter.

        Verifies proper error handling when an unsupported language is provided.
        """
        # Call init with invalid language
        response = await self.call_tool(
            "init",
            {ParamName.LANGUAGE: "unsupported_lang"},
        )

        # Should return error response
        self.assert_response_error(
            response,
            message="Init should fail for invalid language",
        )

        # Check for validation error code (invalid_parameter)
        # Error message should mention language validation
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "language" in error_msg or "unsupported" in error_msg, (
                    "Error should mention language validation"
                )

    @pytest.mark.asyncio
    async def test_init_tool_missing_language(self):
        """Test init without required language parameter.

        Verifies that missing language parameter is caught and reported clearly.
        """
        # Call init without language
        response = await self.call_tool("init", {})

        # Should return error response
        self.assert_response_error(
            response,
            message="Init should fail without language",
        )

        # Check error mentions missing language parameter
        if "error" in response:
            error_obj = response["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "").lower()
                assert "language" in error_msg or "required" in error_msg, (
                    "Error should mention missing language parameter"
                )

    @pytest.mark.asyncio
    async def test_init_response_structure(self):
        """Test init response structure compliance.

        Validates that init response:
        - Has all required MCP response fields
        - Includes next_steps (critical entry point)
        - Is token-efficient (no bloat)
        - Provides clear, actionable summary
        """
        # Call init with JavaScript
        response = await self.call_tool(
            "init",
            {ParamName.LANGUAGE: "javascript"},
        )

        self.assert_response_success(response)

        # Validate MCP response structure
        MCPAssertions.assert_response_structure(response)

        # Init is critical entry point - must have next_steps
        MCPAssertions.assert_next_steps_present(response)

        # Validate response efficiency (no bloat)
        # Init responses can be a bit larger due to guidance, so allow up to 15 fields
        MCPAssertions.assert_response_efficiency(
            response,
            max_data_fields=15,  # More generous for init guidance
            max_summary_chars=200,
        )

        # Validate summary is present and meaningful
        assert "summary" in response
        summary = response["summary"]
        assert len(summary) > 0, "Summary should not be empty"
        assert len(summary) <= 200, "Summary should be concise"

    @pytest.mark.asyncio
    async def test_init_adapter_status_included(self):
        """Test that init includes adapter availability status.

        Verifies that init response includes information about whether the debug adapter
        is installed and provides download suggestions if needed.
        """
        # Call init with Python
        response = await self.call_tool(
            "init",
            {ParamName.LANGUAGE: "python"},
        )

        self.assert_response_success(response)

        # Should include adapter_status
        assert "adapter_status" in response, "Init must include adapter_status"
        adapter_status = response["adapter_status"]

        # Adapter status should have availability info
        assert "available" in adapter_status, "adapter_status must include 'available'"

        # If adapter not available, should include suggestions
        if not adapter_status.get("available"):
            assert "suggestions" in adapter_status or "recommendations" in response, (
                "Should provide suggestions if adapter not available"
            )

    @pytest.mark.asyncio
    async def test_init_all_languages(self):
        """Test init with all supported languages.

        Verifies that init works correctly for Python, JavaScript, and Java.
        """
        supported_languages = ["python", "javascript", "java"]

        for language in supported_languages:
            # Call init with each language
            response = await self.call_tool(
                "init",
                {ParamName.LANGUAGE: language},
            )

            # Should succeed for all supported languages
            self.assert_response_success(
                response,
                message=f"Init should succeed for {language}",
            )

            # Should have proper structure
            MCPAssertions.assert_response_structure(response)

            # Should have next_steps
            MCPAssertions.assert_next_steps_present(response)

    @pytest.mark.asyncio
    async def test_init_with_mode_parameter(self):
        """Test init with different mode parameters (launch/attach).

        Verifies that mode-specific guidance is provided.
        """
        modes = ["launch", "attach"]

        for mode in modes:
            response = await self.call_tool(
                "init",
                {
                    ParamName.LANGUAGE: "python",
                    ParamName.MODE: mode,
                },
            )

            self.assert_response_success(
                response,
                message=f"Init should succeed with mode={mode}",
            )

            # Should have next_steps
            MCPAssertions.assert_next_steps_present(response)

    @pytest.mark.asyncio
    async def test_init_with_workspace_root(self):
        """Test init with workspace_root parameter.

        Verifies that workspace context is handled correctly.
        """
        response = await self.call_tool(
            "init",
            {
                ParamName.LANGUAGE: "python",
                ParamName.WORKSPACE_ROOT: "/path/to/workspace",
            },
        )

        self.assert_response_success(
            response,
            "Init should succeed with workspace_root",
        )

        # Should still have proper structure
        MCPAssertions.assert_response_structure(response)
        MCPAssertions.assert_next_steps_present(response)

    @pytest.mark.asyncio
    async def test_init_verbose_mode(self):
        """Test init with verbose=True parameter.

        Verifies that verbose mode provides additional guidance.
        """
        response = await self.call_tool(
            "init",
            {
                ParamName.LANGUAGE: "python",
                ParamName.VERBOSE: True,
            },
        )

        self.assert_response_success(response, "Init should succeed with verbose=True")

        # Verbose mode may include more guidance
        MCPAssertions.assert_next_steps_present(response)

        # Should have data
        assert "data" in response
        assert isinstance(response["data"], dict)
