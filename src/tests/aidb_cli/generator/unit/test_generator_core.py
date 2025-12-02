"""Tests for core generator engine."""

import json
from pathlib import Path

import pytest
import yaml

from aidb_cli.core.yaml import YamlOperationError
from aidb_cli.generators.core.generator import Generator
from aidb_cli.generators.core.types import Scenario
from aidb_cli.generators.plugins.python_generator import PythonGenerator


class TestGeneratorInitialization:
    """Tests for generator initialization."""

    def test_generator_initialization(self, generator: Generator):
        """Test that generator initializes correctly."""
        assert generator is not None
        assert generator.parser is not None
        assert generator.marker_system is not None
        assert isinstance(generator.language_generators, dict)

    def test_default_generators_registered(self, generator: Generator):
        """Test that default language generators are registered."""
        supported = generator.get_supported_languages()

        # Should have at least Python, JavaScript, Java
        assert "python" in supported
        assert "javascript" in supported
        assert "java" in supported

    def test_register_custom_generator(self, generator: Generator):
        """Test registering a custom generator."""
        initial_count = len(generator.get_supported_languages())

        # Register a new instance (shouldn't add duplicate)
        python_gen = PythonGenerator()
        generator.register_generator(python_gen)

        # Should replace existing, not add new
        assert len(generator.get_supported_languages()) == initial_count

    def test_get_generator(self, generator: Generator):
        """Test retrieving a specific generator."""
        python_gen = generator.get_generator("python")

        assert python_gen is not None
        assert python_gen.language_name == "python"

    def test_get_nonexistent_generator(self, generator: Generator):
        """Test retrieving a nonexistent generator."""
        result = generator.get_generator("nonexistent")
        assert result is None


