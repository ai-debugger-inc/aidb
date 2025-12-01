"""Adapter builder registry."""

from typing import Dict, Type

from .base import AdapterBuilder
from .builders import (
    JavaScriptAdapterBuilder,
    JavaAdapterBuilder,
    PythonAdapterBuilder,
    TypeScriptAdapterBuilder,
)


# Registry of all available adapter builders
ADAPTER_BUILDERS: Dict[str, Type[AdapterBuilder]] = {
    "javascript": JavaScriptAdapterBuilder,
    "java": JavaAdapterBuilder,
    "python": PythonAdapterBuilder,
    "typescript": TypeScriptAdapterBuilder,
    # Easy to add new adapters here:
    # "go": GoAdapterBuilder,
    # "rust": RustAdapterBuilder,
}


def get_builder(
    adapter_name: str,
    versions: dict,
    platform_name: str,
    arch: str
) -> AdapterBuilder:
    """Get an adapter builder instance.

    Parameters
    ----------
    adapter_name : str
        Name of the adapter (e.g., "javascript", "java")
    versions : dict
        Versions configuration from versions.yaml
    platform_name : str
        Target platform (linux, darwin, windows)
    arch : str
        Target architecture (x64, arm64)

    Returns
    -------
    AdapterBuilder
        Instance of the appropriate adapter builder

    Raises
    ------
    ValueError
        If adapter_name is not registered
    """
    if adapter_name not in ADAPTER_BUILDERS:
        available = ", ".join(ADAPTER_BUILDERS.keys())
        raise ValueError(
            f"Unknown adapter: {adapter_name}. Available: {available}"
        )

    builder_class = ADAPTER_BUILDERS[adapter_name]
    return builder_class(versions, platform_name, arch)


def list_adapters() -> list:
    """List all registered adapters.

    Returns
    -------
    list
        List of adapter names
    """
    return list(ADAPTER_BUILDERS.keys())