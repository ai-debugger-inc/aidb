"""Shared adapter downloader implementation.

This module provides the core adapter download and installation functionality that can
be used by both CLI and MCP interfaces.
"""

import platform
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from aidb.patterns import Obj
from aidb.session.adapter_registry import AdapterRegistry
from aidb_common.config import config as env_config
from aidb_common.io import safe_read_json, safe_read_yaml
from aidb_common.io.files import FileOperationError
from aidb_common.path import get_aidb_adapters_dir


def find_project_root() -> Path:
    """Find the project root directory containing versions.yaml.

    Returns
    -------
    Path
        Path to the project root directory

    Raises
    ------
    FileNotFoundError
        If versions.yaml cannot be found
    """
    current = Path(__file__)

    # Walk up the directory tree looking for versions.yaml
    for parent in current.parents:
        versions_file = parent / "versions.yaml"
        if versions_file.exists():
            return parent

    # Fallback: check some common locations relative to this file
    common_locations = [
        Path(
            __file__,
        ).parent.parent.parent.parent.parent,  # From src/aidb/adapters/management/
        Path(__file__).parent.parent.parent.parent,  # One level up
    ]

    for location in common_locations:
        versions_file = location / "versions.yaml"
        if versions_file.exists():
            return location

    msg = "Could not locate project root with versions.yaml"
    raise FileNotFoundError(msg)


def get_project_version() -> str:
    """Get the current project version from versions.yaml.

    Returns
    -------
    str
        Project version string
    """
    try:
        project_root = find_project_root()
        versions_file = project_root / "versions.yaml"

        versions = safe_read_yaml(versions_file)
        return versions.get("version", "latest")
    except (FileOperationError, FileNotFoundError):
        return "latest"


class AdapterDownloaderResult:
    """Result container for adapter download operations."""

    def __init__(
        self,
        success: bool,
        message: str,
        language: str | None = None,
        path: str | None = None,
        status: str | None = None,
        instructions: str | None = None,
        error: str | None = None,
        **kwargs,
    ):
        self.success = success
        self.message = message
        self.language = language
        self.path = path
        self.status = status or ("success" if success else "error")
        self.instructions = instructions
        self.error = error
        self.extra = kwargs

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        result = {
            "success": self.success,
            "status": self.status,
            "message": self.message,
        }

        if self.language:
            result["language"] = self.language
        if self.path:
            result["path"] = self.path
        if self.instructions:
            result["instructions"] = self.instructions
        if self.error:
            result["error"] = self.error

        result.update(self.extra)
        return result


