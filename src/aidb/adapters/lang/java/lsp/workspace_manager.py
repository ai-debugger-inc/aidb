"""Workspace manager for JDT LS workspace and project management.

This module handles workspace folder registration, Maven/Gradle project import, and URI
normalization for cross-platform compatibility.
"""

import asyncio
import random
import time
from pathlib import Path

from aidb.adapters.lang.java.tooling import JavaBuildSystemDetector
from aidb.common.constants import (
    DEFAULT_WAIT_TIMEOUT_S,
    LSP_EXECUTE_COMMAND_TIMEOUT_S,
    LSP_MAVEN_IMPORT_TIMEOUT_S,
    LSP_PROJECT_IMPORT_TIMEOUT_S,
    PROCESS_TERMINATE_TIMEOUT_S,
)
from aidb.patterns.base import Obj


class WorkspaceManager(Obj):
    """Manager for JDT LS workspace and project management.

    Handles:
    - Workspace folder registration with JDT LS
    - Maven/Gradle project import polling (CRITICAL timing logic)
    - URI normalization for cross-platform compatibility
    - Project registration tracking
    """

    def __init__(self, ctx=None):
        """Initialize the workspace manager.

        Parameters
        ----------
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self._workspace_folders: set[str] = set()

    async def register_workspace_folders(
        self,
        lsp_client,
        workspace_folders: list[tuple[Path, str]],
    ) -> None:
        """Register workspace folders with JDT LS and wait for Maven/Gradle import.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        workspace_folders : List[Tuple[Path, str]]
            List of (path, name) tuples for workspace folders

        Raises
        ------
        AidbError
            If workspace folder registration or import fails
        """
        if not workspace_folders:
            return

        # Determine which folders actually need to be added
        to_add: list[tuple[Path, str]] = []
        for folder_path, folder_name in workspace_folders:
            folder_path_str = str(folder_path.resolve())
            if folder_path_str not in self._workspace_folders:
                to_add.append((folder_path, folder_name))
            else:
                self.ctx.debug(
                    f"Workspace folder already registered, skipping: "
                    f"{folder_name} ({folder_path})",
                )

        if not to_add:
            self.ctx.info(
                "All workspace folders already registered; verifying import/health",
            )
        else:
            self.ctx.info(
                f"Registering {len(to_add)} workspace folder(s) with JDT LS...",
            )

        # Register each new workspace folder dynamically
        for folder_path, folder_name in to_add:
            self.ctx.info(f"Adding workspace folder: {folder_name} ({folder_path})")
            await lsp_client.add_workspace_folder(folder_path, folder_name)
            self._workspace_folders.add(str(folder_path.resolve()))

        # Wait for Maven/Gradle project import to complete
        project_root = (to_add or workspace_folders)[0][0]
        project_name = (to_add or workspace_folders)[0][1]
        self.ctx.info(
            f"Waiting for Maven/Gradle import to complete for {project_name}...",
        )

        # Lightweight health check to catch unresponsive LSP early (e.g., after reuse)
        try:
            _ = await lsp_client.execute_command(
                "java.project.getAll",
                [],
                timeout=PROCESS_TERMINATE_TIMEOUT_S,
            )
            self.ctx.debug("LSP health check (java.project.getAll) succeeded")
        except Exception as e:
            self.ctx.warning(
                f"LSP health check failed (getAll): {e}. Continuing with import wait",
            )

        # Skip progress wait for pooled bridges (Events bound to pool loop,
        # not caller loop). Pooled bridges fall back to polling-based wait
        # which works correctly
        progress_ready = False
        if (
            not lsp_client.is_pooled()
            and lsp_client
            and hasattr(lsp_client, "wait_for_maven_import_complete")
        ):
            try:
                progress_ready = await lsp_client.wait_for_maven_import_complete(
                    timeout=LSP_MAVEN_IMPORT_TIMEOUT_S,
                )
            except Exception as e:
                self.ctx.debug(f"Progress-based wait unavailable: {e}")

        if not progress_ready:
            import_ready = await self.wait_for_project_import(
                lsp_client=lsp_client,
                project_name=project_name,
                project_root=project_root,
                timeout=LSP_PROJECT_IMPORT_TIMEOUT_S,
            )

            if not import_ready:
                timeout_msg = f"{LSP_PROJECT_IMPORT_TIMEOUT_S}s"
                self.ctx.warning(
                    f"Maven/Gradle import did not complete within {timeout_msg} "
                    f"for {project_name}. Classpath resolution may fail.",
                )

    async def wait_for_project_import(  # noqa: C901
        self,
        lsp_client,
        project_name: str,
        project_root: Path | None = None,
        test_class: str = "Object",
        timeout: float = 60.0,
    ) -> bool:
        """Wait for Maven/Gradle project import to complete.

        CRITICAL: This method has fragile timing logic that must be preserved exactly.

        JDT LS sends ServiceReady notification before Maven import completes.
        This method polls java.project.getAll to detect when the project appears,
        then verifies classpath resolution is ready.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        project_name : str
            The project name to test
        project_root : Path, optional
            The project root path (used to match URIs from JDT LS)
        test_class : str
            A class name to test resolution with
        timeout : float
            Maximum time to wait in seconds

        Returns
        -------
        bool
            True if project import completed successfully, False if timeout

        Notes
        -----
        This is necessary because:
        - ServiceReady fires when LSP server is ready
        - Maven import happens asynchronously in background
        - No standard notification for Maven import completion
        - Classpath resolution fails if called too early
        - JDT LS returns project URIs, not names, so we match by URI
        """
        start_time = time.time()
        attempt = 0

        # Build expected URI from project root for matching
        expected_uri = None
        if project_root:
            expected_uri = self._normalize_file_uri(project_root.as_uri())
            self.ctx.debug(f"Looking for project URI: {expected_uri}")

        self.ctx.info(
            f"Polling for Maven/Gradle import completion (timeout: {timeout}s)...",
        )

        while time.time() - start_time < timeout:
            attempt += 1
            elapsed = time.time() - start_time

            # First: see if project has appeared in JDT LS workspace
            try:
                proj_list = await lsp_client.execute_command(
                    "java.project.getAll",
                    [],
                    timeout=DEFAULT_WAIT_TIMEOUT_S,
                )
                present = False
                if isinstance(proj_list, list):
                    for item in proj_list:
                        if isinstance(item, str):
                            # Normalize for comparison
                            item_uri = self._normalize_file_uri(item)

                            # Match by URI if we have expected_uri
                            if expected_uri and item_uri == expected_uri:
                                present = True
                                self.ctx.debug(f"Found project URI match: {item_uri}")
                                break

                            # Fallback: check if URI path contains project_name
                            if project_name and project_name in item:
                                present = True
                                self.ctx.debug(
                                    f"Found project name in URI: {item_uri}",
                                )
                                break

                        elif isinstance(item, dict):
                            # Handle dict format
                            name = item.get("name") or item.get("projectName")
                            if name == project_name:
                                present = True
                                break

                if not present:
                    self.ctx.debug(
                        f"Attempt {attempt}: Project '{project_name}' not present "
                        f"(elapsed: {elapsed:.1f}s). URIs: {proj_list}",
                    )
                    await asyncio.sleep(random.uniform(1.0, 2.0))  # noqa: S311
                    continue

                # Project found! Log and proceed to classpath verification
                self.ctx.debug(
                    f"Project found after {elapsed:.1f}s, verifying classpath...",
                )

            except Exception as e:
                # Log error but continue with classpath probe
                self.ctx.debug(f"Attempt {attempt}: getAll failed: {e}")
                await asyncio.sleep(random.uniform(1.0, 2.0))  # noqa: S311
                continue

            try:
                # Try to resolve classpath - succeeds once import is done
                # Need to import the debug_session_manager methods here
                classpath = await lsp_client.execute_command(
                    "vscode.java.resolveClasspath",
                    [test_class, project_name or ""],
                    timeout=LSP_EXECUTE_COMMAND_TIMEOUT_S,
                )

                # Extract classpath from result
                if isinstance(classpath, list):
                    classpath_list = classpath
                elif isinstance(classpath, dict) and "classpaths" in classpath:
                    classpath_list = classpath["classpaths"]
                else:
                    classpath_list = []

                # Success if we got a non-empty classpath
                if classpath_list:
                    self.ctx.info(
                        f"Maven/Gradle import complete after {elapsed:.1f}s "
                        f"({attempt} attempts, "
                        f"{len(classpath_list)} classpath entries)",
                    )
                    return True

                # Empty classpath might mean still importing
                self.ctx.debug(
                    f"Attempt {attempt}: Empty classpath, still waiting... "
                    f"(elapsed: {elapsed:.1f}s)",
                )

            except Exception as e:
                # Errors are expected while import is in progress
                self.ctx.debug(
                    f"Attempt {attempt}: Classpath failed (importing): {e}",
                )

            # Wait before next attempt with small jitter (1-2s)
            await asyncio.sleep(random.uniform(1.0, 2.0))  # noqa: S311

        # Timeout reached
        elapsed = time.time() - start_time
        self.ctx.warning(
            f"Maven/Gradle import did not complete within {timeout}s "
            f"({attempt} attempts, elapsed: {elapsed:.1f}s)",
        )
        return False

    async def register_project(
        self,
        lsp_client,
        project_root: Path,
        project_name: str | None = None,
    ) -> None:
        """Register a Maven/Gradle project with JDT LS for classpath resolution.

        This method dynamically registers a project folder with JDT LS using the
        workspace/didChangeWorkspaceFolders notification. JDT LS will then import
        the project (resolving Maven dependencies or executing Gradle) and make it
        available for classpath resolution.

        Must be called before resolve_classpath() for pooled bridges, as pooled
        bridges start with an empty temp workspace.

        Parameters
        ----------
        lsp_client : LSPClient
            The LSP client for communication
        project_root : Path
            Absolute path to the project root (must contain pom.xml or build.gradle)
        project_name : str | None
            Optional human-readable name for the project (defaults to folder name)

        Raises
        ------
        AidbError
            If LSP client is not initialized

        Notes
        -----
        - Validates that the project has Maven (pom.xml) or Gradle (build.gradle)
        - Skips registration if project was already registered
        - JDT LS needs ~2 seconds to import the project
        """
        # Normalize path to string for tracking
        project_root_str = str(project_root.resolve())

        # Skip if already registered
        if project_root_str in self._workspace_folders:
            self.ctx.debug(f"Project already registered: {project_root}")
            return

        # Validate it's a Maven/Gradle project
        if not JavaBuildSystemDetector.is_maven_gradle_project(project_root):
            self.ctx.warning(
                f"No pom.xml or build.gradle found in {project_root} - "
                "JDT LS may not be able to resolve dependencies",
            )

        # Register with JDT LS
        self.ctx.info(f"Registering project with JDT LS: {project_root}")
        await lsp_client.add_workspace_folder(project_root, project_name)

        # Track registration
        self._workspace_folders.add(project_root_str)
        self.ctx.debug(f"Project registered successfully: {project_root}")

    def _normalize_file_uri(self, uri: str) -> str:
        """Normalize file URI for cross-platform comparison.

        JDT LS may return URIs with varying formats:
        - Linux: file:/path (1 slash)
        - Standard RFC 8089: file:///path (3 slashes)
        - Trailing slashes may vary

        This normalizes to RFC 8089 format for consistent comparison.

        Parameters
        ----------
        uri : str
            File URI to normalize

        Returns
        -------
        str
            Normalized URI in file:/// format without trailing slash
        """
        # Remove trailing slash
        uri = uri.rstrip("/")

        # Normalize file:/ or file:// to file:/// for consistency
        if uri.startswith("file:/"):
            # Count slashes after file:
            if uri.startswith("file:///"):
                # Already normalized (3 slashes)
                pass
            elif uri.startswith("file://"):
                # 2 slashes - add one more
                uri = "file:///" + uri[7:]
            else:
                # 1 slash - convert to 3
                uri = "file:///" + uri[6:]

        return uri
