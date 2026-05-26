import argparse
import sys
from pathlib import Path
from typing import Any

from harness.services.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResult
from harness.services.orchestrator_builder import build_orchestrator_dependencies


def main() -> None:
    parser = argparse.ArgumentParser(
        description="paper CLI - Single entrypoint for scientific drafting CI/CD pipeline."
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
    subparsers.add_parser("search", help="Execute scientific literature search.")

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

    # paper audit
    audit_parser = subparsers.add_parser("audit", help="Audit reporting guidelines.")
    audit_sub = audit_parser.add_subparsers(dest="subcommand", required=True)
    audit_sub.add_parser("reporting", help="Audit manuscript against reporting checklists.")

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

    # Map parsed arguments to OrchestratorRequest
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)

    orch_command = cmd_name
    orch_args: dict[str, Any] = {}
    failure_policy = "stop_on_error"

    if cmd_name == "init":
        orch_args["preset"] = args.preset
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

    # paper doctor — runs before orchestrator, exits directly
    if cmd_name == "doctor":
        from harness.services.doctor import (
            check_all_tools,
            check_internal_capabilities,
            format_doctor_report,
        )

        repo_path = Path.cwd()
        tools = check_all_tools()
        caps = check_internal_capabilities(repo_path)
        print(format_doctor_report(tools, caps))
        sys.exit(0)

    repo_path = Path.cwd()
    request = OrchestratorRequest(
        command=orch_command,
        requested_stage="unknown",
        failure_policy=failure_policy,
        args=orch_args,
        context={"cwd": str(repo_path), "actor": "cli"},
    )

    deps = build_orchestrator_dependencies(project_root=repo_path)
    orchestrator = Orchestrator(
        deps.repo_path, deps.state_manager, deps.checker,
        deps.action_runner, deps.wrappers,
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
