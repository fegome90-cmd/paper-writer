import argparse
import sys
from pathlib import Path
from typing import Any

from harness.adapters.filesystem_action_runner import FilesystemActionRunner
from harness.adapters.filesystem_artifact_checker import FilesystemArtifactChecker
from harness.adapters.yaml_repository import YamlFileStateRepository
from harness.services.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorResult
from harness.services.state_manager import StateManager
from integrations.tools import (  # noqa: IRIX
    BibliographyNormalizer,
    PandocRenderer,
    RefsMetadataValidator,
    RefsValidator,
    ReportingAuditor,
    StyleLinter,
)
from skills.local.adapters import AcademicWriterAdapter, LiteratureSearchAdapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="paper CLI - Single entrypoint for scientific drafting CI/CD pipeline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # paper init
    subparsers.add_parser("init", help="Initialize repository and state.")

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

    # paper render
    subparsers.add_parser("render", help="Render final output formats.")

    # paper verify
    subparsers.add_parser("verify", help="Run final verification check.")

    args = parser.parse_args()

    # Map parsed arguments to OrchestratorRequest
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)

    orch_command = cmd_name
    orch_args: dict[str, Any] = {}
    failure_policy = "stop_on_error"

    if cmd_name == "draft":
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

    request = OrchestratorRequest(
        command=orch_command,
        requested_stage="unknown",
        failure_policy=failure_policy,
        args=orch_args,
        context={"cwd": str(Path.cwd()), "actor": "cli"},
    )

    # Execute orchestrator
    repo_path = Path.cwd()
    state_file_path = repo_path / "outputs" / "state.yaml"
    repository = YamlFileStateRepository(state_file_path)
    state_manager = StateManager(repository)
    checker = FilesystemArtifactChecker(repo_path)

    # Wire skill adapters
    skill_adapters = {
        "literature_search": LiteratureSearchAdapter(),
        "academic_writer": AcademicWriterAdapter(),
    }
    action_runner = FilesystemActionRunner(repo_path, skill_adapters=skill_adapters)

    # Wire tool wrappers
    wrappers = {
        "lint_bib": BibliographyNormalizer(),
        "check_refs": RefsValidator(),
        "check_refs_metadata": RefsMetadataValidator(),
        "lint_style": StyleLinter(),
        "audit_reporting": ReportingAuditor(),
        "render": PandocRenderer(),
    }

    orchestrator = Orchestrator(repo_path, state_manager, checker, action_runner, wrappers)
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
