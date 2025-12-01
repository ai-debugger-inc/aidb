"""E2E tests for Python script launch via launch.json.

Tests that Python scripts can be launched via both the programmatic API and VS Code
launch.json configurations, with equivalent results.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestPythonBasicLaunch(FrameworkDebugTestBase):
    """Test basic Python script launching.

    Validates that Python scripts can be debugged through both the programmatic API and
    VS Code launch configurations.
    """

    framework_name = "Python Script"

    @pytest.fixture
    def test_script(self, temp_workspace: Path) -> Path:
        """Create a simple Python test script.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory

        Returns
        -------
        Path
            Path to created test script
        """
        script = temp_workspace / "test_app.py"
        script.write_text('''"""Simple test application."""

def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    result = a + b  #:bp.sum:
    return result

def main():
    """Main entry point."""
    x = 10  #:bp.main.x:
    y = 20  #:bp.main.y:
    total = calculate_sum(x, y)  #:bp.main.call:
    print(f"Sum: {total}")  #:bp.main.print:
    return total

if __name__ == "__main__":
    main()
''')
        return script

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, test_script: Path):
        """Test Python script debugging via direct API launch.

        Verifies that a Python script can be launched and debugged
        programmatically without using launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Python test script
        """
        # Launch via programmatic API
        session_info = await debug_interface.start_session(
            program=str(test_script),
            cwd=str(test_script.parent),
        )

        # Verify session started
        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        # Stop session
        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        test_script: Path,
        temp_workspace: Path,
    ):
        """Test Python script debugging via VS Code launch.json.

        Verifies that a Python script can be launched using a VS Code
        launch configuration.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Python test script
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        # Create launch.json
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Debug Script",
                    program="${workspaceFolder}/test_app.py",
                    cwd="${workspaceFolder}",
                ),
            ],
        )

        # Load configuration
        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Script")

        assert config is not None, "Debug Script config not found in launch.json"

        # Launch via config
        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=temp_workspace,
        )

        # Verify session started
        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        # Stop session
        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(
        self,
        test_script: Path,
        temp_workspace: Path,
    ):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        test_script : Path
            Path to Python test script
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.debug_interface.api_interface import APIInterface
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        # Method 1: API launch
        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program=str(test_script),
            cwd=str(test_script.parent),
        )

        # Method 2: Launch.json launch
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Debug Script",
                    program="${workspaceFolder}/test_app.py",
                    cwd="${workspaceFolder}",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Script")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=temp_workspace,
        )

        # Verify equivalence
        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        # Both sessions should be active
        assert api_interface.is_session_active

        # Cleanup
        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_breakpoint_in_script(
        self,
        debug_interface,
        test_script: Path,
        temp_workspace: Path,
    ):
        """Test setting breakpoints in Python script via launch.json.

        Uses the standard debugging workflow: set breakpoints when starting
        the session, then continue to hit them.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Python test script
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        # Find breakpoint line
        script_content = test_script.read_text()
        bp_line = None
        for i, line in enumerate(script_content.splitlines(), start=1):
            if "#:bp.main.x:" in line:
                bp_line = i
                break

        assert bp_line is not None, "Breakpoint marker not found"

        # Create launch.json
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                helper.create_python_launch_config(
                    name="Debug Script",
                    program="${workspaceFolder}/test_app.py",
                    cwd="${workspaceFolder}",
                ),
            ],
        )

        # Load configuration
        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Script")

        # Launch with breakpoints - standard human debugging workflow
        _session_info = await self.launch_from_config(
            debug_interface,
            config,
            temp_workspace,
            breakpoints=[{"file": str(test_script), "line": bp_line}],
        )

        # Verify session started and stopped at breakpoint
        assert debug_interface.is_session_active

        # Get execution state (session auto-waits and stops at first breakpoint)
        state = await debug_interface.get_state()

        # Verify stopped at breakpoint (no continue needed - already there!)
        self.verify_exec.verify_stopped(state, expected_line=bp_line)

        # Cleanup
        await debug_interface.stop_session()
