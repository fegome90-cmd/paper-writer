"""Citation consistency validation rules.

Pure domain functions that check inline citation keys against
bibliography entries. No file I/O or subprocess calls.
"""

from typing import Any


def validate_citation_consistency(
    bib_keys: set[str],
    citation_keys: set[str],
) -> list[dict[str, Any]]:
    """Check that all citation keys map to bibliography entries.

    Args:
        bib_keys: Set of keys found in references.bib.
        citation_keys: Set of keys found in manuscript drafts.

    Returns:
        List of finding dicts for unresolved citations.
    """
    findings: list[dict[str, Any]] = []
    unresolved = citation_keys - bib_keys

    for key in sorted(unresolved):
        findings.append(
            {
                "code": "unresolved_citation",
                "severity": "error",
                "message": f"Citation key '{key}' not found in bibliography.",
                "location": key,
            }
        )

    return findings