class TestScenarioGeneration:
    """Tests for scenario generation."""

    def test_generate_simple_scenario(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test generating a simple scenario."""
        results = generator.generate_scenario(simple_scenario)

        # Should generate for all languages
        assert len(results) == 3
        assert "python" in results
        assert "javascript" in results
        assert "java" in results

        # All should succeed
        for lang, result in results.items():
            assert result.success, f"{lang} generation failed: {result.error}"
            assert result.code != ""
            assert result.scenario_id == simple_scenario.id

    def test_generate_specific_languages(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test generating for specific languages only."""
        results = generator.generate_scenario(
            simple_scenario,
            languages=["python", "javascript"],
        )

        assert len(results) == 2
        assert "python" in results
        assert "javascript" in results
        assert "java" not in results

    def test_generate_with_invalid_language(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test generation with invalid language."""
        results = generator.generate_scenario(
            simple_scenario,
            languages=["invalid_lang"],
        )

        assert len(results) == 1
        assert "invalid_lang" in results
        assert not results["invalid_lang"].success
        assert "No generator" in results["invalid_lang"].error

    def test_generated_code_has_markers(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test that generated code contains markers."""
        results = generator.generate_scenario(simple_scenario)

        for lang, result in results.items():
            if result.success:
                assert len(result.markers) > 0, f"{lang} has no markers"

                # Check expected markers are present
                for marker_name in simple_scenario.expected_markers:
                    assert marker_name in result.markers, (
                        f"Missing marker {marker_name} in {lang}"
                    )

    def test_syntax_validation(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test that generated code passes syntax validation."""
        results = generator.generate_scenario(simple_scenario)

        # All results should succeed with valid syntax
        for lang, result in results.items():
            assert result.success, f"{lang} failed validation: {result.error}"


class TestFileWriting:
    """Tests for file writing functionality."""

    def test_generate_and_write_files(
        self,
        generator: Generator,
        simple_scenario: Scenario,
        temp_output_dir: Path,
    ):
        """Test generating and writing files."""
        generator.generate_scenario(
            simple_scenario,
            output_dir=temp_output_dir,
        )

        # Check files were created
        scenario_dir = temp_output_dir / simple_scenario.id
        assert scenario_dir.exists()

        # Check language-specific files
        assert (scenario_dir / "test_program.py").exists()
        assert (scenario_dir / "test_program.js").exists()
        assert (scenario_dir / "TestProgram.java").exists()

    def test_file_content_matches_generated_code(
        self,
        generator: Generator,
        simple_scenario: Scenario,
        temp_output_dir: Path,
    ):
        """Test that written files contain correct code."""
        results = generator.generate_scenario(
            simple_scenario,
            output_dir=temp_output_dir,
        )

        scenario_dir = temp_output_dir / simple_scenario.id

        # Check Python file
        python_file = scenario_dir / "test_program.py"
        python_code = python_file.read_text()
        assert python_code == results["python"].code

        # Check JavaScript file
        js_file = scenario_dir / "test_program.js"
        js_code = js_file.read_text()
        assert js_code == results["javascript"].code


class TestManifestGeneration:
    """Tests for manifest generation."""

    def test_generate_from_file_creates_manifest(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that generating from file creates manifest."""
        # Write test YAML
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        # Generate
        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
        )

        # Check manifest exists
        manifest_file = temp_output_dir / "manifest.json"
        assert manifest_file.exists()

        # Check manifest structure
        manifest = json.loads(manifest_file.read_text())
        assert "generator_version" in manifest
        assert "scenarios" in manifest

    def test_manifest_contains_marker_info(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that manifest contains marker information."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
        )

        manifest = json.loads((temp_output_dir / "manifest.json").read_text())
        scenarios = manifest["scenarios"]

        # Should have scenario data
        assert len(scenarios) > 0

        # Check first scenario
        first_scenario = list(scenarios.values())[0]
        assert "files" in first_scenario
        assert "id" in first_scenario
        assert "name" in first_scenario
        assert "description" in first_scenario
        assert "category" in first_scenario
        assert "expected_markers" in first_scenario

        # Check file data
        for file_data in first_scenario["files"].values():
            assert "path" in file_data
            assert "marker_count" in file_data


class TestManifestMerging:
    """Tests for manifest merge functionality."""

    def test_manifest_merge_with_existing_scenarios(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that manifest merges with existing scenarios instead of overwriting."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        # Generate all scenarios first
        generator.generate_from_file(yaml_file, output_dir=temp_output_dir)

        manifest_file = temp_output_dir / "manifest.json"
        original_manifest = json.loads(manifest_file.read_text())
        original_scenario_count = len(original_manifest["scenarios"])

        # Now generate only the first scenario with filter
        first_scenario_id = list(original_manifest["scenarios"].keys())[0]
        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
            scenario_filter=first_scenario_id,
        )

        # Read updated manifest
        updated_manifest = json.loads(manifest_file.read_text())

        # Should still have all scenarios
        assert len(updated_manifest["scenarios"]) == original_scenario_count
        # All original scenario IDs should still be present
        for scenario_id in original_manifest["scenarios"]:
            assert scenario_id in updated_manifest["scenarios"]

    def test_manifest_merge_updates_filtered_scenario(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that filtered scenario gets updated during merge."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        # Generate all scenarios
        generator.generate_from_file(yaml_file, output_dir=temp_output_dir)

        manifest_file = temp_output_dir / "manifest.json"
        original_manifest = json.loads(manifest_file.read_text())
        first_scenario_id = list(original_manifest["scenarios"].keys())[0]

        # Regenerate only first scenario
        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
            scenario_filter=first_scenario_id,
        )

        updated_manifest = json.loads(manifest_file.read_text())

        # The filtered scenario should be present and valid
        assert first_scenario_id in updated_manifest["scenarios"]
        assert "files" in updated_manifest["scenarios"][first_scenario_id]
        assert "expected_markers" in updated_manifest["scenarios"][first_scenario_id]

    def test_manifest_merge_with_language_subset(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test manifest merge when regenerating with language subset."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        # Generate all scenarios, all languages
        generator.generate_from_file(yaml_file, output_dir=temp_output_dir)

        manifest_file = temp_output_dir / "manifest.json"
        original_manifest = json.loads(manifest_file.read_text())
        first_scenario_id = list(original_manifest["scenarios"].keys())[0]

        # Regenerate first scenario with only Python
        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
            scenario_filter=first_scenario_id,
            languages=["python"],
        )

        updated_manifest = json.loads(manifest_file.read_text())

        # All scenarios should still exist
        assert len(updated_manifest["scenarios"]) == len(
            original_manifest["scenarios"],
        )
        # First scenario should have Python marker data
        assert (
            "python"
            in updated_manifest["scenarios"][first_scenario_id]["expected_markers"]
        )

    def test_first_generation_creates_manifest(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that first generation creates manifest without merge logic."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        manifest_file = temp_output_dir / "manifest.json"

        # Ensure no manifest exists
        assert not manifest_file.exists()

        # Generate scenarios
        generator.generate_from_file(yaml_file, output_dir=temp_output_dir)

        # Manifest should now exist
        assert manifest_file.exists()

        manifest = json.loads(manifest_file.read_text())
        assert "generator_version" in manifest
        assert "scenarios" in manifest
        assert len(manifest["scenarios"]) > 0

    def test_manifest_merge_handles_corrupted_manifest(
        self,
        generator: Generator,
        temp_output_dir: Path,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test that corrupted manifest is handled gracefully."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        manifest_file = temp_output_dir / "manifest.json"

        # Create a corrupted manifest
        manifest_file.write_text("{invalid json content")

        # Generate should handle this gracefully and create new manifest
        generator.generate_from_file(yaml_file, output_dir=temp_output_dir)

        # Should have created valid manifest
        assert manifest_file.exists()
        manifest = json.loads(manifest_file.read_text())
        assert "scenarios" in manifest
        assert len(manifest["scenarios"]) > 0

    def test_manifest_merge_preserves_ungenerated_scenarios(
        self,
        generator: Generator,
        temp_output_dir: Path,
        tmp_path: Path,
    ):
        """Test that scenarios not in current generation are preserved."""
        from typing import Any

        # Create a manifest with multiple scenarios
        manifest_file = temp_output_dir / "manifest.json"
        existing_manifest: dict[str, Any] = {
            "generator_version": "1.0.0",
            "scenarios": {
                "scenario_a": {
                    "id": "scenario_a",
                    "name": "Scenario A",
                    "description": "Test A",
                    "category": "test",
                    "expected_markers": {"python": {"marker.a": 1}},
                    "files": {"python": {"path": "test.py", "marker_count": 1}},
                },
                "scenario_b": {
                    "id": "scenario_b",
                    "name": "Scenario B",
                    "description": "Test B",
                    "category": "test",
                    "expected_markers": {"python": {"marker.b": 1}},
                    "files": {"python": {"path": "test.py", "marker_count": 1}},
                },
            },
        }
        manifest_file.write_text(json.dumps(existing_manifest))

        # Create YAML with only scenario_a
        yaml_content = """
scenarios:
  - id: scenario_a
    name: Scenario A
    description: Test A
    category: test
    constructs:
      - type: variable
        name: x
        initial_value: 10
        marker: var.init.x
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        # Generate only scenario_a
        generator.generate_from_file(
            yaml_file,
            output_dir=temp_output_dir,
            scenario_filter="scenario_a",
        )

        # Read manifest
        updated_manifest = json.loads(manifest_file.read_text())

        # Both scenarios should still be present
        assert "scenario_a" in updated_manifest["scenarios"]
        assert "scenario_b" in updated_manifest["scenarios"]
        # scenario_b should be unchanged
        assert (
            updated_manifest["scenarios"]["scenario_b"]
            == existing_manifest["scenarios"]["scenario_b"]
        )


class TestCrossLanguageValidation:
    """Tests for cross-language consistency validation."""

    def test_validate_consistent_markers(
        self,
        generator: Generator,
        simple_scenario: Scenario,
    ):
        """Test validation passes for consistent markers."""
        results = generator.generate_scenario(simple_scenario)

        is_valid, errors = generator.validate_cross_language_consistency(results)

        assert is_valid, f"Validation failed: {errors}"
        assert len(errors) == 0

    def test_validate_detects_inconsistency(self, generator: Generator):
        """Test validation detects marker inconsistencies."""
        # Create mock results with inconsistent markers
        from aidb_cli.generators.core.types import GenerationResult

        results = {
            "python": GenerationResult(
                scenario_id="test",
                language="python",
                code="x = 10  #:var.init.x:\ny = 20  #:var.init.y:",
                markers={"var.init.x": 1, "var.init.y": 2},
                success=True,
            ),
            "javascript": GenerationResult(
                scenario_id="test",
                language="javascript",
                code="let x = 10;  //:var.init.x:",
                markers={"var.init.x": 1},  # Missing var.init.y
                success=True,
            ),
        }

        is_valid, errors = generator.validate_cross_language_consistency(results)

        assert not is_valid
        assert len(errors) > 0


class TestGenerateFromFile:
    """Tests for generating from YAML files."""

    def test_generate_from_file(
        self,
        generator: Generator,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test generating from a YAML file."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        results = generator.generate_from_file(yaml_file)

        assert len(results) > 0

        # Check structure: scenario_id -> language -> result
        for _scenario_id, lang_results in results.items():
            assert isinstance(lang_results, dict)
            assert "python" in lang_results
            assert "javascript" in lang_results
            assert "java" in lang_results

    def test_generate_with_scenario_filter(
        self,
        generator: Generator,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test filtering scenarios by ID."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        results = generator.generate_from_file(
            yaml_file,
            scenario_filter="test_scenario",
        )

        assert len(results) == 1
        assert "test_scenario" in results

    def test_generate_with_language_filter(
        self,
        generator: Generator,
        valid_scenario_yaml: str,
        tmp_path: Path,
    ):
        """Test filtering by languages."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(valid_scenario_yaml)

        results = generator.generate_from_file(
            yaml_file,
            languages=["python"],
        )

        # Check that only Python was generated
        for _scenario_id, lang_results in results.items():
            assert len(lang_results) == 1
            assert "python" in lang_results
            assert "javascript" not in lang_results


class TestErrorHandling:
    """Tests for error handling."""

    def test_handle_invalid_yaml_file(self, generator: Generator, tmp_path: Path):
        """Test handling of invalid YAML file."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("invalid: yaml: content: [")

        with pytest.raises((YamlOperationError, Exception)):
            generator.generate_from_file(yaml_file)

    def test_handle_nonexistent_file(self, generator: Generator):
        """Test handling of nonexistent file."""
        fake_path = Path("/nonexistent/file.yaml")

        with pytest.raises(YamlOperationError):
            generator.generate_from_file(fake_path)
