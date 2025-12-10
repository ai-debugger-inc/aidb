"""Typed environment variable readers for AIDB common.

This module centralizes safe parsing of environment variables with consistent semantics
across the codebase. Provides both new read_* functions and backward compatible get_*
aliases.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Iterable
    from enum import Enum

T = TypeVar("T")

# Boolean string representations (case-insensitive normalized)
TRUTHY_VALUES = frozenset({"1", "true", "yes", "on", "y", "t"})
FALSY_VALUES = frozenset({"0", "false", "no", "off", "n", "f"})

# Backward compatibility aliases
_TRUTHY = TRUTHY_VALUES
_FALSY = FALSY_VALUES

# NOTE: This module cannot use aidb_logging due to circular import - aidb_logging
# uses this module's read_str() during initialization. Using stdlib logging here.
logger = logging.getLogger(__name__)


def read_str(name: str, default: str | None = None) -> str | None:
    """Read an environment variable as a string.

    Parameters
    ----------
    name : str
        Environment variable name
    default : str | None
        Default value if not found

    Returns
    -------
    str | None
        Environment variable value or default
    """
    return (
        os.environ.get(name, default) if default is not None else os.environ.get(name)
    )


def read_bool(name: str, default: bool = False) -> bool:
    """Read an environment variable parsed as a boolean.

    Recognizes common truthy/falsy strings. Falls back to ``default`` when
    value is empty or unrecognized.

    Parameters
    ----------
    name : str
        Environment variable name
    default : bool
        Default value if not found or invalid

    Returns
    -------
    bool
        Parsed boolean value or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in _TRUTHY:
        return True
    if val in _FALSY:
        return False
    return default


def read_int(name: str, default: int | None = None) -> int | None:
    """Read an environment variable parsed as an int.

    Parameters
    ----------
    name : str
        Environment variable name
    default : int | None
        Default value if not found or invalid

    Returns
    -------
    int | None
        Parsed integer value or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def read_float(name: str, default: float | None = None) -> float | None:
    """Read an environment variable parsed as a float.

    Parameters
    ----------
    name : str
        Environment variable name
    default : float | None
        Default value if not found or invalid

    Returns
    -------
    float | None
        Parsed float value or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def read_enum(
    name: str,
    enum_class: type[Enum],
    default: Enum | None = None,
) -> Enum | None:
    """Read an environment variable constrained to enum values.

    Parameters
    ----------
    name : str
        Environment variable name
    enum_class : type[Enum]
        Enum class to validate against
    default : Enum | None
        Default enum value if not found or invalid

    Returns
    -------
    Enum | None
        Parsed enum value or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    # Try to find enum by name or value
    try:
        # Try by name first (case-insensitive)
        for enum_val in enum_class:
            if enum_val.name.lower() == raw.lower():
                return enum_val

        # Try by value (case-insensitive for strings)
        for enum_val in enum_class:
            if (
                isinstance(enum_val.value, str)
                and enum_val.value.lower() == raw.lower()
                or enum_val.value == raw
            ):
                return enum_val
    except (AttributeError, ValueError):
        pass

    return default


def read_list(
    name: str,
    delimiter: str = ",",
    default: list[str] | None = None,
) -> list[str] | None:
    """Parse a delimited list from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name
    delimiter : str
        Delimiter to split on (default: comma)
    default : list[str] | None
        Default value if not found

    Returns
    -------
    list[str] | None
        Parsed list or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    if not raw.strip():
        return []

    parts = raw.split(delimiter)
    return [p.strip() for p in parts if p.strip()]


def read_path(name: str, default: Path | None = None) -> Path | None:
    """Read an environment variable as a Path object.

    Parameters
    ----------
    name : str
        Environment variable name
    default : Path | None
        Default path if not found

    Returns
    -------
    Path | None
        Path object or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    value = raw.strip()
    if not value:
        return default

    return Path(value).expanduser()


def read_url(name: str, default: str | None = None) -> str | None:
    """Read an environment variable as a URL with basic validation.

    Parameters
    ----------
    name : str
        Environment variable name
    default : str | None
        Default URL if not found or invalid

    Returns
    -------
    str | None
        Valid URL or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default

    url = raw.strip()
    if not url:
        return default

    # Basic URL validation
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return url
    except Exception as e:
        logger.debug("Invalid URL format '%s': %s", url, e)

    return default


def read_json(name: str, default: T | None = None) -> T | None:
    """Parse JSON from an environment variable.

    Parameters
    ----------
    name : str
        Environment variable name
    default : T | None
        Default value if not found or invalid JSON

    Returns
    -------
    T | None
        Parsed JSON data or default
    """
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


# Backward compatibility aliases - keep original function names
get_str = read_str
get_bool = read_bool
get_int = read_int
get_float = read_float
get_list = read_list
get_json = read_json


def get_enum(name: str, allowed: Iterable[str], default: str) -> str:
    """Get an environment variable constrained to a set of allowed values.

    This is the legacy version. Use read_enum() for new code.

    Parameters
    ----------
    name : str
        Environment variable name
    allowed : Iterable[str]
        Allowed values
    default : str
        Default value

    Returns
    -------
    str
        Validated value or default
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    allowed_lower = {a.lower() for a in allowed}
    return raw if raw.lower() in allowed_lower else default
