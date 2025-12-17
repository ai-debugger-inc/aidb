"""AidbBreakpoint-specific utilities for validation and conversion."""

import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, cast

from aidb.common.constants import BREAKPOINT_VALIDATION_DISABLE_MSG
from aidb.common.errors import AidbError
from aidb.dap.protocol.bodies import SetBreakpointsArguments
from aidb.dap.protocol.requests import SetBreakpointsRequest
from aidb.dap.protocol.types import Source, SourceBreakpoint
from aidb.models.entities.breakpoint import BreakpointSpec, HitConditionMode
from aidb_common.config import config
from aidb_common.path import normalize_path

if TYPE_CHECKING:
    from aidb.adapters.base import DebugAdapter


def _get_adapter_name_and_class(adapter: "DebugAdapter") -> tuple[str, str]:
    """Extract adapter name and class name from adapter instance or class.

    Parameters
    ----------
    adapter : DebugAdapter
        Adapter instance or class

    Returns
    -------
    tuple[str, str]
        (adapter_name, adapter_class_name) where adapter_class_name is the base name
        without 'Adapter' suffix (e.g., 'Java', 'Python', 'JavaScript')
    """
    if inspect.isclass(adapter):
        # adapter is a class itself
        class_name = adapter.__name__
    else:
        # adapter is an instance
        class_name = adapter.__class__.__name__

    # Remove 'Adapter' suffix to get base name (e.g., 'JavaAdapter' -> 'Java')
    adapter_class_name = class_name.replace("Adapter", "")
    adapter_name = adapter_class_name.lower()

    return adapter_name, adapter_class_name


def validate_breakpoint_line(
    file_path: str,
    line_num: int,
    adapter: Optional["DebugAdapter"] = None,
) -> tuple[bool, str]:
    """Validate if a line can have a breakpoint.

    Parameters
    ----------
    file_path : str
        Path to the source file
    line_num : int
        Line number (1-based)
    adapter : Optional[DebugAdapter]
        Adapter instance or class for language-specific checks

    Returns
    -------
    Tuple[bool, str]
        (is_valid, reason)
    """
    try:
        with Path(file_path).open() as f:
            lines = f.readlines()

        if line_num < 1 or line_num > len(lines):
            return False, (
                f"Line {line_num} is out of range (file has {len(lines)} lines). "
                f"{BREAKPOINT_VALIDATION_DISABLE_MSG}"
            )

        line_content = lines[line_num - 1]
        stripped = line_content.strip()

        # Universal check: blank lines
        if not stripped:
            return False, (
                f"Line {line_num} is blank and cannot have a breakpoint. "
                f"{BREAKPOINT_VALIDATION_DISABLE_MSG}"
            )

        # Language-specific checks if adapter provided
        if adapter:
            # Get non_executable_patterns from adapter config
            # Handle both adapter instances and classes
            patterns = []
            if hasattr(adapter, "config"):
                # It's an instance
                patterns = adapter.config.non_executable_patterns
            else:
                # It's a class, try to get default config
                try:
                    # Try to get the config class from the adapter module
                    import importlib

                    # Get adapter name from class name
                    adapter_name, adapter_class_name = _get_adapter_name_and_class(
                        adapter,
                    )
                    config_module = importlib.import_module(
                        f"aidb.adapters.lang.{adapter_name}.config",
                    )
                    # Config class follows pattern: {ClassName}AdapterConfig
                    config_class = getattr(
                        config_module,
                        f"{adapter_class_name}AdapterConfig",
                    )
                    default_config = config_class()
                    patterns = default_config.non_executable_patterns
                except Exception as e:
                    msg = (
                        f"Failed to get adapter config for "
                        f"language-specific validation: {e}"
                    )
                    logging.debug(msg)

            # Check against patterns
            for pattern in patterns:
                if stripped.startswith(pattern):
                    # Found a non-executable pattern match
                    return False, (
                        f"Line {line_num} does not appear to be executable code "
                        f"(matches pattern: {pattern!r}). "
                        f"{BREAKPOINT_VALIDATION_DISABLE_MSG}"
                    )

            # No pattern matched, line is executable
            return True, "OK"

        return True, "OK"

    except FileNotFoundError:
        return False, f"File not found: {file_path}"
    except Exception as e:
        return False, f"Error reading file: {e}"


