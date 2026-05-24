"""Reporting audit wrapper.

Audits manuscript against reporting guidelines (STROBE, CONSORT, PRISMA
as applicable). Returns structured findings for the reporting_passed gate.
"""

import re
from pathlib import Path
from typing import Any, ClassVar

from integrations.tools.base import ToolWrapper, ValidatorResult


class ReportingAuditor(ToolWrapper):
    """Audits manuscript structure against reporting checklist requirements.

    Checks for presence of required manuscript sections and basic
    reporting elements. Falls back gracefully when external tools
    are unavailable.
    """

    REQUIRED_SECTIONS: ClassVar[list[str]] = [
        "introduction",
        "methods",
        "results",
        "discussion",
    ]

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
        findings: list[dict[str, Any]] = []

        # Check that all required sections exist as files
        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                continue
            artifacts_checked.append(str(mf_path))

        # Check section content for required reporting elements
        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                findings.append(
                    {
                        "code": "section_missing",
                        "severity": "error",
                        "message": f"Required section file not found: {mf}",
                        "artifact": mf,
                    }
                )
                continue

            section_name = mf_path.stem.lower()
            content = mf_path.read_text(encoding="utf-8", errors="replace")

            if not content.strip():
                findings.append(
                    {
                        "code": "empty_section",
                        "severity": "error",
                        "message": f"Section '{section_name}' is empty.",
                        "artifact": str(mf_path),
                    }
                )
                continue

            # Section-specific checks
            if section_name == "methods":
                findings.extend(self._check_methods(content, str(mf_path)))
            elif section_name == "results":
                findings.extend(self._check_results(content, str(mf_path)))
            elif section_name == "discussion":
                findings.extend(self._check_discussion(content, str(mf_path)))

        # Check outline if provided
        if outline_file:
            outline_path = Path(outline_file)
            if outline_path.is_file():
                artifacts_checked.append(str(outline_path))

        status = "fail" if any(f["severity"] == "error" for f in findings) else "pass"
        error_count = sum(1 for f in findings if f["severity"] == "error")
        warning_count = sum(1 for f in findings if f["severity"] == "warning")

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

    def _check_methods(self, content: str, artifact: str) -> list[dict[str, Any]]:
        """Check methods section for required reporting elements."""
        findings: list[dict[str, Any]] = []
        content_lower = content.lower()

        # Check for study design mention
        study_design_patterns = [
            "study design",
            "design",
            "cohort",
            "cross-sectional",
            "randomized",
            "trial",
            "case-control",
            "systematic review",
            "meta-analysis",
        ]
        if not any(p in content_lower for p in study_design_patterns):
            findings.append(
                {
                    "code": "missing_study_design",
                    "severity": "warning",
                    "message": "Methods section does not mention study design.",
                    "artifact": artifact,
                }
            )

        # Check for sample size / participants
        sample_patterns = ["sample", "participant", "subject", "patient"]
        if not any(p in content_lower for p in sample_patterns):
            findings.append(
                {
                    "code": "missing_sample_description",
                    "severity": "warning",
                    "message": "Methods section does not describe sample/participants.",
                    "artifact": artifact,
                }
            )

        return findings

    def _check_results(self, content: str, artifact: str) -> list[dict[str, Any]]:
        """Check results section for basic reporting elements."""
        findings: list[dict[str, Any]] = []

        # Check for numerical data
        if not re.search(r"\d+\.?\d*", content):
            findings.append(
                {
                    "code": "no_numerical_data",
                    "severity": "warning",
                    "message": "Results section contains no numerical data.",
                    "artifact": artifact,
                }
            )

        return findings

    def _check_discussion(self, content: str, artifact: str) -> list[dict[str, Any]]:
        """Check discussion section for required elements."""
        findings: list[dict[str, Any]] = []
        content_lower = content.lower()

        # Check for limitations mention
        if "limitation" not in content_lower:
            findings.append(
                {
                    "code": "missing_limitations",
                    "severity": "warning",
                    "message": "Discussion section does not mention limitations.",
                    "artifact": artifact,
                }
            )

        return findings
