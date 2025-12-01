"""Python adapter builder implementation."""

from pathlib import Path
from typing import Dict
import subprocess
import shutil
import tempfile

from ..base import AdapterBuilder, BuildError
from ..metadata import create_and_write_metadata


class PythonAdapterBuilder(AdapterBuilder):
    """Builder for Python debug adapter."""

    def __init__(self, versions: Dict, platform_name: str, arch: str):
        super().__init__(versions, platform_name, arch)
        self._built_dist_dir = None

    @property
    def adapter_name(self) -> str:
        """Return the name of this adapter."""
        return "python"

    def get_adapter_config(self) -> Dict:
        """Get Python adapter configuration from versions.json."""
        return self.versions["adapters"]["python"]

    def clone_repository(self) -> Path:
        """Clone the Python adapter repository."""
        config = self.get_adapter_config()
        repo_url = config["repository"]
        ref = config.get("ref", config.get("version", "main"))

        repo_dir = self.build_dir / "debugpy"

        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        print(f"Cloning debugpy from {repo_url} at {ref}")
        subprocess.run([
            "git", "clone",
            "--depth", "1",
            "--branch", ref,
            repo_url,
            str(repo_dir)
        ], check=True)

        return repo_dir

    def build(self) -> Path:
        """Build the Python adapter from source.

        Builds debugpy from source for the target platform.
        """
        repo_dir = self.clone_repository()

        # Create a distribution directory
        dist_dir = self.build_dir / "dist"
        dist_dir.mkdir(exist_ok=True)

        # Build debugpy using setup.py if available
        setup_py = repo_dir / "setup.py"
        if setup_py.exists():
            print("Building debugpy with setup.py...")
            build_result = subprocess.run(
                ["python3", "setup.py", "build"],
                cwd=repo_dir,
                capture_output=True,
                text=True
            )

            if build_result.returncode != 0:
                print(f"Warning: setup.py build failed, using source directly")
                print(f"Error: {build_result.stderr}")

            # Try to find built output
            build_output = repo_dir / "build"
            if build_output.exists():
                lib_dirs = list(build_output.glob("lib*"))
                if lib_dirs:
                    # Use the built version
                    debugpy_src = lib_dirs[0] / "debugpy"
                    if debugpy_src.exists():
                        print(f"Using built debugpy from {debugpy_src}")
                        debugpy_dst = dist_dir / "debugpy"
                        if debugpy_dst.exists():
                            shutil.rmtree(debugpy_dst)
                        shutil.copytree(debugpy_src, debugpy_dst)

                        # Ensure __init__.py exists for health checks
                        init_file = debugpy_dst / "__init__.py"
                        if not init_file.exists():
                            init_file.touch()

                        self._built_dist_dir = dist_dir
                        return dist_dir

        # Fallback: Use source directly
        print("Using debugpy source directly...")
        debugpy_src = repo_dir / "src" / "debugpy"
        if not debugpy_src.exists():
            # Some versions have debugpy at root
            debugpy_src = repo_dir / "debugpy"

        if not debugpy_src.exists():
            raise RuntimeError(f"Could not find debugpy package in {repo_dir}")

        debugpy_dst = dist_dir / "debugpy"
        if debugpy_dst.exists():
            shutil.rmtree(debugpy_dst)

        shutil.copytree(debugpy_src, debugpy_dst)

        # Ensure __init__.py exists for health checks
        init_file = debugpy_dst / "__init__.py"
        if not init_file.exists():
            init_file.touch()

        print(f"Python adapter built in {dist_dir}")
        self._built_dist_dir = dist_dir
        return dist_dir

    def package(self) -> Path:
        """Package the Python adapter for distribution.

        Returns
        -------
        Path
            Path to the packaged adapter tarball
        """
        # Use the already built dist_dir if available
        dist_dir = self._built_dist_dir if self._built_dist_dir else self.build()

        config = self.get_adapter_config()
        version = config.get("version", "unknown")

        # Create package directory name
        adapter_name = f"python-{version}-{self.platform_name}-{self.arch}"
        package_dir = self.dist_dir / adapter_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Copy only the debugpy package - this is all we need for the adapter
        debugpy_src = dist_dir / "debugpy"
        if not debugpy_src.exists():
            raise BuildError(f"debugpy package not found in {dist_dir}")
        shutil.copytree(debugpy_src, package_dir / "debugpy")

        # Create metadata.json with adapter information
        # Python/debugpy is pure Python, so it's universal
        create_and_write_metadata(
            adapter_name="python",
            platform="universal",
            arch="universal",
            output_directory=package_dir,
            binary_identifier="debugpy"  # Package directory name
        )

        # Create tarball
        tarball_path = self.dist_dir / f"{adapter_name}.tar.gz"
        self.run_command([
            "tar", "-czf", str(tarball_path),
            "-C", str(self.dist_dir), adapter_name
        ])

        # Clean up package directory
        shutil.rmtree(package_dir)

        return tarball_path