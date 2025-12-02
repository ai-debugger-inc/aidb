"""Unit tests for ServiceDependencyService."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aidb_cli.core.yaml import YamlOperationError
from aidb_cli.services.docker.service_dependency_service import (
    ServiceDependency,
    ServiceDependencyService,
)


class TestServiceDependency:
    """Test the ServiceDependency data class."""

    def test_init_with_all_params(self):
        """Test creating ServiceDependency with all parameters."""
        dep = ServiceDependency(
            name="postgres",
            profiles=["mcp"],
            depends_on=["redis", "kafka"],
            health_check={"test": ["CMD", "pg_isready"]},
            container_name="test-postgres",
        )

        assert dep.name == "postgres"
        assert dep.profiles == ["mcp"]
        assert dep.depends_on == ["redis", "kafka"]
        assert dep.health_check == {"test": ["CMD", "pg_isready"]}
        assert dep.container_name == "test-postgres"
        assert dep.started is False
        assert dep.healthy is False

    def test_init_with_minimal_params(self):
        """Test creating ServiceDependency with only required parameters."""
        dep = ServiceDependency(name="redis")

        assert dep.name == "redis"
        assert dep.profiles == []
        assert dep.depends_on == []
        assert dep.health_check is None
        assert dep.container_name is None
        assert dep.started is False
        assert dep.healthy is False

    def test_default_values(self):
        """Test ServiceDependency default values."""
        dep = ServiceDependency(name="api")

        assert dep.depends_on == []
        assert dep.started is False
        assert dep.healthy is False

    def test_optional_params(self):
        """Test ServiceDependency with selective optional parameters."""
        dep = ServiceDependency(
            name="api",
            profiles=["mcp"],
            health_check={"test": ["CMD", "curl", "http://localhost:8000/health"]},
        )

        assert dep.name == "api"
        assert dep.profiles == ["mcp"]
        assert dep.depends_on == []
        assert dep.health_check is not None
        assert dep.container_name is None
        assert dep.extends is None

    def test_with_extends(self):
        """Test ServiceDependency with extends parameter."""
        dep = ServiceDependency(
            name="mcp-test-runner",
            profiles=["mcp"],
            extends="test-runner",
        )

        assert dep.name == "mcp-test-runner"
        assert dep.extends == "test-runner"
        assert dep.profiles == ["mcp"]

    def test_extends_defaults_to_none(self):
        """Test that extends defaults to None."""
        dep = ServiceDependency(name="api")

        assert dep.extends is None


class TestServiceDependencyService:
    """Test the ServiceDependencyService."""

    @pytest.fixture
    def mock_command_executor(self):
        """Create a mock command executor."""
        executor = Mock()
        executor.execute = Mock()
        return executor

    @pytest.fixture
    def service(self, tmp_path, mock_command_executor):
        """Create service instance with mocks."""
        return ServiceDependencyService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

    @pytest.fixture
    def sample_compose_data(self):
        """Create sample docker-compose data structure."""
        return {
            "services": {
                "postgres": {
                    "profiles": ["mcp"],
                    "depends_on": ["redis"],
                    "healthcheck": {
                        "test": ["CMD", "pg_isready"],
                        "interval": "10s",
                    },
                    "container_name": "test-postgres",
                },
                "redis": {
                    "profiles": ["mcp"],
                    "healthcheck": {
                        "test": ["CMD", "redis-cli", "ping"],
                    },
                },
                "api": {
                    "profiles": ["mcp"],
                    "depends_on": {
                        "postgres": {"condition": "service_healthy"},
                        "redis": {"condition": "service_started"},
                    },
                },
                "frontend": {
                    "depends_on": ["api"],
                },
            },
        }

    def test_init(self, tmp_path, mock_command_executor):
        """Test service initialization."""
        service = ServiceDependencyService(
            repo_root=tmp_path,
            command_executor=mock_command_executor,
        )

        assert service.repo_root == tmp_path
        assert service.command_executor == mock_command_executor
        assert service.services == {}
        assert (
            service.compose_file == tmp_path / "src/tests/_docker/docker-compose.yaml"
        )

    def test_init_empty_services_dict(self, service):
        """Test services dict is empty on initialization."""
        assert isinstance(service.services, dict)
        assert len(service.services) == 0

    def test_load_services_happy_path(self, service, tmp_path, sample_compose_data):
        """Test loading services from valid compose file."""
        compose_file = tmp_path / "docker-compose.yaml"
        compose_file.touch()

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = sample_compose_data

            service.load_services(compose_file)

            assert len(service.services) == 4
            assert "postgres" in service.services
            assert "redis" in service.services
            assert "api" in service.services
            assert "frontend" in service.services

    def test_load_services_list_depends_on(self, service, tmp_path):
        """Test loading services with list-style depends_on."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        compose_data = {
            "services": {
                "web": {
                    "depends_on": ["db", "cache"],
                },
            },
        }

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = compose_data

            service.load_services(compose_file)

            web_service = service.get_service("web")
            assert web_service.depends_on == ["db", "cache"]

    def test_load_services_dict_depends_on(self, service, tmp_path):
        """Test loading services with dict-style depends_on (conditions)."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        compose_data = {
            "services": {
                "app": {
                    "depends_on": {
                        "postgres": {"condition": "service_healthy"},
                        "redis": {"condition": "service_started"},
                    },
                },
            },
        }

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = compose_data

            service.load_services(compose_file)

            app_service = service.get_service("app")
            assert set(app_service.depends_on) == {"postgres", "redis"}

    def test_load_services_extracts_profiles(
        self,
        service,
        tmp_path,
        sample_compose_data,
    ):
        """Test loading services extracts profiles list."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = sample_compose_data

            service.load_services(compose_file)

            postgres = service.get_service("postgres")
            assert postgres.profiles == ["mcp"]

    def test_load_services_extracts_health_check(
        self,
        service,
        tmp_path,
        sample_compose_data,
    ):
        """Test loading services extracts health check configuration."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = sample_compose_data

            service.load_services(compose_file)

            postgres = service.get_service("postgres")
            assert postgres.health_check is not None
            assert postgres.health_check["test"] == ["CMD", "pg_isready"]

    def test_load_services_extracts_container_name(
        self,
        service,
        tmp_path,
        sample_compose_data,
    ):
        """Test loading services extracts explicit container name."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = sample_compose_data

            service.load_services(compose_file)

            postgres = service.get_service("postgres")
            assert postgres.container_name == "test-postgres"

    def test_load_services_file_not_found(self, service, tmp_path):
        """Test loading services when compose file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.yaml"

        service.load_services(nonexistent_file)

        assert len(service.services) == 0

    def test_load_services_invalid_yaml(self, service, tmp_path):
        """Test loading services with invalid YAML (YamlOperationError)."""
        compose_file = tmp_path / "compose.yaml"

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.side_effect = YamlOperationError("Invalid YAML")

            service.load_services(compose_file)

            assert len(service.services) == 0

    def test_load_services_invalid_structure_key_error(self, service, tmp_path):
        """Test loading services with invalid structure (KeyError)."""
        compose_file = tmp_path / "compose.yaml"

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.side_effect = KeyError("missing key")

            service.load_services(compose_file)

            assert len(service.services) == 0

    def test_load_services_invalid_structure_type_error(self, service, tmp_path):
        """Test loading services with invalid structure (TypeError)."""
        compose_file = tmp_path / "compose.yaml"

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.side_effect = TypeError("Invalid type")

            service.load_services(compose_file)

            assert len(service.services) == 0

    def test_load_services_invalid_structure_attribute_error(self, service, tmp_path):
        """Test loading services with invalid structure (AttributeError)."""
        compose_file = tmp_path / "compose.yaml"

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.side_effect = AttributeError("Missing attribute")

            service.load_services(compose_file)

            assert len(service.services) == 0

    def test_resolve_dependencies_single_no_deps(self, service):
        """Test resolving dependencies for single service with no dependencies."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
        }

        result = service.resolve_dependencies("redis")

        assert result == ["redis"]

    def test_resolve_dependencies_one_dependency(self, service):
        """Test resolving dependencies for service with one dependency."""
        service.services = {
            "db": ServiceDependency(name="db"),
            "api": ServiceDependency(name="api", depends_on=["db"]),
        }

        result = service.resolve_dependencies("api")

        assert result == ["db", "api"]

    def test_resolve_dependencies_chain(self, service):
        """Test resolving dependencies with chain (A→B→C)."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
            "db": ServiceDependency(name="db", depends_on=["redis"]),
            "api": ServiceDependency(name="api", depends_on=["db"]),
        }

        result = service.resolve_dependencies("api")

        assert result == ["redis", "db", "api"]

    def test_resolve_dependencies_multiple_dependencies(self, service):
        """Test resolving dependencies for service with multiple dependencies."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
            "db": ServiceDependency(name="db"),
            "cache": ServiceDependency(name="cache"),
            "api": ServiceDependency(name="api", depends_on=["db", "redis", "cache"]),
        }

        result = service.resolve_dependencies("api")

        assert len(result) == 4
        assert "api" in result
        assert "db" in result
        assert "redis" in result
        assert "cache" in result
        assert result[-1] == "api"

    def test_resolve_dependencies_service_not_found(self, service):
        """Test resolving dependencies for non-existent service."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
        }

        result = service.resolve_dependencies("nonexistent")

        assert result == ["nonexistent"]

    def test_resolve_dependencies_complex_graph(self, service):
        """Test resolving dependencies with complex dependency graph."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
            "kafka": ServiceDependency(name="kafka"),
            "db": ServiceDependency(name="db", depends_on=["redis"]),
            "api": ServiceDependency(name="api", depends_on=["db", "kafka"]),
            "frontend": ServiceDependency(name="frontend", depends_on=["api"]),
        }

        result = service.resolve_dependencies("frontend")

        assert len(result) == 5
        assert result[-1] == "frontend"
        assert result.index("redis") < result.index("db")
        assert result.index("db") < result.index("api")
        assert result.index("kafka") < result.index("api")
        assert result.index("api") < result.index("frontend")

    def test_get_services_by_profile_matching(self, service):
        """Test getting services by profile with matches."""
        service.services = {
            "postgres": ServiceDependency(name="postgres", profiles=["mcp"]),
            "redis": ServiceDependency(name="redis", profiles=["mcp"]),
            "api": ServiceDependency(name="api", profiles=["mcp"]),
            "frontend": ServiceDependency(name="frontend", profiles=["frontend"]),
        }

        result = service.get_services_by_profile("mcp")

        assert len(result) == 3
        assert "postgres" in result
        assert "redis" in result
        assert "api" in result
        assert "frontend" not in result

    def test_get_services_by_profile_no_matches(self, service):
        """Test getting services by profile with no matches."""
        service.services = {
            "postgres": ServiceDependency(name="postgres", profiles=["mcp"]),
            "redis": ServiceDependency(name="redis", profiles=["mcp"]),
        }

        result = service.get_services_by_profile("nonexistent")

        assert result == []

    def test_get_services_by_profile_empty_profiles(self, service):
        """Test getting services with empty profiles list."""
        service.services = {
            "postgres": ServiceDependency(name="postgres", profiles=["mcp"]),
            "redis": ServiceDependency(name="redis", profiles=[]),
            "cache": ServiceDependency(name="cache"),
        }

        # Services with empty profiles won't match any profile
        result = service.get_services_by_profile("mcp")

        assert len(result) == 1
        assert "postgres" in result

    def test_mark_service_started(self, service):
        """Test marking service as started."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        assert service.services["postgres"].started is False

        service.mark_service_started("postgres")

        assert service.services["postgres"].started is True

    def test_mark_service_started_not_found(self, service):
        """Test marking non-existent service as started doesn't crash."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        service.mark_service_started("nonexistent")

        assert len(service.services) == 1

    def test_mark_service_healthy(self, service):
        """Test marking service as healthy."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        assert service.services["postgres"].healthy is False

        service.mark_service_healthy("postgres")

        assert service.services["postgres"].healthy is True

    def test_mark_service_healthy_not_found(self, service):
        """Test marking non-existent service as healthy doesn't crash."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        service.mark_service_healthy("nonexistent")

        assert len(service.services) == 1

    def test_service_state_persists(self, service):
        """Test service state changes persist."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        service.mark_service_started("postgres")
        service.mark_service_healthy("postgres")

        postgres = service.get_service("postgres")
        assert postgres.started is True
        assert postgres.healthy is True

    def test_multiple_service_state_management(self, service):
        """Test managing state for multiple services."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
            "redis": ServiceDependency(name="redis"),
            "api": ServiceDependency(name="api"),
        }

        service.mark_service_started("postgres")
        service.mark_service_started("redis")
        service.mark_service_healthy("postgres")

        assert service.services["postgres"].started is True
        assert service.services["postgres"].healthy is True
        assert service.services["redis"].started is True
        assert service.services["redis"].healthy is False
        assert service.services["api"].started is False
        assert service.services["api"].healthy is False

    def test_get_service_returns_correct_service(self, service):
        """Test get_service returns correct ServiceDependency."""
        dep = ServiceDependency(name="postgres", profiles=["mcp"])
        service.services = {
            "postgres": dep,
            "redis": ServiceDependency(name="redis"),
        }

        result = service.get_service("postgres")

        assert result is dep
        assert result.name == "postgres"
        assert result.profiles == ["mcp"]

    def test_get_service_not_found(self, service):
        """Test get_service returns None for non-existent service."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        result = service.get_service("nonexistent")

        assert result is None

    def test_get_all_services_returns_full_dict(self, service):
        """Test get_all_services returns complete services dictionary."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
            "redis": ServiceDependency(name="redis"),
            "api": ServiceDependency(name="api"),
        }

        result = service.get_all_services()

        assert result is service.services
        assert len(result) == 3
        assert "postgres" in result
        assert "redis" in result
        assert "api" in result

    def test_cleanup_resets_all_states(self, service):
        """Test cleanup resets all service states."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
            "redis": ServiceDependency(name="redis"),
        }

        service.mark_service_started("postgres")
        service.mark_service_healthy("postgres")
        service.mark_service_started("redis")
        service.mark_service_healthy("redis")

        assert service.services["postgres"].started is True
        assert service.services["postgres"].healthy is True
        assert service.services["redis"].started is True
        assert service.services["redis"].healthy is True

        service.cleanup()

        assert service.services["postgres"].started is False
        assert service.services["postgres"].healthy is False
        assert service.services["redis"].started is False
        assert service.services["redis"].healthy is False

    def test_cleanup_with_empty_services(self, service):
        """Test cleanup works with no services loaded."""
        assert len(service.services) == 0

        service.cleanup()

        assert len(service.services) == 0

    def test_get_container_name_exists(self, service):
        """Test getting container name for a service with explicit container_name."""
        service.services = {
            "postgres": ServiceDependency(
                name="postgres",
                container_name="test-postgres-container",
            ),
        }

        result = service.get_container_name("postgres")

        assert result == "test-postgres-container"

    def test_get_container_name_not_found(self, service):
        """Test getting container name for non-existent service."""
        service.services = {
            "postgres": ServiceDependency(name="postgres"),
        }

        result = service.get_container_name("nonexistent")

        assert result is None

    def test_get_container_name_no_explicit_name(self, service):
        """Test getting container name when service has no explicit container_name."""
        service.services = {
            "redis": ServiceDependency(name="redis"),
        }

        result = service.get_container_name("redis")

        assert result is None

    def test_load_services_extracts_extends_string(self, service, tmp_path):
        """Test loading services extracts extends as string."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        compose_data = {
            "services": {
                "test-runner": {
                    "build": {"context": "."},
                },
                "mcp-test-runner": {
                    "extends": "test-runner",
                    "profiles": ["mcp"],
                },
            },
        }

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = compose_data

            service.load_services(compose_file)

            mcp_service = service.get_service("mcp-test-runner")
            assert mcp_service.extends == "test-runner"

            base_service = service.get_service("test-runner")
            assert base_service.extends is None

    def test_load_services_extracts_extends_dict(self, service, tmp_path):
        """Test loading services extracts extends as dict with service key."""
        compose_file = tmp_path / "compose.yaml"
        compose_file.touch()

        compose_data = {
            "services": {
                "test-runner": {
                    "build": {"context": "."},
                },
                "mcp-test-runner": {
                    "extends": {
                        "service": "test-runner",
                    },
                    "profiles": ["mcp"],
                },
            },
        }

        with patch(
            "aidb_cli.services.docker.service_dependency_service.safe_read_yaml",
        ) as mock_read:
            mock_read.return_value = compose_data

            service.load_services(compose_file)

            mcp_service = service.get_service("mcp-test-runner")
            assert mcp_service.extends == "test-runner"

    def test_get_buildable_services_by_profile_excludes_extends(self, service):
        """Test that services with extends are excluded from buildable list."""
        service.services = {
            "test-runner": ServiceDependency(
                name="test-runner",
                profiles=["base"],
                has_build=True,
            ),
            "mcp-test-runner": ServiceDependency(
                name="mcp-test-runner",
                profiles=["base", "mcp"],
                has_build=True,
                extends="test-runner",
            ),
            "adapters-test-runner": ServiceDependency(
                name="adapters-test-runner",
                profiles=["adapters"],
                has_build=True,
                extends="test-runner",
            ),
        }

        result = service.get_buildable_services_by_profile("base")

        assert len(result) == 1
        assert "test-runner" in result
        assert "mcp-test-runner" not in result

    def test_get_all_buildable_services_excludes_extends(self, service):
        """Test that get_all_buildable_services excludes services with extends."""
        service.services = {
            "test-runner": ServiceDependency(
                name="test-runner",
                profiles=["base"],
                has_build=True,
            ),
            "mcp-test-runner": ServiceDependency(
                name="mcp-test-runner",
                profiles=["mcp"],
                has_build=True,
                extends="test-runner",
            ),
            "test-runner-java": ServiceDependency(
                name="test-runner-java",
                profiles=["java"],
                has_build=True,
            ),
        }

        result = service.get_all_buildable_services()

        assert len(result) == 2
        assert "test-runner" in result
        assert "test-runner-java" in result
        assert "mcp-test-runner" not in result
