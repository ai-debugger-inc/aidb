"""E2E tests for Java application launch via launch.json.

Tests that Java applications can be launched via both the programmatic API and VS Code
launch.json configurations, with equivalent results.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestJavaBasicLaunch(FrameworkDebugTestBase):
    """Test basic Java application launching.

    Validates that Java applications can be debugged through both the programmatic API
    and VS Code launch configurations.
    """

    framework_name = "Java Application"

    @pytest.fixture
    def test_application(self, temp_workspace: Path) -> tuple[Path, str]:
        """Create a simple Java test application.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory

        Returns
        -------
        tuple[Path, str]
            Tuple of (source_file_path, main_class_name)
        """
        source_file = temp_workspace / "TestApp.java"
        source_file.write_text("""// Simple test application

public class TestApp {
    public static int calculateSum(int a, int b) {
        int result = a + b;  //:bp.sum:
        return result;
    }

    public static void main(String[] args) {
        int x = 10;  //:bp.main.x:
        int y = 20;  //:bp.main.y:
        int total = calculateSum(x, y);  //:bp.main.call:
        System.out.println("Sum: " + total);  //:bp.main.print:
    }
}
""")
        return source_file, "TestApp"

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(
        self,
        debug_interface,
        test_application: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test Java application debugging via direct API launch.

        Verifies that a Java application can be launched and debugged
        programmatically without using launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_application : tuple[Path, str]
            Tuple of (source_file_path, main_class_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        source_file, main_class = test_application

        session_info = await debug_interface.start_session(
            program=str(source_file),
            cwd=str(temp_workspace),
        )

        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        test_application: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test Java application debugging via VS Code launch.json.

        Verifies that a Java application can be launched using a VS Code
        launch configuration.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_application : tuple[Path, str]
            Tuple of (source_file_path, main_class_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        source_file, main_class = test_application

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                {
                    "type": "java",
                    "request": "launch",
                    "name": "Debug Application",
                    "program": "${workspaceFolder}/TestApp.java",
                    "cwd": "${workspaceFolder}",
                },
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Application")

        assert config is not None, "Debug Application config not found in launch.json"

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
    async def test_breakpoint_in_application(
        self,
        debug_interface,
        test_application: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test setting breakpoints in Java application via launch.json.

        Uses the standard debugging workflow: set breakpoints when starting
        the session, then continue to hit them.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_application : tuple[Path, str]
            Tuple of (source_file_path, main_class_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        source_file, main_class = test_application

        source_content = source_file.read_text()
        bp_line = None
        for i, line in enumerate(source_content.splitlines(), start=1):
            if "//:bp.main.x:" in line:
                bp_line = i
                break

        assert bp_line is not None, "Breakpoint marker not found"

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                {
                    "type": "java",
                    "request": "launch",
                    "name": "Debug Application",
                    "program": "${workspaceFolder}/TestApp.java",
                    "cwd": "${workspaceFolder}",
                },
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Application")

        await self.launch_from_config(
            debug_interface,
            config,
            temp_workspace,
            breakpoints=[{"file": str(source_file), "line": bp_line}],
        )

        assert debug_interface.is_session_active

        state = await debug_interface.get_state()

        self.verify_exec.verify_stopped(state, expected_line=bp_line)

        await debug_interface.stop_session()