class AdapterDownloader(Obj):
    """Shared adapter downloader implementation.

    This class provides the core functionality for downloading and installing debug
    adapters from GitHub releases. It can be used by both CLI and MCP interfaces.
    """

    GITHUB_REPO = "ai-debugger-inc/aidb"

    def __init__(self, ctx=None):
        """Initialize the adapter downloader.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging
        """
        super().__init__(ctx)
        self.registry = AdapterRegistry(ctx=ctx)
        self.install_dir = get_aidb_adapters_dir()
        self._project_root = None
        self._versions_cache = None

    @property
    def project_root(self) -> Path:
        """Get the project root directory (cached)."""
        if self._project_root is None:
            self._project_root = find_project_root()
        return self._project_root

    def get_versions_config(self) -> dict[str, Any]:
        """Get the versions configuration (cached).

        Returns
        -------
        dict
            Versions configuration from versions.yaml
        """
        if self._versions_cache is None:
            try:
                versions_file = self.project_root / "versions.yaml"
                self._versions_cache = safe_read_yaml(versions_file)
            except FileOperationError as e:
                self.ctx.warning(f"Failed to load versions.yaml: {e}")
                self._versions_cache = {}

        return self._versions_cache

    def download_adapter(
        self,
        language: str,
        version: str | None = None,
        force: bool = False,
    ) -> AdapterDownloaderResult:
        """Download and install a specific adapter.

        Parameters
        ----------
        language : str
            The language/adapter to download
        version : str, optional
            Specific version to download (default: project version)
        force : bool
            Force re-download even if already installed

        Returns
        -------
        AdapterDownloaderResult
            Result with status and installation details
        """
        try:
            # Get adapter name from registry
            adapter_class = self.registry.get_adapter_class(language)
            adapter_name = adapter_class.__name__.replace("Adapter", "").lower()

            # Check if already installed
            adapter_dir = self.install_dir / adapter_name
            if adapter_dir.exists() and not force:
                return AdapterDownloaderResult(
                    success=True,
                    status="already_installed",
                    message=f"{language} adapter already installed",
                    language=language,
                    path=str(adapter_dir),
                )

            # Get platform info
            system = platform.system().lower()
            machine = platform.machine().lower()

            from aidb.adapters.constants import get_arch_name, get_platform_name

            platform_name = get_platform_name(system)
            arch_name = get_arch_name(machine)

            # Determine if adapter is universal
            versions_config = self.get_versions_config()
            adapter_config = versions_config.get("adapters", {}).get(adapter_name, {})
            is_universal = adapter_config.get("universal", False)

            # Get version to download
            if version is None:
                # Try to get version from versions.yaml, fallback to project version
                adapter_version = adapter_config.get("version")
                if adapter_version:
                    version = str(adapter_version)
                else:
                    version = get_project_version()

            # Build download URL
            if is_universal:
                artifact_name = f"{adapter_name}-universal.tar.gz"
            else:
                artifact_name = f"{adapter_name}-{platform_name}-{arch_name}.tar.gz"

            download_url = (
                f"https://github.com/{self.GITHUB_REPO}/releases/download/"
                f"{version}/{artifact_name}"
            )

            self.ctx.info(f"Downloading {language} adapter from {download_url}")

            # Download to temp file
            with tempfile.NamedTemporaryFile(
                suffix=".tar.gz",
                delete=False,
            ) as tmp_file:
                try:
                    # Bandit: validate URL scheme before opening
                    from urllib.parse import urlparse

                    parsed = urlparse(download_url)
                    if parsed.scheme not in {"https"}:
                        msg = f"Disallowed URL scheme: {parsed.scheme}"
                        raise ValueError(msg)

                    import requests

                    resp = requests.get(download_url, timeout=30)
                    resp.raise_for_status()
                    tmp_file.write(resp.content)
                    tmp_path = tmp_file.name
                except HTTPError as e:
                    if e.code == 404:
                        return AdapterDownloaderResult(
                            success=False,
                            message=f"Adapter not found at {download_url}",
                            language=language,
                            instructions=self._get_manual_instructions(
                                language,
                                adapter_name,
                                platform_name,
                                arch_name,
                            ),
                        )
                    raise
                except URLError as e:
                    return AdapterDownloaderResult(
                        success=False,
                        message=f"Network error: {e}",
                        language=language,
                        instructions=self._get_offline_instructions(
                            language,
                            adapter_name,
                            platform_name,
                            arch_name,
                            version,
                        ),
                    )

            # Extract to install directory
            adapter_dir.mkdir(parents=True, exist_ok=True)

            with tarfile.open(tmp_path, "r:gz") as tar:
                # Bandit: safe extraction to prevent path traversal
                def _is_within_directory(directory: Path, target: Path) -> bool:
                    try:
                        directory_resolved = directory.resolve()
                        target_resolved = target.resolve()
                        return str(target_resolved).startswith(str(directory_resolved))
                    except Exception:
                        return False

                for member in tar.getmembers():
                    member_path = adapter_dir / member.name
                    if not _is_within_directory(adapter_dir, member_path):
                        msg = f"Unsafe path in tar archive: {member.name}"
                        raise ValueError(msg)
                for member in tar.getmembers():
                    tar.extract(member, path=adapter_dir)

            # Clean up temp file
            Path(tmp_path).unlink()

            # Validate extracted metadata
            try:
                self._validate_extracted_metadata(adapter_dir, language)
            except Exception as e:
                # If metadata is invalid, clean up and return error
                import shutil

                shutil.rmtree(adapter_dir, ignore_errors=True)
                return AdapterDownloaderResult(
                    success=False,
                    message=f"Invalid adapter metadata: {e}",
                    language=language,
                    error=str(e),
                )

            # Write version file
            version_file = adapter_dir / ".version"
            version_file.write_text(version if version != "latest" else "unknown")

            return AdapterDownloaderResult(
                success=True,
                message=f"Successfully installed {language} adapter",
                language=language,
                path=str(adapter_dir),
                version=version,
            )

        except Exception as e:
            self.ctx.error(f"Failed to download {language} adapter: {e}")
            return AdapterDownloaderResult(
                success=False,
                message=f"Failed to download adapter: {e}",
                language=language,
                error=str(e),
            )

    def download_all_adapters(
        self,
        force: bool = False,
    ) -> dict[str, AdapterDownloaderResult]:
        """Download all available adapters for the current platform.

        Parameters
        ----------
        force : bool
            Force re-download even if already installed

        Returns
        -------
        dict[str, AdapterDownloaderResult]
            Results for each adapter by language
        """
        results = {}

        # Get all registered adapters dynamically
        supported_languages = self.registry.get_languages()
        for language in supported_languages:
            try:
                self.registry.get_adapter_class(language)
                result = self.download_adapter(language, force=force)
                results[language] = result
            except Exception as e:
                self.ctx.warning(f"Skipping {language}: {e}")
                results[language] = AdapterDownloaderResult(
                    success=False,
                    message=f"Adapter not registered: {e}",
                    language=language,
                    error=str(e),
                )

        return results

    def list_installed_adapters(self) -> dict[str, dict[str, Any]]:
        """List all installed adapters.

        Returns
        -------
        dict[str, dict[str, Any]]
            Information about installed adapters by adapter name
        """
        installed: dict[str, dict[str, Any]] = {}

        if not self.install_dir.exists():
            return installed

        for adapter_dir in self.install_dir.iterdir():
            if adapter_dir.is_dir():
                version_file = adapter_dir / ".version"
                version = "unknown"
                if version_file.exists():
                    version = version_file.read_text().strip()

                installed[adapter_dir.name] = {
                    "path": str(adapter_dir),
                    "version": version,
                    "exists": True,
                }

        return installed

    def _validate_extracted_metadata(self, adapter_dir: Path, language: str) -> None:
        """Validate extracted adapter metadata.

        Parameters
        ----------
        adapter_dir : Path
            Directory where adapter was extracted
        language : str
            Language identifier for the adapter

        Raises
        ------
        ValueError
            If metadata is missing or invalid
        """
        # Check if metadata.json exists
        metadata_file = adapter_dir / "metadata.json"
        if not metadata_file.exists():
            # Look for extracted subdirectory that might contain metadata
            subdirs = [d for d in adapter_dir.iterdir() if d.is_dir()]
            if subdirs:
                # Check first subdirectory for metadata
                metadata_file = subdirs[0] / "metadata.json"
                if metadata_file.exists():
                    # Move contents up one level
                    for item in subdirs[0].iterdir():
                        if item.is_file():
                            item.rename(adapter_dir / item.name)
                        elif item.is_dir():
                            import shutil

                            shutil.move(str(item), str(adapter_dir / item.name))
                    subdirs[0].rmdir()
                    metadata_file = adapter_dir / "metadata.json"

            if not metadata_file.exists():
                msg = "metadata.json file not found in adapter archive"
                raise ValueError(msg)

        # Load and validate metadata content
        try:
            metadata = safe_read_json(metadata_file)
        except FileOperationError as e:
            msg = f"Invalid JSON in metadata.json: {e}"
            raise ValueError(msg) from e

        # Check required fields
        required_fields = [
            "adapter_name",
            "adapter_version",
            "aidb_version",
            "platform",
            "arch",
            "binary_identifier",
            "repo",
        ]

        missing_fields = [field for field in required_fields if field not in metadata]
        if missing_fields:
            msg = f"Missing required metadata fields: {', '.join(missing_fields)}"
            raise ValueError(msg)

        # Validate adapter name matches expected language
        if metadata.get("adapter_name") != language:
            self.ctx.warning(
                f"Adapter name mismatch: metadata has '{metadata.get('adapter_name')}', "
                f"expected '{language}'",
            )

        # Log metadata for debugging
        self.ctx.debug(f"Validated metadata for {language}: {metadata}")

    def _get_manual_instructions(
        self,
        language: str,
        adapter_name: str,
        platform_name: str,
        arch_name: str,
    ) -> str:
        """Get manual download instructions.

        Parameters
        ----------
        language : str
            Language identifier
        adapter_name : str
            Adapter directory name
        platform_name : str
            Platform name
        arch_name : str
            Architecture name

        Returns
        -------
        str
            Manual download instructions
        """
        env_var = env_config.ADAPTER_PATH_TEMPLATE.format(language.upper())
        return f"""
Manual download instructions for {language} adapter:

1. Visit: https://github.com/{self.GITHUB_REPO}/releases/latest
2. Download: {adapter_name}-{platform_name}-{arch_name}.tar.gz
3. Extract to: {self.install_dir / adapter_name}/
4. Or install in a custom location and set the
   {env_var} environment variable

Example commands:
  mkdir -p ~/.aidb/adapters/{adapter_name}
  tar -xzf {adapter_name}-{platform_name}-{arch_name}.tar.gz \\
    -C ~/.aidb/adapters/{adapter_name}/
"""

    def _get_offline_instructions(
        self,
        language: str,
        adapter_name: str,
        platform_name: str,
        arch_name: str,
        version: str,
    ) -> str:
        """Get offline installation instructions.

        Parameters
        ----------
        language : str
            Language identifier
        adapter_name : str
            Adapter directory name
        platform_name : str
            Platform name
        arch_name : str
            Architecture name
        version : str
            Version to download

        Returns
        -------
        str
            Offline installation instructions
        """
        base_url = f"https://github.com/{self.GITHUB_REPO}/releases"
        if version == "latest":
            url = f"{base_url}/latest"
        else:
            url = f"{base_url}/tag/{version}"

        return f"""
Offline installation instructions for {language} adapter:

You appear to be offline or unable to reach GitHub.

To install manually:
1. On another machine with internet, download:
   {url}
   File: {adapter_name}-{platform_name}-{arch_name}.tar.gz

2. Transfer the file to this machine

3. Extract it:
   mkdir -p ~/.aidb/adapters/{adapter_name}
   tar -xzf {adapter_name}-{platform_name}-{arch_name}.tar.gz \\
     -C ~/.aidb/adapters/{adapter_name}/

The adapter will then be available for use.
"""
