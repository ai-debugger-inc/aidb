"""GitHub Actions reporter for CI/CD output."""

import os
from typing import Any

from .base import Reporter


class GitHubActionsReporter(Reporter):
    """Formats updates for GitHub Actions output."""

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
                lines.append(f"  - {lang}: {old_v} → {new_v} ({itype})")
            lines.append("")

        if "adapters" in all_updates:
            lines.append("Adapter Updates:")
            for adapter_name, info in all_updates["adapters"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                lines.append(f"  - {adapter_name}: {current} → {latest}")
            lines.append("")

        if "global_packages_pip" in all_updates:
            lines.append("PyPI Package Updates:")
            for package_name, info in all_updates["global_packages_pip"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                lines.append(f"  - {package_name}: {current} → {latest}")
            lines.append("")

        if "global_packages_npm" in all_updates:
            lines.append("npm Package Updates:")
            for package_name, info in all_updates["global_packages_npm"].items():
                current = info.get("current", "unknown")
                latest = info.get("latest", "unknown")
                lines.append(f"  - {package_name}: {current} → {latest}")
            lines.append("")

        return "\n".join(lines) if lines else "No updates found."

    def output(
        self, all_updates: dict[str, Any], has_updates: bool, auto_merge: bool, report: str,
    ) -> None:
        """Output in GitHub Actions format.

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
        update_types = []
        if "infrastructure" in all_updates:
            update_types.append("infrastructure")
        if "adapters" in all_updates:
            update_types.append("adapters")
        if "global_packages_pip" in all_updates or "global_packages_npm" in all_updates:
            update_types.append("packages")

        changes_lines = []
        infra = all_updates.get("infrastructure", {})
        for lang, info in infra.items():
            old_v = info.get("old_version", "?")
            new_v = info.get("new_version", "?")
            itype = info.get("type", "stable")
            changes_lines.append(f"- infra {lang} {old_v} -> {new_v} ({itype})")

        adapters = all_updates.get("adapters", {})
        for lang, info in adapters.items():
            cur = info.get("current", "unknown")
            latest = info.get("latest", "unknown")
            changes_lines.append(f"- {lang} adapter {cur} -> {latest}")

        gh_out = os.environ.get("GITHUB_OUTPUT")
        if not gh_out:
            print("Warning: GITHUB_OUTPUT environment variable not set")
            return

        with open(gh_out, "a") as f:
            f.write(f"has_updates={'true' if has_updates else 'false'}\n")
            f.write(f"auto_merge={'true' if auto_merge else 'false'}\n")
            f.write(f"update_types={','.join(update_types)}\n")

            f.write("changes<<EOF\n")
            f.write("\n".join(changes_lines) + "\n")
            f.write("EOF\n")

            f.write("report<<EOF\n")
            f.write(report + "\n")
            f.write("EOF\n")
