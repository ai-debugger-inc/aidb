"""Session management for all test types.

This module consolidates repeated session initialization patterns from MCP tests,
providing a single interface for creating and managing debug sessions.
"""

from contextlib import suppress
from pathlib import Path
from typing import Any, Optional, Union, cast

from aidb.models.entities.breakpoint import BreakpointSpec
from aidb_mcp.core.constants import ParamName
from tests._assets.test_content import get_test_content


class SessionManager:
    """Session management for all test types.

    This class consolidates the common patterns of:
    1. Initializing debugging context
    2. Creating test files with appropriate content
    3. Setting up breakpoints
    4. Starting debug sessions
    5. Managing session lifecycle
    """

    def __init__(self, call_tool_func):
        """Initialize the session manager.

        Parameters
        ----------
        call_tool_func : callable
            The call_tool function from the test class (e.g., self.call_tool)
        """
        self.call_tool = call_tool_func
        self._active_sessions: dict[str, dict[str, Any]] = {}

    async def _initialize_debug_context(
        self,
        language: str,
        temp_dir: Path | None,
        init_args: dict[str, Any] | None,
    ) -> None:
        """Initialize debugging context if requested.

        Parameters
        ----------
        language : str
            Programming language
        temp_dir : Optional[Path]
            Directory for test files
        init_args : Optional[Dict[str, Any]]
            Additional arguments for init tool

        Raises
        ------
        RuntimeError
            If initialization fails
        """
        init_params = {"language": language}
        if init_args:
            init_params.update(init_args)
        if temp_dir and "workspace_root" not in init_params:
            init_params["workspace_root"] = str(temp_dir)

        init_response = await self.call_tool("init", init_params)
        if not init_response.get("success"):
            msg = f"Failed to initialize: {init_response}"
            raise RuntimeError(msg)

    def _create_test_file(
        self,
        language: str,
        scenario: str,
        temp_dir: Path,
        file_name: str | None,
    ) -> Path:
        """Create test file for debugging.

        Parameters
        ----------
        language : str
            Programming language
        scenario : str
            Test scenario name
        temp_dir : Path
            Directory for test files
        file_name : Optional[str]
            Custom name for the test file

        Returns
        -------
        Path
            Path to created test file
        """
        file_extension = {
            "python": ".py",
            "javascript": ".js",
            "java": ".java",
        }.get(language, ".txt")

        if not file_name:
            file_name = f"test_{scenario}{file_extension}"
        elif not file_name.endswith(file_extension):
            file_name += file_extension

        test_file = temp_dir / file_name
        test_content = get_test_content(language, scenario)
        test_file.write_text(test_content)
        return test_file

    def _process_single_breakpoint(
        self,
        bp: int | str | BreakpointSpec,
        test_file: Path | None,
    ) -> dict[str, Any]:
        """Process a single breakpoint specification.

        Parameters
        ----------
        bp : Union[int, str, BreakpointSpec]
            Breakpoint specification
        test_file : Optional[Path]
            Test file path

        Returns
        -------
        dict[str, Any]
            Processed breakpoint
        """
        if isinstance(bp, int):
            # Line number only - use test file if available
            if test_file:
                return {"file": str(test_file), "line": bp}
            return {"line": bp}
        if isinstance(bp, str):
            # String format (file:line or line)
            if ":" in bp:
                file_part, line_part = bp.rsplit(":", 1)
                return {"file": file_part, "line": int(line_part)}
            if test_file:
                return {"file": str(test_file), "line": int(bp)}
            return {"line": int(bp)}
        # BreakpointSpec (TypedDict) or other dict-like object
        return cast("dict[str, Any]", bp)

    def _process_breakpoints(
        self,
        breakpoints: list[int | str | BreakpointSpec] | None,
        test_file: Path | None,
        auto_breakpoint: bool,
    ) -> list[dict[str, Any]]:
        """Process breakpoint specifications.

        Parameters
        ----------
        breakpoints : Optional[List[Union[int, str, BreakpointSpec]]]
            Breakpoint specifications
        test_file : Optional[Path]
            Test file path
        auto_breakpoint : bool
            Whether to add auto-breakpoint at line 1

        Returns
        -------
        list[dict[str, Any]]
            Processed breakpoints
        """
        if breakpoints is not None:
            return [
                self._process_single_breakpoint(bp, test_file) for bp in breakpoints
            ]
        if auto_breakpoint and test_file:
            # Add auto-breakpoint at line 1 if no breakpoints specified
            return [{"file": str(test_file), "line": 1}]
        return []

    async def _start_debug_session(
        self,
        start_args: dict[str, Any],
    ) -> str:
        """Start the debug session.

        Parameters
        ----------
        start_args : dict[str, Any]
            Arguments for session_start

        Returns
        -------
        str
            Session ID

        Raises
        ------
        RuntimeError
            If session start fails
        """
        session_response = await self.call_tool("session_start", start_args)
        if not session_response.get("success"):
            msg = f"Failed to start session: {session_response}"
            raise RuntimeError(msg)

        session_id = session_response.get(ParamName.SESSION_ID)
        if not session_id:
            # Try to extract from data if not at top level
            session_id = session_response.get("data", {}).get(ParamName.SESSION_ID)

        if not session_id:
            msg = f"No session_id in response: {session_response}"
            raise RuntimeError(msg)

        return session_id

    async def create_debug_session(
        self,
        language: str,
        scenario: str = "hello_world",
        temp_dir: Path | None = None,
        breakpoints: list[int | str | BreakpointSpec] | None = None,
        init_args: dict[str, Any] | None = None,
        session_args: dict[str, Any] | None = None,
        auto_init: bool = True,
        auto_breakpoint: bool = True,
        file_name: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Create a complete debug session with one method call.

        This method combines:
        - init_debugging_context
        - test file creation
        - breakpoint setup
        - session_start

        Parameters
        ----------
        language : str
            Programming language (python, javascript, java)
        scenario : str
            Test scenario name from test_content.py
        temp_dir : Optional[Path]
            Directory for test files (required if no existing file)
        breakpoints : Optional[List[Union[int, str, BreakpointSpec]]]
            Breakpoint specifications (line numbers, file:line, or BreakpointSpec
            objects)
        init_args : Optional[Dict[str, Any]]
            Additional arguments for init tool
        session_args : Optional[Dict[str, Any]]
            Additional arguments for session_start tool
        auto_init : bool
            Whether to automatically call init tool (default: True)
        auto_breakpoint : bool
            Whether to include auto-breakpoint at line 1 (default: True)
        file_name : Optional[str]
            Custom name for the test file

        Returns
        -------
        Tuple[str, Dict[str, Any]]
            Session ID and complete session data including:
            - session_id: The session identifier
            - test_file: Path to the created test file
            - response: Full session_start response
            - breakpoints: List of set breakpoints
        """
        # Initialize debugging context if requested
        if auto_init:
            await self._initialize_debug_context(language, temp_dir, init_args)

        # Create test file if temp_dir provided
        test_file = None
        if temp_dir:
            test_file = self._create_test_file(language, scenario, temp_dir, file_name)

        # Prepare session start arguments
        start_args: dict[str, Any] = {"language": language}

        if test_file:
            start_args["target"] = str(test_file)

        # Process breakpoints
        processed_breakpoints = self._process_breakpoints(
            breakpoints,
            test_file,
            auto_breakpoint,
        )
        if processed_breakpoints:
            start_args[ParamName.BREAKPOINTS] = processed_breakpoints

        # Add any additional session arguments
        if session_args:
            start_args.update(session_args)

        # Start the session
        session_id = await self._start_debug_session(start_args)

        # Store session data
        session_data = {
            ParamName.SESSION_ID: session_id,
            "test_file": test_file,
            "response": {"success": True, ParamName.SESSION_ID: session_id},
            "breakpoints": start_args.get(ParamName.BREAKPOINTS, []),
            "language": language,
            "scenario": scenario,
        }

        self._active_sessions[session_id] = session_data

        return session_id, session_data

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        """Stop a debug session.

        Parameters
        ----------
        session_id : str
            The session to stop

        Returns
        -------
        Dict[str, Any]
            Stop response from the session tool
        """
        response = await self.call_tool(
            "session",
            {"action": "stop", ParamName.SESSION_ID: session_id},
        )

        # Remove from active sessions
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]

        return response

    async def cleanup_all_sessions(self) -> None:
        """Clean up all active sessions managed by this instance."""
        for session_id in list(self._active_sessions.keys()):
            with suppress(Exception):
                # Best effort cleanup
                await self.stop_session(session_id)

        self._active_sessions.clear()

    def get_session_data(self, session_id: str) -> dict[str, Any] | None:
        """Get stored data for a session.

        Parameters
        ----------
        session_id : str
            The session ID

        Returns
        -------
        Optional[Dict[str, Any]]
            Session data if found, None otherwise
        """
        return self._active_sessions.get(session_id)

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._active_sessions)

    @property
    def active_session_ids(self) -> list[str]:
        """Get list of active session IDs."""
        return list(self._active_sessions.keys())


class ScenarioBuilder:
    """Builder for creating complex debug scenarios.

    This class provides a fluent interface for building test scenarios with multiple
    files, breakpoints, and configurations.
    """

    def __init__(self, session_manager: SessionManager):
        """Initialize the scenario builder.

        Parameters
        ----------
        session_manager : SessionManager
            The session manager to use for creating sessions
        """
        self.session_manager = session_manager
        self.language = "python"
        self.files: list[dict[str, Any]] = []
        self.breakpoints: list[int | str | BreakpointSpec] = []
        self.init_args: dict[str, Any] = {}
        self.session_args: dict[str, Any] = {}
        self.temp_dir: Path | None = None

    def with_language(self, language: str) -> "ScenarioBuilder":
        """Set the programming language."""
        self.language = language
        return self

    def with_file(
        self,
        scenario: str,
        name: str | None = None,
        breakpoints: list[int] | None = None,
    ) -> "ScenarioBuilder":
        """Add a test file to the scenario."""
        file_spec = {"scenario": scenario, "name": name}
        if breakpoints:
            for line in breakpoints:
                if name:
                    self.breakpoints.append(f"{name}:{line}")
                else:
                    self.breakpoints.append(line)
        self.files.append(file_spec)
        return self

    def with_breakpoint(
        self,
        breakpoint: int | str | BreakpointSpec,
    ) -> "ScenarioBuilder":
        """Add a breakpoint to the scenario."""
        self.breakpoints.append(breakpoint)
        return self

    def with_init_args(self, **kwargs) -> "ScenarioBuilder":
        """Set initialization arguments."""
        self.init_args.update(kwargs)
        return self

    def with_session_args(self, **kwargs) -> "ScenarioBuilder":
        """Set session start arguments."""
        self.session_args.update(kwargs)
        return self

    def in_directory(self, temp_dir: Path) -> "ScenarioBuilder":
        """Set the temporary directory for files."""
        self.temp_dir = temp_dir
        return self

    async def build(self) -> tuple[str, dict[str, Any]]:
        """Build and start the debug scenario.

        Returns
        -------
        Tuple[str, Dict[str, Any]]
            Session ID and session data
        """
        if not self.files:
            # No files specified, use default
            return await self.session_manager.create_debug_session(
                language=self.language,
                temp_dir=self.temp_dir,
                breakpoints=self.breakpoints,
                init_args=self.init_args,
                session_args=self.session_args,
            )

        # Create all specified files
        created_files = []
        for file_spec in self.files:
            if not self.temp_dir:
                msg = "temp_dir required when specifying files"
                raise ValueError(msg)

            file_extension = {
                "python": ".py",
                "javascript": ".js",
                "java": ".java",
            }.get(self.language, ".txt")

            file_name = file_spec.get("name")
            if not file_name:
                file_name = f"test_{file_spec['scenario']}{file_extension}"
            elif not file_name.endswith(file_extension):
                file_name += file_extension

            file_path = self.temp_dir / file_name
            content = get_test_content(self.language, file_spec["scenario"])
            file_path.write_text(content)
            created_files.append(file_path)

        # Use the first file as the target
        target_file = created_files[0] if created_files else None

        # Create the session
        return await self.session_manager.create_debug_session(
            language=self.language,
            scenario=self.files[0]["scenario"] if self.files else "hello_world",
            temp_dir=self.temp_dir,
            breakpoints=self.breakpoints,
            init_args=self.init_args,
            session_args={
                **self.session_args,
                "target": str(target_file) if target_file else None,
            },
            auto_init=True,
            file_name=target_file.name if target_file else None,
        )
