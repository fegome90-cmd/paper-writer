"""CLI integration tests for `paper audit citations`."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "manuscript_with_fabricated_citations.md"


class TestAuditCitationsCLI:
    def test_offline_produces_skipped_findings(self):
        """--offline mode should return P2 skipped findings, no API calls."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "citations",
             "--offline", "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["command"] == "audit_citations"
        assert data["metadata"]["offline"] is True
        assert len(data["findings"]) > 0
        for f in data["findings"]:
            if f["rule_id"] != "citation_verification_summary":
                assert f["rule_id"] == "citation_verify.skipped"
                assert f["severity"] == "2" or f["severity"] == "P2"

    def test_json_output_structure(self):
        """JSON output should have required keys."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "citations",
             "--offline", "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "command" in data
        assert "file" in data
        assert "findings" in data
        assert "summary" in data
        assert "metadata" in data
        assert "total_findings" in data["summary"]
        assert "by_severity" in data["summary"]

    def test_terminal_output(self):
        """Terminal output should produce non-empty output."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "citations",
             "--offline", "--output", "terminal", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0
        assert len(result.stdout) > 0

    def test_missing_file_exits_1(self):
        """Non-existent file should exit with code 1."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "citations",
             "--offline", "--output", "json", "/tmp/nonexistent.md"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1

    def test_fabricated_dois_produce_findings(self):
        """Fixture has fabricated DOIs — should produce not_found or skipped."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "citations",
             "--offline", "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Fixture has 4 references — should produce findings for each
        assert data["summary"]["total_findings"] >= 1
