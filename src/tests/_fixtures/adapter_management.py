"""Test fixtures for adapter management and isolation.

Provides utilities for tests that need to manipulate adapters, including:
- Backing up adapters before tests
- Removing adapters to test absence scenarios
- Restoring adapters after tests
- Verifying adapter state
"""

__all__ = [
    # Classes
    "AdapterManager",
    # Fixtures
    "adapter_manager",
    "isolated_adapters",
    "no_adapters",
    "single_adapter",
    # Functions
    "copy_adapter",
    "ensure_test_adapters",
]

import shutil
from collections.abc import Generator
from pathlib import Path
from typing import Optional

import pytest

from aidb_logging import get_test_logger

logger = get_test_logger(__name__)


class AdapterManager:
    """Manages adapter state for testing scenarios."""

    def __init__(
        self,
        primary_path: Path = Path("/root/.aidb/adapters"),
        backup_path: Path | None = None,
    ):
        """Initialize adapter manager.

        Parameters
        ----------
        primary_path : Path
            Primary adapter location (can be modified by tests)
        backup_path : Path | None
            Backup adapter location (read-only pristine copy).
            Defaults to system temp directory if not specified.
        """
        import tempfile

        self.primary_path = primary_path
        self.backup_path = (
            backup_path or Path(tempfile.gettempdir()) / ".aidb" / "adapters"
        )
        self._original_state: dict[str, bool] = {}

    def backup_state(self) -> dict[str, bool]:
        """Record current adapter state.

        Returns
        -------
        Dict[str, bool]
            Current state of adapters (language -> exists)
        """
        state = {}

        # Check standard adapter locations
        adapters = {
            "javascript": self.primary_path / "javascript" / "dapDebugServer.js",
            "java": self.primary_path / "java" / "java-debug.jar",
            "python": self.primary_path / "python",  # Python uses debugpy
        }

        for language, path in adapters.items():
            state[language] = path.exists()

        self._original_state = state
        logger.debug("Backed up adapter state: %s", state)
        return state

    def remove_adapters(self, languages: list[str] | None = None) -> None:
        """Remove adapters to test absence scenarios.

        Parameters
        ----------
        languages : List[str], optional
            Specific languages to remove. If None, removes all.
        """
        if languages is None:
            languages = ["javascript", "java", "python"]

        for language in languages:
            lang_dir = self.primary_path / language
            if lang_dir.exists():
                shutil.rmtree(lang_dir)
                logger.info("Removed %s adapter from %s", language, lang_dir)

    def restore_adapters(self, languages: list[str] | None = None) -> None:
        """Restore adapters from backup.

        Parameters
        ----------
        languages : List[str], optional
            Specific languages to restore. If None, restores all.
        """
        if languages is None:
            languages = ["javascript", "java", "python"]

        for language in languages:
            backup_dir = self.backup_path / language
            primary_dir = self.primary_path / language

            if backup_dir.exists():
                # Remove existing if present
                if primary_dir.exists():
                    shutil.rmtree(primary_dir)

                # Copy from backup
                shutil.copytree(backup_dir, primary_dir)
                logger.info("Restored %s adapter from backup", language)
            else:
                logger.warning("No backup found for %s adapter", language)

    def restore_original_state(self) -> None:
        """Restore adapters to their original state before the test."""
        for language, was_present in self._original_state.items():
            lang_dir = self.primary_path / language

            if was_present and not lang_dir.exists():
                # Was present, now missing - restore it
                self.restore_adapters([language])
            elif not was_present and lang_dir.exists():
                # Wasn't present, now exists - remove it
                self.remove_adapters([language])

    def verify_adapters_present(self, languages: list[str] | None = None) -> bool:
        """Verify that adapters are present.

        Parameters
        ----------
        languages : List[str], optional
            Languages to check. If None, checks all.

        Returns
        -------
        bool
            True if all specified adapters are present
        """
        if languages is None:
            languages = ["javascript", "java", "python"]

        for language in languages:
            lang_dir = self.primary_path / language
            if not lang_dir.exists():
                return False
        return True

    def verify_adapters_absent(self, languages: list[str] | None = None) -> bool:
        """Verify that adapters are absent.

        Parameters
        ----------
        languages : List[str], optional
            Languages to check. If None, checks all.

        Returns
        -------
        bool
            True if all specified adapters are absent
        """
        if languages is None:
            languages = ["javascript", "java", "python"]

        for language in languages:
            lang_dir = self.primary_path / language
            if lang_dir.exists():
                return False
        return True


