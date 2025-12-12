"""Adapter binary management.

This module provides a streamlined approach to locating debug adapter binaries, checking
standard locations and environment variables.
"""

from pathlib import Path

from aidb.common.errors import AdapterNotFoundError
from aidb.patterns import Obj
from aidb.session.adapter_registry import AdapterRegistry
from aidb_common.config import config as env_config
from aidb_common.io import safe_read_json
from aidb_common.io.files import FileOperationError
from aidb_common.path import get_aidb_adapters_dir


class AdapterBinaryLocator(Obj):
    """Simplified adapter binary locator using registry for naming consistency."""

    def __init__(self, ctx=None):
        """Initialize the binary locator.

        Parameters
        ----------
        ctx : IContext, optional
            Context for logging
        """
        super().__init__(ctx)
        self.registry = AdapterRegistry(ctx=ctx)
        self._metadata_cache = {}  # Cache for loaded metadata

    def locate(self, language: str) -> Path:
        """Locate a debug adapter binary for the given language.

        Search order:
        1. Environment variable: AIDB_{LANGUAGE}_ADAPTER_PATH
        2. User home directory: ~/.aidb/adapters/{adapter_name}/
        3. Raise AdapterNotFoundError with instructions

        Parameters
        ----------
        language : str
            The language/adapter to locate

        Returns
        -------
        Path
            Path to the debug adapter

        Raises
        ------
        AdapterNotFoundError
            If the adapter cannot be found
        """
        searched_locations = []

        # Get adapter class to extract name
        try:
            adapter_class = self.registry.get_adapter_class(language)
            # Extract adapter name: JavaScriptAdapter -> javascript
            adapter_name = adapter_class.__name__.replace("Adapter", "").lower()
        except Exception as e:
            self.ctx.debug(f"Failed to get adapter class for {language}: {e}")
            adapter_name = language.lower()  # Fallback to language name

        # Get binary identifier from adapter config for flexible path resolution
        try:
            config = self.registry.get_adapter_config(language)
            binary_identifier = getattr(config, "binary_identifier", "")
        except Exception as e:
            self.ctx.debug(f"Failed to get adapter config for {language}: {e}")
            binary_identifier = ""

        # 1. Check environment variable using centralized config
        env_path = env_config.get_binary_override(language)
        env_var = env_config.ADAPTER_PATH_TEMPLATE.format(language.upper())
        if env_path:
            resolved_path = self._resolve_adapter_path(env_path, binary_identifier)
            if resolved_path and resolved_path.exists():
                self.ctx.debug(
                    f"Using {language} adapter from {env_var}: {resolved_path}",
                )
                return resolved_path
            searched_locations.append(f"Environment: {env_var}={env_path} (not found)")
        else:
            searched_locations.append(f"Environment: {env_var} (not set)")

        # 2. Check user home directory with dynamic binary lookup
        home_adapter_dir = get_aidb_adapters_dir() / adapter_name
        if home_adapter_dir.exists():
            resolved_path = self._resolve_adapter_path(
                home_adapter_dir,
                binary_identifier,
            )
            if resolved_path and resolved_path.exists():
                self.ctx.debug(f"Found {language} adapter at: {resolved_path}")
                return resolved_path
            searched_locations.append(
                f"Home dir: {home_adapter_dir} (no valid binary found)",
            )
        else:
            searched_locations.append(f"Home dir: {home_adapter_dir} (not found)")

        # 3. Raise error with instructions
        instructions = self._get_install_instructions(language, adapter_name)
        raise AdapterNotFoundError(language, searched_locations, instructions)

    def _resolve_adapter_path(self, path: Path, binary_identifier: str) -> Path | None:
        """Resolve adapter path supporting both file and directory inputs.

        Parameters
        ----------
        path : Path
            Path that could be a file or directory
        binary_identifier : str
            Expected binary filename (e.g., "dapDebugServer.js", "java-debug.jar")

        Returns
        -------
        Path | None
            Resolved path to the adapter binary, or None if not found
        """
        if not path.exists():
            return None

        # Case 1: Path is a file
        if path.is_file():
            if not binary_identifier:
                # No binary identifier specified, accept any file
                return path
            if path.name == binary_identifier:
                # File matches expected binary identifier
                return path
            # File doesn't match binary identifier
            return None

        # Case 2: Path is a directory
        if path.is_dir():
            if not binary_identifier:
                # No binary identifier, return directory
                return path

            # Look for binary identifier in directory
            if "*" in binary_identifier:
                # Handle glob patterns (e.g., for Java JARs)
                matches = list(path.glob(binary_identifier))
                return matches[0] if matches else None
            # Handle direct filename
            binary_path = path / binary_identifier
            return binary_path if binary_path.exists() else None

        return None

    def _load_metadata(self, adapter_path: Path) -> dict | None:
        """Load metadata.json if available for validation (cached).

        Parameters
        ----------
        adapter_path : Path
            Path to adapter binary or directory

        Returns
        -------
        dict | None
            Parsed metadata or None if not available
        """
        # Determine metadata path
        if adapter_path.is_file():
            metadata_path = adapter_path.parent / "metadata.json"
        else:
            metadata_path = adapter_path / "metadata.json"

        # Check cache first (using string path as key for consistency)
        cache_key = str(metadata_path)
        if cache_key in self._metadata_cache:
            return self._metadata_cache[cache_key]

        if not metadata_path.exists():
            # Cache the None result to avoid repeated filesystem checks
            self._metadata_cache[cache_key] = None
            return None

        try:
            metadata = safe_read_json(metadata_path)
            self._metadata_cache[cache_key] = metadata
            return metadata
        except FileOperationError as e:
            self.ctx.debug(f"Failed to load metadata from {metadata_path}: {e}")
            self._metadata_cache[cache_key] = None
            return None

    def get_adapter_dir(self, language: str) -> Path:
        """Get the installation directory for an adapter.

        Parameters
        ----------
        language : str
            The language/adapter identifier

        Returns
        -------
        Path
            Path to the adapter directory (e.g., ~/.aidb/adapters/java/)

        Raises
        ------
        AdapterNotFoundError
            If the adapter directory doesn't exist
        """
        # Get adapter class to extract name
        try:
            adapter_class = self.registry.get_adapter_class(language)
            adapter_name = adapter_class.__name__.replace("Adapter", "").lower()
        except Exception as e:
            self.ctx.debug(f"Failed to get adapter class for {language}: {e}")
            adapter_name = language.lower()

        adapter_dir = get_aidb_adapters_dir() / adapter_name

        if not adapter_dir.exists():
            raise AdapterNotFoundError(
                language,
                [f"Directory: {adapter_dir} (not found)"],
                self._get_install_instructions(language, adapter_name),
            )

        return adapter_dir

    def _get_install_instructions(self, language: str, adapter_name: str) -> str:
        """Get installation instructions for an adapter.

        Parameters
        ----------
        language : str
            The language identifier
        adapter_name : str
            The adapter name for directory

        Returns
        -------
        str
            Installation instructions
        """
        import platform

        system = platform.system().lower()
        machine = platform.machine().lower()

        from aidb.adapters.constants import get_arch_name, get_platform_name

        platform_name = get_platform_name(system)
        arch_name = get_arch_name(machine)

        instructions = [
            f"\nTo install the {language} adapter:",
            "",
            "Option 1: Automatic download (recommended):",
            f"  - MCP: Use adapter tool with action='download', language='{language}'",
            "",
            "Option 2: Manual download from GitHub releases:",
            "  1. Go to: https://github.com/ai-debugger-inc/aidb/releases/latest",
            f"  2. Download: {adapter_name}-*-{platform_name}-{arch_name}.tar.gz",
            f"  3. Extract to: ~/.aidb/adapters/{adapter_name}/",
            "",
            "Option 3: Set environment variable:",
            f"  export AIDB_{language.upper()}_ADAPTER_PATH=/path/to/adapter",
            "",
            "For offline installation, download the adapter archive on another",
            "machine and transfer it to the target system.",
        ]

        return "\n".join(instructions)
