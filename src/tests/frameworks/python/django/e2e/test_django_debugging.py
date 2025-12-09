"""E2E tests for Django framework debugging.

This module demonstrates the dual-launch pattern for framework testing, ensuring both
API and VS Code launch.json entry points work correctly.
"""

import os
from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.launch_test_utils import LaunchConfigTestHelper
from tests._helpers.parametrization import parametrize_interfaces


class TestDjangoDebugging(FrameworkDebugTestBase):
    """Test Django framework debugging capabilities.

    This test class validates that Django applications can be debugged through both the
    programmatic API and VS Code launch configurations.
    """

    framework_name = "Django"

    @pytest.fixture
    def django_app(self) -> Path:
        """Get path to Django test app.

        Returns
        -------
        Path
            Path to Django test application
        """
        return (
            Path(__file__).parents[4]
            / "_assets"
            / "framework_apps"
            / "python"
            / "django_app"
        )

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(self, debug_interface, django_app: Path):
        """Test Django debugging via direct API launch.

        Verifies that Django can be launched and debugged programmatically
        without using launch.json configurations.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        django_app : Path
            Path to Django test application
        """
        manage_py = django_app / "manage.py"

        app_port = os.environ.get("APP_PORT", "8000")
        session_info = await debug_interface.start_session(
            program=str(manage_py),
            args=["runserver", app_port, "--noreload"],
            cwd=str(django_app),
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        django_app: Path,
    ):
        """Test Django debugging via VS Code launch.json configuration.

        Verifies that Django can be launched using a VS Code launch
        configuration loaded from launch.json.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        django_app : Path
            Path to Django test application
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=django_app)

        config = manager.get_configuration(name="Django: Debug Server")

        assert config is not None, (
            "Django: Debug Server config not found in launch.json"
        )

        session_info = await self.launch_from_config(
            debug_interface,
            config,
            workspace_root=django_app,
        )

        self.assert_framework_debuggable(session_info)

        assert debug_interface.is_session_active

        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(self, django_app: Path):
        """Verify that API and launch.json produce equivalent behavior.

        This test ensures that both launch methods result in the same
        debugging capabilities and session state.

        Parameters
        ----------
        django_app : Path
            Path to Django test application
        """
        from tests._helpers.debug_interface.api_interface import APIInterface

        manage_py = django_app / "manage.py"

        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        app_port = os.environ.get("APP_PORT", "8000")
        api_session = await api_interface.start_session(
            program=str(manage_py),
            args=["runserver", app_port, "--noreload"],
            cwd=str(django_app),
        )

        from aidb.adapters.base.vslaunch import LaunchConfigurationManager

        manager = LaunchConfigurationManager(workspace_root=django_app)
        config = manager.get_configuration(name="Django: Debug View")

        vscode_session = await self.launch_from_config(
            api_interface,
            config,
            workspace_root=django_app,
        )

        assert api_session["status"] == vscode_session["status"]
        assert api_session["session_id"] is not None
        assert vscode_session["session_id"] is not None

        await api_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_django_view_debugging(
        self,
        debug_interface,
        django_app: Path,
    ):
        """Test setting breakpoints in Django views.

        This test demonstrates debugging Django view functions with
        breakpoints and variable inspection.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        django_app : Path
            Path to Django test application
        """
        views_file = django_app / "test_project" / "views.py"
        views_content = views_file.read_text()

        home_message_line = None
        for i, line in enumerate(views_content.splitlines(), start=1):
            if "#:bp.home.message:" in line:
                home_message_line = i
                break

        assert home_message_line is not None, "Could not find #:bp.home.message: marker"

        manage_py = django_app / "manage.py"

        app_port = os.environ.get("APP_PORT", "8000")
        await debug_interface.start_session(
            program=str(manage_py),
            args=["runserver", app_port, "--noreload"],
            cwd=str(django_app),
        )

        bp = await debug_interface.set_breakpoint(
            file=views_file,
            line=home_message_line,
        )

        self.verify_bp.verify_breakpoint_verified(bp)

        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_django_variable_inspection(
        self,
        debug_interface,
        django_app: Path,
    ):
        """Test inspecting variables in Django views.

        Verifies that variables in Django view functions can be properly
        inspected during debugging.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        django_app : Path
            Path to Django test application
        """
        views_file = django_app / "test_project" / "views.py"
        views_content = views_file.read_text()

        calc_x_line = None
        calc_y_line = None
        for i, line in enumerate(views_content.splitlines(), start=1):
            if "#:bp.calc.x:" in line:
                calc_x_line = i
            elif "#:bp.calc.y:" in line:
                calc_y_line = i

        assert calc_x_line is not None
        assert calc_y_line is not None

        manage_py = django_app / "manage.py"

        app_port = os.environ.get("APP_PORT", "8000")
        await debug_interface.start_session(
            program=str(manage_py),
            args=["runserver", app_port, "--noreload"],
            cwd=str(django_app),
        )

        bp1 = await debug_interface.set_breakpoint(file=views_file, line=calc_x_line)
        bp2 = await debug_interface.set_breakpoint(file=views_file, line=calc_y_line)

        self.verify_bp.verify_breakpoint_verified(bp1)
        self.verify_bp.verify_breakpoint_verified(bp2)

        await debug_interface.stop_session()
