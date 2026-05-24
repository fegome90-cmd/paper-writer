"""Reporting checklist validation rules.

Pure domain functions that check manuscript sections against
reporting guideline requirements (study design, sample size,
limitations). No file I/O or subprocess calls.
"""

from typing import Any

REQUIRED_ELEMENTS: list[tuple[str, list[str]]] = [
    (
        "study_design",
        [
            "cross-sectional",
            "cohort",
            "case-control",
            "randomized",
            "trial",
            "longitudinal",
            "study design",
            "retrospective",
            "prospective",
            "observational",
            "experimental",
        ],
    ),
    (
        "sample_size",
        [
            "n=",
            "participants",
            "subjects",
            "patients",
            "sample size",
            "cohort of",
            "enrolled",
            "recruited",
        ],
    ),
    (
        "limitations",
        ["limitation", "limitation", "bias", "confound", "caveat", "restriction", "weakness"],
    ),
]


def validate_reporting(
    sections: dict[str, str],
) -> list[dict[str, Any]]:
    """Check manuscript sections against reporting checklist requirements.

    Args:
        sections: Map of {section_name: section_text}.

    Returns:
        List of finding dicts for missing or incomplete reporting elements.
    """
    findings: list[dict[str, Any]] = []
    combined_text = " ".join(sections.values()).lower()

    # Check that sections are non-empty
    for name, text in sections.items():
        stripped = text.strip()
        if not stripped or (stripped.startswith("#") and len(stripped.split("\n")) <= 1):
            findings.append(
                {
                    "code": "empty_section",
                    "severity": "error",
                    "message": f"Section '{name}' appears empty or placeholder-only.",
                    "location": name,
                }
            )

    # Check required reporting elements
    for element, keywords in REQUIRED_ELEMENTS:
        found = any(kw in combined_text for kw in keywords)
        if not found:
            findings.append(
                {
                    "code": f"missing_{element}",
                    "severity": "warning",
                    "message": (
                        f"No mention of {element.replace('_', ' ')} found. "
                        f"Consider adding explicit reporting of {element.replace('_', ' ')}."
                    ),
                    "location": "manuscript",
                }
            )

    return findings
