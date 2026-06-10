from pathlib import Path

import yaml

from harness.domain.state import DomainStateError, ManuscriptState
from harness.ports.state_repository import StateRepository, StateRepositoryError


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
        except (OSError, yaml.YAMLError) as e:
            raise StateRepositoryError(f"Failed to read/parse state file: {e}") from e

        if not isinstance(data, dict):
            raise StateRepositoryError("State contents must be a dictionary.")

        # Use 'or' to handle null values — data.get() returns None when key
        # exists with null value, bypassing the default. Same pattern as #490/#492.
        stage = data.get("stage") or ""
        gates = data.get("gates") or {}

        # Auto-upgrade: map legacy stage names to current names.
        # schema_version < 1.1 used "verified" (now "rendered").
        if stage in ManuscriptState.LEGACY_STAGE_MAP:
            stage = ManuscriptState.LEGACY_STAGE_MAP[stage]

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
        except OSError as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise StateRepositoryError(f"Failed to write state file atomically: {e}") from e
