"""CLI integration tests for `paper audit ethics`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURE_NO_DISCLOSURE = (
    Path(__file__).resolve().parent.parent / "fixtures" / "manuscript_without_ai_disclosure.md"
)
FIXTURE_WITH_DISCLOSURE = (
    Path(__file__).resolve().parent.parent / "fixtures" / "manuscript_with_fabricated_citations.md"
)


class TestAuditEthicsCLI:
    def test_missing_ai_disclosure_finds_p0(self):
        """Manuscript without AI disclosure should produce P0 finding."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.paper.main",
                "audit",
                "ethics",
                "--output",
                "json",
                str(FIXTURE_NO_DISCLOSURE),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1, f"Expected exit 1 for P0, got {result.returncode}"
        data = json.loads(result.stdout)
        assert data["command"] == "audit_ethics"
        assert len(data["findings"]) > 0
        p0_findings = [f for f in data["findings"] if f["severity"] == "P0"]
        assert len(p0_findings) > 0
        assert p0_findings[0]["rule_id"] == "ethics.missing_ai_disclosure"

    def test_with_ai_disclosure_passes(self):
        """Manuscript with AI disclosure should pass (no P0 findings)."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.paper.main",
                "audit",
                "ethics",
                "--output",
                "json",
                str(FIXTURE_WITH_DISCLOSURE),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        data = json.loads(result.stdout)
        p0_findings = [f for f in data["findings"] if f["severity"] == "P0"]
        assert len(p0_findings) == 0

    def test_json_output_structure(self):
        """JSON output should have required keys."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.paper.main",
                "audit",
                "ethics",
                "--output",
                "json",
                str(FIXTURE_NO_DISCLOSURE),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert "command" in data
        assert "file" in data
        assert "findings" in data
        assert "summary" in data
        assert "total_findings" in data["summary"]

    def test_terminal_output(self):
        """Terminal output should produce non-empty output."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.paper.main",
                "audit",
                "ethics",
                "--output",
                "terminal",
                str(FIXTURE_NO_DISCLOSURE),
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1
        assert len(result.stdout) > 0

    def test_missing_file_exits_1(self):
        """Non-existent file should exit with code 1."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.paper.main",
                "audit",
                "ethics",
                "--output",
                "json",
                "/tmp/nonexistent.md",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1
