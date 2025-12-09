"""Service for managing adapter metadata operations."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from aidb import __version__ as current_aidb_version
from aidb_cli.core.constants import Icons
from aidb_cli.core.paths import CachePaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class AdapterMetadataService(BaseService):
    """Service for managing adapter metadata operations.

    This service handles:
    - Loading adapter metadata files
    - Displaying adapter information
    - Version compatibility checking
    - Metadata formatting
    """

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the adapter metadata service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        super().__init__(repo_root, command_executor)
        self._metadata_cache: dict[str, dict] = {}

    def _initialize_service(self) -> None:
        """Initialize service-specific resources."""

    def load_adapter_metadata(self, language: str) -> dict[str, Any]:
        """Load metadata for a specific adapter.

        Parameters
        ----------
        language : str
            Adapter language

        Returns
        -------
        dict[str, Any]
            Metadata dictionary or empty dict if not found
        """
        # Check cache first
        if language in self._metadata_cache:
            return self._metadata_cache[language]

        # Standard locations to check for metadata
        metadata_paths = [
            CachePaths.user_cache() / language / "metadata.json",
            CachePaths.adapters_dir() / language / "metadata.json",
        ]

        for metadata_path in metadata_paths:
            if metadata_path.exists():
                try:
                    metadata = safe_read_json(metadata_path) or {}
                    self._metadata_cache[language] = metadata
                    return metadata
                except FileOperationError as e:
                    self.log_error(
                        "Failed to load metadata from %s: %s",
                        metadata_path,
                        str(e),
                    )

        # Return empty dict if no metadata found
        return {}

    def display_adapter_list_with_metadata(
        self,
        languages: list[str],
        built_list: list[str],
        missing_list: list[str],
    ) -> None:
        """Display adapter list with metadata information.

        Parameters
        ----------
        languages : list[str]
            All supported languages
        built_list : list[str]
            List of built adapters
        missing_list : list[str]
            List of missing adapters
        """
        # Prepare data for auto-table
        from aidb_cli.core.formatting import HeadingFormatter

        table_data = []
        for lang in languages:
            built = lang in built_list
            status_icon = Icons.SUCCESS if built else Icons.ERROR
            status_text = "Built" if built else "Missing"

            if built:
                metadata = self.load_adapter_metadata(lang)
                adapter_version = metadata.get("adapter_version", "unknown")
                adapter_aidb_version = metadata.get("aidb_version", "unknown")
                compat_icon = self._get_compatibility_icon(adapter_aidb_version)
            else:
                adapter_version = "---"
                adapter_aidb_version = "---"
                compat_icon = "---"

            table_data.append(
                {
                    "Language": lang,
                    "Status": status_text,
                    "Version": adapter_version,
                    "AIDB": adapter_aidb_version,
                    "Compat": compat_icon,
                },
            )

        # Auto-generate table with perfect column sizing
        column_order = ["Language", "Status", "Version", "AIDB", "Compat"]
        widths = HeadingFormatter.auto_table(
            f"Adapter Status (AIDB Version: {current_aidb_version})",
            table_data,
            column_order,
        )

        # Display data rows using calculated widths
        for i, lang in enumerate(languages):
            built = lang in built_list
            status_icon = Icons.SUCCESS if built else Icons.ERROR
            row = table_data[i]

            CliOutput.plain(
                f"{status_icon} {row['Language']:<{widths['Language'] - 1}}"
                f"{row['Status']:<{widths['Status']}}"
                f"{row['Version']:<{widths['Version']}}"
                f"{row['AIDB']:<{widths['AIDB']}}"
                f"{row['Compat']:<{widths['Compat']}}",
            )

        HeadingFormatter.table_separator()

        # Summary information
        self._display_summary(languages, built_list, missing_list)

    def display_adapter_info_with_metadata(
        self,
        language: str,
        adapter_info: dict[str, str],
    ) -> None:
        """Display detailed adapter information with metadata.

        Parameters
        ----------
        language : str
            Adapter language
        adapter_info : dict[str, str]
            Basic adapter information
        """
        from aidb_cli.core.formatting import HeadingFormatter

        metadata = self.load_adapter_metadata(language)

        # Display information
        HeadingFormatter.section(f"Adapter Information: {language}", Icons.PACKAGE)

        # Basic info
        CliOutput.plain(f"Status:           {adapter_info['status']}")
        CliOutput.plain(
            f"Type:             {adapter_info.get('type', 'Debug Adapter')}",
        )
        location = adapter_info.get("location", adapter_info.get("path", "unknown"))
        CliOutput.plain(f"Location:         {location}")

        # Metadata info
        if metadata:
            CliOutput.plain("")
            HeadingFormatter.subsection("Metadata Information")

            adapter_version = metadata.get("adapter_version", "unknown")
            adapter_aidb_version = metadata.get("aidb_version", "unknown")
            adapter_name = metadata.get("adapter_name", language)
            build_date = metadata.get("build_date", "unknown")
            binary_identifier = metadata.get("binary_identifier", "unknown")
            repo = metadata.get("repo", "unknown")

            CliOutput.plain(f"Adapter Name:     {adapter_name}")
            CliOutput.plain(f"Adapter Version:  {adapter_version}")
            CliOutput.plain(f"Binary File:      {binary_identifier}")
            CliOutput.plain(f"Source Repo:      {repo}")
            CliOutput.plain(f"Build Date:       {build_date}")
            CliOutput.plain(f"Built with AIDB:  {adapter_aidb_version}")
            CliOutput.plain(f"Current AIDB:     {current_aidb_version}")

            # Version compatibility check
            self._display_compatibility_status(adapter_aidb_version, language)
        else:
            CliOutput.plain("")
            CliOutput.warning("No metadata information available")

    def check_version_mismatches(
        self,
        languages: list[str],
        built_list: list[str],
    ) -> list[str]:
        """Check for version mismatches in built adapters.

        Parameters
        ----------
        languages : list[str]
            All supported languages
        built_list : list[str]
            List of built adapters

        Returns
        -------
        list[str]
            List of adapters with version mismatches
        """
        mismatched = []
        for lang in languages:
            if lang in built_list:
                metadata = self.load_adapter_metadata(lang)
                adapter_aidb_version = metadata.get("aidb_version")
                if (
                    adapter_aidb_version
                    and adapter_aidb_version != current_aidb_version
                ):
                    mismatched.append(lang)
        return mismatched

    def _get_compatibility_icon(self, adapter_aidb_version: str) -> str:
        """Get compatibility icon based on version.

        Parameters
        ----------
        adapter_aidb_version : str
            Adapter AIDB version

        Returns
        -------
        str
            Compatibility icon
        """
        if adapter_aidb_version == current_aidb_version:
            return Icons.SUCCESS
        if adapter_aidb_version == "unknown":
            return "❓"
        return Icons.WARNING

    def _display_compatibility_status(
        self,
        adapter_aidb_version: str,
        language: str,
    ) -> None:
        """Display version compatibility status.

        Parameters
        ----------
        adapter_aidb_version : str
            Adapter AIDB version
        language : str
            Adapter language
        """
        if adapter_aidb_version == current_aidb_version:
            CliOutput.success("Version compatibility: OK")
        elif adapter_aidb_version == "unknown":
            CliOutput.warning("Version compatibility: Unknown")
        else:
            CliOutput.warning("Version compatibility: Mismatch")
            CliOutput.info(
                f"Consider running './dev-cli adapters download --install -l "
                f"{language}' to update",
            )

    def _display_summary(
        self,
        languages: list[str],
        built_list: list[str],
        missing_list: list[str],
    ) -> None:
        """Display summary information for adapter list.

        Parameters
        ----------
        languages : list[str]
            All supported languages
        built_list : list[str]
            List of built adapters
        missing_list : list[str]
            List of missing adapters
        """
        built_count = len(built_list)
        total_count = len(languages)
        CliOutput.plain(f"Total: {built_count}/{total_count} adapters built")

        if built_count > 0:
            # Check for version mismatches
            mismatched = self.check_version_mismatches(languages, built_list)

            if mismatched:
                mismatched_str = ", ".join(mismatched)
                CliOutput.warning(
                    f"Version mismatch detected for: {mismatched_str}",
                )
                CliOutput.info(
                    "Consider running './dev-cli adapters download --install' "
                    "to update",
                )

        if not built_list:
            CliOutput.plain("To build adapters, run: ./dev-cli adapters build")
        elif missing_list:
            CliOutput.plain(f"Missing adapters: {', '.join(missing_list)}")

    def cleanup(self) -> None:
        """Cleanup service resources."""
        self._metadata_cache.clear()
