"""E2E tests for Flask framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestFlaskDebugging(FrameworkDebugTestBase):
    """Test Flask framework debugging capabilities.

    This test class validates that Flask applications can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "Flask"

    @pytest.fixture
    def flask_app(self) -> Path:
        """Get path to Flask test app.

        Returns
        -------
        Path
            Path to Flask test application
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "python"
            / "flask_app"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, flask_app: Path):
        """Test Flask debugging via direct API launch.

        Verifies that Flask can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        flask_app : Path
            Path to Flask test application
        """
        app_py = flask_app / "app.py"

        session_info = await debug_interface.start_session(
            program=str(app_py),
            cwd=str(flask_app),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        flask_app: Path,
    ):
        """Test Flask debugging via VS Code launch.json configuration.

        Verifies that Flask can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        flask_app : Path
            Path to Flask test application
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=flask_app)

        config = manager.get_configuration(name="Flask: Debug Server")

        assert config is not None, "Flask: Debug Server config not found in launch.json"

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=flask_app,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, flask_app: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        flask_app : Path
            Path to Flask test application
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        app_py = flask_app / "app.py"

        # Test 1: API launch
        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program=str(app_py),
            cwd=str(flask_app),
        )

        # Stop first session before starting second to avoid resource conflicts
        await api_interface.stop_session()

        # Test 2: VS Code config launch (fresh interface to avoid state pollution)
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        vscode_interface = APIInterface(language="python")
        await vscode_interface.initialize()

        manager = LaunchConfigurationManager(workspace_root=flask_app)
        config = manager.get_configuration(name="Flask: Debug View")

        vscode_session = await self.launch_from_config(
            vscode_interface,
            config,
            workspace_root=flask_app,
        )

        # Compare results
        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await vscode_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_flask_route_debugging(
        self,
        debug_interface,
        flask_app: Path,
    ):
        """Test setting breakpoints in Flask routes.

        This test demonstrates debugging Flask route functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        flask_app : Path
            Path to Flask test application
        """
        app_file = flask_app / "app.py"
        app_content = app_file.read_text()

        home_message_line = None
        for i, line in enumerate(app_content.splitlines(), start=1):
            if "#:bp.home.message:" in line:
                home_message_line = i
                break

        assert home_message_line is not None, "Could not find #:bp.home.message: marker"

        await debug_interface.start_session(
            program=str(app_file),
            cwd=str(flask_app),
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
    async def test_flask_variable_inspection(
        self,
        debug_interface,
        flask_app: Path,
    ):
        """Test inspecting variables in Flask routes.

        Verifies that variables in Flask route functions can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        flask_app : Path
            Path to Flask test application
        """
        app_file = flask_app / "app.py"
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
            cwd=str(flask_app),
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
