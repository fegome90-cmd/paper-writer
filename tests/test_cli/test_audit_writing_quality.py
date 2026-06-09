"""CLI integration tests for `paper audit writing-quality`."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "manuscript_with_ai_terms.md"


class TestAuditWritingQualityCLI:
    def test_detects_ai_typical_terms(self):
        """Fixture has 'delve', 'tapestry', 'robust' — should produce findings."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        # CLI exits 1 only for P0 — writing-quality produces P1/P2, so exit 0
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"
        data = json.loads(result.stdout)
        assert data["command"] == "audit_writing_quality"
        assert len(data["findings"]) > 0
        # Should find at least delve, tapestry, robust
        rule_ids = {f["rule_id"] for f in data["findings"]}
        assert "writing_quality.ai_typical.delve" in rule_ids
        assert "writing_quality.ai_typical.tapestry" in rule_ids

    def test_whitelist_excludes_terms(self):
        """Whitelist should exclude specified terms from detection."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--whitelist", "delve", "--whitelist", "tapestry",
             "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 0 or result.returncode == 1
        data = json.loads(result.stdout)
        rule_ids = {f["rule_id"] for f in data["findings"]}
        assert "writing_quality.ai_typical.delve" not in rule_ids
        assert "writing_quality.ai_typical.tapestry" not in rule_ids

    def test_json_output_structure(self):
        """JSON output should have required keys."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        data = json.loads(result.stdout)
        assert "command" in data
        assert "file" in data
        assert "findings" in data
        assert "summary" in data
        assert "total_findings" in data["summary"]
        assert "by_severity" in data["summary"]

    def test_terminal_output(self):
        """Terminal output should produce non-empty output."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--output", "terminal", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert len(result.stdout) > 0

    def test_missing_file_exits_1(self):
        """Non-existent file should exit with code 1."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--output", "json", "/tmp/nonexistent.md"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        assert result.returncode == 1

    def test_severity_by_section(self):
        """'robust' in abstract should be P1, not P2."""
        result = subprocess.run(
            [sys.executable, "-m", "cli.paper.main", "audit", "writing-quality",
             "--output", "json", str(FIXTURE)],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent),
        )
        data = json.loads(result.stdout)
        # Find robust findings in abstract
        robust_abstract = [
            f for f in data["findings"]
            if f["rule_id"] == "writing_quality.ai_typical.robust"
            and f.get("section") == "abstract"
        ]
        for f in robust_abstract:
            assert f["severity"] == "P1", f"robust in abstract should be P1, got {f['severity']}"
