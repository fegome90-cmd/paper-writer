from abc import ABC, abstractmethod
from typing import Any


class ActionRunner(ABC):
    """Port for executing side-effect actions and emitting pipeline outputs."""

    @abstractmethod
    def run_action(self, command: str, args: dict[str, Any], state_manager: Any) -> list[str]:
        """Runs the action associated with a command.

        Returns list of generated artifact paths.
        """
        pass

    @abstractmethod
    def emit_manifest(self, gate_snapshot: dict[str, bool]) -> str:
        """Emits the final manifest and returns its path."""
        pass
