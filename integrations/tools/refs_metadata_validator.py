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
        type_pattern = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)", re.IGNORECASE)
        for match in type_pattern.finditer(content):
            key = match.group(2).strip()
            entry_types[key] = match.group(1)

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

        Uses brace-depth-aware parsing to handle single-line entries,
        nested braces in field values, unbraced values, and comments.
        Skips non-entry types (@string, @comment, @preamble).
        """
        _META_TYPES = frozenset({"string", "comment", "preamble"})
        entries: dict[str, dict[str, str]] = {}

        # Find entry starts: @type{
        for m in re.finditer(r"@(\w+)\s*\{", content, re.IGNORECASE):
            entry_type = m.group(1).lower()
            if entry_type in _META_TYPES:
                continue
            start = m.end()  # position after opening {

            # Find the matching closing } by tracking brace depth
            depth = 1
            pos = start
            while pos < len(content) and depth > 0:
                ch = content[pos]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                pos += 1

            if depth != 0:
                continue  # unmatched brace — skip

            entry_body = content[start : pos - 1]  # exclude closing }

            # First token (before comma) is the key
            comma_pos = entry_body.find(",")
            if comma_pos == -1:
                key = entry_body.strip()
                if key:
                    entries[key] = {}
                continue

            key = entry_body[:comma_pos].strip()
            body = entry_body[comma_pos + 1 :]
            fields: dict[str, str] = {}

            # Parse field = value pairs with brace depth tracking
            for fm in re.finditer(r"(\w+)\s*=\s*", body, re.IGNORECASE):
                field_name = fm.group(1).lower()
                val_start = fm.end()

                if val_start >= len(body):
                    continue

                if body[val_start] == "{":
                    # Braced value — find matching }
                    vd = 1
                    vp = val_start + 1
                    while vp < len(body) and vd > 0:
                        if body[vp] == "{":
                            vd += 1
                        elif body[vp] == "}":
                            vd -= 1
                        vp += 1
                    field_value = body[val_start + 1 : vp - 1].strip()
                else:
                    # Unbraced value — read until comma or end
                    end = body.find(",", val_start)
                    if end == -1:
                        end = len(body)
                    field_value = body[val_start:end].strip().strip('"').strip("'")

                if field_value:
                    fields[field_name] = field_value

            entries[key] = fields

        return entries