def _validate_required_fields(spec: dict[str, Any]) -> None:
    """Validate that required fields are present in spec.

    Parameters
    ----------
    spec : dict[str, Any]
        Breakpoint specification to validate

    Raises
    ------
    AidbError
        If required fields are missing
    """
    if "file" not in spec:
        msg = "Breakpoint spec must include 'file' field"
        raise AidbError(msg)
    if "line" not in spec:
        msg = "Breakpoint spec must include 'line' field"
        raise AidbError(msg)


def _validate_line_number(spec: dict[str, Any]) -> None:
    """Validate that line number is a positive integer.

    Parameters
    ----------
    spec : dict[str, Any]
        Breakpoint specification to validate

    Raises
    ------
    AidbError
        If line is not a positive integer
    """
    if not isinstance(spec["line"], int) or spec["line"] < 1:
        msg = f"Line must be a positive integer, got: {spec['line']}"
        raise AidbError(msg)


def _validate_column_number(spec: dict[str, Any]) -> None:
    """Validate column number if present.

    Parameters
    ----------
    spec : dict[str, Any]
        Breakpoint specification to validate

    Raises
    ------
    AidbError
        If column is not a positive integer
    """
    if (
        "column" in spec
        and spec["column"] is not None
        and (not isinstance(spec["column"], int) or spec["column"] < 1)
    ):
        msg = f"Column must be a positive integer, got: {spec['column']}"
        raise AidbError(msg)


def _validate_hit_condition(spec: dict[str, Any]) -> None:
    """Validate hit condition format if present.

    Parameters
    ----------
    spec : dict[str, Any]
        Breakpoint specification to validate

    Raises
    ------
    AidbError
        If hit condition has invalid format
    """
    if "hit_condition" in spec and spec["hit_condition"]:
        try:
            HitConditionMode.parse(spec["hit_condition"])
        except ValueError as e:
            msg = f"Invalid hit condition format: {e}"
            raise AidbError(msg) from e


def _add_optional_fields(validated: BreakpointSpec, spec: dict[str, Any]) -> None:
    """Add optional fields to validated spec if present.

    Parameters
    ----------
    validated : BreakpointSpec
        Validated spec to add fields to
    spec : dict[str, Any]
        Original specification with optional fields
    """
    optional_fields = [
        ("column", lambda v: v is not None),
        ("condition", lambda v: bool(v)),
        ("hit_condition", lambda v: bool(v)),
        ("log_message", lambda v: bool(v)),
    ]

    for field, check_fn in optional_fields:
        if field in spec and check_fn(spec[field]):
            validated[field] = spec[field]


def validate_breakpoint_spec(spec: dict[str, Any]) -> BreakpointSpec:
    """Validate and type-check a breakpoint specification.

    Parameters
    ----------
    spec : Dict[str, Any]
        Breakpoint specification to validate

    Returns
    -------
    BreakpointSpec
        Validated breakpoint specification

    Raises
    ------
    AidbError
        If required fields are missing or invalid
    """
    # Validate required and optional fields
    _validate_required_fields(spec)
    _validate_line_number(spec)
    _validate_column_number(spec)
    _validate_hit_condition(spec)

    # Create validated spec
    validated: BreakpointSpec = {
        "file": normalize_path(spec["file"]),
        "line": spec["line"],
    }

    # Add optional fields
    _add_optional_fields(validated, spec)

    return validated


def process_breakpoint_inputs(
    breakpoints: list[BreakpointSpec] | BreakpointSpec,
) -> list[BreakpointSpec]:
    """Process and normalize breakpoint inputs.

    Parameters
    ----------
    breakpoints : Union[List[BreakpointSpec], BreakpointSpec]
        Breakpoint specifications conforming to BreakpointSpec schema

    Returns
    -------
    List[BreakpointSpec]
        Validated list of breakpoint specifications

    Raises
    ------
    AidbError
        If breakpoint validation fails
    """
    # Convert single breakpoint to list
    if not isinstance(breakpoints, list):
        breakpoints = [breakpoints]

    # Validate each breakpoint
    validated_breakpoints: list[BreakpointSpec] = []
    for bp in breakpoints:
        if not isinstance(bp, dict):
            msg = (
                f"Breakpoint must be a dict conforming "
                f"to BreakpointSpec, got: {type(bp)}"
            )
            raise AidbError(
                msg,
            )
        # bp is confirmed to be a dict at this point, so cast is safe
        bp_dict = cast("dict[str, Any]", bp)
        validated_breakpoints.append(validate_breakpoint_spec(bp_dict))

    return validated_breakpoints


