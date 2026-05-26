"""Reference metadata validator.

Checks that bibliography entries satisfy metadata rules: each entry
must have at least a year, and entries with a DOI or URL field are
considered fully validated. Returns structured findings for the gate system.
"""

import re
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.bibliography import validate_bibliography
from validators.refs import validate_refs_metadata


class RefsMetadataValidator(ToolWrapper):
    """Validates that bibliography entries satisfy metadata completeness rules.

    Checks:
    - Every entry has a ``year`` field (or equivalent date).
    - Entries with ``doi`` or ``url`` are flagged as complete.
    - Entries missing both ``doi`` and ``url`` get a warning (not error).
    - Entries missing ``year`` get an error.
    """

    @property
    def name(self) -> str:
        return "refs-metadata-validator"

    @property
    def gate(self) -> str:
        return "refs_validated"

    def is_available(self) -> bool:
        """Pure Python — always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        bib_path = artifacts.get("bibliography")

        if not bib_path:
            return ValidatorResult(
                validator="refs-metadata",
                status="fail",
                summary="No bibliography file specified.",
                findings=[
                    {
                        "code": "missing_artifact",
                        "severity": "error",
                        "message": "Artifacts dict missing 'bibliography' key.",
                    }
                ],
                artifacts_checked=[],
            )

        bib_file = Path(bib_path)
        artifacts_checked: list[str] = [str(bib_file)]
        findings: list[dict[str, Any]] = []

        if not bib_file.is_file():
            findings.append(
                {
                    "code": "file_not_found",
                    "severity": "error",
                    "message": f"Bibliography file not found: {bib_path}",
                    "artifact": bib_path,
                }
            )
            return ValidatorResult(
                validator="refs-metadata",
                status="fail",
                summary=f"Bibliography file not found: {bib_path}",
                findings=findings,
                artifacts_checked=artifacts_checked,
            )

        # Parse entries (I/O + parsing — wrapper responsibility)
        content = bib_file.read_text(encoding="utf-8", errors="replace")
        entries = self._parse_entries(content)

        if not entries:
            findings.append(
                {
                    "code": "no_entries",
                    "severity": "error",
                    "message": "No bibliography entries found.",
                    "artifact": bib_path,
                }
            )
            return ValidatorResult(
                validator="refs-metadata",
                status="fail",
                summary="No bibliography entries found.",
                findings=findings,
                artifacts_checked=artifacts_checked,
            )

        # Delegate validation logic to domain validators
        findings.extend(validate_refs_metadata(entries))

        # Additional metadata checks from bibliography domain rules

        # Parse entry types for type-aware validation
        entry_types: dict[str, str] = {}
        type_pattern = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE)
        for match in type_pattern.finditer(content):
            entry_types[match.group(2).strip()] = match.group(1)

        findings.extend(validate_bibliography(entries, entry_types))

        error_count = sum(1 for f in findings if f["severity"] == "error")

        if error_count > 0:
            status = "fail"
            summary = (
                f"{error_count} error(s) in {len(entries)} entries (metadata validation failed)."
            )
        else:
            status = "pass"
            summary = f"All {len(entries)} entries satisfy metadata rules."

        return ValidatorResult(
            validator="refs-metadata",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )

    def _parse_entries(self, content: str) -> dict[str, dict[str, str]]:
        """Parse BibTeX entries into {key: {field: value}} map.

        Uses simple regex parsing — sufficient for validation purposes.
        Does NOT need to be a full BibTeX parser.
        """
        entries: dict[str, dict[str, str]] = {}

        # Match @type{key, ... }
        entry_pattern = re.compile(
            r"@\w+\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\s*\}",
            re.DOTALL | re.IGNORECASE,
        )

        for match in entry_pattern.finditer(content):
            key = match.group(1).strip()
            body = match.group(2)
            fields: dict[str, str] = {}

            # Parse field = value pairs
            for field_match in re.finditer(r"(\w+)\s*=\s*\{([^}]*)\}", body, re.IGNORECASE):
                field_name = field_match.group(1).lower()
                field_value = field_match.group(2).strip()
                fields[field_name] = field_value

            entries[key] = fields

        return entries
