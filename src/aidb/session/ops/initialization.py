"""Initialization operations mixin for DAP sequence handling."""

import json
import time
from typing import TYPE_CHECKING, Optional, cast

from aidb.adapters.base.initialize import InitializationOp, InitializationOpType
from aidb.common.constants import (
    EVENT_POLL_TIMEOUT_S,
    INIT_REQUEST_TIMEOUT_S,
    LONG_WAIT_S,
    POLL_SLEEP_INTERVAL_S,
    RECONNECTION_TIMEOUT_S,
    STACK_TRACE_TIMEOUT_S,
)
from aidb.dap.client.constants import EventType
from aidb.dap.protocol.base import Response
from aidb.dap.protocol.bodies import (
    AttachRequestArguments,
    ConfigurationDoneArguments,
    InitializeRequestArguments,
)
from aidb.dap.protocol.requests import (
    AttachRequest,
    ConfigurationDoneRequest,
    InitializeRequest,
    LaunchRequest,
)
from aidb.dap.protocol.responses import (
    AttachResponse,
    InitializeResponse,
    LaunchResponse,
)
from aidb.resources.process_tags import ProcessTags, ProcessType
from aidb_common.path import normalize_path

if TYPE_CHECKING:
    from aidb.interfaces import IContext
    from aidb.session import Session

from .base import BaseOperations


