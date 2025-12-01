"""Unit tests for audit masking functionality.

This module tests the sensitive data masking features of the audit system.
"""

from aidb.audit.events import AuditEvent, AuditLevel
from tests._helpers.audit import AuditTestMixin


class TestMaskSensitiveData(AuditTestMixin):
    """Test the mask_sensitive_data method."""

    def test_mask_basic_sensitive_fields(self):
        """Test masking of basic sensitive fields like password and token."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "username": "john.doe",
            "password": "secret123",
            "token": "abc123xyz",
            "data": "normal_data",
        }

        event.mask_sensitive_data()

        assert event.parameters["username"] == "john.doe"
        assert event.parameters["password"] == "***MASKED***"
        assert event.parameters["token"] == "***MASKED***"
        assert event.parameters["data"] == "normal_data"

    def test_mask_new_critical_fields(self):
        """Test masking of newly added critical fields."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "database_url": "postgresql://user:pass@localhost/db",
            "connection_string": "Server=localhost;Database=mydb;Password=secret",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----",
            "ssh_key": "ssh-rsa AAAAB3NzaC1yc2E...",
            "normal_field": "keep_this",
        }

        event.mask_sensitive_data()

        assert event.parameters["database_url"] == "***MASKED***"
        assert event.parameters["connection_string"] == "***MASKED***"
        assert event.parameters["private_key"] == "***MASKED***"
        assert event.parameters["ssh_key"] == "***MASKED***"
        assert event.parameters["normal_field"] == "keep_this"

    def test_mask_pattern_based_fields(self):
        """Test masking of fields based on suffix patterns."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "api_key": "key123",
            "custom_key": "mykey456",
            "auth_token": "token789",
            "session_token": "session123",
            "app_secret": "secret456",
            "db_password": "dbpass789",
            "webhook_url": "https://example.com/webhook",
            "normal_value": "keep_this",
        }

        event.mask_sensitive_data()

        assert event.parameters["api_key"] == "***MASKED***"
        assert event.parameters["custom_key"] == "***MASKED***"
        assert event.parameters["auth_token"] == "***MASKED***"
        assert event.parameters["session_token"] == "***MASKED***"
        assert event.parameters["app_secret"] == "***MASKED***"
        assert event.parameters["db_password"] == "***MASKED***"
        assert event.parameters["webhook_url"] == "***MASKED***"
        assert event.parameters["normal_value"] == "keep_this"

    def test_mask_case_insensitive(self):
        """Test that masking is case-insensitive."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "PASSWORD": "secret1",
            "Password": "secret2",
            "password": "secret3",
            "API_KEY": "key1",
            "api_key": "key3",
            "AUTH_TOKEN": "token1",
            "authToken": "token2",
            "auth_token": "token3",
        }

        event.mask_sensitive_data()

        assert event.parameters["PASSWORD"] == "***MASKED***"
        assert event.parameters["Password"] == "***MASKED***"
        assert event.parameters["password"] == "***MASKED***"
        assert event.parameters["API_KEY"] == "***MASKED***"
        assert event.parameters["api_key"] == "***MASKED***"
        assert event.parameters["AUTH_TOKEN"] == "***MASKED***"
        assert event.parameters["authToken"] == "***MASKED***"
        assert event.parameters["auth_token"] == "***MASKED***"

    def test_mask_nested_dictionaries(self):
        """Test masking in nested dictionary structures."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "user": {
                "name": "john",
                "password": "secret123",
                "profile": {
                    "email": "john@example.com",
                    "api_key": "key123",
                    "preferences": {
                        "theme": "dark",
                        "session_token": "token456",
                    },
                },
            },
            "system": {
                "version": "1.0",
                "database_url": "postgresql://localhost",
            },
        }

        event.mask_sensitive_data()

        assert event.parameters["user"]["name"] == "john"
        assert event.parameters["user"]["password"] == "***MASKED***"
        assert event.parameters["user"]["profile"]["email"] == "john@example.com"
        assert event.parameters["user"]["profile"]["api_key"] == "***MASKED***"
        assert event.parameters["user"]["profile"]["preferences"]["theme"] == "dark"
        assert (
            event.parameters["user"]["profile"]["preferences"]["session_token"]
            == "***MASKED***"
        )
        assert event.parameters["system"]["version"] == "1.0"
        assert event.parameters["system"]["database_url"] == "***MASKED***"

    def test_mask_lists_containing_dicts(self):
        """Test masking in lists containing dictionaries."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "users": [
                {"name": "alice", "password": "pass1"},
                {"name": "bob", "token": "token2"},
                {"name": "charlie", "api_key": "key3"},
            ],
            "configs": [
                {"setting": "value1", "database_url": "db_url1"},
                {"setting": "value2", "connection_string": "conn_str2"},
            ],
        }

        event.mask_sensitive_data()

        assert event.parameters["users"][0]["name"] == "alice"
        assert event.parameters["users"][0]["password"] == "***MASKED***"
        assert event.parameters["users"][1]["name"] == "bob"
        assert event.parameters["users"][1]["token"] == "***MASKED***"
        assert event.parameters["users"][2]["name"] == "charlie"
        assert event.parameters["users"][2]["api_key"] == "***MASKED***"
        assert event.parameters["configs"][0]["setting"] == "value1"
        assert event.parameters["configs"][0]["database_url"] == "***MASKED***"
        assert event.parameters["configs"][1]["setting"] == "value2"
        assert event.parameters["configs"][1]["connection_string"] == "***MASKED***"

    def test_mask_metadata(self):
        """Test that metadata is also masked."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.metadata = {
            "request_id": "req123",
            "auth_token": "token456",
            "api_secret": "secret789",
        }

        event.mask_sensitive_data()

        assert event.metadata["request_id"] == "req123"
        assert event.metadata["auth_token"] == "***MASKED***"
        assert event.metadata["api_secret"] == "***MASKED***"

    def test_mask_with_additional_keys(self):
        """Test masking with additional custom sensitive keys."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "username": "john",
            "password": "secret123",
            "custom_sensitive": "sensitive_data",
            "my_special_field": "special_value",
            "normal_field": "keep_this",
        }

        # Add custom sensitive keys
        event.mask_sensitive_data(additional_keys={"custom_sensitive", "my_special"})

        assert event.parameters["username"] == "john"
        assert event.parameters["password"] == "***MASKED***"
        assert event.parameters["custom_sensitive"] == "***MASKED***"
        assert event.parameters["my_special_field"] == "***MASKED***"
        assert event.parameters["normal_field"] == "keep_this"

    def test_mask_empty_parameters(self):
        """Test masking with empty parameters and metadata."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {}
        event.metadata = {}

        # Should not raise any errors
        event.mask_sensitive_data()

        assert event.parameters == {}
        assert event.metadata == {}

    def test_mask_none_values(self):
        """Test masking handles None values gracefully."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "password": None,
            "token": "token123",
            "data": None,
        }

        event.mask_sensitive_data()

        assert event.parameters["password"] is None
        assert event.parameters["token"] == "***MASKED***"
        assert event.parameters["data"] is None

    def test_mask_mixed_types(self):
        """Test masking with mixed data types."""
        event = AuditEvent(
            level=AuditLevel.INFO,
            component="test",
            operation="test_op",
        )
        event.parameters = {
            "count": 42,
            "password": "secret123",
            "enabled": True,
            "api_key": "key456",
            "ratio": 3.14,
            "database_url": "db_url",
            "items": ["item1", "item2"],
            "nested": [
                {"token": "token789", "value": 100},
            ],
        }

        event.mask_sensitive_data()

        assert event.parameters["count"] == 42
        assert event.parameters["password"] == "***MASKED***"
        assert event.parameters["enabled"] is True
        assert event.parameters["api_key"] == "***MASKED***"
        assert event.parameters["ratio"] == 3.14
        assert event.parameters["database_url"] == "***MASKED***"
        assert event.parameters["items"] == ["item1", "item2"]
        assert event.parameters["nested"][0]["token"] == "***MASKED***"
        assert event.parameters["nested"][0]["value"] == 100
