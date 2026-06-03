import argparse
import importlib.metadata
import sys
from pathlib import Path
from typing import Any

from cli.paper.commands.audit import (
    _cmd_audit_citations,
    _cmd_audit_claims,
    _cmd_audit_code_health,
    _cmd_audit_ethics,
    _cmd_audit_prose,
    _cmd_audit_writing_quality,
)
from cli.paper.commands.gate import _cmd_gate_method
from cli.paper.commands.graph import _cmd_graph_overview, _cmd_trace
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

    # paper audit citations
    audit_citations = audit_sub.add_parser(
        "citations", help="Verify citations against Crossref + Semantic Scholar."
    )
    audit_citations.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_citations.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_citations.add_argument(
        "--offline", action="store_true", help="Skip API calls (offline mode)"
    )
    audit_citations.set_defaults(func=_cmd_audit_citations)

    # paper audit ethics
    audit_ethics = audit_sub.add_parser("ethics", help="Check AI disclosure compliance.")
    audit_ethics.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_ethics.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_ethics.set_defaults(func=_cmd_audit_ethics)

    # paper audit writing-quality
    audit_wq = audit_sub.add_parser("writing-quality", help="Detect AI-typical writing patterns.")
    audit_wq.add_argument("file", help="Path to manuscript file (.md, .tex, .txt)")
    audit_wq.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    audit_wq.add_argument("--whitelist", "-w", action="append", default=[], help="Terms to skip")
    audit_wq.set_defaults(func=_cmd_audit_writing_quality)

    # paper trace — code traceability via Trifecta graph
    trace_parser = subparsers.add_parser(
        "trace", help="Trace code structure (callers, callees, paths) via Trifecta graph."
    )
    trace_parser.add_argument("symbol", help="Symbol to trace (e.g. 'Orchestrator.execute')")
    trace_parser.add_argument(
        "--action",
        "-a",
        choices=["callers", "callees", "path"],
        default="callers",
        help="Trace action (default: callers)",
    )
    trace_parser.add_argument(
        "--to",
        dest="to_symbol",
        default=None,
        help="Target symbol (required for 'path' action)",
    )
    trace_parser.add_argument(
        "--depth",
        "-d",
        type=int,
        default=1,
        help="Traversal depth for callers (1=direct, 3=transitive). Default: 1",
    )
    trace_parser.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    trace_parser.set_defaults(func=_cmd_trace)

    # paper graph-overview — graph health summary
    overview_parser = subparsers.add_parser(
        "graph-overview",
        help="Show Trifecta graph health overview (nodes, edges, cycles, orphans, hubs).",
    )
    overview_parser.add_argument("--output", "-o", choices=["terminal", "json"], default="terminal")
    overview_parser.set_defaults(func=_cmd_graph_overview)

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
