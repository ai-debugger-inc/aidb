"""Python-specific target resolution.

Handles detection and normalization of Python debug targets including:
- Explicit module syntax: "-m pytest" → "pytest"
- Bare module names: "pytest" → "pytest" (module mode)
- File paths: "script.py" → "script.py" (file mode)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aidb.adapters.base.target_resolver import (
    ResolvedTarget,
    TargetResolver,
    TargetType,
)

if TYPE_CHECKING:
    from aidb.adapters.lang.python.python import PythonAdapter


class PythonTargetResolver(TargetResolver):
    """Target resolver for Python debugging.

    Detection rules (in order):
    1. "-m module" syntax → extract module name, enable module mode
    2. File path (/, \\, .py extension, or exists) → file mode
    3. Bare identifier (pytest, unittest, etc.) → assume module mode
    """

    adapter: PythonAdapter

    def resolve(self, target: str) -> ResolvedTarget:
        """Resolve Python target.

        Parameters
        ----------
        target : str
            Raw target from user/agent

        Returns
        -------
        ResolvedTarget
            Normalized target with type information
        """
        # Already in module mode (set via kwargs or launch config)
        if self.adapter.module:
            return ResolvedTarget(
                target=target,
                target_type=TargetType.MODULE,
                original_target=target,
                metadata={"module_mode": True},
            )

        # 1. Explicit "-m module" syntax
        if target.startswith("-m "):
            module_name = target[3:].strip()
            if module_name:
                # Extract first word (module name) if there are additional args
                module_name = module_name.split()[0]
                self.adapter.module = True
                self.ctx.debug(
                    f"Target resolution: '-m' syntax detected, "
                    f"'{target}' -> module='{module_name}'",
                )
                return ResolvedTarget(
                    target=module_name,
                    target_type=TargetType.MODULE,
                    original_target=target,
                    metadata={"module_mode": True},
                )
            # Empty module name after "-m " - return as-is
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={},
            )

        # 2. Check if it's a file path
        if self._is_file_path(target):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={},
            )

        # 3. Check if file exists (could be relative path without extension)
        if Path(target).exists():
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={},
            )

        # 4. Bare identifier - assume module (pytest, unittest, flask, etc.)
        self.adapter.module = True
        self.ctx.debug(
            f"Target resolution: bare identifier '{target}' detected as module",
        )
        return ResolvedTarget(
            target=target,
            target_type=TargetType.MODULE,
            original_target=target,
            metadata={"module_mode": True},
        )
