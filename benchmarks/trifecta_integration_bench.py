"""A/B Benchmark: does paper-writer find MORE issues with Trifecta?

This benchmark measures the value of Trifecta integration by running paper-writer's
audit commands in two modes:

  1. WITHOUT Trifecta (MCP_TRIFECTA_MODE=off, default for safety)
  2. WITH Trifecta (MCP_TRIFECTA_MODE=real)

It counts capabilities, findings, and effective commands in each mode, then
generates a comparison report.

The benchmark is the GATE for whether the integration is worth keeping.
If paper-writer doesn't measurably improve with Trifecta, the integration
should be reconsidered.

Usage:
    uv run python benchmarks/trifecta_integration_bench.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = REPO_ROOT / "docs" / "integration" / "trifecta-bench-results.md"


@dataclass
class BenchmarkResult:
    """Result of running a paper command in a given mode."""

    command: str
    mode: str  # "off" or "real"
    success: bool
    output: str
    findings_count: int = 0
    capabilities: list[str] = field(default_factory=list)
    error: str = ""

    def is_effective(self) -> bool:
        """Did the command produce non-trivial output?"""
        if not self.success:
            return False
        # "SKIPPED" or "Trifecta not enabled" means degraded
        if "SKIPPED" in self.output or "not enabled" in self.output:
            return False
        return True


def run_paper_command(cmd: list[str], mode: str, timeout: int = 30) -> BenchmarkResult:
    """Run a paper command with the given MCP_TRIFECTA_MODE.

    Args:
        cmd: paper subcommand and args, e.g. ["audit", "code-health", "--output", "json"]
        mode: "off" or "real"
        timeout: subprocess timeout in seconds

    Returns:
        BenchmarkResult with success, output, and findings count.
    """
    env = os.environ.copy()
    env["MCP_TRIFECTA_MODE"] = mode
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            ["uv", "run", "paper", *cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
            env=env,
        )
        output = result.stdout + result.stderr
        # For JSON output, parse it
        findings_count = 0
        if "--output" in cmd and "json" in cmd:
            try:
                # Find the JSON in stdout (skip any non-JSON lines)
                json_start = result.stdout.find("{")
                if json_start >= 0:
                    data = json.loads(result.stdout[json_start:])
                    findings_count = (
                        data.get("actionable_count", 0)
                        or data.get("findings_count", 0)
                        or len(data.get("findings", []))
                    )
            except (json.JSONDecodeError, ValueError):
                pass
        else:
            # For terminal output, count lines that look like findings
            findings_count = sum(
                1 for line in output.splitlines()
                if any(p in line for p in ("::", "validation_gap", "dead_code", "data_flow_break"))
            )

        # Success means: command ran and produced output.
        # exit code 1 is OK for code-health if it has findings (fail-closed).
        # SKIPPED / not enabled = degraded mode.
        is_degraded = "SKIPPED" in output or "not enabled" in output
        return BenchmarkResult(
            command=" ".join(cmd),
            mode=mode,
            success=not is_degraded,
            output=output,
            findings_count=findings_count,
        )
    except subprocess.TimeoutExpired:
        return BenchmarkResult(
            command=" ".join(cmd),
            mode=mode,
            success=False,
            output="",
            error=f"Timeout after {timeout}s",
        )
    except Exception as exc:
        return BenchmarkResult(
            command=" ".join(cmd),
            mode=mode,
            success=False,
            output="",
            error=str(exc),
        )


def run_benchmark() -> dict[str, Any]:
    """Run the full A/B benchmark.

    Returns:
        Dict with 'without_trifecta', 'with_trifecta', and 'comparison' keys.
    """
    commands_to_test = [
        ["audit", "code-health", "--output", "json"],
        ["trace", "Orchestrator.execute", "--action", "callers"],
        ["trace", "main", "--action", "path", "--to", "BibliographyNormalizer.run"],
        ["graph-overview"],
    ]

    without_trifecta: list[BenchmarkResult] = []
    with_trifecta: list[BenchmarkResult] = []

    for cmd in commands_to_test:
        # Run without Trifecta
        without_trifecta.append(run_paper_command(cmd, mode="off"))
        # Run with Trifecta
        with_trifecta.append(run_paper_command(cmd, mode="real"))

    return {
        "without_trifecta": without_trifecta,
        "with_trifecta": with_trifecta,
        "commands": [" ".join(c) for c in commands_to_test],
    }


def compute_comparison(results: dict[str, Any]) -> dict[str, Any]:
    """Compute comparison metrics from benchmark results."""
    without = results["without_trifecta"]
    with_t = results["with_trifecta"]
    cmds = results["commands"]

    without_effective = sum(1 for r in without if r.is_effective())
    with_effective = sum(1 for r in with_t if r.is_effective())

    without_findings = sum(r.findings_count for r in without)
    with_findings = sum(r.findings_count for r in with_t)

    return {
        "commands_tested": len(cmds),
        "without_trifecta": {
            "effective_commands": without_effective,
            "total_findings": without_findings,
        },
        "with_trifecta": {
            "effective_commands": with_effective,
            "total_findings": with_findings,
        },
        "delta": {
            "effective_commands": with_effective - without_effective,
            "total_findings": with_findings - without_findings,
        },
    }


def format_report(results: dict[str, Any], comparison: dict[str, Any]) -> str:
    """Format the benchmark results as a markdown report."""
    lines = [
        "# Trifecta Integration Benchmark Results",
        "",
        f"**Generated**: {datetime.now().isoformat()}",
        f"**Repo**: {REPO_ROOT}",
        "",
        "## Summary",
        "",
        f"- **Commands tested**: {comparison['commands_tested']}",
        f"- **Effective commands WITHOUT Trifecta**: {comparison['without_trifecta']['effective_commands']}",  # noqa: E501
        f"- **Effective commands WITH Trifecta**: {comparison['with_trifecta']['effective_commands']}",  # noqa: E501
        f"- **Delta (net new capabilities)**: +{comparison['delta']['effective_commands']}",
        f"- **Total findings WITHOUT Trifecta**: {comparison['without_trifecta']['total_findings']}",  # noqa: E501
        f"- **Total findings WITH Trifecta**: {comparison['with_trifecta']['total_findings']}",
        f"- **Delta findings**: +{comparison['delta']['total_findings']}",
        "",
        "## Per-command results",
        "",
        "| Command | Without Trifecta | With Trifecta | Delta |",
        "|---------|-----------------|---------------|-------|",
    ]

    for cmd, w, t in zip(results["commands"], results["without_trifecta"], results["with_trifecta"], strict=False):  # noqa: E501
        w_status = "✅" if w.is_effective() else "❌"
        t_status = "✅" if t.is_effective() else "❌"
        w_findings = w.findings_count
        t_findings = t.findings_count
        delta = t_findings - w_findings
        lines.append(
            f"| `{cmd}` | {w_status} ({w_findings} findings) "
            f"| {t_status} ({t_findings} findings) | +{delta} |"
        )

    lines.extend([
        "",
        "## Verdict",
        "",
    ])

    if comparison["delta"]["effective_commands"] > 0:
        lines.append(
            f"**PASSED**: Trifecta integration adds "
            f"+{comparison['delta']['effective_commands']} effective capabilities."
        )
    else:
        lines.append("**FAILED**: Trifecta integration adds no new capabilities.")

    if comparison["delta"]["total_findings"] > 0:
        lines.append(
            f"**PASSED**: Trifecta integration surfaces "
            f"+{comparison['delta']['total_findings']} additional findings."
        )
    else:
        lines.append("**INFO**: No additional findings from Trifecta in this run.")

    return "\n".join(lines) + "\n"


def main() -> int:
    """Run the benchmark and write results to disk."""
    print("Running A/B benchmark (without Trifecta, then with Trifecta)...")
    results = run_benchmark()
    comparison = compute_comparison(results)
    report = format_report(results, comparison)

    # Write to docs
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(report)
    print(f"\nResults written to: {RESULTS_PATH}")
    print("\n" + report)

    # Exit 0 if integration adds value, 1 otherwise
    if comparison["delta"]["effective_commands"] > 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
