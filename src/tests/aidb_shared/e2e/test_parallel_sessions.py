"""E2E tests for parallel session management and isolation.

These tests verify that multiple debug sessions can run concurrently with proper
isolation, and that session cleanup works correctly.
"""

import pytest

from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest


@pytest.mark.serial
@pytest.mark.xdist_group(name="serial")
class TestParallelSessions(BaseE2ETest):
    """E2E tests for parallel session management.

    Marked serial because these tests create multiple concurrent debug sessions
    internally. Running them under pytest-xdist parallel workers causes resource
    contention (ports, adapters) that can lead to hangs.
    """

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_concurrent_sessions_isolation(
        self,
        debug_interface,
        language,
        generated_program_factory,
        debug_interface_factory,
    ):
        """Test that concurrent sessions maintain proper isolation.

        Verifies that two debug sessions running simultaneously don't interfere
        with each other when proper session IDs are tracked and used.

        This test validates the MCP contract: when multiple sessions exist,
        the most recent becomes the default, and older sessions require
        explicit session_id passing (as AI agents do in production).
        """
        # Create first session
        program1 = generated_program_factory("basic_variables", language)
        session1 = debug_interface

        # Create second session with different interface instance
        session2 = await debug_interface_factory(debug_interface.__class__.__name__)
        program2 = generated_program_factory("simple_function", language)

        # Start both sessions with breakpoints
        bp1_line = program1["markers"]["var.init.counter"]
        bp2_line = program2["markers"]["func.call.add"]

        session1_info = await self.start_session_with_breakpoints(
            session1,
            program1["path"],
            [bp1_line],
        )
        session2_info = await self.start_session_with_breakpoints(
            session2,
            program2["path"],
            [bp2_line],
        )

        # Store session IDs for explicit reference
        # After session2 is created, session1.session_id may point to session2
        # (per MCP design), so we store the original IDs from the responses
        session1_id = session1_info["session_id"]
        session2_id = session2_info["session_id"]

        # Verify session isolation - different session IDs were created
        assert session1_id != session2_id, (
            f"Sessions should have unique IDs: "
            f"session1={session1_id}, session2={session2_id}"
        )

        # Wait for both sessions to hit their breakpoints
        # Note: After session2 creation, the global default session is session2
        # Session1 operations may need explicit session_id passing depending on interface
        state1 = await self.wait_for_stopped_state(session1, expected_line=bp1_line)
        state2 = await self.wait_for_stopped_state(session2, expected_line=bp2_line)

        # Verify each session hit its own breakpoint
        # If this fails, it means session IDs are not being properly isolated
        self.verify_exec.verify_stopped(state1, expected_line=bp1_line)
        self.verify_exec.verify_stopped(state2, expected_line=bp2_line)

        # Cleanup
        await session1.stop_session()
        await session2.stop_session()

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_session_cleanup(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test that session cleanup properly releases resources.

        Verifies that stopping a session cleans up resources and that the same interface
        can be reused for a new session.
        """
        program = generated_program_factory("basic_variables", language)
        bp_line = program["markers"]["var.init.counter"]

        # Start first session with breakpoint
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [bp_line],
        )
        first_session_id = debug_interface.session_id

        # Stop the session
        await debug_interface.stop_session()

        # Verify session is cleaned up
        assert (
            debug_interface.session_id is None
            or debug_interface.session_id != first_session_id
        )

        # Start a new session with the same interface (with breakpoint)
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [bp_line],
        )
        second_session_id = debug_interface.session_id

        # Verify new session has different ID
        assert second_session_id != first_session_id

        # Verify new session works - should be paused at breakpoint
        assert debug_interface.is_session_active
        # Verify we're stopped at the breakpoint by getting variables
        await debug_interface.get_variables()
        # This will implicitly verify we're stopped (get_variables only works when paused)

        # Final cleanup
        await debug_interface.stop_session()
