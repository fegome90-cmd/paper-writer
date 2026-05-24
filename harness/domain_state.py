from dataclasses import dataclass, field
from typing import ClassVar


class DomainStateError(Exception):
    """Raised for validation and transition violations in the domain."""

    pass


@dataclass
class ManuscriptState:
    """Core domain entity representing the manuscript pipeline state.

    Contains pure business logic and knows nothing of infrastructure (files, YAML).
    """

    stage: str
    gates: dict[str, bool] = field(default_factory=dict)

    VALID_STAGES: ClassVar[set[str]] = {
        "bootstrap",
        "search",
        "screen",
        "outline",
        "drafting",
        "validating",
        "rendering",
        "verified",
    }

    REQUIRED_GATES: ClassVar[set[str]] = {
        "repo_initialized",
        "search_completed",
        "screened_evidence",
        "outline_drafted",
        "sections_completed",
        "bib_normalized",
        "citations_resolved",
        "refs_validated",
        "style_passed",
        "reporting_passed",
        "render_passed",
        "ready_for_delivery",
    }

    # Preconditions required to ENTER a stage
    STAGE_PRECONDITIONS: ClassVar[dict[str, set[str]]] = {
        "bootstrap": set(),
        "search": {"repo_initialized"},
        "screen": {"search_completed"},
        "outline": {"screened_evidence"},
        "drafting": {"outline_drafted"},
        "validating": {"sections_completed"},
        "rendering": {
            "bib_normalized",
            "citations_resolved",
            "refs_validated",
            "style_passed",
            "reporting_passed",
        },
        "verified": {"render_passed"},
    }

    def validate(self) -> None:
        """Enforces schema invariants of the manuscript state."""
        if self.stage not in self.VALID_STAGES:
            raise DomainStateError(f"Invalid stage name: {self.stage}")

        if not isinstance(self.gates, dict):
            raise DomainStateError("Gates must be a dictionary.")

        missing_gates = self.REQUIRED_GATES - set(self.gates.keys())
        if missing_gates:
            raise DomainStateError(f"Missing required gates: {missing_gates}")

        for gate, value in self.gates.items():
            if gate not in self.REQUIRED_GATES:
                raise DomainStateError(f"Unknown gate key: {gate}")
            if not isinstance(value, bool):
                raise DomainStateError(f"Gate '{gate}' value must be boolean.")

    def set_gate(self, gate_name: str, value: bool) -> None:
        """Updates a single gate value."""
        if gate_name not in self.REQUIRED_GATES:
            raise DomainStateError(f"Unknown gate: {gate_name}")
        self.gates[gate_name] = value

    def transition_to(self, stage_name: str) -> None:
        """Changes the current stage after validating transition preconditions."""
        if stage_name not in self.VALID_STAGES:
            raise DomainStateError(f"Invalid target stage: {stage_name}")

        preconditions = self.STAGE_PRECONDITIONS.get(stage_name, set())
        for gate in preconditions:
            if not self.gates.get(gate, False):
                raise DomainStateError(
                    f"Cannot enter stage '{stage_name}': precondition gate '{gate}' is not True."
                )
        self.stage = stage_name

    def reset_downstream_gates(self, modified_artifact_type: str) -> None:
        """Clears dependent gates when an artifact is modified."""
        if modified_artifact_type == "draft":
            resets = [
                "citations_resolved",
                "style_passed",
                "reporting_passed",
                "render_passed",
                "ready_for_delivery",
            ]
        elif modified_artifact_type == "bib":
            resets = [
                "bib_normalized",
                "refs_validated",
                "render_passed",
                "ready_for_delivery",
            ]
        else:
            raise DomainStateError(f"Unknown artifact type for reset: {modified_artifact_type}")

        for gate in resets:
            self.gates[gate] = False
