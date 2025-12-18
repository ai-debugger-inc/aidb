"""Shared adapter downloader implementation.

This module provides the core adapter download and installation functionality that can
be used by both CLI and MCP interfaces.
"""

import json
import platform
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from aidb.common.constants import DOWNLOAD_TIMEOUT_S
from aidb.patterns import Obj
from aidb.session.adapter_registry import AdapterRegistry
from aidb_common.config import config as env_config
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_common.path import get_aidb_adapters_dir

from .result import AdapterDownloaderResult
from .version import find_project_root, get_project_version


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
            Versions configuration from versions.json
        """
        if self._versions_cache is None:
            try:
                versions_file = self.project_root / "versions.json"
                self._versions_cache = safe_read_json(versions_file)
            except FileOperationError as e:
                self.ctx.warning(f"Failed to load versions.json: {e}")
                self._versions_cache = {}

        return self._versions_cache

    def _fetch_release_manifest(self, release_tag: str) -> dict[str, Any] | None:
        """Fetch the manifest.json from a GitHub release.

        Parameters
        ----------
        release_tag : str
            The release tag (e.g., "0.0.5")

        Returns
        -------
        dict or None
            Manifest data if successfully fetched, None otherwise
        """
        manifest_url = (
            f"https://github.com/{self.GITHUB_REPO}/releases/download/"
            f"{release_tag}/manifest.json"
        )

        try:
            from urllib.parse import urlparse

            parsed = urlparse(manifest_url)
            if parsed.scheme not in {"https"}:
                return None

            with urlopen(manifest_url, timeout=DOWNLOAD_TIMEOUT_S) as resp:  # noqa: S310  # nosec B310
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError) as e:
            self.ctx.debug(f"Failed to fetch manifest from {manifest_url}: {e}")
            return None

    def _get_platform_info(self) -> tuple[str, str]:
        """Get platform and architecture names for current system.

        Returns
        -------
        tuple[str, str]
            (platform_name, arch_name)
        """
        from aidb.adapters.constants import get_arch_name, get_platform_name

        system = platform.system().lower()
        machine = platform.machine().lower()
        return get_platform_name(system), get_arch_name(machine)

    def _resolve_adapter_version(
        self,
        adapter_name: str,
        release_tag: str,
        adapter_config: dict[str, Any],
    ) -> str | None:
        """Resolve adapter version from manifest or local config.

        Parameters
        ----------
        adapter_name : str
            Name of the adapter
        release_tag : str
            Release tag to fetch manifest from
        adapter_config : dict
            Local adapter configuration from versions.json

        Returns
        -------
        str or None
            Adapter version if found
        """
        # Try manifest first (for released versions)
        manifest = self._fetch_release_manifest(release_tag)
        if manifest:
            adapter_info = manifest.get("adapters", {}).get(adapter_name, {})
            version = adapter_info.get("version")
            if version:
                self.ctx.debug(f"Got adapter version {version} from release manifest")
                return version

        # Fall back to local versions.json
        version = adapter_config.get("version")
        if version:
            self.ctx.debug(f"Using local versions.json adapter version: {version}")
        return version

    def _build_artifact_url(
        self,
        adapter_name: str,
        adapter_version: str | None,
        release_tag: str,
        platform_name: str,
        arch_name: str,
        is_universal: bool,
    ) -> tuple[str, str]:
        """Build artifact name and download URL.

        Parameters
        ----------
        adapter_name : str
            Name of the adapter
        adapter_version : str or None
            Version to include in artifact name
        release_tag : str
            Release tag for download URL
        platform_name : str
            Platform name (darwin, linux, windows)
        arch_name : str
            Architecture name (arm64, x64)
        is_universal : bool
            Whether this is a universal (platform-agnostic) adapter

        Returns
        -------
        tuple[str, str]
            (artifact_name, download_url)
        """
        if is_universal:
            if adapter_version:
                artifact_name = f"{adapter_name}-{adapter_version}-universal.tar.gz"
            else:
                artifact_name = f"{adapter_name}-universal.tar.gz"
        else:
            if adapter_version:
                artifact_name = (
                    f"{adapter_name}-{adapter_version}-"
                    f"{platform_name}-{arch_name}.tar.gz"
                )
            else:
                artifact_name = f"{adapter_name}-{platform_name}-{arch_name}.tar.gz"

        download_url = (
            f"https://github.com/{self.GITHUB_REPO}/releases/download/"
            f"{release_tag}/{artifact_name}"
        )
        return artifact_name, download_url

    def _download_to_temp(self, download_url: str) -> str:
        """Download URL content to a temporary file.

        Parameters
        ----------
        download_url : str
            URL to download from

        Returns
        -------
        str
            Path to temporary file

        Raises
        ------
        HTTPError
            If download fails with HTTP error
        URLError
            If network error occurs
        ValueError
            If URL scheme is not HTTPS
        """
        from urllib.parse import urlparse

        parsed = urlparse(download_url)
        if parsed.scheme not in {"https"}:
            msg = f"Disallowed URL scheme: {parsed.scheme}"
            raise ValueError(msg)

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_file:
            with urlopen(download_url, timeout=DOWNLOAD_TIMEOUT_S) as resp:  # noqa: S310  # nosec B310
                tmp_file.write(resp.read())
            return tmp_file.name

    def _safe_extract_tarball(self, tar_path: str, target_dir: Path) -> None:
        """Safely extract tarball with path traversal protection.

        Parameters
        ----------
        tar_path : str
            Path to the tarball file
        target_dir : Path
            Directory to extract to

        Raises
        ------
        ValueError
            If archive contains unsafe paths
        """

        def is_within_directory(directory: Path, target: Path) -> bool:
            try:
                return str(target.resolve()).startswith(str(directory.resolve()))
            except Exception:
                return False

        target_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path, "r:gz") as tar:
            # Validate all paths first
            for member in tar.getmembers():
                member_path = target_dir / member.name
                if not is_within_directory(target_dir, member_path):
                    msg = f"Unsafe path in tar archive: {member.name}"
                    raise ValueError(msg)

            # Extract after validation
            for member in tar.getmembers():
                tar.extract(member, path=target_dir)

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
            # Resolve adapter info from registry
            adapter_class = self.registry.get_adapter_class(language)
            adapter_name = adapter_class.__name__.replace("Adapter", "").lower()
            adapter_dir = self.install_dir / adapter_name

            # Check if already installed
            if adapter_dir.exists() and not force:
                return AdapterDownloaderResult(
                    success=True,
                    status="already_installed",
                    message=f"{language} adapter already installed",
                    language=language,
                    path=str(adapter_dir),
                )

            # Get platform and version info
            platform_name, arch_name = self._get_platform_info()
            versions_config = self.get_versions_config()
            adapter_config = versions_config.get("adapters", {}).get(adapter_name, {})
            is_universal = adapter_config.get("universal", False)
            release_tag = get_project_version() if version is None else version

            # Resolve adapter version from manifest or local config
            adapter_version = self._resolve_adapter_version(
                adapter_name,
                release_tag,
                adapter_config,
            )

            # Build download URL
            _, download_url = self._build_artifact_url(
                adapter_name,
                adapter_version,
                release_tag,
                platform_name,
                arch_name,
                is_universal,
            )

            self.ctx.info(f"Downloading {language} adapter from {download_url}")

            # Download to temp file
            try:
                tmp_path = self._download_to_temp(download_url)
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

            # Extract and clean up temp file
            try:
                self._safe_extract_tarball(tmp_path, adapter_dir)
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            # Validate extracted metadata
            try:
                self._validate_extracted_metadata(adapter_dir, language)
            except Exception as e:
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
            version_to_write = adapter_version or release_tag
            version_file.write_text(
                version_to_write if version_to_write != "latest" else "unknown",
            )

            return AdapterDownloaderResult(
                success=True,
                message=f"Successfully installed {language} adapter",
                language=language,
                path=str(adapter_dir),
                version=adapter_version or release_tag,
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

    def _flatten_nested_extraction(self, adapter_dir: Path) -> None:
        """Move contents from nested subdirectory up to adapter_dir if needed.

        Some tarballs extract with an extra directory level. This flattens
        the structure by moving contents up one level.

        Parameters
        ----------
        adapter_dir : Path
            Directory where adapter was extracted
        """
        import shutil

        subdirs = [d for d in adapter_dir.iterdir() if d.is_dir()]
        if not subdirs:
            return

        # Check first subdirectory for metadata.json
        subdir = subdirs[0]
        if not (subdir / "metadata.json").exists():
            return

        # Move contents up one level
        for item in subdir.iterdir():
            target = adapter_dir / item.name
            if item.is_file():
                item.rename(target)
            elif item.is_dir():
                shutil.move(str(item), str(target))
        subdir.rmdir()

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
        metadata_file = adapter_dir / "metadata.json"

        # Handle nested extraction structure
        if not metadata_file.exists():
            self._flatten_nested_extraction(adapter_dir)

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
            adapter_name = metadata.get("adapter_name")
            self.ctx.warning(
                f"Adapter name mismatch: metadata has '{adapter_name}', "
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
        version: str | None,
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
        version : str or None
            Version to download

        Returns
        -------
        str
            Offline installation instructions
        """
        base_url = f"https://github.com/{self.GITHUB_REPO}/releases"
        if version is None or version == "latest":
            url = f"{base_url}/latest"
        else:
            url = f"{base_url}/tag/{version}"

        return f"""
Offline installation instructions for {language} adapter:

You appear to be offline or unable to reach GitHub.

To install manually:
1. Visit the AIDB releases page:
   {url}

2. Download: {adapter_name}-{platform_name}-{arch_name}.tar.gz

3. Transfer the file to this machine

4. Extract it:
   mkdir -p ~/.aidb/adapters/{adapter_name}
   tar -xzf {adapter_name}-{platform_name}-{arch_name}.tar.gz \\
     -C ~/.aidb/adapters/{adapter_name}/

The adapter will then be available for use.
"""
