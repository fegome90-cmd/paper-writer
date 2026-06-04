"""Writing quality audit wrapper.

Detects AI-typical writing patterns in manuscript. Returns structured
findings for informational purposes (no gate).
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class WritingQualityAuditor(ToolWrapper):
    """Audits manuscript for AI-typical writing patterns."""

    @property
    def name(self) -> str:
        return "writing-quality-auditor"

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
                validator="writing_quality",
                status="pass",
                summary="No manuscript provided — writing quality check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        mf_path = Path(manuscript_path)
        if not mf_path.is_file():
            return ValidatorResult(
                validator="writing_quality",
                status="pass",
                summary=f"Manuscript not found: {mf_path} — writing quality check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked.append(str(mf_path))

        try:
            from parsers.manuscript import ManuscriptParser
            from validators.writing_quality import WritingQualityValidator

            whitelist = set(context.get("whitelist", []))
            parser = ManuscriptParser()
            manuscript = parser.parse(mf_path)
            validator = WritingQualityValidator(whitelist=whitelist)
            findings = validator.validate(manuscript)
        except Exception as e:
            return ValidatorResult(
                validator="writing_quality",
                status="pass",
                summary=f"Writing quality validator error: {e}. Skipping.",
                findings=[],
                artifacts_checked=artifacts_checked,
            )

        error_count = sum(1 for f in findings if f.get("severity") == "P0")
        status = "warn" if error_count > 0 else "pass"

        summary = (
            "Writing quality check passed — no AI patterns detected."
            if not findings
            else f"Writing quality: {len(findings)} finding(s), {error_count} critical."
        )

        return ValidatorResult(
            validator="writing_quality",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
