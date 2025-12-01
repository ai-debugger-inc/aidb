"""Console reporter for human-readable output."""

from typing import Any

from .base import Reporter


class ConsoleReporter(Reporter):
    """Formats updates for console output."""

    def generate_report(self, all_updates: dict[str, Any]) -> str:
        """Generate human-readable update report.

        Parameters
        ----------
        all_updates : dict[str, Any]
            All updates found

        Returns
        -------
        str
            Formatted report text
        """
        lines = []

        if "infrastructure" in all_updates:
            lines.append("Infrastructure Updates:")
            for lang, info in all_updates["infrastructure"].items():
                old_v = info.get("old_version", "?")
                new_v = info.get("new_version", "?")
                itype = info.get("type", "stable")
                eol = info.get("end_of_life")
                lines.append(f"  - {lang}: {old_v} → {new_v} ({itype})")
                if eol:
                    lines.append(f"    EOL: {eol}")
            lines.append("")

        if "adapters" in all_updates:
            lines.append("Adapter Updates:")
            for adapter_name, info in all_updates["adapters"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                repo = info.get("repo", "")
                lines.append(f"  - {adapter_name}: {current} → {latest}")
                if repo:
                    lines.append(f"    Repo: {repo}")
            lines.append("")

        if "global_packages_pip" in all_updates:
            lines.append("PyPI Package Updates:")
            for package_name, info in all_updates["global_packages_pip"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                update_type = info.get("update_type", "unknown")
                lines.append(f"  - {package_name}: {current} → {latest} ({update_type})")
            lines.append("")

        if "global_packages_npm" in all_updates:
            lines.append("npm Package Updates:")
            for package_name, info in all_updates["global_packages_npm"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                update_type = info.get("update_type", "unknown")
                lines.append(f"  - {package_name}: {current} → {latest} ({update_type})")
            lines.append("")

        if "debugpy_sync" in all_updates:
            sync_info = all_updates["debugpy_sync"]
            lines.append("debugpy Synchronization:")
            if sync_info.get("errors"):
                lines.append("  Errors:")
                for error in sync_info["errors"]:
                    lines.append(f"    - {error}")
            if sync_info.get("warnings"):
                lines.append("  Warnings:")
                for warning in sync_info["warnings"]:
                    lines.append(f"    - {warning}")
            if sync_info.get("message"):
                lines.append(f"  {sync_info['message']}")
            lines.append("")

        return "\n".join(lines) if lines else "No updates found."

    def output(
        self, all_updates: dict[str, Any], has_updates: bool, auto_merge: bool, report: str,
    ) -> None:
        """Output to console.

        Parameters
        ----------
        all_updates : dict[str, Any]
            All updates found
        has_updates : bool
            Whether any updates were found
        auto_merge : bool
            Whether updates can be auto-merged
        report : str
            Update report text
        """
        print(report)

        if not has_updates:
            print("✅ All versions are up to date")
        elif auto_merge:
            print("\n✅ Updates can be auto-merged (patch versions only)")
        elif has_updates:
            print("\n⚠️  Manual review required - contains minor/major updates")
