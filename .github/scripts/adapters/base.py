"""Base adapter builder class."""

import hashlib
import platform
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class BuildError(Exception):
    """Raised when adapter build fails."""


class AdapterBuilder(ABC):
    """Base class for all adapter builders."""

    def __init__(self, versions: dict, platform_name: str, arch: str):
        """Initialize adapter builder.

        Parameters
        ----------
        versions : dict
            Versions configuration from versions.json
        platform_name : str
            Target platform (linux, darwin, windows)
        arch : str
            Target architecture (x64, arm64)
        """
        self.versions = versions
        self.platform_name = platform_name
        self.arch = arch
        self.build_dir = Path("build")
        self.dist_dir = Path("dist")

        # On macOS, globally disable creation of ._* resource fork files
        # This ensures no ._* files are created in archives or during any file operations
        if platform.system() == "Darwin":
            import os
            os.environ["COPYFILE_DISABLE"] = "1"

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Return the name of this adapter."""

    @abstractmethod
    def get_adapter_config(self) -> dict:
        """Get adapter configuration from versions.json.

        Returns
        -------
        dict
            Adapter configuration including version, repo, etc.
        """

    @abstractmethod
    def clone_repository(self) -> Path:
        """Clone the adapter repository.

        Returns
        -------
        Path
            Path to the cloned repository
        """

    @abstractmethod
    def build(self) -> Path:
        """Build the adapter.

        Returns
        -------
        Path
            Path to the built distribution directory
        """

    @abstractmethod
    def package(self) -> Path:
        """Package the adapter for distribution.

        Parameters
        ----------
        repo_dir : Path
            Path to the built repository

        Returns
        -------
        Path
            Path to the packaged adapter tarball
        """

    def create_checksum(self, file_path: Path) -> str:
        """Create SHA256 checksum for file.

        Parameters
        ----------
        file_path : Path
            Path to file to checksum

        Returns
        -------
        str
            Hex digest of SHA256 checksum
        """
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def run_command(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        capture_output: bool = False,
        env: dict | None = None,
    ) -> subprocess.CompletedProcess:
        """Run command with error handling.

        Parameters
        ----------
        cmd : List[str]
            Command and arguments
        cwd : Optional[Path]
            Working directory
        capture_output : bool
            Whether to capture output
        env : Optional[dict]
            Environment variables

        Returns
        -------
        subprocess.CompletedProcess
            Result of the command

        Raises
        ------
        BuildError
            If command fails
        """
        print(f"Running: {' '.join(cmd)}")
        if cwd:
            print(f"Working directory: {cwd}")

        # On macOS, prevent creation of ._* resource fork files in archives
        if platform.system() == "Darwin":
            import os
            if env is None:
                env = os.environ.copy()
            env["COPYFILE_DISABLE"] = "1"

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                capture_output=capture_output,
                text=True,
                env=env,
            )
            return result
        except subprocess.CalledProcessError as e:
            error_msg = f"Command failed: {' '.join(cmd)}\nError: {e}"
            if e.stderr:
                error_msg += f"\nStderr: {e.stderr}"
            if e.stdout:
                error_msg += f"\nStdout: {e.stdout}"
            raise BuildError(error_msg)

    def setup_directories(self) -> None:
        """Create necessary build directories."""
        self.build_dir.mkdir(exist_ok=True)
        self.dist_dir.mkdir(exist_ok=True)

    def get_platform_info(self) -> tuple[str, str]:
        """Get current platform and architecture.

        Returns
        -------
        Tuple[str, str]
            Platform name and architecture
        """
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Normalize platform names
        platform_map = {
            "darwin": "darwin",
            "linux": "linux",
            "windows": "windows",
        }

        # Normalize architecture names
        arch_map = {
            "x86_64": "x64",
            "amd64": "x64",
            "arm64": "arm64",
            "aarch64": "arm64",
        }

        return platform_map.get(system, system), arch_map.get(machine, machine)

    def build_adapter(self) -> tuple[Path, str]:
        """Build and package adapter with checksum.

        This is the main entry point that orchestrates the build process.

        Returns
        -------
        Tuple[Path, str]
            Path to packaged adapter and its checksum
        """
        self.setup_directories()

        # Build adapter (handles cloning internally)
        dist_dir = self.build()

        # Package adapter
        tarball_path = self.package()

        # Create checksum
        checksum = self.create_checksum(tarball_path)

        # Create checksum file
        checksum_path = Path(str(tarball_path) + ".sha256")
        with checksum_path.open("w") as f:
            f.write(f"{checksum}  {tarball_path.name}\n")

        print(f"Built {self.adapter_name} adapter: {tarball_path}")
        print(f"Checksum: {checksum}")

        return tarball_path, checksum
