"""Main generator engine for test program generation."""

from pathlib import Path

from aidb_cli.generators.core.marker import MarkerSystem
from aidb_cli.generators.core.parser import ScenarioParser
from aidb_cli.generators.core.types import GenerationResult, Scenario
from aidb_cli.generators.plugins.base import LanguageGenerator
from aidb_common.constants import Language
from aidb_common.io import safe_write_json


class Generator:
    """Main test program generator."""

    def __init__(self):
        """Initialize the generator."""
        self.parser = ScenarioParser()
        self.marker_system = MarkerSystem()
        self.language_generators: dict[str, LanguageGenerator] = {}
        self._register_generators()

    def _register_generators(self):
        """Register all available language generators."""
        # Import and register generators
        try:
            from aidb_cli.generators.plugins.python_generator import PythonGenerator

            self.register_generator(PythonGenerator())
        except ImportError:
            pass

        try:
            from aidb_cli.generators.plugins.javascript_generator import (
                JavaScriptGenerator,
            )

            self.register_generator(JavaScriptGenerator())
        except ImportError:
            pass

        try:
            from aidb_cli.generators.plugins.java_generator import JavaGenerator

            self.register_generator(JavaGenerator())
        except ImportError:
            pass

    def register_generator(self, generator: LanguageGenerator):
        """Register a language generator.

        Args
        ----
            generator: Language generator instance
        """
        self.language_generators[generator.language_name] = generator

    def get_generator(self, language: str) -> LanguageGenerator | None:
        """Get generator for a specific language.

        Args
        ----
            language: Language name

        Returns
        -------
            Language generator or None
        """
        return self.language_generators.get(language)

    def get_supported_languages(self) -> list[str]:
        """Get list of supported languages.

        Returns
        -------
            List of language names
        """
        return list(self.language_generators.keys())

    def generate_scenario(
        self,
        scenario: Scenario,
        languages: list[str] | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, GenerationResult]:
        """Generate test programs for a scenario.

        Args
        ----
            scenario: Scenario to generate
            languages: Languages to generate for (None = all)
            output_dir: Output directory (None = don't write files)

        Returns
        -------
            Dictionary mapping language to generation result
        """
        if languages is None:
            languages = self.get_supported_languages()

        results = {}

        for language in languages:
            generator = self.get_generator(language)
            if not generator:
                results[language] = GenerationResult(
                    scenario_id=scenario.id,
                    language=language,
                    code="",
                    markers={},
                    success=False,
                    error=f"No generator for language: {language}",
                )
                continue

            try:
                # Generate code
                code = generator.generate_program(scenario)

                # Extract markers
                markers = self.marker_system.extract_markers(code, language)

                # Validate syntax (unless it's a syntax error scenario)
                should_validate = "syntax_error" not in scenario.id.lower()
                if should_validate:
                    validation = generator.validate_syntax(code)
                    if not validation.is_valid:
                        results[language] = GenerationResult(
                            scenario_id=scenario.id,
                            language=language,
                            code=code,
                            markers=markers,
                            success=False,
                            error=f"Syntax validation failed: {validation.errors}",
                        )
                        continue

                # Write file if output_dir specified
                if output_dir:
                    self._write_file(scenario, language, code, output_dir)

                results[language] = GenerationResult(
                    scenario_id=scenario.id,
                    language=language,
                    code=code,
                    markers=markers,
                    success=True,
                )

            # Collect errors rather than failing entire generation
            except Exception as e:
                results[language] = GenerationResult(
                    scenario_id=scenario.id,
                    language=language,
                    code="",
                    markers={},
                    success=False,
                    error=str(e),
                )

        return results

    def generate_from_file(
        self,
        yaml_file: Path,
        scenario_filter: str | None = None,
        languages: list[str] | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, dict[str, GenerationResult]]:
        """Generate test programs from a YAML file.

        Args
        ----
            yaml_file: Path to YAML file
            scenario_filter: Optional scenario ID to generate (None = all)
            languages: Languages to generate for (None = all)
            output_dir: Output directory (None = don't write files)

        Returns
        -------
            Nested dict: scenario_id -> language -> GenerationResult
        """
        scenarios = self.parser.parse_file(yaml_file)

        if scenario_filter:
            scenarios = [s for s in scenarios if s.id == scenario_filter]

        all_results = {}
        scenarios_map = {}

        for scenario in scenarios:
            results = self.generate_scenario(scenario, languages, output_dir)
            all_results[scenario.id] = results
            scenarios_map[scenario.id] = scenario

        # Write manifest if output_dir specified
        if output_dir:
            self._write_manifest(all_results, scenarios_map, output_dir)

        return all_results

    def validate_cross_language_consistency(
        self,
        results: dict[str, GenerationResult],
    ) -> tuple[bool, list[str]]:
        """Validate that all languages have consistent markers.

        Args
        ----
            results: Generation results for different languages

        Returns
        -------
            Tuple of (is_valid, error_messages)
        """
        code_files = {
            lang: result.code for lang, result in results.items() if result.success
        }

        return self.marker_system.validate_markers(code_files)

    def _write_file(
        self,
        scenario: Scenario,
        language: str,
        code: str,
        output_dir: Path,
    ) -> Path:
        """Write generated code to file.

        Args
        ----
            scenario: Scenario being generated
            language: Target language
            code: Generated code
            output_dir: Output directory

        Returns
        -------
            Path to written file
        """
        generator = self.get_generator(language)
        if not generator:
            msg = f"No generator for language: {language}"
            raise ValueError(msg)

        # Create scenario directory
        scenario_dir = output_dir / scenario.id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename
        if language == Language.JAVA.value:
            # Java needs specific class names
            filename = "TestProgram" + generator.file_extension
        else:
            filename = "test_program" + generator.file_extension

        file_path = scenario_dir / filename

        # Write file
        file_path.write_text(code)

        return file_path

    def _write_manifest(  # noqa: C901
        self,
        all_results: dict[str, dict[str, GenerationResult]],
        scenarios_map: dict[str, Scenario],
        output_dir: Path,
    ):
        """Write generation manifest with intelligent merging.

        Merges newly generated scenarios into existing manifest, preserving
        scenarios that weren't regenerated. This allows partial regeneration
        without losing other scenarios.

        Args
        ----
            all_results: All generation results
            scenarios_map: Map of scenario_id to Scenario objects
            output_dir: Output directory
        """
        import json
        from typing import Any

        manifest_path = output_dir / "manifest.json"

        # Read existing manifest if it exists (merge strategy)
        if manifest_path.exists():
            try:
                from aidb_cli.core.utils import CliOutput

                existing_manifest = json.loads(manifest_path.read_text())
                manifest: dict[str, Any] = {
                    "generator_version": "1.0.0",
                    "scenarios": existing_manifest.get("scenarios", {}).copy(),
                }
                preserved_count = len(manifest["scenarios"]) - len(all_results)
                if preserved_count > 0:
                    CliOutput.info(
                        f"Merging {len(all_results)} generated scenario(s) "
                        f"with {preserved_count} existing scenario(s)",
                    )
            except (json.JSONDecodeError, KeyError) as e:
                from aidb_cli.core.utils import CliOutput

                CliOutput.warning(
                    f"Could not read existing manifest ({e}), creating new",
                )
                manifest = {
                    "generator_version": "1.0.0",
                    "scenarios": {},
                }
        else:
            manifest = {
                "generator_version": "1.0.0",
                "scenarios": {},
            }

        for scenario_id, results in all_results.items():
            scenario = scenarios_map[scenario_id]

            # Get category value
            category_value = (
                scenario.category.value
                if hasattr(scenario.category, "value")
                else str(scenario.category)
            )

            # Extract markers per language (line numbers are language-specific)
            # Each language has different file structure causing line variations
            extracted_markers = {}
            for lang, result in results.items():
                if result.success:
                    extracted_markers[lang] = result.markers

            scenario_info = {
                "id": scenario.id,
                "name": scenario.name,
                "description": scenario.description,
                "category": category_value,
                "expected_markers": extracted_markers,
                "files": {},
            }

            for language, result in results.items():
                if result.success:
                    generator = self.get_generator(language)
                    if not generator:
                        continue

                    if language == Language.JAVA.value:
                        filename = f"TestProgram{generator.file_extension}"
                    else:
                        filename = f"test_program{generator.file_extension}"

                    file_path = str(output_dir / scenario_id / filename)

                    scenario_info["files"][language] = {
                        "path": file_path,
                        "marker_count": len(result.markers),
                    }

            manifest["scenarios"][scenario_id] = scenario_info

        manifest_path = output_dir / "manifest.json"
        safe_write_json(manifest_path, manifest)
