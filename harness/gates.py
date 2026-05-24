from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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


def run_gate(gate_name: str, checks: list[Check], artifacts: list[Path]) -> GateResult:
    """Executes a list of checks for a gate and consolidates the outcome."""
    blockers: list[str] = []
    warnings: list[str] = []

    for check in checks:
        try:
            check.run_fn()
        except Exception as e:
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
        artifacts=[str(a) for a in artifacts],
    )


# Concrete gate validators


def validate_repo_initialized(repo_path: Path) -> GateResult:
    """Checks if base folders exist."""
    required_dirs = ["cli", "harness", "validators", "templates", "outputs"]
    checks = []

    for d in required_dirs:
        dir_path = repo_path / d

        def make_check(path: Path = dir_path, name: str = d) -> Check:
            def run_fn() -> None:
                _assert_is_dir(path, name)

            return Check(
                id=f"dir_exists_{name}",
                description=f"Verify if {name} directory exists",
                run_fn=run_fn,
            )

        checks.append(make_check())

    return run_gate("repo_initialized", checks, [repo_path / d for d in required_dirs])


def validate_search_completed(repo_path: Path) -> GateResult:
    """Checks if search artifacts exist."""
    plan_file = repo_path / "outputs" / "search" / "search_plan.json"
    results_file = repo_path / "outputs" / "search" / "raw_results.json"

    def check_plan() -> None:
        _assert_is_file(plan_file, "Search Plan")

    def check_results() -> None:
        _assert_is_file(results_file, "Raw Results")

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
    return run_gate("search_completed", checks, [plan_file, results_file])


def validate_screened_evidence(repo_path: Path) -> GateResult:
    """Checks if screened evidence exists."""
    evidence_file = repo_path / "outputs" / "search" / "screened_evidence.json"

    def check_evidence() -> None:
        _assert_is_file(evidence_file, "Screened Evidence")

    checks = [
        Check(
            id="screened_evidence_exists",
            description="Verify if screened_evidence.json exists",
            run_fn=check_evidence,
        )
    ]
    return run_gate("screened_evidence", checks, [evidence_file])


def validate_outline_drafted(repo_path: Path) -> GateResult:
    """Checks if outline exists."""
    outline_file = repo_path / "outputs" / "drafts" / "outline.md"

    def check_outline() -> None:
        _assert_is_file(outline_file, "Outline")

    checks = [
        Check(id="outline_exists", description="Verify if outline.md exists", run_fn=check_outline)
    ]
    return run_gate("outline_drafted", checks, [outline_file])


def validate_sections_completed(repo_path: Path) -> GateResult:
    """Checks if required sections exist."""
    required_sections = ["introduction.md", "methods.md", "results.md", "discussion.md"]
    checks = []

    for section in required_sections:
        sec_file = repo_path / "outputs" / "drafts" / section

        def make_check(file_path: Path = sec_file, name: str = section) -> Check:
            def run_fn() -> None:
                _assert_is_file(file_path, name)

            return Check(
                id=f"section_exists_{name.split('.')[0]}",
                description=f"Verify if {name} exists",
                run_fn=run_fn,
            )

        checks.append(make_check())

    return run_gate(
        "sections_completed",
        checks,
        [repo_path / "outputs" / "drafts" / s for s in required_sections],
    )


def validate_bib_normalized(repo_path: Path) -> GateResult:
    """Checks if references.bib is present."""
    bib_file = repo_path / "templates" / "references.bib"

    def check_bib() -> None:
        _assert_is_file(bib_file, "References Bibliography")

    checks = [
        Check(
            id="references_bib_exists",
            description="Verify if references.bib exists in templates",
            run_fn=check_bib,
        )
    ]
    return run_gate("bib_normalized", checks, [bib_file])


def validate_validator_gate(gate_name: str, validator_result: dict[str, Any] | None) -> GateResult:
    """Generic validator gate evaluation.

    Consumes the output dict from a validator:
    {
        "status": "pass" | "warn" | "fail",
        "findings": [{"severity": "error"|"warning"|"info", "message": "..."}],
        "artifacts_checked": ["..."]
    }
    """
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


def validate_render_passed(repo_path: Path) -> GateResult:
    """Checks if rendered document exists."""
    render_docx = repo_path / "outputs" / "render" / "manuscript.docx"
    render_pdf = repo_path / "outputs" / "render" / "manuscript.pdf"

    def check_render() -> None:
        _assert_any_file_exists([render_docx, render_pdf], "Rendered manuscript")

    checks = [
        Check(
            id="render_output_exists",
            description="Verify if compiled docx or pdf exists",
            run_fn=check_render,
        )
    ]
    return run_gate("render_passed", checks, [render_docx, render_pdf])


def validate_ready_for_delivery(repo_path: Path, state_gates: dict[str, Any]) -> GateResult:
    """Final check gate.

    All gates except 'ready_for_delivery' must be 'True' (or 'pass'/'warn').
    """
    required_gates = [
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
    ]

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

    manifest_file = repo_path / "outputs" / "manifest.yaml"
    return run_gate("ready_for_delivery", checks, [manifest_file])


# Helper assertions for Checks


def _assert_is_dir(path: Path, name: str) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"Directory '{name}' not found at {path}")


def _assert_is_file(path: Path, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"File '{name}' not found at {path}")


def _assert_any_file_exists(paths: list[Path], name: str) -> None:
    if not any(p.is_file() for p in paths):
        raise FileNotFoundError(
            f"No rendered files found for '{name}'. Tried: {[str(p) for p in paths]}"
        )


def _assert_gate_true(gates: dict[str, Any], gate_name: str) -> None:
    if not gates.get(gate_name, False):
        raise ValueError(f"Required gate '{gate_name}' is not satisfied (must be True).")
