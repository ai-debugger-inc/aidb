"""Shared constants for adapter management."""

# Platform and architecture mappings for consistent naming across the system
PLATFORM_MAP = {
    "darwin": "darwin",
    "linux": "linux",
    "windows": "windows",
}

ARCH_MAP = {
    "x86_64": "x64",
    "amd64": "x64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def get_platform_name(system: str) -> str:
    """Get standardized platform name.

    Parameters
    ----------
    system : str
        System name from platform.system().lower()

    Returns
    -------
    str
        Standardized platform name
    """
    return PLATFORM_MAP.get(system, system)


def get_arch_name(machine: str) -> str:
    """Get standardized architecture name.

    Parameters
    ----------
    machine : str
        Machine type from platform.machine().lower()

    Returns
    -------
    str
        Standardized architecture name
    """
    return ARCH_MAP.get(machine, machine)
