from __future__ import annotations

import json
from typing import Any


def format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_terminal(findings: list[dict[str, Any]]) -> str:
    """Format findings as human-readable terminal output.

    Each finding gets a severity icon and one-line description.
    """
    icons = {"P0": "[!!]", "P1": "[!]", "P2": "[i]"}
    lines: list[str] = []
    for f in findings:
        icon = icons.get(f.get("severity", "P2"), "[?]")
        rule_id = f.get("rule_id", "unknown")
        msg = f.get("message", "")
        line = f.get("line", "?")
        col = f.get("column", "?")
        lines.append(f"{icon} {rule_id}: {msg} (line {line}, col {col})")
    if not lines:
        lines.append("No findings.")
    return "\n".join(lines)


def format_gate_result(result: dict[str, Any], output_format: str = "terminal") -> str:
    """Format gate method result for output."""
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)

    lines: list[str] = []
    passed = result.get("gate_passed", False)
    lines.append(f"Gate: {'PASSED' if passed else 'BLOCKED'}")
    lines.append(f"  Guideline: {result.get('guideline', 'N/A')}")
    lines.append(f"  Study type: {result.get('study_type', 'N/A')}")

    summary = result.get("summary", {})
    lines.append(f"  Total items: {summary.get('total_items', 0)}")
    lines.append(f"  Passed: {summary.get('passed', 0)}")
    lines.append(f"  Blockers: {summary.get('blockers', 0)}")
    lines.append(f"  Warnings: {summary.get('warnings', 0)}")
    lines.append(f"  N/A: {summary.get('not_applicable', 0)}")

    blockers = result.get("blockers", [])
    if blockers:
        lines.append("")
        lines.append("[!!] BLOCKERS:")
        for b in blockers:
            lines.append(f"  - {b.get('description', '')}")
            lines.append(f"    Expected: {b.get('expected_location', '?')}")
            lines.append(f"    {b.get('message', '')}")

    warnings_list = result.get("warnings", [])
    if warnings_list:
        lines.append("")
        lines.append("[!] Warnings:")
        for w in warnings_list:
            lines.append(f"  - {w.get('description', '')}: {w.get('message', '')}")

    return "\n".join(lines)


def format_claims_output(result: dict[str, Any], output_format: str = "terminal") -> str:
    """Format claim audit result for output."""
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)

    candidates = result.get("candidates", [])
    lines: list[str] = []
    risk_icons = {"high": "[!!]", "medium": "[!]", "low": "[i]", "info": "[-]"}

    lines.append(f"Total claim candidates: {len(candidates)}")
    summary = result.get("summary", {})
    by_risk = summary.get("by_risk", {})
    lines.append(
        f"  High: {by_risk.get('high', 0)}  "
        f"Medium: {by_risk.get('medium', 0)}  "
        f"Low: {by_risk.get('low', 0)}  "
        f"Info: {by_risk.get('info', 0)}"
    )
    lines.append("")

    for c in candidates:
        icon = risk_icons.get(c.get("risk", "info"), "[?]")
        lines.append(f"{icon} [{c.get('claim_type', '?')}] {c.get('text', '')[:100]}")
        lines.append(f"    Section: {c.get('section', '?')} | Line: {c.get('line', '?')}")
        triggers = c.get("triggers", [])
        if triggers:
            lines.append(f"    Triggers: {', '.join(triggers)}")
        lines.append("")

    return "\n".join(lines)
