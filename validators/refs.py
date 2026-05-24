"""Reference metadata validation rules.

Pure domain functions that check bibliography entries against
metadata requirements: year presence, DOI/URL availability.
No file I/O or subprocess calls — operates on parsed data structures.
"""

from typing import Any


def validate_refs_metadata(
    entries: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Validate bibliography entries against metadata rules.

    Checks:
    - Every entry must have a 'year' field.
    - Every entry must have a 'doi' or 'url' field.

    Args:
        entries: Map of {entry_key: {field_name: field_value}}.

    Returns:
        List of finding dicts with code, severity, message, location.
    """
    findings: list[dict[str, Any]] = []

    for key, fields in entries.items():
        if "year" not in fields:
            findings.append(
                {
                    "code": "missing_year",
                    "severity": "error",
                    "message": f"Entry '{key}' is missing a 'year' field.",
                    "location": key,
                }
            )

        if "doi" not in fields and "url" not in fields:
            findings.append(
                {
                    "code": "no_persistent_id",
                    "severity": "error",
                    "message": (
                        f"Entry '{key}' has neither 'doi' nor 'url'. "
                        f"At least one persistent identifier is required."
                    ),
                    "location": key,
                }
            )

    return findings
