from __future__ import annotations

from typing import Any


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate overlapping findings using sweep-line algorithm.

    SSOT — this is the ONLY dedup implementation used by all validators.

    Algorithm:
      1. Sort by span start ASC, then by length DESC (longest first at same start).
      2. Keep a finding if it extends beyond the current coverage end.
         This preserves findings that partially overlap but contribute unique span.

    Args:
        findings: Raw findings that may overlap.

    Returns:
        Deduplicated findings with assigned finding_id values.
    """
    if not findings:
        return []

    severity_order = {"P0": 0, "P1": 1, "P2": 2}

    sorted_fs = sorted(
        findings,
        key=lambda f: (
            f.get("span", [0, 0])[0],
            -(f.get("span", [0, 0])[1] - f.get("span", [0, 0])[0]),
            severity_order.get(f.get("severity", "P2"), 2),
            f.get("rule_id", ""),
        ),
    )

    deduped: list[dict[str, Any]] = []
    # Track coverage per rule_id so findings from different rules are never collapsed.
    coverage_by_rule: dict[str, int] = {}

    for f in sorted_fs:
        _start, end = f.get("span", [0, 0])
        rule_id = f.get("rule_id", "")
        coverage_end = coverage_by_rule.get(rule_id, -1)

        if end > coverage_end:
            deduped.append(f)
            coverage_by_rule[rule_id] = end

    for i, f in enumerate(deduped):
        f["finding_id"] = f"F-{i + 1:03d}"

    return deduped
