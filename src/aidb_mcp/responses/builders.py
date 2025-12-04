"""Response builder utilities for constructing standardized response components.

This module provides builder classes that eliminate duplication in response
construction. These builders are the single source of truth for building execution_state
and code_snapshot dicts across all response classes.
"""

from __future__ import annotations

from typing import Any

from ..core.constants import DetailedExecutionStatus, ResponseFieldName


class ExecutionStateBuilder:
    """Builds standardized execution_state dicts for responses.

    This builder eliminates ~140 lines of duplicated code across:
    - ExecuteResponse
    - StepResponse
    - RunUntilResponse
    - SessionStartResponse
    - SessionStatusResponse
    """

    @staticmethod
    def build(
        detailed_status: DetailedExecutionStatus,
        location: str | None = None,  # noqa: ARG004 - kept for API compatibility
        has_breakpoints: bool = False,
        stop_reason: str | None = None,
    ) -> dict[str, Any]:
        """Build standardized execution_state dict.

        Parameters
        ----------
        detailed_status : DetailedExecutionStatus
            The detailed execution status enum
        location : str, optional
            Current location in format "file.py:123"
        has_breakpoints : bool
            Whether breakpoints are active
        stop_reason : str, optional
            Reason for stop (e.g., "breakpoint", "step", "exception")

        Returns
        -------
        dict
            Standardized execution_state dict with fields::

                {
                    "status": "stopped_at_breakpoint",
                    "breakpoints_active": true,
                    "stop_reason": "breakpoint"
                }
        """
        return {
            ResponseFieldName.STATUS: detailed_status.value,
            ResponseFieldName.BREAKPOINTS_ACTIVE: has_breakpoints,
            ResponseFieldName.STOP_REASON: stop_reason,
        }


class CodeSnapshotBuilder:
    """Builds standardized code_snapshot dicts for responses.

    This builder eliminates ~80 lines of duplicated code across:
    - ExecuteResponse
    - StepResponse
    - RunUntilResponse
    - SessionStartResponse
    """

    @staticmethod
    def build(
        code_context: dict[str, Any] | None,
        location: str | None = None,  # noqa: ARG004 - kept for API compatibility
        fallback_target: str | None = None,  # noqa: ARG004 - kept for API compatibility
    ) -> dict[str, Any] | None:
        """Build standardized code_snapshot dict.

        Parameters
        ----------
        code_context : dict or None
            Code context result with 'formatted' key
        location : str, optional
            Current location in format "file.py:123" (kept for API compatibility)
        fallback_target : str, optional
            Fallback file path (kept for API compatibility)

        Returns
        -------
        dict or None
            Standardized code_snapshot dict with fields::

                {
                    "formatted": "..."
                }

            Returns None if no code_context available.

        Notes
        -----
        Location information is available in data.location at the response level,
        so we don't duplicate it here (file/line fields removed in Phase 2).
        """
        if not code_context:
            return None

        return {
            ResponseFieldName.FORMATTED: code_context.get(
                ResponseFieldName.FORMATTED,
                "",
            ),
        }
