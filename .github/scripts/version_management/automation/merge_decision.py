"""Auto-merge decision logic for version updates."""

from typing import Any

from packaging import version


def should_auto_merge(all_updates: dict[str, Any]) -> bool:
    """Determine if updates can be auto-merged (patch-only).

    Parameters
    ----------
    all_updates : dict[str, Any]
        All updates found

    Returns
    -------
    bool
        True if safe to auto-merge (all updates are patch-level)
    """
    if "infrastructure" in all_updates:
        for _lang, info in all_updates["infrastructure"].items():
            current = info.get("old_version", "")
            new = info.get("new_version", "")

            if not _is_patch_update(current, new):
                return False

    if "adapters" in all_updates:
        for _adapter_name, info in all_updates["adapters"].items():
            current = info.get("current", "")
            latest = info.get("latest", "")

            if not _is_patch_update(current, latest):
                return False

    if "global_packages_pip" in all_updates:
        for _package_name, info in all_updates["global_packages_pip"].items():
            update_type = info.get("update_type", "unknown")
            if update_type != "patch":
                return False

    if "global_packages_npm" in all_updates:
        for _package_name, info in all_updates["global_packages_npm"].items():
            update_type = info.get("update_type", "unknown")
            if update_type != "patch":
                return False

    return bool(all_updates)


def _is_patch_update(current: str, new: str) -> bool:
    """Check if version update is patch-level only.

    Parameters
    ----------
    current : str
        Current version
    new : str
        New version

    Returns
    -------
    bool
        True if patch-level update
    """
    try:
        current_ver = version.parse(current)
        new_ver = version.parse(new)

        if hasattr(current_ver, "major") and hasattr(new_ver, "major"):
            if current_ver.major != new_ver.major:
                return False
            return current_ver.minor == new_ver.minor

    except Exception:
        pass

    return False
