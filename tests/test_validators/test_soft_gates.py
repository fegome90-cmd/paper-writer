"""Tests for soft gates — citation_verified and ethics_passed."""

from __future__ import annotations

import pytest

from harness.domain.state import DomainStateError, ManuscriptState


def _make_state() -> ManuscriptState:
    return ManuscriptState(stage="bootstrap")


class TestSoftGates:
    def test_set_gate_accepts_soft_gates(self):
        state = _make_state()
        state.set_gate("citation_verified", True)
        assert state.gates["citation_verified"] is True

    def test_set_gate_accepts_ethics_passed(self):
        state = _make_state()
        state.set_gate("ethics_passed", True)
        assert state.gates["ethics_passed"] is True

    def test_set_gate_rejects_unknown_gate(self):
        state = _make_state()
        with pytest.raises(DomainStateError, match="Unknown gate"):
            state.set_gate("nonexistent_gate", True)

    def test_validate_accepts_soft_gates(self):
        state = _make_state()
        state.gates["citation_verified"] = True
        state.gates["ethics_passed"] = True
        state.validate()  # Should not raise

    def test_validate_rejects_non_boolean_soft_gate(self):
        state = _make_state()
        state.gates["citation_verified"] = "not_a_bool"
        with pytest.raises(DomainStateError, match="must be boolean"):
            state.validate()

    def test_reset_draft_resets_soft_gates(self):
        state = _make_state()
        state.gates["citation_verified"] = True
        state.gates["ethics_passed"] = True
        state.reset_downstream_gates("draft")
        assert state.gates["citation_verified"] is False
        assert state.gates["ethics_passed"] is False

    def test_soft_gates_not_in_required_gates(self):
        assert "citation_verified" not in ManuscriptState.REQUIRED_GATES
        assert "ethics_passed" not in ManuscriptState.REQUIRED_GATES
