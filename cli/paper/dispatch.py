"""Command dispatch and orchestrator wiring.

Extracted from main.py in PR1 of cli-structural-refactoring.
Contains the if/elif dispatch block, review_config injection,
orchestrator construction, and _print_summary.

NOTE: P1.7.1-P1.7.3 (PipelineInvocation/PipelineSpec/PIPELINE_MAP) were
deferred to a follow-up PR. The if/elif dispatch pattern is preserved
verbatim from the original main.py. This is a documented decision, not
an oversight -- see tasks.md amendment below.

Tasks.md amendment: P1.7.1-P1.7.3 deferred. The declarative PIPELINE_MAP
redesign requires import:bib dynamic command selection (PipelineInvocation)
which adds complexity beyond pure structural extraction. PR1 scope is
"move code without changing behavior" -- the if/elif achieves that.
PIPELINE_MAP will be implemented in a dedicated iteration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli.paper import output
from cli.paper.errors import UserInputError
from cli.paper.project import resolve_project_root
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.orchestrator_builder import build_orchestrator_dependencies


def execute(args: Any) -> int:
    """Route parsed args to Phase 0 callback or pipeline dispatch. Returns exit code."""
    # Phase 0 commands — run directly via func callback
    func = getattr(args, "func", None)
    if func is not None:
        func(args)
        return 0

    # Map parsed arguments to OrchestratorRequest
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)

    orch_command = cmd_name
    orch_args: dict[str, Any] = {}
    failure_policy = "stop_on_error"

    if cmd_name == "init":
        orch_args["preset"] = args.preset
        orch_args["mode"] = args.mode
        if args.search_window_start is not None and args.search_window_end is not None:
            orch_args["search_window"] = {
                "start_year": args.search_window_start,
                "end_year": args.search_window_end,
            }
    elif cmd_name == "search":
        if not args.query or not args.query.strip():
            raise UserInputError("--query is required. Provide a research query.")
        orch_args["query"] = args.query
        if args.raw_papers:
            orch_args["raw_papers"] = args.raw_papers
        _CLI_FILTER_MAP = {  # noqa: N806
            "year_min": args.year_min,
            "year_max": args.year_max,
            "study_types": args.study_types,
            "human": args.human or None,
            "sample_size_min": args.sample_size_min,
            "sjr_max": args.sjr_max,
            "duration_min": args.duration_min,
            "duration_max": args.duration_max,
            "exclude_preprints": args.exclude_preprints or None,
            "publisher_name": args.publisher_name,
            "clinical_guideline": args.clinical_guideline or None,
            "medical_mode": args.medical_mode or None,
        }
        for key, val in _CLI_FILTER_MAP.items():
            if val is not None:
                orch_args[key] = val
    elif cmd_name == "chain":
        orch_command = "chain"
        _chain_errors: list[str] = []
        if args.max_rounds < 1:
            _chain_errors.append(f"--max-rounds must be ≥1, got {args.max_rounds}")
        if args.max_papers < 1:
            _chain_errors.append(f"--max-papers must be ≥1, got {args.max_papers}")
        if args.relevance_threshold <= 0 or args.relevance_threshold > 1:
            _chain_errors.append(
                f"--relevance-threshold must be 0<val≤1, got {args.relevance_threshold}"
            )
        if _chain_errors:
            raise UserInputError("Chain parameter validation error: " + "; ".join(_chain_errors))
        orch_args["max_rounds"] = args.max_rounds
        orch_args["max_papers"] = args.max_papers
        orch_args["relevance_threshold"] = args.relevance_threshold
        if not args.no_cache:
            orch_args["cache_dir"] = "outputs/.cache/s2_api"
    elif cmd_name == "export-bib":
        orch_command = "export_bib"
        orch_args["bib_path"] = args.bib_path
    elif cmd_name == "screen":
        orch_args["min_tier"] = args.min_tier
    elif cmd_name == "draft":
        if sub_name == "outline":
            orch_command = "draft_outline"
        elif sub_name == "section":
            orch_command = "draft_section"
            orch_args["name"] = args.name
        elif sub_name == "all":
            orch_command = "draft_all"
    elif cmd_name == "protocol":
        orch_command = "protocol"
        orch_args["search_dir"] = args.search_dir
        orch_args["output"] = args.output
        orch_args["project_name"] = args.project_name
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
        # NOTE: audit:ethics has func callback set in parser.py — it never
        # reaches this pipeline block. Dead elif sub_name == "ethics" branch deleted.
    elif cmd_name == "import":
        if sub_name == "bib":
            if not args.source and not args.from_zotero:
                raise UserInputError(
                    "Must specify source .bib file or use --from-zotero to sync from Zotero."
                )
            orch_command = "zotero_sync" if args.from_zotero else "import_bib"
            orch_args["source_bib"] = args.source or ""
            orch_args["target_bib"] = args.target
            orch_args["from_zotero"] = args.from_zotero
            orch_args["collection_key"] = args.collection
            orch_args["since_version"] = args.since
            orch_args["bbt_local"] = args.bbt_local
    elif cmd_name == "render":
        orch_args["output_formats"] = args.formats if args.formats else ["docx", "pdf"]
        orch_args["csl"] = args.csl
        orch_args["reference_doc"] = args.reference_doc

    repo_path = resolve_project_root(args.project, Path.cwd())

    # Load review config for non-init commands to forward mode + search_window
    if cmd_name != "init" and cmd_name not in ("doctor", "thesaurus", "mesh"):
        from harness.services.review_config import load_review_config

        review_cfg = load_review_config(repo_path)
        orch_args["mode"] = review_cfg.get("mode", "rapid")
        if review_cfg.get("search_window"):
            orch_args.setdefault("search_window", review_cfg["search_window"])
        if review_cfg.get("amendments"):
            orch_args.setdefault("amendments", review_cfg["amendments"])

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

    output.summary(result)
    return result.exit_code
