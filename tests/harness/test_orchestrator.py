from pathlib import Path

import pytest
import yaml

from harness.orchestrator import Orchestrator, OrchestratorRequest
from harness.state_manager import StateManager
from harness.state_repository import YamlFileStateRepository


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    # We will use tmp_path as our repo root for isolated testing
    return tmp_path


def _create_orchestrator(repo_path: Path) -> Orchestrator:
    repo = YamlFileStateRepository(repo_path / "outputs" / "state.yaml")
    manager = StateManager(repo)
    return Orchestrator(repo_path, manager)


def test_orchestrator_init(test_repo: Path) -> None:
    orch = _create_orchestrator(test_repo)
    req = OrchestratorRequest(
        command="init", requested_stage="search", failure_policy="stop_on_error"
    )
    result = orch.execute(req)

    assert result.success is True
    assert result.stage_before == "bootstrap"
    assert result.stage_after == "search"
    assert result.exit_code == 0

    # Check that state file was created and stage is search
    state_file = test_repo / "outputs" / "state.yaml"
    assert state_file.is_file()
    with open(state_file, encoding="utf-8") as f:
        state_data = yaml.safe_load(f)
    assert state_data["stage"] == "search"
    assert state_data["gates"]["repo_initialized"] is True

    # Check templates
    assert (test_repo / "templates" / "manuscript.qmd").is_file()
    assert (test_repo / "templates" / "references.bib").is_file()


def test_orchestrator_precondition_failure(test_repo: Path) -> None:
    orch = _create_orchestrator(test_repo)
    # Run screen without init/search (state file doesn't exist yet)
    req = OrchestratorRequest(
        command="screen", requested_stage="outline", failure_policy="stop_on_error"
    )
    result = orch.execute(req)
    assert result.success is False
    assert result.exit_code == 1
    assert any("does not exist" in b for b in result.blockers)


def test_orchestrator_sequential_flow(test_repo: Path) -> None:
    orch = _create_orchestrator(test_repo)

    # 1. Init
    res_init = orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
    assert res_init.success is True

    # 2. Search
    res_search = orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))
    assert res_search.success is True
    assert res_search.stage_after == "screen"
    assert (test_repo / "outputs" / "search" / "search_plan.json").is_file()

    # 3. Screen
    res_screen = orch.execute(OrchestratorRequest("screen", "outline", "stop_on_error"))
    assert res_screen.success is True
    assert res_screen.stage_after == "outline"
    assert (test_repo / "outputs" / "search" / "screened_evidence.json").is_file()

    # 4. Outline
    res_outline = orch.execute(OrchestratorRequest("draft_outline", "drafting", "stop_on_error"))
    assert res_outline.success is True
    assert res_outline.stage_after == "drafting"
    assert (test_repo / "outputs" / "drafts" / "outline.md").is_file()

    # 5. Draft Sections (Must draft all 4 to transition to validating)
    for section in ["introduction", "methods", "results"]:
        res_sec = orch.execute(
            OrchestratorRequest(
                command="draft_section",
                requested_stage="drafting",
                failure_policy="stop_on_error",
                args={"name": section},
            )
        )
        assert res_sec.success is True
        assert res_sec.stage_after == "drafting"  # Stays in drafting until completed

    # Draft last section
    res_last = orch.execute(
        OrchestratorRequest(
            command="draft_section",
            requested_stage="validating",
            failure_policy="stop_on_error",
            args={"name": "discussion"},
        )
    )
    assert res_last.success is True
    assert res_last.stage_after == "validating"  # Successfully transitioned!

    # 6. Run Validators
    # lint_bib
    res_bib = orch.execute(OrchestratorRequest("lint_bib", "validating", "continue_on_error"))
    assert res_bib.success is True

    # check_refs (sets citations_resolved & refs_validated)
    res_refs = orch.execute(OrchestratorRequest("check_refs", "validating", "continue_on_error"))
    assert res_refs.success is True

    # lint_style
    res_style = orch.execute(OrchestratorRequest("lint_style", "validating", "continue_on_error"))
    assert res_style.success is True

    # audit_reporting (sets reporting_passed and triggers transition to rendering)
    res_audit = orch.execute(
        OrchestratorRequest(
            command="audit_reporting",
            requested_stage="rendering",
            failure_policy="continue_on_error",
        )
    )
    assert res_audit.success is True
    assert res_audit.stage_after == "rendering"

    # 7. Render
    res_render = orch.execute(OrchestratorRequest("render", "verified", "stop_on_error"))
    assert res_render.success is True
    assert res_render.stage_after == "verified"
    assert (test_repo / "outputs" / "render" / "manuscript.docx").is_file()

    # 8. Verify (Emits manifest and sets ready_for_delivery)
    res_verify = orch.execute(OrchestratorRequest("verify", "verified", "stop_on_error"))
    assert res_verify.success is True
    assert res_verify.stage_after == "verified"

    manifest_file = test_repo / "outputs" / "manifest.yaml"
    assert manifest_file.is_file()

    with open(manifest_file, encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    assert manifest["status"] == "ready_for_delivery"
    assert manifest["verdict"] == "pass"
    assert manifest["gate_snapshot"]["ready_for_delivery"] is True


def test_orchestrator_gate_reset_on_re_draft(test_repo: Path) -> None:
    orch = _create_orchestrator(test_repo)

    # Walk all the way to validating stage
    orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
    orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))
    orch.execute(OrchestratorRequest("screen", "outline", "stop_on_error"))
    orch.execute(OrchestratorRequest("draft_outline", "drafting", "stop_on_error"))
    for section in ["introduction", "methods", "results", "discussion"]:
        orch.execute(
            OrchestratorRequest(
                command="draft_section",
                requested_stage="drafting",
                failure_policy="stop_on_error",
                args={"name": section},
            )
        )

    # Stage should now be validating
    state_file = test_repo / "outputs" / "state.yaml"
    with open(state_file, encoding="utf-8") as f:
        state_data = yaml.safe_load(f)
    assert state_data["stage"] == "validating"

    # Mock some verification gates
    orch.state_manager.set_gate("citations_resolved", True)
    orch.state_manager.set_gate("style_passed", True)

    # Now re-draft introduction
    orch.execute(
        OrchestratorRequest(
            command="draft_section",
            requested_stage="drafting",
            failure_policy="stop_on_error",
            args={"name": "introduction"},
        )
    )

    # Verify that gates have been reset
    state_data = orch.state_manager.load_state()
    assert state_data["gates"]["citations_resolved"] is False
    assert state_data["gates"]["style_passed"] is False
