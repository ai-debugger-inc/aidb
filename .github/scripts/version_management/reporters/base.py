"""Abstract base class for update reporters."""

from abc import ABC, abstractmethod
from typing import Any


class Reporter(ABC):
    """Abstract base class for formatting update reports."""

    @abstractmethod
    def generate_report(self, all_updates: dict[str, Any]) -> str:
        """Generate update report.

        Parameters
        ----------
        all_updates : dict[str, Any]
            All updates found

        Returns
        -------
        str
            Formatted report
        """

    @abstractmethod
    def output(
        self, all_updates: dict[str, Any], has_updates: bool, auto_merge: bool, report: str,
    ) -> None:
        """Output report in specific format.

        Parameters
        ----------
        all_updates : dict[str, Any]
            All updates found
        has_updates : bool
            Whether any updates were found
        auto_merge : bool
            Whether updates can be auto-merged
        report : str
            Generated report text
        """
