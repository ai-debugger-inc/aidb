"""IDE-related notifications for MCP.

This module provides notification services for IDE state changes and events that might
be relevant to AI assistants during debugging workflows.
"""

from __future__ import annotations

from typing import Any

from aidb.integrations.ide_detector import IDEDetector, IDEType

from aidb.common.constants import (
    DEFAULT_ADAPTER_HOST,
    DEFAULT_VSCODE_BRIDGE_PORT,
    RECEIVE_POLL_TIMEOUT_S,
)
from aidb.integrations.vscode import VSCodeIntegration
from aidb_logging import get_mcp_logger as get_logger

logger = get_logger(__name__)


class IDENotificationService:
    """Service for monitoring and notifying about IDE state changes."""

    def __init__(self, notification_manager):
        """Initialize the IDE notification service.

        Parameters
        ----------
        notification_manager : NotificationManager
            The MCP notification manager
        """
        self.notification_manager = notification_manager
        self._last_known_state = {}
        self._monitoring = False

    async def start_monitoring(self):
        """Start monitoring IDE state changes."""
        if self._monitoring:
            return

        self._monitoring = True
        logger.info("Started IDE state monitoring")

        # Get initial state
        self._last_known_state = self._get_current_state()

    def stop_monitoring(self):
        """Stop monitoring IDE state changes."""
        self._monitoring = False
        logger.info("Stopped IDE state monitoring")

    def _get_current_state(self) -> dict[str, Any]:
        """Get the current IDE state.

        Returns
        -------
        Dict[str, Any]
            Current IDE and extension state
        """
        current_ide = IDEDetector.detect_current_ide()
        state = {
            "ide_type": current_ide.value,
            "ide_available": current_ide != IDEType.UNKNOWN,
        }

        if current_ide != IDEType.UNKNOWN:
            integration = VSCodeIntegration(ide_type=current_ide)
            state["extension_installed"] = integration.is_extension_installed()

            # Check bridge connection
            try:
                import socket

                with socket.create_connection(
                    (DEFAULT_ADAPTER_HOST, DEFAULT_VSCODE_BRIDGE_PORT),
                    timeout=int(RECEIVE_POLL_TIMEOUT_S),
                ):
                    state["bridge_active"] = True
            except (OSError, ConnectionRefusedError, TimeoutError):
                state["bridge_active"] = False
        else:
            state["extension_installed"] = False
            state["bridge_active"] = False

        return state

    async def check_and_notify_changes(self):
        """Check for state changes and send notifications if needed."""
        if not self._monitoring:
            return

        current_state = self._get_current_state()

        # Check for changes
        if current_state != self._last_known_state:
            await self._notify_state_change(self._last_known_state, current_state)
            self._last_known_state = current_state

    async def _notify_state_change(
        self,
        old_state: dict[str, Any],
        new_state: dict[str, Any],
    ):
        """Send notification about IDE state change.

        Parameters
        ----------
        old_state : Dict[str, Any]
            Previous state
        new_state : Dict[str, Any]
            New state
        """
        changes = []

        # Check what changed
        if old_state.get("ide_type") != new_state.get("ide_type"):
            changes.append(
                f"IDE changed from {old_state.get('ide_type')} "
                f"to {new_state.get('ide_type')}",
            )

        if old_state.get("extension_installed") != new_state.get("extension_installed"):
            if new_state.get("extension_installed"):
                changes.append("AIDB extension was installed")
            else:
                changes.append("AIDB extension was uninstalled")

        if old_state.get("bridge_active") != new_state.get("bridge_active"):
            if new_state.get("bridge_active"):
                changes.append("VS Code bridge is now active")
            else:
                changes.append("VS Code bridge disconnected")

        if changes:
            notification_data = {
                "event_type": "ide_state_changed",
                "changes": changes,
                "old_state": old_state,
                "new_state": new_state,
                "recommendation": self._get_recommendation(new_state),
            }

            await self.notification_manager.notify(
                "ide_state_changed",
                notification_data,
            )
            logger.info("IDE state changed: ", ", ".join(changes))

    def _get_recommendation(self, state: dict[str, Any]) -> str | None:
        """Get recommendation based on current state.

        Parameters
        ----------
        state : Dict[str, Any]
            Current IDE state

        Returns
        -------
        Optional[str]
            Recommendation message if action needed
        """
        if not state.get("ide_available"):
            return "No compatible IDE detected. Debugging features may be limited."

        if not state.get("extension_installed"):
            return (
                "Install the AIDB extension using 'ide_install_extension' "
                "for full debugging features."
            )

        if not state.get("bridge_active"):
            return (
                "VS Code bridge is not active. "
                "Restart VS Code to activate the extension."
            )

        return None


async def notify_task_completion(
    notification_manager,
    task_name: str,
    success: bool,
    output: str | None = None,
):
    """Send notification when a VS Code task completes.

    Parameters
    ----------
    notification_manager : NotificationManager
        The MCP notification manager
    task_name : str
        Name of the completed task
    success : bool
        Whether the task completed successfully
    output : Optional[str]
        Task output if available
    """
    notification_data = {
        "event_type": "task_completed",
        "task_name": task_name,
        "success": success,
        "output": output,
    }

    await notification_manager.notify("task_completed", notification_data)
    logger.info(
        "Task '%s' completed: %s",
        task_name,
        "success" if success else "failed",
    )
