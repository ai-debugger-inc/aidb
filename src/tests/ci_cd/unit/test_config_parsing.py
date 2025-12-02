"""Unit tests for CI/CD configuration parsing."""

import json


class TestVersionsJsonParsing:
    """Test versions.json parsing utilities."""

    def test_versions_json_is_valid_json(self, repo_root):
        """Verify versions.json is valid JSON."""
        versions_path = repo_root / "versions.json"
        with versions_path.open() as f:
            data = json.load(f)

        assert data is not None
        assert isinstance(data, dict)

    def test_can_extract_infrastructure_versions(self, versions_json):
        """Verify infrastructure versions can be extracted."""
        infrastructure = versions_json["infrastructure"]

        python_version = infrastructure["python"]["version"]
        node_version = infrastructure["node"]["version"]
        java_version = infrastructure["java"]["version"]

        assert python_version is not None
        assert node_version is not None
        assert java_version is not None

    def test_can_extract_adapter_versions(self, versions_json):
        """Verify adapter versions can be extracted."""
        adapters = versions_json["adapters"]

        python_adapter = adapters["python"]["version"]
        js_adapter = adapters["javascript"]["version"]
        java_adapter = adapters["java"]["version"]

        assert python_adapter is not None
        assert js_adapter is not None
        assert java_adapter is not None
