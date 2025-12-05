"""Target resolution for debug adapters.

Provides language-agnostic target resolution that normalizes and classifies debug
targets (file paths, module names, class identifiers) before launching.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aidb.patterns import Obj

if TYPE_CHECKING:
    from .adapter import DebugAdapter


class TargetType(Enum):
    """Type of debug target."""

    FILE = "file"  # Source file path (script.py, Main.java)
    MODULE = "module"  # Module/package name (pytest, http.server)
    CLASS = "class"  # Class identifier (com.example.Main)
    EXECUTABLE = "executable"  # Binary executable or JAR


@dataclass
class ResolvedTarget:
    """Result of target resolution.

    Attributes
    ----------
    target : str
        The normalized target string to use for launching
    target_type : TargetType
        The detected type of the target
    original_target : str
        The original target string before resolution
    metadata : dict
        Additional resolution metadata (e.g., module_mode flag)
    """

    target: str
    target_type: TargetType
    original_target: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TargetResolver(ABC, Obj):
    """Base class for language-specific target resolution.

    Each adapter implements a resolver to detect target type and normalize
    the target string. Resolution happens at the start of adapter.launch(),
    before any hooks or DAP operations.

    Parameters
    ----------
    adapter : DebugAdapter
        The debug adapter instance (provides access to adapter state like
        module flag)
    ctx : Any
        Context for logging
    """

    def __init__(self, adapter: DebugAdapter, ctx: Any | None = None):
        super().__init__(ctx=ctx or adapter.ctx)
        self.adapter = adapter

    @abstractmethod
    def resolve(self, target: str) -> ResolvedTarget:
        """Resolve and normalize target.

        Parameters
        ----------
        target : str
            Raw target from user/agent

        Returns
        -------
        ResolvedTarget
            Normalized target with type information
        """

    def _is_file_path(self, target: str) -> bool:
        """Check if target looks like a file path.

        Uses the adapter's config.file_extensions to detect known file types.

        Parameters
        ----------
        target : str
            The target string to check

        Returns
        -------
        bool
            True if target appears to be a file path
        """
        # Contains path separators
        if "/" in target or "\\" in target:
            return True
        # Has a known file extension from adapter config
        extensions = set(self.adapter.config.file_extensions)
        return Path(target).suffix.lower() in extensions
