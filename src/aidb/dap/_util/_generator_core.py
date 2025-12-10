#!/usr/bin/env python3
"""DAP Protocol Generator Core Components.

Shared components for generating Python dataclasses from DAP specification JSON. These
are used by _gen_protocol.py (the multi-file generator).
"""

import ast
import json
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FieldSpec:
    """Specification for a dataclass field."""

    name: str
    type_hint: str
    description: str
    is_required: bool
    default_value: Optional[str] = None


@dataclass(frozen=True)
class ClassSpec:
    """Specification for a dataclass."""

    name: str
    description: str
    base_classes: List[str]
    fields: List[FieldSpec]
    spec_line: int


class DocstringFormatter:
    """Handles elegant docstring formatting with proper line wrapping."""

    def __init__(self, max_width: int = 80):
        self.max_width = max_width
        self.single_line_width = max_width - 10
        self.continuation_width = max_width - 10

    def format(self, text: str) -> str:
        """Format text as a properly wrapped docstring."""
        if not text:
            return ""

        text = self._clean_text(text)

        # For short text, use single line
        if len(text) <= self.single_line_width:
            return text

        # For longer text, wrap elegantly
        return self._wrap_multiline(text)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for docstring use."""
        # Handle case where text might be a tuple (convert to string)
        if isinstance(text, tuple):
            text = str(text)
        elif not isinstance(text, str):
            text = str(text) if text is not None else ""

        # Remove excessive whitespace and normalize line breaks
        text = " ".join(text.split())
        return text.strip()

    def _wrap_multiline(self, text: str) -> str:
        """Wrap text across multiple lines with proper indentation."""
        # Use textwrap for consistent, readable wrapping
        wrapped_lines = textwrap.wrap(
            text,
            width=self.continuation_width,
            break_long_words=False,
            break_on_hyphens=False,
        )

        if not wrapped_lines:
            return ""

        # First line at base level, rest indented
        result = wrapped_lines[0]
        if len(wrapped_lines) > 1:
            for line in wrapped_lines[1:]:
                result += f"\n    {line}"

        return result

    def format_with_attributes(self, description: str, fields: List[FieldSpec]) -> str:
        """Format docstring with description and numpy-style attributes section."""
        if not description and not fields:
            return ""

        parts = []

        # Add main description if present
        if description:
            formatted_desc = self.format(description)
            parts.append(formatted_desc)

        # Add attributes section if fields have descriptions
        fields_with_descriptions = [f for f in fields if f.description]
        if fields_with_descriptions:
            parts.append("")
            parts.append("    Attributes")
            parts.append("    " + "-" * 10)

            for field in fields_with_descriptions:
                # Format field header: name : type
                field_header = (
                    f"    {field.name} : {self._clean_type_hint(field.type_hint)}"
                )
                parts.append(field_header)

                # Format field description with indentation
                if field.description:
                    desc_lines = self._wrap_field_description(field.description)
                    for line in desc_lines:
                        parts.append(f"        {line}")
                parts.append("")  # Empty line after each field

            # Remove trailing empty line
            if parts and parts[-1] == "":
                parts.pop()

        return "\n".join(parts)

    def _clean_type_hint(self, type_hint: str) -> str:
        """Clean type hint for display in docstring."""
        # Remove quotes around forward references
        cleaned = type_hint.replace("'", "")
        return cleaned

    def _wrap_field_description(self, description: str) -> List[str]:
        """Wrap field description for attributes section."""
        if not description:
            return []

        # Clean the text first
        cleaned = self._clean_text(description)

        # Wrap with slightly smaller width to account for indentation
        wrapped = textwrap.wrap(
            cleaned,
            width=self.continuation_width - 4,  # Account for indentation
            break_long_words=False,
            break_on_hyphens=False,
        )

        return wrapped or [description]


class TypeMapper:
    """Maps JSON Schema types to Python type hints with forward references."""

    TYPE_MAP = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "List[Any]",
        "object": "Dict[str, Any]",
        "null": "None",
    }

    def map_type(
        self, json_type: Any, items: Optional[Dict] = None, quote_refs: bool = True
    ) -> str:
        """Convert JSON Schema type to Python type hint."""
        if isinstance(json_type, list):
            return self._handle_union_type(json_type, quote_refs)
        if json_type == "array" and items:
            return self._handle_array_type(items, quote_refs)
        return self.TYPE_MAP.get(json_type, "Any")

    def _handle_union_type(self, types: List[str], quote_refs: bool = True) -> str:
        """Handle union types (multiple allowed types)."""
        mapped_types = [self.map_type(t, quote_refs=quote_refs) for t in types]

        if len(mapped_types) == 1:
            return mapped_types[0]

        # Handle nullable types (most common case)
        if "None" in mapped_types:
            non_none = [t for t in mapped_types if t != "None"]
            if len(non_none) == 1:
                return f"Optional[{non_none[0]}]"
            return f"Optional[Union[{', '.join(non_none)}]]"

        return f"Union[{', '.join(mapped_types)}]"

    def _handle_array_type(self, items: Dict, quote_refs: bool = True) -> str:
        """Handle array types with proper item type mapping."""
        if "$ref" in items:
            ref_name = items["$ref"].split("/")[-1]
            # Always quote references to other classes
            return f"List['{ref_name}']"

        if "type" in items:
            item_type = self.map_type(items["type"], quote_refs=quote_refs)
            return f"List[{item_type}]"

        return "List[Any]"


class SpecificationLoader:
    """Loads and parses DAP specification files."""

    def __init__(self, spec_path: Path):
        self.spec_path = spec_path
        self.line_numbers: Dict[str, int] = {}

    def load(self) -> Dict[str, Any]:
        """Load specification and extract line numbers."""
        self._extract_line_numbers()

        with open(self.spec_path) as f:
            return json.load(f)

    def _extract_line_numbers(self) -> None:
        """Extract line numbers for each definition."""
        with open(self.spec_path) as f:
            for line_num, line in enumerate(f, 1):
                if self._is_definition_line(line):
                    def_name = self._extract_definition_name(line)
                    if def_name:
                        self.line_numbers[def_name] = line_num

    def _is_definition_line(self, line: str) -> bool:
        """Check if line contains a definition start."""
        stripped = line.strip()
        return (
            stripped.startswith('"')
            and stripped.endswith('": {')
            and not stripped.startswith('"$')  # Skip schema refs
            and len(stripped.split('"')) >= 3  # Ensure proper quote structure
        )

    def _extract_definition_name(self, line: str) -> Optional[str]:
        """Extract definition name from line."""
        match = re.search(r'^\s*"([A-Z][^"]+)"\s*:\s*\{\s*$', line)
        return match.group(1) if match else None

    def get_line_number(self, def_name: str) -> int:
        """Get line number for a definition."""
        return self.line_numbers.get(def_name, 0)


class DefinitionProcessor:
    """Processes DAP specification definitions into class specifications."""

    # Manually written base classes that should not be generated
    PRESERVED_SPEC_DEFINITIONS = {"ProtocolMessage", "Request", "Response", "Event"}

    def __init__(self, type_mapper: TypeMapper, loader: SpecificationLoader):
        self.type_mapper = type_mapper
        self.loader = loader
        self._response_body_specs: Dict[
            str, Dict[str, Any]
        ] = {}  # Cache for response body specs
        self._event_body_specs: Dict[
            str, Dict[str, Any]
        ] = {}  # Cache for event body specs
        # Cache original definitions for enum detection
        self._original_definitions: Dict[str, Dict[str, Any]] = {}

    def should_generate(self, def_name: str) -> bool:
        """Determine if we should generate a class for this definition."""
        # Skip preserved/manually written classes
        if def_name in self.PRESERVED_SPEC_DEFINITIONS:
            return False

        # Generate ALL definitions (data types, enums, requests, responses,
        # events, arguments) This ensures we create dataclasses for types like
        # ExceptionFilterOptions, ExceptionOptions, etc.
        return True

    def process_definition(
        self, def_name: str, definition: Dict[str, Any]
    ) -> Optional[ClassSpec]:
        """Convert a definition into a class specification."""
        if not self.should_generate(def_name):
            return None

        # Cache original definition for enum detection (like analyzer does)
        self._original_definitions[def_name] = definition

        class_name = def_name
        base_classes, flattened = self._flatten_inheritance(definition)
        description = flattened.get("description", "")

        fields = self._process_fields(def_name, flattened, definition)
        line_number = self.loader.get_line_number(def_name)

        # For Response classes, also cache the body specification for later
        # ResponseBody generation
        if def_name.endswith("Response"):
            self._cache_response_body_spec(def_name, flattened, line_number)

        # For Event classes, also cache the body specification for later
        # EventBody generation
        if def_name.endswith("Event"):
            self._cache_event_body_spec(def_name, flattened, line_number)

        # Ensure all generated dataclasses inherit from DAPDataclass for
        # recursive deserialization unless they already have a base class or are
        # enums
        category = self._determine_category_like_analyzer(def_name, definition)
        if not base_classes and category != "enums":
            base_classes = ["DAPDataclass"]

        return ClassSpec(
            name=class_name,
            description=description,
            base_classes=base_classes,
            fields=fields,
            spec_line=line_number,
        )

    def _flatten_inheritance(
        self, definition: Dict[str, Any]
    ) -> tuple[List[str], Dict[str, Any]]:
        """Flatten allOf inheritance into base classes and properties."""
        base_classes = []
        merged_props = {}
        required_fields = set()
        description = definition.get("description", "")

        if "allOf" in definition:
            for item in definition["allOf"]:
                if "$ref" in item:
                    ref_name = item["$ref"].split("/")[-1]
                    base_classes.append(ref_name)
                elif "properties" in item:
                    merged_props.update(item.get("properties", {}))
                    required_fields.update(item.get("required", []))

                # Use description from allOf if not set
                if "description" in item and not description:
                    description = item["description"]

        # Add direct properties
        merged_props.update(definition.get("properties", {}))
        required_fields.update(definition.get("required", []))

        return base_classes, {
            "properties": merged_props,
            "required": list(required_fields),
            "description": description,
        }

    def _process_fields(
        self, def_name: str, flattened: Dict[str, Any], original: Dict[str, Any]
    ) -> List[FieldSpec]:
        """Process definition fields into field specifications.

        Uses simplified category-based approach.
        """
        category = self._determine_category_like_analyzer(def_name, original)

        if category == "enums":
            enum_values = original.get("enum", [])
            return [
                FieldSpec(
                    name="_enum_values",
                    type_hint="List[str]",
                    description="Enum values from spec",
                    is_required=True,
                    default_value=repr(enum_values),
                )
            ]
        elif category == "requests":
            return self._create_request_fields(def_name, flattened)
        elif category == "responses":
            return self._create_response_fields(def_name, flattened)
        elif category == "events":
            return self._create_event_fields(def_name, flattened)
        else:
            # Arguments, data types, and other complex types use property fields
            return self._create_property_fields(flattened, category == "events")

    def _create_request_fields(
        self, def_name: str, flattened: Dict[str, Any]
    ) -> List[FieldSpec]:
        """Create standardized fields for Request classes."""
        command_name = self._extract_enum_value(flattened, "command")

        # Check if the request definition actually defines arguments
        properties = flattened.get("properties", {})
        has_arguments = "arguments" in properties

        if not has_arguments:
            arguments_type_hint = "None"
        else:
            args_prop = properties.get("arguments", {})
            if "$ref" in args_prop:
                ref_name = args_prop["$ref"].split("/")[-1]
                arguments_type_hint = f"Optional['{ref_name}']"
            else:
                # Generate arguments class name based on request name
                arguments_class_name = def_name.replace("Request", "Arguments")
                if arguments_class_name not in ["RequestArguments", "Arguments"]:
                    # Always quote the reference
                    arguments_type_hint = f"Optional['{arguments_class_name}']"
                else:
                    # Fall back to generic type for generic requests
                    arguments_type_hint = "Optional[Dict[str, Any]]"

        return [
            FieldSpec(
                name="command",
                type_hint="str",
                description="The command to execute.",
                is_required=True,
                default_value=f'"{command_name}"',
            ),
            FieldSpec(
                name="arguments",
                type_hint=arguments_type_hint,
                description="Object containing arguments for the command.",
                is_required=False,
                default_value="None",
            ),
        ]

    def _create_property_fields(
        self, flattened: Dict[str, Any], is_event: bool = False
    ) -> List[FieldSpec]:
        """Create fields from properties for Arguments and Event classes."""
        properties = flattened.get("properties", {})
        required = flattened.get("required", [])

        fields = []
        for field_name, field_def in properties.items():
            # Handle special event field
            if is_event and field_name == "event":
                event_name = self._extract_enum_value(flattened, "event")
                if event_name:
                    field_spec = FieldSpec(
                        name="event",
                        type_hint="str",
                        description="The event type.",
                        is_required=True,
                        default_value=f'"{event_name}"',
                    )
                    fields.append(field_spec)
                    continue

            # Handle special body field for events - use typed EventBody class
            if is_event and field_name == "body":
                # This would need to be handled at the calling site since we
                # don't have the event name here. Skip it for now - it's handled
                # in _create_event_fields
                continue

            field_spec = self._create_field_spec(field_name, field_def, required)
            fields.append(field_spec)
        return fields

    def _create_response_fields(
        self, def_name: str, flattened: Dict[str, Any]
    ) -> List[FieldSpec]:
        """Create fields for Response classes from properties."""
        properties = flattened.get("properties", {})
        required = flattened.get("required", [])

        fields = []
        for field_name, field_def in properties.items():
            # Skip inherited Response base class fields (seq, type, request_seq,
            # etc.)
            if field_name in [
                "seq",
                "type",
                "request_seq",
                "success",
                "command",
                "message",
            ]:
                continue

            # Handle body field specially
            if field_name == "body":
                # Check if body has a $ref - if so, use that type directly
                if "$ref" in field_def:
                    # Extract the referenced type name
                    ref_type = field_def["$ref"].split("/")[-1]
                    # Use the referenced type directly
                    type_hint = f"Optional['{ref_type}']"

                    field_spec = FieldSpec(
                        name="body",
                        type_hint=type_hint,
                        description=field_def.get("description", "Response body."),
                        is_required=field_name in required,
                        default_value="None",
                    )
                else:
                    # No $ref, create a synthetic ResponseBody class
                    body_class_name = def_name.replace("Response", "ResponseBody")

                    # Always use forward references to avoid ordering issues
                    type_hint = f"Optional['{body_class_name}']"

                    field_spec = FieldSpec(
                        name="body",
                        type_hint=type_hint,
                        description=field_def.get("description", "Response body."),
                        is_required=field_name in required,
                        default_value="None",
                    )
            else:
                field_spec = self._create_field_spec(field_name, field_def, required)

            fields.append(field_spec)
        return fields

    def _create_event_fields(
        self, def_name: str, flattened: Dict[str, Any]
    ) -> List[FieldSpec]:
        """Create fields for Event classes from properties."""
        properties = flattened.get("properties", {})
        required = flattened.get("required", [])

        fields = []
        for field_name, field_def in properties.items():
            # Skip inherited Event base class fields (seq, type, event)
            if field_name in ["seq", "type"]:
                continue

            # Handle event field specially - use enum value as default
            if field_name == "event":
                event_name = self._extract_enum_value(flattened, "event")
                if event_name:
                    field_spec = FieldSpec(
                        name="event",
                        type_hint="str",
                        description="The event type.",
                        is_required=True,
                        default_value=f'"{event_name}"',
                    )
                    fields.append(field_spec)
                    continue

            # Handle body field specially
            if field_name == "body":
                # Check if body has a $ref - if so, use that type directly
                if "$ref" in field_def:
                    # Extract the referenced type name
                    ref_type = field_def["$ref"].split("/")[-1]
                    # Use the referenced type directly
                    type_hint = f"Optional['{ref_type}']"

                    field_spec = FieldSpec(
                        name="body",
                        type_hint=type_hint,
                        description=field_def.get("description", "Event body."),
                        is_required=field_name in required,
                        default_value="None",
                    )
                else:
                    # No $ref, create a synthetic EventBody class
                    body_class_name = def_name.replace("Event", "EventBody")

                    # Always use forward references to avoid ordering issues
                    type_hint = f"Optional['{body_class_name}']"

                    field_spec = FieldSpec(
                        name="body",
                        type_hint=type_hint,
                        description=field_def.get("description", "Event body."),
                        is_required=field_name in required,
                        default_value="None",
                    )
            else:
                field_spec = self._create_field_spec(field_name, field_def, required)

            fields.append(field_spec)
        return fields

    def _create_field_spec(
        self, name: str, definition: Dict[str, Any], required: List[str]
    ) -> FieldSpec:
        """Create a field specification from a property definition."""
        is_required = name in required
        description = definition.get("description", "")

        # Handle $ref references - always quote them
        if "$ref" in definition:
            ref_name = definition["$ref"].split("/")[-1]
            type_hint = f"'{ref_name}'"
        else:
            field_type = definition.get("type", "object")
            type_hint = self.type_mapper.map_type(
                field_type, definition.get("items"), quote_refs=True
            )

        # Make optional if not required
        if not is_required and not type_hint.startswith("Optional["):
            type_hint = f"Optional[{type_hint}]"

        default_value = None if is_required else "None"

        return FieldSpec(
            name=name,
            type_hint=type_hint,
            description=description,
            is_required=is_required,
            default_value=default_value,
        )

    def _extract_enum_value(
        self, flattened: Dict[str, Any], field_name: str
    ) -> Optional[str]:
        """Extract enum value from a field property."""
        properties = flattened.get("properties", {})
        field_prop = properties.get(field_name, {})

        if "enum" in field_prop and field_prop["enum"]:
            return field_prop["enum"][0]

        return "unknown" if field_name == "command" else None

    def _cache_body_spec(
        self,
        parent_name: str,
        flattened: Dict[str, Any],
        line_number: int,
        body_type: str,
    ) -> None:
        """Cache body specification for generating ResponseBody/EventBody classes."""
        properties = flattened.get("properties", {})

        if "body" not in properties:
            return

        body_prop = properties["body"]

        # Skip caching if body is a $ref to an existing type (not an inline object)
        if "$ref" in body_prop:
            # Don't cache - we'll use the referenced type directly
            return

        body_class_name = parent_name.replace(body_type, f"{body_type}Body")
        cache = (
            self._response_body_specs
            if body_type == "Response"
            else self._event_body_specs
        )
        parent_key = "response_name" if body_type == "Response" else "event_name"

        base_spec = {
            parent_key: parent_name,
            "description": (
                f"{body_type.split('Response')[0] or body_type.split('Event')[0]} "
                + f"body for {parent_name}.",
            ),
            "line_number": line_number,
        }

        if "type" in body_prop and body_prop["type"] == "object":
            cache[body_class_name] = {
                **base_spec,
                "properties": body_prop.get("properties", {}),
                "required": body_prop.get("required", []),
                "description": body_prop.get("description", base_spec["description"]),
            }

    def _cache_response_body_spec(
        self, response_name: str, flattened: Dict[str, Any], response_line: int
    ) -> None:
        """Cache response body specification."""
        self._cache_body_spec(response_name, flattened, response_line, "Response")

    def _cache_event_body_spec(
        self, event_name: str, flattened: Dict[str, Any], event_line: int
    ) -> None:
        """Cache event body specification."""
        self._cache_body_spec(event_name, flattened, event_line, "Event")

    def _generate_body_specs(
        self, body_specs_cache: Dict[str, Dict], base_class: str
    ) -> List[ClassSpec]:
        """Generate body class specifications from cached specs."""
        body_specs = []

        for body_class_name, spec in body_specs_cache.items():
            fields = []

            if "ref" in spec:
                # Handle $ref cases by inlining the referenced definition's
                # properties
                ref_definition = self._resolve_ref_definition(spec["ref"])
                if ref_definition and "properties" in ref_definition:
                    properties = ref_definition["properties"]
                    required = ref_definition.get("required", [])
                else:
                    continue
            elif "properties" in spec:
                properties = spec["properties"]
                required = spec.get("required", [])
            else:
                continue

            for field_name, field_def in properties.items():
                field_spec = self._create_field_spec(field_name, field_def, required)
                fields.append(field_spec)

            body_spec = ClassSpec(
                name=body_class_name,
                description=spec["description"],
                base_classes=[base_class],
                fields=fields,
                spec_line=spec.get("line_number", 0),
            )
            body_specs.append(body_spec)

        return body_specs

    def get_response_body_specs(self) -> List[ClassSpec]:
        """Generate ResponseBody class specifications."""
        return self._generate_body_specs(
            self._response_body_specs, "OperationResponseBody"
        )

    def get_event_body_specs(self) -> List[ClassSpec]:
        """Generate EventBody class specifications."""
        return self._generate_body_specs(self._event_body_specs, "OperationEventBody")

    def _resolve_ref_definition(self, ref_path: str) -> Dict[str, Any]:
        """Resolve a $ref path to get the actual definition.

        Parameters
        ----------
        ref_path : str
            Reference path like '#/definitions/Capabilities'

        Returns
        -------
        Dict[str, Any]
            The resolved definition dictionary
        """
        if not ref_path.startswith("#/definitions/"):
            return {}

        def_name = ref_path.split("/")[-1]  # Extract 'Capabilities' from path
        # Access spec through the loader which loaded it
        spec_data = self.loader.load()
        return spec_data.get("definitions", {}).get(def_name, {})

    def _determine_category_like_analyzer(
        self, def_name: str, definition: Dict[str, Any]
    ) -> str:
        """Determine the category of a definition using analyzer's simplified logic."""
        # Base protocol types
        if def_name in ["ProtocolMessage", "Request", "Response", "Event"]:
            return "base"

        # Simple suffix-based categorization like the analyzer
        if def_name.endswith("Request"):
            return "requests"
        if def_name.endswith("Response"):
            return "responses"
        if def_name.endswith("Arguments"):
            return "arguments"
        if def_name.endswith("Event"):
            return "events"

        # Enums (simple string types with enum values) - analyzer's exact logic
        if definition.get("type") == "string" and "enum" in definition:
            return "enums"

        # Everything else is a data type
        return "data_types"


