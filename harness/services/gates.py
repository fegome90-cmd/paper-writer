from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from harness.domain.state import ManuscriptState
from harness.ports.artifact_checker import ArtifactChecker


@dataclass
class Check:
    """A single verification check."""

    id: str
    description: str
    run_fn: Callable[[], None]
    soft: bool = False


@dataclass
class GateResult:
    """Structured result of a gate evaluation."""

    gate: str
    status: str  # pass | warn | fail
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


def run_gate(gate_name: str, checks: list[Check], artifacts: list[str]) -> GateResult:
    """Executes a list of checks for a gate and consolidates the outcome."""
    blockers: list[str] = []
    warnings: list[str] = []

    for check in checks:
        try:
            check.run_fn()
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            msg = f"{check.id}: {e}"
            if check.soft:
                warnings.append(msg)
            else:
                blockers.append(msg)

    # Determine gate status
    if blockers:
        status = "fail"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    return GateResult(
        gate=gate_name,
        status=status,
        blockers=blockers,
        warnings=warnings,
        artifacts=artifacts,
    )


# Concrete gate validators using the ArtifactChecker port


def validate_repo_initialized(checker: ArtifactChecker) -> GateResult:
    """Checks if project directories and state file exist."""
    required_dirs = ["templates", "outputs"]
    required_files = ["outputs/state.yaml"]
    checks = []

    for d in required_dirs:

        def make_check(name: str = d) -> Check:
            def run_fn() -> None:
                checker.check_dir_exists(name)

            return Check(
                id=f"dir_exists_{name}",
                description=f"Verify if {name} directory exists",
                run_fn=run_fn,
            )

        checks.append(make_check())

    for f in required_files:

        def make_file_check(name: str = f) -> Check:
            def run_fn() -> None:
                checker.check_file_exists(name)

            return Check(
                id=f"file_exists_{name}",
                description=f"Verify if {name} file exists",
                run_fn=run_fn,
            )

        checks.append(make_file_check())

    return run_gate(
        "repo_initialized",
        checks,
        [checker.get_full_path_str(d) for d in required_dirs]
        + [checker.get_full_path_str(f) for f in required_files],
    )


def validate_search_completed(checker: ArtifactChecker) -> GateResult:
    """Checks if search artifacts exist."""
    plan_file = "outputs/search/search_plan.json"
    results_file = "outputs/search/raw_results.json"

    def check_plan() -> None:
        checker.check_file_exists(plan_file)

    def check_results() -> None:
        checker.check_file_exists(results_file)

    checks = [
        Check(
            id="search_plan_exists",
            description="Verify if search_plan.json exists",
            run_fn=check_plan,
        ),
        Check(
            id="raw_results_exists",
            description="Verify if raw_results.json exists",
            run_fn=check_results,
        ),
    ]
    return run_gate(
        "search_completed",
        checks,
        [checker.get_full_path_str(plan_file), checker.get_full_path_str(results_file)],
    )


def validate_screened_evidence(checker: ArtifactChecker) -> GateResult:
    """Checks if screened evidence exists."""
    evidence_file = "outputs/search/screened_evidence.json"

    def check_evidence() -> None:
        checker.check_file_exists(evidence_file)

    checks = [
        Check(
            id="screened_evidence_exists",
            description="Verify if screened_evidence.json exists",
            run_fn=check_evidence,
        )
    ]
    return run_gate("screened_evidence", checks, [checker.get_full_path_str(evidence_file)])


def validate_outline_drafted(checker: ArtifactChecker) -> GateResult:
    """Checks if outline exists."""
    outline_file = "outputs/drafts/outline.md"

    def check_outline() -> None:
        checker.check_file_exists(outline_file)

    checks = [
        Check(
            id="outline_exists",
            description="Verify if outline.md exists",
            run_fn=check_outline,
        )
    ]
    return run_gate("outline_drafted", checks, [checker.get_full_path_str(outline_file)])


