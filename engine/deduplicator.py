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

    sorted_fs = sorted(
        findings,
        key=lambda f: (
            f.get("span", [0, 0])[0],
            -(f.get("span", [0, 0])[1] - f.get("span", [0, 0])[0]),
        ),
    )

    deduped: list[dict[str, Any]] = []
    coverage_end = -1

    for f in sorted_fs:
        start, end = f.get("span", [0, 0])
        # Keep if non-overlapping OR if it extends beyond current coverage
        if end > coverage_end:
            deduped.append(f)
            coverage_end = end

    for i, f in enumerate(deduped):
        f["finding_id"] = f"F-{i + 1:03d}"

    return deduped
