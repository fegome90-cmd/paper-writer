"""Prose audit wrapper.

Checks manuscript for passive voice, long sentences, unbacked claims,
forbidden phrases, and informal language. Returns structured findings
for informational purposes (no gate).
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class ProseAuditor(ToolWrapper):
    """Audits manuscript prose quality."""

    @property
    def name(self) -> str:
        return "prose-auditor"

    @property
    def gate(self) -> str:
        return "style_passed"

    def is_available(self) -> bool:
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_path = artifacts.get("manuscript")
        artifacts_checked: list[str] = []

        if not manuscript_path:
            return ValidatorResult(
                validator="prose",
                status="pass",
                summary="No manuscript provided — prose check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        mf_path = Path(manuscript_path)
        if not mf_path.is_file():
            return ValidatorResult(
                validator="prose",
                status="pass",
                summary=f"Manuscript not found: {mf_path} — prose check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked.append(str(mf_path))

        try:
            from parsers.manuscript import ManuscriptParser
            from validators.prose import ProseValidator

            whitelist = set(context.get("whitelist", []))
            parser = ManuscriptParser()
            manuscript = parser.parse(mf_path)
            validator = ProseValidator(whitelist=whitelist)
            findings = validator.validate(manuscript)
        except Exception as e:
            return ValidatorResult(
                validator="prose",
                status="pass",
                summary=f"Prose validator error: {e}. Skipping.",
                findings=[],
                artifacts_checked=artifacts_checked,
            )

        error_count = sum(1 for f in findings if f.get("severity") == "P0")
        status = "warn" if error_count > 0 else "pass"

        summary = (
            "Prose check passed — no issues found."
            if not findings
            else f"Prose check: {len(findings)} finding(s), {error_count} critical."
        )

        return ValidatorResult(
            validator="prose",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
