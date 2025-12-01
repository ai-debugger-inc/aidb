"""Version parsing, comparison, and classification utilities."""

import re

from packaging import version


class UpdateType:
    """Version update type constants."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    UNKNOWN = "unknown"


def is_stable_version(version_str: str) -> bool:
    """Check if version string represents a stable version.

    Parameters
    ----------
    version_str : str
        Version string to check

    Returns
    -------
    bool
        True if version appears to be stable (not alpha/beta/rc/dev)
    """
    unstable_indicators = ["alpha", "beta", "rc", "dev", "preview", "snapshot", "pre", "a", "b"]
    version_lower = version_str.lower()

    for indicator in unstable_indicators:
        if indicator == "a" or indicator == "b":
            if re.search(r"\d+[ab]\d+", version_lower):
                return False
        elif indicator in version_lower:
            return False

    return True


def is_semver(tag: str) -> bool:
    """Check if tag is a semantic version.

    Parameters
    ----------
    tag : str
        Tag to check

    Returns
    -------
    bool
        True if tag appears to be semantic version
    """
    tag_clean = tag.lstrip("v")

    pattern = r"^\d+\.\d+\.\d+(-[\w.]+)?$"
    if re.match(pattern, tag_clean):
        return not any(pre in tag_clean.lower() for pre in ["alpha", "beta", "rc", "dev", "pre"])
    return False


def classify_version_update(current: str, new: str) -> str:
    """Classify the type of version update.

    Parameters
    ----------
    current : str
        Current version
    new : str
        New version

    Returns
    -------
    str
        Update type: 'patch', 'minor', 'major', or 'unknown'
    """
    try:
        current_ver = version.parse(current)
        new_ver = version.parse(new)

        if hasattr(current_ver, "major") and hasattr(new_ver, "major"):
            if new_ver.major > current_ver.major:
                return UpdateType.MAJOR
            if new_ver.minor > current_ver.minor:
                return UpdateType.MINOR
            if new_ver.micro > current_ver.micro:
                return UpdateType.PATCH

    except Exception:
        pass

    return UpdateType.UNKNOWN
