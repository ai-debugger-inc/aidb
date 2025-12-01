#!/usr/bin/env python3
"""DAP Protocol Multi-File Generator.

Generates DAP protocol classes split across multiple files for better
organization and maintainability. Creates separate files for requests,
responses, events, bodies, and types.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

# Import components from the existing generator
from _gen_protocol import (
    ClassSpec,
    CodeGenerator,
    DefinitionProcessor,
    DocstringFormatter,
    SpecificationLoader,
    TypeMapper,
)


@dataclass
class FileCategory:
    """Represents a category of protocol classes for a specific file."""

    name: str
    filename: str
    description: str
    base_imports: List[str]
    classes: List[ClassSpec]


class MultiFileGenerator(CodeGenerator):
    """Generator that outputs protocol classes to multiple files."""

    # Base classes that go in base.py
    BASE_CLASSES = {
        "ProtocolMessage",
        "Request",
        "Response",
        "Event",
        "DAPDataclass",
        "ImmutableAfterInit",
    }

    def __init__(self, spec_path: Path, protocol_dir: Path):
        """Initialize the multi-file generator."""
        super().__init__(DocstringFormatter(max_width=80))
        self.spec_path = spec_path
        self.protocol_dir = protocol_dir

        # Initialize components from original generator
        self.loader = SpecificationLoader(spec_path)
        self.type_mapper = TypeMapper()
        self.processor = DefinitionProcessor(self.type_mapper, self.loader)

    def categorize_specs(
        self,
        class_specs: List[ClassSpec],
        response_body_specs: List[ClassSpec],
        event_body_specs: List[ClassSpec],
    ) -> Dict[str, FileCategory]:
        """Categorize class specifications by their target file."""
        categories = {
            "base": FileCategory(
                name="base",
                filename="base.py",
                description="Base protocol classes and core interfaces",
                base_imports=[
                    "from dataclasses import dataclass, field, fields",
                    "from enum import Enum",
                    "from typing import Any, Dict, List, Optional, Union, ClassVar",
                ],
                classes=[],
            ),
            "requests": FileCategory(
                name="requests",
                filename="requests.py",
                description="DAP request message classes",
                base_imports=[
                    "from dataclasses import dataclass",
                    "from typing import Any, Dict, List, Optional, Union",
                    "from .base import Request",
                    "from .types import Breakpoint, Source, SourceBreakpoint, FunctionBreakpoint",
                    "from .types import DataBreakpoint, InstructionBreakpoint, ExceptionBreakpointsFilter",
                    "from .types import ExceptionPathSegment, ExceptionFilterOptions, StackFrameFormat",
                    "from .types import ValueFormat, Checksum, DisassembledInstruction",
                ],
                classes=[],
            ),
            "responses": FileCategory(
                name="responses",
                filename="responses.py",
                description="DAP response message classes",
                base_imports=[
                    "from dataclasses import dataclass",
                    "from typing import Any, Dict, List, Optional, Union",
                    "from .base import Response",
                    "from .bodies import *",  # Import all body classes
                ],
                classes=[],
            ),
            "events": FileCategory(
                name="events",
                filename="events.py",
                description="DAP event message classes",
                base_imports=[
                    "from dataclasses import dataclass",
                    "from typing import Any, Dict, List, Optional, Union",
                    "from .base import Event",
                    "from .bodies import *",  # Import all body classes
                ],
                classes=[],
            ),
            "bodies": FileCategory(
                name="bodies",
                filename="bodies.py",
                description="DAP message body and arguments classes",
                base_imports=[
                    "from dataclasses import dataclass",
                    "from typing import Any, Dict, List, Optional, Union",
                    "from .base import DAPDataclass, ImmutableAfterInit, OperationResponseBody, OperationEventBody",
                    "from .types import *",  # Import all type classes
                ],
                classes=[],
            ),
            "types": FileCategory(
                name="types",
                filename="types.py",
                description="DAP data type classes and enums",
                base_imports=[
                    "from dataclasses import dataclass",
                    "from enum import Enum",
                    "from typing import Any, Dict, List, Optional, Union",
                    "from .base import DAPDataclass",
                ],
                classes=[],
            ),
        }

        # Categorize all specs
        all_specs = class_specs + response_body_specs + event_body_specs

        for spec in all_specs:
            category = self._determine_category(spec)
            if category in categories:
                categories[category].classes.append(spec)

        return categories

    def _determine_category(self, spec: ClassSpec) -> str:
        """Determine which file category a class belongs to."""
        name = spec.name

        # Check for base classes
        if name in self.BASE_CLASSES:
            return "base"

        # Check suffixes
        if name.endswith("Request"):
            return "requests"
        elif name.endswith("Response"):
            return "responses"
        elif name.endswith("Event"):
            return "events"
        elif "Body" in name or name.endswith("Arguments"):
            return "bodies"
        else:
            # Everything else goes to types (enums, data structures, etc.)
            return "types"

    def _extract_type_dependencies(self, spec: ClassSpec) -> Set[str]:
        """Extract all type dependencies from a class spec."""
        deps = set()

        # Check base classes
        for base in spec.base_classes:
            if base not in ["str", "Enum", "DAPDataclass", "ImmutableAfterInit"]:
                deps.add(base)

        # Check field types
        for field in spec.fields:
            # Extract type names from type hints
            type_hint = field.type_hint
            # Match class names (capitalized words not followed by brackets)
            matches = re.findall(r"\b([A-Z][a-zA-Z0-9_]*)\b(?!\[)", type_hint)
            deps.update(matches)

        return deps

    def _get_cross_file_imports(
        self, category: FileCategory, all_categories: Dict[str, FileCategory]
    ) -> List[str]:
        """Determine what imports are needed from other protocol files."""
        imports = []
        class_names_in_file = {cls.name for cls in category.classes}

        # Collect all dependencies
        all_deps = set()
        for spec in category.classes:
            deps = self._extract_type_dependencies(spec)
            all_deps.update(deps)

        # Remove self-references
        all_deps -= class_names_in_file

        # Group dependencies by their source file
        imports_by_file: dict[str, list[str]] = {}
        for dep in all_deps:
            # Find which file contains this dependency
            for other_cat_name, other_cat in all_categories.items():
                if other_cat_name == category.name:
                    continue
                if any(cls.name == dep for cls in other_cat.classes):
                    if other_cat.filename not in imports_by_file:
                        imports_by_file[other_cat.filename] = []
                    imports_by_file[other_cat.filename].append(dep)
                    break

        # Generate import statements
        for filename, class_names in sorted(imports_by_file.items()):
            module_name = filename.replace(".py", "")
            sorted_names = sorted(set(class_names))
            if sorted_names:
                imports.append(f"from .{module_name} import {', '.join(sorted_names)}")

        return imports

    def generate_file_content(
        self, category: FileCategory, all_categories: Dict[str, FileCategory]
    ) -> str:
        """Generate the content for a single protocol file."""
        lines = []

        # File header
        lines.append('"""DAP Protocol - ' + category.description + ".")
        lines.append("")
        lines.append("Auto-generated from Debug Adapter Protocol specification.")
        lines.append('Do not edit manually."""')
        lines.append("")

        # For base.py, include additional imports needed by base classes
        if category.name == "base":
            lines.append("import json")
            lines.append("import sys")
            lines.append("from dataclasses import dataclass")
            lines.append("from enum import Enum")
            lines.append("from typing import (")
            lines.append("    Any,")
            lines.append("    Dict,")
            lines.append("    List,")
            lines.append("    Literal,")
            lines.append("    Optional,")
            lines.append("    Type,")
            lines.append("    TypeVar,")
            lines.append("    Union,")
            lines.append("    get_args,")
            lines.append("    get_origin,")
            lines.append(")")
            lines.append("")
            lines.append("from aidb.common.errors import AidbError, DAPProtocolError")
            lines.append("")
            lines.append('T = TypeVar("T", bound="ProtocolMessage")')
            lines.append('D = TypeVar("D", bound="DAPDataclass")')
            lines.append("")
        else:
            # Regular imports for other files
            lines.extend(category.base_imports)

        # Add cross-file imports if needed
        if category.name != "base":
            cross_imports = self._get_cross_file_imports(category, all_categories)
            if cross_imports:
                lines.append("")
                lines.extend(cross_imports)

        lines.append("")
        lines.append("")

        # For base.py, include the hardcoded base classes
        if category.name == "base":
            lines.append(self._get_base_classes_code())
            lines.append("")
            lines.append("")

        # Sort classes by dependencies within this file
        sorted_classes = self._sort_by_dependencies(category.classes)

        # Generate classes
        for i, spec in enumerate(sorted_classes):
            if i > 0:
                lines.append("")
                lines.append("")
            lines.append(self.generate_class(spec))

        return "\n".join(lines)

    def _get_base_classes_code(self) -> str:
        """Get the hardcoded base classes from the original protocol.py."""
        # Read the existing protocol.py to extract base classes
        protocol_path = self.protocol_dir.parent / "protocol.py"
        if not protocol_path.exists():
            # Return a minimal version if file doesn't exist
            return self._get_default_base_classes()

        with open(protocol_path) as f:
            lines = f.readlines()

        # Find where base classes end (before AttachRequest)
        base_end_line = None
        for i, line in enumerate(lines):
            if line.strip().startswith("class AttachRequest"):
                base_end_line = i
                break

        if base_end_line is None:
            return self._get_default_base_classes()

        # Find where imports end and classes begin
        class_start_line = None
        for i, line in enumerate(lines):
            if line.strip().startswith("class DAPDataclass"):
                class_start_line = i
                break

        if class_start_line is None:
            return self._get_default_base_classes()

        # Extract base classes
        base_lines = lines[class_start_line:base_end_line]

        # Remove any trailing blank lines
        while base_lines and base_lines[-1].strip() == "":
            base_lines.pop()

        base_content = "".join(base_lines)
        return base_content

    def _get_default_base_classes(self) -> str:
        """Return default base classes if we can't extract from existing
        file."""
        return '''class DAPDataclass:
    """Base class for DAP protocol dataclasses."""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DAPDataclass":
        """Create instance from dictionary."""
        # Implementation would go here
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary."""
        # Implementation would go here
        pass


class ImmutableAfterInit:
    """Mixin to make dataclasses immutable after initialization."""

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent attribute modification after initialization."""
        if hasattr(self, "_initialized") and self._initialized:
            raise AttributeError(f"Cannot modify attribute {name} after initialization")
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        """Mark as initialized after dataclass initialization."""
        object.__setattr__(self, "_initialized", True)


@dataclass
class ProtocolMessage(DAPDataclass):
    """Base class for all DAP protocol messages."""

    seq: int
    type: str


@dataclass
class Request(ProtocolMessage):
    """Base class for all DAP requests."""

    type: str = "request"
    command: str = ""
    arguments: Optional[Dict[str, Any]] = None


@dataclass
class Response(ProtocolMessage):
    """Base class for all DAP responses."""

    type: str = "response"
    request_seq: int = 0
    success: bool = True
    command: str = ""
    message: Optional[str] = None
    body: Optional[Any] = None


@dataclass
class Event(ProtocolMessage):
    """Base class for all DAP events."""

    type: str = "event"
    event: str = ""
    body: Optional[Any] = None'''

    def generate_init_file(self, categories: Dict[str, FileCategory]) -> str:
        """Generate __init__.py with convenience imports."""
        lines = []

        # File header
        lines.append('"""DAP Protocol Package.')
        lines.append("")
        lines.append(
            "This package contains auto-generated Debug Adapter Protocol classes."
        )
        lines.append('"""')
        lines.append("")

        # Import all classes from each module for convenience
        lines.append("# Base classes")
        lines.append("from .base import (")
        lines.append("    DAPDataclass,")
        lines.append("    ImmutableAfterInit,")
        lines.append("    ProtocolMessage,")
        lines.append("    Request,")
        lines.append("    Response,")
        lines.append("    Event,")
        lines.append(")")
        lines.append("")

        # Import key classes from other modules
        lines.append("# Import all protocol classes for convenience")
        lines.append("from .requests import *")
        lines.append("from .responses import *")
        lines.append("from .events import *")
        lines.append("from .bodies import *")
        lines.append("from .types import *")
        lines.append("")

        lines.append("__all__ = [")
        lines.append('    "DAPDataclass",')
        lines.append('    "ImmutableAfterInit",')
        lines.append('    "ProtocolMessage",')
        lines.append('    "Request",')
        lines.append('    "Response",')
        lines.append('    "Event",')
        lines.append("]")

        return "\n".join(lines)

    def generate(self) -> None:
        """Execute the complete multi-file generation process."""
        print("Loading DAP specification...")
        spec_data = self.loader.load()
        definitions = spec_data.get("definitions", {})
        print(f"Found {len(definitions)} definitions")

        print("Processing definitions...")
        class_specs = []
        for def_name, definition in definitions.items():
            spec = self.processor.process_definition(def_name, definition)
            if spec:
                class_specs.append(spec)

        print(f"Generated {len(class_specs)} class specifications")

        print("Generating ResponseBody classes...")
        response_body_specs = self.processor.get_response_body_specs()
        print(f"Generated {len(response_body_specs)} ResponseBody class specifications")

        print("Generating EventBody classes...")
        event_body_specs = self.processor.get_event_body_specs()
        print(f"Generated {len(event_body_specs)} EventBody class specifications")

        print("Categorizing specifications...")
        categories = self.categorize_specs(
            class_specs, response_body_specs, event_body_specs
        )

        # Print category summary
        for cat_name, category in categories.items():
            print(f"  {cat_name}: {len(category.classes)} classes")

        # Create protocol directory if it doesn't exist
        self.protocol_dir.mkdir(parents=True, exist_ok=True)

        # Generate each file
        for cat_name, category in categories.items():
            if not category.classes and cat_name != "base":
                continue  # Skip empty categories except base

            file_path = self.protocol_dir / category.filename
            print(f"Generating {file_path}...")

            content = self.generate_file_content(category, categories)
            with open(file_path, "w") as f:
                f.write(content)

        # Generate __init__.py
        init_path = self.protocol_dir / "__init__.py"
        print(f"Generating {init_path}...")
        init_content = self.generate_init_file(categories)
        with open(init_path, "w") as f:
            f.write(init_content)

        print(f"Successfully generated protocol files in {self.protocol_dir}")

        # Print summary
        total_classes = sum(len(cat.classes) for cat in categories.values())
        print(f"Total: {total_classes} classes across {len(categories)} files")


def main() -> int:
    """Main entry point for the multi-file generator."""
    script_dir = Path(__file__).parent
    spec_path = script_dir / "_spec.json"
    protocol_dir = script_dir.parent / "protocol"

    if not spec_path.exists():
        print(f"DAP specification not found at {spec_path}")
        return 1

    try:
        generator = MultiFileGenerator(spec_path, protocol_dir)
        generator.generate()
        return 0
    except Exception as e:
        print(f"Error generating protocol classes: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
