"""Variable change tracking for debugging sessions.

This module provides utilities to track variable changes across debug inspections,
enabling better context for debugging operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aidb_logging import get_mcp_logger as get_logger

logger = get_logger(__name__)


class VariableTracker:
    """Track variable changes across debug inspections.

    Maintains a history of variable states to detect additions, removals, and
    modifications between inspection calls.
    """

    def __init__(self, max_history_size: int = 50):
        """Initialize the variable tracker.

        Parameters
        ----------
        max_history_size : int
            Maximum number of change records to keep in history
        """
        self._last_locals: dict[str, Any] = {}
        self._last_globals: dict[str, Any] = {}
        self._inspection_count: int = 0
        self._change_history: list[dict[str, Any]] = []
        self._max_history_size = max_history_size
        self._last_operation: str | None = None

        logger.debug(
            "Initialized variable tracker",
            extra={"max_history_size": max_history_size},
        )

    def _find_variable_changes(
        self,
        current_locals: dict[str, Any],
        changes: dict[str, Any],
    ) -> None:
        """Find added, modified, and removed variables.

        Parameters
        ----------
        current_locals : Dict[str, Any]
            Current local variables
        changes : Dict[str, Any]
            Dictionary to populate with changes
        """
        for name, current_value in current_locals.items():
            if name not in self._last_locals:
                changes["added"].append({"name": name, "value": str(current_value)})
            else:
                last_value = self._last_locals[name]
                # Compare string representations for complex objects
                if str(current_value) != str(last_value):
                    changes["modified"].append(
                        {
                            "name": name,
                            "old_value": str(last_value),
                            "new_value": str(current_value),
                        },
                    )
                else:
                    changes["unchanged"] += 1

        for name in self._last_locals:
            if name not in current_locals:
                changes["removed"].append(
                    {"name": name, "last_value": str(self._last_locals[name])},
                )

    def _create_history_entry(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Create a history entry from changes.

        Parameters
        ----------
        changes : Dict[str, Any]
            Current changes

        Returns
        -------
        Dict[str, Any]
            History entry
        """
        return {
            "timestamp": changes["timestamp"],
            "operation": changes["operation"],
            "location": changes["location"],
            "summary": (
                f"{len(changes['added'])} added, "
                f"{len(changes['removed'])} removed, "
                f"{len(changes['modified'])} modified"
            ),
            "changes": changes.copy(),
        }

    def _add_to_history(self, changes: dict[str, Any]) -> None:
        """Add changes to history if significant.

        Parameters
        ----------
        changes : Dict[str, Any]
            Current changes
        """
        if not any([changes["added"], changes["removed"], changes["modified"]]):
            return

        history_entry = self._create_history_entry(changes)
        self._change_history.append(history_entry)

        logger.info(
            "Variable changes detected",
            extra={
                "added_count": len(changes["added"]),
                "removed_count": len(changes["removed"]),
                "modified_count": len(changes["modified"]),
                "unchanged_count": changes["unchanged"],
                "operation": changes["operation"],
                "scope": "locals",
            },
        )

        self._trim_history_if_needed()

    def _trim_history_if_needed(self) -> None:
        """Trim history if it exceeds max size."""
        if len(self._change_history) > self._max_history_size:
            logger.debug(
                "Trimming variable history",
                extra={
                    "max_size": self._max_history_size,
                    "current_size": len(self._change_history),
                },
            )
            self._change_history.pop(0)

    def track_locals(
        self,
        current_locals: dict[str, Any],
        operation: str | None = None,
        location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Track changes in local variables.

        Parameters
        ----------
        current_locals : Dict[str, Any]
            Current local variables from debug session
        operation : Optional[str]
            The operation that triggered this tracking (e.g., "step_over",
            "breakpoint_hit")
        location : Optional[Dict[str, Any]]
            Current code location (file, line, function)

        Returns
        -------
        Dict[str, Any]
            Dictionary containing:
            - added: List of newly added variable names with values
            - removed: List of removed variable names
            - modified: List of modified variables with old/new values
            - unchanged: Count of unchanged variables
            - timestamp: When the change was recorded
            - operation: What operation caused the change
            - location: Where in the code this occurred
        """
        logger.debug(
            "Tracking local variables",
            extra={
                "variable_count": len(current_locals),
                "operation": operation,
                "inspection_count": self._inspection_count,
                "location": location,
            },
        )

        changes: dict[str, Any] = {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation or self._last_operation,
            "location": location,
            "inspection_count": self._inspection_count + 1,
        }

        if self._inspection_count > 0 and self._last_locals:
            self._find_variable_changes(current_locals, changes)
        elif self._inspection_count == 0:
            # First inspection - all variables are "new"
            changes["added"] = [
                {"name": k, "value": str(v)} for k, v in current_locals.items()
            ]

        self._last_locals = current_locals.copy()
        self._inspection_count += 1
        if operation:
            self._last_operation = operation

        self._add_to_history(changes)

        return changes

    def track_globals(
        self,
        current_globals: dict[str, Any],
        operation: str | None = None,
        location: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Track changes in global variables.

        Parameters
        ----------
        current_globals : Dict[str, Any]
            Current global variables from debug session
        operation : Optional[str]
            The operation that triggered this tracking
        location : Optional[Dict[str, Any]]
            Current code location

        Returns
        -------
        Dict[str, Any]
            Dictionary containing changes (same format as track_locals)
        """
        # Filter out built-ins and modules to focus on user variables
        filtered_globals = {
            k: v
            for k, v in current_globals.items()
            if not k.startswith("__") and not k.startswith("_")
        }

        logger.debug(
            "Tracking global variables",
            extra={
                "total_globals": len(current_globals),
                "filtered_globals": len(filtered_globals),
                "operation": operation,
                "location": location,
            },
        )

        changes: dict[str, Any] = {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation or self._last_operation,
            "location": location,
            "scope": "global",
        }

        if self._last_globals:
            for name, current_value in filtered_globals.items():
                if name not in self._last_globals:
                    changes["added"].append({"name": name, "value": str(current_value)})
                else:
                    last_value = self._last_globals[name]
                    if str(current_value) != str(last_value):
                        changes["modified"].append(
                            {
                                "name": name,
                                "old_value": str(last_value),
                                "new_value": str(current_value),
                            },
                        )
                    else:
                        changes["unchanged"] += 1

            for name in self._last_globals:
                if name not in filtered_globals:
                    changes["removed"].append(
                        {"name": name, "last_value": str(self._last_globals[name])},
                    )

        self._last_globals = filtered_globals.copy()

        if operation:
            self._last_operation = operation

        change_count = (
            len(changes["added"]) + len(changes["removed"]) + len(changes["modified"])
        )
        if change_count > 0:
            logger.info(
                "Global variable changes detected",
                extra={
                    "added_count": len(changes["added"]),
                    "removed_count": len(changes["removed"]),
                    "modified_count": len(changes["modified"]),
                    "unchanged_count": changes["unchanged"],
                    "operation": operation,
                    "scope": "globals",
                },
            )

        return changes

    def get_change_history(self) -> list[dict[str, Any]]:
        """Get the history of variable changes.

        Returns
        -------
        List[Dict[str, Any]]
            List of recent change dictionaries
        """
        logger.debug(
            "Retrieving change history",
            extra={"history_size": len(self._change_history)},
        )
        return self._change_history.copy()

    def reset(self):
        """Reset the tracker state."""
        logger.info(
            "Resetting variable tracker",
            extra={
                "locals_tracked": len(self._last_locals),
                "globals_tracked": len(self._last_globals),
                "inspection_count": self._inspection_count,
                "history_size": len(self._change_history),
            },
        )
        self._last_locals.clear()
        self._last_globals.clear()
        self._inspection_count = 0
        self._change_history.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of tracking state.

        Returns
        -------
        Dict[str, Any]
            Summary containing inspection count and change patterns
        """
        summary = {
            "inspection_count": self._inspection_count,
            "locals_tracked": len(self._last_locals),
            "globals_tracked": len(self._last_globals),
            "changes_recorded": len(self._change_history),
            "recent_changes": self._change_history[-3:] if self._change_history else [],
        }

        logger.debug(
            "Generated tracker summary",
            extra={
                "inspection_count": summary["inspection_count"],
                "locals_tracked": summary["locals_tracked"],
                "globals_tracked": summary["globals_tracked"],
                "changes_recorded": summary["changes_recorded"],
            },
        )

        return summary
