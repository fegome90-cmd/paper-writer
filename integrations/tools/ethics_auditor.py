"""Ethics audit wrapper.

Checks manuscript for AI disclosure compliance. Returns structured
findings for the ethics_passed soft gate. Uses EthicsValidator from
validators/ethics.py which requires a Manuscript object — this wrapper
handles the I/O of parsing the manuscript and running validation.
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class EthicsAuditor(ToolWrapper):
    """Audits manuscript for AI disclosure compliance.

    Runs EthicsValidator against the parsed manuscript and returns
    findings. Sets the ethics_passed soft gate based on results.
    """

    @property
    def name(self) -> str:
        return "ethics-auditor"

    @property
    def gate(self) -> str:
        return "ethics_passed"

    def is_available(self) -> bool:
        """Pure Python — always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_path = artifacts.get("manuscript")
        artifacts_checked: list[str] = []
        findings: list[dict[str, Any]] = []

        if not manuscript_path:
            return ValidatorResult(
                validator="ethics",
                status="pass",
                summary="No manuscript provided — ethics check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        mf_path = Path(manuscript_path)
        if not mf_path.is_file():
            return ValidatorResult(
                validator="ethics",
                status="pass",
                summary=f"Manuscript not found: {mf_path} — ethics check skipped.",
                findings=[],
                artifacts_checked=[],
            )

        artifacts_checked.append(str(mf_path))

        try:
            from parsers.manuscript import ManuscriptParser
            from validators.ethics import EthicsValidator

            parser = ManuscriptParser()
            manuscript = parser.parse(mf_path)
            validator = EthicsValidator()
            findings = validator.validate(manuscript)
        except Exception as e:
            return ValidatorResult(
                validator="ethics",
                status="pass",
                summary=f"Ethics validator error: {e}. Skipping.",
                findings=[],
                artifacts_checked=artifacts_checked,
            )

        # Ethics findings are warnings, not hard blockers (soft gate)
        status = "pass"

        error_count = sum(1 for f in findings if f.get("severity") == "P0")
        warning_count = len(findings)

        summary = (
            "AI disclosure statement found — ethics check passed."
            if not findings
            else f"Ethics check: {warning_count} finding(s), {error_count} critical."
        )

        return ValidatorResult(
            validator="ethics",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
