"""Reference consistency validator.

Checks that inline citation keys in manuscript files map to entries
in references.bib. Returns structured findings for the gate system.
"""

import re
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.citations import validate_citation_consistency


class RefsValidator(ToolWrapper):
    """Validates that all inline citations resolve to bibliography entries.

    Checks manuscript draft files for \\cite{key} / @key patterns and
    verifies each key exists in references.bib.
    """

    @property
    def name(self) -> str:
        return "refs-validator"

    @property
    def gate(self) -> str:
        return "citations_resolved"

    def is_available(self) -> bool:
        """Pure Python — always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        bib_path = artifacts.get("bibliography")
        manuscript_files = artifacts.get("manuscript_files", [])

        if not bib_path:
            return ValidatorResult(
                validator="refs",
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
                validator="refs",
                status="fail",
                summary=f"Bibliography file not found: {bib_path}",
                findings=findings,
                artifacts_checked=artifacts_checked,
            )

        # Extract bib keys (I/O + parsing — wrapper responsibility)
        bib_keys = self._extract_bib_keys(bib_file)

        # Extract citation keys from manuscript files (I/O + parsing — wrapper responsibility)
        all_citation_keys: set[str] = set()
        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                continue
            artifacts_checked.append(str(mf_path))
            citation_keys = self._extract_citation_keys(mf_path)
            all_citation_keys.update(citation_keys)

        # Delegate validation logic to domain validator
        findings.extend(validate_citation_consistency(bib_keys, all_citation_keys))

        status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
        unresolved_count = len(all_citation_keys - bib_keys)
        summary = (
            f"All {len(all_citation_keys)} citations resolve."
            if status == "pass"
            else f"{unresolved_count} unresolved citation(s) out of {len(all_citation_keys)}."
        )

        return ValidatorResult(
            validator="refs",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )

    def _extract_bib_keys(self, bib_file: Path) -> set[str]:
        """Extract entry keys from a .bib file."""
        if not bib_file.is_file():
            return set()
        content = bib_file.read_text(encoding="utf-8", errors="replace")
        return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)", content, re.IGNORECASE))

    def _extract_citation_keys(self, manuscript_file: Path) -> set[str]:
        """Extract citation keys from a manuscript file."""
        content = manuscript_file.read_text(encoding="utf-8", errors="replace")
        keys: set[str] = set()
        # LaTeX-style: \cite{key1, key2}
        for match in re.finditer(r"\\cite\{([^}]+)\}", content):
            for k in match.group(1).split(","):
                keys.add(k.strip())
        # Markdown-style: [@key] or @key
        # BibTeX keys must contain at least one letter — filter out
        # pure-numeric keys (e.g. @1 from Pandoc/LLM auto-numbering)
        # and common false positives (email domains, social handles).
        _FALSE_POSITIVES = frozenset(
            {
                "example",
                "handle",
                "figure",
                "table",
                "section",
                "equation",
                "chapter",
                "appendix",
                "ref",
                "cite",
                "see",
                "email",
                "http",
                "https",
            }
        )
        for match in re.finditer(r"@(\w[\w\-]*)", content):
            candidate = match.group(1)
            # Skip pure-numeric keys (not valid BibTeX)
            if candidate.isdigit():
                continue
            # Skip known false positives
            if candidate.lower() in _FALSE_POSITIVES:
                continue
            # BibTeX keys must contain at least one letter
            if not any(c.isalpha() for c in candidate):
                continue
            keys.add(candidate)
        return keys
