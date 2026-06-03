import argparse
import importlib.metadata
import sys
import time
from pathlib import Path
from typing import Any

from harness.services.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResult
from harness.services.orchestrator_builder import build_orchestrator_dependencies


def _get_version() -> str:
    """Get package version from metadata."""
    try:
        return importlib.metadata.version("paper-writer")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


MAX_ASCENDING_DEPTH = 20


def resolve_project_root(explicit_path: Path | None, cwd: Path) -> Path:
    """Resolve project root. Priority: flag → ascending search → CWD.

    Ascending search resolves symlinks via Path.resolve() before
    checking for outputs/state.yaml to prevent symlink injection.
    """
    if explicit_path is not None:
        resolved = explicit_path.resolve()
        if not resolved.is_dir():
            print(
                f"Error: Project path does not exist: {explicit_path}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return resolved

    # Ascending search for outputs/state.yaml (innermost match)
    candidate = cwd.resolve()
    for _ in range(MAX_ASCENDING_DEPTH):
        marker = candidate / "outputs" / "state.yaml"
        if marker.is_file():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break  # filesystem root
        candidate = parent

    # Fallback: CWD
    return cwd.resolve()


def _cmd_audit_prose(args: argparse.Namespace) -> None:
    """Run prose analysis (Phase 0)."""
    import json

    from engine.formatter import format_terminal
    from parsers.manuscript import ManuscriptParser
    from validators.prose import ProseValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = ProseValidator(whitelist=set(args.whitelist or []))
    findings = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    by_sev: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    by_cat: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "P2")
        by_sev[sev] = by_sev.get(sev, 0) + 1
        rg = f.get("rule_id", "").rsplit(".", 1)[0]
        by_cat[rg] = by_cat.get(rg, 0) + 1

    result = {
        "command": "audit_prose",
        "file": str(path),
        "format": manuscript.format,
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "by_severity": by_sev,
            "by_category": by_cat,
        },
        "metadata": {
            "parser_version": "1.0",
            "rules_loaded": validator.rules_count,
            "rules_enabled": validator.rules_count,
            "execution_time_ms": elapsed,
        },
    }

    # Validate key fields against expected schema
    required_keys = {"command", "file", "findings", "summary", "metadata"}
    missing = required_keys - set(result.keys())
    if missing:
        print(f"Warning: result missing schema fields: {missing}", file=sys.stderr)

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_terminal(findings))


def _cmd_audit_claims(args: argparse.Namespace) -> None:
    """Run claim candidate detection (Phase 0)."""
    import json

    from parsers.manuscript import ManuscriptParser
    from validators.claims import ClaimsValidator, build_claims_report

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = ClaimsValidator(whitelist=set(args.whitelist or []))
    candidates = validator.validate(manuscript)
    elapsed = int((time.time() - t0) * 1000)

    result = build_claims_report(manuscript, candidates, elapsed, rules_loaded=len(validator.rules))

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        from engine.formatter import format_claims_output

        print(format_claims_output(result))


def _cmd_audit_code_health(args: argparse.Namespace) -> None:
    """Run code health audit using Trifecta graph index.

    Finds actionable dead code / orphan methods in the project, filtering
    out known false positives (tests, mixin inheritance, CLI dispatch).
    Requires MCP_TRIFECTA_MODE=real to be useful.
    """
    import json

    from validators.code_health import analyze_code_health

    t0 = time.time()
    report = analyze_code_health()
    elapsed = int((time.time() - t0) * 1000)

    output = {
        "summary": report.summary(),
        "trifecta_enabled": report.trifecta_enabled,
        "actionable_count": len(report.findings),
        "filtered_count": report.filtered_count,
        "total_orphans_seen": report.total_orphans_seen,
        "elapsed_ms": elapsed,
        "error": report.error,
        "findings": [f.to_dict() for f in report.findings],
    }

    if args.output == "json":
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(output["summary"])
        if report.findings:
            print()
            for finding in report.findings:
                print(f"  {finding.file_rel}::{finding.symbol_name} ({finding.orphan_type})")
        if report.error:
            print(f"  Note: {report.error}", file=sys.stderr)

    # Exit 1 if there are actionable findings, 0 otherwise
    sys.exit(1 if report.findings else 0)


