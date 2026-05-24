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
        """Enforces schema invariants and stage-gates consistency.

        Checks:
        1. Stage name is valid
        2. All required gates present and boolean-typed
        3. Stage preconditions are consistent with gate values
           (a stage cannot be entered unless its precondition gates are True)
        """
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

        # Stage-gates consistency: precondition gates for the current stage
        # must be True. This detects states where e.g. stage=rendering but
        # bib_normalized=False (an impossible state if transitions are correct).
        self._validate_stage_consistency()

    def _validate_stage_consistency(self) -> None:
        """Checks that the current stage's precondition gates are all True.

        For each stage, STAGE_PRECONDITIONS defines the gates required to
        ENTER that stage. If the system is AT a stage, those gates must be True.
        The bootstrap stage has no preconditions, so it always passes.
        """
        preconditions = self.STAGE_PRECONDITIONS.get(self.stage, set())
        violated: list[str] = []
        for gate in preconditions:
            if not self.gates.get(gate, False):
                violated.append(gate)

        if violated:
            raise DomainStateError(
                f"Stage-gates inconsistency at stage '{self.stage}': "
                f"precondition gates not satisfied: {sorted(violated)}. "
                f"A stage cannot be active unless its precondition gates are True."
            )

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
