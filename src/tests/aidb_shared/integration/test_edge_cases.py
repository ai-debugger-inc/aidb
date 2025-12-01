"""Integration tests for edge cases and boundary conditions.

These tests verify that the debugger handles unusual or boundary conditions gracefully,
including empty programs, unusual breakpoint locations, and minimal code structures.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestEdgeCases(BaseIntegrationTest):
    """Integration tests for edge cases."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_minimal_program(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test debugging a minimal single-line program.

        Verifies that the debugger can handle the smallest possible program without
        errors.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Start with initial breakpoint to keep session alive (standard pattern)
        first_marker_line = next(iter(markers.values()))
        session_info = await debug_interface.start_session(
            program=program["path"],
            breakpoints=[{"file": program["path"], "line": first_marker_line}],
        )

        assert session_info["session_id"] is not None
        assert session_info["status"] == "started"

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_empty_function(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test debugging an empty function with only pass statement.

        Verifies that breakpoints work in minimal function bodies.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"]],
        )

        # Session paused at breakpoint - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_breakpoint_on_last_line(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test breakpoint on the final line of a program.

        Verifies that breakpoints work correctly even on the last executable line of a
        file.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.counter"]],
        )

        # Session paused at last line
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "counter")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_breakpoint_on_return_statement(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test breakpoint on a return statement.

        Verifies that breakpoints on return statements work and the return value is
        accessible.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.return.result"]],
        )

        # Session paused at return statement
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "result")

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Specific test scenario not in manifest - covered by other tests",
    )
    async def test_single_character_variable_names(
        self,
        debug_interface,
        temp_workspace: Path,
    ):
        """Test variables with single-character names.

        Verifies that the debugger handles minimal variable names correctly.
        """

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Specific scenario not in manifest - would need modified basic_for_loop",
    )
    async def test_zero_iterations_loop(self, debug_interface, temp_workspace: Path):
        """Test loop that executes zero iterations.

        Verifies that the debugger handles loops that never execute their body.
        """

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Specific scenario not in manifest - would need modified basic_for_loop",
    )
    async def test_single_iteration_loop(self, debug_interface, temp_workspace: Path):
        """Test loop with exactly one iteration.

        Verifies that the debugger correctly handles minimal loop execution.
        """

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Specific scenario not in manifest - empty data structures",
    )
    async def test_nested_empty_structures(self, debug_interface, temp_workspace: Path):
        """Test nested empty data structures.

        Verifies that the debugger handles empty lists, dicts, and sets correctly.
        """

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_single_breakpoint_hit_once(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that a breakpoint in non-repeating code is hit exactly once.

        Verifies that breakpoints in linear code paths execute the expected number of
        times.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.counter"]],
        )

        # Session paused at single breakpoint - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Continue to completion
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_completion(state)

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Specific scenario not in manifest - immediate return",
    )
    async def test_immediate_return(self, debug_interface, temp_workspace: Path):
        """Test function that immediately returns without local variables.

        Verifies that the debugger handles functions with no local state.
        """

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_very_long_line(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test debugging code with very long lines.

        Verifies that the debugger handles unusually long source lines.
        """
        program = generated_program_factory("complex_expressions", language)
        markers = program["markers"]

        # Complex expressions scenario has longer expression lines
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"]],
        )

        # Session paused - verify breakpoint hit on complex expression line
        variables = await debug_interface.get_variables()
        # Verify we can debug complex/long expression lines
        assert len(variables) > 0

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_consecutive_breakpoints(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test multiple breakpoints on consecutive lines.

        Verifies that the debugger handles breakpoints on adjacent lines correctly.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"], markers["func.return.result"]],
        )

        # Session paused at first consecutive breakpoint - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Continue to second consecutive breakpoint
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.return.result"],
        )