def _cmd_gate_method(args: argparse.Namespace) -> None:
    """Run methodological gate (Phase 0)."""
    import json

    from engine.formatter import format_gate_result
    from parsers.manuscript import ManuscriptParser
    from validators.method_gate import MethodGateValidator

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    t0 = time.time()
    manuscript = ManuscriptParser().parse(path)
    validator = MethodGateValidator()
    result = validator.validate(
        manuscript=manuscript,
        study_type=args.study_type,
        checklist_name=args.checklist,
        na_items=args.na,
    )
    elapsed = int((time.time() - t0) * 1000)
    result["metadata"]["execution_time_ms"] = elapsed

    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_gate_result(result))

    # Fail-closed: exit code 1 if gate blocked
    if not result.get("gate_passed", True):
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="paper CLI - Single entrypoint for scientific drafting CI/CD pipeline."
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=_get_version(),
    )
    parser.add_argument(
        "--project",
        "-C",
        default=None,
        type=Path,
        help="Project root directory (default: auto-detect from CWD).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # paper init
    init_parser = subparsers.add_parser("init", help="Initialize repository and state.")
    init_parser.add_argument(
        "--preset",
        default=None,
        help="Journal preset name (e.g. 'nature'). Loads from templates/journals/<name>/.",
    )

    # paper search
    search_parser = subparsers.add_parser("search", help="Execute scientific literature search.")
    search_parser.add_argument(
        "--raw-papers",
        help="Path to JSON file containing raw paper candidates.",
    )

    # paper screen
    subparsers.add_parser("screen", help="Screen search results to evidence set.")

    # paper draft
    draft_parser = subparsers.add_parser("draft", help="Draft outline or sections.")
    draft_sub = draft_parser.add_subparsers(dest="subcommand", required=True)
    draft_sub.add_parser("outline", help="Draft outline.")
    sec_parser = draft_sub.add_parser("section", help="Draft section.")
    sec_parser.add_argument(
        "name", help="Section name (introduction, methods, results, discussion)"
    )

    # paper lint
    lint_parser = subparsers.add_parser("lint", help="Lint bibliography or style.")
    lint_sub = lint_parser.add_subparsers(dest="subcommand", required=True)
    lint_sub.add_parser("bib", help="Lint and normalize references.bib.")
    lint_sub.add_parser("style", help="Lint styling rules.")

    # paper check
    check_parser = subparsers.add_parser(
        "check", help="Check citations and references consistency."
    )
    check_sub = check_parser.add_subparsers(dest="subcommand", required=True)
    check_sub.add_parser("refs", help="Check inline citations against references.bib.")

    # paper audit (Phase 0 + existing)
    audit_parser = subparsers.add_parser("audit", help="Audit manuscript quality.")
    audit_sub = audit_parser.add_subparsers(dest="subcommand", required=True)
    audit_sub.add_parser("reporting", help="Audit manuscript against reporting checklists.")
    audit_prose = audit_sub.add_parser("prose", help="Analyze scientific prose quality (Phase 0).")
    audit_prose.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_prose.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_prose.add_argument("--whitelist", "-w", action="append", default=[], help="Terms to skip")
    audit_prose.set_defaults(func=_cmd_audit_prose)
    audit_claims = audit_sub.add_parser("claims", help="Detect claim candidates (Phase 0).")
    audit_claims.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_claims.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_claims.add_argument(
        "--whitelist", "-w", action="append", default=[], help="Terms to skip"
    )
    audit_claims.set_defaults(func=_cmd_audit_claims)
    audit_code_health = audit_sub.add_parser(
        "code-health",
        help="Audit code health (dead code, unused methods) via Trifecta graph.",
    )
    audit_code_health.add_argument(
        "--output", "-o", choices=["terminal", "json"], default="terminal"
    )
    audit_code_health.set_defaults(func=_cmd_audit_code_health)

    # paper gate (Phase 0)
    gate_parser = subparsers.add_parser(
        "gate", help="Run fail-closed methodological gates (Phase 0)."
    )
    gate_sub = gate_parser.add_subparsers(dest="subcommand", required=True)
    gate_method = gate_sub.add_parser("method", help="Apply EQUATOR-derived checklist gate.")
    gate_method.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    gate_method.add_argument(
        "--study-type",
        "-t",
        default="*",
        choices=[
            "*",
            "rct",
            "randomized_controlled_trial",
            "randomised_controlled_trial",
            "cohort",
            "case_control",
            "cross_sectional",
            "observational",
            "prospective",
            "retrospective",
            "systematic_review",
            "meta_analysis",
            "scoping_review",
            "literature_review",
            "narrative_review",
            "qualitative",
        ],
        help="Study type for checklist selection",
    )
    gate_method.add_argument(
        "--checklist",
        "-c",
        default=None,
        help="Explicit checklist name (e.g. 'consort', 'strobe', 'prisma')",
    )
    gate_method.add_argument(
        "--na", action="append", default=[], help="Item ID to mark as not applicable (repeatable)"
    )
    gate_method.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    gate_method.set_defaults(func=_cmd_gate_method)

    # paper import
    import_parser = subparsers.add_parser("import", help="Import external resources.")
    import_sub = import_parser.add_subparsers(dest="subcommand", required=True)
    import_bib = import_sub.add_parser("bib", help="Import .bib from Zotero/Better BibTeX export.")
    import_bib.add_argument("source", help="Path to source .bib file to import.")
    import_bib.add_argument(
        "--target",
        default="templates/references.bib",
        help="Target bibliography path (default: templates/references.bib).",
    )

    # paper render
    render_parser = subparsers.add_parser("render", help="Render final output formats.")
    render_parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=["docx", "pdf"],
        default=None,
        help="Output format(s). Can be repeated. Default: docx and pdf.",
    )
    render_parser.add_argument(
        "--csl",
        default=None,
        help="Path to CSL citation style file (e.g. styles/csl/vancouver.csl).",
    )
    render_parser.add_argument(
        "--reference-doc",
        default=None,
        help="Path to reference docx for styling.",
    )

    # paper verify
    subparsers.add_parser("verify", help="Run final verification check.")

    # paper doctor
    subparsers.add_parser("doctor", help="Check environment and report tool status.")

    args = parser.parse_args()

    # Phase 0 commands (audit prose, audit claims, gate method) — run directly
    func = getattr(args, "func", None)
    if func is not None:
        func(args)
        return

    # paper doctor — runs directly, exits directly
    if args.command == "doctor":
        from harness.services.doctor import (
            check_all_tools,
            check_internal_capabilities,
            format_doctor_report,
        )

        repo_path = resolve_project_root(args.project, Path.cwd())
        tools = check_all_tools()
        caps = check_internal_capabilities(repo_path)
        print(format_doctor_report(tools, caps))
        sys.exit(0)

    # Map parsed arguments to OrchestratorRequest
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)

    orch_command = cmd_name
    orch_args: dict[str, Any] = {}
    failure_policy = "stop_on_error"

    if cmd_name == "init":
        orch_args["preset"] = args.preset
    elif cmd_name == "search":
        if args.raw_papers:
            orch_args["raw_papers"] = args.raw_papers
    elif cmd_name == "draft":
        if sub_name == "outline":
            orch_command = "draft_outline"
        elif sub_name == "section":
            orch_command = "draft_section"
            orch_args["name"] = args.name
    elif cmd_name == "lint":
        failure_policy = "continue_on_error"
        if sub_name == "bib":
            orch_command = "lint_bib"
        elif sub_name == "style":
            orch_command = "lint_style"
    elif cmd_name == "check":
        failure_policy = "continue_on_error"
        if sub_name == "refs":
            orch_command = "check_refs"
    elif cmd_name == "audit":
        failure_policy = "continue_on_error"
        if sub_name == "reporting":
            orch_command = "audit_reporting"
    elif cmd_name == "import":
        if sub_name == "bib":
            orch_command = "import_bib"
            orch_args["source_bib"] = args.source
            orch_args["target_bib"] = args.target
    elif cmd_name == "render":
        orch_args["output_formats"] = args.formats if args.formats else ["docx", "pdf"]
        orch_args["csl"] = args.csl
        orch_args["reference_doc"] = args.reference_doc

    repo_path = resolve_project_root(args.project, Path.cwd())
    request = OrchestratorRequest(
        command=orch_command,
        requested_stage="unknown",
        failure_policy=failure_policy,
        args=orch_args,
        context={"cwd": str(repo_path), "actor": "cli"},
    )

    deps = build_orchestrator_dependencies(project_root=repo_path)
    orchestrator = Orchestrator(
        deps.repo_path,
        deps.state_manager,
        deps.checker,
        deps.action_runner,
        dict(deps.wrappers),
    )
    result = orchestrator.execute(request)

    # Format outputs
    _print_summary(result)
    sys.exit(result.exit_code)


def _print_summary(result: OrchestratorResult) -> None:
    """Outputs status-oriented console logs."""
    for step in result.steps:
        status = step.get("status")
        step_id = step.get("step_id")
        error = step.get("error")

        if status == "succeeded":
            print(f"[ok] Step: {step_id}")
        elif status == "failed":
            print(f"[!!] Step: {step_id} - FAILED")
            if error:
                print(f"     Error: {error}")
        else:
            print(f"[--] Step: {step_id} - {status.upper() if status else 'UNKNOWN'}")

    if result.success:
        print(
            f"\nSuccess: Stage progressed from '{result.stage_before}' to '{result.stage_after}'."
        )
    else:
        print("\nPipeline Blocked:")
        for blocker in result.blockers:
            print(f"  - {blocker}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.artifacts:
        print("\nArtifacts:")
        for artifact in result.artifacts:
            print(f"  - {artifact}")


if __name__ == "__main__":
    main()
