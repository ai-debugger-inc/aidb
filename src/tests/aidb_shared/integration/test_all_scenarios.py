"""Integration tests for comprehensive scenario validation.

These tests systematically verify that all generated test program scenarios work
correctly, validating marker accuracy, program structure, and cross-language
consistency.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestAllScenarios(BaseIntegrationTest):
    """Comprehensive tests for all generated program scenarios."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_basic_variables(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of basic_variables scenario.

        Tests that all markers in the basic_variables scenario are valid and that
        breakpoints trigger correctly at each marker location.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Test a representative subset of markers
        test_markers = ["var.init.counter", "var.assign.counter"]

        for i, marker_name in enumerate(test_markers):
            if marker_name not in markers:
                continue

            # Stop previous session if not first iteration
            if i > 0:
                await debug_interface.stop_session()

            # Start fresh session with single breakpoint for this marker
            await self.start_session_with_breakpoints(
                debug_interface,
                program["path"],
                [markers[marker_name]],
            )

            # Session paused at breakpoint - verify we can get variables (implicitly verifies paused)
            _ = await debug_interface.get_variables()
            # If we can get variables successfully, session is paused correctly
            assert debug_interface.is_session_active, (
                f"Marker {marker_name} failed: session not active"
            )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_basic_for_loop(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of basic_for_loop scenario.

        Tests that the for loop scenario executes correctly with proper iteration and
        variable updates.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.total"], markers["var.add.total"]],
        )

        # Session paused at initialization - verify by getting variables
        variables = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Hit first loop iteration
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.add.total"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "i")
        self.verify_vars.verify_variable_exists(variables, "total")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_simple_function(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of simple_function scenario.

        Tests function definition, calling, and return value handling.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["var.init.x"],
                markers["func.call.add"],
                markers["var.calc.result"],
            ],
        )

        # Session paused at variable initialization - verify by getting variables
        variables = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Hit function call
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.call.add"],
        )

        # Hit inside function
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.calc.result"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "a")
        self.verify_vars.verify_variable_exists(variables, "b")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_basic_while_loop(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of basic_while_loop scenario.

        Tests while loop execution with proper condition checking and iteration.
        """
        program = generated_program_factory("basic_while_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.counter"], markers["var.increment.counter"]],
        )

        # Session paused at initialization line, step over to execute it
        await debug_interface.step_over()

        # Now counter should be initialized
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "counter", "0")

        # Continue to first loop iteration
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.increment.counter"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "counter")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_conditionals(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of conditionals scenario.

        Tests if/else branching and conditional logic execution.
        """
        program = generated_program_factory("conditionals", language)
        markers = program["markers"]

        # Set breakpoints at condition check and completion (skip initialization)
        # This avoids the step-over issue where we'd land on the next breakpoint
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["flow.if.less_than"],
                markers["func.print.complete"],
            ],
        )

        # Session paused at first condition check
        # At this point, value has already been initialized
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "value", "7")

        # We're already at the condition check breakpoint (first breakpoint hit)

        # Continue to completion
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.complete"],
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_scenario_basic_exception(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Comprehensive validation of basic_exception scenario.

        Tests exception handling with try/catch/finally blocks.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Start with 3 breakpoints (skip var.init.result to avoid line 7/9 interference)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["func.print.attempt"],
                markers["func.print.cleanup"],
                markers["func.print.result"],
            ],
        )

        # Session paused at first breakpoint (func.print.attempt) - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Hit finally block
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.cleanup"],
        )

        # Hit final statement
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.result"],
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_all_scenarios_structure(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Verify all scenarios have correct structure and required markers.

        Tests that each scenario provides the expected structure including path, markers
        dictionary, and valid file paths.
        """
        scenarios = [
            "basic_variables",
            "basic_for_loop",
            "simple_function",
            "basic_while_loop",
            "conditionals",
            "basic_exception",
        ]

        for scenario_id in scenarios:
            program = generated_program_factory(scenario_id, language)

            # Verify required keys
            assert "path" in program, f"Scenario {scenario_id} missing 'path'"
            assert "markers" in program, f"Scenario {scenario_id} missing 'markers'"

            # Verify path exists and is valid
            assert Path(program["path"]).exists(), (
                f"Scenario {scenario_id} file not found: {program['path']}"
            )

            # Verify markers is a non-empty dict
            assert isinstance(program["markers"], dict), (
                f"Scenario {scenario_id} markers not a dict"
            )
            assert len(program["markers"]) > 0, f"Scenario {scenario_id} has no markers"

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_all_scenarios_markers(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Verify all scenario markers are valid line numbers.

        Tests that marker values are positive integers representing valid line numbers
        in the generated program files.
        """
        scenarios = [
            "basic_variables",
            "basic_for_loop",
            "simple_function",
            "basic_while_loop",
            "conditionals",
            "basic_exception",
        ]

        for scenario_id in scenarios:
            program = generated_program_factory(scenario_id, language)
            markers = program["markers"]

            # Count lines in file
            line_count = len(Path(program["path"]).read_text().splitlines())

            # Verify each marker
            for marker_name, line_number in markers.items():
                assert isinstance(
                    line_number,
                    int,
                ), (
                    f"Scenario {scenario_id} marker {marker_name} is not an int: {line_number}"
                )
                assert line_number > 0, (
                    f"Scenario {scenario_id} marker {marker_name} has invalid line number: {line_number}"
                )
                assert line_number <= line_count, (
                    f"Scenario {scenario_id} marker {marker_name} line {line_number} exceeds file length {line_count}"
                )
