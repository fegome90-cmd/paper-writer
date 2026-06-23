"""Tests for _build_command_log_payload() field completeness (Task A2).

Verifies that the structured command log payload includes:
- gate_changes (dict[str, bool])
- state_changes (dict[str, Any])
- failure_policy (str)

The payload is built by Orchestrator._build_command_log_payload() and
persisted via ActionRunner.write_command_log().
"""

from __future__ import annotations

from pathlib import Path

from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.state_manager import StateManager
from tests.harness.mocks import (
    InMemoryActionRunner,
    InMemoryArtifactChecker,
    InMemoryStateRepository,
    create_mock_wrappers,
)


def _create_orchestrator() -> tuple[
    Orchestrator,
    InMemoryActionRunner,
]:
    repo = InMemoryStateRepository()
    manager = StateManager(repo)
    checker = InMemoryArtifactChecker()
    action_runner = InMemoryActionRunner(checker)
    wrappers = create_mock_wrappers()
    orch = Orchestrator(Path("/mock_root"), manager, checker, action_runner, wrappers)
    return orch, action_runner


class TestBuildCommandLogPayloadNewFields:
    """A2: the 3 fields MUST appear in the command log payload."""

    def test_build_command_log_payload_includes_gate_changes(self) -> None:
        orch, action_runner = _create_orchestrator()
        orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
        assert len(action_runner.command_logs) == 1
        _, payload = action_runner.command_logs[0]
        assert "gate_changes" in payload
        assert isinstance(payload["gate_changes"], dict)

    def test_build_command_log_payload_includes_state_changes(self) -> None:
        orch, action_runner = _create_orchestrator()
        orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
        _, payload = action_runner.command_logs[0]
        assert "state_changes" in payload
        assert isinstance(payload["state_changes"], dict)

    def test_build_command_log_payload_includes_failure_policy(self) -> None:
        orch, action_runner = _create_orchestrator()
        orch.execute(
            OrchestratorRequest("init", "search", "continue_on_error")
        )
        _, payload = action_runner.command_logs[0]
        assert "failure_policy" in payload
        assert payload["failure_policy"] == "continue_on_error"


class TestBuildCommandLogPayloadBackwardCompat:
    """A2: existing fields MUST remain present and unchanged."""

    def test_build_command_log_payload_backward_compat(self) -> None:
        orch, action_runner = _create_orchestrator()
        orch.execute(OrchestratorRequest("init", "search", "stop_on_error"))
        _, payload = action_runner.command_logs[0]
        expected_keys = {
            "command",
            "requested_stage",
            "failure_policy",
            "args",
            "success",
            "exit_code",
            "stage_before",
            "stage_after",
            "steps",
            "blockers",
            "warnings",
            "artifacts",
        }
        assert expected_keys.issubset(payload.keys())
        assert payload["command"] == "init"
        assert payload["success"] is True