class InitializationMixin(BaseOperations):
    """Mixin providing DAP initialization sequence operations.

    Handles the complex multi-step process of initializing debug adapters through the
    Debug Adapter Protocol.
    """

    def __init__(self, session: "Session", ctx: Optional["IContext"] = None) -> None:
        """Initialize initialization operations.

        Parameters
        ----------
        session : Session
            The session that owns this debugger operations
        ctx : AidbContext, optional
            Application context, by default `None`
        """
        super().__init__(session, ctx)

    def _get_operation_handlers(self) -> dict:
        """Get mapping of operation types to handler methods.

        Returns
        -------
        dict
            Mapping of InitializationOpType to handler method
        """
        return {
            InitializationOpType.INITIALIZE: self._handle_initialize_op,
            InitializationOpType.WAIT_FOR_INITIALIZED: self._handle_wait_initialized_op,
            InitializationOpType.WAIT_FOR_PLUGIN_READY: self._handle_wait_plugin_op,
            InitializationOpType.ATTACH: self._handle_attach_op,
            InitializationOpType.LAUNCH: self._handle_launch_op,
            InitializationOpType.SET_BREAKPOINTS: self._handle_set_breakpoints_op,
            InitializationOpType.WAIT_FOR_BREAKPOINT_VERIFICATION: (
                self._handle_wait_breakpoint_verification_op
            ),
            InitializationOpType.CONFIGURATION_DONE: self._handle_config_done_op,
            InitializationOpType.WAIT_FOR_ATTACH_RESPONSE: (
                self._handle_wait_attach_response_op
            ),
            InitializationOpType.WAIT_FOR_LAUNCH_RESPONSE: (
                self._handle_wait_launch_response_op
            ),
        }

    async def _handle_initialize_op(
        self,
        operation: InitializationOp,  # noqa: ARG002
    ) -> None:
        """Handle initialize operation."""
        response = await self._do_initialize()
        self._operation_responses["initialize"] = response

    async def _handle_wait_initialized_op(self, operation: InitializationOp) -> None:
        """Handle wait for initialized event operation."""
        await self._wait_for_initialized(operation.timeout)

    async def _handle_wait_plugin_op(self, operation: InitializationOp) -> None:
        """Handle wait for plugin ready operation."""
        await self._wait_for_plugin_ready(operation.timeout)

    async def _handle_attach_op(self, operation: InitializationOp) -> None:
        """Handle attach operation."""
        attach_response = await self._do_attach(
            wait_for_response=operation.wait_for_response,
            timeout=operation.timeout,
        )
        if attach_response:
            self._operation_responses["attach"] = attach_response

    async def _handle_launch_op(self, operation: InitializationOp) -> None:
        """Handle launch operation."""
        launch_response = await self._do_launch(
            wait_for_response=operation.wait_for_response,
            timeout=operation.timeout,
        )
        if launch_response:
            self._operation_responses["launch"] = launch_response

    async def _handle_set_breakpoints_op(
        self,
        operation: InitializationOp,  # noqa: ARG002
    ) -> None:
        """Handle set breakpoints operation."""
        await self._do_set_breakpoints()

    async def _handle_wait_breakpoint_verification_op(
        self,
        operation: InitializationOp,
    ) -> None:
        """Handle wait for breakpoint verification operation."""
        await self._wait_for_breakpoint_verification(operation.timeout)

    async def _handle_config_done_op(
        self,
        operation: InitializationOp,  # noqa: ARG002
    ) -> None:
        """Handle configuration done operation."""
        config_done_response = await self._do_configuration_done()
        self._operation_responses["configuration_done"] = config_done_response

    async def _handle_wait_attach_response_op(
        self,
        operation: InitializationOp,
    ) -> None:
        """Handle wait for deferred attach response operation."""
        self.ctx.debug("Waiting for deferred attach response...")
        if self._deferred_attach_request:
            response = await self._wait_for_deferred_attach_response(
                operation.timeout,
            )
            self._operation_responses["attach"] = response
            self.ctx.debug("Got attach response, continuing...")

    async def _handle_wait_launch_response_op(
        self,
        operation: InitializationOp,
    ) -> None:
        """Handle wait for deferred launch response operation."""
        self.ctx.debug("Waiting for deferred launch response...")
        if self._deferred_launch_request:
            response = await self._wait_for_deferred_launch_response(
                operation.timeout,
            )
            self._operation_responses["launch"] = response
            self.ctx.debug("Got launch response, continuing...")

    async def _execute_initialization_sequence(
        self,
        sequence: list[InitializationOp],
    ) -> None:
        """Execute the DAP initialization sequence.

        Parameters
        ----------
        sequence : list[InitializationOp]
            The ordered list of operations to perform
        """
        # Track responses for operations that need them later
        self._operation_responses: dict[str, Response] = {}
        self._deferred_attach_seq: int | None = None
        self._deferred_attach_request: AttachRequest | None = None
        self._deferred_launch_seq: int | None = None
        self._deferred_launch_request: LaunchRequest | None = None

        # Get operation handlers
        handlers = self._get_operation_handlers()

        for operation in sequence:
            try:
                # Get handler for operation type
                handler = handlers.get(operation.type)
                if handler:
                    await handler(operation)
                else:
                    self.ctx.warning(f"Unknown operation type: {operation.type}")

            except Exception as e:
                if not operation.optional:
                    raise
                self.ctx.warning(
                    f"Optional operation {operation.type.value} failed: {e}",
                )

    async def _do_initialize(self) -> InitializeResponse:
        """Send the initialize request to the debug adapter."""
        self.ctx.debug("Preparing initialize request")

        # Get client capabilities from the DAP client
        client_caps = self.session.dap.client_capabilities

        # Create initialize arguments with centralized client capabilities
        init_args = InitializeRequestArguments(
            adapterID=self.session.adapter.config.adapter_id,
            **client_caps,  # Unpack all client capabilities
        )
        init_request = InitializeRequest(seq=0, arguments=init_args)

        self.ctx.info("Sending initialize request to debug adapter")
        init_response = cast(
            "InitializeResponse",
            await self.session.dap.send_request(
                init_request,
                timeout=INIT_REQUEST_TIMEOUT_S,
            ),
        )
        init_response.ensure_success()
        self.ctx.info("Initialize request successful")

        # Store adapter capabilities
        if init_response.body:
            self.session.store_capabilities(init_response.body)

        return init_response

    async def _wait_for_initialized(self, timeout: float) -> None:
        """Wait for the initialized event from the adapter with fallback retry."""
        self.ctx.debug("Waiting for initialized event from adapter...")

        # First attempt
        if await self.session.dap.event_processor.wait_for_event(
            EventType.INITIALIZED.value,
            timeout=timeout,
        ):
            self.ctx.debug("Received initialized event")
            return

        # Timeout on first attempt - try reconnection fallback if adapter supports it
        if self._should_attempt_reconnection():
            self.ctx.warning(
                "Initialized event timeout - attempting DAP reconnection fallback...",
            )

            if await self._reconnect_and_retry_initialize(timeout):
                return

        self.ctx.warning("Did not receive initialized event, proceeding anyway")

    async def _reconnect_and_retry_initialize(self, timeout: float) -> bool:
        """Reconnect DAP and retry waiting for initialized event.

        Returns
        -------
        bool
            True if retry successful, False otherwise
        """
        # Attempt reconnection using the public reconnect method
        if not await self.session.dap.reconnect(timeout=RECONNECTION_TIMEOUT_S):
            self.ctx.error("Reconnection failed, cannot retry initialization")
            return False

        # Retry initialize request
        self.ctx.info("Resending initialize request after reconnection...")
        try:
            await self._do_initialize()
        except Exception as e:
            self.ctx.error(f"Initialize retry failed: {e}")
            return False

        # Resend launch/attach request if we had sent one before
        if self._deferred_launch_seq is not None:
            self.ctx.info("Resending launch request after reconnection...")
            try:
                self._deferred_launch_seq = await self.session.dap.send_request_no_wait(
                    self._deferred_launch_request,
                )
                self.ctx.debug(
                    f"Launch request resent with seq={self._deferred_launch_seq}",
                )
            except Exception as e:
                self.ctx.error(f"Launch resend failed: {e}")
                return False
        elif self._deferred_attach_seq is not None:
            self.ctx.info("Resending attach request after reconnection...")
            try:
                self._deferred_attach_seq = await self.session.dap.send_request_no_wait(
                    self._deferred_attach_request,
                )
                self.ctx.debug(
                    f"Attach request resent with seq={self._deferred_attach_seq}",
                )
            except Exception as e:
                self.ctx.error(f"Attach resend failed: {e}")
                return False

        # Retry waiting for initialized event
        self.ctx.debug("Waiting for initialized event (retry attempt)...")
        if await self.session.dap.event_processor.wait_for_event(
            EventType.INITIALIZED.value,
            timeout=timeout,
        ):
            self.ctx.info("Received initialized event on retry!")
            return True

        self.ctx.error("Initialized event timeout on retry - giving up")

        # Mark the test pool as unhealthy if we're using it
        self._mark_pool_unhealthy()

        return False

    def _mark_pool_unhealthy(self) -> None:
        """Mark the JDT LS pool as unhealthy if we're using it."""
        if not hasattr(self.session.adapter, "_lsp_dap_bridge"):
            return

        bridge = self.session.adapter._lsp_dap_bridge

        # Check test pool first
        try:
            from tests._fixtures.java_lsp_pool import get_test_jdtls_pool

            test_pool = get_test_jdtls_pool()
            if test_pool and test_pool.bridge == bridge:
                test_pool.mark_unhealthy()
                self.ctx.warning(
                    "Marked test JDT LS pool as unhealthy due to repeated "
                    "initialization failures",
                )
                return
        except ImportError:
            pass  # Not in test environment
        except Exception as e:
            self.ctx.debug(f"Error checking test pool health: {e}")

        # Check per-project pool (new)
        try:
            from aidb.adapters.lang.java.jdtls_project_pool import (
                get_jdtls_project_pool_sync,
                shutdown_jdtls_project_pool,
            )

            proj_pool = get_jdtls_project_pool_sync()
            if proj_pool:
                # Best-effort: schedule a shutdown to force clean restart on next use
                import asyncio

                try:
                    asyncio.create_task(shutdown_jdtls_project_pool())
                except RuntimeError:
                    # No running loop; ignore
                    pass
                self.ctx.warning(
                    "Scheduled per-project JDT LS pool shutdown due to repeated "
                    "initialization failures",
                )
        except Exception as e:
            self.ctx.debug(f"Error checking per-project pool health: {e}")

    def _should_attempt_reconnection(self) -> bool:
        """Check if reconnection should be attempted.

        Delegates to adapter to determine if reconnection fallback is needed.
        Adapters can implement the `should_attempt_dap_reconnection_fallback`
        property to enable this feature.

        Returns
        -------
        bool
            True if reconnection fallback should be tried
        """
        return getattr(
            self.session.adapter,
            "should_attempt_dap_reconnection_fallback",
            False,
        )

    async def _wait_for_plugin_ready(self, timeout: float) -> None:
        """Wait for Java debug plugin to be ready in Eclipse JDT LS.

        This method checks if the Java adapter is using LSP-DAP bridge and polls the
        java-debug plugin via LSP commands until it's ready.

        For pooled bridges that have been used before, the plugin is already loaded and
        ready, so the wait is skipped entirely.
        """
        from aidb.adapters.lang.java.java import JavaAdapter

        # Only apply plugin readiness check for Java adapters with LSP bridge
        if not isinstance(self.session.adapter, JavaAdapter):
            self.ctx.debug("Not a Java adapter, skipping plugin readiness check")
            return

        if (
            not hasattr(self.session.adapter, "_lsp_dap_bridge")
            or not self.session.adapter._lsp_dap_bridge
        ):
            self.ctx.debug("No LSP-DAP bridge found, skipping plugin readiness check")
            return

        bridge = self.session.adapter._lsp_dap_bridge

        # For pooled bridges, check if plugin was already initialized
        # Pooled bridges reuse JDT LS instances, so the plugin is already loaded
        # Use is_pooled() as the single source of truth for pool detection
        if hasattr(bridge, "is_pooled") and bridge.is_pooled():
            self.ctx.debug(
                "Skipping plugin readiness wait for pooled bridge "
                "(plugin already initialized from previous sessions)",
            )
            return

        self.ctx.info(
            f"Waiting for java-debug plugin readiness (timeout: {timeout}s)...",
        )

        import asyncio
        import time

        start_time = time.time()
        check_interval = LONG_WAIT_S

        while time.time() - start_time < timeout:
            try:
                # Check if LSP-DAP bridge is ready and responsive
                if (
                    bridge
                    and bridge.lsp_client
                    and hasattr(bridge, "debug_session_manager")
                    and hasattr(bridge.debug_session_manager, "dap_port")
                    and bridge.debug_session_manager.dap_port
                ):
                    # The bridge has established a DAP port, which means JDT LS
                    # is running and the java-debug plugin has loaded
                    self.ctx.info(
                        f"Java-debug plugin is ready! "
                        f"DAP port: {bridge.debug_session_manager.dap_port}",
                    )
                    return

            except Exception as e:
                self.ctx.debug(f"Plugin readiness check failed: {e}")

            # Wait before next check
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                wait_time = min(check_interval, remaining)
                self.ctx.debug(f"Plugin not ready yet, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)

        self.ctx.warning(
            f"Java-debug plugin readiness timeout after {timeout}s, proceeding anyway",
        )  # Let configurationDone handle any remaining issues

    async def _do_attach(
        self,
        wait_for_response: bool = True,
        timeout: float = 15.0,
    ) -> AttachResponse | None:
        """Send attach request to the debug adapter."""
        attach_args = AttachRequestArguments()

        # Get the adapter's custom attach config, similar to _do_launch
        if hasattr(self.session.adapter, "get_launch_configuration"):
            self.ctx.debug("Getting adapter configuration for attach...")
            attach_config = self.session.adapter.get_launch_configuration()
            if attach_config:
                self.ctx.debug(
                    f"Using adapter attach configuration: {list(attach_config.keys())}",
                )
                # Dynamically add all configuration fields to attach arguments
                for key, value in attach_config.items():
                    setattr(attach_args, key, value)
                    self.ctx.debug(f"  Set attach_args.{key} = {value}")
            else:
                self.ctx.debug("Adapter returned no attach configuration")

        attach_request = AttachRequest(seq=0, arguments=attach_args)
        self.ctx.debug("Sending attach request")

        if not wait_for_response:
            # For debugpy, send but don't wait for response
            self._deferred_attach_request = attach_request
            self._deferred_attach_seq = await self.session.dap.send_request_no_wait(
                attach_request,
            )
            self.ctx.debug(
                f"Attach request sent with seq={self._deferred_attach_seq} "
                f"(not waiting for response)",
            )
            return None
        attach_response = cast(
            "AttachResponse",
            await self.session.dap.send_request(attach_request, timeout=timeout),
        )
        attach_response.ensure_success()
        self.ctx.info("DAP attach successful")
        return attach_response

    async def _do_launch(
        self,
        wait_for_response: bool = True,
        timeout: float = 15.0,
    ) -> LaunchResponse | None:
        """Send launch request to the debug adapter."""
        # Check if session has launch args override (used for child sessions)
        if (
            hasattr(self.session, "_launch_args_override")
            and self.session._launch_args_override
        ):
            # Use dict arguments directly for child sessions with special fields
            # like __pendingTargetId
            launch_args = self.session._launch_args_override.copy()
            launch_args.setdefault("noDebug", False)
            self.ctx.debug(
                f"Using launch args override from session: {list(launch_args.keys())}",
            )
        else:
            # Standard launch args for regular sessions
            launch_args = {"noDebug": False}

            # Get the adapter's custom launch config, if any
            self.ctx.debug("Adapter has get_launch_configuration method, calling it...")
            launch_config = self.session.adapter.get_launch_configuration()
            if launch_config:
                from aidb.adapters.base.launch import BaseLaunchConfig

                self.ctx.debug(
                    f"Using adapter launch configuration: {list(launch_config.keys())}",
                )

                # Dynamically add all configuration fields to launch arguments
                for key, value in launch_config.items():
                    # Skip VS Code-only fields (not part of DAP)
                    if key in BaseLaunchConfig.VSCODE_ONLY_FIELDS:
                        self.ctx.debug(f"  Filtered VS Code-only field: {key}")
                        continue

                    # Skip null values (DAP adapters prefer omission to null)
                    if value is None:
                        self.ctx.debug(f"  Skipped null value for: {key}")
                        continue

                    # Normalize program path if present to resolve symlinks
                    if key == "program" and value and isinstance(value, str):
                        value = normalize_path(value)
                        self.ctx.debug(f"  Normalized program path: {value}")
                    launch_args[key] = value
                    self.ctx.debug(
                        f"  Set launch_args[{key}] = "
                        f"{value if key != 'trace' else '...'}",
                    )
            else:
                self.ctx.debug("Adapter returned no launch configuration")

        # Inject AIDB process tags into debuggee environment
        debuggee_env = launch_args.get("env", {})
        if not isinstance(debuggee_env, dict):
            debuggee_env = {}
        debuggee_env.update(
            {
                ProcessTags.OWNER: ProcessTags.OWNER_VALUE,
                ProcessTags.SESSION_ID: self.session.id,
                ProcessTags.PROCESS_TYPE: ProcessType.DEBUGGEE,
                ProcessTags.LANGUAGE: self.session.adapter.config.language,
                ProcessTags.START_TIME: str(int(time.time())),
            },
        )
        launch_args["env"] = debuggee_env
        self.ctx.debug(f"Tagged debuggee with session_id={self.session.id}")

        # DAP spec says launch arguments are implementation-specific,
        # so pass dict directly instead of typed LaunchRequestArguments
        launch_request = LaunchRequest(
            seq=0,
            arguments=launch_args,
        )

        # Debug logging for launch request body
        launch_body = launch_request.to_dict()
        self.ctx.debug(f"Launch request body:\n{json.dumps(launch_body, indent=2)}")

        if not wait_for_response:
            self._deferred_launch_request = launch_request
            self._deferred_launch_seq = await self.session.dap.send_request_no_wait(
                launch_request,
            )
            self.ctx.debug(
                f"Launch request sent with seq={self._deferred_launch_seq} "
                f"(not waiting for response)",
            )
            return None
        self.ctx.debug("Sending launch request and waiting for response")
        launch_response = cast(
            "LaunchResponse",
            await self.session.dap.send_request(launch_request, timeout=timeout),
        )
        launch_response.ensure_success()
        self.ctx.info("DAP launch successful")
        return launch_response

    async def _do_set_breakpoints(self) -> None:
        """Set initial breakpoints if any are configured."""
        if self.session.breakpoints:
            await self.session._set_initial_breakpoints()

    async def _wait_for_breakpoint_verification(self, timeout: float) -> None:
        """Wait for breakpoint verification events from the adapter.

        After setBreakpoints is called, adapters send 'breakpoint' events to update
        verification status. We need to wait for these events before starting execution
        to ensure breakpoints are actually bound to code.

        Parameters
        ----------
        timeout : float
            Maximum time to wait for verification in seconds
        """
        if not self.session.breakpoints:
            self.ctx.debug("No breakpoints to verify, skipping wait")
            return

        breakpoint_count = len(self.session.breakpoints)
        self.ctx.debug(
            f"Waiting up to {timeout}s for {breakpoint_count} "
            f"breakpoint(s) to be verified",
        )

        import asyncio

        # Wait for breakpoint events using the event system
        # This is more reliable than polling since events arrive asynchronously
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Wait for a breakpoint event (with a short timeout for each iteration)
            got_event = await self.session.dap.event_processor.wait_for_event(
                EventType.BREAKPOINT.value,
                timeout=EVENT_POLL_TIMEOUT_S,
            )

            # After each event (or timeout), check if all breakpoints are verified
            # Check the live breakpoint store, not the initial spec list
            current_bps = self.session.current_breakpoints
            if current_bps and current_bps.breakpoints:
                verified_count = sum(
                    1 for bp in current_bps.breakpoints.values() if bp.verified
                )
            else:
                verified_count = 0

            if verified_count == breakpoint_count:
                self.ctx.debug(
                    f"All {breakpoint_count} breakpoint(s) verified",
                )
                return

            # If no event in this iteration, continue waiting
            if not got_event:
                await asyncio.sleep(POLL_SLEEP_INTERVAL_S)

        # Final check after timeout
        current_bps = self.session.current_breakpoints
        if current_bps and current_bps.breakpoints:
            verified_count = sum(
                1 for bp in current_bps.breakpoints.values() if bp.verified
            )
        else:
            verified_count = 0
        self.ctx.warning(
            f"Breakpoint verification timeout: {verified_count}/{breakpoint_count} "
            f"verified after {timeout}s. Proceeding anyway.",
        )

    async def _do_configuration_done(self) -> Response:
        """Send configurationDone request."""
        self.ctx.debug("Sending configurationDone request")
        config_done_args = ConfigurationDoneArguments()
        config_done_request = ConfigurationDoneRequest(
            seq=0,
            arguments=config_done_args,
        )
        config_done_response = await self.session.dap.send_request(
            config_done_request,
            timeout=STACK_TRACE_TIMEOUT_S,
        )
        config_done_response.ensure_success()
        self.ctx.info("Configuration done")
        return config_done_response

    async def _wait_for_deferred_attach_response(
        self,
        timeout: float,
    ) -> AttachResponse:
        """Wait for a deferred attach response (debugpy-specific)."""
        self.ctx.debug("Waiting for deferred attach response...")
        # For debugpy, the attach response comes after configurationDone We need
        # to read it from the response queue
        if (
            hasattr(self, "_deferred_attach_seq")
            and self._deferred_attach_seq is not None
        ):
            response = await self.session.dap.wait_for_response(
                self._deferred_attach_seq,
                timeout,
            )
            attach_response = cast("AttachResponse", response)
            attach_response.ensure_success()
            self.ctx.info("Received deferred attach response")
            return attach_response
        msg = "No deferred attach request to wait for"
        raise RuntimeError(msg)

    async def _wait_for_deferred_launch_response(
        self,
        timeout: float,
    ) -> LaunchResponse:
        """Wait for a deferred launch response."""
        self.ctx.debug("Waiting for deferred launch response...")
        if self._deferred_launch_seq is not None:
            response = await self.session.dap.wait_for_response(
                self._deferred_launch_seq,
                timeout,
            )
            launch_response = cast("LaunchResponse", response)
            launch_response.ensure_success()
            self.ctx.info("Received deferred launch response")
            return launch_response
        msg = "No deferred launch request to wait for"
        raise RuntimeError(msg)