@pytest.fixture
def adapter_manager() -> AdapterManager:
    """Provide adapter manager for tests.

    Returns
    -------
    AdapterManager
        Adapter management utility
    """
    return AdapterManager()


@pytest.fixture
def isolated_adapters(
    adapter_manager: AdapterManager,
) -> Generator[AdapterManager, None, None]:
    """Provide isolated adapter environment that auto-restores.

    This fixture:
    1. Backs up current adapter state
    2. Yields the adapter manager for test use
    3. Restores original state after test

    Yields
    ------
    AdapterManager
        Adapter manager with backup/restore capabilities
    """
    # Backup current state
    adapter_manager.backup_state()

    try:
        yield adapter_manager
    finally:
        # Always restore original state
        adapter_manager.restore_original_state()


@pytest.fixture
def no_adapters(adapter_manager: AdapterManager) -> Generator[None, None, None]:
    """Provide environment with no adapters for testing absence scenarios.

    This fixture:
    1. Backs up current adapters
    2. Removes all adapters
    3. Restores adapters after test
    """
    # Backup and remove
    adapter_manager.backup_state()
    adapter_manager.remove_adapters()

    try:
        yield
    finally:
        # Restore original state
        adapter_manager.restore_original_state()


@pytest.fixture
def single_adapter(
    adapter_manager: AdapterManager,
    language: str = "python",
) -> Generator[str, None, None]:
    """Provide environment with only a single adapter.

    Parameters
    ----------
    language : str
        The language adapter to keep (default: python)

    Yields
    ------
    str
        The language that has an adapter
    """
    # Backup state
    adapter_manager.backup_state()

    # Remove all adapters
    adapter_manager.remove_adapters()

    # Restore only the specified one
    adapter_manager.restore_adapters([language])

    try:
        yield language
    finally:
        # Restore original state
        adapter_manager.restore_original_state()


def copy_adapter(
    source_lang: str,
    dest_lang: str,
    adapter_manager: AdapterManager | None = None,
) -> None:
    """Copy adapter from one language to another (for testing).

    Parameters
    ----------
    source_lang : str
        Source language adapter to copy
    dest_lang : str
        Destination language location
    adapter_manager : AdapterManager, optional
        Adapter manager to use (creates new if not provided)
    """
    if adapter_manager is None:
        adapter_manager = AdapterManager()

    source = adapter_manager.backup_path / source_lang
    dest = adapter_manager.primary_path / dest_lang

    if source.exists():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        logger.info("Copied %s adapter to %s", source_lang, dest_lang)


def ensure_test_adapters() -> bool:
    """Ensure adapters are available for testing.

    Returns
    -------
    bool
        True if adapters are available, False otherwise
    """
    manager = AdapterManager()

    # Check if we have backups
    backup_exists = any(
        (manager.backup_path / lang).exists()
        for lang in ["javascript", "java", "python"]
    )

    if not backup_exists:
        logger.error("No adapter backups found in /tmp/.aidb/adapters")
        logger.error("Ensure adapters are built and mounted to container")
        return False

    # If primary adapters are missing, restore from backup
    if not manager.verify_adapters_present():
        logger.info("Primary adapters missing, restoring from backup")
        manager.restore_adapters()

    return manager.verify_adapters_present()
