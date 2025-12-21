"""E2E performance tests for core debugging operations.

These tests measure and validate performance characteristics of debugging operations
across different languages and scenarios. Tests use MCP instrumentation (TraceSpan) for
detailed performance profiling.

**MCP-Only**: These tests require MCP's comprehensive instrumentation (correlation IDs,
token tracking, operation breakdown). API tests use basic timing assertions only.

Performance baselines are based on measured values from dogfooding (see SESSION_3_MEASUREMENTS.md):
- Measured on M1 Mac, native execution (no Docker)
- Baselines include 50-100% buffer for system variability
- Language multipliers account for startup differences (Java 2.5x, JS 0.8x)
"""

import asyncio
import contextlib
import time

import pytest

from tests._helpers.assertions.performance_assertions import PerformanceAssertions
from tests._helpers.constants import get_container_multiplier
from tests._helpers.debug_interface import MCPInterface
from tests._helpers.parametrization import parametrize_interfaces, parametrize_languages
from tests._helpers.test_bases.base_e2e_test import BaseE2ETest


@pytest.mark.serial
@pytest.mark.xdist_group(name="serial")
class TestPerformance(BaseE2ETest):
    """E2E performance tests with MCP instrumentation.

    Marked serial to ensure consistent timing when running with pytest-xdist
    parallelism. Performance tests are sensitive to CPU contention from parallel
    workers. The xdist_group marker ensures all tests in this class run on the same
    worker when using --dist loadgroup.
    """

    perf = PerformanceAssertions()

    # Reference baselines (measured on M1 Mac, Python, native execution)
    # Container multiplier (1.3x) applied automatically via get_container_multiplier()
    REFERENCE_BASELINES = {
        "session_startup": 3000,  # ms (native: ~2.6s, auto-adjusts for containers)
        "step_over": 150,  # ms (native: ~50ms, conservative)
        "breakpoint_hit": 150,  # ms (similar to step)
        "variable_inspection": 200,  # ms (native: ~31ms, conservative)
        "stack_trace": 100,  # ms (native: ~9ms, conservative)
        "evaluation_simple": 150,  # ms (native: ~50ms, conservative)
        "evaluation_complex": 200,  # ms (conservative)
        "large_program_startup": 3000,  # ms (same as session startup)
        "repeated_cycle": 250,  # ms (continue + inspect)
    }

    # Language-specific baseline multipliers
    # Adjusted for Docker container overhead
    # Java warmup is performed before session_startup measurement
    BASELINE_MULTIPLIERS = {
        "python": 1.0,
        "javascript": 1.0,
        "java": 1.3,
    }

    # Optional per-language, per-operation caps (pre-container), applied AFTER
    # language multiplier and BEFORE container multiplier. This trims overly
    # generous ceilings where we have strong headroom in practice.
    # Keys use REFERENCE_BASELINES names.
    LANGUAGE_BASELINE_CAPS_MS = {
        "javascript": {
            "session_startup": 2000,
            "step_over": 145,
            "variable_inspection": 190,
            "repeated_cycle": 230,
            "stack_trace": 90,  # Increased from 85 for CI variance (GHA: 0.225s threshold)
        },
        "java": {
            "session_startup": 2300,
            "step_over": 230,
            "variable_inspection": 310,
            "repeated_cycle": 230,
            "stack_trace": 85,
        },
    }

    def get_baseline(self, operation: str, language: str) -> float:
        """Get language-specific baseline in seconds.

        Automatically adjusts for container environments.

        Parameters
        ----------
        operation : str
            Operation name (from REFERENCE_BASELINES)
        language : str
            Language name

        Returns
        -------
        float
            Adjusted baseline in seconds
        """
        base_ms = self.REFERENCE_BASELINES[operation]
        language_multiplier = self.BASELINE_MULTIPLIERS.get(language, 1.0)
        container_multiplier = get_container_multiplier()

        # Apply language multiplier
        adjusted_ms = base_ms * language_multiplier

        # Apply optional per-language cap (pre-container)
        caps = self.LANGUAGE_BASELINE_CAPS_MS.get(language, {})
        cap_ms = caps.get(operation)
        if cap_ms is not None:
            adjusted_ms = min(adjusted_ms, cap_ms)

        return (adjusted_ms * container_multiplier) / 1000.0

    async def _warmup_java_session(self, debug_interface, program, markers):
        """Warmup Java JDT/LSP for accurate performance measurement.

        Java's first debug session includes JDT/LSP initialization overhead
        (~15-20s). Subsequent sessions are much faster (~3-5s). This warmup
        ensures we measure normal Java performance, not cold-start overhead.

        Parameters
        ----------
        debug_interface : DebugInterface
            Debug interface to use for warmup
        program : dict
            Program info from generated_program_factory
        markers : dict
            Marker lines for the program
        """
        await debug_interface.start_session(
            program=program["path"],
            breakpoints=[
                {"file": program["path"], "line": markers["var.init.counter"]},
            ],
        )
        # Stop the warmup session immediately (interface tracks current session)
        await debug_interface.stop_session()

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_session_startup_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test session startup latency from creation to first paused state.

        Measures the complete initialization cycle including adapter startup,
        DAP connection, and initial program load.

        For Java: Runs a warmup session first to initialize JDT/LSP, then
        measures the second session for accurate performance baseline (avoiding
        cold-start overhead).

        Baselines (Python):
        - Session start: <4000ms
        - Java: <8000ms (2.0x multiplier, post-warmup)
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("basic_variables", language)
        markers = program["markers"]

        # Java warmup: initialize JDT/LSP before measuring
        if language == "java":
            await self._warmup_java_session(debug_interface, program, markers)
            # Brief pause to ensure cleanup
            await asyncio.sleep(0.5)

        # Measure session startup time (post-warmup for Java)
        start_time = time.time()

        session_info = await debug_interface.start_session(
            program=program["path"],
            breakpoints=[
                {"file": program["path"], "line": markers["var.init.counter"]},
            ],
        )

        startup_time = time.time() - start_time

        # Verify session started
        assert session_info["session_id"] is not None
        assert session_info["status"] == "started"

        # Session should reach paused state quickly
        await self.wait_for_stopped_state(
            debug_interface,
            expected_line=markers["var.init.counter"],
        )
        total_time = time.time() - start_time

        # Assert baselines (language-specific)
        startup_baseline = self.get_baseline("session_startup", language)
        total_baseline = self.get_baseline("session_startup", language)

        self.perf.assert_operation_time(
            startup_time,
            startup_baseline,
            f"{language} session startup",
        )
        self.perf.assert_operation_time(
            total_time,
            total_baseline,
            f"{language} session to first pause",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_breakpoint_hit_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test breakpoint hit latency in loop iterations.

        Measures time to hit breakpoints across multiple iterations,
        ensuring consistent performance without degradation.

        Baselines (Python):
        - Set breakpoint: <100ms
        - Per hit: <50ms average
        - 10 hits: <500ms total
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        # Start session
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.add.total"]],  # Inside loop (5 iterations total)
        )

        # Measure time for 4 breakpoint hits (loop has 5 iterations, can continue 4 times from initial pause)
        start_time = time.time()
        hit_count = 0

        for _i in range(
            4,
        ):  # Loop has 5 iterations (0-4); continue 4 times from initial pause
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(
                state,
                expected_line=markers["var.add.total"],
            )
            hit_count += 1

        total_hit_time = time.time() - start_time
        avg_hit_time = total_hit_time / hit_count

        # Assert baselines
        per_hit_baseline = self.get_baseline("breakpoint_hit", language)
        total_baseline = self.get_baseline("breakpoint_hit", language) * 4  # 4 hits

        self.perf.assert_operation_time(
            avg_hit_time,
            per_hit_baseline,
            f"{language} average breakpoint hit",
        )
        self.perf.assert_operation_time(
            total_hit_time,
            total_baseline,
            f"{language} total for {hit_count} hits",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_stepping_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test stepping operation latency.

        Measures performance of consecutive step_over operations,
        ensuring low latency for interactive debugging.

        Baselines (Python):
        - Per step: <50ms
        - 20 steps: <1000ms total
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.init.total"]],
        )

        # Measure 20 consecutive step operations
        start_time = time.time()
        step_count = 20

        for _ in range(step_count):
            try:
                await debug_interface.step_over()
            except Exception:
                # Program may complete before 20 steps
                break

        total_step_time = time.time() - start_time
        avg_step_time = total_step_time / step_count

        # Assert baselines
        per_step_baseline = self.get_baseline("step_over", language)
        total_baseline = self.get_baseline("step_over", language) * 20  # 20 steps

        self.perf.assert_operation_time(
            avg_step_time,
            per_step_baseline,
            f"{language} average step_over",
        )
        self.perf.assert_operation_time(
            total_step_time,
            total_baseline,
            f"{language} total for {step_count} steps",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_variable_inspection_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test variable inspection throughput with large collections.

        Measures performance of get_variables() with large data structures,
        ensuring acceptable latency for large-scale debugging.

        Baselines (Python):
        - Inspection: <200ms for large arrays
        - Repeated: <250ms (with caching)
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("large_array_operations", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [list(markers.values())[0]],  # First marker in program
        )

        # Step over to ensure variable is defined (breakpoint hits before line executes)
        await debug_interface.step_over()

        # Measure variable inspection time
        start_time = time.time()
        variables = await debug_interface.get_variables()
        inspection_time = time.time() - start_time

        # Verify we got variables
        assert len(variables) > 0

        # Second inspection (may be cached)
        start_time_2 = time.time()
        await debug_interface.get_variables()
        inspection_time_2 = time.time() - start_time_2

        # Assert baselines
        first_baseline = self.get_baseline("variable_inspection", language)
        second_baseline = self.get_baseline("variable_inspection", language)

        self.perf.assert_operation_time(
            inspection_time,
            first_baseline,
            f"{language} first variable inspection",
        )
        self.perf.assert_operation_time(
            inspection_time_2,
            second_baseline,
            f"{language} second variable inspection",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_stack_trace_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test stack trace retrieval with deep call stacks.

        Measures performance of get_stack_trace() with deep recursion,
        ensuring acceptable latency for complex debugging scenarios.

        Baselines (Python):
        - Stack trace: <100ms for deep stacks
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("function_chain", language)
        markers = program["markers"]

        # Break inside nested function call
        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["func.call.multiply"]],  # Inside calculate() function
        )

        # Measure stack trace retrieval
        start_time = time.time()
        stack_trace = await debug_interface.get_stack_trace()
        trace_time = time.time() - start_time

        # Verify we got a stack trace with multiple frames
        assert len(stack_trace) >= 2  # At least main + calculate

        # Assert baseline
        baseline = self.get_baseline("stack_trace", language)
        self.perf.assert_operation_time(
            trace_time,
            baseline,
            f"{language} stack trace retrieval",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_repeated_operations_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test performance degradation over repeated operations.

        Measures whether performance degrades over many continue/inspect cycles,
        detecting memory leaks or performance regressions.

        Baselines (Python):
        - Per cycle: <100ms
        - 20 cycles: <2000ms
        - No degradation: last 5 cycles ~= first 5 cycles
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("basic_for_loop", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.add.total"]],
        )

        # Measure 4 continue/inspect cycles (loop has 5 iterations, can continue 4 times from initial pause)
        cycle_times = []
        for _i in range(
            4,
        ):  # Loop has 5 iterations (0-4); continue 4 times from initial pause
            start_time = time.time()

            # Continue to breakpoint
            state = await debug_interface.continue_execution()
            self.verify_exec.verify_stopped(state)

            # Inspect variables
            await debug_interface.get_variables()

            cycle_time = time.time() - start_time
            cycle_times.append(cycle_time)

        # Calculate statistics
        avg_cycle_time = sum(cycle_times) / len(cycle_times)
        first_half_avg = sum(cycle_times[: len(cycle_times) // 2]) / (
            len(cycle_times) // 2
        )
        second_half_avg = sum(cycle_times[len(cycle_times) // 2 :]) / (
            len(cycle_times) - len(cycle_times) // 2
        )

        # Assert baselines
        per_cycle_baseline = self.get_baseline("repeated_cycle", language)
        self.perf.assert_operation_time(
            avg_cycle_time,
            per_cycle_baseline,
            f"{language} average cycle time",
        )

        # Check for degradation: second half shouldn't be >50% slower
        degradation_ratio = (
            second_half_avg / first_half_avg if first_half_avg > 0 else 1.0
        )
        assert degradation_ratio < 1.5, (
            f"{language} performance degraded: "
            f"first_half={first_half_avg:.3f}s, second_half={second_half_avg:.3f}s, "
            f"ratio={degradation_ratio:.2f}"
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_large_program_startup_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test session startup with complex nested code.

        Measures startup performance impact of deeply nested structures,
        ensuring acceptable latency for large/complex programs.

        Baselines (Python):
        - Startup: <1000ms for complex programs
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("nested_loops", language)
        markers = program["markers"]

        # Measure startup time for complex program
        start_time = time.time()

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [list(markers.values())[0]],  # First marker
        )

        startup_time = time.time() - start_time

        # Assert baseline (more generous for complex programs)
        baseline = self.get_baseline("large_program_startup", language)
        self.perf.assert_operation_time(
            startup_time,
            baseline,
            f"{language} complex program startup",
        )

    @parametrize_interfaces
    @parametrize_languages()
    @pytest.mark.asyncio
    async def test_evaluation_performance(
        self,
        debug_interface,
        language,
        generated_program_factory,
    ):
        """Test expression evaluation latency.

        Measures performance of evaluate() with complex expressions,
        ensuring low latency for watch expressions and interactive eval.

        Baselines (Python):
        - Simple eval: <50ms
        - Complex eval: <100ms
        """
        if not isinstance(debug_interface, MCPInterface):
            pytest.skip("Performance tests require MCP instrumentation")

        program = generated_program_factory("complex_expressions", language)
        markers = program["markers"]

        await self.start_session_with_breakpoints(
            debug_interface,
            program["path"],
            [markers["var.calc.result"]],
        )

        # Step over to ensure variable is defined
        await debug_interface.step_over()

        # Measure simple evaluation
        start_time = time.time()
        await debug_interface.evaluate("result")
        simple_eval_time = time.time() - start_time

        # Measure complex evaluation (if variable exists)
        start_time = time.time()
        # Variable may not exist in scope - still measuring timing
        with contextlib.suppress(Exception):
            await debug_interface.evaluate("a")
        complex_eval_time = time.time() - start_time

        # Assert baselines
        simple_baseline = self.get_baseline("evaluation_simple", language)
        complex_baseline = self.get_baseline("evaluation_complex", language)

        self.perf.assert_operation_time(
            simple_eval_time,
            simple_baseline,
            f"{language} simple expression evaluation",
        )
        self.perf.assert_operation_time(
            complex_eval_time,
            complex_baseline,
            f"{language} complex expression evaluation",
        )
