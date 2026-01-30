"""Unit tests for aggregate_flakes_report.py script."""

import json
from pathlib import Path

import pytest
from _script_loader import load_script_module

# Load the script module
aggregate_flakes_report = load_script_module("aggregate_flakes_report")


# Test fixtures


@pytest.fixture
def mock_flakes_data_suite1() -> dict:
    """Mock flakes.json data for suite 1."""
    return {
        "suite": "shared-python",
        "flaky_tests": [
            "src/tests/aidb/session/test_session.py::test_connect",
            "src/tests/aidb/service/test_service.py::test_call",
        ],
        "consistently_failing": [],
        "rerun_count": 2,
        "timestamp": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def mock_flakes_data_suite2() -> dict:
    """Mock flakes.json data for suite 2."""
    return {
        "suite": "core",
        "flaky_tests": [
            "src/tests/aidb/session/test_session.py::test_connect",  # Same as suite1
            "src/tests/aidb/dap/test_protocol.py::test_message",
        ],
        "consistently_failing": [
            "src/tests/aidb/dap/test_client.py::test_timeout",
        ],
        "rerun_count": 3,
        "timestamp": "2024-01-15T10:35:00Z",
    }


@pytest.fixture
def mock_flakes_data_no_flakes() -> dict:
    """Mock flakes.json data with no flakes."""
    return {
        "suite": "cli",
        "flaky_tests": [],
        "consistently_failing": [],
        "rerun_count": 0,
        "timestamp": "2024-01-15T10:40:00Z",
    }


@pytest.fixture
def setup_summaries_dir(
    tmp_path: Path,
    mock_flakes_data_suite1: dict,
    mock_flakes_data_suite2: dict,
) -> Path:
    """Create a summaries directory with mock flakes.json files."""
    summaries_dir = tmp_path / "summaries"

    # Create artifact directories
    artifact1_dir = summaries_dir / "test-summary-shared-python"
    artifact1_dir.mkdir(parents=True)
    (artifact1_dir / "flakes.json").write_text(json.dumps(mock_flakes_data_suite1))

    artifact2_dir = summaries_dir / "test-summary-core"
    artifact2_dir.mkdir(parents=True)
    (artifact2_dir / "flakes.json").write_text(json.dumps(mock_flakes_data_suite2))

    return summaries_dir


class TestLoadFlakesFiles:
    """Test loading flakes.json files from directory."""

    def test_load_multiple_files(
        self,
        setup_summaries_dir: Path,
    ):
        """Test loading multiple flakes.json files."""
        result = aggregate_flakes_report.load_flakes_files(setup_summaries_dir)

        assert len(result) == 2
        suites = {d["suite"] for d in result}
        assert "shared-python" in suites
        assert "core" in suites

    def test_load_empty_directory(self, tmp_path: Path):
        """Test loading from empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = aggregate_flakes_report.load_flakes_files(empty_dir)

        assert result == []

    def test_load_ignores_missing_flakes_json(self, tmp_path: Path):
        """Test that directories without flakes.json are ignored."""
        summaries_dir = tmp_path / "summaries"
        artifact_dir = summaries_dir / "test-summary-cli"
        artifact_dir.mkdir(parents=True)
        # Create summary.md but no flakes.json
        (artifact_dir / "summary.md").write_text("# Summary")

        result = aggregate_flakes_report.load_flakes_files(summaries_dir)

        assert result == []

    def test_load_handles_malformed_json(self, tmp_path: Path, capsys):
        """Test that malformed JSON files are skipped with warning."""
        summaries_dir = tmp_path / "summaries"
        artifact_dir = summaries_dir / "test-summary-bad"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "flakes.json").write_text("not valid json")

        result = aggregate_flakes_report.load_flakes_files(summaries_dir)

        assert result == []
        captured = capsys.readouterr()
        assert "Warning" in captured.err


class TestAggregateFlakes:
    """Test flakes aggregation logic."""

    def test_aggregate_single_suite(self, mock_flakes_data_suite1: dict):
        """Test aggregating single suite data."""
        result = aggregate_flakes_report.aggregate_flakes([mock_flakes_data_suite1])

        assert result["total_flaky_tests"] == 2
        assert result["total_consistently_failing"] == 0
        assert "shared-python" in result["by_suite"]
        assert len(result["by_test"]) == 2

    def test_aggregate_multiple_suites(
        self,
        mock_flakes_data_suite1: dict,
        mock_flakes_data_suite2: dict,
    ):
        """Test aggregating multiple suites with overlapping tests."""
        result = aggregate_flakes_report.aggregate_flakes(
            [
                mock_flakes_data_suite1,
                mock_flakes_data_suite2,
            ]
        )

        # test_connect appears in both suites, so total unique flaky is 3
        assert result["total_flaky_tests"] == 3
        assert result["total_consistently_failing"] == 1
        assert len(result["by_suite"]) == 2

        # Check that test_connect is tracked with both suites
        test_connect_key = "src/tests/aidb/session/test_session.py::test_connect"
        assert test_connect_key in result["by_test"]
        assert result["by_test"][test_connect_key]["flake_count"] == 2
        assert len(result["by_test"][test_connect_key]["suites"]) == 2

    def test_aggregate_empty_data(self):
        """Test aggregating empty data."""
        result = aggregate_flakes_report.aggregate_flakes([])

        assert result["total_flaky_tests"] == 0
        assert result["total_consistently_failing"] == 0
        assert result["by_test"] == {}
        assert result["by_suite"] == {}

    def test_aggregate_no_flakes(self, mock_flakes_data_no_flakes: dict):
        """Test aggregating suite with no flakes."""
        result = aggregate_flakes_report.aggregate_flakes([mock_flakes_data_no_flakes])

        assert result["total_flaky_tests"] == 0
        assert result["total_consistently_failing"] == 0
        assert "cli" in result["by_suite"]
        assert result["by_suite"]["cli"]["flaky_count"] == 0


class TestFormatGithubSummary:
    """Test GitHub summary markdown formatting."""

    def test_format_with_flaky_tests(
        self,
        mock_flakes_data_suite1: dict,
        mock_flakes_data_suite2: dict,
    ):
        """Test formatting with flaky tests."""
        aggregated = aggregate_flakes_report.aggregate_flakes(
            [
                mock_flakes_data_suite1,
                mock_flakes_data_suite2,
            ]
        )

        result = aggregate_flakes_report.format_github_summary(aggregated, "12345678")

        assert "## Flaky Tests Report" in result
        assert "3 flaky test(s)" in result
        assert "| Test | Suites | Count |" in result
        assert "By Suite" in result
        assert "gh run download 12345678" in result

    def test_format_no_flakes(self):
        """Test formatting when no flakes detected."""
        aggregated = {
            "by_test": {},
            "by_suite": {},
            "total_flaky_tests": 0,
            "total_consistently_failing": 0,
        }

        result = aggregate_flakes_report.format_github_summary(aggregated, "12345678")

        assert "No flaky or retried tests detected" in result

    def test_format_with_consistently_failing(self, mock_flakes_data_suite2: dict):
        """Test formatting with consistently failing tests."""
        aggregated = aggregate_flakes_report.aggregate_flakes([mock_flakes_data_suite2])

        result = aggregate_flakes_report.format_github_summary(aggregated, "12345678")

        assert "Consistently Failing (not flaky)" in result
        assert "test_timeout" in result


class TestExportReport:
    """Test JSON report export."""

    def test_export_creates_file(self, tmp_path: Path):
        """Test that export creates the report file."""
        aggregated = {
            "by_test": {},
            "by_suite": {},
            "total_flaky_tests": 0,
            "total_consistently_failing": 0,
        }
        output_path = tmp_path / "flaky-tests-report.json"

        aggregate_flakes_report.export_report(aggregated, "12345678", output_path)

        assert output_path.exists()

    def test_export_json_structure(
        self,
        tmp_path: Path,
        mock_flakes_data_suite1: dict,
    ):
        """Test that exported JSON has correct structure."""
        aggregated = aggregate_flakes_report.aggregate_flakes([mock_flakes_data_suite1])
        output_path = tmp_path / "flaky-tests-report.json"

        aggregate_flakes_report.export_report(aggregated, "12345678", output_path)

        data = json.loads(output_path.read_text())
        assert data["run_id"] == "12345678"
        assert "timestamp" in data
        assert "by_test" in data
        assert "by_suite" in data
        assert data["total_flaky_tests"] == 2


class TestIntegration:
    """Integration tests for the full workflow."""

    def test_full_workflow(self, setup_summaries_dir: Path, tmp_path: Path):
        """Test the complete aggregation workflow."""
        # Load files
        flakes_data = aggregate_flakes_report.load_flakes_files(setup_summaries_dir)
        assert len(flakes_data) == 2

        # Aggregate
        aggregated = aggregate_flakes_report.aggregate_flakes(flakes_data)
        assert aggregated["total_flaky_tests"] == 3

        # Format summary
        summary = aggregate_flakes_report.format_github_summary(aggregated, "99999999")
        assert "## Flaky Tests Report" in summary

        # Export report
        output_path = tmp_path / "report.json"
        aggregate_flakes_report.export_report(aggregated, "99999999", output_path)
        assert output_path.exists()

        # Verify exported data
        data = json.loads(output_path.read_text())
        assert data["run_id"] == "99999999"
        assert data["total_flaky_tests"] == 3
