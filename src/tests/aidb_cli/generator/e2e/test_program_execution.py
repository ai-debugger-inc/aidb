"""End-to-end tests for test program execution."""

import subprocess
import sys
from pathlib import Path

import pytest

from aidb_cli.generators.core.generator import Generator
from aidb_common.constants import SUPPORTED_LANGUAGES


class TestRuntimeExecution:
    """Tests for runtime execution of generated programs."""

    def test_python_programs_execute_successfully(self, tmp_path: Path):
        """Test that generated Python programs run without errors."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Run each Python program
        for scenario_id, _lang_results in results.items():
            python_file = output_dir / scenario_id / "test_program.py"

            result = subprocess.run(
                [sys.executable, str(python_file)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            assert result.returncode == 0, (
                f"Python execution failed for {scenario_id}: {result.stderr}"
            )

    def test_javascript_programs_execute_successfully(self, tmp_path: Path):
        """Test that generated JavaScript programs run without errors."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Run each JavaScript program
        for scenario_id, _lang_results in results.items():
            js_file = output_dir / scenario_id / "test_program.js"

            result = subprocess.run(
                ["node", str(js_file)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            assert result.returncode == 0, (
                f"JavaScript execution failed for {scenario_id}: {result.stderr}"
            )

    def test_java_programs_execute_successfully(self, tmp_path: Path):
        """Test that generated Java programs run without errors."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/basic.yaml")
        output_dir = tmp_path / "generated"

        # Generate all scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Compile and run each Java program
        for scenario_id, _lang_results in results.items():
            java_file = output_dir / scenario_id / "TestProgram.java"

            # Compile
            compile_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(java_file.parent),
            )
            assert compile_result.returncode == 0, (
                f"Java compilation failed for {scenario_id}: {compile_result.stderr}"
            )

            # Run
            run_result = subprocess.run(
                ["java", "TestProgram"],
                capture_output=True,
                text=True,
                cwd=str(java_file.parent),
                timeout=5,
            )

            assert run_result.returncode == 0, (
                f"Java execution failed for {scenario_id}: {run_result.stderr}"
            )


class TestIntermediateScenarios:
    """Tests specific to intermediate complexity scenarios."""

    def test_generate_intermediate_scenarios(self, tmp_path: Path):
        """Test generating all intermediate scenarios."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/intermediate.yaml")
        output_dir = tmp_path / "generated"

        # Generate all intermediate scenarios
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Should have 5 intermediate scenarios
        assert len(results) == 5
        assert "array_operations" in results
        assert "nested_loops" in results
        assert "function_chain" in results
        assert "nested_conditionals" in results
        assert "complex_expressions" in results

        # All should generate successfully
        for scenario_id, lang_results in results.items():
            for language, result in lang_results.items():
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

    def test_array_operations_execution(self, tmp_path: Path):
        """Test that array_operations scenario executes correctly."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/intermediate.yaml")
        output_dir = tmp_path / "generated"

        # Generate array_operations scenario
        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
            scenario_filter="array_operations",
        )

        assert "array_operations" in results
        scenario_dir = output_dir / "array_operations"

        # Test Python execution
        py_result = subprocess.run(
            [sys.executable, str(scenario_dir / "test_program.py")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert py_result.returncode == 0
        assert "Element: 10" in py_result.stdout
        assert "Element: 50" in py_result.stdout

        # Test JavaScript execution
        js_result = subprocess.run(
            ["node", str(scenario_dir / "test_program.js")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert js_result.returncode == 0
        assert "Element: 10" in js_result.stdout

        # Test Java execution
        java_file = scenario_dir / "TestProgram.java"
        subprocess.run(
            ["javac", str(java_file)],
            capture_output=True,
            cwd=str(scenario_dir),
        )
        java_result = subprocess.run(
            ["java", "TestProgram"],
            capture_output=True,
            text=True,
            cwd=str(scenario_dir),
            timeout=5,
        )
        assert java_result.returncode == 0
        assert "Element: 10" in java_result.stdout

    def test_nested_loops_execution(self, tmp_path: Path):
        """Test that nested_loops scenario executes correctly."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/intermediate.yaml")
        output_dir = tmp_path / "generated"

        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
            scenario_filter="nested_loops",
        )

        assert "nested_loops" in results
        scenario_dir = output_dir / "nested_loops"

        # Test Python execution
        py_result = subprocess.run(
            [sys.executable, str(scenario_dir / "test_program.py")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert py_result.returncode == 0
        # Should have 3x3=9 iterations
        assert "Final total: 9" in py_result.stdout

    def test_function_chain_execution(self, tmp_path: Path):
        """Test that function_chain scenario executes correctly."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/intermediate.yaml")
        output_dir = tmp_path / "generated"

        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
            scenario_filter="function_chain",
        )

        assert "function_chain" in results
        scenario_dir = output_dir / "function_chain"

        # Test Python execution
        py_result = subprocess.run(
            [sys.executable, str(scenario_dir / "test_program.py")],
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert py_result.returncode == 0
        # (10 + 20) * 3 = 90
        assert "Result: 90" in py_result.stdout

    def test_intermediate_marker_consistency(self, tmp_path: Path):
        """Test marker consistency for intermediate scenarios."""
        generator = Generator()
        yaml_file = Path("src/aidb_cli/generators/scenarios/intermediate.yaml")
        output_dir = tmp_path / "generated"

        results = generator.generate_from_file(
            yaml_file=yaml_file,
            output_dir=output_dir,
        )

        # Check marker consistency for each intermediate scenario
        for scenario_id, lang_results in results.items():
            python_markers = set(lang_results["python"].markers.keys())
            js_markers = set(lang_results["javascript"].markers.keys())
            java_markers = set(lang_results["java"].markers.keys())

            assert python_markers == js_markers, (
                f"Marker mismatch in {scenario_id}: Python vs JS"
            )
            assert python_markers == java_markers, (
                f"Marker mismatch in {scenario_id}: Python vs Java"
            )


class TestAllScenarios:
    """Tests for all scenarios (basic + intermediate)."""

    def test_all_scenarios_execute_successfully(self, tmp_path: Path):
        """Test that all 11 scenarios generate and execute successfully."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        all_results = {}

        # Generate from each YAML file
        for yaml_file in scenarios_dir.glob("*.yaml"):
            results = generator.generate_from_file(
                yaml_file=yaml_file,
                output_dir=output_dir,
            )
            all_results.update(results)

        # Should have 15 total scenarios (6 basic + 5 intermediate + 4 critical)
        assert len(all_results) == 15

        # Verify all scenarios generated successfully
        for scenario_id, lang_results in all_results.items():
            for language, result in lang_results.items():
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

        # Test execution for all scenarios (skip error scenarios)
        for scenario_id in all_results:
            # Skip syntax error scenarios - they're supposed to fail
            if "syntax_error" in scenario_id:
                continue
            # Skip infinite loop scenarios - they don't terminate
            if "infinite_loop" in scenario_id:
                continue
            # Skip stack overflow scenarios - they crash with recursion errors
            if "stack_overflow" in scenario_id or "recursive" in scenario_id:
                continue

            scenario_dir = output_dir / scenario_id

            # Python
            py_result = subprocess.run(
                [sys.executable, str(scenario_dir / "test_program.py")],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert py_result.returncode == 0, (
                f"Python execution failed for {scenario_id}: {py_result.stderr}"
            )

            # JavaScript
            js_result = subprocess.run(
                ["node", str(scenario_dir / "test_program.js")],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert js_result.returncode == 0, (
                f"JavaScript execution failed for {scenario_id}: {js_result.stderr}"
            )

            # Java
            java_file = scenario_dir / "TestProgram.java"
            compile_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert compile_result.returncode == 0, (
                f"Java compilation failed for {scenario_id}: {compile_result.stderr}"
            )

            run_result = subprocess.run(
                ["java", "TestProgram"],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
                timeout=5,
            )
            assert run_result.returncode == 0, (
                f"Java execution failed for {scenario_id}: {run_result.stderr}"
            )


class TestSyntaxErrorScenarios:
    """Tests for syntax error scenarios - verify they fail as expected."""

    def test_syntax_error_programs_fail_compilation(self, tmp_path: Path):
        """Test that syntax error programs fail compilation/parsing as expected."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate syntax error scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only syntax error scenarios
        syntax_error_scenarios = {
            sid: res for sid, res in results.items() if "syntax_error" in sid
        }

        assert len(syntax_error_scenarios) > 0, "No syntax error scenarios found"

        for scenario_id, _lang_results in syntax_error_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Python should fail parsing
            py_file = scenario_dir / "test_program.py"
            py_result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(py_file)],
                capture_output=True,
                text=True,
            )
            assert py_result.returncode != 0, (
                f"Python syntax error {scenario_id} should fail parsing but succeeded"
            )
            assert "SyntaxError" in py_result.stderr, (
                f"Expected SyntaxError in {scenario_id}, got: {py_result.stderr}"
            )

            # JavaScript should fail parsing
            js_file = scenario_dir / "test_program.js"
            js_result = subprocess.run(
                ["node", "--check", str(js_file)],
                capture_output=True,
                text=True,
            )
            assert js_result.returncode != 0, (
                f"JavaScript syntax error {scenario_id} should fail parsing but succeeded"
            )

            # Java should fail compilation
            java_file = scenario_dir / "TestProgram.java"
            java_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert java_result.returncode != 0, (
                f"Java syntax error {scenario_id} should fail compilation but succeeded"
            )

    def test_syntax_error_markers_present(self, tmp_path: Path):
        """Test that syntax error programs still have markers at error locations."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate syntax error scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only syntax error scenarios
        syntax_error_scenarios = {
            sid: res for sid, res in results.items() if "syntax_error" in sid
        }

        for scenario_id, lang_results in syntax_error_scenarios.items():
            # Verify each language has the error marker
            for language, result in lang_results.items():
                assert result.success, (
                    f"Generation should succeed for {scenario_id}/{language}"
                )

                # Should have marker indicating the syntax error location
                error_markers = [m for m in result.markers if "error" in m]
                assert len(error_markers) > 0, (
                    f"Expected error marker in {scenario_id}/{language}, found markers: {list(result.markers.keys())}"
                )

    def test_syntax_error_generation_succeeds(self, tmp_path: Path):
        """Test that generating syntax error programs succeeds (even though execution
        fails)."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate syntax error scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only syntax error scenarios
        syntax_error_scenarios = {
            sid: res for sid, res in results.items() if "syntax_error" in sid
        }

        assert len(syntax_error_scenarios) > 0, "No syntax error scenarios found"

        for scenario_id, lang_results in syntax_error_scenarios.items():
            for language, result in lang_results.items():
                # Generation should succeed
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

                # Code should be generated
                assert len(result.code) > 0, (
                    f"No code generated for {scenario_id}/{language}"
                )

                # Files should exist
                scenario_dir = output_dir / scenario_id
                if language == "python":
                    assert (scenario_dir / "test_program.py").exists()
                elif language == "javascript":
                    assert (scenario_dir / "test_program.js").exists()
                elif language == "java":
                    assert (scenario_dir / "TestProgram.java").exists()


class TestInfiniteLoopScenarios:
    """Tests for infinite loop scenarios - verify they run with timeout."""

    def test_infinite_loop_starts_execution(self, tmp_path: Path):
        """Test that infinite loop programs start and run (timeout expected)."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate infinite loop scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only infinite loop scenarios
        infinite_loop_scenarios = {
            sid: res for sid, res in results.items() if "infinite_loop" in sid
        }

        assert len(infinite_loop_scenarios) > 0, "No infinite loop scenarios found"

        for scenario_id, _lang_results in infinite_loop_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Python - should timeout (success means it was running)
            py_file = scenario_dir / "test_program.py"
            try:
                subprocess.run(
                    [sys.executable, str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                pytest.fail(
                    f"Python infinite loop {scenario_id} should timeout but terminated",
                )
            except subprocess.TimeoutExpired:
                pass

            # JavaScript - should timeout
            js_file = scenario_dir / "test_program.js"
            try:
                subprocess.run(
                    ["node", str(js_file)],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                pytest.fail(
                    f"JavaScript infinite loop {scenario_id} should timeout but terminated",
                )
            except subprocess.TimeoutExpired:
                pass

            # Java - compile first, then should timeout
            java_file = scenario_dir / "TestProgram.java"
            compile_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert compile_result.returncode == 0, (
                f"Java infinite loop {scenario_id} should compile: {compile_result.stderr}"
            )

            try:
                subprocess.run(
                    ["java", "TestProgram"],
                    capture_output=True,
                    text=True,
                    cwd=str(scenario_dir),
                    timeout=3,
                )
                pytest.fail(
                    f"Java infinite loop {scenario_id} should timeout but terminated",
                )
            except subprocess.TimeoutExpired:
                pass

    def test_infinite_loop_produces_output(self, tmp_path: Path):
        """Test that infinite loop programs produce progress output before timeout."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate infinite loop scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only infinite loop scenarios
        infinite_loop_scenarios = {
            sid: res for sid, res in results.items() if "infinite_loop" in sid
        }

        for scenario_id, _lang_results in infinite_loop_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Python - capture output before timeout
            py_file = scenario_dir / "test_program.py"
            try:
                subprocess.run(
                    [sys.executable, str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
            except subprocess.TimeoutExpired as e:
                output = e.stdout.decode() if e.stdout else ""
                assert "Still running:" in output, (
                    f"Expected progress output in Python {scenario_id}, got: {output}"
                )

    def test_infinite_loop_can_be_terminated(self, tmp_path: Path):
        """Test that infinite loop programs can be interrupted via timeout."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate infinite loop scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only infinite loop scenarios
        infinite_loop_scenarios = {
            sid: res for sid, res in results.items() if "infinite_loop" in sid
        }

        assert len(infinite_loop_scenarios) > 0, "No infinite loop scenarios found"

        for scenario_id, _lang_results in infinite_loop_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Test that timeout mechanism works (program is interruptible)
            py_file = scenario_dir / "test_program.py"
            with pytest.raises(subprocess.TimeoutExpired):
                subprocess.run(
                    [sys.executable, str(py_file)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )


class TestStackOverflowScenarios:
    """Tests for stack overflow scenarios - verify they crash as expected."""

    def test_stack_overflow_programs_crash(self, tmp_path: Path):
        """Test that stack overflow programs crash with recursion errors."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate stack overflow scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only stack overflow scenarios
        stack_overflow_scenarios = {
            sid: res
            for sid, res in results.items()
            if "stack_overflow" in sid or "recursive" in sid
        }

        assert len(stack_overflow_scenarios) > 0, "No stack overflow scenarios found"

        for scenario_id, _lang_results in stack_overflow_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Python should crash with RecursionError
            py_file = scenario_dir / "test_program.py"
            py_result = subprocess.run(
                [sys.executable, str(py_file)],
                capture_output=True,
                text=True,
            )
            assert py_result.returncode != 0, (
                f"Python stack overflow {scenario_id} should crash but succeeded"
            )
            assert "RecursionError" in py_result.stderr, (
                f"Expected RecursionError in {scenario_id}, got: {py_result.stderr}"
            )

            # JavaScript should crash (stack overflow)
            js_file = scenario_dir / "test_program.js"
            js_result = subprocess.run(
                ["node", str(js_file)],
                capture_output=True,
                text=True,
            )
            assert js_result.returncode != 0, (
                f"JavaScript stack overflow {scenario_id} should crash but succeeded"
            )
            # Node.js: "RangeError: Maximum call stack size exceeded"
            assert "stack" in js_result.stderr.lower(), (
                f"Expected stack error in {scenario_id}, got: {js_result.stderr}"
            )

            # Java should crash with StackOverflowError
            java_file = scenario_dir / "TestProgram.java"
            compile_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert compile_result.returncode == 0, (
                f"Java stack overflow {scenario_id} should compile: {compile_result.stderr}"
            )

            java_result = subprocess.run(
                ["java", "TestProgram"],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert java_result.returncode != 0, (
                f"Java stack overflow {scenario_id} should crash but succeeded"
            )
            # Java: "Exception in thread "main" java.lang.StackOverflowError"
            assert "StackOverflowError" in java_result.stderr, (
                f"Expected StackOverflowError in {scenario_id}, got: {java_result.stderr}"
            )

    def test_stack_overflow_generation_succeeds(self, tmp_path: Path):
        """Test that generating stack overflow programs succeeds."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate stack overflow scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only stack overflow scenarios
        stack_overflow_scenarios = {
            sid: res
            for sid, res in results.items()
            if "stack_overflow" in sid or "recursive" in sid
        }

        assert len(stack_overflow_scenarios) > 0, "No stack overflow scenarios found"

        for scenario_id, lang_results in stack_overflow_scenarios.items():
            for language, result in lang_results.items():
                # Generation should succeed
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

                # Code should be generated
                assert len(result.code) > 0, (
                    f"No code generated for {scenario_id}/{language}"
                )

                # Should have recursive function definition
                if language == "python":
                    assert "def recursive_function" in result.code
                elif language == "javascript":
                    assert "function recursive_function" in result.code
                elif language == "java":
                    assert "recursive_function" in result.code

    def test_stack_overflow_markers_present(self, tmp_path: Path):
        """Test that stack overflow programs have markers at recursion points."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate stack overflow scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only stack overflow scenarios
        stack_overflow_scenarios = {
            sid: res
            for sid, res in results.items()
            if "stack_overflow" in sid or "recursive" in sid
        }

        for scenario_id, lang_results in stack_overflow_scenarios.items():
            # Verify each language has the function markers
            for language, result in lang_results.items():
                assert result.success, (
                    f"Generation should succeed for {scenario_id}/{language}"
                )

                # Should have markers for function definition and call
                func_markers = [m for m in result.markers if "func" in m]
                assert len(func_markers) >= 2, (
                    f"Expected function markers in {scenario_id}/{language}, "
                    f"found markers: {list(result.markers.keys())}"
                )


class TestLargeDataScenarios:
    """Tests for large data structure scenarios - verify they execute successfully."""

    def test_large_data_programs_execute(self, tmp_path: Path):
        """Test that large data programs execute successfully with realistic array
        sizes."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate large data scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only large data scenarios
        large_data_scenarios = {
            sid: res
            for sid, res in results.items()
            if "large_array" in sid or "large_data" in sid
        }

        assert len(large_data_scenarios) > 0, "No large data scenarios found"

        for scenario_id, _lang_results in large_data_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Python should execute successfully
            py_file = scenario_dir / "test_program.py"
            py_result = subprocess.run(
                [sys.executable, str(py_file)],
                capture_output=True,
                text=True,
                timeout=10,  # Increased timeout for large data
            )
            assert py_result.returncode == 0, (
                f"Python large data {scenario_id} failed: {py_result.stderr}"
            )
            # Should print checkpoint messages
            assert "Checkpoint:" in py_result.stdout, (
                f"Expected checkpoint output in {scenario_id}"
            )

            # JavaScript should execute successfully
            js_file = scenario_dir / "test_program.js"
            js_result = subprocess.run(
                ["node", str(js_file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert js_result.returncode == 0, (
                f"JavaScript large data {scenario_id} failed: {js_result.stderr}"
            )
            assert "Checkpoint:" in js_result.stdout, (
                f"Expected checkpoint output in {scenario_id}"
            )

            # Java should compile and execute successfully
            java_file = scenario_dir / "TestProgram.java"
            compile_result = subprocess.run(
                ["javac", str(java_file)],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
            )
            assert compile_result.returncode == 0, (
                f"Java large data {scenario_id} should compile: {compile_result.stderr}"
            )

            java_result = subprocess.run(
                ["java", "TestProgram"],
                capture_output=True,
                text=True,
                cwd=str(scenario_dir),
                timeout=10,
            )
            assert java_result.returncode == 0, (
                f"Java large data {scenario_id} failed: {java_result.stderr}"
            )
            assert "Checkpoint:" in java_result.stdout, (
                f"Expected checkpoint output in {scenario_id}"
            )

    def test_large_data_generation_succeeds(self, tmp_path: Path):
        """Test that generating large data programs succeeds."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate large data scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only large data scenarios
        large_data_scenarios = {
            sid: res
            for sid, res in results.items()
            if "large_array" in sid or "large_data" in sid
        }

        assert len(large_data_scenarios) > 0, "No large data scenarios found"

        for scenario_id, lang_results in large_data_scenarios.items():
            scenario_dir = output_dir / scenario_id

            # Check that generation succeeded for all languages
            for language in SUPPORTED_LANGUAGES:
                assert language in lang_results
                result = lang_results[language]
                assert result.success, (
                    f"Generation failed for {scenario_id}/{language}: {result.error}"
                )

                # Check files exist
                if language == "python":
                    py_path = scenario_dir / "test_program.py"
                    assert py_path.exists()
                    # Check for array creation
                    content = py_path.read_text()
                    assert "list(range(3000))" in content or "range(3000)" in content
                elif language == "javascript":
                    js_path = scenario_dir / "test_program.js"
                    assert js_path.exists()
                    content = js_path.read_text()
                    assert "Array.from({length: 3000}" in content
                elif language == "java":
                    java_path = scenario_dir / "TestProgram.java"
                    assert java_path.exists()
                    content = java_path.read_text()
                    assert "IntStream.range(0, 3000)" in content

    def test_large_data_markers_present(self, tmp_path: Path):
        """Test that all expected markers are present in large data programs."""
        generator = Generator()
        scenarios_dir = Path("src/aidb_cli/generators/scenarios")
        output_dir = tmp_path / "generated"

        # Generate large data scenarios
        critical_yaml = scenarios_dir / "critical.yaml"
        results = generator.generate_from_file(
            yaml_file=critical_yaml,
            output_dir=output_dir,
        )

        # Filter to only large data scenarios
        large_data_scenarios = {
            sid: res
            for sid, res in results.items()
            if "large_array" in sid or "large_data" in sid
        }

        assert len(large_data_scenarios) > 0, "No large data scenarios found"

        # Expected markers for large array operations
        expected_markers = {
            "var.create.large_array",
            "flow.loop.iterate",
            "flow.if.checkpoint",
            "func.print.checkpoint",
        }

        for scenario_id, lang_results in large_data_scenarios.items():
            for language, result in lang_results.items():
                # Extract markers from generated code
                marker_set = set(result.markers.keys())

                # Verify all expected markers are present
                assert expected_markers.issubset(marker_set), (
                    f"Missing markers in {scenario_id}/{language}. "
                    f"Expected: {expected_markers}, Found: {marker_set}"
                )
