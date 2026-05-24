from pathlib import Path

import pytest
import yaml

from harness.state_manager import StateManager, StateManagerError
from harness.state_repository import YamlFileStateRepository


@pytest.fixture
def temp_state_file(tmp_path: Path) -> Path:
    state_file = tmp_path / "state.yaml"
    initial_content = {
        "stage": "bootstrap",
        "gates": {
            "repo_initialized": True,
            "search_completed": False,
            "screened_evidence": False,
            "outline_drafted": False,
            "sections_completed": False,
            "bib_normalized": False,
            "citations_resolved": False,
            "refs_validated": False,
            "style_passed": False,
            "reporting_passed": False,
            "render_passed": False,
            "ready_for_delivery": False,
        },
    }
    with open(state_file, "w", encoding="utf-8") as f:
        yaml.dump(initial_content, f)
    return state_file


def test_load_state_success(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    state = manager.load_state()
    assert state["stage"] == "bootstrap"
    assert state["gates"]["repo_initialized"] is True
    assert state["gates"]["search_completed"] is False


def test_load_state_missing_file(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.yaml"
    repo = YamlFileStateRepository(non_existent)
    manager = StateManager(repo)
    with pytest.raises(StateManagerError, match="does not exist"):
        manager.load_state()


def test_load_state_invalid_yaml(temp_state_file: Path) -> None:
    with open(temp_state_file, "w", encoding="utf-8") as f:
        f.write("{invalid_yaml: [missing_bracket")
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    with pytest.raises(StateManagerError, match="failed to load"):
        manager.load_state()


def test_validate_state_invalid_types() -> None:
    repo = YamlFileStateRepository(Path("dummy.yaml"))
    manager = StateManager(repo)
    with pytest.raises(StateManagerError, match="Validation failed"):
        manager.validate_state({"stage": "bootstrap", "gates": "not_a_dict"})


def test_validate_state_unknown_gate() -> None:
    repo = YamlFileStateRepository(Path("dummy.yaml"))
    manager = StateManager(repo)
    invalid_data = {
        "stage": "bootstrap",
        "gates": {
            "repo_initialized": True,
            "unknown_gate": False,  # Unknown
        },
    }
    with pytest.raises(StateManagerError):
        manager.validate_state(invalid_data)


def test_set_gate(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    manager.set_gate("search_completed", True)

    new_repo = YamlFileStateRepository(temp_state_file)
    new_manager = StateManager(new_repo)
    state = new_manager.load_state()
    assert state["gates"]["search_completed"] is True


def test_set_gate_unknown(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    with pytest.raises(StateManagerError):
        manager.set_gate("non_existent_gate", True)


def test_set_stage_valid_transition(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    manager.set_stage("search")
    assert manager.state.stage == "search"  # type: ignore


def test_set_stage_invalid_transition(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    with pytest.raises(StateManagerError, match="precondition gate 'search_completed' is not True"):
        manager.set_stage("screen")


def test_reset_downstream_gates_draft(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    manager.set_gate("citations_resolved", True)
    manager.set_gate("style_passed", True)
    manager.set_gate("reporting_passed", True)
    manager.set_gate("render_passed", True)
    manager.set_gate("ready_for_delivery", True)

    manager.reset_downstream_gates("draft")

    state = manager.load_state()
    assert state["gates"]["citations_resolved"] is False
    assert state["gates"]["style_passed"] is False
    assert state["gates"]["reporting_passed"] is False
    assert state["gates"]["render_passed"] is False
    assert state["gates"]["ready_for_delivery"] is False
    assert state["gates"]["bib_normalized"] is False


def test_reset_downstream_gates_bib(temp_state_file: Path) -> None:
    repo = YamlFileStateRepository(temp_state_file)
    manager = StateManager(repo)
    manager.set_gate("bib_normalized", True)
    manager.set_gate("refs_validated", True)
    manager.set_gate("render_passed", True)
    manager.set_gate("ready_for_delivery", True)

    manager.reset_downstream_gates("bib")

    state = manager.load_state()
    assert state["gates"]["bib_normalized"] is False
    assert state["gates"]["refs_validated"] is False
    assert state["gates"]["render_passed"] is False
    assert state["gates"]["ready_for_delivery"] is False
