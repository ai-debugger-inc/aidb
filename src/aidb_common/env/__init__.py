"""Environment variable resolution utilities.

Provides robust, reusable environment variable resolution that handles template files
with ${VAR} substitution syntax, plus typed environment variable readers.
"""

from .reader import (
    read_bool,
    read_enum,
    read_float,
    read_int,
    read_json,
    read_list,
    read_path,
    read_str,
    read_url,
)
from .resolver import apply_env_template_to_environ, resolve_env_template

__all__ = [
    "resolve_env_template",
    "apply_env_template_to_environ",
    "read_str",
    "read_bool",
    "read_int",
    "read_float",
    "read_enum",
    "read_list",
    "read_path",
    "read_url",
    "read_json",
]
