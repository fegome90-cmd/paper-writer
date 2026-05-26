"""Zotero/Better BibTeX import wrapper.

Imports a .bib file exported from Zotero/Better BibTeX into the
paper-writer bibliography pipeline. Validates and normalizes before
accepting. Does NOT call Zotero API directly — only handles file import.

This is an OPTIONAL integration surface. It is not required for MVP
delivery. The bibliography truth always remains inspectable and auditable.
"""

import re
import shutil
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.bibliography import validate_bibliography


class ZoteroImporter(ToolWrapper):
    """Imports .bib files from Zotero/Better BibTeX exports.

    Accepts a path to a Zotero-exported .bib file, validates it
    against domain rules, and copies it to the target bibliography path.

    Does NOT:
    - Call Zotero API
    - Modify workflow state directly
    - Bypass the gate system
    """

    @property
    def name(self) -> str:
        return "zotero-import"

    @property
    def gate(self) -> str:
        return "bib_normalized"

    def is_available(self) -> bool:
        """Always available — pure Python, no external tool needed."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        """Import a .bib file from Zotero export.

        Expected artifacts:
        - ``source_bib``: Path to the Zotero-exported .bib file.
        - ``target_bib``: Path where the validated .bib should be copied.
          Defaults to ``templates/references.bib``.

        Returns:
            ValidatorResult with validation findings and import status.
        """
        source_bib = artifacts.get("source_bib")
        if not source_bib:
            return ValidatorResult(
                validator="zotero-import",
                status="fail",
                summary="No source .bib file specified.",
                findings=[
                    {
                        "code": "missing_artifact",
                        "severity": "error",
                        "message": "Artifacts dict missing 'source_bib' key.",
                    }
                ],
                artifacts_checked=[],
            )

        source_path = Path(source_bib)
        if not source_path.is_file():
            return ValidatorResult(
                validator="zotero-import",
                status="fail",
                summary=f"Source .bib file not found: {source_bib}",
                findings=[
                    {
                        "code": "file_not_found",
                        "severity": "error",
                        "message": f"Source file does not exist: {source_bib}",
                        "artifact": source_bib,
                    }
                ],
                artifacts_checked=[],
            )

        # Read and validate the source .bib
        content = source_path.read_text(encoding="utf-8", errors="replace")
        entries, entry_types = self._parse_bib(content)

        findings: list[dict[str, Any]] = []

        if not entries:
            return ValidatorResult(
                validator="zotero-import",
                status="fail",
                summary="Source .bib file contains no valid entries.",
                findings=[
                    {
                        "code": "no_entries",
                        "severity": "error",
                        "message": "No BibTeX entries found in source file.",
                        "artifact": source_bib,
                    }
                ],
                artifacts_checked=[source_bib],
            )

        # Delegate to domain validator
        findings.extend(validate_bibliography(entries, entry_types))

        errors = [f for f in findings if f["severity"] == "error"]
        if errors:
            return ValidatorResult(
                validator="zotero-import",
                status="fail",
                summary=(
                    f"Source .bib has {len(errors)} error(s). "
                    f"Import blocked — fix errors before importing."
                ),
                findings=findings,
                artifacts_checked=[source_bib],
            )

        # Copy to target if validation passed
        target_bib = artifacts.get("target_bib", "templates/references.bib")
        target_path = Path(target_bib)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

        warnings = [f for f in findings if f["severity"] == "warning"]
        status = "warn" if warnings else "pass"
        summary = f"Imported {len(entries)} entries from Zotero export → {target_path}"
        if warnings:
            summary += f" ({len(warnings)} warning(s))"

        return ValidatorResult(
            validator="zotero-import",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=[source_bib, str(target_path)],
        )

    @staticmethod
    def _parse_bib(content: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
        """Parse BibTeX entries and types from content.

        Returns:
            Tuple of (entries dict, entry_types dict).
        """
        entries: dict[str, dict[str, str]] = {}
        entry_types: dict[str, str] = {}

        entry_pattern = re.compile(
            r"@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\s*\}",
            re.DOTALL | re.IGNORECASE,
        )

        for match in entry_pattern.finditer(content):
            entry_type = match.group(1)
            key = match.group(2).strip()
            body = match.group(3)
            fields: dict[str, str] = {}

            for field_match in re.finditer(r"(\w+)\s*=\s*\{([^}]*)\}", body, re.IGNORECASE):
                fields[field_match.group(1).lower().strip()] = field_match.group(2).strip()

            entries[key] = fields
            entry_types[key] = entry_type

        return entries, entry_types
