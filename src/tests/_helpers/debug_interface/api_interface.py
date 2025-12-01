"""API-based debug interface implementation.

This module provides a DebugInterface implementation that wraps the aidb API directly,
allowing tests to verify the API entry point works correctly.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.api.api import DebugAPI
from aidb.common import ensure_ctx
from tests._helpers.debug_interface.base import DebugInterface

if TYPE_CHECKING:
    from aidb.models.entities.breakpoint import BreakpointSpec
    from aidb.session import Session


class APIInterface(DebugInterface):
    """Debug interface implementation using direct aidb API calls.

    This implementation wraps the aidb DebugAPI and Session classes directly,
    providing a unified interface for testing the API entry point.

    Attributes
    ----------
    api : DebugAPI
        The underlying DebugAPI instance.
    session : Session, optional
        The current debugging session.
    _session_pool : Any, optional
        Optional session pool for Java session reuse (test optimization).
    """

    def __init__(self, language: str | None = None, session_pool: Any = None):
        """Initialize the API interface.

        Parameters
        ----------
        language : str, optional
            Programming language (python, javascript, java).
        session_pool : Any, optional
            Optional session pool for reusing sessions (Java test optimization).
        """
        super().__init__(language)
        self.api: DebugAPI | None = None
        self.session: Session | None = None
        self._breakpoints: dict[str, dict[str, Any]] = {}
        self._session_pool = session_pool
        self._session_from_pool = False

    async def initialize(
        self,
        language: str | None = None,
        **config,
    ) -> None:
        """Initialize the API interface.

        Parameters
        ----------
        language : str, optional
            Programming language (python, javascript, java).
        **config : dict
            Additional configuration (unused for API interface).
        """
        if language:
            self.language = language

        if not self.language:
            msg = "Language must be specified for API interface"
            raise ValueError(msg)

        # Create API instance with context
        ctx = ensure_ctx()
        self.api = DebugAPI(ctx=ctx)

        self._initialized = True

    async def start_session(  # noqa: C901
        self,
        program: str | Path,
        breakpoints: list[dict[str, Any]] | None = None,
        **launch_args,
    ) -> dict[str, Any]:
        """Start a debug session via the API.

        Parameters
        ----------
        program : Union[str, Path]
            Path to the program to debug.
        breakpoints : list[dict[str, Any]], optional
            Initial breakpoints to set.
        **launch_args : dict
            Additional launch arguments (cwd, env, args, etc.)

        Returns
        -------
        dict[str, Any]
            Session information.
        """
        self._validate_initialized()

        # Convert breakpoints to BreakpointSpec format
        bp_specs = None
        if breakpoints:
            bp_specs = []
            for bp in breakpoints:
                bp_spec: BreakpointSpec = {
                    "file": bp.get("file", str(program)),
                    "line": bp["line"],
                }
                # Add optional fields
                if bp.get("condition"):
                    bp_spec["condition"] = bp["condition"]
                if bp.get("hit_condition"):
                    bp_spec["hit_condition"] = bp["hit_condition"]
                if bp.get("log_message"):
                    bp_spec["log_message"] = bp["log_message"]
                bp_specs.append(bp_spec)

        # Try to get session from pool if available (Java optimization)
        assert self.api is not None
        if self._session_pool and self.language == "java":
            import logging

            logger = logging.getLogger(__name__)
            logger.info("🏊 Using Java session pool for %s", str(program))

            async def create_session_fn():
                """Factory function for pool to create new sessions."""
                assert self.api is not None, "API must be initialized before use"
                session = await self.api.create_session(
                    target=str(program),
                    language=self.language,
                    breakpoints=bp_specs,
                    **launch_args,
                )
                start_response = await session.start()
                if not start_response.success:
                    error_msg = start_response.message or "Session start failed"
                    raise RuntimeError(error_msg)
                return session

            # Checkout session from pool
            self.session = await self._session_pool.checkout(create_session_fn)
            self._session_from_pool = True

            # Register the pooled session with the API's session manager
            # This ensures get_active_session() returns the correct session
            if hasattr(self.api, "_session_manager"):
                self.api._session_manager._current_session = self.session

            # If session was from pool, we need to set breakpoints after checkout
            if breakpoints:
                # Clear any existing breakpoints first
                await self.session.debug.clear_breakpoints(clear_all=True)

                # Set new breakpoints
                from aidb.dap.protocol.types import Source, SourceBreakpoint

                # Group breakpoints by file
                bp_by_file: dict[str, list] = {}
                for bp in breakpoints:
                    file_path = bp.get("file", str(program))
                    if file_path not in bp_by_file:
                        bp_by_file[file_path] = []
                    bp_by_file[file_path].append(bp)

                # Set breakpoints for each file
                for file_path, file_bps in bp_by_file.items():
                    source = Source(path=str(file_path))
                    source_bps = [
                        SourceBreakpoint(
                            line=bp["line"],
                            condition=bp.get("condition"),
                            hitCondition=bp.get("hit_condition"),
                            logMessage=bp.get("log_message"),
                        )
                        for bp in file_bps
                    ]
                    result = await self.session.debug.set_breakpoints(
                        source,
                        source_bps,
                    )

                    # Populate tracking dict with breakpoint metadata
                    for bp_id, bp in result.breakpoints.items():
                        bp_dict: dict[str, Any] = {
                            "id": bp_id,
                            "file": str(file_path),
                            "line": bp.line,
                            "location": f"{file_path}:{bp.line}",
                            "verified": bp.verified or False,
                        }
                        # Add optional fields
                        if hasattr(bp, "condition") and bp.condition:
                            bp_dict["condition"] = bp.condition
                        if hasattr(bp, "hit_condition") and bp.hit_condition:
                            bp_dict["hit_condition"] = bp.hit_condition
                        if hasattr(bp, "log_message") and bp.log_message:
                            bp_dict["log_message"] = bp.log_message

                        self._breakpoints[str(bp_id)] = bp_dict

        else:
            # Normal session creation (non-Java or no pool)
            self.session = await self.api.create_session(
                target=str(program),
                language=self.language,
                breakpoints=bp_specs,
                **launch_args,
            )

            # Start the session
            start_response = await self.session.start()

            # Check if session start was successful
            if not start_response.success:
                error_msg = start_response.message or "Session start failed"
                raise RuntimeError(error_msg)

        self.session_id = self.session.id
        self._session_active = True

        # Populate _breakpoints dictionary with initial breakpoints
        # This ensures remove_breakpoint works correctly
        # Wait for breakpoint verification to avoid race condition in CI
        if breakpoints:
            import asyncio
            import time

            verification_timeout = 3.0
            poll_interval = 0.1
            start_time = time.monotonic()
            breakpoint_count = len(breakpoints)

            # Wait for all breakpoints to be verified
            while time.monotonic() - start_time < verification_timeout:
                breakpoints_list = await self.list_breakpoints()
                verified_count = sum(
                    1 for bp in breakpoints_list if bp.get("verified", False)
                )

                if verified_count == breakpoint_count:
                    break

                await asyncio.sleep(poll_interval)

            # Populate tracking dict with final state
            breakpoints_list = await self.list_breakpoints()
            for bp in breakpoints_list:
                bp_id = str(bp.get("id", ""))
                if bp_id:
                    self._breakpoints[bp_id] = bp

        return {
            "session_id": self.session_id,
            "status": "started",
            "language": self.language,
            "program": str(program),
        }

    async def stop_session(self) -> None:
        """Stop the current debug session.

        Raises
        ------
        RuntimeError
            If no active session.
        """
        self._validate_session_active()

        if self.session:
            # Check if session is already terminated before attempting to stop
            # This prevents errors/timeouts when trying to stop naturally completed sessions
            from aidb.session.state import SessionStatus

            # Check both status property and DAP client termination state
            is_terminated = False
            if hasattr(self.session, "status"):
                is_terminated = self.session.status == SessionStatus.TERMINATED
            if (
                not is_terminated
                and hasattr(self.session, "dap")
                and hasattr(self.session.dap, "is_terminated")
            ):
                is_terminated = self.session.dap.is_terminated

            if is_terminated:
                # Session already terminated, just clean up our tracking
                self.session = None
                self._session_active = False
                self.session_id = None
                return

            # Session is not terminated, proceed with stop
            # Note: The stop() method has defensive timeout handling for race conditions
            await self.session.stop()

            # Clear session manager reference
            if self.api and hasattr(self.api, "_session_manager"):
                self.api._session_manager._current_session = None

            self.session = None
            self._session_active = False
            self.session_id = None

    async def set_breakpoint(
        self,
        file: str | Path,
        line: int,
        condition: str | None = None,
        hit_condition: str | None = None,
        log_message: str | None = None,
    ) -> dict[str, Any]:
        """Set a breakpoint via the API.

        Parameters
        ----------
        file : Union[str, Path]
            File path for the breakpoint.
        line : int
            Line number.
        condition : str, optional
            Conditional expression.
        hit_condition : str, optional
            Hit count condition.
        log_message : str, optional
            Log message (logpoint).

        Returns
        -------
        dict[str, Any]
            Breakpoint information.
        """
        self._validate_session_active()

        # Import DAP types
        from aidb.dap.protocol.types import Source, SourceBreakpoint

        # Create DAP Source and SourceBreakpoint objects
        source = Source(path=str(file))
        source_bp = SourceBreakpoint(
            line=line,
            condition=condition,
            hitCondition=hit_condition,
            logMessage=log_message,
        )

        assert self.session is not None
        result = await self.session.debug.set_breakpoints(source, [source_bp])

        # Extract first breakpoint from response
        # Note: result.breakpoints is dict[int, AidbBreakpoint], not list
        if result.breakpoints:
            bp = next(iter(result.breakpoints.values()))
            bp_id = str(bp.id) if bp.id is not None else f"{file}:{line}"
            self._breakpoints[bp_id] = {
                "id": bp_id,
                "file": str(file),
                "line": bp.line or line,
                "verified": bp.verified or False,
                "condition": condition,
                "hit_condition": hit_condition,
                "log_message": log_message,
            }
            return self._breakpoints[bp_id]

        # Fallback if no breakpoints returned
        bp_id = f"{file}:{line}"
        self._breakpoints[bp_id] = {
            "id": bp_id,
            "file": str(file),
            "line": line,
            "verified": False,
            "condition": condition,
            "hit_condition": hit_condition,
            "log_message": log_message,
        }
        return self._breakpoints[bp_id]

    async def remove_breakpoint(self, breakpoint_id: str | int) -> bool:
        """Remove a breakpoint via the API.

        Parameters
        ----------
        breakpoint_id : Union[str, int]
            Breakpoint ID.

        Returns
        -------
        bool
            True if removed successfully.
        """
        self._validate_session_active()

        bp_id = str(breakpoint_id)
        if bp_id not in self._breakpoints:
            return False

        bp = self._breakpoints[bp_id]
        file_path = bp["file"]
        line = bp["line"]

        assert self.session is not None

        # Use the orchestration layer's remove_breakpoint operation
        # This properly updates the _breakpoint_store
        await self.session.debug.remove_breakpoint(file_path, line)

        # Update our tracking dict
        del self._breakpoints[bp_id]
        return True

    async def list_breakpoints(self) -> list[dict[str, Any]]:
        """List all current breakpoints.

        Uses the public API method which handles verification waiting
        automatically, preventing race conditions with fast-executing programs.

        Returns
        -------
        list[dict[str, Any]]
            List of breakpoint information.
        """
        self._validate_session_active()

        # Delegate to public API method
        assert self.api is not None
        response = await self.api.orchestration.list_breakpoints()

        # Convert AidbBreakpointsResponse to test format
        breakpoints = []
        if response.breakpoints:
            for bp_id, bp in response.breakpoints.items():
                # Prefer metadata from our tracking dict if available (has correct file path)
                bp_id_str = str(bp_id)
                if bp_id_str in self._breakpoints:
                    breakpoints.append(self._breakpoints[bp_id_str])
                else:
                    bp_info = {
                        "id": bp_id,
                        "file": bp.source_path,
                        "line": bp.line,
                        "location": f"{bp.source_path}:{bp.line}",
                        "verified": bp.verified,
                    }
                    if hasattr(bp, "condition") and bp.condition:
                        bp_info["condition"] = bp.condition
                    if hasattr(bp, "hit_condition") and bp.hit_condition:
                        bp_info["hit_condition"] = bp.hit_condition
                    if hasattr(bp, "log_message") and bp.log_message:
                        bp_info["log_message"] = bp.log_message
                    breakpoints.append(bp_info)

        return breakpoints

    async def step_over(self) -> dict[str, Any]:
        """Step over the current line via the API.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        assert self.session is not None
        # Get current thread ID from session
        thread_id = await self.session.debug.get_current_thread_id()
        result = await self.session.debug.step_over(
            thread_id=thread_id,
            wait_for_stop=True,
        )

        return self._format_execution_state(result)

    async def step_into(self) -> dict[str, Any]:
        """Step into a function via the API.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        assert self.session is not None
        thread_id = await self.session.debug.get_current_thread_id()
        result = await self.session.debug.step_into(
            thread_id=thread_id,
            wait_for_stop=True,
        )

        return self._format_execution_state(result)

    async def step_out(self) -> dict[str, Any]:
        """Step out of the current function via the API.

        Returns
        -------
        dict[str, Any]
            Execution state after stepping.
        """
        self._validate_session_active()

        assert self.session is not None
        thread_id = await self.session.debug.get_current_thread_id()
        result = await self.session.debug.step_out(
            thread_id=thread_id,
            wait_for_stop=True,
        )

        return self._format_execution_state(result)

    async def continue_execution(self) -> dict[str, Any]:
        """Continue execution via the API.

        Returns
        -------
        dict[str, Any]
            Execution state.
        """
        self._validate_session_active()

        # Import DAP request type
        from aidb.dap.protocol.bodies import ContinueArguments
        from aidb.dap.protocol.requests import ContinueRequest

        assert self.session is not None
        thread_id = await self.session.debug.get_current_thread_id()

        # Use singleThread=True to ensure only the current thread resumes.
        # This prevents other threads from executing, matching typical single-threaded
        # test program behavior and avoiding race conditions in test assertions.
        request = ContinueRequest(
            seq=0,  # Will be set by the client
            arguments=ContinueArguments(threadId=thread_id, singleThread=True),
        )
        result = await self.session.debug.continue_(request=request, wait_for_stop=True)

        return self._format_execution_state(result)

    async def get_state(self) -> dict[str, Any]:
        """Get the current execution state via the API.

        Returns
        -------
        dict[str, Any]
            Current execution state.

        Raises
        ------
        RuntimeError
            If unable to get execution state
        """
        self._validate_session_active()

        assert self.session is not None

        try:
            # Get the current state from the session
            result = await self.session.debug.get_execution_state()
            return self._format_execution_state(result)
        except Exception as e:
            msg = f"Failed to get execution state: {type(e).__name__}: {e}"
            raise RuntimeError(msg) from e

    async def get_variables(
        self,
        scope: str = "locals",
        frame: int | None = None,
    ) -> dict[str, Any]:
        """Get variables via the API.

        Parameters
        ----------
        scope : str, optional
            Scope ('locals', 'globals', 'all').
        frame : int, optional
            Stack frame ID. If None, uses current active frame.

        Returns
        -------
        dict[str, Any]
            Dictionary of variables.
        """
        self._validate_session_active()

        assert self.api is not None
        if scope == "locals":
            result = await self.api.introspection.locals(frame_id=frame)
        elif scope == "globals":
            result = await self.api.introspection.globals(frame_id=frame)
        elif scope == "all":
            locals_result = await self.api.introspection.locals(frame_id=frame)
            globals_result = await self.api.introspection.globals(frame_id=frame)
            # Combine both, locals take precedence
            return {
                **globals_result.variables,
                **locals_result.variables,
            }
        else:
            msg = f"Unknown scope: {scope}"
            raise ValueError(msg)

        return result.variables

    async def get_stack_trace(self) -> list[dict[str, Any]]:
        """Get the current stack trace via the API.

        Returns
        -------
        list[dict[str, Any]]
            List of stack frames.
        """
        self._validate_session_active()

        assert self.api is not None
        result = await self.api.introspection.callstack()

        return result.frames

    async def evaluate(
        self,
        expression: str,
        frame: int | None = None,
    ) -> Any:
        """Evaluate an expression via the API.

        Parameters
        ----------
        expression : str
            Expression to evaluate.
        frame : int, optional
            Stack frame ID. If None, uses current active frame.

        Returns
        -------
        Any
            Evaluation result.
        """
        self._validate_session_active()

        assert self.api is not None
        result = await self.api.introspection.evaluate(
            expression=expression,
            frame_id=frame,
        )

        # Return the result value from the EvaluationResult dataclass
        return result.result if hasattr(result, "result") else result

    async def cleanup(self) -> None:
        """Clean up the API interface resources.

        Stops any active session and releases resources. If session pool is enabled and
        session is from pool, returns it instead of destroying. Cleanup failures are
        logged but don't fail the test to ensure test teardown completes.
        """
        import logging
        import time

        logger = logging.getLogger(__name__)
        cleanup_start = time.time()

        if self._session_active and self.session:
            # If session is from pool, return it; otherwise destroy it
            if self._session_from_pool and self._session_pool:
                pool_return_start = time.time()

                try:
                    # Clear session manager reference before returning to pool
                    if self.api and hasattr(self.api, "_session_manager"):
                        self.api._session_manager._current_session = None
                    # Return session to pool (pool will reset state)
                    await self._session_pool.return_session(self.session)
                except Exception as e:
                    session_id = self.session.id if self.session else "unknown"
                    logger.warning(
                        "Pool return failed for session %s: %s",
                        session_id,
                        e,
                        exc_info=True,
                    )

                pool_return_time = time.time() - pool_return_start
                logger.info("Pool return took %.2fs", pool_return_time)
            else:
                destroy_start = time.time()
                try:
                    # Cleanup for non-pooled sessions
                    await self.session.stop()
                except Exception as e:
                    session_id = self.session.id if self.session else "unknown"
                    logger.warning(
                        "Session destroy failed for %s: %s",
                        session_id,
                        e,
                        exc_info=True,
                    )
                destroy_time = time.time() - destroy_start
                logger.info("Session destroy took %.2fs", destroy_time)

            self.session = None
            self._session_active = False

        total_cleanup_time = time.time() - cleanup_start
        logger.info("Total cleanup time: %.2fs", total_cleanup_time)

        self._session_from_pool = False
        self.api = None
        self._breakpoints.clear()
        self._initialized = False
