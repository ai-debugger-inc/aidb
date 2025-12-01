"""Base class for framework debugging tests enforcing dual-launch pattern.

This module provides a base class that ensures framework tests validate both API and VS
Code launch.json entry points, guaranteeing consistency across both debugging methods.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Any

from tests._helpers.test_bases.base_e2e_test import BaseE2ETest


class FrameworkDebugTestBase(BaseE2ETest):
    """Base class for framework debugging tests with dual-launch enforcement.

    This base class ensures that all framework tests verify both debugging
    entry points:
    1. Direct API launch (programmatic)
    2. VS Code launch.json configuration

    The class enforces this by requiring three abstract methods that all
    framework tests must implement. This guarantees that we never ship
    a framework integration that only works through one entry point.

    Usage
    -----
    Inherit and implement the three required methods::

        class TestDjangoDebugging(FrameworkDebugTestBase):
            '''Test Django framework debugging.'''

            @parametrize_interfaces
            async def test_launch_via_api(self, debug_interface, django_app):
                '''Test Django debugging via direct API.'''
                # Launch Django app programmatically
                session = await debug_interface.start_session(
                    program=django_app / "manage.py",
                    args=["runserver", "--noreload"],
                )
                # Set breakpoints, verify debugging works
                ...

            @parametrize_interfaces
            async def test_launch_via_vscode_config(
                self,
                debug_interface,
                django_app,
                django_launch_config,
            ):
                '''Test Django debugging via launch.json.'''
                # Use core's LaunchConfigurationManager
                from aidb.adapters.base.vslaunch import LaunchConfigurationManager

                manager = LaunchConfigurationManager(django_app)
                config = manager.get_configuration(name="Django: Debug")

                # Launch via config
                session = await self.launch_from_config(
                    debug_interface,
                    config,
                )
                # Verify same debugging capabilities
                ...

            async def test_dual_launch_equivalence(
                self,
                debug_interface,
                django_app,
            ):
                '''Verify API and launch.json produce identical behavior.'''
                # Run same test via both methods
                api_result = await self._run_breakpoint_test_via_api(
                    debug_interface,
                    django_app,
                )
                vscode_result = await self._run_breakpoint_test_via_config(
                    debug_interface,
                    django_app,
                )

                # Assert equivalence
                assert api_result == vscode_result

    Attributes
    ----------
    framework_name : str
        Name of the framework being tested (e.g., "Django", "Express")
    """

    framework_name: str = "Unknown Framework"

    @abstractmethod
    async def test_launch_via_api(self, debug_interface, *args, **kwargs):
        """Test framework debugging via direct API launch.

        This method must demonstrate that the framework can be debugged
        using the programmatic API (calling start_session directly).

        Parameters
        ----------
        debug_interface : DebugInterface
            The debug interface (MCP or API)
        *args
            Additional positional arguments (framework app paths, etc.)
        **kwargs
            Additional keyword arguments (ports, environment, etc.)

        Raises
        ------
        AssertionError
            If framework cannot be debugged via API
        NotImplementedError
            If subclass doesn't implement this method
        """
        msg = f"{self.__class__.__name__} must implement test_launch_via_api()"
        raise NotImplementedError(msg)

    @abstractmethod
    async def test_launch_via_vscode_config(self, debug_interface, *args, **kwargs):
        """Test framework debugging via VS Code launch.json configuration.

        This method must demonstrate that the framework can be debugged
        using a VS Code launch configuration loaded from launch.json.

        Should use core's LaunchConfigurationManager to load configs.

        Parameters
        ----------
        debug_interface : DebugInterface
            The debug interface (MCP or API)
        *args
            Additional positional arguments (workspace path, config name, etc.)
        **kwargs
            Additional keyword arguments (environment, etc.)

        Raises
        ------
        AssertionError
            If framework cannot be debugged via launch.json
        NotImplementedError
            If subclass doesn't implement this method
        """
        msg = (
            f"{self.__class__.__name__} must implement test_launch_via_vscode_config()"
        )
        raise NotImplementedError(msg)

    @abstractmethod
    async def test_dual_launch_equivalence(self, *args, **kwargs):
        """Verify that API and launch.json produce equivalent debugging behavior.

        This method must demonstrate that both entry points work identically.
        Typically this involves running the same debugging operation through
        both paths and comparing results.

        Example operations to verify:
        - Breakpoints hit at same locations
        - Variables have same values
        - Stack traces are equivalent
        - Stepping behavior is identical

        Parameters
        ----------
        *args
            Additional positional arguments
        **kwargs
            Additional keyword arguments

        Raises
        ------
        AssertionError
            If the two launch methods produce different results
        NotImplementedError
            If subclass doesn't implement this method
        """
        msg = f"{self.__class__.__name__} must implement test_dual_launch_equivalence()"
        raise NotImplementedError(msg)

    async def launch_from_config(
        self,
        debug_interface,
        config,
        workspace_root: Path | None = None,
        breakpoints: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Helper to launch debugging session from a launch configuration.

        Uses core's infrastructure to convert launch.json config to
        adapter args and start the session.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface to use
        config : BaseLaunchConfig
            Launch configuration from LaunchConfigurationManager
        workspace_root : Path, optional
            Workspace root for path resolution
        breakpoints : list[dict[str, Any]], optional
            Initial breakpoints to set when starting the session.
            Follows the standard human debugging workflow pattern.

        Returns
        -------
        dict[str, Any]
            Session information

        Examples
        --------
        >>> from aidb.adapters.base.vslaunch import LaunchConfigurationManager
        >>> manager = LaunchConfigurationManager(workspace_root)
        >>> config = manager.get_configuration(name="Django: Debug")
        >>> session = await self.launch_from_config(debug_interface, config)
        """
        if workspace_root is None:
            workspace_root = Path.cwd()

        adapter_args = config.to_adapter_args(workspace_root)

        # Check both "target" (modern) and "program" (legacy) for compatibility
        program = adapter_args.get("target") or adapter_args.get("program")

        # For Java, main_class serves as the program identifier
        if not program and "main_class" in adapter_args:
            program = adapter_args["main_class"]

        if not program:
            msg = (
                f"Launch config '{config.name}' has no program/target/main_class "
                "defined"
            )
            raise ValueError(msg)

        launch_args = {
            "program": program,
            "args": adapter_args.get("args", []),
            "cwd": adapter_args.get("cwd"),
            "env": adapter_args.get("env", {}),
        }

        if "port" in adapter_args:
            launch_args["port"] = adapter_args["port"]

        # Pass through module flag for Python module launch (python -m module_name)
        if "module" in adapter_args:
            launch_args["module"] = adapter_args["module"]

        # Pass through Java-specific fields
        if "main_class" in adapter_args:
            launch_args["main_class"] = adapter_args["main_class"]
        if "project_name" in adapter_args:
            launch_args["project_name"] = adapter_args["project_name"]

        # Add breakpoints if provided - standard debugging workflow
        if breakpoints:
            launch_args["breakpoints"] = breakpoints

        return await debug_interface.start_session(**launch_args)

    def assert_framework_debuggable(
        self,
        session_info: dict[str, Any],
        expected_status: str = "started",
    ):
        """Helper assertion that framework debugging session started correctly.

        Parameters
        ----------
        session_info : dict[str, Any]
            Session information from start_session
        expected_status : str
            Expected status value, default "started"

        Raises
        ------
        AssertionError
            If session didn't start correctly
        """
        assert session_info is not None, (
            f"{self.framework_name} session failed to start"
        )
        assert session_info.get("status") == expected_status, (
            f"{self.framework_name} session status is "
            f"'{session_info.get('status')}', expected '{expected_status}'"
        )
        assert session_info.get("session_id") is not None, (
            f"{self.framework_name} session has no session_id"
        )
