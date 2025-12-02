"""TypeScript adapter builder implementation."""

from pathlib import Path
from typing import Dict
import subprocess
import shutil
import json

from ..base import AdapterBuilder


class TypeScriptAdapterBuilder(AdapterBuilder):
    """Builder for TypeScript debug adapter.

    Note: TypeScript typically uses the same adapter as JavaScript
    (vscode-js-debug), but this builder can be customized if needed.
    """

    def get_adapter_config(self) -> Dict:
        """Get TypeScript adapter configuration from versions.json."""
        # TypeScript uses the JavaScript adapter by default
        # Override this method if a separate TypeScript adapter is added
        return self.versions["adapters"].get("typescript",
                                             self.versions["adapters"]["javascript"])

    def clone_repository(self) -> Path:
        """Clone the TypeScript/JavaScript adapter repository."""
        config = self.get_adapter_config()
        repo_url = config["repository"]
        ref = config.get("ref", config.get("version", "main"))

        repo_dir = self.build_dir / "vscode-js-debug"

        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        print(f"Cloning vscode-js-debug from {repo_url} at {ref}")
        subprocess.run([
            "git", "clone",
            "--depth", "1",
            "--branch", ref,
            repo_url,
            str(repo_dir)
        ], check=True)

        return repo_dir

    def build(self) -> Path:
        """Build the TypeScript adapter."""
        repo_dir = self.clone_repository()

        print("Installing dependencies...")
        subprocess.run(["npm", "ci"], cwd=repo_dir, check=True)

        print("Building TypeScript adapter...")
        subprocess.run(["npm", "run", "compile"], cwd=repo_dir, check=True)

        # The built files are typically in the 'dist' or 'out' directory
        built_dir = repo_dir / "dist"
        if not built_dir.exists():
            built_dir = repo_dir / "out"

        if not built_dir.exists():
            raise RuntimeError(f"Build output directory not found in {repo_dir}")

        return built_dir

    def package(self) -> Path:
        """Package the TypeScript adapter for distribution."""
        repo_dir = self.build_dir / "vscode-js-debug"
        built_dir = self.build()
        config = self.get_adapter_config()
        version = config.get("version", "unknown")

        # Create package filename
        package_name = f"vscode-js-debug-ts-{version}-{self.platform}-{self.arch}.tar.gz"
        package_path = self.dist_dir / package_name

        print(f"Creating TypeScript adapter package: {package_name}")

        # Create distribution directory with necessary files
        dist_staging = self.build_dir / "typescript-dist"
        if dist_staging.exists():
            shutil.rmtree(dist_staging)
        dist_staging.mkdir()

        # Copy built files
        shutil.copytree(built_dir, dist_staging / "dist")

        # Copy package.json (needed for node module resolution)
        pkg_json_src = repo_dir / "package.json"
        if pkg_json_src.exists():
            shutil.copy2(pkg_json_src, dist_staging / "package.json")

        # Create TypeScript-specific launch configuration
        ts_config = {
            "type": "pwa-node",
            "request": "launch",
            "name": "TypeScript Debug",
            "runtimeArgs": ["--nolazy", "-r", "ts-node/register"],
            "sourceMaps": True,
            "cwd": "${workspaceFolder}",
            "protocol": "inspector",
            "console": "integratedTerminal",
            "resolveSourceMapLocations": [
                "${workspaceFolder}/**",
                "!**/node_modules/**"
            ]
        }

        config_path = dist_staging / "typescript-config.json"
        config_path.write_text(json.dumps(ts_config, indent=2))

        # Create tarball
        subprocess.run([
            "tar", "-czf",
            str(package_path),
            "-C", str(dist_staging.parent),
            dist_staging.name
        ], check=True)

        # Create checksum
        checksum = self.create_checksum(package_path)
        checksum_path = package_path.with_suffix(".tar.gz.sha256")
        checksum_path.write_text(f"{checksum}  {package_name}\n")

        print(f"Package created: {package_path}")
        print(f"Checksum: {checksum}")

        # Cleanup
        shutil.rmtree(dist_staging)

        return package_path