import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.domain.state import DomainStateError, ManuscriptState
from harness.ports.action_runner import ActionRunner
from harness.ports.artifact_checker import ArtifactChecker
from harness.ports.tool_wrapper import ToolNotAvailableError, ToolWrapper
from harness.services.gates import (
    GateResult,
    validate_bib_normalized,
    validate_citation_verify_gate,
    validate_ethics_passed_gate,
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
        wrappers: dict[str, ToolWrapper] | None = None,
    ) -> None:
        self.repo_path = repo_path
        self.state_manager = state_manager
        self.checker = checker
        self.action_runner = action_runner
        self.wrappers = wrappers or {}

    def _build_command_log_payload(
        self, request: OrchestratorRequest, result: OrchestratorResult
    ) -> dict[str, Any]:
        """Build a structured, serializable payload for command execution logs."""
        return {
            "command": request.command,
            "requested_stage": request.requested_stage,
            "failure_policy": request.failure_policy,
            "args": request.args,
            "success": result.success,
            "exit_code": result.exit_code,
            "stage_before": result.stage_before,
            "stage_after": result.stage_after,
            "steps": result.steps,
            "blockers": result.blockers,
            "warnings": result.warnings,
            "artifacts": result.artifacts,
            "gate_changes": result.gate_changes,
            "state_changes": result.state_changes,
        }

    def _write_command_log_best_effort(
        self, request: OrchestratorRequest, result: OrchestratorResult
    ) -> None:
        """Persist a structured command log without affecting command success/failure."""
        try:
            payload = self._build_command_log_payload(request, result)
            self.action_runner.write_command_log(request.command, payload)
        except (OSError, RuntimeError, ValueError):
            return

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

        # Bootstrap state if command is init and state does not exist yet.
        # IMPORTANT: all gates start False. repo_initialized is only set
        # AFTER the verify phase confirms the scaffold exists.
        if request.command == "init" and not self.state_manager.exists():
            try:
                self.state_manager.state = ManuscriptState(
                    stage="bootstrap",
                    gates=dict.fromkeys(ManuscriptState.REQUIRED_GATES, False),
                )
                self.state_manager.save_state()
            except (DomainStateError, StateManagerError) as e:
                msg = f"Failed to bootstrap state: {e}"
                blockers.append(msg)
                steps.append({"step_id": "bootstrap_state", "status": "failed", "error": msg})
                fail_result = self._build_fail_result(result, steps, blockers, warnings)
                self._write_command_log_best_effort(request, fail_result)
                return fail_result

        # Load state
        stage_before = "bootstrap"
        state_dict: dict[str, Any] = {}
        if request.command != "init" or self.state_manager.exists():
            try:
                state_dict = self.state_manager.load_state()
                # Validate the loaded state — without this, a corrupted state.yaml
                # with invalid stage names or non-boolean gates would silently pass
                # through and the orchestrator would trust it. (O-9 fix)
                self.state_manager.validate_state(state_dict)
                stage_before = state_dict.get("stage", "bootstrap")
                result.stage_before = stage_before
            except StateManagerError as e:
                msg = f"Failed to load state: {e}"
                blockers.append(msg)
                steps.append({"step_id": "load_state", "status": "failed", "error": msg})
                fail_result = self._build_fail_result(result, steps, blockers, warnings)
                self._write_command_log_best_effort(request, fail_result)
                return fail_result
        else:
            result.stage_before = "bootstrap"

        steps.append({"step_id": "load_state", "status": "succeeded"})

        # Validate Preconditions
        try:
            self._validate_preconditions(
                request.command,
                stage_before,
                state_dict.get("gates", {}) if request.command != "init" else {},
            )
            steps.append({"step_id": "validate_preconditions", "status": "succeeded"})
        except ValueError as e:
            msg = f"Precondition failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "validate_preconditions", "status": "failed", "error": msg})
            fail_result = self._build_fail_result(result, steps, blockers, warnings)
            self._write_command_log_best_effort(request, fail_result)
            return fail_result

        # ----------------------------------------------------
        # 2. APPLY PHASE: Execute command action
        # ----------------------------------------------------
        try:
            # Trigger downstream gate reset if editing a draft
            if request.command in ("draft_section", "draft_all"):
                self.state_manager.reset_downstream_gates("draft")
            elif request.command in ("import_bib", "zotero_sync"):
                self.state_manager.reset_downstream_gates("bib")

            action_artifacts = self.action_runner.run_action(request.command, request.args)
            artifacts.extend(action_artifacts)
            steps.append({"step_id": "run_core_action", "status": "succeeded"})
        except (ValueError, StateManagerError, DomainStateError, OSError) as e:
            msg = f"Action failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "run_core_action", "status": "failed", "error": msg})
            fail_result = self._build_fail_result(result, steps, blockers, warnings)
            self._write_command_log_best_effort(request, fail_result)
            return fail_result

        # ----------------------------------------------------
        # 3. VERIFY PHASE: Evaluate gates and update state
        # ----------------------------------------------------
        # R2-BH4: Snapshot state before verify phase for rollback on failure
        _pre_verify_snapshot = None
        _sm_state = getattr(self.state_manager, "state", None)
        if _sm_state is not None:
            _pre_verify_snapshot = copy.deepcopy(_sm_state)
        try:
            gate_verdicts = self._run_gate_verification(request)
            is_draft = request.command in ("draft_section", "draft_all")

            for gate_verdict in gate_verdicts:
                # Record gate changes
                gate_changes[gate_verdict.gate] = gate_verdict.status in ["pass", "warn"]

                # Incomplete drafts are not command blockers
                if gate_verdict.blockers and not is_draft:
                    blockers.extend(gate_verdict.blockers)
                if gate_verdict.warnings:
                    warnings.extend(gate_verdict.warnings)

                step_status = (
                    "succeeded"
                    if (gate_verdict.status in ["pass", "warn"] or is_draft)
                    else "failed"
                )
                step_err = (
                    ", ".join(gate_verdict.blockers)
                    if gate_verdict.blockers and not is_draft
                    else None
                )
                steps.append(
                    {
                        "step_id": f"verify_gate_{gate_verdict.gate}",
                        "status": step_status,
                        "error": step_err,
                    }
                )

                # Persist state update
                self.state_manager.set_gate(gate_verdict.gate, gate_changes[gate_verdict.gate])

            # Check failure policy (bypass for draft_section since incomplete draft
            # is not a command failure)
            any_failed = any(v.status == "fail" for v in gate_verdicts)
            if any_failed and request.failure_policy == "stop_on_error" and not is_draft:
                fail_result = self._build_fail_result(
                    result, steps, blockers, warnings, artifacts, gate_changes
                )
                self._write_command_log_best_effort(request, fail_result)
                return fail_result

            # Transition stage if all verification gates passed (or warned) or if it's
            # draft_section (stage manager will handle transition)
            all_passed = all(gate_changes.get(v.gate, False) for v in gate_verdicts)
            if all_passed or is_draft:
                next_stage = self._get_next_stage(request.command, stage_before)
                if next_stage:
                    self.state_manager.set_stage(next_stage)
                    result.stage_after = next_stage
                else:
                    result.stage_after = stage_before
            else:
                result.stage_after = stage_before

            # Emit manifest after successful paper verify (stage is now 'rendered')
            if request.command == "verify" and result.stage_after == "rendered":
                full_snapshot = self.state_manager.load_state().get("gates", {})
                manifest_path = self.action_runner.emit_manifest(full_snapshot)
                artifacts.append(manifest_path)
                steps.append({"step_id": "emit_manifest", "status": "succeeded"})

            steps.append({"step_id": "persist_state", "status": "succeeded"})

        except (ValueError, StateManagerError, DomainStateError) as e:
            msg = f"Verification/Persistence failed: {e}"
            blockers.append(msg)
            steps.append({"step_id": "persist_state", "status": "failed", "error": msg})
            # R2-BH4: Roll back state to snapshot if persist failed mid-transaction
            if _pre_verify_snapshot is not None:
                try:
                    self.state_manager.state = _pre_verify_snapshot
                    self.state_manager.save_state()
                    steps.append({"step_id": "rollback_state", "status": "succeeded"})
                except Exception as rollback_err:
                    steps.append(
                        {
                            "step_id": "rollback_state",
                            "status": "failed",
                            "error": f"State rollback also failed: {rollback_err}",
                        }
                    )
            fail_result = self._build_fail_result(
                result, steps, blockers, warnings, artifacts, gate_changes
            )
            self._write_command_log_best_effort(request, fail_result)
            return fail_result

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
        self._write_command_log_best_effort(request, result)
        return result

    def _validate_preconditions(
        self,
        command: str,
        current_stage: str,
        current_gates: dict[str, Any] | None = None,
    ) -> None:
        """Verifies if the command is allowed in the current stage."""
        stage_order = ManuscriptState.STAGE_ORDER

        try:
            current_idx = stage_order.index(current_stage)
        except ValueError as e:
            raise ValueError(f"Unknown current stage: {current_stage}") from e

        # Precondition rules mapping command to minimum required stage
        command_min_stages = {
            "init": "bootstrap",
            "search": "search",
            "chain": "screen",  # chain requires search results to exist
            "screen": "screen",
            "export_bib": "screen",
            "draft_outline": "outline",
            "draft_section": "drafting",
            "draft_all": "drafting",
            "lint_bib": "validating",
            "check_refs": "validating",
            "lint_style": "validating",
            "audit_reporting": "validating",
            "audit_ethics": "outline",
            "audit_factuality": "screen",
            "audit_tables": "drafting",
            "audit_quality_appraisal": "screen",
            "audit_prose": "drafting",
            "audit_claims": "drafting",
            "audit_citations": "drafting",
            "audit_writing_quality": "drafting",
            "audit_code_health": "outline",
            "protocol": "screen",
            "render": "rendering",
            "import_bib": "bootstrap",
            "zotero_sync": "bootstrap",
            "verify": "rendered",
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

        if command == "verify":
            gates = current_gates or {}
            if not gates.get("render_passed", False):
                raise ValueError(
                    "Command 'verify' requires gate 'render_passed' to be True. "
                    "Run 'paper render' successfully before verification."
                )

    def _run_gate_verification(self, request: OrchestratorRequest) -> list[GateResult]:
        """Invokes the gate verifiers corresponding to the executed command.

        For validation commands (lint_bib, check_refs, lint_style, audit_reporting),
        uses real ToolWrapper instances instead of inline mocked results.
        If no wrapper is registered for a command, fails closed with an explicit blocker.
        """
        cmd = request.command

        if cmd == "init":
            return [validate_repo_initialized(self.checker)]
        elif cmd == "search":
            return [validate_search_completed(self.checker)]
        elif cmd == "chain":
            return [validate_search_completed(self.checker)]
        elif cmd == "screen":
            return [validate_screened_evidence(self.checker)]
        elif cmd == "export_bib":
            return [validate_screened_evidence(self.checker)]
        elif cmd == "draft_outline":
            return [validate_outline_drafted(self.checker)]
        elif cmd == "draft_section":
            return [validate_sections_completed(self.checker)]
        elif cmd == "lint_bib":
            return [self._run_wrapper_gate("lint_bib")]
        elif cmd == "check_refs":
            results = [
                self._run_wrapper_gate("check_refs", gate_override="citations_resolved"),
                self._run_wrapper_gate("check_refs_metadata", gate_override="refs_validated"),
            ]
            # Soft gate: if refs are resolved, citations are verified
            all_ok = all(r.status in ("pass", "warn") for r in results)
            status = "pass" if all_ok else "warn"

            # Compute tiered gate verdict
            from validators.gate_verdict import tier_from_findings

            # Collect findings from upstream gate results
            citation_findings = []
            for r in results:
                for b in r.blockers:
                    citation_findings.append({"severity": "P0", "message": b})
                for w in r.warnings:
                    citation_findings.append({"severity": "P2", "message": w})
            verdict = tier_from_findings(citation_findings)

            results.append(
                GateResult(
                    gate="citation_verified",
                    status=status,
                    blockers=[],
                    warnings=(
                        [] if all_ok else ["Citations not fully verified — check refs output"]
                    ),
                    artifacts=[],
                    gate_verdict=verdict.to_dict(),
                )
            )
            return results
        elif cmd == "lint_style":
            return [self._run_wrapper_gate("lint_style")]
        elif cmd == "audit_reporting":
            return [self._run_wrapper_gate("audit_reporting")]
        elif cmd == "audit_ethics":
            return [self._run_wrapper_gate("audit_ethics", gate_override="ethics_passed")]
        elif cmd == "render":
            wrapper_result = self._run_wrapper_gate("render", request_args=request.args)
            # Only check artifact existence if the wrapper succeeded.
            # If the renderer itself reports failure, the artifact check is
            # redundant (and may give misleading results if the action runner
            # mock-populated paths regardless).
            if wrapper_result.status in ("pass", "warn"):
                return [wrapper_result, validate_render_passed(self.checker)]
            return [wrapper_result]
        elif cmd in ("import_bib", "zotero_sync"):
            wrapper_key = "zotero_sync" if cmd == "zotero_sync" else "import_bib"
            wrapper_result = self._run_wrapper_gate(wrapper_key, request_args=request.args)
            # Chain bib_normalized validation when the wrapper succeeds so the gate
            # is evaluated immediately after import/sync (mirrors render → render_passed chain).
            if wrapper_result.status in ("pass", "warn"):
                return [wrapper_result, validate_bib_normalized(self.checker)]
            return [wrapper_result]
        elif cmd == "verify":
            state_gates = self.state_manager.load_state().get("gates", {})
            return [
                validate_ready_for_delivery(self.checker, state_gates),
                validate_citation_verify_gate(self.checker, state_gates),
                validate_ethics_passed_gate(self.checker, state_gates),
            ]
        elif cmd == "draft_all":
            return [validate_sections_completed(self.checker)]
        elif cmd == "protocol":
            return [validate_screened_evidence(self.checker)]
        elif cmd == "audit_factuality":
            return [validate_screened_evidence(self.checker)]
        elif cmd == "audit_tables":
            return [validate_sections_completed(self.checker)]
        elif cmd == "audit_quality_appraisal":
            return [validate_screened_evidence(self.checker)]
        elif cmd == "audit_prose":
            return [self._run_wrapper_gate("audit_prose", gate_override="style_passed")]
        elif cmd == "audit_claims":
            return [self._run_wrapper_gate("audit_claims", gate_override="style_passed")]
        elif cmd == "audit_citations":
            return [self._run_wrapper_gate("audit_citations", gate_override="citations_resolved")]
        elif cmd == "audit_writing_quality":
            return [self._run_wrapper_gate("audit_writing_quality", gate_override="style_passed")]
        elif cmd == "audit_code_health":
            return [self._run_wrapper_gate("audit_code_health", gate_override="style_passed")]

        raise ValueError(f"Unknown gate verification for command: {cmd}")

    def _get_next_stage(self, command: str, current_stage: str) -> str | None:
        """Calculates the target stage based on completed action."""
        if command == "init":
            return "search"
        elif command == "search":
            return "screen"
        elif command == "chain":
            return "screen"  # chain produces more search results, advances to screen-ready
        elif command == "export_bib":
            return None  # export doesn't advance pipeline stage
        elif command == "screen":
            return "outline"
        elif command == "draft_outline":
            return "drafting"
        elif command == "draft_section":
            gate_res = validate_sections_completed(self.checker)
            if gate_res.status == "pass" and current_stage == "drafting":
                return "validating"
        elif command == "draft_all":
            gate_res = validate_sections_completed(self.checker)
            if gate_res.status == "pass" and current_stage == "drafting":
                return "validating"
        elif command in ["lint_bib", "check_refs", "lint_style", "audit_reporting"]:
            state_gates = self.state_manager.load_state().get("gates", {})
            validation_gates = ManuscriptState.STAGE_PRECONDITIONS["rendering"]
            if all(state_gates.get(g, False) for g in validation_gates):
                return "rendering"
        elif command == "render":
            return "rendered"
        elif command == "verify":
            return "rendered"
        return None

    def _run_wrapper_gate(
        self,
        command: str,
        gate_override: str | None = None,
        request_args: dict[str, Any] | None = None,
    ) -> GateResult:
        """Run a tool wrapper and convert its ValidatorResult to a GateResult.

        Fails closed if:
        - No wrapper is registered for the command
        - The wrapper raises ToolNotAvailableError
        - The wrapper returns status=fail
        """
        wrapper = self.wrappers.get(command)

        if wrapper is None:
            gate_name = gate_override or command
            return GateResult(
                gate=gate_name,
                status="fail",
                blockers=[f"No tool wrapper registered for command '{command}'."],
                warnings=[],
                artifacts=[],
            )

        gate_name = gate_override or wrapper.gate

        try:
            if request_args:
                artifacts_input = self._build_wrapper_artifacts_with_args(command, request_args)
            else:
                artifacts_input = self._build_wrapper_artifacts(command)
            context = {"cwd": str(self.repo_path)}

            validator_result = wrapper.run(artifacts_input, context)

            # Convert ValidatorResult to the dict format expected by validate_validator_gate
            result_dict = validator_result.to_dict()
            return validate_validator_gate(gate_name, result_dict)

        except ToolNotAvailableError as e:
            return GateResult(
                gate=gate_name,
                status="fail",
                blockers=[
                    f"Tool not available for gate '{gate_name}': {e}. "
                    f"Install '{e.tool_name}' to enable this validation."
                ],
                warnings=[],
                artifacts=[],
            )
        except (ValueError, OSError, RuntimeError) as e:
            return GateResult(
                gate=gate_name,
                status="fail",
                blockers=[f"Wrapper '{wrapper.name}' failed: {e}"],
                warnings=[],
                artifacts=[],
            )

    def _build_wrapper_artifacts(self, command: str) -> dict[str, Any]:
        """Build the artifacts input dict for a tool wrapper based on command."""
        from harness.ports.assets import get_project_asset

        bib_path = str(get_project_asset(self.repo_path, "templates", "references.bib"))
        draft_dir = self.repo_path / "outputs" / "latest" / "drafts"
        manuscript_files = (
            [str(f) for f in sorted(draft_dir.glob("*.md"))] if draft_dir.is_dir() else []
        )

        base: dict[str, Any] = {
            "bibliography": bib_path,
            "manuscript_files": manuscript_files,
        }

        if command == "audit_reporting":
            outline_path = str(draft_dir / "outline.md")
            base["outline"] = outline_path

        if command == "render":
            render_dir = self.repo_path / "outputs" / "latest" / "render"
            base["output_dir"] = str(render_dir)
            # Priority: assembled manuscript (real content) > placeholder template
            assembled = draft_dir / "manuscript.md"
            manuscript_qmd = get_project_asset(self.repo_path, "templates", "manuscript.qmd")
            if assembled.is_file():
                base["manuscript"] = str(assembled)
            elif manuscript_qmd.is_file():
                base["manuscript"] = str(manuscript_qmd)
            elif manuscript_files:
                base["manuscript"] = manuscript_files[0]

        return base

    def _build_wrapper_artifacts_with_args(
        self, command: str, request_args: dict[str, Any]
    ) -> dict[str, Any]:
        """Build artifacts dict including CLI-passed render/import options."""
        base = self._build_wrapper_artifacts(command)

        if command == "render":
            if "output_formats" in request_args:
                base["output_formats"] = request_args["output_formats"]
            if request_args.get("csl"):
                base["csl"] = request_args["csl"]
            if request_args.get("reference_doc"):
                base["reference_doc"] = request_args["reference_doc"]

        if command in ("import_bib", "zotero_sync"):
            base["source_bib"] = request_args.get("source_bib", "")
            base["target_bib"] = request_args.get("target_bib", "templates/references.bib")
            base["from_zotero"] = request_args.get("from_zotero", False)
            base["collection_key"] = request_args.get("collection_key")
            base["since_version"] = request_args.get("since_version")
            base["bbt_local"] = request_args.get("bbt_local", False)

        return base

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
