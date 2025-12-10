"""Integration tests for test program generation workflow."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aidb_cli.generators.core.generator import Generator
from aidb_common.constants import SUPPORTED_LANGUAGES


class TestEndToEndGeneration:
    """Tests for complete generation workflow from YAML to executable files."""

    def test_generate_all_scenarios(self, tmp_path: Path):
        """Test generating all scenarios from basic.yaml."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Should have generated multiple scenarios
        assert len(results) > 0

        # Each result should have 3 languages
        for scenario_id, lang_results in results.items():
            assert len(lang_results) == 3
            assert "python" in lang_results
            assert "javascript" in lang_results
            assert "java" in lang_results

            # All language results should be successful
            for language, result in lang_results.items():
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

            # All files should exist
            scenario_dir = output_dir / scenario_id
            assert (scenario_dir / "test_program.py").exists()
            assert (scenario_dir / "test_program.js").exists()
            assert (scenario_dir / "TestProgram.java").exists()

        # Manifest should be created
        manifest_file = output_dir / "manifest.json"
        assert manifest_file.exists()

        # Validate manifest structure
        manifest = json.loads(manifest_file.read_text())
        assert "scenarios" in manifest
        assert len(manifest["scenarios"]) == len(results)

    def test_generate_specific_scenario(self, tmp_path: Path):
        """Test generating a specific scenario."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate only basic_variables scenario
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
            scenario_filter="basic_variables",
        )

        # Should have generated only one scenario
        assert len(results) == 1
        assert "basic_variables" in results

    def test_generate_specific_languages(self, tmp_path: Path):
        """Test generating only specific languages."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate only Python and JavaScript
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
            languages=["python", "javascript"],
        )

        # Each result should have only 2 languages
        for scenario_id, lang_results in results.items():
            assert len(lang_results) == 2
            assert "python" in lang_results
            assert "javascript" in lang_results
            assert "java" not in lang_results

            # Files should exist only for Python and JavaScript
            scenario_dir = output_dir / scenario_id
            assert (scenario_dir / "test_program.py").exists()
            assert (scenario_dir / "test_program.js").exists()
            assert not (scenario_dir / "TestProgram.java").exists()

    def test_generated_files_are_valid(self, tmp_path: Path):
        """Test that all generated files are syntactically valid (except syntax error
        scenarios)."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Validate each file (skip syntax error, infinite loop, and stack overflow scenarios)
        for scenario_id, lang_results in results.items():
            # Skip syntax error scenarios - they're supposed to be invalid
            if "syntax_error" in scenario_id:
                continue
            # Skip infinite loop scenarios - they don't terminate
            if "infinite_loop" in scenario_id:
                continue
            # Skip stack overflow scenarios - they crash with recursion errors
            if "stack_overflow" in scenario_id or "recursive" in scenario_id:
                continue

            scenario_dir = output_dir / scenario_id

            for language, result in lang_results.items():
                assert result.success, f"Generation failed for {scenario_id}/{language}"

                # Get file path based on language
                if language == "python":
                    file_path = scenario_dir / "test_program.py"
                    # Python syntax check
                    check_result = subprocess.run(
                        [sys.executable, "-m", "py_compile", str(file_path)],
                        capture_output=True,
                        text=True,
                    )
                    assert check_result.returncode == 0, (
                        f"Python syntax error in {scenario_id}: {check_result.stderr}"
                    )

                elif language == "javascript":
                    file_path = scenario_dir / "test_program.js"
                    # JavaScript syntax check
                    check_result = subprocess.run(
                        ["node", "--check", str(file_path)],
                        capture_output=True,
                        text=True,
                    )
                    assert check_result.returncode == 0, (
                        f"JavaScript syntax error in {scenario_id}: {check_result.stderr}"
                    )

                elif language == "java":
                    file_path = scenario_dir / "TestProgram.java"
                    # Java compilation check
                    check_result = subprocess.run(
                        ["javac", str(file_path)],
                        capture_output=True,
                        text=True,
                        cwd=str(scenario_dir),
                    )
                    assert check_result.returncode == 0, (
                        f"Java compilation error in {scenario_id}: {check_result.stderr}"
                    )

    def test_manifest_contains_correct_metadata(self, tmp_path: Path):
        """Test that manifest contains correct metadata for all scenarios."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Load manifest
        manifest_file = output_dir / "manifest.json"
        manifest = json.loads(manifest_file.read_text())

        # Validate each scenario entry
        for scenario_id in results:
            assert scenario_id in manifest["scenarios"]
            scenario_data = manifest["scenarios"][scenario_id]

            # Check required fields
            assert "id" in scenario_data
            assert "description" in scenario_data
            assert "category" in scenario_data
            assert "expected_markers" in scenario_data
            assert "files" in scenario_data

            # Check files metadata
            files = scenario_data["files"]
            assert "python" in files
            assert "javascript" in files
            assert "java" in files

            # Each file should have path and marker_count
            for _lang, file_info in files.items():
                assert "path" in file_info
                assert "marker_count" in file_info
                assert isinstance(file_info["marker_count"], int)


