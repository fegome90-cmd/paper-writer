"""Ethics audit wrapper.

Audits manuscript for AI disclosure compliance. Returns structured
findings for the ethics_passed soft gate.
"""

from pathlib import Path
from typing import Any

from integrations.tools.base import ToolWrapper, ValidatorResult
from validators.style import validate_style


class StyleAuditToolWrapper(ToolWrapper):
    """Audits manuscript style (passive voice, long sentences, strong claims, etc.).

    Delegates to validators.style.validate_style() for pure domain logic.
    """

    @property
    def name(self) -> str:
        return "style-auditor"

    @property
    def gate(self) -> str:
        return "style_passed"

    def is_available(self) -> bool:
        """Pure Python — always available."""
        return True

    def run(self, artifacts: dict[str, Any], context: dict[str, Any]) -> ValidatorResult:
        manuscript_files = artifacts.get("manuscript_files", [])
        artifacts_checked: list[str] = []
        all_findings: list[dict[str, Any]] = []

        for mf in manuscript_files:
            mf_path = Path(mf)
            if not mf_path.is_file():
                continue
            artifacts_checked.append(str(mf_path))
            content = mf_path.read_text(encoding="utf-8", errors="replace")
            findings = validate_style(content, file_label=str(mf_path))
            all_findings.extend(findings)

        status = "fail" if any(f["severity"] == "error" for f in all_findings) else "pass"

        error_count = sum(1 for f in all_findings if f["severity"] == "error")
        warning_count = sum(1 for f in all_findings if f["severity"] == "warning")

        summary = (
            "Style audit passed."
            if status == "pass"
            else f"Style audit found {error_count} error(s), {warning_count} warning(s)."
        )

        return ValidatorResult(
            validator="style",
            status=status,
            summary=summary,
            findings=all_findings,
            artifacts_checked=artifacts_checked,
        )
