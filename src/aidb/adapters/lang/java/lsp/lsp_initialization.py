"""LSP initialization helpers for JDT LS setup.

This module provides stateless helper functions for building JDT LS initialization
options and handling the initialization sequence.
"""

from pathlib import Path
from typing import Any

from aidb.patterns.base import Obj


class LSPInitialization(Obj):
    """Stateless helpers for LSP initialization.

    Handles:
    - Building initialization options with java-debug bundle
    - Workspace folder URI formatting
    - Extended client capabilities configuration
    """

    def __init__(self, java_debug_jar: Path, ctx=None):
        """Initialize the LSP initialization helper.

        Parameters
        ----------
        java_debug_jar : Path
            Path to the java-debug-server plugin JAR
        ctx : optional
            Context for logging
        """
        super().__init__(ctx)
        self.java_debug_jar = java_debug_jar

    def build_initialization_options(
        self,
        workspace_folders: list[tuple[Path, str]] | None = None,
    ) -> dict[str, Any]:
        """Build initialization options for JDT LS with java-debug plugin.

        Parameters
        ----------
        workspace_folders : Optional[List[Tuple[Path, str]]]
            List of (path, name) tuples for workspace folders to include during init

        Returns
        -------
        Dict[str, Any]
            The initialization options dictionary
        """
        init_options: dict[str, Any] = {
            "bundles": [str(self.java_debug_jar)],
            "extendedClientCapabilities": {
                "classFileContentsSupport": True,
                "overrideMethodsPromptSupport": True,
                "hashCodeEqualsPromptSupport": True,
                "advancedOrganizeImportsSupport": True,
                "generateToStringPromptSupport": True,
                "advancedGenerateAccessorsSupport": True,
                "generateConstructorsPromptSupport": True,
                "generateDelegateMethodsPromptSupport": True,
                "advancedExtractRefactoringSupport": True,
                "inferSelectionSupport": [
                    "extractMethod",
                    "extractVariable",
                    "extractConstant",
                ],
                "moveRefactoringSupport": True,
                "clientHoverProvider": True,
                "clientDocumentSymbolProvider": True,
                "gradleChecksumWrapperPromptSupport": True,
                "resolveAdditionalTextEditsSupport": True,
                "progressReportProvider": True,
                "buildStatusProvider": True,
                "debuggingSupport": True,  # Important for java-debug integration
            },
        }

        # Pass workspace folders during initialization if provided
        # JDT LS expects a Collection<String> of URIs
        if workspace_folders:
            folder_uris = [
                folder_path.as_uri() for folder_path, _name in workspace_folders
            ]
            init_options["workspaceFolders"] = folder_uris
            self.ctx.info(
                f"Initializing JDT LS with {len(folder_uris)} workspace folder(s)",
            )

        return init_options
