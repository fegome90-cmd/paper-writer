"""Tests for _serialize_result() field completeness (Task A1).

Verifies that OrchestratorResult JSON serialization includes:
- gate_changes (dict[str, bool])
- state_changes (dict[str, Any])
- failure_policy (str)

And that the existing 9 fields remain unchanged (backward compat).
"""

from __future__ import annotations

from cli.paper.output import _serialize_result
from harness.services.orchestrator import OrchestratorResult


def _make_result(**overrides: object) -> OrchestratorResult:
    """Build an OrchestratorResult with sensible defaults + overrides."""
    defaults: dict[str, object] = {
        "command": "init",
        "success": True,
        "stage_before": "bootstrap",
        "stage_after": "search",
        "failure_policy": "stop_on_error",
        "exit_code": 0,
    }
    defaults.update(overrides)
    return OrchestratorResult(**defaults)  # type: ignore[arg-type]


class TestSerializeResultNewFields:
    """A1: the 3 new fields MUST appear in the serialized output."""

    def test_serialize_result_includes_gate_changes(self) -> None:
        result = _make_result(gate_changes={"repo_initialized": True})
        serialized = _serialize_result(result)
        assert "gate_changes" in serialized
        assert serialized["gate_changes"] == {"repo_initialized": True}

    def test_serialize_result_includes_state_changes(self) -> None:
        result = _make_result(
            state_changes={"stage_before": "bootstrap", "stage_after": "search"}
        )
        serialized = _serialize_result(result)
        assert "state_changes" in serialized
        assert serialized["state_changes"] == {
            "stage_before": "bootstrap",
            "stage_after": "search",
        }

    def test_serialize_result_includes_failure_policy(self) -> None:
        result = _make_result(failure_policy="continue_on_error")
        serialized = _serialize_result(result)
        assert "failure_policy" in serialized
        assert serialized["failure_policy"] == "continue_on_error"


class TestSerializeResultBackwardCompat:
    """A1: existing 9 fields MUST remain present and unchanged."""

    def test_serialize_result_backward_compat(self) -> None:
        result = _make_result()
        serialized = _serialize_result(result)
        expected_keys = {
            "command",
            "success",
            "stage_before",
            "stage_after",
            "steps",
            "blockers",
            "warnings",
            "artifacts",
            "exit_code",
        }
        assert expected_keys.issubset(serialized.keys())
        assert serialized["command"] == "init"
        assert serialized["success"] is True
        assert serialized["stage_before"] == "bootstrap"
        assert serialized["stage_after"] == "search"
        assert serialized["exit_code"] == 0


class TestSerializeResultEdgeCases:
    """A1: empty / nested values serialize correctly."""

    def test_serialize_result_empty_gate_changes(self) -> None:
        result = _make_result()
        serialized = _serialize_result(result)
        assert serialized["gate_changes"] == {}

    def test_serialize_result_nested_state_changes(self) -> None:
        result = _make_result(
            state_changes={
                "stage_before": "drafting",
                "stage_after": "validating",
                "gate_deltas": {"sections_completed": True},
            }
        )
        serialized = _serialize_result(result)
        assert serialized["state_changes"]["stage_before"] == "drafting"
        assert serialized["state_changes"]["stage_after"] == "validating"
        assert serialized["state_changes"]["gate_deltas"] == {"sections_completed": True}
