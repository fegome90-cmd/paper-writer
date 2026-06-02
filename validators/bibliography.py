"""Bibliography normalization rules.

Pure domain functions that normalize and validate BibTeX entries:
field normalization, sorting, duplicate detection, entry type validation.
No file I/O or subprocess calls — operates on parsed data structures.
"""

import re
from typing import Any

# Valid BibTeX entry types
VALID_ENTRY_TYPES: frozenset[str] = frozenset(
    {
        "article",
        "book",
        "booklet",
        "conference",
        "inbook",
        "incollection",
        "inproceedings",
        "manual",
        "mastersthesis",
        "misc",
        "phdthesis",
        "proceedings",
        "techreport",
        "unpublished",
    }
)

# Required fields per entry type
REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "article": frozenset({"author", "title", "journal", "year"}),
    "book": frozenset({"author", "title", "publisher", "year"}),
    "inproceedings": frozenset({"author", "title", "booktitle", "year"}),
    "phdthesis": frozenset({"author", "title", "school", "year"}),
    "mastersthesis": frozenset({"author", "title", "school", "year"}),
    "techreport": frozenset({"author", "title", "institution", "year"}),
    "misc": frozenset({"author", "title", "year"}),
    "unpublished": frozenset({"author", "title", "note"}),
}


def normalize_entry_fields(fields: dict[str, str]) -> dict[str, str]:
    """Normalize field names to lowercase and strip whitespace from values.

    Args:
        fields: Map of {field_name: field_value}.

    Returns:
        Normalized fields dict with lowercase keys and stripped values.
        None values are converted to empty strings.
    """
    normalized: dict[str, str] = {}
    for key, value in fields.items():
        normalized[key.lower().strip()] = value.strip() if isinstance(value, str) else ""
    return normalized


def detect_duplicate_keys(entries: dict[str, dict[str, str]]) -> list[str]:
    """Detect entries that share the same key (case-insensitive).

    Args:
        entries: Map of {entry_key: {field_name: field_value}}.

    Returns:
        List of duplicate keys found.
    """
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for key in entries:
        lower_key = key.lower()
        if lower_key in seen:
            duplicates.append(key)
        else:
            seen[lower_key] = key
    return duplicates


def validate_entry_type(
    entry_type: str,
) -> list[dict[str, Any]]:
    """Validate that an entry type is recognized.

    Args:
        entry_type: The BibTeX entry type (e.g., 'article', 'book').

    Returns:
        List of findings for invalid types.
    """
    findings: list[dict[str, Any]] = []
    if entry_type.lower() not in VALID_ENTRY_TYPES:
        findings.append(
            {
                "code": "unknown_entry_type",
                "severity": "warning",
                "message": (
                    f"Unrecognized entry type '@{entry_type}'. "
                    f"Expected one of: {', '.join(sorted(VALID_ENTRY_TYPES))}."
                ),
                "location": entry_type,
            }
        )
    return findings


def validate_required_fields(
    entry_type: str,
    fields: dict[str, str],
    entry_key: str,
) -> list[dict[str, Any]]:
    """Validate that an entry has required fields for its type.

    Args:
        entry_type: The BibTeX entry type.
        fields: Normalized field map for the entry.
        entry_key: The entry key for error messages.

    Returns:
        List of findings for missing required fields.
    """
    findings: list[dict[str, Any]] = []
    et_lower = entry_type.lower()
    required = REQUIRED_FIELDS.get(et_lower)

    if required is None:
        # Unknown type — no required fields check
        return findings

    missing = required - set(fields.keys())
    for field_name in sorted(missing):
        findings.append(
            {
                "code": "missing_required_field",
                "severity": "error",
                "message": (
                    f"Entry '{entry_key}' (@{et_lower}) is missing required field '{field_name}'."
                ),
                "location": entry_key,
            }
        )
    return findings


def validate_doi_format(doi: str, entry_key: str) -> list[dict[str, Any]]:
    """Validate DOI format.

    Args:
        doi: The DOI string to validate.
        entry_key: Entry key for error messages.

    Returns:
        List of findings for malformed DOIs.
    """
    findings: list[dict[str, Any]] = []
    # DOI pattern: 10.XXXX/... where XXXX is registrant code
    if not re.match(r"^10\.\d{4,9}/\S+$", doi.strip()):
        findings.append(
            {
                "code": "malformed_doi",
                "severity": "error",
                "message": (
                    f"Entry '{entry_key}' has malformed DOI: '{doi}'. "
                    f"Expected format: 10.XXXX/suffix"
                ),
                "location": entry_key,
            }
        )
    return findings


def validate_year_range(year: str, entry_key: str) -> list[dict[str, Any]]:
    """Validate year is within a reasonable range.

    Args:
        year: The year string to validate.
        entry_key: Entry key for error messages.

    Returns:
        List of findings for out-of-range years.
    """
    findings: list[dict[str, Any]] = []
    try:
        year_int = int(year.strip())
    except ValueError:
        findings.append(
            {
                "code": "invalid_year",
                "severity": "error",
                "message": f"Entry '{entry_key}' has non-numeric year: '{year}'.",
                "location": entry_key,
            }
        )
        return findings

    if year_int < 1900 or year_int > 2030:
        findings.append(
            {
                "code": "suspicious_year",
                "severity": "warning",
                "message": (
                    f"Entry '{entry_key}' has year {year_int}, "
                    f"which is outside the expected range (1900-2030)."
                ),
                "location": entry_key,
            }
        )
    return findings


def validate_bibliography(
    entries: dict[str, dict[str, str]],
    entry_types: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Run all bibliography validation checks.

    Args:
        entries: Map of {entry_key: {field_name: field_value}}.
            Fields should be pre-normalized (lowercase keys).
        entry_types: Optional map of {entry_key: entry_type}.

    Returns:
        Aggregated list of findings from all validation checks.
    """
    findings: list[dict[str, Any]] = []

    # Check for duplicate keys
    duplicates = detect_duplicate_keys(entries)
    for dup in duplicates:
        findings.append(
            {
                "code": "duplicate_key",
                "severity": "error",
                "message": f"Duplicate entry key detected: '{dup}'.",
                "location": dup,
            }
        )

    for key, fields in entries.items():
        # Normalize fields
        normalized = normalize_entry_fields(fields)

        # Validate entry type if provided
        if entry_types and key in entry_types:
            etype = entry_types[key]
            findings.extend(validate_entry_type(etype))
            findings.extend(validate_required_fields(etype, normalized, key))

        # Validate DOI format if present
        if "doi" in normalized:
            findings.extend(validate_doi_format(normalized["doi"], key))

        # Validate year if present
        if "year" in normalized:
            findings.extend(validate_year_range(normalized["year"], key))

    return findings
