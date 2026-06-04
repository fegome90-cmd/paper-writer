from pathlib import Path

import pytest
import yaml

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.adapters.filesystem_artifact_checker import FilesystemArtifactChecker
from harness.domain.state import ManuscriptState


def test_artifact_checker_dir_exists(tmp_path: Path) -> None:
    checker = FilesystemArtifactChecker(tmp_path)

    # Missing directory
    with pytest.raises(FileNotFoundError, match="Directory 'outputs' not found"):
        checker.check_dir_exists("outputs")

    # Created directory
    (tmp_path / "outputs").mkdir()
    checker.check_dir_exists("outputs")


def test_artifact_checker_file_exists(tmp_path: Path) -> None:
    checker = FilesystemArtifactChecker(tmp_path)

    # Missing file
    with pytest.raises(FileNotFoundError, match=r"File 'manuscript\.qmd' not found"):
        checker.check_file_exists("manuscript.qmd")

    # Empty file should fail — gates require non-empty artifacts
    (tmp_path / "manuscript.qmd").touch()
    with pytest.raises(ValueError, match="empty"):
        checker.check_file_exists("manuscript.qmd")

    # Non-empty file should pass
    (tmp_path / "manuscript.qmd").write_text("# Title\n\nContent.", encoding="utf-8")
    checker.check_file_exists("manuscript.qmd")


def test_artifact_checker_any_file_exists(tmp_path: Path) -> None:
    checker = FilesystemArtifactChecker(tmp_path)

    files = ["file1.txt", "file2.txt"]
    with pytest.raises(FileNotFoundError, match="No files found"):
        checker.check_any_file_exists(files)

    # Empty file should fail — all existing files must be non-empty
    (tmp_path / "file2.txt").touch()
    with pytest.raises(ValueError, match="empty"):
        checker.check_any_file_exists(files)

    # Non-empty file should pass
    (tmp_path / "file2.txt").write_text("content", encoding="utf-8")
    checker.check_any_file_exists(files)


def test_artifact_checker_get_full_path_str(tmp_path: Path) -> None:
    checker = FilesystemArtifactChecker(tmp_path)
    assert checker.get_full_path_str("templates/ref.bib") == str(tmp_path / "templates" / "ref.bib")


RUN_ID = "20260603T120000"


def _run_path(tmp_path: Path, *parts: str) -> Path:
    """Helper to build per-run artifact path."""
    return (
        tmp_path / "outputs" / "runs" / RUN_ID / Path(*parts)
        if parts
        else tmp_path / "outputs" / "runs" / RUN_ID
    )


