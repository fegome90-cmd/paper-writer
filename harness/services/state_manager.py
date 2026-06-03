from typing import Any

from harness.domain.state import DomainStateError, ManuscriptState
from harness.ports.state_repository import StateRepository, StateRepositoryError


class StateManagerError(Exception):
    """Exception raised by StateManager for orchestrator-facing errors."""

    pass


class StateManager:
    """Application service coordinating ManuscriptState domain and StateRepository."""

    def __init__(self, repository: StateRepository) -> None:
        self.repository = repository
        self.state: ManuscriptState | None = None

    def exists(self) -> bool:
        """Returns True if the persisted state exists."""
        return self.repository.exists()

    def load_state(self) -> dict[str, Any]:
        """Loads state through the repository and returns its representation."""
        try:
            self.state = self.repository.load()
            self.state.validate()
            return {
                "stage": self.state.stage,
                "gates": self.state.gates,
            }
        except (StateRepositoryError, DomainStateError) as e:
            raise StateManagerError(f"State Manager failed to load state: {e}") from e

    def validate_state(self, data: dict[str, Any]) -> None:
        """Helper to validate arbitrary state structure using domain invariants."""
        try:
            stage = data.get("stage", "")
            # Auto-upgrade legacy stage names (e.g. "verified" -> "rendered")
            if stage in ManuscriptState.LEGACY_STAGE_MAP:
                stage = ManuscriptState.LEGACY_STAGE_MAP[stage]
            temp_state = ManuscriptState(stage=stage, gates=data.get("gates", {}))
            temp_state.validate()
        except DomainStateError as e:
            raise StateManagerError(f"Validation failed: {e}") from e

    def save_state(self) -> None:
        """Saves current state to persistence."""
        if not self.state:
            raise StateManagerError("No state loaded to save.")
        try:
            self.repository.save(self.state)
        except StateRepositoryError as e:
            raise StateManagerError(f"State Manager failed to save state: {e}") from e

    def set_gate(self, gate_name: str, value: bool) -> None:
        """Sets a gate value in the loaded state and persists the changes."""
        if not self.state:
            self.load_state()

        if self.state is None:
            raise StateManagerError("State could not be loaded.")
        try:
            self.state.set_gate(gate_name, value)
            self.save_state()
        except DomainStateError as e:
            raise StateManagerError(f"Failed to set gate: {e}") from e

    def set_stage(self, stage_name: str) -> None:
        """Performs a domain stage transition and persists the changes."""
        if not self.state:
            self.load_state()

        if self.state is None:
            raise StateManagerError("State could not be loaded.")
        try:
            self.state.transition_to(stage_name)
            self.save_state()
        except DomainStateError as e:
            raise StateManagerError(f"Failed to change stage: {e}") from e

    def reset_downstream_gates(self, modified_artifact_type: str) -> None:
        """Performs domain gate reset based on modified artifact type and persists."""
        if not self.state:
            self.load_state()

        if self.state is None:
            raise StateManagerError("State could not be loaded.")
        try:
            self.state.reset_downstream_gates(modified_artifact_type)
            self.save_state()
        except DomainStateError as e:
            raise StateManagerError(f"Failed to reset gates: {e}") from e
