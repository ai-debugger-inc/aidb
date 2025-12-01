"""Mock session manager for testing."""

import time
from typing import Any

from aidb_mcp.core.constants import ParamName
from tests._helpers.constants import Language
from tests._helpers.mocks.adapter_mocks import MockAdapter
from tests._helpers.mocks.dap_mocks import MockDAPClient


class MockSessionManager:
    """Mock session manager for testing."""

    def __init__(self):
        """Initialize mock session manager."""
        self.sessions: dict[str, dict[str, Any]] = {}
        self.active_session_id: str | None = None

    def create_session(self, session_id: str, **kwargs) -> str:
        """Create a mock session."""
        session = {
            "id": session_id,
            "created_at": time.time(),
            "status": "created",
            "language": kwargs.get("language", Language.PYTHON.value),
            "target": kwargs.get("target", "main.py"),
            "adapter": MockAdapter(kwargs.get("language", Language.PYTHON.value)),
            "dap_client": MockDAPClient(),
            "port": None,
        }

        self.sessions[session_id] = session
        return session_id

    async def start_session(self, session_id: str, **kwargs) -> dict[str, Any]:
        """Start a mock session."""
        if session_id not in self.sessions:
            msg = f"Session {session_id} not found"
            raise ValueError(msg)

        session = self.sessions[session_id]

        # Mock starting the adapter
        adapter_result = await session["adapter"].start(session["target"], **kwargs)

        session["port"] = adapter_result["port"]
        session["status"] = "running"
        self.active_session_id = session_id

        return {
            ParamName.SESSION_ID: session_id,
            "status": "running",
            "port": session["port"],
            "language": session["language"],
        }

    async def stop_session(self, session_id: str) -> bool:
        """Stop a mock session."""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]
        await session["adapter"].stop()
        await session["dap_client"].disconnect()

        session["status"] = "stopped"

        if self.active_session_id == session_id:
            self.active_session_id = None

        return True

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session information."""
        return self.sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        return [
            {
                "id": sid,
                "status": session["status"],
                "language": session["language"],
                "created_at": session["created_at"],
            }
            for sid, session in self.sessions.items()
        ]

    def cleanup(self) -> None:
        """Clean up all sessions."""
        self.sessions.clear()
        self.active_session_id = None
