from harness.domain.state import ManuscriptState
from harness.services.gates import validate_ready_for_delivery
from tests.harness.mocks import InMemoryArtifactChecker


def test_bib_imported_is_valid_soft_gate() -> None:
    """bib_imported should be accepted as a soft gate in ManuscriptState."""
    state = ManuscriptState(stage="bootstrap", gates={"bib_imported": False})
    state.validate()
    state.set_gate("bib_imported", True)
    assert state.gates["bib_imported"] is True


def test_bib_imported_is_reset_on_bib_modification() -> None:
    """bib_imported should be reset to False when bibliography is modified."""
    state = ManuscriptState(stage="bootstrap", gates={"bib_imported": True})
    state.reset_downstream_gates("bib")
    assert state.gates["bib_imported"] is False


def test_ready_for_delivery_ignores_bib_imported() -> None:
    """validate_ready_for_delivery ignores bib_imported False status."""
    checker = InMemoryArtifactChecker()
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
        "citation_verified": True,
        "ethics_passed": True,
        "bib_imported": False,  # False soft gate
    }
    result = validate_ready_for_delivery(checker, gates_state)
    assert result.status == "pass"
    assert not result.blockers
    assert not result.warnings
