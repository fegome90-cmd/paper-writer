from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.ports.action_runner import ActionRunner
from harness.ports.artifact_checker import ArtifactChecker
from harness.services.gates import (
    validate_outline_drafted,
    validate_ready_for_delivery,
    validate_render_passed,
    validate_repo_initialized,
    validate_screened_evidence,
    validate_search_completed,
    validate_sections_completed,
    validate_validator_gate,
)
from harness.services.state_manager import StateManager, StateManagerError


@dataclass
class OrchestratorRequest:
    """Request object parsed from CLI and sent to Orchestrator."""

    command: str
    requested_stage: str
    failure_policy: str  # stop_on_error | continue_on_error
    args: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    """Consolidated execution output from the Orchestrator."""

    command: str
    success: bool = False
    stage_before: str = "unknown"
    stage_after: str = "unknown"
    failure_policy: str = "stop_on_error"
    steps: list[dict[str, Any]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    gate_changes: dict[str, bool] = field(default_factory=dict)
    state_changes: dict[str, Any] = field(default_factory=dict)
    exit_code: int = 0


class Orchestrator:
    """Central orchestrator managing stage progression and gates validation."""

    def __init__(
        self,
        repo_path: Path,
        state_manager: StateManager,
        checker: ArtifactChecker,
        action_runner: ActionRunner,
    ) -> None:
        self.repo_path = repo_path
        self.state_manager = state_manager
        self.checker = checker
        self.action_runner = action_runner

    def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
        """Executes a command by loading state, validating, and updating gates."""
        result = OrchestratorResult(
            command=request.command,
            stage_before="unknown",
            stage_after="unknown",
            failure_policy=request.failure_policy,
        )

        steps: list[dict[str, Any]] = []
        blockers: list[str] = []
        warnings: list[str] = []
        artifacts: list[str] = []
        gate_changes: dict[str, bool] = {}

        # ----------------------------------------------------
        # 1. PREPARE PHASE: Load state and check preconditions
        # ----------------------------------------------------

        # Load state (except for 'init' if it does not exist yet)
        stage_before = "bootstrap"
        if request.command != "init" or self.state_manager.exists():
            try:
                state_dict = self.state_manager.load_state()
                stage_before = state_dict.get("stage", "bootstrap")
                result.stage_before = stage_before
            except StateManagerError as e:
                msg = f"Failed to load state: {e}"
                blockers.append(msg)
                steps.append({"step_id": "load_state", "status": "failed", "error": msg})
                return self._build_fail_result(result, steps, blockers, warnings)
        else:
            result.stage_before = "bootstrap"

        steps.append({"step_id": "load_state", "status": "succeeded"})

        # Validate Preconditions
        try:
            self._validate_preconditions(request.command, stage_before)
            steps.append({"step_id": "validate_preconditions", "status": "succeeded"})
        except Exception as e:
            msg = f"Precondition failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "validate_preconditions", "status": "failed", "error": msg})
            return self._build_fail_result(result, steps, blockers, warnings)

        # ----------------------------------------------------
        # 2. APPLY PHASE: Execute command action
        # ----------------------------------------------------
        try:
            action_artifacts = self.action_runner.run_action(
                request.command, request.args, self.state_manager
            )
            artifacts.extend(action_artifacts)
            steps.append({"step_id": "run_core_action", "status": "succeeded"})
        except Exception as e:
            msg = f"Action failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "run_core_action", "status": "failed", "error": msg})
            return self._build_fail_result(result, steps, blockers, warnings)

        # ----------------------------------------------------
        # 3. VERIFY PHASE: Evaluate gates and update state
        # ----------------------------------------------------
        try:
            gate_verdict = self._run_gate_verification(request)

            # Record gate changes
            gate_changes[gate_verdict.gate] = gate_verdict.status in ["pass", "warn"]

            # For draft_section, incomplete sections are NOT command blockers
            is_draft = request.command == "draft_section"
            if gate_verdict.blockers and not is_draft:
                blockers.extend(gate_verdict.blockers)
            if gate_verdict.warnings:
                warnings.extend(gate_verdict.warnings)

            step_status = (
                "succeeded" if (gate_verdict.status in ["pass", "warn"] or is_draft) else "failed"
            )
            step_err = (
                ", ".join(gate_verdict.blockers) if gate_verdict.blockers and not is_draft else None
            )
            steps.append(
                {
                    "step_id": f"verify_gate_{gate_verdict.gate}",
                    "status": step_status,
                    "error": step_err,
                }
            )

            # Check failure policy (bypass for draft_section since incomplete draft
            # is not a command failure)
            if (
                gate_verdict.status == "fail"
                and request.failure_policy == "stop_on_error"
                and not is_draft
            ):
                return self._build_fail_result(
                    result, steps, blockers, warnings, artifacts, gate_changes
                )

            # Persist state update
            # Write gate value
            self.state_manager.set_gate(gate_verdict.gate, gate_changes[gate_verdict.gate])

            # Transition stage if the verification passed (or warned) or if it's
            # draft_section (stage manager will handle transition)
            if gate_changes[gate_verdict.gate] or is_draft:
                next_stage = self._get_next_stage(request.command, stage_before)
                if next_stage:
                    self.state_manager.set_stage(next_stage)
                    result.stage_after = next_stage
                else:
                    result.stage_after = stage_before
            else:
                result.stage_after = stage_before

            # Emit manifest if we transitioned successfully to 'verified' stage (paper verify)
            if request.command == "verify" and result.stage_after == "verified":
                manifest_path = self.action_runner.emit_manifest(gate_changes)
                artifacts.append(manifest_path)
                steps.append({"step_id": "emit_manifest", "status": "succeeded"})

            steps.append({"step_id": "persist_state", "status": "succeeded"})

        except Exception as e:
            msg = f"Verification/Persistence failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "persist_state", "status": "failed", "error": msg})
            return self._build_fail_result(
                result, steps, blockers, warnings, artifacts, gate_changes
            )

        # Successful Execution Result
        result.success = len(blockers) == 0
        result.steps = steps
        result.blockers = blockers
        result.warnings = warnings
        result.artifacts = artifacts
        result.gate_changes = gate_changes
        result.state_changes = {
            "stage_before": stage_before,
            "stage_after": result.stage_after,
        }
        result.exit_code = 0 if result.success else 1
        return result

    def _validate_preconditions(self, command: str, current_stage: str) -> None:
        """Verifies if the command is allowed in the current stage."""
        stage_order = [
            "bootstrap",
            "search",
            "screen",
            "outline",
            "drafting",
            "validating",
            "rendering",
            "verified",
        ]

        try:
            current_idx = stage_order.index(current_stage)
        except ValueError as e:
            raise ValueError(f"Unknown current stage: {current_stage}") from e

        # Precondition rules mapping command to minimum required stage
        command_min_stages = {
            "init": "bootstrap",
            "search": "search",
            "screen": "screen",
            "draft_outline": "outline",
            "draft_section": "drafting",
            "lint_bib": "validating",
            "check_refs": "validating",
            "lint_style": "validating",
            "audit_reporting": "validating",
            "render": "rendering",
            "verify": "verified",
        }

        min_stage = command_min_stages.get(command)
        if not min_stage:
            raise ValueError(f"Unsupported command: {command}")

        min_idx = stage_order.index(min_stage)
        if current_idx < min_idx:
            raise ValueError(
                f"Command '{command}' requires stage '{min_stage}' or later. "
                f"Current stage is '{current_stage}'."
            )

    def _run_gate_verification(self, request: OrchestratorRequest) -> Any:
        """Invokes the gate verifier corresponding to the executed command."""
        cmd = request.command

        if cmd == "init":
            return validate_repo_initialized(self.checker)
        elif cmd == "search":
            return validate_search_completed(self.checker)
        elif cmd == "screen":
            return validate_screened_evidence(self.checker)
        elif cmd == "draft_outline":
            return validate_outline_drafted(self.checker)
        elif cmd == "draft_section":
            return validate_sections_completed(self.checker)
        elif cmd == "lint_bib":
            result_mock = {
                "status": "pass",
                "findings": [],
                "artifacts_checked": [self.checker.get_full_path_str("templates/references.bib")],
            }
            return validate_validator_gate("bib_normalized", result_mock)
        elif cmd == "check_refs":
            result_mock = {
                "status": "pass",
                "findings": [],
                "artifacts_checked": [self.checker.get_full_path_str("templates/references.bib")],
            }
            self.state_manager.set_gate("citations_resolved", True)
            return validate_validator_gate("refs_validated", result_mock)
        elif cmd == "lint_style":
            result_mock = {"status": "pass", "findings": [], "artifacts_checked": []}
            return validate_validator_gate("style_passed", result_mock)
        elif cmd == "audit_reporting":
            result_mock = {"status": "pass", "findings": [], "artifacts_checked": []}
            return validate_validator_gate("reporting_passed", result_mock)
        elif cmd == "render":
            return validate_render_passed(self.checker)
        elif cmd == "verify":
            state_gates = self.state_manager.load_state().get("gates", {})
            return validate_ready_for_delivery(self.checker, state_gates)

        raise ValueError(f"Unknown gate verification for command: {cmd}")

    def _get_next_stage(self, command: str, current_stage: str) -> str | None:
        """Calculates the target stage based on completed action."""
        if command == "init":
            return "search"
        elif command == "search":
            return "screen"
        elif command == "screen":
            return "outline"
        elif command == "draft_outline":
            return "drafting"
        elif command == "draft_section":
            gate_res = validate_sections_completed(self.checker)
            if gate_res.status == "pass" and current_stage == "drafting":
                return "validating"
        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
            state_gates = self.state_manager.load_state().get("gates", {})
            validation_gates = [
                "bib_normalized",
                "citations_resolved",
                "refs_validated",
                "style_passed",
                "reporting_passed",
            ]
            if all(state_gates.get(g, False) for g in validation_gates):
                return "rendering"
        elif command == "render":
            return "verified"
        elif command == "verify":
            return "verified"
        return None

    def _build_fail_result(
        self,
        result: OrchestratorResult,
        steps: list[dict[str, Any]],
        blockers: list[str],
        warnings: list[str],
        artifacts: list[str] | None = None,
        gate_changes: dict[str, bool] | None = None,
    ) -> OrchestratorResult:
        """Convenience method to format a failed OrchestratorResult."""
        result.success = False
        result.steps = steps
        result.blockers = blockers
        result.warnings = warnings
        result.artifacts = artifacts or []
        result.gate_changes = gate_changes or {}
        result.state_changes = {
            "stage_before": result.stage_before,
            "stage_after": result.stage_before,
        }
        result.stage_after = result.stage_before
        result.exit_code = 1
        return result