def validate_sections_completed(checker: ArtifactChecker) -> GateResult:
    """Checks if required sections exist."""
    required_sections = ["introduction.md", "methods.md", "results.md", "discussion.md"]
    checks = []

    for section in required_sections:
        sec_file = f"outputs/drafts/{section}"

        def make_check(file_path: str = sec_file, name: str = section) -> Check:
            def run_fn() -> None:
                checker.check_file_exists(file_path)

            return Check(
                id=f"section_exists_{name.split('.')[0]}",
                description=f"Verify if {name} exists",
                run_fn=run_fn,
            )

        checks.append(make_check())

    return run_gate(
        "sections_completed",
        checks,
        [checker.get_full_path_str(f"outputs/drafts/{s}") for s in required_sections],
    )


def validate_bib_normalized(checker: ArtifactChecker) -> GateResult:
    """Checks if references.bib is present."""
    bib_file = "templates/references.bib"

    def check_bib() -> None:
        checker.check_file_exists(bib_file)

    checks = [
        Check(
            id="references_bib_exists",
            description="Verify if references.bib exists in templates",
            run_fn=check_bib,
        )
    ]
    return run_gate("bib_normalized", checks, [checker.get_full_path_str(bib_file)])


def validate_validator_gate(gate_name: str, validator_result: dict[str, Any] | None) -> GateResult:
    """Generic validator gate evaluation."""
    if not validator_result:
        return GateResult(
            gate=gate_name,
            status="fail",
            blockers=[f"No validation results found for gate {gate_name}."],
        )

    status = validator_result.get("status", "fail")
    findings = validator_result.get("findings", [])
    artifacts_checked = validator_result.get("artifacts_checked", [])

    blockers = []
    warnings = []

    for f in findings:
        severity = f.get("severity", "error")
        msg = f"{f.get('code', 'finding')}: {f.get('message', 'Unknown issue')}"
        if severity == "error":
            blockers.append(msg)
        elif severity == "warning":
            warnings.append(msg)

    # Force fail status if blockers are present
    if blockers:
        status = "fail"
    elif status == "pass" and warnings:
        status = "warn"

    return GateResult(
        gate=gate_name,
        status=status,
        blockers=blockers,
        warnings=warnings,
        artifacts=artifacts_checked,
    )


def validate_render_passed(checker: ArtifactChecker) -> GateResult:
    """Checks if rendered document exists."""
    render_docx = "outputs/render/manuscript.docx"
    render_pdf = "outputs/render/manuscript.pdf"

    def check_render() -> None:
        checker.check_any_file_exists([render_docx, render_pdf])

    checks = [
        Check(
            id="render_output_exists",
            description="Verify if compiled docx or pdf exists",
            run_fn=check_render,
        )
    ]
    return run_gate(
        "render_passed",
        checks,
        [checker.get_full_path_str(render_docx), checker.get_full_path_str(render_pdf)],
    )


def validate_ready_for_delivery(
    checker: ArtifactChecker, state_gates: dict[str, Any]
) -> GateResult:
    """Final check gate."""
    # All gates except ready_for_delivery itself must be True
    required_gates = sorted(ManuscriptState.REQUIRED_GATES - {"ready_for_delivery"})

    checks = []
    for g in required_gates:

        def make_check(gate_name: str = g) -> Check:
            def run_fn() -> None:
                _assert_gate_true(state_gates, gate_name)

            return Check(
                id=f"gate_satisfied_{gate_name}",
                description=f"Verify if gate '{gate_name}' is satisfied",
                run_fn=run_fn,
            )

        checks.append(make_check())

    manifest_file = "outputs/manifest.yaml"
    return run_gate("ready_for_delivery", checks, [checker.get_full_path_str(manifest_file)])


# Helper assertions for Checks


def _assert_gate_true(gates: dict[str, Any], gate_name: str) -> None:
    if not gates.get(gate_name, False):
        raise ValueError(f"Required gate '{gate_name}' is not satisfied (must be True).")
