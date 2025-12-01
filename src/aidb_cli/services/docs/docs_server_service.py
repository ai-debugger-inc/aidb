"""Service for serving documentation."""

import time
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.common.errors import AidbError
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_cli.services.docs.docs_builder_service import DocsBuilderService, DocsTarget
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class DocsServerService(BaseService):
    """Service for serving documentation.

    This service handles:
    - Starting/stopping documentation servers
    - Port management
    - Browser launching
    - Server status monitoring
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the docs server service."""
        super().__init__(repo_root, command_executor)
        self.builder_service = DocsBuilderService(repo_root, command_executor)

    def serve_docs(
        self,
        target: DocsTarget,
        port: int | None = None,
        build_first: bool = False,
    ) -> None:
        """Start documentation server.

        Args
        ----
            target: Documentation target configuration
            port: Port to serve on (uses default if None)
            build_first: Whether to build before serving
        """
        if build_first:
            self.builder_service.build_docs(target)

        env = {target.port_env_var: str(port or target.default_port)}
        executor = self.builder_service.get_docs_executor()

        executor.up(
            services=[target.serve_service],
            detach=True,
            extra_env=env,
            capture_output=True,
            check=True,
        )

    def stop_docs(self) -> None:
        """Stop all documentation servers."""
        executor = self.builder_service.get_docs_executor()
        result = executor.down(timeout=0)

        if result.returncode != 0:
            msg = f"Failed to stop docs: exit code {result.returncode}"
            raise AidbError(msg)

    def open_docs(
        self,
        target: DocsTarget,
        port: int | None = None,
    ) -> None:
        """Open documentation in browser, starting server if needed.

        Args
        ----
            target: Documentation target
            port: Port to use if starting server
        """
        running, detected_port = self.builder_service.get_service_status(target)

        if not running:
            CliOutput.info("Docs not running, starting...")
            self.serve_docs(target, port, build_first=True)
            time.sleep(2)
            running, detected_port = self.builder_service.get_service_status(target)

        final_port = detected_port or str(port or target.default_port)
        webbrowser.open(f"http://localhost:{final_port}")

    def get_docs_status(
        self,
        target: DocsTarget,
    ) -> tuple[str, str | None]:
        """Get formatted status of documentation service.

        Args
        ----
            target: Documentation target

        Returns
        -------
            Tuple of (status_message, url_if_running)
        """
        running, port = self.builder_service.get_service_status(target)

        if running:
            url = f"http://localhost:{port}"
            return f"Running on port {port}", url
        return "Not running", None

    def show_all_status(self) -> None:
        """Display status of documentation services."""
        public_running, public_port = self.builder_service.get_service_status(
            DocsBuilderService.PUBLIC,
        )

        from aidb_cli.core.constants import Icons
        from aidb_cli.core.formatting import HeadingFormatter

        HeadingFormatter.section("Documentation Status", Icons.GLOBE)

        if public_running:
            CliOutput.success(f"Docs: Running at http://localhost:{public_port}")
        else:
            CliOutput.info("Docs: Not running")
