"""Journal preset validation rules.

Pure domain functions that validate journal preset.yaml schemas.
No file I/O or subprocess calls.
"""

from typing import Any

# Required fields in preset.yaml
REQUIRED_PRESET_FIELDS: frozenset[str] = frozenset({
    "name",
    "format",
    "citation_style",
    "required_sections",
})


def validate_preset(preset: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a journal preset dictionary.

    Args:
        preset: Parsed preset.yaml contents.

    Returns:
        List of finding dicts for validation issues.
    """
    findings: list[dict[str, Any]] = []

    if not preset:
        findings.append(
            {
                "code": "empty_preset",
                "severity": "error",
                "message": "Preset is empty or could not be parsed.",
                "location": "preset",
            }
        )
        return findings

    # Check required fields
    for field in REQUIRED_PRESET_FIELDS:
        if field not in preset:
            findings.append(
                {
                    "code": "missing_preset_field",
                    "severity": "error",
                    "message": f"Preset is missing required field '{field}'.",
                    "location": field,
                }
            )

    # Validate required_sections is non-empty list
    sections = preset.get("required_sections")
    if sections is not None:
        if not isinstance(sections, list):
            findings.append(
                {
                    "code": "invalid_sections",
                    "severity": "error",
                    "message": "Preset field 'required_sections' must be a list.",
                    "location": "required_sections",
                }
            )
        elif len(sections) == 0:
            findings.append(
                {
                    "code": "empty_sections",
                    "severity": "error",
                    "message": "Preset field 'required_sections' must not be empty.",
                    "location": "required_sections",
                }
            )

    # Validate format is recognized
    valid_formats = {"docx", "pdf", "html", "latex"}
    fmt = preset.get("format")
    if fmt is not None and fmt not in valid_formats:
        findings.append(
            {
                "code": "invalid_format",
                "severity": "warning",
                "message": (
                    f"Preset format '{fmt}' is not in recognized"
                    f" formats: {', '.join(sorted(valid_formats))}."
                ),
                "location": "format",
            }
        )

    # Validate max_words is positive if present
    max_words = preset.get("max_words")
    if max_words is not None:
        if not isinstance(max_words, int) or max_words <= 0:
            findings.append(
                {
                    "code": "invalid_max_words",
                    "severity": "warning",
                    "message": (
                    f"Preset 'max_words' should be a positive"
                    f" integer, got: {max_words}."
                ),
                    "location": "max_words",
                }
            )

    return findings
