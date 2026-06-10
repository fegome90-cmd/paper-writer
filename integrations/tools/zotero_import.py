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
        return "bib_imported"

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
        repo_root = Path(context.get("repo_path") or context.get("cwd", ".")).resolve()
        target_path = Path(target_bib)
        if not target_path.is_absolute():
            target_path = repo_root / target_path

        target_path = target_path.resolve()
        if target_path.is_dir():
            target_path = target_path / "references.bib"

        if not target_path.is_relative_to(repo_root):
            return ValidatorResult(
                validator="zotero-import",
                status="fail",
                summary="Path traversal detected for target_bib.",
                findings=[
                    {
                        "code": "path_traversal",
                        "severity": "error",
                        "message": f"Target path resolves outside repository bounds: {target_bib}",
                    }
                ],
                artifacts_checked=[],
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)

        incremental = artifacts.get("incremental", False)
        if incremental and target_path.exists():
            source_content = source_path.read_text(encoding="utf-8", errors="replace")
            target_content = target_path.read_text(encoding="utf-8", errors="replace")

            # Deduplicate: remove target entries whose keys appear in source
            source_keys = set(entries.keys())
            deduped = ZoteroImporter._remove_entries_by_keys(target_content, source_keys)

            merged = deduped
            if merged and not merged.endswith("\n"):
                merged += "\n"
            merged += source_content
            target_path.write_text(merged, encoding="utf-8")
        else:
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
    def _remove_entries_by_keys(content: str, keys_to_remove: set[str]) -> str:
        """Remove BibTeX entries whose citation keys match *keys_to_remove*.

        Uses brace-depth-aware scanning so nested braces in field values
        are handled correctly.  Meta-entries (@string, @comment, @preamble)
        are preserved unconditionally.
        """
        import re as _re

        _META_TYPES = frozenset({"string", "comment", "preamble"})
        pattern = _re.compile(r"@(\w+)\s*([\{\(])", _re.IGNORECASE)

        chunks: list[str] = []
        last_pos = 0
        search_pos = 0

        while search_pos < len(content):
            m = pattern.search(content, search_pos)
            if not m:
                break
            if m.group(1).lower() in _META_TYPES:
                search_pos = m.end()
                continue

            start = m.end()
            depth = 1
            pos = start
            open_char = m.group(2)
            close_char = "}" if open_char == "{" else ")"

            while pos < len(content) and depth > 0:
                if content[pos] == "\\" and pos + 1 < len(content):
                    pos += 2
                    continue
                if content[pos] == open_char:
                    depth += 1
                elif content[pos] == close_char:
                    depth -= 1
                pos += 1

            if depth != 0:
                search_pos = start
                continue

            search_pos = pos
            entry_body = content[start : pos - 1]
            comma_pos = entry_body.find(",")
            key = entry_body[:comma_pos].strip() if comma_pos != -1 else entry_body.strip()

            if key in keys_to_remove:
                chunks.append(content[last_pos : m.start()])
                last_pos = pos

        chunks.append(content[last_pos:])
        return "".join(chunks)

    @staticmethod
    def _parse_bib(content: str) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
        """Parse BibTeX entries and types from content.

        Returns:
            Tuple of (entries dict, entry_types dict).
        """
        entries: dict[str, dict[str, str]] = {}
        entry_types: dict[str, str] = {}

        # Brace-depth-aware parser handles single-line and multiline entries
        _META_TYPES = frozenset({"string", "comment", "preamble"})
        for m in re.finditer(r"@(\w+)\s*([\{\(])", content, re.IGNORECASE):
            if m.group(1).lower() in _META_TYPES:
                continue
            start = m.end()
            depth = 1
            pos = start
            open_char = m.group(2)
            close_char = "}" if open_char == "{" else ")"

            while pos < len(content) and depth > 0:
                # Skip escaped characters to avoid depth desync
                if content[pos] == "\\" and pos + 1 < len(content):
                    pos += 2
                    continue
                if content[pos] == open_char:
                    depth += 1
                elif content[pos] == close_char:
                    depth -= 1
                pos += 1
            if depth != 0:
                continue
            entry_body = content[start : pos - 1]
            comma_pos = entry_body.find(",")
            if comma_pos == -1:
                key = entry_body.strip()
                if key:
                    entries[key] = {}
                    entry_types[key] = m.group(1)
                continue
            key = entry_body[:comma_pos].strip()
            body = entry_body[comma_pos + 1 :]
            fields: dict[str, str] = {}

            bpos = 0
            while bpos < len(body):
                # Skip leading whitespace, commas, and newlines between fields
                while bpos < len(body) and body[bpos] in " \t\r\n,":
                    bpos += 1

                # Use re.match (anchored) so we only match a field key at the
                # current parse position — never inside a previously-parsed value.
                field_match = re.match(r"([\w-]+)\s*=\s*", body[bpos:], re.IGNORECASE)
                if not field_match:
                    bpos += 1
                    continue
                field_name = field_match.group(1).lower().strip()
                val_start = bpos + field_match.end()

                if val_start < len(body) and body[val_start] == "{":
                    # Brace-delimited value
                    vd = 1
                    vp = val_start + 1
                    while vp < len(body) and vd > 0:
                        if body[vp] == "\\" and vp + 1 < len(body):
                            vp += 2
                            continue
                        if body[vp] == "{":
                            vd += 1
                        elif body[vp] == "}":
                            vd -= 1
                        vp += 1
                    fields[field_name] = body[val_start + 1 : vp - 1].strip()
                    bpos = vp
                elif val_start < len(body) and body[val_start] == '"':
                    # Double-quote-delimited value
                    vp = val_start + 1
                    while vp < len(body):
                        if body[vp] == "\\" and vp + 1 < len(body):
                            vp += 2
                            continue
                        if body[vp] == '"':
                            vp += 1
                            break
                        vp += 1
                    fields[field_name] = body[val_start + 1 : vp - 1].strip()
                    bpos = vp
                elif val_start < len(body):
                    # Bare value: ends at next comma that precedes a field key
                    vp = val_start
                    while vp < len(body):
                        if body[vp] == "," and re.match(r"\s*\w+\s*=", body[vp + 1 :]):
                            break
                        vp += 1
                    fields[field_name] = body[val_start:vp].strip().rstrip(",")
                    bpos = vp
                else:
                    break

            entries[key] = fields
            entry_types[key] = m.group(1)

        return entries, entry_types
