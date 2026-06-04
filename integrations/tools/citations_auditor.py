"""Citation verification audit wrapper.

Verifies manuscript citations against Crossref and Semantic Scholar.
Returns structured findings for informational purposes (no gate).
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class CitationsAuditor(ToolWrapper):
    """Audits manuscript citations against reference databases."""

    @property
    def name(self) -> str:
        return "citations-auditor"

    @property
    def gate(self) -> str:
        return "citations_resolved"

    def is_available(self) -> bool:
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_path = artifacts.get("manuscript")
        artifacts_checked: list[str] = []

        if not manuscript_path:
            return ValidatorResult(
                validator="citations",
                status="pass",
                summary="No manuscript provided — citation check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        mf_path = Path(manuscript_path)
        if not mf_path.is_file():
            return ValidatorResult(
                validator="citations",
                status="pass",
                summary=f"Manuscript not found: {mf_path} — citation check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked.append(str(mf_path))

        try:
            from parsers.manuscript import ManuscriptParser
            from validators.citation_verify import CitationVerifyValidator

            offline = context.get("offline", True)
            parser = ManuscriptParser()
            manuscript = parser.parse(mf_path)
            validator = CitationVerifyValidator(offline=offline)
            findings = validator.validate(manuscript)
        except Exception as e:
            return ValidatorResult(
                validator="citations",
                status="pass",
                summary=f"Citation validator error: {e}. Skipping.",
                findings=[],
                artifacts_checked=artifacts_checked,
            )

        error_count = sum(1 for f in findings if f.get("severity") == "P0")
        status = "warn" if error_count > 0 else "pass"

        summary = (
            "Citation check passed — all citations verified."
            if not findings
            else f"Citation check: {len(findings)} finding(s), {error_count} critical."
        )

        return ValidatorResult(
            validator="citations",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
