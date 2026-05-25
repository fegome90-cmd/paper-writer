"""Bibliography normalization wrapper.

Runs bibtex-tidy (or falls back to a built-in validator) to normalize
and validate the references.bib file. Returns structured findings
consumed by the gate system.
"""

import subprocess
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class BibliographyNormalizer(ToolWrapper):
    """Normalizes and validates the references.bib file.

    Uses bibtex-tidy if available. Falls back to a built-in syntax
    check that detects unclosed braces and malformed entries.
    """

    @property
    def name(self) -> str:
        return "bibtex-tidy"

    @property
    def gate(self) -> str:
        return "bib_normalized"

    def is_available(self) -> bool:
        """bibtex-tidy is optional — built-in fallback always exists."""
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

        # Try bibtex-tidy first
        try:
            result = subprocess.run(
                ["bibtex-tidy", str(bib_file), "--modify", "--sort"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return ValidatorResult(
                    validator="bibliography",
                    status="fail",
                    summary="bibtex-tidy reported errors.",
                    findings=self._parse_bibtex_tidy_errors(result.stderr, bib_path),
                    artifacts_checked=[bib_path],
                )
        except FileNotFoundError:
            # bibtex-tidy not installed — run built-in validation
            return self._builtin_validate(bib_file, bib_path)
        except (OSError, subprocess.SubprocessError) as e:
            return ValidatorResult(
                validator="bibliography",
                status="fail",
                summary=f"bibtex-tidy execution failed: {e}",
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

        return ValidatorResult(
            validator="bibliography",
            status="pass",
            summary="Bibliography normalized successfully.",
            findings=[],
            artifacts_checked=[bib_path],
        )

    def _builtin_validate(self, bib_file: Path, bib_path: str) -> ValidatorResult:
        """Built-in BibTeX validation when bibtex-tidy is not available."""
        findings: list[dict[str, Any]] = []
        content = bib_file.read_text(encoding="utf-8", errors="replace")

        if not content.strip():
            findings.append(
                {
                    "code": "empty_file",
                    "severity": "error",
                    "message": "Bibliography file is empty.",
                    "artifact": bib_path,
                }
            )
        else:
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

            # Check for @type{ entries
            import re

            entries = re.findall(r"@(\w+)\s*\{", content, re.IGNORECASE)
            if not entries:
                findings.append(
                    {
                        "code": "no_entries",
                        "severity": "error",
                        "message": "No BibTeX entries found.",
                        "artifact": bib_path,
                    }
                )

        status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
        return ValidatorResult(
            validator="bibliography",
            status=status,
            summary="Built-in BibTeX validation complete (bibtex-tidy not installed).",
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
