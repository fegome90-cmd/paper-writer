"""Style linting wrapper.

Runs Vale (or built-in prose checks) against manuscript drafts.
Returns structured findings for the style_passed gate.
"""

import re
from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class StyleLinter(ToolWrapper):
    """Lints manuscript prose for style issues.

    Uses Vale if installed, otherwise runs built-in checks for
    passive voice, long sentences, and common issues.
    """

    @property
    def name(self) -> str:
        return "vale"

    @property
    def gate(self) -> str:
        return "style_passed"

    def is_available(self) -> bool:
        """Built-in fallback always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_files = artifacts.get("manuscript_files", [])

        if not manuscript_files:
            return ValidatorResult(
                validator="style",
                status="pass",
                summary="No manuscript files to lint.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked: list[str] = []
        findings: list[dict[str, Any]] = []

        # Try Vale first
        vale_available = self._vale_available()

        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                continue
            artifacts_checked.append(str(mf_path))

            if vale_available:
                findings.extend(self._run_vale(mf_path))
            else:
                findings.extend(self._builtin_lint(mf_path))

        errors = [f for f in findings if f["severity"] == "error"]
        warnings = [f for f in findings if f["severity"] == "warning"]

        if errors:
            status = "fail"
        elif warnings:
            status = "warn"
        else:
            status = "pass"

        tool_label = "Vale" if vale_available else "built-in linter"
        summary = (
            f"Style check passed ({tool_label})."
            if status == "pass"
            else (
                f"Style check found {len(errors)} error(s),"
                f" {len(warnings)} warning(s) ({tool_label})."
            )
        )

        return ValidatorResult(
            validator="style",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )

    def _vale_available(self) -> bool:
        """Check if Vale CLI is installed."""
        import subprocess

        try:
            result = subprocess.run(
                ["vale", "--version"], capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, Exception):
            return False

    def _run_vale(self, file_path: Path) -> list[dict[str, Any]]:
        """Run Vale and parse JSON output into findings."""
        import json
        import subprocess

        findings: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                ["vale", "--output=JSON", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout.strip():
                data = json.loads(result.stdout)
                for _filepath, alerts in data.items():
                    for alert in alerts:
                        severity = "warning" if alert.get("Severity") == "warning" else "error"
                        findings.append(
                            {
                                "code": alert.get("Check", "vale"),
                                "severity": severity,
                                "message": alert.get("Message", "Unknown style issue"),
                                "artifact": str(file_path),
                                "location": f"line {alert.get('Line', '?')}",
                            }
                        )
        except (json.JSONDecodeError, Exception):
            # Vale failed — fall back to built-in
            findings.extend(self._builtin_lint(file_path))
        return findings

    def _builtin_lint(self, file_path: Path) -> list[dict[str, Any]]:
        """Built-in prose checks when Vale is not available."""
        findings: list[dict[str, Any]] = []
        content = file_path.read_text(encoding="utf-8", errors="replace")

        # Check for passive voice patterns
        passive_patterns = [
            (r"\bwas\s+\w+ed\b", "passive_voice"),
            (r"\bwere\s+\w+ed\b", "passive_voice"),
            (r"\bis\s+\w+ed\b", "passive_voice"),
            (r"\bare\s+\w+ed\b", "passive_voice"),
            (r"\bbeen\s+\w+ed\b", "passive_voice"),
        ]
        for pattern, code in passive_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[: match.start()].count("\n") + 1
                findings.append(
                    {
                        "code": code,
                        "severity": "warning",
                        "message": f"Possible passive voice: '{match.group()}'",
                        "artifact": str(file_path),
                        "location": f"line {line_num}",
                    }
                )

        # Check for very long sentences (>40 words)
        sentences = re.split(r"[.!?]+", content)
        for sentence in sentences:
            words = sentence.split()
            if len(words) > 40:
                findings.append(
                    {
                        "code": "long_sentence",
                        "severity": "warning",
                        "message": f"Sentence has {len(words)} words (max 40 recommended).",
                        "artifact": str(file_path),
                    }
                )

        return findings
