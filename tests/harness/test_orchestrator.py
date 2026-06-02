from pathlib import Path

from harness.domain.state import ManuscriptState
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.state_manager import StateManager
from tests.harness.mocks import (
    InMemoryActionRunner,
    InMemoryArtifactChecker,
    InMemoryStateRepository,
    InMemoryToolWrapper,
    create_mock_wrappers,
)


def _create_orchestrator() -> tuple[
    Orchestrator,
    InMemoryStateRepository,
    InMemoryArtifactChecker,
    InMemoryActionRunner,
]:
    repo = InMemoryStateRepository()
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)
    return orch, repo, checker, action_runner


def test_orchestrator_init() -> None:
    orch, repo, checker, _ = _create_orchestrator()
    req = OrchestratorRequest(
        command="init", requested_stage="search", failure_policy="stop_on_error"
    )
    result = orch.execute(req)

    assert result.success is True
    assert result.stage_before == "bootstrap"
    assert result.stage_after == "search"
    assert result.exit_code == 0

    assert repo.current_state is not None
    assert repo.current_state.stage == "search"
    assert repo.current_state.gates["repo_initialized"] is True

    # Check mock file existence
    assert "templates/manuscript.qmd" in checker.existing_paths
    assert "templates/references.bib" in checker.existing_paths


def test_orchestrator_precondition_failure() -> None:
    orch, _, _, _ = _create_orchestrator()
    # Run screen without init/search (state doesn't exist yet)
    req = OrchestratorRequest(
        command="screen", requested_stage="outline", failure_policy="stop_on_error"
    )
    result = orch.execute(req)
    assert result.success is False
    assert result.exit_code == 1
    assert result.blockers
    assert result.stage_before == "unknown"
    assert result.stage_after == "unknown"


def test_orchestrator_sequential_flow() -> None:
    orch, _, checker, action_runner = _create_orchestrator()

    # 1. Init
    res_init = orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
    assert res_init.success is True

    # 2. Search
    res_search = orch.execute(OrchestratorRequest("search", "screen", "stop_on_error"))
    assert res_search.success is True
    assert res_search.stage_after == "screen"
    assert "outputs/search/search_plan.json" in checker.existing_paths

    # 3. Screen
    res_screen = orch.execute(OrchestratorRequest("screen", "outline", "stop_on_error"))
    assert res_screen.success is True
    assert res_screen.stage_after == "outline"
    assert "outputs/search/screened_evidence.json" in checker.existing_paths

    # 4. Outline
    res_outline = orch.execute(OrchestratorRequest("draft_outline", "drafting", "stop_on_error"))
    assert res_outline.success is True
    assert res_outline.stage_after == "drafting"
    assert "outputs/drafts/outline.md" in checker.existing_paths

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
    assert "outputs/render/manuscript.docx" in checker.existing_paths

    # 8. Verify (Emits manifest and sets ready_for_delivery)
    res_verify = orch.execute(OrchestratorRequest("verify", "verified", "stop_on_error"))
    assert res_verify.success is True
    assert res_verify.stage_after == "verified"

    assert "outputs/manifest.yaml" in checker.existing_paths

    # Check manifest emitted snapshot in action runner mock
    assert action_runner.manifest_emitted is not None
    snapshot = action_runner.manifest_emitted
    # Assert snapshot keys match the domain gate contract
    assert set(snapshot.keys()) == set(ManuscriptState.REQUIRED_GATES)
    assert snapshot["ready_for_delivery"] is True
    assert snapshot["style_passed"] is True
    assert snapshot["bib_normalized"] is True


def test_orchestrator_gate_reset_on_re_draft() -> None:
    orch, repo, _, _ = _create_orchestrator()

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
    assert repo.current_state is not None
    assert repo.current_state.stage == "validating"

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


def _create_orchestrator_in_stage(stage: str, render_wrapper_status: str) -> Orchestrator:
    # Set the precondition gates for the target stage so the fixture is valid
    # (O-9 fix: fixtures with all-gates-False at non-bootstrap stage violate
    # the domain invariant; previously the test was passing by accident
    # because load_state() silently accepted the invalid state)
    preconditions = ManuscriptState.STAGE_PRECONDITIONS.get(stage, frozenset())
    initial_gates: dict[str, bool] = dict.fromkeys(preconditions, True)
    for gate in ManuscriptState.REQUIRED_GATES:
        initial_gates.setdefault(gate, False)
    repo = InMemoryStateRepository(
        ManuscriptState(
            stage=stage,
            gates=initial_gates,
        )
    )
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    wrappers["render"] = InMemoryToolWrapper("render_passed", return_status=render_wrapper_status)
    return Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)


def test_orchestrator_render_warn_is_success_and_transitions_to_verified() -> None:
    orch = _create_orchestrator_in_stage("rendering", render_wrapper_status="warn")

    result = orch.execute(
        OrchestratorRequest(
            command="render",
            requested_stage="verified",
            failure_policy="stop_on_error",
        )
    )

    assert result.success is True
    assert result.exit_code == 0
    assert result.stage_before == "rendering"
    assert result.stage_after == "verified"
    assert result.gate_changes["render_passed"] is True


def test_orchestrator_render_fail_blocks_and_keeps_rendering_stage() -> None:
    orch = _create_orchestrator_in_stage("rendering", render_wrapper_status="fail")

    result = orch.execute(
        OrchestratorRequest(
            command="render",
            requested_stage="verified",
            failure_policy="stop_on_error",
        )
    )

    assert result.success is False
    assert result.exit_code == 1
    assert result.stage_before == "rendering"
    assert result.stage_after == "rendering"
    assert result.gate_changes["render_passed"] is False


def test_orchestrator_verify_requires_render_passed_gate() -> None:
    # O-9 fix: use a state with valid preconditions for 'verified' stage
    preconditions = ManuscriptState.STAGE_PRECONDITIONS.get("verified", frozenset())
    initial_gates: dict[str, bool] = dict.fromkeys(preconditions, True)
    for gate in ManuscriptState.REQUIRED_GATES:
        initial_gates.setdefault(gate, False)
    # But force render_passed to False to test the rejection
    initial_gates["render_passed"] = False
    repo = InMemoryStateRepository(
        ManuscriptState(
            stage="verified",
            gates=initial_gates,
        )
    )
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)

    result = orch.execute(
        OrchestratorRequest(
            command="verify",
            requested_stage="verified",
            failure_policy="stop_on_error",
        )
    )

    # The validate() in load_state will reject because render_passed is False
    # but the stage is 'verified' (which requires render_passed=True)
    assert result.success is False
    assert result.exit_code == 1
    assert result.stage_before == "unknown"  # load_state failed → state not loaded
    assert result.stage_after == "unknown"
    assert any("render_passed" in s for s in result.steps) or any(
        "render_passed" in b for b in result.blockers
    ) or any("inconsistency" in b.lower() for b in result.blockers)
