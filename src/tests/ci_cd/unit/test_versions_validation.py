"""Unit tests for versions.json validation logic."""

import pytest


class TestVersionsJsonStructure:
    """Test versions.json structure and completeness."""

    def test_has_required_top_level_keys(self, versions_json):
        """Verify versions.json has all required top-level keys."""
        required_keys = [
            "version",
            "infrastructure",
            "adapters",
            "platforms",
        ]
        for key in required_keys:
            assert key in versions_json, f"Missing required key: {key}"

    def test_infrastructure_has_python_node_java(self, versions_json):
        """Verify infrastructure section has Python, Node, and Java."""
        infrastructure = versions_json["infrastructure"]
        assert "python" in infrastructure
        assert "node" in infrastructure
        assert "java" in infrastructure

    def test_infrastructure_versions_are_strings(self, versions_json):
        """Verify infrastructure versions are string values."""
        infrastructure = versions_json["infrastructure"]
        for lang in ["python", "node", "java"]:
            assert "version" in infrastructure[lang]
            assert isinstance(infrastructure[lang]["version"], str)

    def test_adapters_has_python_javascript_java(self, versions_json):
        """Verify adapters section has all supported languages."""
        adapters = versions_json["adapters"]
        assert "python" in adapters
        assert "javascript" in adapters
        assert "java" in adapters

    def test_adapter_versions_format(self, versions_json):
        """Verify adapter versions are properly formatted."""
        adapters = versions_json["adapters"]

        # Python: should be semantic version string
        assert isinstance(adapters["python"]["version"], str)
        assert adapters["python"]["version"].count(".") == 2  # X.Y.Z format

        # JavaScript: may have 'v' prefix
        js_version = adapters["javascript"]["version"]
        assert isinstance(js_version, str)
        assert js_version.startswith("v") or js_version[0].isdigit()

        # Java: should be semantic version
        java_version = adapters["java"]["version"]
        assert isinstance(java_version, (str, float))

    def test_platforms_list_not_empty(self, versions_json):
        """Verify platforms list is populated."""
        platforms = versions_json["platforms"]
        assert isinstance(platforms, list)
        assert len(platforms) > 0

    def test_platforms_have_required_fields(self, versions_json):
        """Verify each platform has required fields."""
        platforms = versions_json["platforms"]
        required_fields = ["os", "platform", "arch"]

        for platform in platforms:
            for field in required_fields:
                assert field in platform, f"Platform missing field: {field}"

    def test_platforms_cover_major_architectures(self, versions_json):
        """Verify platforms cover linux, darwin, and windows."""
        platforms = versions_json["platforms"]
        platform_names = {p["platform"] for p in platforms}

        assert "linux" in platform_names
        assert "darwin" in platform_names
        assert "windows" in platform_names


class TestVersionsJsonConsistency:
    """Test internal consistency of versions.json."""

    def test_infrastructure_python_matches_docker_tag(self, versions_json):
        """Verify Python version matches docker_tag format."""
        python = versions_json["infrastructure"]["python"]
        version = python["version"]
        docker_tag = python.get("docker_tag", "")

        # docker_tag should start with version (e.g., "3.12" in "3.12-slim")
        assert docker_tag.startswith(version), (
            f"Docker tag '{docker_tag}' doesn't match version '{version}'"
        )

    def test_infrastructure_node_matches_docker_tag(self, versions_json):
        """Verify Node version matches docker_tag format."""
        node = versions_json["infrastructure"]["node"]
        version = node["version"]
        docker_tag = node.get("docker_tag", "")

        # docker_tag should start with version
        assert docker_tag.startswith(version), (
            f"Docker tag '{docker_tag}' doesn't match version '{version}'"
        )

    def test_adapter_repos_are_github(self, versions_json):
        """Verify all adapter repos are from GitHub."""
        adapters = versions_json["adapters"]

        for adapter_name, adapter_config in adapters.items():
            repo = adapter_config.get("repo", "")
            assert "/" in repo, f"{adapter_name} repo should be in owner/name format"
            # Should be microsoft repos
            assert "microsoft" in repo.lower() or "github" in repo.lower()


class TestDebugpySynchronization:
    """Test debugpy version synchronization between versions.json and pyproject.toml."""

    def test_debugpy_version_exists_in_versions_json(self, versions_json):
        """Verify debugpy version is specified in adapters.python."""
        python_adapter = versions_json["adapters"]["python"]
        assert "version" in python_adapter
        assert python_adapter["version"]  # Not empty

    def test_debugpy_minimum_version_format(self, versions_json):
        """Verify debugpy version follows semantic versioning."""
        python_adapter = versions_json["adapters"]["python"]
        version = python_adapter["version"]

        # Should be X.Y.Z format
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)
