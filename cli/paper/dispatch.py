"""Command dispatch and orchestrator wiring.

Extracted from main.py in PR1 of cli-structural-refactoring. Provides the
declarative PIPELINE_MAP dispatch (Phase C): every pipeline command has an
explicit owner, resolved via `_make_key(cmd, sub) -> spec.resolve(args) ->
PipelineInvocation`. Phase 0 callbacks (audit/gate/graph/zotero/doctor/
thesaurus/mesh) bypass the MAP via argparse's `func` default.

The MAP was introduced in Phase C5-C8 to replace the original if/elif chain.
It closes the `verify` CRITICAL gap (verify now has an explicit entry rather
than falling through to an implicit default) and makes dispatch testable via
the bidirectional parser-leaves↔PIPELINE_MAP coverage test.

Contains: output contract wiring, output_policy validation, clean_cancel
SIGINT wrapping for Zotero write ops, review_config injection, orchestrator
construction, and summary rendering (delegated to output.summary).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cli.paper import output
from cli.paper.errors import UserInputError
from cli.paper.project import resolve_project_root
from harness.services.orchestrator import Orchestrator, OrchestratorRequest
from harness.services.orchestrator_builder import build_orchestrator_dependencies


@dataclass(frozen=True)
class PipelineInvocation:
    """The complete orchestrator invocation: command + args (decided at runtime).

    Spec S3 + design.md:212-216. The indirection through a resolver lets a
    single CLI key (e.g. import:bib) choose the orchestrator command at runtime
    (import_bib vs zotero_sync) — impossible with a plain command->command dict.
    """

    orch_command: str
    args: dict[str, Any]


@dataclass(frozen=True)
class PipelineSpec:
    """Maps a CLI command key to a resolver that produces a complete invocation.

    Spec S3 + design.md:218-222. resolve(args) returns the PipelineInvocation.
    failure_policy and needs_review_config are declared per-command so the
    dispatch can construct OrchestratorRequest without command-specific branching.
    """

    resolve: Callable[[Any], PipelineInvocation]
    failure_policy: str = "stop_on_error"
    needs_review_config: bool = True


def _make_key(cmd_name: str, sub_name: str | None) -> str:
    """Build the PIPELINE_MAP key: composite 'cmd:sub' when sub present, else 'cmd'."""
    return f"{cmd_name}:{sub_name}" if sub_name else cmd_name


# --- Resolvers: each maps a CLI command's args to a PipelineInvocation. ---
# Semantics migrated 1:1 from the prior if/elif chain (failure_policy +
# needs_review_config declared on the PipelineSpec, not in the resolver).


def _resolve_init(args: Any) -> PipelineInvocation:
    orch_args: dict[str, Any] = {"preset": args.preset, "mode": args.mode}
    if args.search_window_start is not None and args.search_window_end is not None:
        orch_args["search_window"] = {
            "start_year": args.search_window_start,
            "end_year": args.search_window_end,
        }
    return PipelineInvocation("init", orch_args)


def _resolve_search(args: Any) -> PipelineInvocation:
    if not args.query or not args.query.strip():
        raise UserInputError("--query is required. Provide a research query.")
    orch_args: dict[str, Any] = {"query": args.query}
    if args.raw_papers:
        orch_args["raw_papers"] = args.raw_papers
    filter_map = {
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
    for key, val in filter_map.items():
        if val is not None:
            orch_args[key] = val
    return PipelineInvocation("search", orch_args)


def _resolve_chain(args: Any) -> PipelineInvocation:
    errors: list[str] = []
    if args.max_rounds < 1:
        errors.append(f"--max-rounds must be ≥1, got {args.max_rounds}")
    if args.max_papers < 1:
        errors.append(f"--max-papers must be ≥1, got {args.max_papers}")
    if args.relevance_threshold <= 0 or args.relevance_threshold > 1:
        errors.append(f"--relevance-threshold must be 0<val≤1, got {args.relevance_threshold}")
    if errors:
        raise UserInputError("Chain parameter validation error: " + "; ".join(errors))
    orch_args: dict[str, Any] = {
        "max_rounds": args.max_rounds,
        "max_papers": args.max_papers,
        "relevance_threshold": args.relevance_threshold,
    }
    if not args.no_cache:
        orch_args["cache_dir"] = "outputs/.cache/s2_api"
    return PipelineInvocation("chain", orch_args)


def _resolve_import_bib(args: Any) -> PipelineInvocation:
    if not args.source and not args.from_zotero:
        raise UserInputError(
            "Must specify source .bib file or use --from-zotero to sync from Zotero."
        )
    orch_command = "zotero_sync" if args.from_zotero else "import_bib"
    orch_args: dict[str, Any] = {
        "source_bib": args.source or "",
        "target_bib": args.target,
        "from_zotero": args.from_zotero,
        "collection_key": args.collection,
        "since_version": args.since,
        "bbt_local": args.bbt_local,
    }
    return PipelineInvocation(orch_command, orch_args)


def _resolve_protocol(args: Any) -> PipelineInvocation:
    return PipelineInvocation(
        "protocol",
        {
            "search_dir": args.search_dir,
            "output": args.output,
            "project_name": args.project_name,
        },
    )


def _resolve_render(args: Any) -> PipelineInvocation:
    return PipelineInvocation(
        "render",
        {
            "output_formats": args.formats if args.formats else ["docx", "pdf"],
            "csl": args.csl,
            "reference_doc": args.reference_doc,
        },
    )


# The authoritative registry of pipeline commands (spec S3, design.md:222-242).
# Every key has an explicit owner — no implicit `orch_command = cmd_name` default.
# This closes the CRITICAL 'verify' gap (verify now has an explicit entry).
PIPELINE_MAP: dict[str, PipelineSpec] = {
    "init": PipelineSpec(resolve=_resolve_init, needs_review_config=False),
    "search": PipelineSpec(resolve=_resolve_search),
    "chain": PipelineSpec(resolve=_resolve_chain),
    "export-bib": PipelineSpec(
        resolve=lambda a: PipelineInvocation("export_bib", {"bib_path": a.bib_path})
    ),
    "screen": PipelineSpec(
        resolve=lambda a: PipelineInvocation("screen", {"min_tier": a.min_tier})
    ),
    "draft:outline": PipelineSpec(resolve=lambda a: PipelineInvocation("draft_outline", {})),
    "draft:section": PipelineSpec(
        resolve=lambda a: PipelineInvocation("draft_section", {"name": a.name})
    ),
    "draft:all": PipelineSpec(resolve=lambda a: PipelineInvocation("draft_all", {})),
    "protocol": PipelineSpec(resolve=_resolve_protocol),
    "lint:bib": PipelineSpec(
        resolve=lambda a: PipelineInvocation("lint_bib", {}),
        failure_policy="continue_on_error",
    ),
    "lint:style": PipelineSpec(
        resolve=lambda a: PipelineInvocation("lint_style", {}),
        failure_policy="continue_on_error",
    ),
    "check:refs": PipelineSpec(
        resolve=lambda a: PipelineInvocation("check_refs", {}),
        failure_policy="continue_on_error",
    ),
    "audit:reporting": PipelineSpec(
        resolve=lambda a: PipelineInvocation("audit_reporting", {}),
        failure_policy="continue_on_error",
    ),
    "import:bib": PipelineSpec(resolve=_resolve_import_bib),
    "render": PipelineSpec(resolve=_resolve_render),
    "verify": PipelineSpec(resolve=lambda a: PipelineInvocation("verify", {})),
}


def execute(args: Any) -> int:
    """Route parsed args to Phase 0 callback or pipeline dispatch. Returns exit code."""
    # Wire the output contract (P2.5.1): configure emit_* channels from root flags.
    # P2.5.2: validate output_policy (reject json for text-only, fail-closed).
    effective_format = output.effective_output_format(args)
    output.configure(quiet=getattr(args, "quiet", False), output_format=effective_format)
    output._validate_output_policy(args, effective_format)

    # Phase 0 commands — run directly via func callback.
    # S16: callbacks marked clean_cancel=True (Zotero write ops) are wrapped in
    # temporary_sigint_handler() so Ctrl+C during long operations raises
    # KeyboardInterrupt -> exit 130 cleanly. Read-only commands are NOT wrapped.
    func = getattr(args, "func", None)
    if func is not None:
        if getattr(args, "clean_cancel", False):
            from cli.paper.runtime import temporary_sigint_handler

            with temporary_sigint_handler():
                func(args)
        else:
            func(args)
        return 0

    # Map parsed arguments to OrchestratorRequest via the declarative PIPELINE_MAP
    # (spec S3). dict lookup replaces the prior if/elif chain. Every pipeline
    # command has an explicit owner; unknown keys fail closed (UserInputError).
    cmd_name = args.command
    sub_name = getattr(args, "subcommand", None)
    key = _make_key(cmd_name, sub_name)
    spec = PIPELINE_MAP.get(key)
    if spec is None:
        # No implicit orch_command=cmd_name default — unknown routes are errors.
        # Phase 0 callbacks are handled above (func is not None); reaching here
        # with no MAP entry means an unmapped pipeline command (config bug).
        raise UserInputError(f"Unmapped pipeline command: {key}")
    invocation = spec.resolve(args)

    repo_path = resolve_project_root(args.project, Path.cwd())

    # Load review config to forward mode + search_window (skip when the spec
    # declares needs_review_config=False — currently only 'init').
    if spec.needs_review_config:
        from harness.services.review_config import load_review_config

        review_cfg = load_review_config(repo_path)
        invocation.args["mode"] = review_cfg.get("mode", "rapid")
        if review_cfg.get("search_window"):
            invocation.args.setdefault("search_window", review_cfg["search_window"])
        if review_cfg.get("amendments"):
            invocation.args.setdefault("amendments", review_cfg["amendments"])

    request = OrchestratorRequest(
        command=invocation.orch_command,
        requested_stage="unknown",
        failure_policy=spec.failure_policy,
        args=invocation.args,
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
