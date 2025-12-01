"""Mock DAP client for testing without real debug adapters."""

import asyncio
import time
from typing import Any

from aidb.dap.protocol import (
    BreakpointEvent,
    ContinuedEvent,
    ExitedEvent,
    LoadedSourceEvent,
    ModuleEvent,
    OutputEvent,
    ProcessEvent,
    Response,
    StoppedEvent,
    TerminatedEvent,
    ThreadEvent,
)
from tests._helpers.constants import DebugPorts, StopReason


class MockDAPClient:
    """Mock DAP client for testing without real debug adapters."""

    def __init__(self):
        """Initialize mock DAP client."""
        self.is_connected = False
        self.capabilities = {
            "supportsConfigurationDoneRequest": True,
            "supportsConditionalBreakpoints": True,
            "supportsSetVariable": True,
            "supportsHitConditionalBreakpoints": True,
            "supportsLogPoints": True,
            "supportsRestartRequest": True,
            "supportsTerminateRequest": True,
        }

        # Track requests and responses
        self.requests: list[dict[str, Any]] = []
        self.responses: dict[str, Response] = {}
        self.events: list[Any] = []

        # State tracking
        self.initialized = False
        self.configured = False
        self.running = False
        self.breakpoints: dict[str, dict[str, Any]] = {}
        self.threads = [{"id": 1, "name": "Main Thread"}]
        self.stack_frames: dict[int, list[dict[str, Any]]] = {}
        self.variables: dict[int, list[dict[str, Any]]] = {}

        # Response customization
        self.custom_responses: dict[str, dict[str, Any]] = {}
        self.event_sequence: list[Any] = []
        self.error_responses: dict[str, str] = {}

    async def connect(
        self,
        host: str = "localhost",
        port: int = DebugPorts.PYTHON,
    ) -> bool:
        """Mock connection to debug adapter."""
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        """Mock disconnection from debug adapter."""
        self.is_connected = False
        self.initialized = False
        self.configured = False
        self.running = False

    async def request(self, command: str, arguments: dict | None = None) -> Response:
        """Mock DAP request with configurable responses."""
        if arguments is None:
            arguments = {}

        # Record the request
        request_record = {
            "command": command,
            "arguments": arguments,
            "timestamp": time.time(),
        }
        self.requests.append(request_record)

        # Check for custom error responses
        if command in self.error_responses:
            error_msg = self.error_responses[command]
            response = Response(
                seq=len(self.requests),
                request_seq=len(self.requests),
                success=False,
                command=command,
                message=error_msg,
            )
            self.responses[command] = response
            return response

        # Check for custom responses
        if command in self.custom_responses:
            response = Response(
                seq=len(self.requests),
                request_seq=len(self.requests),
                success=True,
                command=command,
                body=None,
            )
            self.responses[command] = response
            return response

        # Default responses for common commands
        self._get_default_response(command, arguments)

        response = Response(
            seq=len(self.requests),
            request_seq=len(self.requests),
            success=True,
            command=command,
            body=None,
        )

        self.responses[command] = response

        # Trigger events for certain commands
        await self._trigger_events_for_command(command, arguments)

        return response

    def _handle_initialize(self) -> dict[str, Any]:
        """Handle initialize command."""
        self.initialized = True
        return self.capabilities

    def _handle_launch_attach(self) -> dict[str, Any]:
        """Handle launch/attach commands."""
        self.configured = True
        return {}

    def _handle_configuration_done(self) -> dict[str, Any]:
        """Handle configurationDone command."""
        self.running = True
        return {}

    def _handle_set_breakpoints(self, arguments: dict) -> dict[str, Any]:
        """Handle setBreakpoints command."""
        source = arguments.get("source", {})
        breakpoints_args = arguments.get("breakpoints", [])

        source_path = source.get("path", "unknown")
        verified_breakpoints = []

        for i, bp in enumerate(breakpoints_args):
            bp_id = f"{source_path}:{bp.get('line', i)}"
            verified_bp = {
                "id": len(self.breakpoints) + i,
                "verified": True,
                "line": bp.get("line", 1),
                "source": source,
            }

            if "condition" in bp:
                verified_bp["condition"] = bp["condition"]

            verified_breakpoints.append(verified_bp)
            self.breakpoints[bp_id] = verified_bp

        return {"breakpoints": verified_breakpoints}

    def _handle_stack_trace(self, arguments: dict) -> dict[str, Any]:
        """Handle stackTrace command."""
        thread_id = arguments.get("threadId", 1)

        default_frames = [
            {
                "id": 0,
                "name": "main",
                "source": {"path": "/test/main.py", "name": "main.py"},
                "line": 10,
                "column": 1,
            },
            {
                "id": 1,
                "name": "calculate",
                "source": {"path": "/test/main.py", "name": "main.py"},
                "line": 3,
                "column": 1,
            },
        ]

        frames = self.stack_frames.get(thread_id, default_frames)
        return {"stackFrames": frames, "totalFrames": len(frames)}

    def _handle_scopes(self, arguments: dict) -> dict[str, Any]:
        """Handle scopes command."""
        frame_id = arguments.get("frameId", 0)
        return {
            "scopes": [
                {
                    "name": "Locals",
                    "variablesReference": frame_id * 1000 + 1,
                    "expensive": False,
                },
                {
                    "name": "Globals",
                    "variablesReference": frame_id * 1000 + 2,
                    "expensive": True,
                },
            ],
        }

    def _handle_variables(self, arguments: dict) -> dict[str, Any]:
        """Handle variables command."""
        variables_ref = arguments.get("variablesReference", 1)

        default_variables = [
            {"name": "x", "value": "10", "type": "int", "variablesReference": 0},
            {"name": "y", "value": "20", "type": "int", "variablesReference": 0},
            {
                "name": "result",
                "value": "30",
                "type": "int",
                "variablesReference": 0,
            },
        ]

        variables = self.variables.get(variables_ref, default_variables)
        return {"variables": variables}

    def _handle_evaluate(self, arguments: dict) -> dict[str, Any]:
        """Handle evaluate command."""
        expression = arguments.get("expression", "unknown")
        return {
            "result": f"result_of_{expression}",
            "type": "string",
            "variablesReference": 0,
        }

    def _handle_set_variable(self, arguments: dict) -> dict[str, Any]:
        """Handle setVariable command."""
        return {"value": arguments.get("value", "new_value"), "type": "string"}

    def _get_default_response(self, command: str, arguments: dict) -> dict[str, Any]:
        """Get default response for a command."""
        # Simple command handlers
        simple_handlers = {
            "initialize": lambda: self._handle_initialize(),
            "launch": lambda: self._handle_launch_attach(),
            "attach": lambda: self._handle_launch_attach(),
            "configurationDone": lambda: self._handle_configuration_done(),
            "threads": lambda: {"threads": self.threads},
            "continue": lambda: {"allThreadsContinued": True},
            "disconnect": dict,
            "terminate": dict,
        }

        # Stepping commands
        step_commands = {"next", "stepIn", "stepOut", StopReason.PAUSE.value}
        if command in step_commands:
            return {}

        # Commands that need arguments
        arg_handlers = {
            "setBreakpoints": self._handle_set_breakpoints,
            "stackTrace": self._handle_stack_trace,
            "scopes": self._handle_scopes,
            "variables": self._handle_variables,
            "evaluate": self._handle_evaluate,
            "setVariable": self._handle_set_variable,
        }

        # Try simple handlers first
        if command in simple_handlers:
            return simple_handlers[command]()

        # Try argument handlers
        if command in arg_handlers:
            return arg_handlers[command](arguments)

        # Default response
        return {"success": True}

    async def _trigger_events_for_command(self, command: str, arguments: dict) -> None:
        """Trigger appropriate events for commands."""
        if command == "continue":
            # Simulate continued event
            from aidb.dap.protocol.bodies import ContinuedEventBody

            event = ContinuedEvent(
                seq=len(self.events) + 1,
                body=ContinuedEventBody(threadId=1, allThreadsContinued=True),
            )
            self.events.append(event)

            # If we have a predefined event sequence, use it
            if self.event_sequence:
                next_event = self.event_sequence.pop(0)
                # Small delay to simulate async nature
                await asyncio.sleep(0.1)
                self.events.append(next_event)

        elif command in ["next", "stepIn", "stepOut"]:
            # Simulate step completion with stopped event
            await asyncio.sleep(0.05)
            from aidb.dap.protocol.bodies import StoppedEventBody

            stopped_event = StoppedEvent(
                seq=len(self.events) + 1,
                body=StoppedEventBody(
                    reason=StopReason.STEP.value,
                    threadId=1,
                    allThreadsStopped=True,
                ),
            )
            self.events.append(stopped_event)

        elif command == "launch" or command == "attach":
            # Simulate process and thread events
            from aidb.dap.protocol.bodies import ProcessEventBody, ThreadEventBody

            process_event = ProcessEvent(
                seq=len(self.events) + 1,
                body=ProcessEventBody(
                    name="test_process",
                    systemProcessId=12345,
                    startMethod="launch" if command == "launch" else "attach",
                ),
            )
            self.events.append(process_event)

            thread_event = ThreadEvent(
                seq=len(self.events) + 2,
                body=ThreadEventBody(reason="started", threadId=1),
            )
            self.events.append(thread_event)

        elif command == "setBreakpoints":
            # Simulate breakpoint events
            from aidb.dap.protocol.bodies import BreakpointEventBody
            from aidb.dap.protocol.types import Breakpoint

            for bp in arguments.get("breakpoints", []):
                bp_event = BreakpointEvent(
                    seq=len(self.events) + 1,
                    body=BreakpointEventBody(
                        reason="new",
                        breakpoint=Breakpoint(
                            id=len(self.breakpoints) + 1,
                            verified=True,
                            line=bp.get("line", 1),
                        ),
                    ),
                )
                self.events.append(bp_event)

        elif command == "disconnect" or command == "terminate":
            # Simulate termination events
            from aidb.dap.protocol.bodies import (
                ExitedEventBody,
                TerminatedEventBody,
            )

            exited_event = ExitedEvent(
                seq=len(self.events) + 1,
                body=ExitedEventBody(exitCode=0),
            )
            self.events.append(exited_event)

            terminated_event = TerminatedEvent(
                seq=len(self.events) + 2,
                body=TerminatedEventBody(),
            )
            self.events.append(terminated_event)

    def set_custom_response(self, command: str, response_body: dict[str, Any]) -> None:
        """Set a custom response for a command."""
        self.custom_responses[command] = response_body

    def set_error_response(self, command: str, error_message: str) -> None:
        """Set an error response for a command."""
        self.error_responses[command] = error_message

    def add_event_to_sequence(
        self,
        event: StoppedEvent
        | ContinuedEvent
        | BreakpointEvent
        | OutputEvent
        | ThreadEvent
        | ModuleEvent
        | LoadedSourceEvent
        | ProcessEvent
        | TerminatedEvent
        | ExitedEvent,
    ) -> None:
        """Add an event to the sequence that will be triggered."""
        self.event_sequence.append(event)

    def simulate_output(
        self,
        category: str = "console",
        output: str = "Test output\n",
    ) -> None:
        """Simulate output event."""
        from aidb.dap.protocol.bodies import OutputEventBody

        output_event = OutputEvent(
            seq=len(self.events) + 1,
            body=OutputEventBody(category=category, output=output),
        )
        self.events.append(output_event)

    def simulate_module_loaded(self, module_name: str, module_path: str) -> None:
        """Simulate module loaded event."""
        from aidb.dap.protocol.bodies import ModuleEventBody
        from aidb.dap.protocol.types import Module

        module_event = ModuleEvent(
            seq=len(self.events) + 1,
            body=ModuleEventBody(
                reason="new",
                module=Module(
                    id=len(self.events),
                    name=module_name,
                    path=module_path,
                ),
            ),
        )
        self.events.append(module_event)

    def simulate_thread_event(self, thread_id: int, reason: str = "started") -> None:
        """Simulate thread event."""
        from aidb.dap.protocol.bodies import ThreadEventBody

        thread_event = ThreadEvent(
            seq=len(self.events) + 1,
            body=ThreadEventBody(reason=reason, threadId=thread_id),
        )
        self.events.append(thread_event)

        # Update internal thread list
        if reason == "started":
            self.threads.append({"id": thread_id, "name": f"Thread {thread_id}"})
        elif reason == "exited":
            self.threads = [t for t in self.threads if t["id"] != thread_id]

    def get_requests_for_command(self, command: str) -> list[dict[str, Any]]:
        """Get all requests made for a specific command."""
        return [req for req in self.requests if req["command"] == command]

    def was_command_called(self, command: str, **expected_args) -> bool:
        """Check if a command was called with expected arguments."""
        for request in self.requests:
            if request["command"] == command:
                args = request["arguments"]
                if all(args.get(k) == v for k, v in expected_args.items()):
                    return True
        return False

    def reset(self) -> None:
        """Reset the mock to initial state."""
        self.is_connected = False
        self.initialized = False
        self.configured = False
        self.running = False
        self.requests.clear()
        self.responses.clear()
        self.events.clear()
        self.breakpoints.clear()
        self.stack_frames.clear()
        self.variables.clear()
        self.custom_responses.clear()
        self.event_sequence.clear()
        self.error_responses.clear()
