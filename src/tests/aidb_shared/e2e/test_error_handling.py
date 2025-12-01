"""E2E tests for error handling and graceful failure recovery.

These tests verify that the debugger handles errors gracefully, provides meaningful
error messages, and can recover from various failure scenarios.
"""

from pathlib import Path

import pytest

from aidb.common.errors import AidbError
from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest


class TestErrorHandling(BaseE2ETest):
    """E2E tests for error handling and recovery."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_invalid_breakpoint_location(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test graceful handling of invalid breakpoint locations.

        Verifies that setting a breakpoint at an invalid line doesn't crash the session
        and the debugger remains usable afterward.
        """
        program = generated_program_factory("basic_variables", language)

        # Start session with valid breakpoint (test error handling doesn't interfere)
        valid_line = program["markers"]["var.init.counter"]
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [valid_line],
        )

        # Session should be paused at valid breakpoint
        assert debug_interface.session_id is not None

        # Try to set breakpoint at invalid line (999) while paused
        # This should either raise an error or return unverified breakpoint
        invalid_line = 999
        try:
            bp = await debug_interface.set_breakpoint(program["path"], invalid_line)
            # If it succeeds, breakpoint should be unverified
            if isinstance(bp, dict):
                assert bp.get("verified") is not True, (
                    f"Expected breakpoint at line {invalid_line} to be unverified"
                )
        except (RuntimeError, ValueError, AidbError):
            # Expected - invalid breakpoint should fail
            pass

        # Session should still be usable - verify session is still active
        assert debug_interface.is_session_active

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_breakpoint_after_program_end(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test setting breakpoint beyond program's last line.

        Verifies that breakpoints set after the program's end are handled gracefully and
        don't cause session crashes.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Start with initial breakpoint to keep session alive (standard pattern)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.counter"]],
        )

        # Session is now paused at the breakpoint
        # Get the actual line count
        line_count = len(Path(program["path"]).read_text().splitlines())

        # Try to set breakpoint past the end of the file while session is paused
        # This should either raise an error or return unverified breakpoint
        invalid_line = line_count + 10
        try:
            bp = await debug_interface.set_breakpoint(program["path"], invalid_line)
            # If it succeeds, breakpoint should be unverified
            if isinstance(bp, dict):
                assert bp.get("verified") is not True, (
                    f"Expected breakpoint at line {invalid_line} (past EOF) to be unverified"
                )
        except (RuntimeError, ValueError, AidbError):
            # Expected - invalid breakpoint past EOF should fail
            pass

        # Session should still be active
        assert debug_interface.session_id is not None

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_invalid_file_path(
        self,
        debug_interface,
    ):
        """Test error handling when working with nonexistent files.

        Verifies that attempting operations on files that don't exist produces
        appropriate errors without crashing.
        """
        # Use a clearly nonexistent path that doesn't imply tmp directory usage
        nonexistent_file = "/nonexistent/path/does_not_exist_12345.py"

        # Starting session with nonexistent file should fail
        with pytest.raises((RuntimeError, FileNotFoundError, ValueError, AidbError)):
            await debug_interface.start_session(program=nonexistent_file)

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_session_already_stopped(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test handling operations on already-stopped sessions.

        Verifies that operations on stopped sessions are handled gracefully with
        appropriate error messages.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Start with breakpoint to ensure session doesn't terminate immediately (standard pattern)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.counter"]],
        )
        session_id = debug_interface.session_id

        # Explicitly stop the session (tests stopping, not auto-completion)
        await debug_interface.stop_session()

        # Verify session is stopped
        assert (
            debug_interface.session_id != session_id
            or debug_interface.session_id is None
        )

        # Operations on stopped session should fail gracefully
        with pytest.raises((RuntimeError, ValueError, AidbError)):
            await debug_interface.continue_execution()

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_step_when_not_paused(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test stepping when program is not paused at breakpoint.

        Verifies that step operations when not paused either fail gracefully or are no-
        ops, without crashing the session.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Start with breakpoint to ensure session is alive (standard pattern)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.counter"]],
        )

        # Session is now paused at breakpoint. Continue to let it run/complete
        await debug_interface.continue_execution()

        # Now program is running or completed - try to step without being paused
        # This should either:
        # 1. Raise an error (preferred)
        # 2. Be a no-op
        # 3. Complete execution
        try:
            await debug_interface.step_over()
            # If step succeeds, session should still be in valid state
            assert debug_interface.session_id is not None
        except (RuntimeError, ValueError, AidbError):
            # Expected - stepping when not paused should fail
            pass

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_syntax_error_in_source_file(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test error handling when source file has syntax errors.

        Verifies that attempting to debug a file with syntax errors produces appropriate
        errors and doesn't crash the system. The debugger should detect and report
        syntax errors before starting the session.
        """
        # Load the syntax_error_unclosed_bracket scenario - intentionally broken code
        program = generated_program_factory("syntax_error_unclosed_bracket", language)

        # Attempting to start a session with a syntax error should fail gracefully
        with pytest.raises((RuntimeError, SyntaxError, ValueError, AidbError)):
            await debug_interface.start_session(
                program=str(program["path"]),
                breakpoints=[{"file": str(program["path"]), "line": 10}],
            )
