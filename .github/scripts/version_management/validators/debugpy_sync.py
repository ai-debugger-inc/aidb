"""Debugpy version synchronization validation between versions.json and pyproject.toml."""

import re
from pathlib import Path
from typing import Any

from packaging import version


class DebugpySyncValidator:
    """Validates debugpy version synchronization between config files."""

    def __init__(self, config_path: Path):
        """Initialize validator.

        Parameters
        ----------
        config_path : Path
            Path to versions.json
        """
        self.config_path = config_path

    def validate(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate debugpy version sync between versions.json and pyproject.toml.

        Parameters
        ----------
        config : dict[str, Any]
            Loaded versions.json configuration

        Returns
        -------
        dict[str, Any]
            Validation result with status and details
        """
        result = {"valid": True, "warnings": [], "errors": []}

        adapters = config.get("adapters", {})
        python_adapter = adapters.get("python", {})
        adapter_version = python_adapter.get("version", "")

        if not adapter_version:
            result["warnings"].append("No Python adapter version found in versions.json")
            return result

        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        pyproject_path = self.config_path.parent / "pyproject.toml"
        if not pyproject_path.exists():
            result["errors"].append(f"pyproject.toml not found at {pyproject_path}")
            result["valid"] = False
            return result

        with pyproject_path.open("rb") as f:
            pyproject_data = tomllib.load(f)

        dependencies = pyproject_data.get("project", {}).get("dependencies", [])
        debugpy_constraint = None

        for dep in dependencies:
            if dep.startswith("debugpy"):
                debugpy_constraint = dep
                break

        if not debugpy_constraint:
            result["warnings"].append(
                "debugpy not found in pyproject.toml dependencies "
                "(expected if using pre-packaged adapter only)",
            )
            return result

        match = re.search(r"debugpy([><=~]+)([\d.]+)", debugpy_constraint)
        if not match:
            result["warnings"].append(
                f"Could not parse debugpy constraint: {debugpy_constraint}",
            )
            return result

        operator, toml_version = match.groups()

        try:
            adapter_ver = version.parse(adapter_version)
            toml_ver = version.parse(toml_version)

            if toml_ver < adapter_ver:
                result["valid"] = False
                result["errors"].append(
                    f"pyproject.toml debugpy minimum ({toml_version}) is older than "
                    f"adapter version ({adapter_version}). "
                    f"Update pyproject.toml to: debugpy>={adapter_version}",
                )
            elif toml_ver > adapter_ver:
                result["warnings"].append(
                    f"pyproject.toml debugpy minimum ({toml_version}) is newer than "
                    f"adapter version ({adapter_version}). "
                    f"Consider updating versions.json adapter version.",
                )
            else:
                result["message"] = (
                    f"debugpy versions in sync: adapter={adapter_version}, "
                    f"pyproject.toml>={toml_version}"
                )

        except Exception as e:
            result["warnings"].append(f"Error comparing versions: {e}")

        return result
