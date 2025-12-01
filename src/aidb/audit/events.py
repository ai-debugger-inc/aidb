"""Audit event definitions and structures."""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from aidb.audit.constants import MaskingConstants
from aidb_common.config import ConfigManager, config


class AuditLevel(Enum):
    """Audit event severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AuditEvent:
    """Structured audit event.

    Represents a single audit log entry with all necessary context
    for tracking debug operations, API calls, and system events.

    Attributes
    ----------
    timestamp : str
        ISO 8601 timestamp of the event
    level : AuditLevel
        Severity level of the event
    component : str
        Component that generated the event (e.g., "api.operations", "binary.manager")
    operation : str
        Specific operation being audited (e.g., "continue_execution", "download_binary")
    session_id : Optional[str]
        Associated debug session ID, if applicable
    parameters : Dict[str, Any]
        Input parameters for the operation
    result : Dict[str, Any]
        Result of the operation (success, duration, etc.)
    metadata : Dict[str, Any]
        Additional context (language, adapter, user, pid, etc.)
    error : Optional[str]
        Error message if operation failed
    """

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    level: AuditLevel = AuditLevel.INFO
    component: str = ""
    operation: str = ""
    session_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        if "pid" not in self.metadata:
            self.metadata["pid"] = os.getpid()
        if "user" not in self.metadata:
            self.metadata["user"] = config.get_user()

    def to_json(self) -> str:
        """Serialize event to JSON string.

        Returns
        -------
        str
            JSON representation of the event
        """
        data = asdict(self)
        data["level"] = data["level"].value
        data = {k: v for k, v in data.items() if v is not None}
        return json.dumps(data, separators=(",", ":"))

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary.

        Returns
        -------
        Dict[str, Any]
            Dictionary representation of the event
        """
        data = asdict(self)
        data["level"] = data["level"].value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        """Create event from dictionary.

        Parameters
        ----------
        data : Dict[str, Any]
            Dictionary containing event data

        Returns
        -------
        AuditEvent
            Reconstructed audit event
        """
        if "level" in data and isinstance(data["level"], str):
            data["level"] = AuditLevel(data["level"])
        return cls(**data)

    def mask_sensitive_data(self, additional_keys: set[str] | None = None) -> None:
        """Mask sensitive information in parameters.

        Removes or masks potentially sensitive data like passwords, tokens, and
        API keys from the parameters and metadata using configuration settings.

        Parameters
        ----------
        additional_keys : Optional[Set[str]]
            Additional sensitive keys to mask beyond those in configuration

        Raises
        ------
        Exception
            If strict_mode is enabled and masking fails
        """
        config_manager = ConfigManager()
        masking_config = self._get_masking_config(config_manager, additional_keys)

        is_field_sensitive = self._create_field_checker(masking_config)
        mask_dict = self._create_dict_masker(masking_config, is_field_sensitive)

        try:
            mask_dict(self.parameters)
            if masking_config["mask_in_metadata"]:
                mask_dict(self.metadata)
        except Exception as e:
            if masking_config["strict_mode"]:
                raise
            # Log the error but continue in non-strict mode
            import logging

            logging.getLogger(__name__).warning("Masking error (non-strict): %s", e)

    def _get_masking_config(
        self,
        config_manager: ConfigManager,
        additional_keys: set[str] | None,
    ) -> dict[str, Any]:
        """Get masking configuration settings."""
        sensitive_keys = set(MaskingConstants.SENSITIVE_FIELDS)
        if additional_keys:
            sensitive_keys.update(additional_keys)
        sensitive_keys.update(config_manager.get_audit_custom_sensitive_keys())

        case_sensitive = config_manager.is_audit_case_sensitive()
        if not case_sensitive:
            sensitive_keys = {k.lower() for k in sensitive_keys}

        return {
            "mask_replacement": config_manager.get_audit_mask_replacement(),
            "max_depth": config_manager.get_audit_max_depth(),
            "strict_mode": config_manager.is_audit_strict_mode(),
            "mask_in_metadata": config_manager.should_mask_metadata(),
            "case_sensitive": case_sensitive,
            "sensitive_keys": sensitive_keys,
            "custom_patterns": config_manager.get_audit_custom_patterns(),
        }

    def _create_field_checker(self, config: dict[str, Any]):
        """Create a field sensitivity checker function."""

        def is_field_sensitive(field_name: str) -> bool:
            """Check if a field should be masked."""
            check_name = field_name if config["case_sensitive"] else field_name.lower()

            # Check if any sensitive key appears in the field name
            if any(key in check_name for key in config["sensitive_keys"]):
                return True

            # Check suffix patterns
            if check_name.endswith(MaskingConstants.SENSITIVE_SUFFIXES):
                return True

            # Check custom patterns
            return self._check_custom_patterns(field_name, config["custom_patterns"])

        return is_field_sensitive

    def _check_custom_patterns(
        self,
        field_name: str,
        custom_patterns: list[str],
    ) -> bool:
        """Check field against custom regex patterns."""
        if not custom_patterns:
            return False

        import re

        for pattern_str in custom_patterns:
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(field_name):
                    return True
            except re.error:
                continue
        return False

    def _create_dict_masker(self, config: dict[str, Any], is_field_sensitive):
        """Create a dictionary masking function."""

        def mask_dict(d: dict[str, Any], depth: int = 0) -> None:
            """Recursively mask sensitive keys in dictionary."""
            if depth >= config["max_depth"]:
                return

            for key in list(d.keys()):
                self._mask_dict_key(
                    d,
                    key,
                    config,
                    is_field_sensitive,
                    mask_dict,
                    depth,
                )

        return mask_dict

    def _mask_dict_key(
        self,
        d: dict[str, Any],
        key: str,
        config: dict[str, Any],
        is_field_sensitive,
        mask_dict,
        depth: int,
    ) -> None:
        """Mask a single key in a dictionary."""
        try:
            # Skip None values - don't mask them
            if d[key] is None:
                return

            # Check if field is sensitive
            if is_field_sensitive(key):
                d[key] = config["mask_replacement"]
            # Recursively mask nested dictionaries
            elif isinstance(d[key], dict):
                mask_dict(d[key], depth + 1)
            # Handle lists containing dictionaries
            elif isinstance(d[key], list):
                for item in d[key]:
                    if isinstance(item, dict):
                        mask_dict(item, depth + 1)
        except Exception as e:
            if config["strict_mode"]:
                msg = f"Failed to mask field '{key}': {e}"
                raise Exception(msg) from e
            # In non-strict mode, continue masking other fields
