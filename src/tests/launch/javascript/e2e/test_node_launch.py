"""E2E tests for Node.js script launch via launch.json.

Tests that Node.js scripts can be launched via both the programmatic API and VS Code
launch.json configurations, with equivalent results.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestNodeBasicLaunch(FrameworkDebugTestBase):
    """Test basic Node.js script launching.

    Validates that Node.js scripts can be debugged through both the programmatic API and
    VS Code launch configurations.
    """

    framework_name = "Node.js Script"

    @pytest.fixture
    def test_script(self, temp_workspace: Path) -> Path:
        """Create a simple Node.js test script.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory

        Returns
        -------
        Path
            Path to created test script
        """
        script = temp_workspace / "test_app.js"
        script.write_text("""// Simple test application

function calculateSum(a, b) {
    const result = a + b;  //:bp.sum:
    return result;
}

function main() {
    const x = 10;  //:bp.main.x:
    const y = 20;  //:bp.main.y:
    const total = calculateSum(x, y);  //:bp.main.call:
    console.log(`Sum: ${total}`);  //:bp.main.print:
    return total;
}

main();
""")
        return script

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, test_script: Path):
        """Test Node.js script debugging via direct API launch.

        Verifies that a Node.js script can be launched and debugged
        programmatically without using launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Node.js test script
        """
        session_info = await debug_interface.start_session(
            program=str(test_script),
            cwd=str(test_script.parent),
        )

        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        test_script: Path,
        temp_workspace: Path,
    ):
        """Test Node.js script debugging via VS Code launch.json.

        Verifies that a Node.js script can be launched using a VS Code
        launch configuration.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Node.js test script
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                helper.create_javascript_launch_config(
                    name="Debug Script",
                    program="${workspaceFolder}/test_app.js",
                    cwd="${workspaceFolder}",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Script")

        assert config is not None, "Debug Script config not found in launch.json"

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=temp_workspace,
        )

        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_breakpoint_in_script(
        self,
        debug_interface,
        test_script: Path,
        temp_workspace: Path,
    ):
        """Test setting breakpoints in Node.js script via launch.json.

        Uses the standard debugging workflow: set breakpoints when starting
        the session, then continue to hit them.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_script : Path
            Path to Node.js test script
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        script_content = test_script.read_text()
        bp_line = None
        for i, line in enumerate(script_content.splitlines(), start=1):
            if "//:bp.main.x:" in line:
                bp_line = i
                break

        assert bp_line is not None, "Breakpoint marker not found"

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                helper.create_javascript_launch_config(
                    name="Debug Script",
                    program="${workspaceFolder}/test_app.js",
                    cwd="${workspaceFolder}",
                ),
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Script")

        await self.launch_from_config(
            debug_interface,
            config,
            temp_workspace,
            breakpoints=[{"file": str(test_script), "line": bp_line}],
        )

        assert debug_interface.is_session_active

        state = await debug_interface.get_state()

        self.verify_exec.verify_stopped(state, expected_line=bp_line)

        await debug_interface.stop_session()
