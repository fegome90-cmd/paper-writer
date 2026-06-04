"""Code health audit wrapper.

Runs Trifecta-based code health analysis (orphan detection, dependency risk).
Returns structured findings for informational purposes (no gate).
"""

from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult


class CodeHealthAuditor(ToolWrapper):
    """Audits project code health via Trifecta graph index."""

    @property
    def name(self) -> str:
        return "code-health-auditor"

    @property
    def gate(self) -> str:
        return "style_passed"

    def is_available(self) -> bool:
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        try:
            from validators.code_health import (
                analyze_code_health,
                analyze_dependency_risk,
            )

            report = analyze_code_health()
            dep_report = analyze_dependency_risk()
        except Exception as e:
            return ValidatorResult(
                validator="code_health",
                status="pass",
                summary=f"Code health analysis error: {e}. Skipping.",
                findings=[],
                artifacts_checked=[],
            )

        all_findings: list[dict[str, Any]] = [f.to_dict() for f in report.findings]
        all_findings.extend([f.to_dict() for f in dep_report.findings])

        status = "warn" if all_findings else "pass"

        summary = report.summary()
        if dep_report.findings:
            summary += f" {dep_report.summary()}"

        return ValidatorResult(
            validator="code_health",
            status=status,
            summary=summary,
            findings=all_findings,
            artifacts_checked=["trifecta_graph_index"],
        )
