"""Service for discovering and checking adapter status."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from aidb.session.adapter_registry import AdapterRegistry
from aidb_cli.core.constants import Icons
from aidb_cli.core.paths import CachePaths
from aidb_cli.core.utils import CliOutput
from aidb_cli.managers.base.service import BaseService
from aidb_common.config import VersionManager
from aidb_logging import get_cli_logger

if TYPE_CHECKING:
    from aidb_cli.services import CommandExecutor

logger = get_cli_logger(__name__)


class AdapterDiscoveryService(BaseService):
    """Service for discovering and checking adapter status.

    This service handles:
    - Finding adapter source directories
    - Checking adapter build status
    - Getting adapter information
    """

    # Binary files that indicate a built adapter (matches Docker healthcheck paths)
    # See: src/tests/_docker/docker-compose.base.yaml healthcheck
    ADAPTER_BINARY_FILES: dict[str, str] = {
        "python": "debugpy/__init__.py",
        "javascript": "src/dapDebugServer.js",
        "java": "java-debug.jar",
    }

    def __init__(
        self,
        repo_root: Path,
        command_executor: Optional["CommandExecutor"] = None,
    ) -> None:
        """Initialize the adapter discovery service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        command_executor : CommandExecutor | None, optional
            Command executor instance for running commands
        """
        self._adapter_registry: AdapterRegistry | None = None
        self._cache_dir: Path | None = None
        super().__init__(repo_root, command_executor)

    def _initialize_service(self) -> None:
        """Initialize service-specific resources."""
        self._cache_dir = CachePaths.repo_cache(self.repo_root)

    @property
    def registry(self) -> AdapterRegistry | None:
        """Get the adapter registry.

        Returns
        -------
        AdapterRegistry | None
            Adapter registry if initialized
        """
        if self._adapter_registry is None:
            try:
                self._adapter_registry = AdapterRegistry()
            except Exception as e:
                self.log_error("Failed to initialize adapter registry: %s", str(e))
        return self._adapter_registry

    def get_supported_languages(self) -> list[str]:
        """Get list of supported adapter languages.

        Returns
        -------
        list[str]
            List of supported language names
        """
        if not self.registry:
            return []

        try:
            return self.registry.get_languages()
        except (AttributeError, RuntimeError) as e:
            self.log_error("Failed to get supported languages: %s", str(e))
            return []

    def find_adapter_source(
        self,
        language: str,
        check_built: bool = False,
        verbose: bool = False,
    ) -> Path | None:
        """Find the source directory for a specific adapter.

        Parameters
        ----------
        language : str
            Language name (e.g., 'python', 'javascript')
        check_built : bool, optional
            Whether to check if adapter is already built
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        Path | None
            Path to adapter source directory or None if not found
        """
        cache_path = self._cache_dir / language if self._cache_dir else None
        if cache_path and cache_path.exists():
            if verbose:
                CliOutput.info(
                    f"{Icons.SUCCESS} Found {language} adapter in cache: {cache_path}",
                )
            return cache_path

        repo_adapter_path = (
            self.repo_root / "src" / "aidb" / "adapters" / "lang" / language
        )
        if repo_adapter_path.exists():
            if check_built:
                adapter_file = repo_adapter_path / f"{language}.py"
                if not adapter_file.exists():
                    if verbose:
                        msg = (
                            f"{Icons.WARNING} {language} adapter source found "
                            f"but not built: {repo_adapter_path}"
                        )
                        CliOutput.warning(msg)
                    return None

            if verbose:
                msg = (
                    f"{Icons.SUCCESS} Found {language} adapter in repo: "
                    f"{repo_adapter_path}"
                )
                CliOutput.info(msg)
            return repo_adapter_path

        if verbose:
            CliOutput.warning(f"{language} adapter not found")
        return None

    def find_all_adapters(self, verbose: bool = False) -> dict[str, Path | None]:
        """Find all available adapters and their locations.

        Parameters
        ----------
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        dict[str, Path | None]
            Mapping of language to adapter path (or None if not found)
        """
        adapters = {}
        languages = self.get_supported_languages()

        if verbose:
            from aidb_cli.core.formatting import HeadingFormatter

            HeadingFormatter.discovery("Searching for adapters...")

        for lang in languages:
            adapter_path = self.find_adapter_source(lang, verbose=verbose)
            adapters[lang] = adapter_path

        if verbose:
            found = [lang for lang, p in adapters.items() if p is not None]
            missing = [lang for lang, p in adapters.items() if p is None]

            if found:
                CliOutput.success(
                    f"{Icons.SUCCESS} Found adapters: {', '.join(found)}",
                )
            if missing:
                CliOutput.warning(
                    f"{Icons.WARNING} Missing adapters: {', '.join(missing)}",
                )

        return adapters

    def check_adapters_built(
        self,
        languages: list[str] | None = None,
        verbose: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Check which adapters are built and which need building.

        Parameters
        ----------
        languages : list[str] | None, optional
            Specific languages to check, or None for all
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        tuple[list[str], list[str]]
            Tuple of (built_adapters, missing_adapters)
        """
        if languages is None:
            languages = self.get_supported_languages()

        built = []
        missing = []

        for lang in languages:
            adapter_path = self.find_adapter_source(
                lang,
                check_built=True,
                verbose=False,
            )
            if adapter_path:
                built.append(lang)
            else:
                missing.append(lang)

        if verbose:
            if built:
                CliOutput.success(f"Built adapters: {', '.join(built)}")
            if missing:
                CliOutput.warning(
                    f"{Icons.WARNING} Missing adapters: {', '.join(missing)}",
                )

        return built, missing

    def check_adapters_in_cache(
        self,
        languages: list[str] | None = None,
        verbose: bool = False,
    ) -> tuple[list[str], list[str]]:
        """Check for built adapters in repo cache (.cache/adapters/).

        Unlike check_adapters_built(), this does NOT fall back to source paths.
        Use for Docker suites that mount .cache/adapters/ into containers.

        Parameters
        ----------
        languages : list[str] | None, optional
            Specific languages to check, or None for all
        verbose : bool, optional
            Whether to show verbose output

        Returns
        -------
        tuple[list[str], list[str]]
            Tuple of (built_adapters, missing_adapters)
        """
        if languages is None:
            languages = self.get_supported_languages()

        if not self._cache_dir:
            return [], list(languages)

        built = []
        missing = []

        for lang in languages:
            cache_path = self._cache_dir / lang
            binary_file = self.ADAPTER_BINARY_FILES.get(lang)

            if binary_file and (cache_path / binary_file).exists():
                built.append(lang)
            else:
                missing.append(lang)

        if verbose:
            if built:
                CliOutput.success(f"Adapters in cache: {', '.join(built)}")
            if missing:
                CliOutput.warning(f"Missing from cache: {', '.join(missing)}")

        return built, missing

    def get_adapter_info(self, language: str) -> dict[str, str]:
        """Get information about a specific adapter.

        Parameters
        ----------
        language : str
            Language name

        Returns
        -------
        dict[str, str]
            Adapter information including path, version, etc.
        """
        info = {
            "language": language,
            "status": "unknown",
            "path": "",
            "version": "",
        }

        adapter_path = self.find_adapter_source(
            language,
            check_built=True,
            verbose=False,
        )

        if adapter_path:
            info["status"] = "built"
            info["path"] = str(adapter_path)

            try:
                version_manager = VersionManager()
                info["version"] = version_manager.package_version
            except Exception:
                info["version"] = "unknown"
        else:
            source_path = self.find_adapter_source(
                language,
                check_built=False,
                verbose=False,
            )
            if source_path:
                info["status"] = "source_only"
                info["path"] = str(source_path)
            else:
                info["status"] = "missing"

        return info

    def cleanup(self) -> None:
        """Cleanup service resources."""
