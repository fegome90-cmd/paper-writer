"""Reporting audit wrapper.

Audits manuscript against reporting guidelines (STROBE, CONSORT, PRISMA
as applicable). Returns structured findings for the reporting_passed gate.
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.reporting import validate_reporting
from validators.structure import validate_section_structure


class ReportingAuditor(ToolWrapper):
    """Audits manuscript structure against reporting checklist requirements.

    Checks for presence of required manuscript sections and basic
    reporting elements. Falls back gracefully when external tools
    are unavailable.
    """

    @property
    def name(self) -> str:
        return "reporting-auditor"

    @property
    def gate(self) -> str:
        return "reporting_passed"

    def is_available(self) -> bool:
        """Pure Python — always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_files = artifacts.get("manuscript_files", [])
        outline_file = artifacts.get("outline")

        artifacts_checked: list[str] = []
        io_findings: list[dict[str, Any]] = []
        sections: dict[str, str] = {}

        # Read manuscript files (I/O — wrapper responsibility)
        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                io_findings.append(
                    {
                        "code": "section_missing",
                        "severity": "error",
                        "message": f"Required section file not found: {mf}",
                        "artifact": mf,
                    }
                )
                continue
            artifacts_checked.append(str(mf_path))
            section_name = mf_path.stem.lower()
            content = mf_path.read_text(encoding="utf-8", errors="replace")
            sections[section_name] = content

        # Check outline if provided
        if outline_file:
            outline_path = Path(outline_file)
            if outline_path.is_file():
                artifacts_checked.append(str(outline_path))

        # Delegate validation logic to domain validators
        reporting_findings = validate_reporting(sections) if sections else []
        structure_findings = validate_section_structure(list(sections.keys()))

        # Combine all findings
        findings = io_findings + reporting_findings + structure_findings

        # Status from I/O and reporting findings (structure findings are advisory)
        gating_findings = io_findings + reporting_findings
        status = "fail" if any(f["severity"] == "error" for f in gating_findings) else "pass"

        error_count = sum(1 for f in gating_findings if f["severity"] == "error")
        warning_count = sum(1 for f in gating_findings if f["severity"] == "warning")

        summary = (
            "Reporting audit passed."
            if status == "pass"
            else f"Reporting audit found {error_count} error(s), {warning_count} warning(s)."
        )

        return ValidatorResult(
            validator="reporting",
            status=status,
            summary=summary,
            findings=findings,
            artifacts_checked=artifacts_checked,
        )
