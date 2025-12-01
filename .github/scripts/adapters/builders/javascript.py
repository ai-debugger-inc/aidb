"""JavaScript adapter builder."""

import platform
import shutil
from pathlib import Path

from ..base import AdapterBuilder, BuildError
from ..metadata import create_and_write_metadata


class JavaScriptAdapterBuilder(AdapterBuilder):
    """Builder for JavaScript/TypeScript debug adapter (vscode-js-debug)."""

    def __init__(self, versions: dict, platform_name: str, arch: str):
        super().__init__(versions, platform_name, arch)
        self._built_dist_dir = None

    @property
    def adapter_name(self) -> str:
        """Return the name of this adapter."""
        return "javascript"

    def get_adapter_config(self) -> dict:
        """Get adapter configuration from versions.json."""
        return self.versions["adapters"]["javascript"]

    def clone_repository(self) -> Path:
        """Clone the vscode-js-debug repository.

        Preserves node_modules if it exists (from CI cache) to speed up builds.

        Returns
        -------
        Path
            Path to the cloned repository
        """
        config = self.get_adapter_config()
        version = config["version"]
        repo = config["repo"]

        repo_dir = self.build_dir / "vscode-js-debug"
        node_modules = repo_dir / "node_modules"
        preserved_node_modules = self.build_dir / "_node_modules_cache"

        # Preserve node_modules if it exists (from CI cache)
        if node_modules.exists():
            print("Preserving cached node_modules...")
            if preserved_node_modules.exists():
                shutil.rmtree(preserved_node_modules)
            shutil.move(str(node_modules), str(preserved_node_modules))

        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        self.run_command([
            "git", "clone", "--depth", "1", "--branch", version,
            f"https://github.com/{repo}.git", str(repo_dir),
        ])

        # Restore node_modules if we preserved it
        if preserved_node_modules.exists():
            print("Restoring cached node_modules...")
            shutil.move(str(preserved_node_modules), str(node_modules))

        print("Clone completed successfully")
        return repo_dir

    def build(self) -> Path:
        """Build the JavaScript adapter.

        Returns
        -------
        Path
            Path to the built distribution directory
        """
        repo_dir = self.clone_repository()

        # Determine npm/npx commands (npm.cmd/npx.cmd on Windows)
        npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
        npx_cmd = "npx.cmd" if platform.system() == "Windows" else "npx"

        # Install dependencies
        # --prefer-offline: uses cached packages when available
        # --ignore-scripts: skips postinstall (playwright install) which takes ~3 min on Windows
        #                   due to Windows Feature installation (Media Foundation)
        #                   The DAP server build doesn't need Playwright - it's only for tests
        print("Installing dependencies...")
        self.run_command(
            [npm_cmd, "ci", "--prefer-offline", "--ignore-scripts"],
            cwd=repo_dir,
        )

        # Build the standalone DAP server
        print("Building DAP debug server...")
        self.run_command([npx_cmd, "gulp", "dapDebugServer"], cwd=repo_dir)

        print("Build completed successfully")

        # Create distribution directory
        dist_dir = self.build_dir / "dist"
        dist_dir.mkdir(parents=True, exist_ok=True)

        # The build creates dist/ with src/, vendor/, and other directories
        built_dist = repo_dir / "dist"

        if not built_dist.exists():
            msg = f"dist directory not found at {built_dist}"
            raise BuildError(msg)

        dap_server_src = built_dist / "src" / "dapDebugServer.js"
        if not dap_server_src.exists():
            msg = f"dapDebugServer.js not found at {dap_server_src}"
            raise BuildError(msg)

        # Copy directories and metadata files only
        # Build artifacts (.js, .wasm, .css, .node) are in src/ subdirectory
        # Only copy metadata/documentation files from root level to avoid duplicates
        metadata_files = {"LICENSE", "README.md", "package.nls.json"}

        for item in built_dist.glob("*"):
            if item.is_dir() and item.name != "resources":
                shutil.copytree(item, dist_dir / item.name, dirs_exist_ok=True)
                print(f"Copied directory {item.name}/ to dist")
            elif item.is_file() and item.name in metadata_files:
                shutil.copy2(item, dist_dir / item.name)
                print(f"Copied {item.name} to dist")

        self._built_dist_dir = dist_dir
        return dist_dir

    def package(self) -> Path:
        """Package the JavaScript adapter.

        Returns
        -------
        Path
            Path to the packaged adapter tarball
        """
        # Use the already built dist_dir if available
        dist_dir = self._built_dist_dir if self._built_dist_dir else self.build()

        config = self.get_adapter_config()
        version = config["version"]

        # Create package directory
        adapter_name = f"javascript-{version}-{self.platform_name}-{self.arch}"
        package_dir = self.dist_dir / adapter_name
        package_dir.mkdir(parents=True, exist_ok=True)

        # Copy all necessary files and directories from dist_dir
        dap_server = dist_dir / "src" / "dapDebugServer.js"
        if not dap_server.exists():
            msg = f"dapDebugServer.js not found in {dist_dir}/src"
            raise BuildError(msg)

        # Copy directories and metadata files only (avoid duplicating build artifacts)
        metadata_files = {"LICENSE", "README.md", "package.nls.json"}

        for item in dist_dir.glob("*"):
            if item.is_dir() and item.name != "resources":
                shutil.copytree(item, package_dir / item.name, dirs_exist_ok=True)
                print(f"Packaged directory {item.name}/")
            elif item.is_file() and item.name in metadata_files:
                shutil.copy2(item, package_dir / item.name)
                print(f"Packaged {item.name}")

        # Create metadata.json with adapter information
        # JavaScript adapter may have platform-specific dependencies from npm
        create_and_write_metadata(
            adapter_name="javascript",
            platform=self.platform_name,
            arch=self.arch,
            output_directory=package_dir,
            binary_identifier="src/dapDebugServer.js",
        )

        # Create tarball
        tarball_path = self.dist_dir / f"{adapter_name}.tar.gz"
        self.run_command([
            "tar", "-czf", str(tarball_path),
            "-C", str(self.dist_dir), adapter_name,
        ])

        # Clean up package directory
        shutil.rmtree(package_dir)

        return tarball_path
