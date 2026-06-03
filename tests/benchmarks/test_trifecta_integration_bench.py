"""Tests for the Trifecta integration A/B benchmark.

These tests verify the benchmark logic is correct (without running the
actual subprocess commands — that's done by the benchmark itself).
"""
from __future__ import annotations

from benchmarks.trifecta_integration_bench import (
    BenchmarkResult,
    compute_comparison,
    format_report,
)


def _make_result(
    mode: str,
    success: bool = True,
    output: str = "Some output",
    findings_count: int = 0,
    error: str = "",
) -> BenchmarkResult:
    """Helper to build a BenchmarkResult for tests."""
    return BenchmarkResult(
        command="test cmd",
        mode=mode,
        success=success,
        output=output,
        findings_count=findings_count,
        error=error,
    )


class TestBenchmarkResult:
    """BenchmarkResult data class and is_effective()."""

    def test_is_effective_when_success_and_output(self) -> None:
        """Successful command with real output is effective."""
        r = _make_result("real", success=True, output="35 actionable findings")
        assert r.is_effective() is True

    def test_not_effective_when_skipped(self) -> None:
        """SKIPPED output is not effective (degraded)."""
        r = _make_result("off", success=True, output="Code health: SKIPPED")
        assert r.is_effective() is False

    def test_not_effective_when_not_enabled(self) -> None:
        """'not enabled' output is not effective."""
        r = _make_result("off", success=True, output="Trifecta not enabled")
        assert r.is_effective() is False

    def test_not_effective_when_failed(self) -> None:
        """Failed command is not effective."""
        r = _make_result("off", success=False, output="Error")
        assert r.is_effective() is False


class TestComputeComparison:
    """compute_comparison() correctly aggregates results."""

    def test_counts_effective_commands(self) -> None:
        """Counts effective commands per mode."""
        without = [
            _make_result("off", success=True, output="SKIPPED"),
            _make_result("off", success=True, output="SKIPPED"),
            _make_result("off", success=True, output="real output"),  # effective
        ]
        with_t = [
            _make_result("real", success=True, output="real output"),
            _make_result("real", success=True, output="real output"),
        ]
        result = compute_comparison({
            "without_trifecta": without,
            "with_trifecta": with_t,
            "commands": ["c1", "c2", "c3"],
        })
        assert result["without_trifecta"]["effective_commands"] == 1
        assert result["with_trifecta"]["effective_commands"] == 2

    def test_aggregates_findings(self) -> None:
        """Aggregates total findings per mode."""
        without = [
            _make_result("off", success=True, output="real", findings_count=0),
            _make_result("off", success=True, output="real", findings_count=0),
        ]
        with_t = [
            _make_result("real", success=True, output="real", findings_count=35),
            _make_result("real", success=True, output="real", findings_count=0),
        ]
        result = compute_comparison({
            "without_trifecta": without,
            "with_trifecta": with_t,
            "commands": ["c1", "c2"],
        })
        assert result["without_trifecta"]["total_findings"] == 0
        assert result["with_trifecta"]["total_findings"] == 35
        assert result["delta"]["total_findings"] == 35

    def test_calculates_delta(self) -> None:
        """Delta is the difference between modes."""
        without = [
            _make_result("off", success=True, output="real", findings_count=5),
        ]
        with_t = [
            _make_result("real", success=True, output="real", findings_count=20),
        ]
        result = compute_comparison({
            "without_trifecta": without,
            "with_trifecta": with_t,
            "commands": ["c1"],
        })
        assert result["delta"]["total_findings"] == 15


class TestFormatReport:
    """format_report() produces a useful markdown report."""

    def test_report_includes_summary(self) -> None:
        """Report includes the summary section."""
        result = {
            "without_trifecta": [_make_result("off", success=True, output="real")],
            "with_trifecta": [_make_result("real", success=True, output="real", findings_count=10)],
            "commands": ["c1"],
        }
        comparison = compute_comparison(result)
        report = format_report(result, comparison)
        assert "## Summary" in report
        assert "Commands tested**" in report
        assert "**Commands tested**: 1" in report

    def test_report_includes_per_command_table(self) -> None:
        """Report has a per-command table."""
        result = {
            "without_trifecta": [_make_result("off", success=True, output="SKIPPED")],
            "with_trifecta": [_make_result("real", success=True, output="real", findings_count=5)],
            "commands": ["c1"],
        }
        comparison = compute_comparison(result)
        report = format_report(result, comparison)
        assert "## Per-command results" in report
        assert "| Command |" in report
        assert "`c1`" in report

    def test_report_includes_verdict(self) -> None:
        """Report ends with a verdict."""
        result = {
            "without_trifecta": [_make_result("off", success=True, output="SKIPPED")],
            "with_trifecta": [_make_result("real", success=True, output="real", findings_count=5)],
            "commands": ["c1"],
        }
        comparison = compute_comparison(result)
        report = format_report(result, comparison)
        assert "## Verdict" in report
        # With +1 effective command and +5 findings, both should PASS
        assert "PASSED" in report
