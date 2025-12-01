"""High-level orchestration for version update checking."""

import logging
from pathlib import Path
from typing import Any

from .checkers.adapters import AdapterChecker
from .checkers.infrastructure import InfrastructureChecker
from .checkers.packages import PackageChecker
from .config.loader import ConfigLoader
from .validators.debugpy_sync import DebugpySyncValidator

logger = logging.getLogger(__name__)


class SectionType:
    """Section type constants for filtering updates."""

    INFRASTRUCTURE = "infrastructure"
    ADAPTERS = "adapters"
    ALL = "all"


class VersionUpdateOrchestrator:
    """Orchestrates version checking across all sources."""

    def __init__(self, config_path: Path, target_section: str = SectionType.ALL):
        """Initialize orchestrator.

        Parameters
        ----------
        config_path : Path
            Path to versions.yaml configuration file
        target_section : str
            Section to update (infrastructure, adapters, or all)
        """
        self.config_path = config_path
        self.target_section = target_section
        self.config = ConfigLoader.load(config_path)

        self.infrastructure_checker = InfrastructureChecker(self.config)
        self.adapter_checker = AdapterChecker(self.config)
        self.package_checker = PackageChecker(self.config)
        self.debugpy_validator = DebugpySyncValidator(config_path)

    def check_all_updates(self) -> dict[str, Any]:
        """Check all configured sections for updates.

        Returns
        -------
        dict[str, Any]
            All updates found across all sections
        """
        all_updates = {}

        if self.target_section in [SectionType.INFRASTRUCTURE, SectionType.ALL]:
            try:
                infrastructure_updates = self.infrastructure_checker.check_updates()
                if infrastructure_updates:
                    all_updates["infrastructure"] = infrastructure_updates
            except Exception as e:
                logger.warning("Infrastructure checker failed: %s", e)

        if self.target_section in [SectionType.ADAPTERS, SectionType.ALL]:
            try:
                adapter_updates = self.adapter_checker.check_updates()
                if adapter_updates:
                    all_updates["adapters"] = adapter_updates
            except Exception as e:
                logger.warning("Adapter checker failed: %s", e)

        try:
            pypi_updates = self.package_checker.check_pypi_updates()
            if pypi_updates:
                all_updates["global_packages_pip"] = pypi_updates
        except Exception as e:
            logger.warning("PyPI checker failed: %s", e)

        try:
            npm_updates = self.package_checker.check_npm_updates()
            if npm_updates:
                all_updates["global_packages_npm"] = npm_updates
        except Exception as e:
            logger.warning("npm checker failed: %s", e)

        try:
            debugpy_validation = self.debugpy_validator.validate(self.config)
            if not debugpy_validation["valid"] or debugpy_validation.get("warnings"):
                all_updates["debugpy_sync"] = debugpy_validation
        except Exception as e:
            logger.warning("Debugpy validation failed: %s", e)

        return all_updates
