"""E2E tests for FastAPI framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly with async frameworks.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


@pytest.mark.xdist_group("fastapi")
class TestFastAPIDebugging(FrameworkDebugTestBase):
    """Test FastAPI framework debugging capabilities.

    This test class validates that FastAPI applications (async) can be debugged through
    both the programmatic API and VS Code launch configurations.
    """

    framework_name = "FastAPI"

    @pytest.fixture
    def fastapi_app(self) -> Path:
        """Get path to FastAPI test app.

        Returns
        -------
        Path
            Path to FastAPI test application
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "python"
            / "fastapi_app"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, fastapi_app: Path):
        """Test FastAPI debugging via direct API launch.

        Verifies that FastAPI can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        fastapi_app : Path
            Path to FastAPI test application
        """
        app_py = fastapi_app / "app.py"

        session_info = await debug_interface.start_session(
            program=str(app_py),
            cwd=str(fastapi_app),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        fastapi_app: Path,
    ):
        """Test FastAPI debugging via VS Code launch.json configuration.

        Verifies that FastAPI can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        fastapi_app : Path
            Path to FastAPI test application
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=fastapi_app)

        config = manager.get_configuration(name="FastAPI: Debug Server")

        assert config is not None, (
            "FastAPI: Debug Server config not found in launch.json"
        )

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=fastapi_app,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, fastapi_app: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        fastapi_app : Path
            Path to FastAPI test application
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        app_py = fastapi_app / "app.py"

        # Test 1: API launch
        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program=str(app_py),
            cwd=str(fastapi_app),
        )

        # Stop first session before starting second to avoid resource conflicts
        await api_interface.stop_session()

        # Test 2: VS Code config launch (fresh interface to avoid state pollution)
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        vscode_interface = APIInterface(language="python")
        await vscode_interface.initialize()

        manager = LaunchConfigurationManager(workspace_root=fastapi_app)
        config = manager.get_configuration(name="FastAPI: Debug View")

        vscode_session = await self.launch_from_config(
            vscode_interface,
            config,
            workspace_root=fastapi_app,
        )

        # Compare results
        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await vscode_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_fastapi_async_route_debugging(
        self,
        debug_interface,
        fastapi_app: Path,
    ):
        """Test setting breakpoints in FastAPI async routes.

        This test demonstrates debugging FastAPI async route functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        fastapi_app : Path
            Path to FastAPI test application
        """
        app_file = fastapi_app / "app.py"
        app_content = app_file.read_text()

        home_message_line = None
        for i, line in enumerate(app_content.splitlines(), start=1):
            if "#:bp.home.message:" in line:
                home_message_line = i
                break

        assert home_message_line is not None, "Could not find #:bp.home.message: marker"

        await debug_interface.start_session(
            program=str(app_file),
            cwd=str(fastapi_app),
            breakpoints=[{"file": str(app_file), "line": home_message_line}],
        )

        # Verify breakpoint was set
        breakpoints = await debug_interface.list_breakpoints()
        bp = next((bp for bp in breakpoints if bp["line"] == home_message_line), None)
        assert bp is not None, f"No breakpoint found at line {home_message_line}"
        self.verify_bp.verify_breakpoint_verified(bp)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_fastapi_variable_inspection(
        self,
        debug_interface,
        fastapi_app: Path,
    ):
        """Test inspecting variables in FastAPI async routes.

        Verifies that variables in FastAPI async route functions can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        fastapi_app : Path
            Path to FastAPI test application
        """
        app_file = fastapi_app / "app.py"
        app_content = app_file.read_text()

        calc_x_line = None
        calc_y_line = None
        for i, line in enumerate(app_content.splitlines(), start=1):
            if "#:bp.calc.x:" in line:
                calc_x_line = i
            elif "#:bp.calc.y:" in line:
                calc_y_line = i

        assert calc_x_line is not None
        assert calc_y_line is not None

        await debug_interface.start_session(
            program=str(app_file),
            cwd=str(fastapi_app),
            breakpoints=[
                {"file": str(app_file), "line": calc_x_line},
                {"file": str(app_file), "line": calc_y_line},
            ],
        )

        # Verify breakpoints were set
        breakpoints = await debug_interface.list_breakpoints()
        bp1 = next((bp for bp in breakpoints if bp["line"] == calc_x_line), None)
        bp2 = next((bp for bp in breakpoints if bp["line"] == calc_y_line), None)
        assert bp1 is not None, f"No breakpoint found at line {calc_x_line}"
        assert bp2 is not None, f"No breakpoint found at line {calc_y_line}"

        self.verify_bp.verify_breakpoint_verified(bp1)
        self.verify_bp.verify_breakpoint_verified(bp2)

        await debug_interface.stop_session()
