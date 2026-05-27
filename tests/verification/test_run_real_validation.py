"""Tests for Phase 6 — Real Material Validation Runner.

Tests cover:
- Manifest loading and validation
- Workspace isolation
- Pipeline execution (mocked)
- Acceptance checks
- Verdict computation
- Report generation
- Source file validation (missing PDF produces clear error)
"""

from __future__ import annotations

import shutil
import textwrap
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from verification.run_real_validation import (
    VERDICT_DEGRADED,
    VERDICT_FAIL,
    VERDICT_MANUAL,
    VERDICT_PASS,
    StageResult,
    ValidationResult,
    check_acceptance,
    compute_verdict,
    generate_report,
    load_manifest,
    prepare_workspace,
    resolve_bib_path,
    run_stage,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

MINIMAL_MANIFEST = textwrap.dedent("""\
    schema_version: 1
    case_id: test-case
    title: Test Case
    source_material:
      pdf_path: /tmp/test.pdf
      source_url: ""
      sensitivity: public
      commit_to_repo: false
    stages:
      - name: doctor
        command: doctor
        args: []
        allow_degraded: false
        description: Check tools
    acceptance:
      pipeline_completed: true
    manual_review:
      required: true
      checklist:
        - item: "DOCX opens"
          category: render
""")


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    p = tmp_path / "test-case.local.yaml"
    p.write_text(MINIMAL_MANIFEST)
    return p


@pytest.fixture
def manifest_with_bib(tmp_path: Path) -> Path:
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{key, title={T}, year={2024}}")
    manifest_text = textwrap.dedent(f"""\
        schema_version: 1
        case_id: bib-case
        title: Bib Case
        source_material:
          pdf_path: /tmp/test.pdf
          source_url: ""
          sensitivity: public
          commit_to_repo: false
        bibliography:
          mode: required
          bib_path: {bib}
        stages:
          - name: import_bib
            command: import
            args: ["bib", "{{bib_path}}"]
            allow_degraded: false
            description: Import bib
        acceptance:
          pipeline_completed: true
        manual_review:
          required: false
          checklist: []
    """)
    p = tmp_path / "bib-case.local.yaml"
    p.write_text(manifest_text)
    return p


@pytest.fixture
def empty_result() -> ValidationResult:
    return ValidationResult(
        case_id="test-case",
        title="Test Case",
        manifest_path="/tmp/test.yaml",
        workspace="/tmp/ws",
    )


# ── Manifest loading ──────────────────────────────────────────────────────


class TestLoadManifest:
    def test_loads_valid_manifest(self, manifest_file: Path) -> None:
        data = load_manifest(manifest_file)
        assert data["case_id"] == "test-case"
        assert data["title"] == "Test Case"

    def test_missing_file_exits(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc_info:
            load_manifest(tmp_path / "nonexistent.yaml")
        assert exc_info.value.code == 2

    def test_missing_required_field_exits(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("schema_version: 1\n")
        with pytest.raises(SystemExit) as exc_info:
            load_manifest(bad)
        assert exc_info.value.code == 2

    def test_missing_pdf_path_exits(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(textwrap.dedent("""\
            schema_version: 1
            case_id: x
            title: X
            source_material:
              source_url: ""
            stages: []
        """))
        with pytest.raises(SystemExit) as exc_info:
            load_manifest(bad)
        assert exc_info.value.code == 2


class TestResolveBibPath:
    def test_skip_mode_returns_none(self) -> None:
        assert resolve_bib_path({"bibliography": {"mode": "skip"}}) is None

    def test_optional_empty_returns_none(self) -> None:
        assert resolve_bib_path({"bibliography": {"mode": "optional", "bib_path": ""}}) is None

    def test_optional_with_path_returns_path(self) -> None:
        result = resolve_bib_path({"bibliography": {"mode": "optional", "bib_path": "/a.bib"}})
        assert result == "/a.bib"

    def test_required_empty_exits(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            resolve_bib_path({"bibliography": {"mode": "required", "bib_path": ""}})
        assert exc_info.value.code == 2


# ── Workspace isolation ────────────────────────────────────────────────────


class TestPrepareWorkspace:
    def test_creates_workspace_dirs(self, manifest_file: Path, tmp_path: Path) -> None:
        manifest = load_manifest(manifest_file)
        ws = prepare_workspace(manifest, tmp_root=tmp_path)
        assert ws.exists()
        assert (ws / "outputs").exists()
        assert (ws / "outputs" / "drafts").exists()
        assert (ws / "outputs" / "render").exists()
        assert (ws / "outputs" / "state.yaml").exists()
        # Cleanup
        shutil.rmtree(ws, ignore_errors=True)

    def test_state_yaml_is_uninitialized(self, manifest_file: Path, tmp_path: Path) -> None:
        manifest = load_manifest(manifest_file)
        ws = prepare_workspace(manifest, tmp_root=tmp_path)
        state = yaml.safe_load((ws / "outputs" / "state.yaml").read_text())
        assert state["repo_initialized"] is False
        shutil.rmtree(ws, ignore_errors=True)

    def test_copies_templates_and_styles(self, manifest_file: Path, tmp_path: Path) -> None:
        manifest = load_manifest(manifest_file)
        ws = prepare_workspace(manifest, tmp_root=tmp_path)
        assert (ws / "templates").exists()
        assert (ws / "styles").exists()
        assert (ws / "skills").exists()
        shutil.rmtree(ws, ignore_errors=True)

    def test_venv_symlink(self, manifest_file: Path, tmp_path: Path) -> None:
        manifest = load_manifest(manifest_file)
        ws = prepare_workspace(manifest, tmp_root=tmp_path)
        venv_link = ws / ".venv"
        # If .venv exists in repo, it should be symlinked
        if (Path(__file__).resolve().parent.parent / ".venv").exists():
            assert venv_link.is_symlink()
        shutil.rmtree(ws, ignore_errors=True)


# ── Pipeline execution ─────────────────────────────────────────────────────


class TestRunStage:
    def test_skip_if_bib_skip(self, tmp_path: Path) -> None:
        stage = {
            "name": "import_bib",
            "command": "import",
            "args": ["bib", "{bib_path}"],
            "allow_degraded": False,
            "skip_if": "bibliography.mode == skip",
        }
        result = run_stage(tmp_path, stage, bib_path=None)
        assert result.skipped is True
        assert result.success is True

    @patch("verification.run_real_validation.subprocess.run")
    def test_successful_stage(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        stage = {"name": "doctor", "command": "doctor", "args": []}
        result = run_stage(tmp_path, stage, bib_path=None)
        assert result.success is True
        assert result.exit_code == 0

    @patch("verification.run_real_validation.subprocess.run")
    def test_degraded_stage_treated_as_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: tool unavailable"
        )
        stage = {
            "name": "lint_bib",
            "command": "lint",
            "args": ["bib"],
            "allow_degraded": True,
            "degraded_reason": "bibtex-tidy unavailable",
        }
        result = run_stage(tmp_path, stage, bib_path=None)
        assert result.degraded is True
        assert result.success is True

    @patch("verification.run_real_validation.subprocess.run")
    def test_hard_failure_stops_pipeline(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="fatal error"
        )
        stage = {"name": "init", "command": "init", "args": []}
        result = run_stage(tmp_path, stage, bib_path=None)
        assert result.success is False

    @patch("verification.run_real_validation.subprocess.run")
    def test_timeout_captured(self, mock_run: MagicMock, tmp_path: Path) -> None:
        import subprocess as sp

        mock_run.side_effect = sp.TimeoutExpired(cmd="paper", timeout=5)
        stage = {"name": "slow", "command": "render", "args": []}
        result = run_stage(tmp_path, stage, bib_path=None, timeout=5)
        assert result.success is False
        assert "timed out" in result.stderr


# ── Acceptance checks ──────────────────────────────────────────────────────


class TestCheckAcceptance:
    def test_pipeline_completed_true(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        empty_result.stages = [
            StageResult("a", "x", True, 0, "", "", 0.1),
            StageResult("b", "y", True, 0, "", "", 0.2),
        ]
        manifest = {"acceptance": {"pipeline_completed": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["pipeline_completed"] is True

    def test_pipeline_completed_false(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        empty_result.stages = [
            StageResult("a", "x", True, 0, "", "", 0.1),
            StageResult("b", "y", False, 1, "", "err", 0.2),
        ]
        manifest = {"acceptance": {"pipeline_completed": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["pipeline_completed"] is False

    def test_no_fabricated_refs(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        drafts = tmp_path / "outputs" / "drafts"
        drafts.mkdir(parents=True)
        (drafts / "intro.md").write_text("This cites [@doe2024] properly.")
        manifest = {"acceptance": {"no_fabricated_refs": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["no_fabricated_refs"] is True

    def test_fabricated_refs_detected(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        drafts = tmp_path / "outputs" / "drafts"
        drafts.mkdir(parents=True)
        (drafts / "intro.md").write_text("Bad cite [@al2024] here.")
        manifest = {"acceptance": {"no_fabricated_refs": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["no_fabricated_refs"] is False

    def test_docx_integrity_pass(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        render = tmp_path / "outputs" / "render"
        render.mkdir(parents=True)
        docx = render / "manuscript.docx"
        with zipfile.ZipFile(docx, "w") as zf:
            zf.writestr("word/document.xml", "<doc/>")
        manifest = {"acceptance": {"docx_integrity": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["docx_integrity"] is True

    def test_render_missing(self, empty_result: ValidationResult, tmp_path: Path) -> None:
        manifest = {"acceptance": {"render_output_exists": True}}
        checks = check_acceptance(empty_result, manifest, tmp_path)
        assert checks["render_output_exists"] is False


# ── Verdict computation ────────────────────────────────────────────────────


class TestComputeVerdict:
    def test_fail_on_failed_stage(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [StageResult("a", "x", False, 1, "", "err", 0.1)]
        manifest = {"manual_review": {"required": False}}
        assert compute_verdict(empty_result, manifest) == VERDICT_FAIL

    def test_fail_on_failed_acceptance(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [StageResult("a", "x", True, 0, "", "", 0.1)]
        empty_result.acceptance = {"pipeline_completed": False}
        manifest = {"manual_review": {"required": False}}
        assert compute_verdict(empty_result, manifest) == VERDICT_FAIL

    def test_pass_no_manual_review(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [StageResult("a", "x", True, 0, "", "", 0.1)]
        empty_result.acceptance = {"pipeline_completed": True}
        manifest = {"manual_review": {"required": False}}
        assert compute_verdict(empty_result, manifest) == VERDICT_PASS

    def test_manual_review_required(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [StageResult("a", "x", True, 0, "", "", 0.1)]
        empty_result.acceptance = {"pipeline_completed": True}
        manifest = {"manual_review": {"required": True}}
        assert compute_verdict(empty_result, manifest) == VERDICT_MANUAL

    def test_degraded_mode(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [
            StageResult("a", "x", True, 0, "", "", 0.1, degraded=True,
                degraded_reason="missing tool"),
        ]
        empty_result.acceptance = {"pipeline_completed": True}
        manifest = {"manual_review": {"required": True}}
        assert compute_verdict(empty_result, manifest) == VERDICT_DEGRADED


# ── Report generation ──────────────────────────────────────────────────────


class TestGenerateReport:
    def test_contains_verdict(self, empty_result: ValidationResult) -> None:
        empty_result.verdict = VERDICT_PASS
        report = generate_report(empty_result)
        assert VERDICT_PASS in report
        assert "test-case" in report

    def test_contains_stages_table(self, empty_result: ValidationResult) -> None:
        empty_result.stages = [StageResult("init", "init", True, 0, "", "", 0.3)]
        report = generate_report(empty_result)
        assert "init" in report
        assert "0.3s" in report

    def test_contains_manual_checklist(
        self, manifest_file: Path, empty_result: ValidationResult,
    ) -> None:
        empty_result.manifest_path = str(manifest_file)
        report = generate_report(empty_result)
        assert "- [ ]" in report


# ── Source validation ──────────────────────────────────────────────────────


class TestSourceValidation:
    def test_missing_pdf_exits(self, manifest_file: Path) -> None:
        """Runner exits with code 2 when source PDF does not exist."""
        from verification.run_real_validation import run_validation

        # manifest references /tmp/test.pdf which doesn't exist
        with pytest.raises(SystemExit) as exc_info:
            run_validation(manifest_file, dry_run=False, tmp_root=Path("/tmp"))
        assert exc_info.value.code == 2

    def test_dry_run_succeeds(self, manifest_file: Path) -> None:
        """Dry run validates manifest without checking source existence."""
        from verification.run_real_validation import run_validation

        result = run_validation(manifest_file, dry_run=True)
        assert result.verdict == VERDICT_MANUAL
        assert any("DRY RUN" in n for n in result.notes)
