"""Bibliography normalization wrapper.

Runs bibtex-tidy (or falls back to a built-in validator) to normalize
and validate the references.bib file. Returns structured findings
consumed by the gate system.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.bibliography import validate_bibliography


class BibliographyNormalizer(ToolWrapper):
    """Normalizes and validates the references.bib file.

    Uses bibtex-tidy if available. Falls back to a built-in syntax
    check that detects unclosed braces and malformed entries.
    """

    _MINIMUM_VERSION: ClassVar[str] = "1.11.0"

    @property
    def name(self) -> str:
        return "bibtex-tidy"

    @property
    def gate(self) -> str:
        return "bib_normalized"

    def is_available(self) -> bool:
        """bibtex-tidy is available if the resolver can find it."""
        if self._resolver:
            return self._resolver.resolve(self.name, self._MINIMUM_VERSION) is not None
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        bib_path = artifacts.get("bibliography")
        if not bib_path:
            return ValidatorResult(
                validator="bibliography",
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
        if not bib_file.is_file():
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"Bibliography file not found: {bib_path}",
                findings=[
                    {
                        "code": "file_not_found",
                        "severity": "error",
                        "message": f"File does not exist: {bib_path}",
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[],
            )

        # Resolve path to bibtex-tidy via tool resolver
        resolution = None
        if self._resolver:
            resolution = self._resolver.resolve(self.name, self._MINIMUM_VERSION)

        if not resolution:
            # Fall back to built-in validation
            return self._builtin_validate(bib_file, bib_path)

        executable = resolution.path

        # Backup the original bibliography file to protect against corruption during --modify
        # Apply strict collision protection
        backup_path = bib_file.with_suffix(".bib.bak")
        if backup_path.exists():
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary="Backup collision detected: references.bib.bak already exists.",
                findings=[
                    {
                        "code": "backup_collision",
                        "severity": "error",
                        "message": (
                            "A temporary backup file already exists. Aborting to prevent data loss."
                        ),
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        try:
            shutil.copy2(bib_file, backup_path)
        except OSError as e:
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"Failed to create backup of bibliography file: {e}",
                findings=[
                    {
                        "code": "backup_error",
                        "severity": "error",
                        "message": f"Could not copy {bib_path} to backup: {e}",
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        # Execute bibtex-tidy with strict parameters
        try:
            result = subprocess.run(
                [str(executable), str(bib_file), "--modify", "--sort"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                # Restore original file from backup
                if backup_path.exists():
                    shutil.move(str(backup_path), str(bib_file))
                return ValidatorResult(
                    validator="bibliography",
                    status="fail",
                    summary="bibtex-tidy reported errors. Restored bibliography from backup.",
                    findings=self._parse_bibtex_tidy_errors(result.stderr, bib_path),
                    artifacts_checked=[bib_path],
                )

            # Success, remove backup file
            if backup_path.exists():
                backup_path.unlink()
        except (OSError, subprocess.SubprocessError) as e:
            # Restore original file from backup
            if backup_path.exists():
                shutil.move(str(backup_path), str(bib_file))
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"bibtex-tidy execution failed: {e}. Restored backup.",
                findings=[
                    {
                        "code": "tool_error",
                        "severity": "error",
                        "message": str(e),
                        "artifact": bib_path,
                    }
                ],
                artifacts_checked=[bib_path],
            )

        findings: list[dict[str, Any]] = []
        summary = "Bibliography normalized successfully."

        return ValidatorResult(
            validator="bibliography",
            status="pass",
            summary=summary,
            findings=findings,
            artifacts_checked=[bib_path],
        )

    def _builtin_validate(self, bib_file: Path, bib_path: str) -> ValidatorResult:
        """Built-in BibTeX validation when bibtex-tidy is not available.

        Parses entries and delegates domain validation to
        validators.bibliography. Emits explicit degraded-mode notice.
        """

        findings: list[dict[str, Any]] = []
        content = bib_file.read_text(encoding="utf-8", errors="replace")

        # Explicit degraded-mode notice
        findings.append(
            {
                "code": "degraded_mode",
                "severity": "warning",
                "message": (
                    "bibtex-tidy not installed. Using built-in validation. "
                    "Install: npm install -g bibtex-tidy"
                ),
                "artifact": bib_path,
            }
        )

        if not content.strip():
            findings.append(
                {
                    "code": "empty_file",
                    "severity": "error",
                    "message": "Bibliography file is empty.",
                    "artifact": bib_path,
                }
            )
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary="Bibliography file is empty.",
                findings=findings,
                artifacts_checked=[bib_path],
            )

        # Basic brace balance check
        open_braces = content.count("{")
        close_braces = content.count("}")
        if open_braces != close_braces:
            findings.append(
                {
                    "code": "unbalanced_braces",
                    "severity": "error",
                    "message": f"Unbalanced braces: {open_braces} open, {close_braces} close.",
                    "artifact": bib_path,
                }
            )

        # Parse entries and entry types for domain validation
        # Brace-depth-aware parser handles single-line and multiline entries
        _META_TYPES = frozenset({"string", "comment", "preamble"})
        entries: dict[str, dict[str, str]] = {}
        entry_types: dict[str, str] = {}

        for m in re.finditer(r"@(\w+)\s*\{", content, re.IGNORECASE):
            entry_type_raw = m.group(1).lower()
            if entry_type_raw in _META_TYPES:
                continue
            start = m.end()
            depth = 1
            pos = start
            while pos < len(content) and depth > 0:
                if content[pos] == "{":
                    depth += 1
                elif content[pos] == "}":
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
            for field_match in re.finditer(r"(\w+)\s*=\s*", body, re.IGNORECASE):
                field_name = field_match.group(1).lower().strip()
                val_start = field_match.end()
                if val_start < len(body) and body[val_start] == "{":
                    vd = 1
                    vp = val_start + 1
                    while vp < len(body) and vd > 0:
                        if body[vp] == "{":
                            vd += 1
                        elif body[vp] == "}":
                            vd -= 1
                        vp += 1
                    fields[field_name] = body[val_start + 1 : vp - 1].strip()
                elif val_start < len(body):
                    end = body.find(",", val_start)
                    if end == -1:
                        end = len(body)
                    fields[field_name] = body[val_start:end].strip().strip('"').strip("'")
            entries[key] = fields
            entry_types[key] = m.group(1)

        if not entries:
            findings.append(
                {
                    "code": "no_entries",
                    "severity": "error",
                    "message": "No BibTeX entries found.",
                    "artifact": bib_path,
                }
            )
        else:
            # Delegate to domain validator
            findings.extend(validate_bibliography(entries, entry_types))

        status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
        return ValidatorResult(
            validator="bibliography",
            status=status,
            summary="normalization skipped / builtin validation used",
            findings=findings,
            artifacts_checked=[bib_path],
        )

    def _parse_bibtex_tidy_errors(self, stderr: str, bib_path: str) -> list[dict[str, Any]]:
        """Parse bibtex-tidy stderr into structured findings."""
        findings: list[dict[str, Any]] = []
        for line in stderr.strip().splitlines():
            line = line.strip()
            if line:
                findings.append(
                    {
                        "code": "bibtex_tidy_error",
                        "severity": "error",
                        "message": line,
                        "artifact": bib_path,
                    }
                )
        if not findings:
            findings.append(
                {
                    "code": "bibtex_tidy_error",
                    "severity": "error",
                    "message": "bibtex-tidy exited non-zero but produced no error output.",
                    "artifact": bib_path,
                }
            )
        return findings
