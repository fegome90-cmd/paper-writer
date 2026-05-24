"""Port for domain skill adapters.

Defines the normalized contract that all skill adapters must implement.
The orchestrator depends on this port, never on concrete skill internals.

See docs/SKILL_ADAPTERS_SPEC.md for the canonical request/result contracts.
"""

from abc import ABC, abstractmethod
from typing import Any


class SkillResult:
    """Normalized result from a skill adapter.

    Matches the canonical result contract from SKILL_ADAPTERS_SPEC.md.
    """

    def __init__(
        self,
        adapter: str,
        status: str,
        summary: str,
        artifacts: list[str],
        gate_changes: dict[str, bool],
        warnings: list[str] | None = None,
    ) -> None:
        if status not in ("pass", "warn", "fail"):
            raise ValueError(f"Invalid status: {status}. Must be pass, warn, or fail.")
        self.adapter = adapter
        self.status = status
        self.summary = summary
        self.artifacts = artifacts
        self.gate_changes = gate_changes
        self.warnings = warnings or []

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the canonical result schema."""
        return {
            "adapter": self.adapter,
            "status": self.status,
            "summary": self.summary,
            "artifacts": self.artifacts,
            "gate_changes": self.gate_changes,
            "warnings": self.warnings,
        }


class SkillAdapter(ABC):
    """Port for invoking domain skills through a normalized interface.

    Adapters isolate skill-specific folder structure and API details from the
    orchestrator. The orchestrator only sees the SkillAdapter contract.
    """

    @abstractmethod
    def execute(
        self,
        command: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        """Execute a skill command and return a normalized result.

        Args:
            command: Skill-specific command (e.g. 'search', 'screen').
            inputs: Normalized input parameters (query, paths, options).
            context: Execution context (state_file, cwd, stage).

        Returns:
            SkillResult with status, summary, artifacts, and gate_changes.

        Raises:
            ValueError: If the command is not recognized by this adapter.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter name for logging and result attribution."""
        pass
