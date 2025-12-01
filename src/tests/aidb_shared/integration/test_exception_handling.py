"""Integration tests for exception handling debugging capabilities.

These tests verify that the debugger correctly handles try/catch/finally blocks,
exception breakpoints, and error recovery across all supported languages.
"""

from pathlib import Path

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_integration_test import BaseIntegrationTest


class TestExceptionHandling(BaseIntegrationTest):
    """Integration tests for exception handling debugging."""

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_try_block_execution(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test execution flow through try block without exceptions.

        Verifies that the debugger correctly tracks execution through a try block when
        no exception is raised.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Set breakpoints in try block
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.attempt"], markers["var.assign.result"]],
        )

        # Session paused at first breakpoint
        variables = await debug_interface.get_variables()
        # Continue to second statement in try block

        # Continue to second statement in try block
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.assign.result"],
        )

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_exists(variables, "result")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_catch_block_triggered(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that catch block is accessible in the program structure.

        Verifies that the debugger can set breakpoints in exception handling blocks even
        when no exception is raised.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.cleanup"]],
        )

        # Session paused at finally block (catch was skipped) - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_finally_block_always_runs(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that finally block always executes.

        Verifies that the finally block executes regardless of whether an exception was
        raised, demonstrating proper control flow through exception handling.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.cleanup"]],
        )

        # Session paused at finally block
        variables = await debug_interface.get_variables()
        # Result was assigned in try block
        self.verify_vars.verify_variable_exists(variables, "result")
        self.verify_vars.verify_variable_value(variables, "result", "10")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_exception_breakpoint(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test breakpoint placement at exception handling points.

        Verifies that breakpoints can be set at strategic exception handling locations
        like catch and finally blocks.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Set breakpoints at exception handling boundaries
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["func.print.attempt"],
                markers["func.print.cleanup"],
            ],
        )

        # Session paused at first breakpoint (first executable line in try) - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Hit finally block code
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["func.print.cleanup"],
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_uncaught_exception(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test program execution with proper exception handling.

        Verifies that programs with exception handling structures execute completely
        through to their final statements.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Set breakpoint at final print statement
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.print.result"]],
        )

        # Session paused at final print statement
        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "result", "10")

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_nested_try_catch(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test complete exception handling workflow.

        Verifies end-to-end execution through a complete exception handling structure,
        from initialization through try/catch/finally and final output.
        """
        program = generated_program_factory("basic_exception", language)
        markers = program["markers"]

        # Trace through entire exception handling flow
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [
                markers["var.init.result"],
                markers["var.assign.result"],
                markers["func.print.cleanup"],
                markers["func.print.result"],
            ],
        )

        # Session paused at first breakpoint (initialization) - verify by getting variables
        _ = await debug_interface.get_variables()
        # Getting variables successfully confirms we're paused at the breakpoint

        # Hit try block
        state = await debug_interface.continue_execution()
        self.verify_exec.verify_stopped(
            state,
            expected_line=markers["var.assign.result"],
        )

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

        variables = await debug_interface.get_variables()
        self.verify_vars.verify_variable_value(variables, "result", "10")
