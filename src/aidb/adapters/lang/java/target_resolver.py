"""Java-specific target resolution.

Handles detection and normalization of Java debug targets including:
- Source files: "Main.java" → FILE type (needs compilation)
- Compiled classes: "Main.class" → CLASS type
- JAR files: "app.jar" → EXECUTABLE type
- Qualified class names: "com.example.Main" → CLASS type
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aidb.adapters.base.target_resolver import (
    ResolvedTarget,
    TargetResolver,
    TargetType,
)

if TYPE_CHECKING:
    from aidb.adapters.lang.java.java import JavaAdapter


class JavaTargetResolver(TargetResolver):
    """Target resolver for Java debugging.

    Detection rules (in order):
    1. .java file → FILE type (source, needs compilation)
    2. .class file → CLASS type (compiled bytecode)
    3. .jar file → EXECUTABLE type
    4. File path with separators → FILE type
    5. Qualified class name (contains dots) → CLASS type
    6. Default → FILE type
    """

    adapter: JavaAdapter

    def resolve(self, target: str) -> ResolvedTarget:
        """Resolve Java target.

        Parameters
        ----------
        target : str
            Raw target from user/agent

        Returns
        -------
        ResolvedTarget
            Normalized target with type information
        """
        # 1. Java source file
        if target.endswith(".java"):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={"needs_compilation": True},
            )

        # 2. Compiled class file
        if target.endswith(".class"):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.CLASS,
                original_target=target,
                metadata={},
            )

        # 3. JAR file
        if target.endswith(".jar"):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.EXECUTABLE,
                original_target=target,
                metadata={},
            )

        # 4. File path with separators
        if self._is_file_path(target):
            return ResolvedTarget(
                target=target,
                target_type=TargetType.FILE,
                original_target=target,
                metadata={},
            )

        # 5. Qualified class name (contains dots but no path separators)
        # e.g., "com.example.Main" or "Main"
        if "." in target and "/" not in target and "\\" not in target:
            return ResolvedTarget(
                target=target,
                target_type=TargetType.CLASS,
                original_target=target,
                metadata={"qualified_class_name": True},
            )

        # 6. Default: assume file (simple class name or unknown)
        return ResolvedTarget(
            target=target,
            target_type=TargetType.FILE,
            original_target=target,
            metadata={},
        )
