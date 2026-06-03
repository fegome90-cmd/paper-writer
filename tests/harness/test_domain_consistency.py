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
        state = ManuscriptState(stage="rendered", gates=_make_all_gates_false())
        with pytest.raises(DomainStateError, match="render_passed"):
            state.validate()

    def test_verified_with_render_passed_true(self) -> None:
        """verified with render_passed=True should be valid."""
        gates = _make_all_gates_false()
        gates["render_passed"] = True
        state = ManuscriptState(stage="rendered", gates=gates)
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


class TestTransitionTo:
    """Test transition_to enforces forward-only and precondition checks."""

    def _bootstrap_state(self) -> ManuscriptState:
        """Create a bootstrap state with all gates False."""
        return ManuscriptState(stage="bootstrap", gates=_make_all_gates_false())

    def test_forward_transition_allowed(self) -> None:
        """bootstrap -> search should succeed."""
        state = self._bootstrap_state()
        state.gates["repo_initialized"] = True
        state.transition_to("search")
        assert state.stage == "search"

    def test_same_stage_is_noop(self) -> None:
        """Transition to current stage is a silent no-op."""
        state = self._bootstrap_state()
        state.transition_to("bootstrap")
        assert state.stage == "bootstrap"

    def test_backward_transition_rejected(self) -> None:
        """search -> bootstrap should be rejected (backward)."""
        gates = _make_all_gates_false()
        gates["repo_initialized"] = True
        state = ManuscriptState(stage="search", gates=gates)
        with pytest.raises(DomainStateError, match="Backward transition not allowed"):
            state.transition_to("bootstrap")

    def test_skip_stages_rejected(self) -> None:
        """bootstrap -> screen (skipping search) should be rejected."""
        state = self._bootstrap_state()
        with pytest.raises(DomainStateError, match="Cannot skip stages"):
            state.transition_to("screen")

    def test_transition_with_unsatisfied_preconditions_rejected(self) -> None:
        """search -> screen without search_completed should be rejected."""
        gates = _make_all_gates_false()
        gates["repo_initialized"] = True
        state = ManuscriptState(stage="search", gates=gates)
        # search_completed is False — precondition for 'screen'
        with pytest.raises(DomainStateError, match=r"precondition gate.*not True"):
            state.transition_to("screen")

    def test_transition_with_satisfied_preconditions_allowed(self) -> None:
        """search -> screen with search_completed=True should succeed."""
        gates = _make_all_gates_false()
        gates["repo_initialized"] = True
        gates["search_completed"] = True
        state = ManuscriptState(stage="search", gates=gates)
        state.transition_to("screen")
        assert state.stage == "screen"

    def test_multi_step_forward_progression(self) -> None:
        """Full valid progression: bootstrap -> search -> screen."""
        state = self._bootstrap_state()
        state.gates["repo_initialized"] = True
        state.transition_to("search")
        state.gates["search_completed"] = True
        state.transition_to("screen")
        assert state.stage == "screen"

    def test_backward_from_verified_rejected(self) -> None:
        """verified -> rendering should be rejected."""
        gates = _make_all_gates_true()
        state = ManuscriptState(stage="rendered", gates=gates)
        with pytest.raises(DomainStateError, match="Backward transition"):
            state.transition_to("rendering")


class TestPostInitGateAutoFill:
    """Test that __post_init__ auto-fills missing gates from REQUIRED_GATES."""

    def test_empty_gates_dict_fills_all_required(self) -> None:
        """Creating state with empty gates dict should fill all REQUIRED_GATES."""
        state = ManuscriptState(stage="bootstrap", gates={})
        assert set(state.gates.keys()) == ManuscriptState.REQUIRED_GATES
        assert all(v is False for v in state.gates.values())

    def test_partial_gates_dict_preserves_existing(self) -> None:
        """Partial gates dict should preserve existing values and fill the rest."""
        state = ManuscriptState(stage="bootstrap", gates={"repo_initialized": True})
        assert state.gates["repo_initialized"] is True
        assert len(state.gates) == len(ManuscriptState.REQUIRED_GATES)
        rest = {k: v for k, v in state.gates.items() if k != "repo_initialized"}
        assert all(v is False for v in rest.values())

    def test_complete_gates_dict_unchanged(self) -> None:
        """Complete gates dict should not be modified by __post_init__."""
        gates = dict.fromkeys(ManuscriptState.REQUIRED_GATES, True)
        state = ManuscriptState(stage="rendered", gates=gates)
        assert all(v is True for v in state.gates.values())
