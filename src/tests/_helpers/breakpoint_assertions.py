"""Shared breakpoint assertion helpers for multi-language tests.

This module provides common assertion utilities for breakpoint-related tests, ensuring
consistent validation across test_breakpoint_multilang.py and
test_auto_breakpoint_multilang.py.
"""

from typing import Any, Optional


class BreakpointAssertions:
    """Common assertions for breakpoint functionality."""

    @staticmethod
    def assert_breakpoint_response_structure(
        response: dict[str, Any],
        check_auto_breakpoint: bool = False,
    ) -> None:
        """Assert that a breakpoint response has the expected structure.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from breakpoint or session_start operation
        check_auto_breakpoint : bool
            Whether to check for auto-breakpoint fields
        """
        assert "success" in response, "Response missing success field"
        assert "data" in response, "Response missing data field"

        data = response["data"]

        if check_auto_breakpoint:
            # Auto-breakpoint specific fields
            assert "auto_breakpoint_set" in data, "Missing auto_breakpoint_set field"
            assert isinstance(
                data["auto_breakpoint_set"],
                bool,
            ), "auto_breakpoint_set must be boolean"

            if data["auto_breakpoint_set"]:
                assert "auto_breakpoint_location" in data, (
                    "Missing auto_breakpoint_location when auto_breakpoint_set is True"
                )
                assert data["auto_breakpoint_location"] is not None, (
                    "auto_breakpoint_location should not be None when set"
                )

                # Check location format
                location = data["auto_breakpoint_location"]
                assert ":" in location, f"Invalid location format: {location}"
                parts = location.rsplit(":", 1)
                assert len(parts) == 2, f"Invalid location format: {location}"
                assert parts[1].isdigit(), f"Line number must be numeric: {parts[1]}"

    @staticmethod
    def assert_breakpoint_set_response(
        response: dict[str, Any],
        expected_location: str | None = None,
        expected_verified: bool = True,
        expected_condition: str | None = None,
        expected_hit_condition: str | None = None,
        expected_log_message: str | None = None,
    ) -> None:
        """Assert that a breakpoint set response is valid.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from breakpoint set operation
        expected_location : str, optional
            Expected breakpoint location
        expected_verified : bool
            Whether breakpoint should be verified
        expected_condition : str, optional
            Expected condition expression
        expected_hit_condition : str, optional
            Expected hit condition
        expected_log_message : str, optional
            Expected log message for logpoint
        """
        assert response.get("success"), f"Breakpoint set failed: {response}"
        assert "data" in response, "Response missing data field"

        data = response["data"]

        # Required fields for set operation
        assert "location" in data, "Breakpoint response missing location field"
        assert "verified" in data, "Breakpoint response missing verified field"

        # Type checks
        assert isinstance(data["verified"], bool), "verified must be boolean"
        assert isinstance(data["location"], str), "location must be string"

        # Value checks
        if expected_location:
            assert expected_location in data["location"] or data["location"].endswith(
                expected_location,
            ), (
                f"Location mismatch: expected '{expected_location}' in '{data['location']}'"
            )

        assert data["verified"] == expected_verified, (
            f"Verified mismatch: expected {expected_verified}, got {data['verified']}"
        )

        if expected_condition:
            assert "condition" in data, "Missing condition field"
            assert data["condition"] == expected_condition, (
                f"Condition mismatch: expected '{expected_condition}', "
                f"got '{data['condition']}'"
            )

        if expected_hit_condition:
            assert "hit_condition" in data, "Missing hit_condition field"
            assert data["hit_condition"] == expected_hit_condition, (
                f"Hit condition mismatch: expected '{expected_hit_condition}', "
                f"got '{data['hit_condition']}'"
            )

        if expected_log_message:
            assert "log_message" in data, "Missing log_message field"
            assert data["log_message"] == expected_log_message, (
                f"Log message mismatch: expected '{expected_log_message}', "
                f"got '{data['log_message']}'"
            )

    @staticmethod
    def _validate_breakpoint_count(
        breakpoints: list[dict[str, Any]],
        min_count: int | None,
        max_count: int | None,
    ) -> None:
        """Validate the number of breakpoints.

        Parameters
        ----------
        breakpoints : List[Dict[str, Any]]
            List of breakpoints
        min_count : int, optional
            Minimum expected number
        max_count : int, optional
            Maximum expected number
        """
        if min_count is not None:
            assert len(breakpoints) >= min_count, (
                f"Expected at least {min_count} breakpoints, got {len(breakpoints)}"
            )

        if max_count is not None:
            assert len(breakpoints) <= max_count, (
                f"Expected at most {max_count} breakpoints, got {len(breakpoints)}"
            )

    @staticmethod
    def _validate_breakpoint_structure(bp: dict[str, Any]) -> None:
        """Validate individual breakpoint structure.

        Parameters
        ----------
        bp : Dict[str, Any]
            Breakpoint to validate
        """
        assert isinstance(bp, dict), f"Breakpoint must be dict, got {type(bp)}"

        # Must have either location or file+line
        has_location = "location" in bp
        has_file_line = "file" in bp or ("source" in bp and "line" in bp)
        assert has_location or has_file_line, f"Breakpoint missing location info: {bp}"

        if "line" in bp:
            assert isinstance(bp["line"], int), "line must be integer"
            assert bp["line"] > 0, "line must be positive"

        if "verified" in bp:
            assert isinstance(bp["verified"], bool), "verified must be boolean"

    @staticmethod
    def _extract_location(bp: dict[str, Any]) -> str | None:
        """Extract location string from a breakpoint.

        Parameters
        ----------
        bp : Dict[str, Any]
            Breakpoint data

        Returns
        -------
        str | None
            Location string or None
        """
        if "location" in bp:
            return bp["location"]
        if "source" in bp and "line" in bp:
            path = bp["source"].get("path", "")
            return f"{path}:{bp['line']}"
        if "file" in bp and "line" in bp:
            return f"{bp['file']}:{bp['line']}"
        return None

    @staticmethod
    def _validate_expected_locations(
        breakpoints: list[dict[str, Any]],
        expected_locations: list[str],
    ) -> None:
        """Validate that expected locations are present.

        Parameters
        ----------
        breakpoints : List[Dict[str, Any]]
            List of breakpoints
        expected_locations : List[str]
            Expected locations
        """
        actual_locations = []
        for bp in breakpoints:
            loc = BreakpointAssertions._extract_location(bp)
            if loc:
                actual_locations.append(loc)

        for expected_loc in expected_locations:
            found = any(
                expected_loc in loc or loc.endswith(expected_loc)
                for loc in actual_locations
            )
            assert found, (
                f"Expected location '{expected_loc}' not found in {actual_locations}"
            )

    @staticmethod
    def assert_breakpoint_list_response(
        response: dict[str, Any],
        min_count: int | None = None,
        max_count: int | None = None,
        expected_locations: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Assert that a breakpoint list response is valid.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from breakpoint list operation
        min_count : int, optional
            Minimum expected number of breakpoints
        max_count : int, optional
            Maximum expected number of breakpoints
        expected_locations : List[str], optional
            Expected breakpoint locations

        Returns
        -------
        List[Dict[str, Any]]
            List of breakpoints from response
        """
        assert response.get("success"), f"Breakpoint list failed: {response}"
        assert "data" in response, "Response missing data field"
        assert "breakpoints" in response["data"], "Response missing breakpoints field"

        breakpoints = response["data"]["breakpoints"]
        assert isinstance(breakpoints, list), "breakpoints must be a list"

        # Validate count
        BreakpointAssertions._validate_breakpoint_count(
            breakpoints,
            min_count,
            max_count,
        )

        # Validate each breakpoint structure
        for bp in breakpoints:
            BreakpointAssertions._validate_breakpoint_structure(bp)

        # Validate expected locations
        if expected_locations:
            BreakpointAssertions._validate_expected_locations(
                breakpoints,
                expected_locations,
            )

        return breakpoints

    @staticmethod
    def assert_breakpoint_clear_all_response(
        response: dict[str, Any],
        expected_cleared: int | None = None,
    ) -> None:
        """Assert that a clear all breakpoints response is valid.

        Parameters
        ----------
        response : Dict[str, Any]
            Response from clear all operation
        expected_cleared : int, optional
            Expected number of cleared breakpoints
        """
        assert response.get("success"), f"Clear all failed: {response}"
        assert "data" in response, "Response missing data field"

        data = response["data"]

        # Should have one of these fields indicating what was cleared
        has_cleared = "cleared" in data
        has_count = "cleared_count" in data
        has_breakpoints = "breakpoints" in data  # Some return empty list

        assert has_cleared or has_count or has_breakpoints, (
            "Response missing cleared/cleared_count/breakpoints field"
        )

        if has_count:
            assert isinstance(
                data["cleared_count"],
                int,
            ), "cleared_count must be integer"
            assert data["cleared_count"] >= 0, "cleared_count must be non-negative"

            if expected_cleared is not None:
                assert data["cleared_count"] == expected_cleared, (
                    f"Expected {expected_cleared} cleared, got {data['cleared_count']}"
                )

        if has_breakpoints:
            assert isinstance(data["breakpoints"], list), "breakpoints must be list"
            assert len(data["breakpoints"]) == 0, (
                "breakpoints should be empty after clear_all"
            )

    @staticmethod
    def assert_session_auto_breakpoint_fields(
        response: dict[str, Any],
        expected_auto_breakpoint: bool,
    ) -> None:
        """Assert auto-breakpoint fields in session start response.

        Parameters
        ----------
        response : Dict[str, Any]
            Session start response
        expected_auto_breakpoint : bool
            Whether auto-breakpoint should be set
        """
        assert "data" in response, "Response missing data field"
        data = response["data"]

        # Check required auto-breakpoint fields
        assert "auto_breakpoint_set" in data, "Missing auto_breakpoint_set field"
        assert isinstance(
            data["auto_breakpoint_set"],
            bool,
        ), "auto_breakpoint_set must be boolean"

        assert data["auto_breakpoint_set"] == expected_auto_breakpoint, (
            f"Expected auto_breakpoint_set={expected_auto_breakpoint}, "
            f"got {data['auto_breakpoint_set']}"
        )

        if expected_auto_breakpoint:
            assert "auto_breakpoint_location" in data, (
                "Missing auto_breakpoint_location when auto-breakpoint is set"
            )
            assert data["auto_breakpoint_location"] is not None, (
                "auto_breakpoint_location should not be None"
            )

            # Validate location format
            location = data["auto_breakpoint_location"]
            assert isinstance(location, str), "auto_breakpoint_location must be string"
            assert ":" in location, f"Invalid location format: {location}"

            # Check the optional auto_breakpoint dict
            if "auto_breakpoint" in data:
                auto_bp = data["auto_breakpoint"]
                assert isinstance(auto_bp, dict), "auto_breakpoint must be dict"
                assert auto_bp.get("set") is True, "auto_breakpoint.set should be True"
                assert "location" in auto_bp, "auto_breakpoint missing location"
                assert auto_bp["location"] == location, (
                    "auto_breakpoint.location mismatch"
                )
        else:
            # When not set, location should be None or missing
            if "auto_breakpoint_location" in data:
                assert data["auto_breakpoint_location"] is None, (
                    "auto_breakpoint_location should be None when not set"
                )

    @staticmethod
    def find_breakpoint_in_list(
        breakpoints: list[dict[str, Any]],
        line: int,
        file_path: str | None = None,
        condition: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a specific breakpoint in a list.

        Parameters
        ----------
        breakpoints : List[Dict[str, Any]]
            List of breakpoints
        line : int
            Line number to find
        file_path : str, optional
            File path to match (partial match)
        condition : str, optional
            Condition to match

        Returns
        -------
        Dict[str, Any] or None
            The matching breakpoint or None if not found
        """
        for bp in breakpoints:
            # Check line number
            bp_line = bp.get("line")
            if bp_line != line:
                continue

            # Check file if specified
            if file_path:
                bp_path = ""
                if "location" in bp:
                    bp_path = bp["location"].rsplit(":", 1)[0]
                elif "source" in bp:
                    bp_path = bp["source"].get("path", "")
                elif "file" in bp:
                    bp_path = bp["file"]

                if file_path not in bp_path:
                    continue

            # Check condition if specified
            if condition and bp.get("condition") != condition:
                continue

            return bp

        return None

    @staticmethod
    def assert_breakpoint_exists(
        breakpoints: list[dict[str, Any]],
        line: int,
        file_path: str | None = None,
        verified: bool | None = None,
    ) -> None:
        """Assert that a specific breakpoint exists in the list.

        Parameters
        ----------
        breakpoints : List[Dict[str, Any]]
            List of breakpoints
        line : int
            Expected line number
        file_path : str, optional
            Expected file path (partial match)
        verified : bool, optional
            Expected verification status
        """
        bp = BreakpointAssertions.find_breakpoint_in_list(breakpoints, line, file_path)

        assert bp is not None, f"Breakpoint not found at line {line}" + (
            f" in {file_path}" if file_path else ""
        )

        if verified is not None and "verified" in bp:
            assert bp["verified"] == verified, (
                f"Expected verified={verified}, got {bp['verified']}"
            )

    @staticmethod
    def assert_no_duplicate_breakpoints(breakpoints: list[dict[str, Any]]) -> None:
        """Assert that there are no duplicate breakpoints in the list.

        Parameters
        ----------
        breakpoints : List[Dict[str, Any]]
            List of breakpoints to check
        """
        seen_locations = set()

        for bp in breakpoints:
            # Build a unique identifier for this breakpoint
            if "location" in bp:
                loc = bp["location"]
            elif "source" in bp and "line" in bp:
                path = bp["source"].get("path", "unknown")
                loc = f"{path}:{bp['line']}"
            elif "file" in bp and "line" in bp:
                loc = f"{bp['file']}:{bp['line']}"
            else:
                continue  # Can't determine location

            assert loc not in seen_locations, f"Duplicate breakpoint found at {loc}"
            seen_locations.add(loc)
