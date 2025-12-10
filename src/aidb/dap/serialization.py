"""Shared serialization logic for DAP protocol classes.

This module provides a mixin class that implements common serialization and
deserialization patterns used across all DAP protocol dataclasses.
"""

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any, Optional, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T", bound="SerializableMixin")


class SerializableMixin:
    """Mixin providing serialization capabilities for DAP protocol classes.

    This mixin implements the common from_dict and to_dict patterns used throughout the
    DAP protocol implementation, reducing code duplication across the protocol classes.
    """

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create instance from dictionary with recursive field conversion.

        Parameters
        ----------
        data : Dict[str, Any]
            Dictionary representation of the object

        Returns
        -------
        T
            Instance of the class with fields populated from the dictionary
        """
        # Get the dataclass fields and their types
        if dataclasses.is_dataclass(cls):
            # Use get_type_hints to properly resolve string annotations from
            # __future__ annotations
            try:
                field_types = cls._get_resolved_type_hints()
            except Exception:
                # Fall back to raw field.type if get_type_hints fails
                field_types = {
                    field.name: field.type for field in dataclasses.fields(cls)
                }
            converted_data = {}
            for key, value in data.items():
                if key in field_types:
                    field_type = field_types[key]
                    if value is not None:
                        converted_data[key] = cls._convert_field_value(
                            value,
                            field_type,
                        )
                    else:
                        converted_data[key] = value
                # Skip unknown fields for forward compatibility with newer DAP versions

            return cls(**converted_data)
        # Not a dataclass, use direct construction
        return cls(**data)

    @classmethod
    def _get_resolved_type_hints(cls) -> dict[str, Any]:
        """Get type hints with string annotations resolved to actual types.

        Uses typing.get_type_hints() which properly resolves forward references and
        string annotations from `from __future__ import annotations`.
        """
        # Import protocol modules to ensure types are available for resolution
        cls._ensure_protocol_modules_loaded()

        # Build a namespace with all protocol types for resolution
        namespace = cls._build_type_namespace()

        try:
            return get_type_hints(cls, globalns=namespace, localns=namespace)
        except NameError:
            # If resolution fails, fall back to raw annotations
            return {
                field.name: field.type
                for field in dataclasses.fields(cls)  # type: ignore[arg-type]
            }

    @classmethod
    def _ensure_protocol_modules_loaded(cls) -> None:
        """Ensure all protocol modules are loaded into sys.modules."""
        protocol_modules = [
            "aidb.dap.protocol.types",
            "aidb.dap.protocol.bodies",
            "aidb.dap.protocol.events",
            "aidb.dap.protocol.requests",
            "aidb.dap.protocol.responses",
            "aidb.dap.protocol.base",
        ]
        import contextlib

        for module_name in protocol_modules:
            if module_name not in sys.modules:
                with contextlib.suppress(ImportError):
                    __import__(module_name)

    @classmethod
    def _build_type_namespace(cls) -> dict[str, Any]:
        """Build a namespace dict with all protocol types for annotation resolution."""
        namespace: dict[str, Any] = {}

        # Add standard typing constructs
        namespace.update(
            {
                "Any": Any,
                "Dict": dict,
                "List": list,
                "Optional": Optional,
                "Union": Union,
            },
        )

        # Add all exported names from protocol modules
        protocol_modules = [
            "aidb.dap.protocol.types",
            "aidb.dap.protocol.bodies",
            "aidb.dap.protocol.events",
            "aidb.dap.protocol.requests",
            "aidb.dap.protocol.responses",
            "aidb.dap.protocol.base",
        ]
        for module_name in protocol_modules:
            module = sys.modules.get(module_name)
            if module:
                for name in dir(module):
                    if not name.startswith("_"):
                        namespace[name] = getattr(module, name)

        return namespace

    @classmethod
    def _handle_union_type(cls, value: Any, field_type: Any) -> Any:
        """Handle Union/Optional types.

        Parameters
        ----------
        value : Any
            The value to convert
        field_type : Any
            The Union type annotation

        Returns
        -------
        Any
            The converted value
        """
        args = get_args(field_type)
        # Check if it's Optional (Union with None)
        if type(None) in args:
            # Get the non-None type
            for arg in args:
                if arg is not type(None):
                    return cls._convert_field_value(value, arg)
        return value

    @classmethod
    def _handle_list_type(cls, value: Any, field_type: Any) -> Any:
        """Handle List types.

        Parameters
        ----------
        value : Any
            The value to convert
        field_type : Any
            The List type annotation

        Returns
        -------
        Any
            The converted value
        """
        if isinstance(value, list):
            item_type = get_args(field_type)[0] if get_args(field_type) else Any
            return [cls._convert_field_value(item, item_type) for item in value]
        return value

    @classmethod
    def _handle_dataclass_type(cls, value: dict[str, Any], target_type: type) -> Any:
        """Handle dataclass type conversion.

        Parameters
        ----------
        value : Dict[str, Any]
            The dictionary value to convert
        target_type : Type
            The target dataclass type

        Returns
        -------
        Any
            The converted dataclass instance or original value
        """
        # Recursively convert nested dataclasses
        if hasattr(target_type, "from_dict"):
            return target_type.from_dict(value)
        # For dataclasses without from_dict, try direct construction
        try:
            return target_type(**value)
        except TypeError:
            # If direct construction fails, return the dict
            return value

    @classmethod
    def _convert_field_value(cls, value: Any, field_type: Any) -> Any:
        """Convert a field value to its proper type.

        Parameters
        ----------
        value : Any
            The value to convert
        field_type : Any
            The target type annotation

        Returns
        -------
        Any
            The converted value
        """
        origin = get_origin(field_type)

        # Handle Union/Optional types
        if origin is Union:
            return cls._handle_union_type(value, field_type)

        # Handle List types
        if origin is list:
            return cls._handle_list_type(value, field_type)

        # Handle Dict types - pass through
        if origin is dict:
            return value

        # Try to resolve and convert dataclass types
        target_type = cls._resolve_target_type(field_type)
        if target_type and isinstance(value, dict):
            return cls._handle_dataclass_type(value, target_type)

        # Return value as-is if no conversion needed
        return value

    @classmethod
    def _resolve_from_modules(cls, type_name: str) -> type | None:
        """Try to resolve a type name from various modules.

        Parameters
        ----------
        type_name : str
            The type name to resolve

        Returns
        -------
        Optional[Type]
            The resolved type, or None if not found
        """
        # Try to resolve from current module
        current_module = sys.modules[cls.__module__]
        if hasattr(current_module, type_name):
            return getattr(current_module, type_name)

        # Check protocol modules
        protocol_modules = [
            "types",
            "bodies",
            "events",
            "requests",
            "responses",
            "base",
        ]
        for module_name in protocol_modules:
            try:
                protocol_module = sys.modules.get(
                    f"aidb.dap.protocol.{module_name}",
                )
                if protocol_module and hasattr(protocol_module, type_name):
                    return getattr(protocol_module, type_name)
            except (ImportError, AttributeError):
                continue

        return None

    @classmethod
    def _resolve_forward_ref(cls, field_type: Any) -> type | None:
        """Resolve a ForwardRef type.

        Parameters
        ----------
        field_type : Any
            The forward reference to resolve

        Returns
        -------
        Optional[Type]
            The resolved type, or None if not resolvable
        """
        forward_arg = field_type.__forward_arg__
        if isinstance(forward_arg, str):
            return cls._resolve_from_modules(forward_arg)
        return None

    @classmethod
    def _resolve_string_type(cls, field_type: str) -> type | None:
        """Resolve a string type hint.

        Parameters
        ----------
        field_type : str
            The string type hint to resolve

        Returns
        -------
        Optional[Type]
            The resolved type, or None if not resolvable
        """
        # Remove quotes if present
        type_name = field_type.strip("\"'")
        return cls._resolve_from_modules(type_name)

    @classmethod
    def _resolve_target_type(cls, field_type: type | str | Any) -> type | None:
        """Resolve the type from field_type, handling ForwardRef and strings.

        Parameters
        ----------
        field_type : Union[Type, str, Any]
            The field type annotation to resolve

        Returns
        -------
        Optional[Type]
            The resolved type, or None if it cannot be resolved
        """
        # Check if field_type is a ForwardRef
        if hasattr(field_type, "__forward_arg__"):  # ForwardRef object
            return cls._resolve_forward_ref(field_type)

        # If it's already a type, return it
        if isinstance(field_type, type):
            return field_type

        # Handle string type hints
        if isinstance(field_type, str):
            return cls._resolve_string_type(field_type)

        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert the instance to a dictionary for JSON serialization.

        Returns
        -------
        Dict[str, Any]
            Dictionary representation of the object
        """
        result = {}

        # Process all attributes (both dataclass fields and dynamic)
        for attr_name, attr_value in self.__dict__.items():
            if attr_name.startswith("_"):
                continue  # Skip private attributes

            # Handle None values
            if attr_value is None:
                continue  # Skip None values for cleaner JSON

            # Convert the value
            result[attr_name] = self._serialize_value(attr_value)

        return result

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON conversion.

        Parameters
        ----------
        value : Any
            The value to serialize

        Returns
        -------
        Any
            The serialized value
        """
        if value is None:
            return None
        if isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        # Convert pathlib.Path to string for JSON serialization
        if isinstance(value, Path):
            return str(value)
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            # For dataclasses without to_dict, use dataclasses.asdict
            return dataclasses.asdict(value)
        # For other types, try to convert to string or return as-is
        return value

    def to_json(self) -> str:
        """Convert the instance to a JSON string.

        Returns
        -------
        str
            JSON string representation of the object
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create instance from JSON string.

        Parameters
        ----------
        json_str : str
            JSON string representation of the object

        Returns
        -------
        T
            Instance of the class created from the JSON string
        """
        return cls.from_dict(json.loads(json_str))
