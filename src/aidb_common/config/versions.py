"""Centralized version management for AIDB shared components.

This replicates and generalizes the CLI VersionManager so it can be used by CLI, tests,
and MCP without duplication.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from aidb_common.constants import SUPPORTED_LANGUAGES, Language
from aidb_common.io.files import FileOperationError
from aidb_common.repo import detect_repo_root
from aidb_logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)


class VersionManager:
    """Manages version information from versions.json."""

    def __init__(self, versions_file: Path | None = None):
        """Initialize the version manager.

        Parameters
        ----------
        versions_file : Path, optional
            Path to versions.json file. Defaults to repo root versions.json.
        """
        if versions_file is None:
            # Use shared repo detection to locate versions.json
            repo_root = detect_repo_root()
            versions_file = repo_root / "versions.json"

        self.versions_file = versions_file
        self._versions_data: dict[str, Any] | None = None

    @property
    def versions(self) -> dict[str, Any]:
        """Get versions data, loading if necessary."""
        if self._versions_data is None:
            self._load_versions()
        assert self._versions_data is not None
        return self._versions_data

    def _load_versions(self) -> None:
        """Load versions from versions.json."""
        if not self.versions_file.exists():
            msg = f"Versions file not found: {self.versions_file}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        try:
            with self.versions_file.open(encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in {self.versions_file}: {e}"
            logger.error(msg)
            raise ValueError(msg) from e
        except OSError as e:
            msg = f"Cannot read versions file {self.versions_file}: {e}"
            logger.error(msg)
            raise FileOperationError(msg) from e

        if not isinstance(data, dict):
            msg = (
                "Versions file must contain a mapping at the top level: "
                f"{self.versions_file}"
            )
            logger.error(msg)
            raise ValueError(msg)

        self._versions_data = data

        logger.debug("Loaded versions from %s", self.versions_file)

    # ===== Infrastructure =====

    def get_infrastructure_versions(self) -> dict[str, str]:
        """Get infrastructure versions for Docker builds."""
        infra = self.versions.get("infrastructure", {})

        # Support both old format (python_version) and new format (python.version)
        result: dict[str, str] = {}
        for lang in ["python", "node", "java"]:
            if lang in infra and isinstance(infra[lang], dict):
                result[lang] = infra[lang].get("version", "")
            else:
                old_key = f"{lang}_version"
                result[lang] = infra.get(
                    old_key,
                    {
                        "python": "3.12",
                        "node": "22",
                        "java": "21",
                    }.get(lang, ""),
                )
        return result

    def get_infrastructure_metadata(self, language: str) -> dict[str, Any] | None:
        """Get infrastructure metadata including EOL dates."""
        infra = self.versions.get("infrastructure", {})
        if language in infra and isinstance(infra[language], dict):
            return infra[language]
        return None

    def get_infrastructure_docker_tag(self, language: str) -> str:
        """Get Docker base image tag for infrastructure.

        Parameters
        ----------
        language : str
            Language ('python', 'node', 'java')

        Returns
        -------
        str
            Docker tag (e.g., '3.12-slim')
        """
        infra = self.versions.get("infrastructure", {})
        lang_config = infra.get(language, {})

        # Fallback to version if docker_tag not specified
        docker_tag = lang_config.get("docker_tag")
        if docker_tag:
            return docker_tag

        version = lang_config.get("version", "")
        logger.warning(
            "No docker_tag for %s, falling back to version: %s",
            language,
            version,
        )
        return version

    # ===== Global Packages =====

    def get_global_package_version(self, manager: str, package: str) -> str:
        """Get global package version.

        Parameters
        ----------
        manager : str
            Package manager ('pip' or 'npm')
        package : str
            Package name

        Returns
        -------
        str
            Version string, empty if not found
        """
        packages = self.versions.get("global_packages", {})
        manager_packages = packages.get(manager, {})
        package_info = manager_packages.get(package, {})
        return package_info.get("version", "")

    # ===== Adapters =====

    def get_adapter_version(self, language: str) -> str | None:
        """Get adapter version for a specific language."""
        adapters = self.versions.get("adapters", {})

        if language in adapters:
            version = adapters[language].get("version", "")
            # Strip 'v' prefix if present (e.g., 'v1.104.0' -> '1.104.0')
            return version.lstrip("v") if version else None
        return None

    def get_docker_build_args(self) -> dict[str, str]:
        """Generate Docker build arguments from versions.json.

        Returns all versions as ARG-ready key-value pairs for docker-compose
        and Dockerfile consumption.

        Returns
        -------
        dict[str, str]
            Build arguments mapping ARG names to values
        """
        build_args: dict[str, str] = {}

        # Infrastructure versions
        infra = self.get_infrastructure_versions()
        build_args["PYTHON_VERSION"] = infra["python"]
        build_args["NODE_VERSION"] = infra["node"]
        build_args["JAVA_VERSION"] = infra["java"]

        # Infrastructure Docker tags
        build_args["PYTHON_BASE_TAG"] = self.get_infrastructure_docker_tag("python")
        build_args["NODE_BASE_TAG"] = self.get_infrastructure_docker_tag("node")

        # Adapter versions
        build_args["DEBUGPY_VERSION"] = self.get_adapter_version("python") or "1.8.0"
        build_args["JS_DEBUG_VERSION"] = (
            self.get_adapter_version("javascript") or "1.104.0"
        )
        build_args["JAVA_DEBUG_VERSION"] = self.get_adapter_version("java") or "0.53.1"

        # JDTLS version (Eclipse JDT Language Server)
        java_adapter = self.versions.get("adapters", {}).get("java", {})
        build_args["JDTLS_VERSION"] = java_adapter.get(
            "jdtls_version",
            "1.55.0-202511271007",
        )

        # Global package versions
        build_args["PIP_VERSION"] = self.get_global_package_version("pip", "pip")
        build_args["SETUPTOOLS_VERSION"] = self.get_global_package_version(
            "pip",
            "setuptools",
        )
        build_args["WHEEL_VERSION"] = self.get_global_package_version("pip", "wheel")
        build_args["TYPESCRIPT_VERSION"] = self.get_global_package_version(
            "npm",
            "typescript",
        )
        build_args["TS_NODE_VERSION"] = self.get_global_package_version(
            "npm",
            "ts_node",
        )

        return build_args

    def get_all_versions(self) -> dict[str, Any]:
        """Get all version information in a structured format."""
        infra = self.get_infrastructure_versions()
        result: dict[str, Any] = {
            "aidb_version": self.versions.get("version", "0.0.0"),
            "infrastructure": infra,
            "adapters": {},
            "global_packages": {},
            "runtimes": {},
        }

        for lang in SUPPORTED_LANGUAGES:
            version = self.get_adapter_version(lang)
            if version:
                result["adapters"][lang] = version

        # Include global_packages section
        global_packages = self.versions.get("global_packages", {})
        for manager, packages in global_packages.items():
            result["global_packages"][manager] = {}
            for pkg_name, pkg_info in packages.items():
                result["global_packages"][manager][pkg_name] = {
                    "version": pkg_info.get("version", ""),
                    "description": pkg_info.get("description", ""),
                }

        runtimes = self.versions.get("runtimes", {})
        for lang, config in runtimes.items():
            result["runtimes"][lang] = {
                "min_version": config.get("min_version"),
                "recommended": config.get("recommended"),
            }
        return result

    def validate_versions(self) -> dict[str, bool]:
        """Validate that all required version fields are present."""
        results: dict[str, bool] = {}

        infra = self.versions.get("infrastructure", {})
        infra_valid = False
        if all(
            isinstance(infra.get(lang), dict) and infra[lang].get("version")
            for lang in ["python", "node", "java"]
        ) or all(f"{lang}_version" in infra for lang in ["python", "node", "java"]):
            infra_valid = True
        results["infrastructure"] = infra_valid

        adapters = self.versions.get("adapters", {})
        results["adapters"] = all(
            [
                "javascript" in adapters,
                "java" in adapters,
                adapters.get("javascript", {}).get("version"),
                adapters.get("java", {}).get("version"),
                adapters.get("java", {}).get("jdtls_version"),
            ],
        )

        runtimes = self.versions.get("runtimes", {})
        results["runtimes"] = "python" in runtimes
        return results

    def get_adapter_download_info(self, language: str) -> dict[str, str] | None:
        """Get download information for an adapter."""
        adapters = self.versions.get("adapters", {})
        if language not in adapters:
            return None
        adapter = adapters[language]
        info = {
            "version": adapter.get("version", ""),
            "repo": adapter.get("repo", ""),
        }
        if language == Language.JAVASCRIPT:
            version = info["version"]
            info["url"] = (
                f"https://github.com/microsoft/vscode-js-debug/releases/download/{version}/js-debug-dap-{version}.tar.gz"
            )
        elif language == Language.JAVA:
            version = info["version"]
            info["url"] = (
                f"https://vscjava.gallery.vsassets.io/_apis/public/gallery/publisher/vscjava/extension/vscode-java-debug/{version}/assetbyname/Microsoft.VisualStudio.Services.VSIXPackage"
            )
        return info

    def _format_global_packages_section(self, global_packages: dict) -> list[str]:
        """Format global packages section for text output."""
        lines = []
        for manager, packages in global_packages.items():
            lines.extend(["", f"{manager.upper()} Packages:"])
            for pkg_name, pkg_info in packages.items():
                version_str = pkg_info.get("version", "")
                lines.append(f"  {pkg_name:20s} {version_str}")
                if pkg_info.get("description"):
                    lines.append(f"    → {pkg_info['description']}")
        return lines

    def _format_runtimes_section(self, runtimes: dict) -> list[str]:
        """Format runtimes section for text output."""
        lines = ["", "Runtime Requirements:"]
        for lang, reqs in runtimes.items():
            lines.append(f"  {lang}:")
            if reqs.get("min_version"):
                lines.append(f"    Minimum: {reqs['min_version']}")
            if reqs.get("recommended"):
                lines.append(f"    Recommended: {reqs['recommended']}")
        return lines

    def format_versions_output(self, format_type: str = "text") -> str:
        """Format version information for display."""
        if format_type == "json":
            return json.dumps(self.get_all_versions(), indent=2)
        if format_type == "yaml":
            # YAML output requires pyyaml (dev dependency only)
            try:
                import yaml

                return yaml.dump(self.get_all_versions(), default_flow_style=False)
            except ImportError:
                return json.dumps(self.get_all_versions(), indent=2)
        if format_type == "env":
            build_args = self.get_docker_build_args()
            lines = [f"export {key}={value}" for key, value in build_args.items()]
            return "\n".join(lines)

        versions = self.get_all_versions()
        lines = [
            "AIDB Version Information",
            "=" * 40,
            f"AIDB Version: {versions['aidb_version']}",
            "",
            "Infrastructure Versions:",
            f"  Python: {versions['infrastructure']['python']}",
            f"  Node.js: {versions['infrastructure']['node']}",
            f"  Java: {versions['infrastructure']['java']}",
            "",
            "Adapter Versions:",
        ]
        for lang, version in versions["adapters"].items():
            lines.append(f"  {lang}: {version}")

        if versions.get("global_packages"):
            lines.extend(
                self._format_global_packages_section(versions["global_packages"]),
            )

        if versions["runtimes"]:
            lines.extend(self._format_runtimes_section(versions["runtimes"]))

        return "\n".join(lines)
