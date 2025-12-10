"""JavaScript/TypeScript-specific target resolution.

Handles detection and normalization of JavaScript debug targets. JavaScript targets are
typically file paths (.js, .ts, .mjs, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aidb.adapters.base.target_resolver import (
    ResolvedTarget,
    TargetResolver,
    TargetType,
)

if TYPE_CHECKING:
    from aidb.adapters.lang.javascript.javascript import JavaScriptAdapter


class JavaScriptTargetResolver(TargetResolver):
    """Target resolver for JavaScript/TypeScript debugging.

    JavaScript targets are typically file paths. This resolver performs minimal
    transformation, primarily classifying targets by type.
    """

    adapter: JavaScriptAdapter

    def resolve(self, target: str) -> ResolvedTarget:
        """Resolve JavaScript target.

        Parameters
        ----------
        target : str
            Raw target from user/agent

        Returns
        -------
        ResolvedTarget
            Normalized target with type information
        """
        # JavaScript targets are typically files
        if self._is_file_path(target):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={},
            )

        # Default: assume file (JavaScript doesn't have module mode like Python)
        return ResolvedTarget(
            target=target,
            target_type=TargetType.FILE,
            original_target=target,
            metadata={},
        )