class CodeGenerator:
    """Generates Python dataclass code from class specifications."""

    def __init__(self, formatter: DocstringFormatter):
        self.formatter = formatter

    def generate_class(self, spec: ClassSpec) -> str:
        """Generate Python code for a dataclass or enum."""
        # Check if this is an enum specification
        if self._is_enum_spec(spec):
            return self.generate_enum_class(spec)

        lines = []

        lines.append("@dataclass")

        # For class inheritance, we cannot quote base classes even if they're
        # forward references since Python doesn't support quoted base classes in
        # class definitions. We rely on dependency sorting to ensure proper
        # order
        quoted_base_classes = spec.base_classes

        base_str = f"({', '.join(quoted_base_classes)})" if quoted_base_classes else ""
        lines.append(f"class {spec.name}{base_str}:")

        # Enhanced docstring with attributes section for Arguments classes
        if spec.description or (spec.name.endswith("Arguments") and spec.fields):
            if spec.name.endswith("Arguments") and any(
                f.description for f in spec.fields
            ):
                # Use enhanced formatting for Arguments classes with field
                # descriptions
                docstring = self.formatter.format_with_attributes(
                    spec.description, spec.fields
                )
            else:
                # Use standard formatting for other classes
                docstring = self.formatter.format(spec.description or "")

            if docstring:
                lines.append(f'    """{docstring}"""')
                lines.append("")

        # Spec reference
        spec_ref = (
            f"_spec.json#{spec.spec_line}"
            if spec.spec_line
            else f"_spec.json#{spec.name}"
        )
        lines.append(f"    # {spec_ref}")
        lines.append("")

        # Fields - sort to ensure required fields come before optional fields
        if spec.fields:
            # Sort fields: required fields (no defaults) first, then optional
            # fields (with defaults)
            sorted_fields = sorted(
                spec.fields, key=lambda f: (f.default_value is not None, f.name)
            )
            for field in sorted_fields:
                field_line = f"    {field.name}: {field.type_hint}"
                if field.default_value:
                    field_line += f" = {field.default_value}"
                lines.append(field_line)
        else:
            lines.append("    pass")

        return "\n".join(lines)

    def _is_enum_spec(self, spec: ClassSpec) -> bool:
        """Check if a ClassSpec represents an enum definition."""
        # Enum specs have a special _enum_values field that stores the enum
        # values
        return len(spec.fields) == 1 and spec.fields[0].name == "_enum_values"

    def generate_enum_class(self, spec: ClassSpec) -> str:
        """Generate Python code for an enum class."""
        lines = []

        # Class definition with Enum inheritance
        lines.append(f"class {spec.name}(str, Enum):")

        # Docstring
        if spec.description:
            docstring = self.formatter.format(spec.description)
            if docstring:
                lines.append(f'    """{docstring}"""')
                lines.append("")

        # Spec reference
        spec_ref = (
            f"_spec.json#{spec.spec_line}"
            if spec.spec_line
            else f"_spec.json#{spec.name}"
        )
        lines.append(f"    # {spec_ref}")
        lines.append("")

        # Extract enum values from the special _enum_values field
        enum_values = []
        if spec.fields and spec.fields[0].name == "_enum_values":
            # Parse the enum values from the default_value string
            try:
                if spec.fields[0].default_value is not None:
                    enum_values = ast.literal_eval(spec.fields[0].default_value)
                else:
                    enum_values = []
            except (ValueError, SyntaxError):
                enum_values = []

        if enum_values:
            for value in enum_values:
                # Convert to Python constant name (e.g., "userUnhandled" ->
                # "USER_UNHANDLED")
                const_name = self._to_enum_constant_name(value)
                lines.append(f'    {const_name} = "{value}"')
        else:
            # Fallback if we can't extract values
            lines.append("    pass")

        return "\n".join(lines)

    def _to_enum_constant_name(self, value: str) -> str:
        """Convert enum value to Python constant naming convention."""
        # Convert camelCase/PascalCase to UPPER_SNAKE_CASE e.g., "userUnhandled"
        # -> "USER_UNHANDLED"
        result = ""
        for i, char in enumerate(value):
            if char.isupper() and i > 0:
                result += "_"
            result += char.upper()
        return result

    def _sort_by_dependencies(self, specs: List[ClassSpec]) -> List[ClassSpec]:
        """Sort class specs with dependency awareness.

        Classes that are used as base classes should be defined before classes that
        inherit from them.
        """
        # Create a mapping of class names to specs
        spec_map = {spec.name: spec for spec in specs}

        # Build dependency graph (what each class depends on)
        dependencies = {}
        for spec in specs:
            deps = set()
            for base_class in spec.base_classes:
                # Only track dependencies on classes we're generating
                if base_class in spec_map:
                    deps.add(base_class)
            dependencies[spec.name] = deps

        # Topological sort with fallback to alphabetical
        result = []
        remaining = set(spec.name for spec in specs)

        while remaining:
            # Find classes with no unresolved dependencies
            ready = []
            for class_name in remaining:
                if not (dependencies[class_name] & remaining):
                    ready.append(class_name)

            if not ready:
                # Circular dependency or other issue - fall back to alphabetical
                ready = sorted(remaining)

            # Sort ready classes alphabetically for consistent output
            ready.sort()

            # Add the first ready class to result
            next_class = ready[0]
            result.append(spec_map[next_class])
            remaining.remove(next_class)

        return result
