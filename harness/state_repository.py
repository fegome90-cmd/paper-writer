from abc import ABC, abstractmethod
from pathlib import Path

import yaml

from harness.domain_state import DomainStateError, ManuscriptState


class StateRepositoryError(Exception):
    """Raised for serialization and persistence issues in the repository."""

    pass


class StateRepository(ABC):
    """Abstract port defining persistence contract for ManuscriptState."""

    @abstractmethod
    def exists(self) -> bool:
        """Returns True if the persisted state exists."""
        pass

    @abstractmethod
    def load(self) -> ManuscriptState:
        """Loads and returns the ManuscriptState from persistence."""
        pass

    @abstractmethod
    def save(self, state: ManuscriptState) -> None:
        """Persists the ManuscriptState to storage."""
        pass


class YamlFileStateRepository(StateRepository):
    """Adapter implementing StateRepository using a local YAML file."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def exists(self) -> bool:
        return self.file_path.exists()

    def load(self) -> ManuscriptState:
        if not self.file_path.exists():
            raise StateRepositoryError(f"State file {self.file_path} does not exist.")

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise StateRepositoryError(f"Failed to read/parse state file: {e}") from e

        if not isinstance(data, dict):
            raise StateRepositoryError("State contents must be a dictionary.")

        stage = data.get("stage", "")
        gates = data.get("gates", {})

        try:
            state = ManuscriptState(stage=stage, gates=gates)
            state.validate()
            return state
        except DomainStateError as e:
            raise StateRepositoryError(f"Loaded state violates domain invariants: {e}") from e

    def save(self, state: ManuscriptState) -> None:
        try:
            state.validate()
        except DomainStateError as e:
            raise StateRepositoryError(f"Cannot save invalid state: {e}") from e

        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write("# Schema version: 1.0\n")
                yaml.dump(
                    {
                        "stage": state.stage,
                        "gates": state.gates,
                    },
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
            tmp_path.replace(self.file_path)
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise StateRepositoryError(f"Failed to write state file atomically: {e}") from e
