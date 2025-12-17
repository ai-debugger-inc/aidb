"""E2E tests for Jest framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly with test frameworks.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestJestDebugging(FrameworkDebugTestBase):
    """Test Jest framework debugging capabilities.

    This test class validates that Jest test suites can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "Jest"

    @pytest.fixture
    def jest_suite(self) -> Path:
        """Get path to Jest test suite.

        Returns
        -------
        Path
            Path to Jest test suite
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "javascript"
            / "jest_suite"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, jest_suite: Path):
        """Test Jest debugging via direct API launch.

        Verifies that Jest can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        jest_suite : Path
            Path to Jest test suite
        """
        jest_bin = jest_suite / "node_modules" / ".bin" / "jest"

        session_info = await debug_interface.start_session(
            program=str(jest_bin),
            args=["--runInBand", "--no-coverage"],
            cwd=str(jest_suite),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        jest_suite: Path,
    ):
        """Test Jest debugging via VS Code launch.json configuration.

        Verifies that Jest can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        jest_suite : Path
            Path to Jest test suite
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=jest_suite)

        config = manager.get_configuration(name="Jest: Debug Tests")

        assert config is not None, "Jest: Debug Tests config not found in launch.json"

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=jest_suite,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_jest_test_debugging(
        self,
        debug_interface,
        jest_suite: Path,
    ):
        """Test setting breakpoints in Jest tests.

        This test demonstrates debugging Jest test functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        jest_suite : Path
            Path to Jest test suite
        """
        test_file = jest_suite / "sample.test.js"
        test_content = test_file.read_text()

        test_x_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "//:bp.test.x:" in line:
                test_x_line = i
                break

        assert test_x_line is not None, "Could not find //:bp.test.x: marker"

        jest_bin = jest_suite / "node_modules" / ".bin" / "jest"

        session_info = await debug_interface.start_session(
            program=str(jest_bin),
            args=["--runInBand", "--no-coverage"],
            cwd=str(jest_suite),
            breakpoints=[{"file": str(test_file), "line": test_x_line}],
        )

        self.assert_framework_debuggable(session_info)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_jest_async_test_debugging(
        self,
        debug_interface,
        jest_suite: Path,
    ):
        """Test inspecting variables in Jest async tests.

        Verifies that variables in Jest async tests can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        jest_suite : Path
            Path to Jest test suite
        """
        test_file = jest_suite / "sample.test.js"
        test_content = test_file.read_text()

        async_value_line = None
        async_result_line = None
        for i, line in enumerate(test_content.splitlines(), start=1):
            if "//:bp.async.value:" in line:
                async_value_line = i
            elif "//:bp.async.result:" in line:
                async_result_line = i

        assert async_value_line is not None
        assert async_result_line is not None

        jest_bin = jest_suite / "node_modules" / ".bin" / "jest"

        session_info = await debug_interface.start_session(
            program=str(jest_bin),
            args=["--runInBand", "--no-coverage"],
            cwd=str(jest_suite),
            breakpoints=[
                {"file": str(test_file), "line": async_value_line},
                {"file": str(test_file), "line": async_result_line},
            ],
        )

        self.assert_framework_debuggable(session_info)

        await debug_interface.stop_session()
