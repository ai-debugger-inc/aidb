"""Response size limiting for token efficiency.

This module provides systematic size limiting for MCP responses to prevent token
explosion from large data structures like deep call stacks.
"""

from __future__ import annotations

from typing import Any

from aidb_common.config.runtime import ConfigManager
from aidb_mcp.utils.token_estimation import estimate_tokens

__all__ = ["ResponseLimiter"]


class ResponseLimiter:
    """Applies size limits to MCP responses based on configuration."""

    @classmethod
    def limit_stack_frames(
        cls,
        frames: list[dict[str, Any]],
        max_frames: int | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Limit stack frames to configured maximum.

        Parameters
        ----------
        frames : list[dict]
            Stack frames to limit
        max_frames : int, optional
            Maximum frames (defaults to config)

        Returns
        -------
        tuple[list[dict], bool]
            (limited_frames, was_truncated)
        """
        if max_frames is None:
            max_frames = ConfigManager().get_mcp_max_stack_frames()

        if len(frames) <= max_frames:
            return frames, False

        # Take first N frames (most recent/relevant)
        limited = frames[:max_frames]
        return limited, True

    @classmethod
    def limit_variables(
        cls,
        variables: list[dict[str, Any]],
        max_vars: int | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Limit variables to configured maximum.

        Parameters
        ----------
        variables : list[dict]
            Variables to limit
        max_vars : int, optional
            Maximum variables (defaults to config)

        Returns
        -------
        tuple[list[dict], bool]
            (limited_variables, was_truncated)
        """
        if max_vars is None:
            max_vars = ConfigManager().get_mcp_max_variables()

        if len(variables) <= max_vars:
            return variables, False

        # Take first N variables
        limited = variables[:max_vars]
        return limited, True

    @classmethod
    def limit_threads(
        cls,
        threads: dict[int, Any],
        max_threads: int | None = None,
        current_thread_id: int | None = None,
    ) -> tuple[dict[int, Any], bool]:
        """Limit threads to configured maximum, prioritizing current thread.

        Parameters
        ----------
        threads : dict[int, Any]
            Threads dict (thread_id -> thread_data)
        max_threads : int, optional
            Maximum threads (defaults to config)
        current_thread_id : int, optional
            Current/stopped thread ID to prioritize

        Returns
        -------
        tuple[dict[int, Any], bool]
            (limited_threads, was_truncated)
        """
        if max_threads is None:
            max_threads = ConfigManager().get_mcp_max_threads()

        if len(threads) <= max_threads:
            return threads, False

        # Prioritize current thread (the one that triggered the stop)
        limited: dict[int, Any] = {}
        if current_thread_id is not None and current_thread_id in threads:
            limited[current_thread_id] = threads[current_thread_id]

        # Fill remaining slots
        for tid, tdata in threads.items():
            if len(limited) >= max_threads:
                break
            if tid not in limited:
                limited[tid] = tdata

        return limited, True

    @classmethod
    def limit_code_context(
        cls,
        lines: list[tuple[int, str]],
        current_line: int,
        context_lines: int | None = None,
    ) -> list[tuple[int, str]]:
        """Limit code context to N lines before/after current line.

        Parameters
        ----------
        lines : list[tuple[int, str]]
            Lines as (line_number, code) tuples
        current_line : int
            Current line number
        context_lines : int, optional
            Lines of context (defaults to config)

        Returns
        -------
        list[tuple[int, str]]
            Limited context
        """
        if context_lines is None:
            context_lines = ConfigManager().get_mcp_code_context_lines()

        # Find current line index
        current_idx = None
        for idx, (line_num, _) in enumerate(lines):
            if line_num == current_line:
                current_idx = idx
                break

        if current_idx is None:
            # Current line not found, return first N lines
            return lines[: context_lines * 2 + 1]

        # Get context window around current line
        start = max(0, current_idx - context_lines)
        end = min(len(lines), current_idx + context_lines + 1)

        return lines[start:end]

    @classmethod
    def apply_token_budget(
        cls,
        data: Any,
        max_tokens: int,
    ) -> tuple[Any, bool]:
        """Truncate data to fit within token budget.

        Parameters
        ----------
        data : Any
            Data to potentially truncate
        max_tokens : int
            Maximum tokens allowed

        Returns
        -------
        tuple[Any, bool]
            (data_or_truncated, was_truncated)
        """
        current_tokens = estimate_tokens(str(data), method="simple")

        if current_tokens is None or current_tokens <= max_tokens:
            return data, False

        # Token budget exceeded - need to truncate
        # For now, just indicate truncation
        # Full implementation would intelligently truncate
        return data, True  # Will enhance in Phase 3
