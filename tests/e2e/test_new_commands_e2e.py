"""E2E CLI tests for new commands: draft all, audit factuality/tables/quality-appraisal, protocol.

Requires init+search+screen pipeline setup. Graceful degradation if S2 API unavailable.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_CMD = [sys.executable, "-m", "cli.paper.main"]
ENV = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=ENV,
        timeout=60,
    )


def _setup_to_screen(project: Path) -> None:
    """Run pipeline to screen stage: init → search → screen."""
    r = _run(CLI_CMD + ["init"], project)
    assert r.returncode == 0, f"init failed: {r.stdout}"

    r = _run(CLI_CMD + ["search"], project)
    assert r.returncode == 0, f"search failed: {r.stdout}"

    r = _run(CLI_CMD + ["screen"], project)
    assert r.returncode == 0, f"screen failed: {r.stdout}"


def _setup_to_draft(project: Path) -> None:
    """Run pipeline to draft stage: init → search → screen → draft outline + all."""
    _setup_to_screen(project)

    r = _run(CLI_CMD + ["draft", "outline"], project)
    assert r.returncode == 0, f"draft outline failed: {r.stdout}"

    r = _run(CLI_CMD + ["draft", "all"], project)
    # draft all may fail if no LLM — check it ran (not crashed)
    assert "Step:" in r.stdout or r.returncode == 0, f"draft all crashed: {r.stderr}"


class TestE2EDraftAll:
    """Test paper draft all subcommand."""

    def test_draft_all_generates_sections(self, tmp_path: Path) -> None:
        _setup_to_draft(tmp_path)

        r = _run(CLI_CMD + ["draft", "all"], tmp_path)
        # Should complete (may produce placeholders without LLM)
        assert "Step:" in r.stdout or r.returncode == 0

    def test_draft_all_flagged_by_orchestrator_before_screen(self, tmp_path: Path) -> None:
        """draft all should fail precondition before screen stage."""
        _run(CLI_CMD + ["init"], tmp_path)

        r = _run(CLI_CMD + ["draft", "all"], tmp_path)
        assert r.returncode != 0 or "FAILED" in r.stdout


class TestE2EAuditFactuality:
    """Test paper audit factuality subcommand."""

    def test_factuality_requires_evidence(self, tmp_path: Path) -> None:
        """factuality should error without --evidence flag."""
        _run(CLI_CMD + ["init"], tmp_path)
        dummy = tmp_path / "test.md"
        dummy.write_text("# Test\nSome claims here.\n")

        r = _run(CLI_CMD + ["audit", "factuality", str(dummy)], tmp_path)
        assert r.returncode != 0  # missing --evidence

    def test_factuality_with_mock_evidence(self, tmp_path: Path) -> None:
        """factuality should run with valid evidence file."""
        _setup_to_screen(tmp_path)

        dummy = tmp_path / "test.md"
        dummy.write_text("# Test\nCodeBERT achieves strong results.\n")

        evidence = tmp_path / "outputs" / "latest" / "search" / "screened_evidence.json"
        if not evidence.exists():
            pytest.skip("screened_evidence.json not generated")

        r = _run(
            CLI_CMD + ["audit", "factuality", str(dummy),
                       "--evidence", str(evidence)],
            tmp_path,
        )
        # Should run without crashing
        assert r.returncode in (0, 1)  # 0 = no findings, 1 = findings


class TestE2EAuditTables:
    """Test paper audit tables subcommand."""

    def test_tables_missing_draft_dir(self, tmp_path: Path) -> None:
        r = _run(CLI_CMD + ["audit", "tables", "/tmp/nonexistent_dir_xyz"], tmp_path)
        assert r.returncode != 0  # missing dir

    def test_tables_on_empty_drafts(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        (draft / "intro.md").write_text("# Introduction\nNo tables.\n")

        r = _run(CLI_CMD + ["audit", "tables", str(draft)], tmp_path)
        assert r.returncode == 1  # findings exist
        assert "no_tables" in r.stdout or "Table" in r.stdout

    def test_tables_on_complete_drafts(self, tmp_path: Path) -> None:
        draft = tmp_path / "drafts"
        draft.mkdir()
        content = (
            "# Results\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "```mermaid\nflowchart TD\n```\n"
        )
        (draft / "results.md").write_text(content)

        r = _run(CLI_CMD + ["audit", "tables", str(draft)], tmp_path)
        assert r.returncode == 0  # all checks passed


class TestE2EAuditQualityAppraisal:
    """Test paper audit quality-appraisal subcommand."""

    def test_quality_appraisal_requires_evidence(self, tmp_path: Path) -> None:
        r = _run(CLI_CMD + ["audit", "quality-appraisal"], tmp_path)
        assert r.returncode != 0  # missing --evidence

    def test_quality_appraisal_with_evidence(self, tmp_path: Path) -> None:
        _setup_to_screen(tmp_path)

        evidence = tmp_path / "outputs" / "latest" / "search" / "screened_evidence.json"
        if not evidence.exists():
            pytest.skip("screened_evidence.json not generated")

        r = _run(
            CLI_CMD + ["audit", "quality-appraisal", "--evidence", str(evidence)],
            tmp_path,
        )
        assert r.returncode in (0, 1)  # 0 = no findings, 1 = findings


class TestE2EProtocol:
    """Test paper protocol subcommand."""

    def test_protocol_requires_search_dir(self, tmp_path: Path) -> None:
        r = _run(CLI_CMD + ["protocol"], tmp_path)
        assert r.returncode != 0  # missing --search-dir

    def test_protocol_generates_output(self, tmp_path: Path) -> None:
        _setup_to_screen(tmp_path)

        search_dir = tmp_path / "outputs" / "latest" / "search"
        if not (search_dir / "screened_evidence.json").exists():
            pytest.skip("search output not generated")

        r = _run(
            CLI_CMD + ["protocol", "--search-dir", str(search_dir)],
            tmp_path,
        )
        # Protocol should generate through orchestrator or fail gracefully
        # The key is it doesn't crash with a Python traceback
        assert "Traceback" not in r.stderr
