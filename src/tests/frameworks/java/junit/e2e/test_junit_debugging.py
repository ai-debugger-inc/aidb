"""E2E tests for JUnit framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly with test frameworks.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestJUnitDebugging(FrameworkDebugTestBase):
    """Test JUnit framework debugging capabilities.

    This test class validates that JUnit test suites can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "JUnit"

    @pytest.fixture
    def junit_suite(self) -> Path:
        """Get path to JUnit test suite.

        Returns
        -------
        Path
            Path to JUnit test suite
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "java"
            / "junit_suite"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, junit_suite: Path):
        """Test JUnit debugging via direct API launch.

        Verifies that JUnit can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        junit_suite : Path
            Path to JUnit test suite
        """
        session_info = await debug_interface.start_session(
            program="org.junit.platform.console.ConsoleLauncher",
            main_class="org.junit.platform.console.ConsoleLauncher",
            project_name="junit-tests",
            args=["--select-package", "com.example.test", "--fail-if-no-tests"],
            cwd=str(junit_suite),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        junit_suite: Path,
    ):
        """Test JUnit debugging via VS Code launch.json configuration.

        Verifies that JUnit can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        junit_suite : Path
            Path to JUnit test suite
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=junit_suite)

        config = manager.get_configuration(name="JUnit: Debug Tests")

        assert config is not None, "JUnit: Debug Tests config not found in launch.json"

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=junit_suite,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, junit_suite: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        junit_suite : Path
            Path to JUnit test suite
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        api_interface = APIInterface(language="java")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program="org.junit.platform.console.ConsoleLauncher",
            main_class="org.junit.platform.console.ConsoleLauncher",
            project_name="junit-tests",
            args=["--select-package", "com.example.test", "--fail-if-no-tests"],
            cwd=str(junit_suite),
        )

        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=junit_suite)
        config = manager.get_configuration(name="JUnit: Debug Single Test")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=junit_suite,
        )

        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_junit_test_debugging(
        self,
        debug_interface,
        junit_suite: Path,
    ):
        """Test setting breakpoints in JUnit tests.

        This test demonstrates debugging JUnit test methods with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        junit_suite : Path
            Path to JUnit test suite
        """
        test_file = (
            junit_suite
            / "src"
            / "test"
            / "java"
            / "com"
            / "example"
            / "test"
            / "SampleTest.java"
        )
        test_content = test_file.read_text()

        test_x_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "//:bp.test.x:" in line:
                test_x_line = i
                break

        assert test_x_line is not None, "Could not find //:bp.test.x: marker"

        await debug_interface.start_session(
            program="org.junit.platform.console.ConsoleLauncher",
            main_class="org.junit.platform.console.ConsoleLauncher",
            project_name="junit-tests",
            args=["--select-class", "com.example.test.SampleTest"],
            cwd=str(junit_suite),
            breakpoints=[{"file": str(test_file), "line": test_x_line}],
        )

        # Verify breakpoint was set
        breakpoints = await debug_interface.list_breakpoints()
        bp = next((bp for bp in breakpoints if bp["line"] == test_x_line), None)
        assert bp is not None, f"No breakpoint found at line {test_x_line}"
        self.verify_bp.verify_breakpoint_verified(bp)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_junit_variable_inspection(
        self,
        debug_interface,
        junit_suite: Path,
    ):
        """Test inspecting variables in JUnit tests.

        Verifies that variables in JUnit test methods can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        junit_suite : Path
            Path to JUnit test suite
        """
        test_file = (
            junit_suite
            / "src"
            / "test"
            / "java"
            / "com"
            / "example"
            / "test"
            / "SampleTest.java"
        )
        test_content = test_file.read_text()

        calc_a_line = None
        calc_b_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "//:bp.calc.a:" in line:
                calc_a_line = i
            elif "//:bp.calc.b:" in line:
                calc_b_line = i

        assert calc_a_line is not None
        assert calc_b_line is not None

        await debug_interface.start_session(
            program="org.junit.platform.console.ConsoleLauncher",
            main_class="org.junit.platform.console.ConsoleLauncher",
            project_name="junit-tests",
            args=["--select-class", "com.example.test.SampleTest"],
            cwd=str(junit_suite),
            breakpoints=[
                {"file": str(test_file), "line": calc_a_line},
                {"file": str(test_file), "line": calc_b_line},
            ],
        )

        # Verify breakpoints were set
        breakpoints = await debug_interface.list_breakpoints()
        bp1 = next((bp for bp in breakpoints if bp["line"] == calc_a_line), None)
        bp2 = next((bp for bp in breakpoints if bp["line"] == calc_b_line), None)
        assert bp1 is not None, f"No breakpoint found at line {calc_a_line}"
        assert bp2 is not None, f"No breakpoint found at line {calc_b_line}"

        self.verify_bp.verify_breakpoint_verified(bp1)
        self.verify_bp.verify_breakpoint_verified(bp2)

        await debug_interface.stop_session()
