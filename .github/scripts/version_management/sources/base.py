"""Abstract base class for version sources."""

from abc import ABC, abstractmethod


class VersionSource(ABC):
    """Abstract base class for fetching version information from external sources."""

    @abstractmethod
    def fetch_latest_version(self, identifier: str) -> str | None:
        """Fetch latest version from source.

        Parameters
        ----------
        identifier : str
            Package/project identifier (format depends on source)

        Returns
        -------
        str | None
            Latest version string, or None if not found/error
        """

    def _handle_error(self, identifier: str, error: Exception) -> None:
        """Handle errors during version fetching.

        Parameters
        ----------
        identifier : str
            Package/project identifier
        error : Exception
            Exception that occurred
        """
        print(f"Error checking {identifier}: {error}")
