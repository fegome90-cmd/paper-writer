import sys
from pathlib import Path


def test_orchestrator_imports_audit():
    """Verify that orchestrator.py does not even import subprocess or os.system."""
    orchestrator_path = Path("harness/services/orchestrator.py")
    content = orchestrator_path.read_text()
    
    # Static check: No forbidden imports
    forbidden = ["import subprocess", "from subprocess", "os.system", "os.popen"]
    for word in forbidden:
        assert word not in content, f"Forbidden pattern found in Orchestrator: {word}"

def test_orchestrator_no_dynamic_subprocess_real():
    """Execute Orchestrator and use sys.addaudithook to ensure no subprocess is spawned."""
    from unittest.mock import MagicMock

    from harness.ports.action_runner import ActionRunner
    from harness.ports.artifact_checker import ArtifactChecker
    from harness.services.orchestrator import Orchestrator, OrchestratorRequest
    from harness.services.state_manager import StateManager

    # Setup real dependencies where possible, mock only ports
    mock_state_manager = MagicMock(spec=StateManager)
    mock_state_manager.exists.return_value = True
    mock_state_manager.load_state.return_value = {"stage": "search", "gates": {}}
    
    mock_checker = MagicMock(spec=ArtifactChecker)
    mock_action_runner = MagicMock(spec=ActionRunner)
    mock_action_runner.run_action.return_value = []
    
    orchestrator = Orchestrator(
        repo_path=Path("."),
        state_manager=mock_state_manager,
        checker=mock_checker,
        action_runner=mock_action_runner
    )
    
    request = OrchestratorRequest(
        command="search",
        requested_stage="screen",
        failure_policy="stop_on_error"
    )

    violations = []
    def audit_hook(event, args):
        if event in ["subprocess.Popen", "os.system", "os.posix_spawn"]:
            violations.append((event, args))

    sys.addaudithook(audit_hook)
    
    try:
        orchestrator.execute(request)
    finally:
        # We can't remove audit hooks in Python, but we can check if any occurred during our execution  # noqa: E501
        pass

    assert not violations, f"Constitutional violation! Forbidden event detected: {violations}"

def test_method_gates_fail_closed_real():
    """Verify fail-closed behavior with a real Orchestrator execution path."""
    from unittest.mock import MagicMock

    from harness.ports.action_runner import ActionRunner
    from harness.ports.artifact_checker import ArtifactChecker
    from harness.services.orchestrator import Orchestrator, OrchestratorRequest
    from harness.services.state_manager import StateManager

    mock_state_manager = MagicMock(spec=StateManager)
    mock_state_manager.exists.return_value = True
    mock_state_manager.load_state.return_value = {"stage": "validating", "gates": {}}
    
    mock_checker = MagicMock(spec=ArtifactChecker)
    mock_action_runner = MagicMock(spec=ActionRunner)
    mock_action_runner.run_action.return_value = []

    orchestrator = Orchestrator(
        repo_path=Path("."),
        state_manager=mock_state_manager,
        checker=mock_checker,
        action_runner=mock_action_runner,
        wrappers={} # EMPTY
    )
    
    request = OrchestratorRequest(
        command="lint_bib",
        requested_stage="rendering",
        failure_policy="stop_on_error"
    )
    
    result = orchestrator.execute(request)
    
    assert result.success is False
    assert result.exit_code == 1
    assert any("No tool wrapper registered" in b for b in result.blockers)
