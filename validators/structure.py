"""Section structure validation rules.

Pure domain functions that check manuscript section presence and
ordering. No file I/O or subprocess calls.
"""

from typing import Any

# Core sections required for any manuscript (hard error if missing)
REQUIRED_SECTIONS = ["introduction", "methods", "results", "discussion"]

# Extended sections from the manifest — recommended but not blocking
RECOMMENDED_SECTIONS = ["abstract", "literature_review", "conclusion"]


def validate_section_structure(
    existing_sections: list[str],
) -> list[dict[str, Any]]:
    """Check that all required manuscript sections are present.

    Args:
        existing_sections: List of section names found in drafts.

    Returns:
        List of finding dicts for missing sections. Core sections
        produce errors; recommended sections produce warnings.
    """
    if existing_sections is None:
        return []
    findings: list[dict[str, Any]] = []
    existing_lower = {s.lower() for s in existing_sections}

    for section in REQUIRED_SECTIONS:
        if section not in existing_lower:
            findings.append(
                {
                    "code": "missing_section",
                    "severity": "error",
                    "message": (
                        f"Required section '{section}' is missing from the manuscript drafts."
                    ),
                    "location": section,
                }
            )

    for section in RECOMMENDED_SECTIONS:
        if section not in existing_lower:
            findings.append(
                {
                    "code": "missing_recommended_section",
                    "severity": "warning",
                    "message": (
                        f"Recommended section '{section}' is missing from the manuscript drafts."
                    ),
                    "location": section,
                }
            )

    return findings
