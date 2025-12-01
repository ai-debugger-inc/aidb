"""Unit tests for audit events."""

import json
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from aidb.audit.events import AuditEvent, AuditLevel
from tests._helpers.audit import AuditEventFactory, AuditTestMixin


class TestAuditEvent(AuditTestMixin):
    """Test AuditEvent class functionality."""

    def test_event_creation_defaults(self):
        """Test event creation with default values."""
        event = AuditEvent()

        # Check defaults
        assert event.level == AuditLevel.INFO
        assert event.component == ""
        assert event.operation == ""
        assert event.session_id is None
        assert event.parameters == {}
        assert event.result == {}
        assert event.metadata != {}  # Should have pid and user
        assert event.error is None

        # Check timestamp is set
        assert event.timestamp
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))

    def test_event_post_init_metadata(self):
        """Test that post_init adds pid and user to metadata."""
        with patch.dict(os.environ, {"USER": "testuser"}):
            event = AuditEvent(
                component="test",
                operation="test_op",
            )

            assert "pid" in event.metadata
            assert event.metadata["pid"] == os.getpid()
            assert "user" in event.metadata
            assert event.metadata["user"] == "testuser"

    def test_event_post_init_preserves_existing_metadata(self):
        """Test that post_init doesn't override existing metadata."""
        event = AuditEvent(
            component="test",
            operation="test_op",
            metadata={"pid": 999, "user": "existing", "custom": "value"},
        )

        assert event.metadata["pid"] == 999
        assert event.metadata["user"] == "existing"
        assert event.metadata["custom"] == "value"

    def test_event_to_json(self):
        """Test JSON serialization of events."""
        event = AuditEvent(
            level=AuditLevel.WARNING,
            component="api.test",
            operation="test_operation",
            session_id="session_123",
            parameters={"param1": "value1", "param2": 42},
            result={"success": True, "data": [1, 2, 3]},
            metadata={"language": "python"},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["level"] == "WARNING"
        assert data["component"] == "api.test"
        assert data["operation"] == "test_operation"
        assert data["session_id"] == "session_123"
        assert data["parameters"] == {"param1": "value1", "param2": 42}
        assert data["result"] == {"success": True, "data": [1, 2, 3]}
        assert "language" in data["metadata"]
        assert "pid" in data["metadata"]
        assert "user" in data["metadata"]

    def test_event_to_json_excludes_none(self):
        """Test that None values are excluded from JSON."""
        event = AuditEvent(
            component="test",
            operation="test_op",
            session_id=None,
            error=None,
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert "session_id" not in data
        assert "error" not in data
        assert "component" in data
        assert "operation" in data

    def test_event_to_json_compact_format(self):
        """Test that JSON uses compact separators."""
        event = AuditEvent(
            component="test",
            operation="test_op",
            parameters={"a": 1, "b": 2},
        )

        json_str = event.to_json()
        # Check for compact format (no spaces after colons/commas)
        assert '", "' not in json_str  # No space after comma
        assert '": ' not in json_str  # No space after colon
        assert '","' in json_str or '":"' in json_str  # Compact format

    def test_event_with_error(self):
        """Test event with error information."""
        event = AuditEvent(
            level=AuditLevel.ERROR,
            component="db.connection",
            operation="connect",
            error="Connection refused",
            result={"success": False, "retry_count": 3},
        )

        assert event.level == AuditLevel.ERROR
        assert event.error == "Connection refused"
        assert event.result["success"] is False

        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["error"] == "Connection refused"

    def test_audit_level_enum(self):
        """Test AuditLevel enum values."""
        assert AuditLevel.DEBUG.value == "DEBUG"
        assert AuditLevel.INFO.value == "INFO"
        assert AuditLevel.WARNING.value == "WARNING"
        assert AuditLevel.ERROR.value == "ERROR"
        assert AuditLevel.CRITICAL.value == "CRITICAL"

        # Test all levels are distinct
        levels = list(AuditLevel)
        assert len(levels) == 5
        assert len(set(levels)) == 5

    def test_event_timestamp_timezone(self):
        """Test that timestamps include timezone information."""
        event = AuditEvent(component="test", operation="test_op")

        # Should be ISO format with timezone
        assert "T" in event.timestamp  # ISO separator
        assert any(
            tz in event.timestamp for tz in ["Z", "+", "-"]
        )  # Timezone indicator

        # Should be parseable as timezone-aware datetime
        if event.timestamp.endswith("Z"):
            dt = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(event.timestamp)

        assert dt.tzinfo is not None

    def test_event_factory_basic(self):
        """Test AuditEventFactory basic creation."""
        event = AuditEventFactory.create_event(
            level=AuditLevel.DEBUG,
            component="factory.test",
            operation="create",
            parameters={"test": True},
        )

        assert event.level == AuditLevel.DEBUG
        assert event.component == "factory.test"
        assert event.operation == "create"
        assert event.parameters == {"test": True}
        assert event.result["success"] is True

    def test_event_factory_with_error(self):
        """Test AuditEventFactory with error."""
        event = AuditEventFactory.create_event(
            level=AuditLevel.ERROR,
            error="Test error",
        )

        assert event.level == AuditLevel.ERROR
        assert event.error == "Test error"
        assert event.result["success"] is False

    def test_event_factory_batch(self):
        """Test AuditEventFactory batch creation."""
        events = AuditEventFactory.create_batch(count=10, base_component="batch")

        assert len(events) == 10

        # Check variety in levels
        levels = {e.level for e in events}
        assert AuditLevel.INFO in levels
        assert AuditLevel.WARNING in levels

        # Check sequential operations
        for i, event in enumerate(events):
            assert event.operation == f"operation_{i}"
            assert event.parameters["index"] == i

        # Check some have failures
        successes = [e.result["success"] for e in events]
        assert True in successes
        assert False in successes

    def test_event_validation_mixin(self):
        """Test AuditTestMixin validation methods."""
        event = AuditEvent(
            component="mixin.test",
            operation="validate",
        )

        # Use mixin method to validate
        self.assert_event_valid(event)

        # Test with missing required fields would fail
        invalid_event = AuditEvent()
        invalid_event.component = ""  # Empty component
        with pytest.raises(AssertionError):
            self.assert_event_valid(invalid_event)

    def test_event_large_payload(self):
        """Test event with large payload."""
        large_data = {"key_" + str(i): "value_" * 100 for i in range(100)}

        event = AuditEvent(
            component="test.large",
            operation="process",
            parameters=large_data,
            result={"processed_items": list(range(1000))},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert len(data["parameters"]) == 100
        assert len(data["result"]["processed_items"]) == 1000

    def test_event_special_characters(self):
        """Test event with special characters in strings."""
        event = AuditEvent(
            component="test.special",
            operation="handle_special",
            parameters={
                "unicode": "Hello 世界 🌍",
                "quotes": 'He said "Hello"',
                "backslash": "C:\\Users\\test",
                "newline": "Line1\nLine2",
            },
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["parameters"]["unicode"] == "Hello 世界 🌍"
        assert data["parameters"]["quotes"] == 'He said "Hello"'
        assert data["parameters"]["backslash"] == "C:\\Users\\test"
        assert data["parameters"]["newline"] == "Line1\nLine2"

    def test_event_numeric_types(self):
        """Test event with various numeric types."""
        event = AuditEvent(
            component="test.numeric",
            operation="calculate",
            parameters={
                "int": 42,
                "float": 3.14159,
                "negative": -100,
                "zero": 0,
                "large": 1_000_000_000,
            },
            result={
                "sum": 42.5,
                "product": 0,
                "division": 0.5,
            },
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["parameters"]["int"] == 42
        assert data["parameters"]["float"] == 3.14159
        assert data["parameters"]["negative"] == -100
        assert data["parameters"]["zero"] == 0
        assert data["parameters"]["large"] == 1_000_000_000

    def test_event_boolean_values(self):
        """Test event with boolean values."""
        event = AuditEvent(
            component="test.boolean",
            operation="check",
            parameters={
                "enabled": True,
                "disabled": False,
                "flags": [True, False, True],
            },
            result={"success": True, "failed": False},
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["parameters"]["enabled"] is True
        assert data["parameters"]["disabled"] is False
        assert data["parameters"]["flags"] == [True, False, True]
        assert data["result"]["success"] is True
        assert data["result"]["failed"] is False

    def test_event_nested_structures(self):
        """Test event with deeply nested data structures."""
        event = AuditEvent(
            component="test.nested",
            operation="process_nested",
            parameters={
                "level1": {
                    "level2": {
                        "level3": {
                            "value": "deep",
                            "items": [1, 2, 3],
                        },
                    },
                },
            },
            metadata={
                "config": {
                    "settings": {
                        "debug": True,
                        "options": ["a", "b", "c"],
                    },
                },
            },
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["parameters"]["level1"]["level2"]["level3"]["value"] == "deep"
        assert data["parameters"]["level1"]["level2"]["level3"]["items"] == [1, 2, 3]
        assert data["metadata"]["config"]["settings"]["debug"] is True

    def test_event_empty_collections(self):
        """Test event with empty collections."""
        event = AuditEvent(
            component="test.empty",
            operation="handle_empty",
            parameters={
                "empty_dict": {},
                "empty_list": [],
                "empty_string": "",
            },
        )

        json_str = event.to_json()
        data = json.loads(json_str)

        assert data["parameters"]["empty_dict"] == {}
        assert data["parameters"]["empty_list"] == []
        assert data["parameters"]["empty_string"] == ""