class TestCrossLanguageConsistency:
    """Tests for cross-language marker consistency."""

    def test_all_languages_have_same_markers(self, tmp_path: Path):
        """Test that all languages generate the same set of markers."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Check marker consistency for each scenario
        for scenario_id, lang_results in results.items():
            # Get markers from GenerationResult objects
            python_markers = set(lang_results["python"].markers.keys())
            js_markers = set(lang_results["javascript"].markers.keys())
            java_markers = set(lang_results["java"].markers.keys())

            # All languages should have the same markers
            assert python_markers == js_markers, (
                f"Marker mismatch in {scenario_id}: Python vs JS"
            )
            assert python_markers == java_markers, (
                f"Marker mismatch in {scenario_id}: Python vs Java"
            )

    def test_marker_names_match_yaml_definition(self, tmp_path: Path):
        """Test that generated markers exactly match YAML expected_markers."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Process all YAML files
        for yaml_file in scenarios_dir.glob("*.yaml"):
            # Parse scenarios to get expected markers
            scenarios = generator.parser.parse_file(yaml_file)

            # Generate code
            results = generator.generate_from_file(
                yaml_file=yaml_file,
                output_dir=output_dir,
            )

            # Check each scenario
            for scenario in scenarios:
                if scenario.id not in results:
                    continue

                expected_marker_names = set(scenario.expected_markers.keys())
                lang_results = results[scenario.id]

                # Check each language
                for language in SUPPORTED_LANGUAGES:
                    result = lang_results[language]
                    actual_marker_names = set(result.markers.keys())

                    # Find mismatches
                    missing_markers = expected_marker_names - actual_marker_names
                    extra_markers = actual_marker_names - expected_marker_names

                    # Build detailed error message
                    error_parts = []
                    if missing_markers:
                        error_parts.append(
                            f"  Missing markers: {sorted(missing_markers)}",
                        )
                    if extra_markers:
                        error_parts.append(f"  Extra markers: {sorted(extra_markers)}")

                    assert actual_marker_names == expected_marker_names, (
                        f"Marker name mismatch in {scenario.id}/{language}:\n"
                        f"  Expected: {sorted(expected_marker_names)}\n"
                        f"  Actual: {sorted(actual_marker_names)}\n"
                        + "\n".join(error_parts)
                    )

    def test_marker_count_matches_yaml_definition(self, tmp_path: Path):
        """Test that number of markers matches YAML expected_markers count."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Process all YAML files
        for yaml_file in scenarios_dir.glob("*.yaml"):
            # Parse scenarios to get expected markers
            scenarios = generator.parser.parse_file(yaml_file)

            # Generate code
            results = generator.generate_from_file(
                yaml_file=yaml_file,
                output_dir=output_dir,
            )

            # Check each scenario
            for scenario in scenarios:
                if scenario.id not in results:
                    continue

                expected_count = len(scenario.expected_markers)
                lang_results = results[scenario.id]

                # Check each language
                for language in SUPPORTED_LANGUAGES:
                    result = lang_results[language]
                    actual_count = len(result.markers)

                    assert actual_count == expected_count, (
                        f"Marker count mismatch in {scenario.id}/{language}:\n"
                        f"  Expected count: {expected_count}\n"
                        f"  Actual count: {actual_count}\n"
                        f"  Expected markers: {sorted(scenario.expected_markers.keys())}\n"
                        f"  Actual markers: {sorted(result.markers.keys())}"
                    )

    def test_marker_ordering_consistent(self, tmp_path: Path):
        """Test that markers appear in consistent order across languages."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Process all YAML files
        for yaml_file in scenarios_dir.glob("*.yaml"):
            # Generate code
            results = generator.generate_from_file(
                yaml_file=yaml_file,
                output_dir=output_dir,
            )

            # Check each scenario
            for scenario_id, lang_results in results.items():
                # Get markers sorted by line number for each language
                python_result = lang_results["python"]
                js_result = lang_results["javascript"]
                java_result = lang_results["java"]

                # Sort markers by line number and extract names
                python_order = [
                    name
                    for name, _line in sorted(
                        python_result.markers.items(),
                        key=lambda x: x[1],
                    )
                ]
                js_order = [
                    name
                    for name, _line in sorted(
                        js_result.markers.items(),
                        key=lambda x: x[1],
                    )
                ]
                java_order = [
                    name
                    for name, _line in sorted(
                        java_result.markers.items(),
                        key=lambda x: x[1],
                    )
                ]

                # For syntax error scenarios, ordering may be inconsistent
                # (intentionally malformed code). Assert that inconsistency exists.
                if "syntax_error" in scenario_id:
                    # Syntax errors should have marker ordering inconsistencies
                    has_inconsistency = (
                        python_order != js_order or python_order != java_order
                    )
                    assert has_inconsistency, (
                        f"Syntax error scenario {scenario_id} should have "
                        f"marker ordering inconsistencies, but all languages match:\n"
                        f"  Python order: {python_order}\n"
                        f"  JS order: {js_order}\n"
                        f"  Java order: {java_order}"
                    )
                else:
                    # Normal scenarios: all languages should have same marker ordering
                    assert python_order == js_order, (
                        f"Marker ordering mismatch in {scenario_id}: Python vs JS\n"
                        f"  Python order: {python_order}\n"
                        f"  JS order: {js_order}"
                    )
                    assert python_order == java_order, (
                        f"Marker ordering mismatch in {scenario_id}: Python vs Java\n"
                        f"  Python order: {python_order}\n"
                        f"  Java order: {java_order}"
                    )

    def test_marker_counts_match_manifest(self, tmp_path: Path):
        """Test that marker counts in manifest match actual counts."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Load manifest
        manifest_file = output_dir / "manifest.json"
        manifest = json.loads(manifest_file.read_text())

        # Check marker counts for each scenario
        for scenario_id, lang_results in results.items():
            scenario_data = manifest["scenarios"][scenario_id]

            # Check each language
            for language, result in lang_results.items():
                # Get marker count from GenerationResult
                actual_count = len(result.markers)

                # Check against manifest
                manifest_count = scenario_data["files"][language]["marker_count"]
                assert actual_count == manifest_count, (
                    f"Marker count mismatch in {scenario_id}/{language}: {actual_count} != {manifest_count}"
                )


class TestDeterminism:
    """Tests for generation determinism."""

    def test_multiple_runs_produce_identical_output(self, tmp_path: Path):
        """Test that running generation multiple times produces identical output."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")

        # Generate 5 times
        outputs = []
        for i in range(5):
            output_dir = tmp_path / f"run_{i}"
            results = generator.generate_from_file(
                yaml_file=yaml_file,
                output_dir=output_dir,
            )
            outputs.append(results)

        # All runs should produce the same scenario IDs
        scenario_ids = [set(output.keys()) for output in outputs]
        assert all(ids == scenario_ids[0] for ids in scenario_ids)

        # Compare code contents across runs
        for scenario_id in outputs[0]:
            # Get language results from first run
            lang_results_run0 = outputs[0][scenario_id]

            for i in range(1, 5):
                lang_results_run_i = outputs[i][scenario_id]

                # Compare each language
                for language in lang_results_run0:
                    code0 = lang_results_run0[language].code
                    code_i = lang_results_run_i[language].code

                    assert code0 == code_i, (
                        f"Code differs for {scenario_id}/{language} between run 0 and run {i}"
                    )

    def test_manifest_is_deterministic(self, tmp_path: Path):
        """Test that manifest generation is deterministic."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")

        # Generate twice
        output_dir1 = tmp_path / "run1"
        output_dir2 = tmp_path / "run2"

        generator.generate_from_file(yaml_file=yaml_file, output_dir=output_dir1)
        generator.generate_from_file(yaml_file=yaml_file, output_dir=output_dir2)

        # Load both manifests
        manifest1 = json.loads((output_dir1 / "manifest.json").read_text())
        manifest2 = json.loads((output_dir2 / "manifest.json").read_text())

        # Manifests should be identical (except for absolute paths)
        # Compare structure and metadata
        assert set(manifest1["scenarios"].keys()) == set(manifest2["scenarios"].keys())

        for scenario_id in manifest1["scenarios"]:
            s1 = manifest1["scenarios"][scenario_id]
            s2 = manifest2["scenarios"][scenario_id]

            # Compare metadata fields
            assert s1["id"] == s2["id"]
            assert s1["description"] == s2["description"]
            assert s1["category"] == s2["category"]
            assert s1["expected_markers"] == s2["expected_markers"]

            # Compare marker counts
            for lang in SUPPORTED_LANGUAGES:
                assert (
                    s1["files"][lang]["marker_count"]
                    == s2["files"][lang]["marker_count"]
                )
