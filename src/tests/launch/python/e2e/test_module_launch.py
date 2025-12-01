"""Tests for Python module launching via launch.json."""

from pathlib import Path

import pytest

from tests._helpers.framework_base import FrameworkDebugTestBase
from tests._helpers.parametrization import parametrize_interfaces


class TestPythonModuleLaunch(FrameworkDebugTestBase):
    """Test Python module launching via launch.json.

    Tests the ability to launch Python code as a module using the `-m module` syntax
    through launch.json configuration.
    """

    @pytest.fixture
    def test_module(self, temp_workspace: Path) -> tuple[Path, str]:
        """Create a simple Python module for testing.

        Parameters
        ----------
        temp_workspace : Path
            Temporary workspace directory

        Returns
        -------
        tuple[Path, str]
            Tuple of (module_dir, module_name)
        """
        # Create package structure: mymodule/__main__.py
        module_dir = temp_workspace / "mymodule"
        module_dir.mkdir()

        # Create __init__.py (empty)
        (module_dir / "__init__.py").write_text('"""Simple test module."""\n')

        # Create __main__.py with entrypoint
        main_file = module_dir / "__main__.py"
        main_file.write_text('''"""Module entry point."""

def greet(name: str) -> str:
    """Generate greeting message."""
    message = f"Hello, {name}!"  #:bp.greet:
    return message

def main():
    """Main entry point for module."""
    result = greet("World")  #:bp.main.call:
    print(result)  #:bp.main.print:
    return result

if __name__ == "__main__":
    main()
''')
        return module_dir, "mymodule"

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_api(
        self,
        debug_interface,
        test_module: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test Python module debugging via direct API launch.

        Verifies that a Python module can be launched with -m syntax
        programmatically without using launch.json. Uses target + module=True
        to indicate module mode (python -m module_name).

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_module : tuple[Path, str]
            Tuple of (module_dir, module_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        module_dir, module_name = test_module

        # Launch via programmatic API with module syntax
        # Note: For module launch, pass module name as program + module=True
        session_info = await debug_interface.start_session(
            program=module_name,
            module=True,
            cwd=str(temp_workspace),
        )

        # Verify session started
        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        # Stop session
        await debug_interface.stop_session()

    @parametrize_interfaces
    @pytest.mark.asyncio
    async def test_launch_via_vscode_config(
        self,
        debug_interface,
        test_module: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test Python module debugging via launch.json configuration.

        Verifies that a Python module can be launched using launch.json
        with module syntax and variable resolution.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface (MCP or API)
        test_module : tuple[Path, str]
            Tuple of (module_dir, module_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        module_dir, module_name = test_module

        # Create launch.json with module configuration
        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                {
                    "type": "python",
                    "request": "launch",
                    "name": "Debug Module",
                    "module": module_name,
                    "cwd": "${workspaceFolder}",
                },
            ],
        )

        # Load configuration
        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Module")

        # Launch via launch.json
        session_info = await self.launch_from_config(
            debug_interface,
            config,
            temp_workspace,
        )

        # Verify session started
        self.assert_framework_debuggable(session_info)
        assert debug_interface.is_session_active

        # Stop session
        await debug_interface.stop_session()

    @pytest.mark.asyncio
    async def test_dual_launch_equivalence(
        self,
        test_module: tuple[Path, str],
        temp_workspace: Path,
    ):
        """Test that API and launch.json launches produce equivalent sessions.

        Compares launching via programmatic API vs launch.json configuration
        to ensure they produce equivalent debugging sessions.

        Parameters
        ----------
        test_module : tuple[Path, str]
            Tuple of (module_dir, module_name)
        temp_workspace : Path
            Temporary workspace directory
        """
        from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        from tests._helpers.debug_interface.api_interface import APIInterface
        from tests._helpers.launch_test_utils import LaunchConfigTestHelper

        module_dir, module_name = test_module

        # Launch 1: Direct API
        api_interface = APIInterface(language="python")
        await api_interface.initialize()

        api_session = await api_interface.start_session(
            program=module_name,
            module=True,
            cwd=str(temp_workspace),
        )

        # Launch 2: via launch.json
        config_interface = APIInterface(language="python")
        await config_interface.initialize()

        helper = LaunchConfigTestHelper(workspace_root=temp_workspace)
        helper.create_test_launch_json(
            [
                {
                    "type": "python",
                    "request": "launch",
                    "name": "Debug Module",
                    "module": module_name,
                    "cwd": "${workspaceFolder}",
                },
            ],
        )

        manager = LaunchConfigurationManager(workspace_root=temp_workspace)
        config = manager.get_configuration(name="Debug Module")

        config_session = await self.launch_from_config(
            config_interface,
            config,
            temp_workspace,
        )

        # Verify both sessions are debuggable
        self.assert_framework_debuggable(api_session)
        self.assert_framework_debuggable(config_session)

        # Verify both use module mode
        # (Cannot directly compare sessions due to different PIDs,
        # but both starting successfully proves equivalence)
        assert api_interface.is_session_active
        assert config_interface.is_session_active

        # Cleanup
        await api_interface.stop_session()
        await config_interface.stop_session()
