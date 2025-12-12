"""High-level LSP client coordinator for Eclipse JDT LS integration.

This module provides a high-level interface for LSP communication with JDT LS,
coordinating between the protocol layer and message handler.
"""

import asyncio
from pathlib import Path
from typing import Any

from aidb.patterns.base import Obj

from .lsp_message_handler import LSPMessageHandler
from .lsp_protocol import LSPProtocol


class LSPClient(Obj):
    """High-level LSP client for Eclipse JDT LS communication.

    This client coordinates between the protocol layer (LSPProtocol) and
    message handler (LSPMessageHandler) to provide a clean API for:
    1. LSP lifecycle (initialize, shutdown, exit)
    2. Workspace operations (execute commands, add folders)
    3. Event waiting (ServiceReady, diagnostics, Maven import)
    """

    def __init__(self, process: asyncio.subprocess.Process, ctx=None):
        """Initialize the LSP client with an async subprocess.

        Parameters
        ----------
        process : asyncio.subprocess.Process
            The JDT LS async subprocess with stdin/stdout streams
        ctx : optional
            Context for logging and storage
        """
        super().__init__(ctx)
        self.process = process

        # Create protocol and message handler components
        self.protocol = LSPProtocol(process, ctx=ctx)
        self.message_handler = LSPMessageHandler(self.protocol, ctx=ctx)

    def is_pooled(self) -> bool:
        """Check if this LSP client is managed by a pooled bridge.

        The _is_pooled flag is propagated from JavaLSPDAPBridge when it is
        allocated from a pool. This method provides a consistent API for
        checking pool status.

        Returns
        -------
        bool
            True if this client's parent bridge is pooled, False otherwise.
        """
        return getattr(self, "_is_pooled", False)

    async def start(self):
        """Start the LSP client (starts message handler loop)."""
        await self.message_handler.start()

    async def stop(self):
        """Stop the LSP client and cleanup transports."""
        await self.message_handler.stop()

    async def initialize(
        self,
        root_uri: str,
        initialization_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send initialize request to the language server.

        Parameters
        ----------
        root_uri : str
            The root URI of the workspace
        initialization_options : Optional[Dict[str, Any]]
            Server-specific initialization options

        Returns
        -------
        Dict[str, Any]
            The server capabilities
        """
        return await self.protocol.initialize(root_uri, initialization_options)

    async def shutdown(self):
        """Send shutdown request to the language server."""
        await self.protocol.shutdown()

    async def exit(self):
        """Send exit notification to the language server."""
        await self.protocol.exit()

    async def execute_command(
        self,
        command: str,
        arguments: list[Any] | None = None,
        timeout: float = 30.0,
    ) -> Any:
        """Execute a workspace command.

        Parameters
        ----------
        command : str
            The command identifier
        arguments : Optional[List[Any]]
            Command arguments
        timeout : float
            Timeout in seconds

        Returns
        -------
        Any
            The command result
        """
        params = {"command": command, "arguments": arguments or []}
        return await self.protocol.send_request(
            "workspace/executeCommand",
            params,
            timeout=timeout,
        )

    async def add_workspace_folder(
        self,
        folder_path: Path,
        name: str | None = None,
    ) -> None:
        """Add a workspace folder to JDT LS for dynamic project discovery.

        This sends a workspace/didChangeWorkspaceFolders notification to inform
        JDT LS about a new project folder. JDT LS will then import the project
        (Maven/Gradle) and make it available for classpath resolution.

        Parameters
        ----------
        folder_path : Path
            Absolute path to the project folder to register
        name : str | None
            Optional human-readable name for the folder (defaults to folder name)

        Notes
        -----
        - JDT LS needs time to import the project after registration
        - This method waits 8 seconds to allow import to complete
        - For Maven projects, JDT LS will resolve all dependencies
        - For Gradle projects, JDT LS will execute Gradle to get classpath
        """
        folder_uri = folder_path.as_uri()
        folder_name = name or folder_path.name

        params = {
            "event": {
                "added": [{"uri": folder_uri, "name": folder_name}],
                "removed": [],
            },
        }

        self.ctx.info(f"Adding workspace folder to JDT LS: {folder_path}")
        await self.protocol.send_notification(
            "workspace/didChangeWorkspaceFolders",
            params,
        )
        self.ctx.debug(f"Workspace folder registered: {folder_name}")

    async def wait_for_service_ready(self, timeout: float = 30.0) -> bool:
        """Wait for JDT LS to send ServiceReady notification.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if ServiceReady was received, False if timeout
        """
        return await self.message_handler.wait_for_service_ready(timeout)

    async def wait_for_diagnostics(
        self,
        file_path: str,
        timeout: float = 5.0,
    ) -> bool:
        """Wait for textDocument/publishDiagnostics after opening a file.

        Parameters
        ----------
        file_path : str
            Path to the file (will be converted to file:// URI)
        timeout : float
            Maximum seconds to wait

        Returns
        -------
        bool
            True if diagnostics received, False if timeout
        """
        return await self.message_handler.wait_for_diagnostics(file_path, timeout)

    async def wait_for_maven_import_complete(self, timeout: float = 60.0) -> bool:
        """Wait until an "Importing Maven project(s)" progress completes.

        Parameters
        ----------
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if Maven import completed, False if timeout
        """
        return await self.message_handler.wait_for_maven_import_complete(timeout)

    async def open_file(self, file_path: str, language_id: str = "java") -> None:
        """Open a file in the language server via textDocument/didOpen.

        This notifies JDT LS that a file is being worked with, which triggers
        the creation of the invisible project for single files.

        Parameters
        ----------
        file_path : str
            Absolute path to the file to open
        language_id : str
            Language identifier (default: "java")
        """
        from aidb.common.errors import AidbError

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            msg = f"File not found: {file_path}"
            raise AidbError(msg)

        # Read file content
        content = file_path_obj.read_text(encoding="utf-8")

        # Build textDocument/didOpen notification
        params = {
            "textDocument": {
                "uri": file_path_obj.as_uri(),
                "languageId": language_id,
                "version": 1,
                "text": content,
            },
        }

        self.ctx.debug(f"Opening file in JDT LS: {file_path}")
        await self.protocol.send_notification("textDocument/didOpen", params)

    async def reset_session_state(self) -> None:
        """Reset session-specific state for a new debug session.

        This method clears accumulated state from previous debug sessions while
        preserving the LSP connection itself. Call this before starting a new
        debug session on a pooled LSP bridge to prevent state corruption.

        Clears:
        - Protocol state (pending requests, responses, request ID counter)
        - Message handler state (notifications)

        Does NOT:
        - Stop the reader task (connection stays alive)
        - Terminate the LSP process (shared resource)
        - Clear initialization state (LSP remains initialized)
        """
        self.ctx.debug("Resetting LSP client session state")

        # Reset protocol state (requests, responses, IDs)
        await self.protocol.reset_state()

        # Reset message handler state (notifications)
        await self.message_handler.reset_session_state()

        self.ctx.debug(
            "LSP client session state reset complete - ready for new debug session",
        )
