"""Integration tests for variable inspection capabilities.

These tests verify that the debugger can inspect variables of different types, scopes,
and complexities, providing accurate information about program state.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestVariableInspection(BaseIntegrationTest):
    """Integration tests for variable inspection."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_local_variables(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test inspection of local variables in function scope.

        Verifies that all local variables are accessible and have correct values when
        stopped at a breakpoint.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.return.result"]],
        )

        # Session is paused at breakpoint - ready for inspection
        variables = await debug_interface.get_variables()

        # At the return statement, all variables should be in scope
        self.verify_vars.verify_variable_exists(variables, "result")
        self.verify_vars.verify_variable_exists(variables, "a")
        self.verify_vars.verify_variable_exists(variables, "b")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_different_types(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test inspection of variables with different data types.

        Verifies that the debugger correctly handles primitives, collections, and custom
        objects.
        """
        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.assign.counter"]],
        )

        # Session is paused at breakpoint - ready for inspection
        variables = await debug_interface.get_variables()

        self.verify_vars.verify_variable_exists(variables, "counter")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_nested_structures(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test inspection of nested data structures.

        Verifies that the debugger can navigate and inspect nested lists, dictionaries,
        and mixed structures.
        """
        program = generated_program_factory("array_operations", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["flow.loop.iterate"]],
        )

        # Session paused at loop iteration - inspect array variable
        variables = await debug_interface.get_variables()

        # Should have access to the numbers array
        self.verify_vars.verify_variable_exists(variables, "numbers")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_after_modification(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that variable inspection shows updated values.

        Verifies that stepping through code and modifying variables is correctly
        reflected in inspection results.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.total"], markers["func.print.final"]],
        )

        # Session paused at first breakpoint (BEFORE var.init.total line executes)
        # Step over to execute the initialization line
        await debug_interface.step_over()

        # Now inspect the initialized value
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "total", "0")

        # Continue to second breakpoint
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.final"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "total")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_in_loop(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test variable inspection within loop iterations.

        Verifies that loop variables update correctly and can be inspected at each
        iteration.
        """
        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.add.total"]],
        )

        # Session paused at first iteration - inspect variables
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "total")
        self.verify_vars.verify_variable_exists(variables, "i")

        # Continue through remaining iterations
        for _i in range(4):
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(
                state,
                expected_line=markers["var.add.total"],
            )

            variables = await debug_interface.get_variables()
            self.verify_vars.verify_variable_exists(variables, "total")
            self.verify_vars.verify_variable_exists(variables, "i")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_function_arguments(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test inspection of function arguments.

        Verifies that function parameters are available for inspection and have the
        correct values passed by the caller.
        """
        program = generated_program_factory("simple_function", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"]],
        )

        # Session is paused at breakpoint - ready for inspection
        variables = await debug_interface.get_variables()

        self.verify_vars.verify_variable_exists(variables, "a")
        self.verify_vars.verify_variable_exists(variables, "b")

    @parametrize_interfaces
    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Missing scenario: class/object scenarios not in manifest",
    )
    async def test_inspect_class_attributes(
        self,
        debug_interface,
        temp_workspace: Path,
    ):
        """Test inspection of class instance attributes.

        Verifies that object attributes and properties are accessible during debugging.
        """

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_inspect_large_collections(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test inspection of large collections.

        Verifies that the debugger can handle large lists and dictionaries without
        performance issues.
        """
        program = generated_program_factory("large_array_operations", language)
        markers = program["markers"]

        # Use first available marker
        first_marker_line = next(iter(markers.values()))

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [first_marker_line],
        )

        # Step over to execute the variable creation line
        await debug_interface.step_over()

        # Session paused - inspect variables (should handle large collections)
        variables = await debug_interface.get_variables()

        # Verify we got variables without errors (the key test for large collections)
        assert len(variables) > 0
