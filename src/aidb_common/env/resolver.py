"""Shared environment variable resolution utilities.

Provides robust, thin environment variable resolution that can be used by both Docker
orchestration and pytest fixtures.
"""

import os
from pathlib import Path


def resolve_env_template(
    template_file: Path,
    strict: bool = False,
    critical_prefixes: tuple[str, ...] = ("AIDB_",),
) -> dict[str, str]:
    """Resolve environment variables from a template file.

    Supports shell variable substitution syntax like ${VAR} and direct values.

    Parameters
    ----------
    template_file : Path
        Path to .env.test or similar template file
    strict : bool
        If True, only include variables that fully resolve (no unresolved ${VAR})
        If False, include all variables, setting unresolved ones to empty string
    critical_prefixes : tuple[str, ...]
        Variable prefixes that should always be included even if unresolved

    Returns
    -------
    Dict[str, str]
        Resolved environment variables

    Examples
    --------
    Template file content:
        API_KEY=${API_KEY}
        DATABASE_URL=sqlite:///test.db
        MISSING_VAR=${UNDEFINED_VAR}

    With strict=False:
        {'API_KEY': 'secret_...', 'DATABASE_URL': 'sqlite:///test.db',
         'MISSING_VAR': ''}

    With strict=True:
        {'API_KEY': 'secret_...', 'DATABASE_URL': 'sqlite:///test.db'}
    """
    resolved_vars: dict[str, str] = {}

    if not template_file.exists():
        return resolved_vars

    with template_file.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Use os.path.expandvars for robust variable substitution
            resolved_value = os.path.expandvars(value)

            # Check if there are still unresolved variables
            has_unresolved_vars = "${" in resolved_value and "}" in resolved_value

            # Handle unresolved variables
            if has_unresolved_vars:
                # Check if this is a critical variable that should always be included
                is_critical = any(
                    key.startswith(prefix) for prefix in critical_prefixes
                )

                if strict and not is_critical:
                    # In strict mode, skip unresolved non-critical variables
                    continue
                # Include critical variables or in non-strict mode, set to empty
                resolved_vars[key] = ""
            else:
                # Successfully resolved or static value
                resolved_vars[key] = resolved_value

    return resolved_vars


def apply_env_template_to_environ(template_file: Path, strict: bool = False) -> int:
    """Resolve and apply environment template to os.environ.

    This is a convenience function that applies resolved variables directly
    to the current process environment.

    Parameters
    ----------
    template_file : Path
        Path to .env.test or similar template file
    strict : bool
        If True, only apply variables that fully resolve

    Returns
    -------
    int
        Number of variables that were applied to os.environ
    """
    resolved = resolve_env_template(template_file, strict=strict)

    for key, value in resolved.items():
        os.environ[key] = value

    return len(resolved)
