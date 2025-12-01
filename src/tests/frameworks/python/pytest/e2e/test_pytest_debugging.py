"""E2E tests for pytest framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly with test frameworks.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestPytestDebugging(FrameworkDebugTestBase):
    """Test pytest framework debugging capabilities.

    This test class validates that pytest test suites can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "pytest"

    @pytest.fixture
    def pytest_suite(self) -> Path:
        """Get path to pytest test suite.

        Returns
        -------
        Path
            Path to pytest test suite
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "python"
            / "pytest_suite"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, pytest_suite: Path):
        """Test pytest debugging via direct API launch.

        Verifies that pytest can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        pytest_suite : Path
            Path to pytest test suite
        """
        test_file = pytest_suite / "test_sample.py"

        session_info = await debug_interface.start_session(
            program="pytest",
            module=True,
            args=[str(test_file), "-v"],
            cwd=str(pytest_suite),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        pytest_suite: Path,
    ):
        """Test pytest debugging via VS Code launch.json configuration.

        Verifies that pytest can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        pytest_suite : Path
            Path to pytest test suite
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=pytest_suite)

        config = manager.get_configuration(name="pytest: Debug Tests")

        assert config is not None, "pytest: Debug Tests config not found in launch.json"

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=pytest_suite,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, pytest_suite: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        pytest_suite : Path
            Path to pytest test suite
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        test_file = pytest_suite / "test_sample.py"

        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program="pytest",
            module=True,
            args=[str(test_file), "-v"],
            cwd=str(pytest_suite),
        )

        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=pytest_suite)
        config = manager.get_configuration(name="pytest: Debug Single Test")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=pytest_suite,
        )

        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_pytest_test_debugging(
        self,
        debug_interface,
        pytest_suite: Path,
    ):
        """Test setting breakpoints in pytest tests.

        This test demonstrates debugging pytest test functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        pytest_suite : Path
            Path to pytest test suite
        """
        test_file = pytest_suite / "test_sample.py"
        test_content = test_file.read_text()

        test_x_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "#:bp.test.x:" in line:
                test_x_line = i
                break

        assert test_x_line is not None, "Could not find #:bp.test.x: marker"

        await debug_interface.start_session(
            program="pytest",
            module=True,
            args=[str(test_file), "-v"],
            cwd=str(pytest_suite),
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
    async def test_pytest_fixture_inspection(
        self,
        debug_interface,
        pytest_suite: Path,
    ):
        """Test inspecting variables in pytest fixtures.

        Verifies that variables in pytest fixtures can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        pytest_suite : Path
            Path to pytest test suite
        """
        test_file = pytest_suite / "test_sample.py"
        test_content = test_file.read_text()

        fixture_value_line = None
        fixture_result_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "#:bp.fixture.value:" in line:
                fixture_value_line = i
            elif "#:bp.fixture.result:" in line:
                fixture_result_line = i

        assert fixture_value_line is not None
        assert fixture_result_line is not None

        await debug_interface.start_session(
            program="pytest",
            module=True,
            args=[str(test_file), "-v"],
            cwd=str(pytest_suite),
            breakpoints=[
                {"file": str(test_file), "line": fixture_value_line},
                {"file": str(test_file), "line": fixture_result_line},
            ],
        )

        # Verify breakpoints were set
        breakpoints = await debug_interface.list_breakpoints()
        bp1 = next(
            (bp for bp in breakpoints if bp["line"] == fixture_value_line),
            None,
        )
        bp2 = next(
            (bp for bp in breakpoints if bp["line"] == fixture_result_line),
            None,
        )
        assert bp1 is not None, f"No breakpoint found at line {fixture_value_line}"
        assert bp2 is not None, f"No breakpoint found at line {fixture_result_line}"

        self.verify_bp.verify_breakpoint_verified(bp1)
        self.verify_bp.verify_breakpoint_verified(bp2)

        await debug_interface.stop_session()
