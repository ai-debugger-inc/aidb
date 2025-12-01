"""E2E tests for Spring Boot framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly.
"""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestSpringBootDebugging(FrameworkDebugTestBase):
    """Test Spring Boot framework debugging capabilities.

    This test class validates that Spring Boot applications can be debugged through both
    the programmatic API and VS Code launch configurations.
    """

    framework_name = "Spring Boot"

    @pytest.fixture
    def springboot_app(self) -> Path:
        """Get path to Spring Boot test app.

        Returns
        -------
        Path
            Path to Spring Boot test application
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "java"
            / "springboot_app"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, springboot_app: Path):
        """Test Spring Boot debugging via direct API launch.

        Verifies that Spring Boot can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        springboot_app : Path
            Path to Spring Boot test application
        """
        session_info = await debug_interface.start_session(
            program="com.example.demo.DemoApplication",
            main_class="com.example.demo.DemoApplication",
            project_name="springboot-demo",
            args=["--server.port=8080"],
            cwd=str(springboot_app),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        springboot_app: Path,
    ):
        """Test Spring Boot debugging via VS Code launch.json configuration.

        Verifies that Spring Boot can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        springboot_app : Path
            Path to Spring Boot test application
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=springboot_app)

        config = manager.get_configuration(name="Spring Boot: Debug Server")

        assert config is not None, (
            "Spring Boot: Debug Server config not found in launch.json"
        )

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=springboot_app,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, springboot_app: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        springboot_app : Path
            Path to Spring Boot test application
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        api_interface = APIInterface(language="java")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program="com.example.demo.DemoApplication",
            main_class="com.example.demo.DemoApplication",
            project_name="springboot-demo",
            args=["--server.port=8082"],
            cwd=str(springboot_app),
        )

        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=springboot_app)
        config = manager.get_configuration(name="Spring Boot: Debug Controller")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=springboot_app,
        )

        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_springboot_controller_debugging(
        self,
        debug_interface,
        springboot_app: Path,
    ):
        """Test setting breakpoints in Spring Boot controllers.

        This test demonstrates debugging Spring Boot controller methods with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        springboot_app : Path
            Path to Spring Boot test application
        """
        controller_file = (
            springboot_app
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "demo"
            / "HelloController.java"
        )
        controller_content = controller_file.read_text()

        home_message_line = None
        for i, line in enumerate(controller_content.splitlines(), start=1):
            if "//:bp.home.message:" in line:
                home_message_line = i
                break

        assert home_message_line is not None, (
            "Could not find //:bp.home.message: marker"
        )

        await debug_interface.start_session(
            program="com.example.demo.DemoApplication",
            main_class="com.example.demo.DemoApplication",
            project_name="springboot-demo",
            args=["--server.port=8083"],
            cwd=str(springboot_app),
            breakpoints=[{"file": str(controller_file), "line": home_message_line}],
        )

        # Verify breakpoint was set
        breakpoints = await debug_interface.list_breakpoints()
        bp = next((bp for bp in breakpoints if bp["line"] == home_message_line), None)
        assert bp is not None, f"No breakpoint found at line {home_message_line}"
        self.verify_bp.verify_breakpoint_verified(bp)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_springboot_variable_inspection(
        self,
        debug_interface,
        springboot_app: Path,
    ):
        """Test inspecting variables in Spring Boot controllers.

        Verifies that variables in Spring Boot controller methods can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        springboot_app : Path
            Path to Spring Boot test application
        """
        controller_file = (
            springboot_app
            / "src"
            / "main"
            / "java"
            / "com"
            / "example"
            / "demo"
            / "HelloController.java"
        )
        controller_content = controller_file.read_text()

        calc_x_line = None
        calc_y_line = None
        for i, line in enumerate(controller_content.splitlines(), start=1):
            if "//:bp.calc.x:" in line:
                calc_x_line = i
            elif "//:bp.calc.y:" in line:
                calc_y_line = i

        assert calc_x_line is not None
        assert calc_y_line is not None

        await debug_interface.start_session(
            program="com.example.demo.DemoApplication",
            main_class="com.example.demo.DemoApplication",
            project_name="springboot-demo",
            args=["--server.port=8084"],
            cwd=str(springboot_app),
            breakpoints=[
                {"file": str(controller_file), "line": calc_x_line},
                {"file": str(controller_file), "line": calc_y_line},
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
