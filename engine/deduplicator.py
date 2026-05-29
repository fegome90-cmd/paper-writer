from __future__ import annotations

from typing import Any


def deduplicate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve overlapping matches: longest match wins.

    When two findings overlap on the same span, keep the one with
    the longer match text (by span length).

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
    last_end = -1

    for f in sorted_fs:
        start, end = f.get("span", [0, 0])
        if start >= last_end:
            deduped.append(f)
            last_end = end

    for i, f in enumerate(deduped):
        f["finding_id"] = f"F-{i + 1:03d}"

    return deduped
