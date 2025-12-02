"""Docker Compose generation service.

This service generates docker-compose.yaml files programmatically from declarative
language configurations and Jinja2 templates.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aidb_cli.core.paths import CachePaths, ProjectPaths
from aidb_cli.core.yaml import YamlOperationError, safe_read_yaml
from aidb_common.config import VersionManager
from aidb_common.io import (
    compute_files_hash,
    read_cache_file,
    write_cache_file,
)
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class ComposeGeneratorService:
    """Service for generating docker-compose.yaml from templates."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize the compose generator service.

        Parameters
        ----------
        repo_root : Path
            Repository root directory
        """
        self.repo_root = repo_root
        self.docker_dir = repo_root / ProjectPaths.TEST_DOCKER_DIR
        self.templates_dir = repo_root / ProjectPaths.TEST_DOCKER_TEMPLATES
        self.languages_file = repo_root / ProjectPaths.TEST_DOCKER_LANGUAGES
        self.base_compose_file = repo_root / ProjectPaths.TEST_DOCKER_BASE_COMPOSE
        self.output_file = repo_root / ProjectPaths.TEST_DOCKER_COMPOSE
        cache_dir = CachePaths.compose_cache_dir(repo_root)
        self.hash_cache_file = cache_dir / "compose-generation-hash"

        self.version_manager = VersionManager(repo_root / ProjectPaths.VERSIONS_YAML)

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _compute_source_hash(self) -> str:
        """Compute hash of source files to detect changes.

        Returns
        -------
        str
            SHA256 hash of all source files
        """
        source_files = [
            self.languages_file,
            self.repo_root / ProjectPaths.VERSIONS_YAML,
            self.base_compose_file,
        ]

        # Add all template files (sorted for deterministic ordering)
        template_files = sorted(self.templates_dir.glob("*.j2"))
        source_files.extend(template_files)

        return compute_files_hash(source_files)

    def _get_cached_hash(self) -> str | None:
        """Get cached hash from previous generation.

        Returns
        -------
        str | None
            Cached hash or None if not found
        """
        return read_cache_file(self.hash_cache_file)

    def _save_hash(self, hash_value: str) -> None:
        """Save hash to cache file.

        Parameters
        ----------
        hash_value : str
            Hash to save
        """
        write_cache_file(self.hash_cache_file, hash_value)

    def needs_regeneration(self) -> bool:
        """Check if compose file needs regeneration.

        Returns
        -------
        bool
            True if regeneration is needed
        """
        if not self.output_file.exists():
            logger.debug("Output file does not exist, regeneration needed")
            return True

        current_hash = self._compute_source_hash()
        cached_hash = self._get_cached_hash()

        if cached_hash != current_hash:
            logger.debug(
                "Source files changed (hash mismatch), regeneration needed",
            )
            return True

        logger.debug("No changes detected, using cached compose file")
        return False

    def _load_languages_config(self) -> dict[str, Any]:
        """Load language configurations from languages.yaml.

        Returns
        -------
        dict[str, Any]
            Language configurations
        """
        config = safe_read_yaml(self.languages_file)
        return config.get("languages", {})

    def _generate_language_services(self, languages: dict[str, Any]) -> str:
        """Generate YAML for all language-specific services.

        Parameters
        ----------
        languages : dict[str, Any]
            Language configurations from languages.yaml

        Returns
        -------
        str
            Generated YAML content
        """
        framework_template = self.jinja_env.get_template(
            "framework-test-runner.yaml.j2",
        )
        mcp_template = self.jinja_env.get_template("mcp-test-runner.yaml.j2")

        sections = []

        sections.append(
            "  # ===========================",
        )
        sections.append(
            "  # LANGUAGE-SPECIFIC: Framework Testing per Language",
        )
        sections.append(
            "  # Generated from templates - do not edit manually",
        )
        sections.append(
            "  # ===========================",
        )

        for lang, config in sorted(languages.items()):
            sections.append(
                framework_template.render(lang=lang, config=config),
            )

        sections.append("")
        sections.append(
            "  # Language-specific MCP runners (generated)",
        )

        for lang, config in sorted(languages.items()):
            sections.append(mcp_template.render(lang=lang, config=config))

        return "\n".join(sections)

    def _merge_compose_files(self, language_services: str) -> str:
        """Merge base compose file with generated language services.

        Parameters
        ----------
        language_services : str
            Generated language service YAML

        Returns
        -------
        str
            Complete merged compose file content
        """
        base_content = self.base_compose_file.read_text()

        header = [
            "# Docker Compose configuration for AIDB testing",
            "# This file is AUTO-GENERATED by ComposeGeneratorService",
            "# DO NOT EDIT MANUALLY - changes will be overwritten",
            "#",
            "# To modify:",
            "#   - Static services: Edit docker-compose.base.yaml",
            "#   - Language configs: Edit languages.yaml",
            "#   - Service templates: Edit templates/*.j2",
            "#",
            "# Generation is automatic when running './dev-cli test run'",
            "",
        ]

        lines = base_content.split("\n")

        for i, line in enumerate(lines):
            if line.strip().startswith("services:"):
                services_line = i
                break
        else:
            msg = "Could not find 'services:' section in base compose file"
            raise ValueError(msg)

        for i in range(services_line + 1, len(lines)):
            is_top_level = lines[i] and not lines[i].startswith((" ", "#"))
            if is_top_level:
                end_services_line = i
                break
        else:
            end_services_line = len(lines)

        # Insert generated services just before the end of services section
        merged_lines = (
            header
            + lines[:end_services_line]
            + [language_services, ""]
            + lines[end_services_line:]
        )

        return "\n".join(merged_lines)

    def generate(self, force: bool = False) -> tuple[bool, str]:
        """Generate docker-compose.yaml file.

        Parameters
        ----------
        force : bool, optional
            Force regeneration even if cache is valid

        Returns
        -------
        tuple[bool, str]
            (was_generated, output_path)
        """
        if not force and not self.needs_regeneration():
            logger.info("Compose file is up to date, skipping regeneration")
            return False, str(self.output_file)

        logger.info("Generating docker-compose.yaml from templates...")

        languages = self._load_languages_config()
        logger.debug("Loaded %d language configurations", len(languages))

        language_services = self._generate_language_services(languages)
        logger.debug("Generated language-specific services")

        merged_content = self._merge_compose_files(language_services)
        logger.debug("Merged base and generated content")

        self.output_file.write_text(merged_content)
        logger.info("Generated compose file: %s", self.output_file)

        current_hash = self._compute_source_hash()
        self._save_hash(current_hash)
        logger.debug("Saved generation hash: %s", current_hash[:12])

        return True, str(self.output_file)

    def validate_generated_file(self) -> tuple[bool, list[str]]:
        """Validate that generated file is syntactically correct.

        Returns
        -------
        tuple[bool, list[str]]
            (is_valid, error_messages)
        """
        errors = []

        if not self.output_file.exists():
            errors.append(f"Generated file does not exist: {self.output_file}")
            return False, errors

        try:
            safe_read_yaml(self.output_file)
            logger.debug("Generated compose file is valid YAML")
        except YamlOperationError as e:
            errors.append(str(e))
            return False, errors

        return True, []
