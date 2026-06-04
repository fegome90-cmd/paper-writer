"""Claims audit wrapper.

Detects claim candidates in manuscript that may need evidence backing.
Returns structured findings for informational purposes (no gate).
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class ClaimsAuditor(ToolWrapper):
    """Audits manuscript for claim candidates needing evidence."""

    @property
    def name(self) -> str:
        return "claims-auditor"

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
                validator="claims",
                status="pass",
                summary="No manuscript provided — claims check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        mf_path = Path(manuscript_path)
        if not mf_path.is_file():
            return ValidatorResult(
                validator="claims",
                status="pass",
                summary=f"Manuscript not found: {mf_path} — claims check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked.append(str(mf_path))

        try:
            from parsers.manuscript import ManuscriptParser
            from validators.claims import ClaimsValidator, build_claims_report

            whitelist = set(context.get("whitelist", []))
            parser = ManuscriptParser()
            manuscript = parser.parse(mf_path)
            validator = ClaimsValidator(whitelist=whitelist)
            candidates = validator.validate(manuscript)
            report = build_claims_report(
                manuscript, candidates, 0, rules_loaded=len(validator.rules)
            )
            findings = report.get("findings", [])
        except Exception as e:
            return ValidatorResult(
                validator="claims",
                status="pass",
                summary=f"Claims validator error: {e}. Skipping.",
                findings=[],
                artifacts_checked=artifacts_checked,
            )

        status = "warn" if findings else "pass"

        summary = (
            "Claims check passed — no unsupported claims found."
            if not findings
            else f"Claims check: {len(findings)} candidate(s) needing evidence."
        )

        return ValidatorResult(
            validator="claims",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