def _validate_breakpoints(
    breakpoints_by_source: dict[str, list[BreakpointSpec]],
    adapter: Optional["DebugAdapter"] = None,
) -> None:
    """Validate breakpoints if validation is enabled.

    Parameters
    ----------
    breakpoints_by_source : Dict[str, List[Dict[str, Any]]]
        Breakpoints grouped by source file
    adapter : Optional[DebugAdapter]
        Debug adapter for language-specific validation

    Raises
    ------
    ValueError
        If any breakpoint validation fails
    """
    if not config.is_breakpoint_validation_enabled():
        return

    for source_path, bps in breakpoints_by_source.items():
        for bp in bps:
            line_num = bp["line"]
            is_valid, reason = validate_breakpoint_line(source_path, line_num, adapter)
            if not is_valid:
                msg = f"Invalid breakpoint at {source_path}:{line_num} - {reason}"
                # Extract user-friendly summary from reason
                summary = None
                if "does not appear to be executable" in reason:
                    summary = "Line is not executable"
                elif "is out of range" in reason:
                    summary = "Line number out of range"
                elif "is blank and cannot have a breakpoint" in reason:
                    summary = "Cannot set breakpoint on blank line"
                elif "invalid breakpoint" in reason.lower():
                    summary = "Invalid breakpoint location"
                raise AidbError(
                    msg,
                    summary=summary,
                )


def _create_dap_request(
    source_path: str,
    breakpoints: list[BreakpointSpec],
) -> SetBreakpointsRequest:
    """Create a DAP SetBreakpointsRequest for a source file.

    Parameters
    ----------
    source_path : str
        Path to the source file
    breakpoints : List[Dict[str, Any]]
        List of breakpoint dicts for this source

    Returns
    -------
    SetBreakpointsRequest
        DAP protocol request
    """
    source = Source(path=source_path)
    source_breakpoints = []

    for bp in breakpoints:
        source_bp = SourceBreakpoint(
            line=bp["line"],
            column=bp.get("column"),  # Add column support for minified files
            condition=bp.get("condition"),
            hitCondition=bp.get("hit_condition"),  # Note: DAP uses camelCase
            logMessage=bp.get("log_message"),  # Note: DAP uses camelCase
        )
        source_breakpoints.append(source_bp)

    args = SetBreakpointsArguments(source=source, breakpoints=source_breakpoints)
    return SetBreakpointsRequest(seq=0, arguments=args)


def _group_breakpoints_by_source(
    breakpoints: list[BreakpointSpec],
) -> dict[str, list[BreakpointSpec]]:
    """Group breakpoints by their source file.

    Parameters
    ----------
    breakpoints : List[Dict[str, Any]]
        List of breakpoint dicts

    Returns
    -------
    Dict[str, List[Dict[str, Any]]]
        Breakpoints grouped by source path
    """
    breakpoints_by_source: dict[str, list[BreakpointSpec]] = {}
    for bp in breakpoints:
        source_path = bp["file"]
        if source_path not in breakpoints_by_source:
            breakpoints_by_source[source_path] = []
        breakpoints_by_source[source_path].append(bp)
    return breakpoints_by_source


def convert_breakpoints(
    breakpoints: list[BreakpointSpec],
    adapter: Optional["DebugAdapter"] = None,
) -> list[SetBreakpointsRequest]:
    """Convert breakpoint specifications to DAP SetBreakpointsRequest objects.

    Parameters
    ----------
    breakpoints : List[BreakpointSpec]
        List of breakpoint specifications conforming to BreakpointSpec schema
    adapter : Optional[DebugAdapter]
        Debug adapter for language-specific validation

    Returns
    -------
    List[SetBreakpointsRequest]
        List of DAP protocol requests ready to send to the session

    Raises
    ------
    AidbError
        If breakpoint validation fails and AIDB_VALIDATE_BREAKPOINTS is enabled
    """
    if not breakpoints:
        return []

    # Group breakpoints by source file
    breakpoints_by_source = _group_breakpoints_by_source(breakpoints)

    # Validate breakpoints if enabled
    _validate_breakpoints(breakpoints_by_source, adapter)

    # Create DAP requests for each source file
    dap_requests = []
    for source_path, bps in breakpoints_by_source.items():
        request = _create_dap_request(source_path, bps)
        dap_requests.append(request)

    return dap_requests
