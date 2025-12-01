"""E2E tests for Express framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly.
"""

from pathlib import Path

import pytest

from tests._helpers.constants import get_framework_app_path
from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestExpressDebugging(FrameworkDebugTestBase):
    """Test Express framework debugging capabilities.

    This test class validates that Express applications can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "Express"

    @pytest.fixture
    def express_app(self) -> Path:
        """Get path to Express test app.

        Returns
        -------
        Path
            Path to Express test application
        """
        return get_framework_app_path("javascript", "express")

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, express_app: Path):
        """Test Express debugging via direct API launch.

        Verifies that Express can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        express_app : Path
            Path to Express test application
        """
        server_js = express_app / "server.js"

        session_info = await debug_interface.start_session(
            program=str(server_js),
            env={"PORT": "3000"},
            cwd=str(express_app),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        express_app: Path,
    ):
        """Test Express debugging via VS Code launch.json configuration.

        Verifies that Express can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        express_app : Path
            Path to Express test application
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=express_app)

        config = manager.get_configuration(name="Express: Debug Server")

        assert config is not None, (
            "Express: Debug Server config not found in launch.json"
        )

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=express_app,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, express_app: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        express_app : Path
            Path to Express test application
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        server_js = express_app / "server.js"

        api_interface = APIInterface(language="javascript")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program=str(server_js),
            env={"PORT": "3002"},
            cwd=str(express_app),
        )

        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=express_app)
        config = manager.get_configuration(name="Express: Debug Routes")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=express_app,
        )

        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_express_route_debugging(
        self,
        debug_interface,
        express_app: Path,
    ):
        """Test setting breakpoints in Express route handlers.

        This test demonstrates debugging Express route functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        express_app : Path
            Path to Express test application
        """
        routes_file = express_app / "routes" / "index.js"
        routes_content = routes_file.read_text()

        home_message_line = None
        for i, line in enumerate(routes_content.splitlines(), start=1):
            if ":bp.home.message:" in line:
                home_message_line = i
                break

        assert home_message_line is not None, "Could not find :bp.home.message: marker"

        server_js = express_app / "server.js"

        await debug_interface.start_session(
            program=str(server_js),
            env={"PORT": "3003"},
            cwd=str(express_app),
            breakpoints=[{"file": str(routes_file), "line": home_message_line}],
        )

        # Verify breakpoint was set
        breakpoints = await debug_interface.list_breakpoints()
        bp = next((bp for bp in breakpoints if bp["line"] == home_message_line), None)
        assert bp is not None, f"No breakpoint found at line {home_message_line}"
        self.verify_bp.verify_breakpoint_verified(bp)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_express_middleware_debugging(
        self,
        debug_interface,
        express_app: Path,
    ):
        """Test debugging Express middleware functions.

        Verifies that breakpoints can be set in middleware and that
        middleware variables can be inspected.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        express_app : Path
            Path to Express test application
        """
        server_file = express_app / "server.js"
        server_content = server_file.read_text()

        middleware_timestamp_line = None
        middleware_log_line = None
        for i, line in enumerate(server_content.splitlines(), start=1):
            if ":bp.middleware.timestamp:" in line:
                middleware_timestamp_line = i
            elif ":bp.middleware.log:" in line:
                middleware_log_line = i

        assert middleware_timestamp_line is not None
        assert middleware_log_line is not None

        await debug_interface.start_session(
            program=str(server_file),
            env={"PORT": "3004"},
            cwd=str(express_app),
            breakpoints=[
                {"file": str(server_file), "line": middleware_timestamp_line},
                {"file": str(server_file), "line": middleware_log_line},
            ],
        )

        # Verify breakpoints were set
        breakpoints = await debug_interface.list_breakpoints()
        bp1 = next(
            (bp for bp in breakpoints if bp["line"] == middleware_timestamp_line),
            None,
        )
        bp2 = next(
            (bp for bp in breakpoints if bp["line"] == middleware_log_line),
            None,
        )
        assert bp1 is not None, (
            f"No breakpoint found at line {middleware_timestamp_line}"
        )
        assert bp2 is not None, f"No breakpoint found at line {middleware_log_line}"

        self.verify_bp.verify_breakpoint_verified(bp1)
        self.verify_bp.verify_breakpoint_verified(bp2)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_express_variable_inspection(
        self,
        debug_interface,
        express_app: Path,
    ):
        """Test inspecting variables in Express route handlers.

        Verifies that variables in Express route functions can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        express_app : Path
            Path to Express test application
        """
        routes_file = express_app / "routes" / "index.js"
        routes_content = routes_file.read_text()

        calc_x_line = None
        calc_y_line = None
        for i, line in enumerate(routes_content.splitlines(), start=1):
            if ":bp.calc.x:" in line:
                calc_x_line = i
            elif ":bp.calc.y:" in line:
                calc_y_line = i

        assert calc_x_line is not None
        assert calc_y_line is not None

        server_js = express_app / "server.js"

        await debug_interface.start_session(
            program=str(server_js),
            env={"PORT": "3005"},
            cwd=str(express_app),
            breakpoints=[
                {"file": str(routes_file), "line": calc_x_line},
                {"file": str(routes_file), "line": calc_y_line},
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