def test_action_runner_init(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    artifacts = runner.run_action("init", {})

    assert len(artifacts) == 3
    assert (tmp_path / "templates" / "manuscript.qmd").is_file()
    assert (tmp_path / "templates" / "references.bib").is_file()
    assert (tmp_path / "outputs" / "runs").is_dir()
    assert (tmp_path / "outputs" / "logs").is_dir()


def test_action_runner_search(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    artifacts = runner.run_action("search", {})

    assert len(artifacts) == 2
    plan_path = _run_path(tmp_path, "search", "search_plan.json")
    results_path = _run_path(tmp_path, "search", "raw_results.json")
    assert plan_path.is_file()
    assert results_path.is_file()


def test_action_runner_screen(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    artifacts = runner.run_action("screen", {})

    assert len(artifacts) == 1
    evidence_path = _run_path(tmp_path, "search", "screened_evidence.json")
    assert evidence_path.is_file()


def test_action_runner_draft_outline(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    artifacts = runner.run_action("draft_outline", {})

    assert len(artifacts) == 1
    outline_path = _run_path(tmp_path, "drafts", "outline.md")
    assert outline_path.is_file()


def test_action_runner_draft_section(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    # Missing name
    with pytest.raises(ValueError, match="Missing 'name' argument"):
        runner.run_action("draft_section", {})

    # Invalid name
    with pytest.raises(ValueError, match="Invalid section name"):
        runner.run_action("draft_section", {"name": "bibliography"})

    # Valid section
    artifacts = runner.run_action("draft_section", {"name": "introduction"})
    assert len(artifacts) == 1
    intro_path = _run_path(tmp_path, "drafts", "introduction.md")
    assert intro_path.is_file()

    # Previously rejected sections now accepted
    for section in ["abstract", "literature_review", "conclusion"]:
        artifacts = runner.run_action("draft_section", {"name": section})
        assert len(artifacts) == 1


def test_action_runner_draft_all(tmp_path: Path) -> None:
    """draft_all handler creates all 7 manifest section files."""
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    artifacts = runner.run_action("draft_all", {})
    assert len(artifacts) == 7, f"Expected 7 section artifacts, got {len(artifacts)}"

    # Verify all 7 manifest sections are created
    expected_sections = [
        "introduction",
        "methods",
        "results",
        "discussion",
        "abstract",
        "literature_review",
        "conclusion",
    ]
    for sec in expected_sections:
        sec_path = _run_path(tmp_path, "drafts", f"{sec}.md")
        assert sec_path.is_file(), f"Missing section file: {sec}.md"
        content = sec_path.read_text(encoding="utf-8")
        assert len(content) > 0, f"Empty section: {sec}.md"

    # Verify artifacts list matches created files
    for artifact in artifacts:
        assert Path(artifact).is_file(), f"Artifact not found: {artifact}"


def test_action_runner_validation_logs(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    for cmd in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
        artifacts = runner.run_action(cmd, {})
        assert len(artifacts) == 1
        log_path = _run_path(tmp_path, "logs", f"{cmd}.log")
        assert log_path.is_file()


def test_action_runner_render(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)
    artifacts = runner.run_action("render", {})

    assert len(artifacts) == 1
    assert _run_path(tmp_path, "render").is_dir()


def test_action_runner_chain(tmp_path: Path) -> None:
    """chain handler delegates to adapter or writes search output."""
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    # Without adapter — falls through (no artifacts, search dir created)
    artifacts = runner.run_action("chain", {})
    search_dir = _run_path(tmp_path, "search")
    assert search_dir.is_dir()


def test_action_runner_export_bib(tmp_path: Path) -> None:
    """export_bib handler delegates to adapter for bib generation."""
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    # Without adapter — no artifacts but doesn't crash
    artifacts = runner.run_action("export_bib", {})
    assert isinstance(artifacts, list)


def test_action_runner_protocol(tmp_path: Path) -> None:
    """protocol handler generates reproducibility protocol markdown."""
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    artifacts = runner.run_action("protocol", {})
    assert len(artifacts) == 1
    protocol_path = Path(artifacts[0])
    assert protocol_path.is_file()
    content = protocol_path.read_text(encoding="utf-8")
    assert "Reproducibility" in content or "Protocol" in content or "Search Strategy" in content


def test_action_runner_audit_code_health(tmp_path: Path) -> None:
    """audit_code_health handler writes a log file."""
    runner = FilesystemActionRunner(tmp_path, run_id=RUN_ID)

    artifacts = runner.run_action("audit_code_health", {})
    assert len(artifacts) == 1
    log_path = Path(artifacts[0])
    assert log_path.is_file()
    assert "audit_code_health" in str(log_path)


def test_action_runner_emit_manifest(tmp_path: Path) -> None:
    runner = FilesystemActionRunner(tmp_path)
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)

    gates = {
        "repo_initialized": True,
        "search_completed": True,
        "screened_evidence": True,
        "outline_drafted": True,
        "sections_completed": True,
        "bib_normalized": True,
        "citations_resolved": True,
        "refs_validated": True,
        "style_passed": True,
        "reporting_passed": True,
        "render_passed": True,
        "ready_for_delivery": True,
    }

    manifest_path_str = runner.emit_manifest(gates)
    manifest_path = Path(manifest_path_str)
    assert manifest_path.is_file()

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    assert manifest["schema_version"] == "1.1"
    assert manifest["status"] == "ready_for_delivery"
    assert manifest["stage"] == "rendered"
    assert manifest["gate_snapshot"] == gates
    assert manifest["verdict"] == "pass"
    assert len(manifest["gate_snapshot"]) == 12


def test_emit_manifest_reflects_failed_gates(tmp_path: Path) -> None:
    """Manifest must NOT claim delivery-ready when gates have failed."""
    runner = FilesystemActionRunner(tmp_path)
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)

    all_failed = dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)
    manifest_path_str = runner.emit_manifest(all_failed)
    manifest_path = Path(manifest_path_str)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    assert manifest["status"] == "incomplete", "Manifest must say 'incomplete' when no gates passed"
    assert manifest["verdict"] == "fail", "Manifest must say 'fail' when no gates passed"
    assert manifest["gate_snapshot"] == all_failed
    assert len(manifest["notes"]) > 0, "Failed manifest should list issue notes"


def test_emit_manifest_only_lists_existing_artifacts(tmp_path: Path) -> None:
    """Manifest must not claim artifacts exist if they don't."""
    runner = FilesystemActionRunner(tmp_path)
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)

    all_passed = dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)
    manifest_path_str = runner.emit_manifest(all_passed)

    with open(manifest_path_str, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    # No render outputs or bib exist — artifacts should be empty
    assert manifest["artifacts"] == {}, (
        "Manifest should not list artifacts that don't exist on disk"
    )
