from pathlib import Path

from harness.gates import (
    validate_bib_normalized,
    validate_outline_drafted,
    validate_ready_for_delivery,
    validate_render_passed,
    validate_repo_initialized,
    validate_screened_evidence,
    validate_search_completed,
    validate_sections_completed,
    validate_validator_gate,
)


def test_validate_repo_initialized_success(tmp_path: Path) -> None:
    # Create required directories
    for d in ["cli", "harness", "validators", "templates", "outputs"]:
        (tmp_path / d).mkdir()

    result = validate_repo_initialized(tmp_path)
    assert result.status == "pass"
    assert not result.blockers
    assert not result.warnings


def test_validate_repo_initialized_fail(tmp_path: Path) -> None:
    # Leave outputs directory missing
    for d in ["cli", "harness", "validators", "templates"]:
        (tmp_path / d).mkdir()

    result = validate_repo_initialized(tmp_path)
    assert result.status == "fail"
    assert any("dir_exists_outputs" in b for b in result.blockers)


def test_validate_search_completed_success(tmp_path: Path) -> None:
    search_dir = tmp_path / "outputs" / "search"
    search_dir.mkdir(parents=True)
    (search_dir / "search_plan.json").touch()
    (search_dir / "raw_results.json").touch()

    result = validate_search_completed(tmp_path)
    assert result.status == "pass"


def test_validate_search_completed_fail(tmp_path: Path) -> None:
    result = validate_search_completed(tmp_path)
    assert result.status == "fail"
    assert len(result.blockers) == 2


def test_validate_screened_evidence(tmp_path: Path) -> None:
    search_dir = tmp_path / "outputs" / "search"
    search_dir.mkdir(parents=True)

    result1 = validate_screened_evidence(tmp_path)
    assert result1.status == "fail"

    (search_dir / "screened_evidence.json").touch()
    result2 = validate_screened_evidence(tmp_path)
    assert result2.status == "pass"


def test_validate_outline_drafted(tmp_path: Path) -> None:
    drafts_dir = tmp_path / "outputs" / "drafts"
    drafts_dir.mkdir(parents=True)

    result1 = validate_outline_drafted(tmp_path)
    assert result1.status == "fail"

    (drafts_dir / "outline.md").touch()
    result2 = validate_outline_drafted(tmp_path)
    assert result2.status == "pass"


def test_validate_sections_completed(tmp_path: Path) -> None:
    drafts_dir = tmp_path / "outputs" / "drafts"
    drafts_dir.mkdir(parents=True)

    result1 = validate_sections_completed(tmp_path)
    assert result1.status == "fail"
    assert len(result1.blockers) == 4

    # Create sections
    for sec in ["introduction.md", "methods.md", "results.md", "discussion.md"]:
        (drafts_dir / sec).touch()

    result2 = validate_sections_completed(tmp_path)
    assert result2.status == "pass"


def test_validate_bib_normalized(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True)

    result1 = validate_bib_normalized(tmp_path)
    assert result1.status == "fail"

    (templates_dir / "references.bib").touch()
    result2 = validate_bib_normalized(tmp_path)
    assert result2.status == "pass"


def test_validate_validator_gate() -> None:
    # Test missing result
    result = validate_validator_gate("style_passed", None)
    assert result.status == "fail"
    assert "No validation results found" in result.blockers[0]

    # Test pass result
    pass_res = {
        "status": "pass",
        "findings": [],
        "artifacts_checked": ["outputs/drafts/introduction.md"],
    }
    result_pass = validate_validator_gate("style_passed", pass_res)
    assert result_pass.status == "pass"

    # Test warn result
    warn_res = {
        "status": "pass",
        "findings": [
            {"code": "passive_voice", "severity": "warning", "message": "Use active voice."}
        ],
        "artifacts_checked": ["outputs/drafts/introduction.md"],
    }
    result_warn = validate_validator_gate("style_passed", warn_res)
    assert result_warn.status == "warn"
    assert "passive_voice" in result_warn.warnings[0]

    # Test fail result
    fail_res = {
        "status": "pass",
        "findings": [
            {"code": "unresolved_ref", "severity": "error", "message": "Ref smith2024 not found."}
        ],
    }
    result_fail = validate_validator_gate("style_passed", fail_res)
    assert result_fail.status == "fail"
    assert "unresolved_ref" in result_fail.blockers[0]


def test_validate_render_passed(tmp_path: Path) -> None:
    render_dir = tmp_path / "outputs" / "render"
    render_dir.mkdir(parents=True)

    result1 = validate_render_passed(tmp_path)
    assert result1.status == "fail"

    # Create docx file
    (render_dir / "manuscript.docx").touch()
    result2 = validate_render_passed(tmp_path)
    assert result2.status == "pass"


def test_validate_ready_for_delivery(tmp_path: Path) -> None:
    gates_state = {
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
        "ready_for_delivery": False,
    }

    result1 = validate_ready_for_delivery(tmp_path, gates_state)
    assert result1.status == "pass"

    # Break one gate
    gates_state["style_passed"] = False
    result2 = validate_ready_for_delivery(tmp_path, gates_state)
    assert result2.status == "fail"
    assert any("style_passed" in b for b in result2.blockers)
