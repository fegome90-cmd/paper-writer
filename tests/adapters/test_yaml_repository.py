from pathlib import Path

import pytest
import yaml

from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.domain.state import ManuscriptState
from harness.ports.state_repository import StateRepositoryError


def test_exists_and_load_success(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    repo = YamlFileStateRepository(file_path)

    assert repo.exists() is False

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

    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(initial_content, f)

    assert repo.exists() is True
    state = repo.load()
    assert state.stage == "bootstrap"
    assert state.gates["repo_initialized"] is True
    assert state.gates["search_completed"] is False


def test_load_missing_file(tmp_path: Path) -> None:
    non_existent = tmp_path / "missing.yaml"
    repo = YamlFileStateRepository(non_existent)
    with pytest.raises(StateRepositoryError, match="does not exist"):
        repo.load()


def test_load_invalid_yaml(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{invalid_yaml: [missing_bracket")

    repo = YamlFileStateRepository(file_path)
    with pytest.raises(StateRepositoryError, match="Failed to read/parse state file"):
        repo.load()


def test_load_not_dict_yaml(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(["not", "a", "dict"], f)

    repo = YamlFileStateRepository(file_path)
    with pytest.raises(StateRepositoryError, match="must be a dictionary"):
        repo.load()


def test_load_invalid_domain_state(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    # Use a genuinely invalid stage — empty gates are auto-filled by
    # ManuscriptState.__post_init__ and are NOT a domain violation.
    invalid_content = {
        "stage": "NOT_A_REAL_STAGE",
        "gates": {},
    }
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(invalid_content, f)

    repo = YamlFileStateRepository(file_path)
    with pytest.raises(StateRepositoryError, match="Loaded state violates domain invariants"):
        repo.load()


def test_save_atomic_success(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    repo = YamlFileStateRepository(file_path)

    gates = {
        "repo_initialized": True,
        "search_completed": True,
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
    }
    state = ManuscriptState(stage="search", gates=gates)
    repo.save(state)

    assert file_path.is_file()
    with open(file_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["stage"] == "search"
    assert data["gates"]["search_completed"] is True


def test_save_invalid_state(tmp_path: Path) -> None:
    file_path = tmp_path / "state.yaml"
    repo = YamlFileStateRepository(file_path)

    # Empty gates is invalid in Domain
    state = ManuscriptState(stage="search", gates={})
    with pytest.raises(StateRepositoryError, match="Cannot save invalid state"):
        repo.save(state)
