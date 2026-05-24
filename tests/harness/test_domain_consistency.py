"""Tests for domain state stage-gates consistency validation."""

import pytest

from harness.domain.state import DomainStateError, ManuscriptState


def _make_all_gates_true() -> dict[str, bool]:
    return dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)


def _make_all_gates_false() -> dict[str, bool]:
    return dict.fromkeys(ManuscriptState.REQUIRED_GATES, False)


class TestStageGatesConsistency:
    """Validate that stage-gates inconsistency is detected by validate()."""

    def test_bootstrap_all_false_is_valid(self) -> None:
        """Bootstrap with all gates False is valid — no preconditions."""
        state = ManuscriptState(stage="bootstrap", gates=_make_all_gates_false())
        state.validate()  # should not raise

    def test_search_with_repo_initialized_true(self) -> None:
        """search stage requires repo_initialized=True."""
        gates = _make_all_gates_false()
        gates["repo_initialized"] = True
        state = ManuscriptState(stage="search", gates=gates)
        state.validate()

    def test_search_with_repo_initialized_false_invalid(self) -> None:
        """search stage without repo_initialized should be rejected."""
        state = ManuscriptState(stage="search", gates=_make_all_gates_false())
        with pytest.raises(DomainStateError, match="Stage-gates inconsistency"):
            state.validate()

    def test_rendering_without_validation_gates_invalid(self) -> None:
        """rendering requires bib_normalized, citations_resolved, refs_validated,
        style_passed, reporting_passed all True."""
        state = ManuscriptState(stage="rendering", gates=_make_all_gates_false())
        with pytest.raises(DomainStateError, match="Stage-gates inconsistency"):
            state.validate()

    def test_rendering_with_all_validation_gates_true(self) -> None:
        """rendering should be valid when all validation gates are True."""
        gates = _make_all_gates_false()
        gates["bib_normalized"] = True
        gates["citations_resolved"] = True
        gates["refs_validated"] = True
        gates["style_passed"] = True
        gates["reporting_passed"] = True
        state = ManuscriptState(stage="rendering", gates=gates)
        state.validate()

    def test_validating_without_sections_completed_invalid(self) -> None:
        """validating requires sections_completed=True."""
        state = ManuscriptState(stage="validating", gates=_make_all_gates_false())
        with pytest.raises(DomainStateError, match="sections_completed"):
            state.validate()

    def test_verified_without_render_passed_invalid(self) -> None:
        """verified requires render_passed=True."""
        state = ManuscriptState(stage="verified", gates=_make_all_gates_false())
        with pytest.raises(DomainStateError, match="render_passed"):
            state.validate()

    def test_verified_with_render_passed_true(self) -> None:
        """verified with render_passed=True should be valid."""
        gates = _make_all_gates_false()
        gates["render_passed"] = True
        state = ManuscriptState(stage="verified", gates=gates)
        state.validate()

    def test_full_progression_valid(self) -> None:
        """Simulate a valid full stage progression."""
        gates = _make_all_gates_true()
        for stage in ManuscriptState.VALID_STAGES:
            state = ManuscriptState(stage=stage, gates=gates)
            state.validate()

    def test_each_stage_with_only_preconditions(self) -> None:
        """Each stage should be valid when only its preconditions are True."""
        for stage, preconditions in ManuscriptState.STAGE_PRECONDITIONS.items():
            gates = _make_all_gates_false()
            for gate in preconditions:
                gates[gate] = True
            state = ManuscriptState(stage=stage, gates=gates)
            state.validate()
