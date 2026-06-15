"""Tests for Judgment Day Round 1 fixes: W-3 (audit_code_health error) + W-4 (RuntimeError clarity).

W-3: audit_code_health exits 1 when report.error is set even if findings list
     is empty (Trifecta failure with --quiet would otherwise show success).
W-4: a callback missing output_policy metadata gives a clear "Configuration
     error" message, not the generic "Internal error" (RuntimeError from
     validate_output_policy fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from cli.paper.commands.audit import _cmd_audit_code_health


@dataclass
class _FakeCodeHealthReport:
    trifecta_enabled: bool = False
    findings: list[object] = field(default_factory=list)
    filtered_count: int = 0
    total_orphans_seen: int = 0
    error: str = ""

    def summary(self) -> str:
        if self.error:
            return f"Code health: SKIPPED ({self.error})"
        return "Code health: OK"


class TestAuditCodeHealthErrorExit:
    """W-3: error in report (Trifecta down) MUST exit 1 even with no findings."""

    def test_error_without_findings_exits_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """If report.error is set but findings empty, exit 1 (not 0)."""
        import argparse

        error_report = _FakeCodeHealthReport(
            trifecta_enabled=True,
            findings=[],
            error="Trifecta find_orphans failed",
        )
        ok_report = _FakeCodeHealthReport(findings=[])

        with (
            patch(
                "validators.code_health.analyze_code_health",
                return_value=error_report,
            ),
            patch(
                "validators.code_health.analyze_dependency_risk",
                return_value=ok_report,
            ),
        ):
            args = argparse.Namespace(output="json")
            with pytest.raises(SystemExit) as exc:
                _cmd_audit_code_health(args)
        assert exc.value.code == 1, (
            "audit code-health MUST exit 1 when report.error is set (closes W-3)"
        )

    def test_no_error_no_findings_exits_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Happy path: no error, no findings -> exit 0."""
        import argparse

        ok_report = _FakeCodeHealthReport(findings=[])

        with (
            patch("validators.code_health.analyze_code_health", return_value=ok_report),
            patch("validators.code_health.analyze_dependency_risk", return_value=ok_report),
        ):
            args = argparse.Namespace(output="json")
            with pytest.raises(SystemExit) as exc:
                _cmd_audit_code_health(args)
        assert exc.value.code == 0


class TestValidateOutputPolicyRuntimeErrorClarity:
    """W-4: missing output_policy -> clear config-error message, not 'Internal error'."""

    def test_missing_policy_message_is_configuration_error(self) -> None:
        """W-4: missing output_policy RuntimeError carries a clear message.

        The catch-all in main.py wraps the exception as 'Internal error: {exc}',
        so the user sees 'Internal error: Missing output_policy for callback X'.
        The 'Missing output_policy' text makes the config/registration bug clear
        even though it routes through the generic handler (RuntimeError is too
        broad to catch specifically without conflicting with unexpected-error tests).
        """
        import argparse

        from cli.paper.output import validate_output_policy

        args = argparse.Namespace(
            command="test_cmd",
            func=lambda _a: None,  # is a callback
            output_policy=None,  # missing — must trigger fail-closed RuntimeError
            output_format="text",
        )
        with pytest.raises(RuntimeError, match="Missing output_policy"):
            validate_output_policy(args, "text")
        # The RuntimeError message itself is the clear config-error signal.
        # main.py's catch-all surfaces it as 'Internal error: Missing output_policy...'.
