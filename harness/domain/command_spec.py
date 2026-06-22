"""Command specification registry for the core layer.

v1 scope: TRANSITORY MIRROR of existing metadata.
Dispatch remains authoritative. Parity tests detect divergence.
Full migration is a v2 concern.

PIPELINE_MAP lives in the CLI layer and only covers orchestrated commands.
This registry covers ALL commands — orchestrated, Phase 0, and external —
without importing from CLI (hexagonal architecture: CLI → Core, never reverse).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CommandSpec:
    """Specification for a single CLI command.

    v1 scope: This is a TRANSITORY MIRROR of existing metadata.
    Dispatch remains authoritative. Parity tests detect divergence.
    """

    # Identity
    id: str
    dispatch_key: str | None
    cli_path: tuple[str, ...]

    # Classification
    operation: Literal["create", "audit", "revise", "unknown"]
    handler_kind: Literal["orchestrated", "callback_direct"]
    owner_kind: Literal["core", "integration", "local_subproject"]

    # Stage requirements (pipeline_governed only)
    minimum_stage: str
    required_gates: tuple[str, ...] = ()

    # Pipeline progression (for next_action computation)
    advances_pipeline: bool = False
    produced_gates: tuple[str, ...] = ()
    next_stage: str | None = None
    workflow_rank: int | None = None
    recommended_when_gates_missing: tuple[str, ...] = ()

    # What it produces
    target: str | None = None

    # Mutation info
    mutates_project: bool = False
    creates_run: bool = False

    # Network requirements
    network_policy: Literal["local_only", "external_allowed", "external_required"] = (
        "local_only"
    )

    # Arguments
    requires_args: tuple[str, ...] = ()

    # State policy
    state_policy: Literal[
        "pipeline_initializer", "pipeline_governed", "standalone_allowed"
    ] = "pipeline_governed"

    # Human info
    description: str = ""


COMMAND_REGISTRY: dict[str, CommandSpec] = {
    # ═══════════════════════════════════════════════
    # ORCHESTRATED COMMANDS (go through Orchestrator)
    # ═══════════════════════════════════════════════

    "init": CommandSpec(
        id="init",
        dispatch_key="init",
        cli_path=("init",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="bootstrap",
        advances_pipeline=True,
        produced_gates=("repo_initialized",),
        next_stage="search",
        workflow_rank=0,
        recommended_when_gates_missing=("repo_initialized",),
        target="repo_scaffold",
        mutates_project=True,
        creates_run=True,
        state_policy="pipeline_initializer",
        description="Initialize project structure and state",
    ),
    "search": CommandSpec(
        id="search",
        dispatch_key="search",
        cli_path=("search",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="search",
        required_gates=("repo_initialized",),
        advances_pipeline=True,
        produced_gates=("search_completed",),
        next_stage="screen",
        workflow_rank=1,
        recommended_when_gates_missing=("search_completed",),
        target="search_results",
        mutates_project=True,
        creates_run=True,
        network_policy="external_required",
        state_policy="pipeline_governed",
        description="Search for papers and evidence",
    ),
    "chain": CommandSpec(
        id="chain",
        dispatch_key="chain",
        cli_path=("chain",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="screen",
        required_gates=("repo_initialized",),
        advances_pipeline=False,
        produced_gates=("search_completed",),
        target="chained_results",
        mutates_project=True,
        creates_run=True,
        network_policy="external_required",
        state_policy="pipeline_governed",
        description="Expand search via citation chaining",
    ),
    "screen": CommandSpec(
        id="screen",
        dispatch_key="screen",
        cli_path=("screen",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="screen",
        required_gates=("search_completed",),
        advances_pipeline=True,
        produced_gates=("screened_evidence",),
        next_stage="outline",
        workflow_rank=2,
        recommended_when_gates_missing=("screened_evidence",),
        target="screened_evidence",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Screen search results for relevance",
    ),
    "export-bib": CommandSpec(
        id="export-bib",
        dispatch_key="export-bib",
        cli_path=("export-bib",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="screen",
        required_gates=("screened_evidence",),
        advances_pipeline=False,
        target="bibliography",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Export screened evidence to BibTeX",
    ),
    "draft:outline": CommandSpec(
        id="draft:outline",
        dispatch_key="draft:outline",
        cli_path=("draft", "outline"),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="outline",
        required_gates=("screened_evidence",),
        advances_pipeline=True,
        produced_gates=("outline_drafted",),
        next_stage="drafting",
        workflow_rank=3,
        recommended_when_gates_missing=("outline_drafted",),
        target="outline",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Generate paper outline",
    ),
    "draft:section": CommandSpec(
        id="draft:section",
        dispatch_key="draft:section",
        cli_path=("draft", "section"),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="drafting",
        required_gates=("outline_drafted",),
        advances_pipeline=False,
        produced_gates=("sections_completed",),
        target="draft_sections",
        mutates_project=True,
        requires_args=("section_name",),
        state_policy="pipeline_governed",
        description="Draft a specific section",
    ),
    "draft:all": CommandSpec(
        id="draft:all",
        dispatch_key="draft:all",
        cli_path=("draft", "all"),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="drafting",
        required_gates=("outline_drafted",),
        advances_pipeline=True,
        produced_gates=("sections_completed",),
        next_stage="validating",
        workflow_rank=4,
        recommended_when_gates_missing=("sections_completed",),
        target="draft_sections",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Draft all sections",
    ),
    "protocol": CommandSpec(
        id="protocol",
        dispatch_key="protocol",
        cli_path=("protocol",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="screen",
        required_gates=("screened_evidence",),
        advances_pipeline=False,
        target="protocol",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Generate research protocol",
    ),
    "lint:bib": CommandSpec(
        id="lint:bib",
        dispatch_key="lint:bib",
        cli_path=("lint", "bib"),
        operation="audit",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="validating",
        required_gates=("bib_imported",),
        advances_pipeline=False,
        produced_gates=("bib_normalized",),
        workflow_rank=10,
        recommended_when_gates_missing=("bib_normalized",),
        target="bibliography",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Normalize bibliography with bibtex-tidy",
    ),
    "lint:style": CommandSpec(
        id="lint:style",
        dispatch_key="lint:style",
        cli_path=("lint", "style"),
        operation="audit",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="validating",
        required_gates=("sections_completed",),
        advances_pipeline=False,
        produced_gates=("style_passed",),
        workflow_rank=11,
        recommended_when_gates_missing=("style_passed",),
        target="style_report",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Lint manuscript style with Vale",
    ),
    "check:refs": CommandSpec(
        id="check:refs",
        dispatch_key="check:refs",
        cli_path=("check", "refs"),
        operation="audit",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="validating",
        required_gates=("sections_completed", "bib_normalized"),
        advances_pipeline=False,
        produced_gates=("refs_validated", "citations_resolved", "citation_verified"),
        workflow_rank=12,
        recommended_when_gates_missing=("refs_validated", "citations_resolved"),
        target="refs_report",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Validate references and citations",
    ),
    "audit:reporting": CommandSpec(
        id="audit:reporting",
        dispatch_key="audit:reporting",
        cli_path=("audit", "reporting"),
        operation="audit",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="validating",
        required_gates=("sections_completed",),
        advances_pipeline=False,
        produced_gates=("reporting_passed",),
        workflow_rank=13,
        recommended_when_gates_missing=("reporting_passed",),
        target="reporting_report",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Audit reporting compliance",
    ),
    "import:bib": CommandSpec(
        id="import:bib",
        dispatch_key="import:bib",
        cli_path=("import", "bib"),
        operation="revise",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="bootstrap",
        advances_pipeline=True,
        produced_gates=("bib_imported", "bib_normalized"),
        workflow_rank=9,
        recommended_when_gates_missing=("bib_imported",),
        target="bibliography",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Import bibliography from file or Zotero",
    ),
    "render": CommandSpec(
        id="render",
        dispatch_key="render",
        cli_path=("render",),
        operation="create",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="rendering",
        required_gates=(
            "style_passed",
            "reporting_passed",
            "bib_normalized",
            "refs_validated",
            "citations_resolved",
        ),
        advances_pipeline=True,
        produced_gates=("render_passed",),
        next_stage="rendered",
        workflow_rank=5,
        recommended_when_gates_missing=("render_passed",),
        target="rendered_output",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Render manuscript to DOCX/PDF",
    ),
    "verify": CommandSpec(
        id="verify",
        dispatch_key="verify",
        cli_path=("verify",),
        operation="audit",
        handler_kind="orchestrated",
        owner_kind="core",
        minimum_stage="rendered",
        required_gates=("render_passed",),
        advances_pipeline=False,
        produced_gates=("ready_for_delivery", "citation_verified", "ethics_passed"),
        workflow_rank=20,
        recommended_when_gates_missing=("ready_for_delivery",),
        target="verification_result",
        mutates_project=True,
        state_policy="pipeline_governed",
        description="Verify publication readiness",
    ),

    # ═══════════════════════════════════════════════
    # PREFLIGHT COMMAND (Phase 0, read-only, standalone)
    # ═══════════════════════════════════════════════

    "preflight": CommandSpec(
        id="preflight",
        dispatch_key=None,
        cli_path=("preflight",),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Show pipeline status, blockers, and recommended next action",
    ),

    # ═══════════════════════════════════════════════
    # PHASE 0 COMMANDS (direct callback, bypass Orchestrator)
    # ═══════════════════════════════════════════════

    "doctor": CommandSpec(
        id="doctor",
        dispatch_key=None,
        cli_path=("doctor",),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Check environment and tool availability",
    ),
    "gate:method": CommandSpec(
        id="gate:method",
        dispatch_key=None,
        cli_path=("gate", "method"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="screen",
        state_policy="standalone_allowed",
        description="Evaluate method gate checklist",
    ),
    "trace": CommandSpec(
        id="trace",
        dispatch_key=None,
        cli_path=("trace",),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Show code traceability graph via Trifecta",
    ),
    "graph-overview": CommandSpec(
        id="graph-overview",
        dispatch_key=None,
        cli_path=("graph-overview",),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Show graph overview via Trifecta",
    ),

    # ═══════════════════════════════════════════════
    # AUDIT COMMANDS (Phase 0, read-only, standalone)
    # ═══════════════════════════════════════════════

    "audit:prose": CommandSpec(
        id="audit:prose",
        dispatch_key=None,
        cli_path=("audit", "prose"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit scientific prose quality",
    ),
    "audit:claims": CommandSpec(
        id="audit:claims",
        dispatch_key=None,
        cli_path=("audit", "claims"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit claim detection",
    ),
    "audit:citations": CommandSpec(
        id="audit:citations",
        dispatch_key=None,
        cli_path=("audit", "citations"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit citation consistency",
    ),
    "audit:ethics": CommandSpec(
        id="audit:ethics",
        dispatch_key=None,
        cli_path=("audit", "ethics"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit ethics compliance",
    ),
    "audit:writing-quality": CommandSpec(
        id="audit:writing-quality",
        dispatch_key=None,
        cli_path=("audit", "writing-quality"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit writing quality",
    ),
    "audit:code-health": CommandSpec(
        id="audit:code-health",
        dispatch_key=None,
        cli_path=("audit", "code-health"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit code health via Trifecta",
    ),
    "audit:factuality": CommandSpec(
        id="audit:factuality",
        dispatch_key=None,
        cli_path=("audit", "factuality"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="screen",
        state_policy="standalone_allowed",
        description="Audit factuality of claims",
    ),
    "audit:tables": CommandSpec(
        id="audit:tables",
        dispatch_key=None,
        cli_path=("audit", "tables"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="drafting",
        state_policy="standalone_allowed",
        description="Audit table and figure consistency",
    ),
    "audit:quality-appraisal": CommandSpec(
        id="audit:quality-appraisal",
        dispatch_key=None,
        cli_path=("audit", "quality-appraisal"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="core",
        minimum_stage="screen",
        state_policy="standalone_allowed",
        description="Appraise study quality",
    ),

    # ═══════════════════════════════════════════════
    # ZOTERO COMMANDS (Phase 0, external, standalone)
    # ═══════════════════════════════════════════════

    "zotero:collections": CommandSpec(
        id="zotero:collections",
        dispatch_key=None,
        cli_path=("zotero", "collections"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="List Zotero collections",
    ),
    "zotero:search": CommandSpec(
        id="zotero:search",
        dispatch_key=None,
        cli_path=("zotero", "search"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Search Zotero library",
    ),
    "zotero:get": CommandSpec(
        id="zotero:get",
        dispatch_key=None,
        cli_path=("zotero", "get"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Get Zotero item",
    ),
    "zotero:create": CommandSpec(
        id="zotero:create",
        dispatch_key=None,
        cli_path=("zotero", "create"),
        operation="create",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Create Zotero item",
    ),
    "zotero:template": CommandSpec(
        id="zotero:template",
        dispatch_key=None,
        cli_path=("zotero", "template"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Get empty template for an item type",
    ),
    "zotero:update": CommandSpec(
        id="zotero:update",
        dispatch_key=None,
        cli_path=("zotero", "update"),
        operation="revise",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Update Zotero item",
    ),
    "zotero:delete": CommandSpec(
        id="zotero:delete",
        dispatch_key=None,
        cli_path=("zotero", "delete"),
        operation="revise",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Delete Zotero item",
    ),
    "zotero:upload": CommandSpec(
        id="zotero:upload",
        dispatch_key=None,
        cli_path=("zotero", "upload"),
        operation="revise",
        handler_kind="callback_direct",
        owner_kind="integration",
        minimum_stage="bootstrap",
        network_policy="external_required",
        state_policy="standalone_allowed",
        description="Upload attachment to Zotero",
    ),

    # ═══════════════════════════════════════════════
    # THESAURUS COMMANDS (external subproject, standalone)
    # ═══════════════════════════════════════════════

    "thesaurus:import": CommandSpec(
        id="thesaurus:import",
        dispatch_key=None,
        cli_path=("thesaurus", "import"),
        operation="create",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        target="thesaurus_db",
        mutates_project=True,
        state_policy="standalone_allowed",
        description="Import concepts into thesaurus",
    ),
    "thesaurus:search": CommandSpec(
        id="thesaurus:search",
        dispatch_key=None,
        cli_path=("thesaurus", "search"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Search thesaurus",
    ),
    "thesaurus:list": CommandSpec(
        id="thesaurus:list",
        dispatch_key=None,
        cli_path=("thesaurus", "list"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="List thesaurus concepts",
    ),
    "thesaurus:audit": CommandSpec(
        id="thesaurus:audit",
        dispatch_key=None,
        cli_path=("thesaurus", "audit"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Audit thesaurus store",
    ),
    "thesaurus:rebuild": CommandSpec(
        id="thesaurus:rebuild",
        dispatch_key=None,
        cli_path=("thesaurus", "rebuild"),
        operation="revise",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        target="thesaurus_db",
        mutates_project=True,
        state_policy="standalone_allowed",
        description="Rebuild thesaurus from JSONL",
    ),

    # ═══════════════════════════════════════════════
    # MESH COMMANDS (external subproject, standalone)
    # ═══════════════════════════════════════════════

    "mesh:import": CommandSpec(
        id="mesh:import",
        dispatch_key=None,
        cli_path=("mesh", "import"),
        operation="create",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        target="mesh_db",
        mutates_project=True,
        state_policy="standalone_allowed",
        description="Import MeSH XML",
    ),
    "mesh:resolve": CommandSpec(
        id="mesh:resolve",
        dispatch_key=None,
        cli_path=("mesh", "resolve"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Resolve MeSH term",
    ),
    "mesh:expand": CommandSpec(
        id="mesh:expand",
        dispatch_key=None,
        cli_path=("mesh", "expand"),
        operation="audit",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        state_policy="standalone_allowed",
        description="Expand MeSH tree",
    ),
    "mesh:export": CommandSpec(
        id="mesh:export",
        dispatch_key=None,
        cli_path=("mesh", "export"),
        operation="create",
        handler_kind="callback_direct",
        owner_kind="local_subproject",
        minimum_stage="bootstrap",
        target="mesh_jsonl",
        state_policy="standalone_allowed",
        description="Export MeSH to JSONL",
    ),
}


__all__ = ["COMMAND_REGISTRY", "CommandSpec"]
