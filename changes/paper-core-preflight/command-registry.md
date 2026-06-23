# Command Specification Registry

**Date:** 2026-06-19
**Status:** New artifact — transitory mirror command registry for core layer

---

## Purpose

`PIPELINE_MAP` lives in `cli/paper/dispatch.py` and only covers orchestrated commands. The preflight resolver needs to know ALL commands — orchestrated, Phase 0, direct callbacks — without importing from the CLI layer.

`CommandRegistry` is a **policy mirror + safety augmentation** of existing command metadata for v1:

- Mirrors what `PIPELINE_MAP` and Phase 0 registrations already define (routing, stages)
- Adds `state_policy` to distinguish standalone vs pipeline-governed commands
- Adds pipeline progression metadata for `next_action` computation
- May impose **stricter workflow preconditions** than the Orchestrator (e.g., requiring `bib_imported` before `lint:bib`)
- Parity tests detect divergence from `PIPELINE_MAP` and parser registrations
- Dispatch remains authoritative for execution in v1

**Key distinction**: The registry reflects routing and stage requirements from the current codebase, but may add workflow-level safety preconditions that the Orchestrator does not yet enforce. This is intentional — preflight should be at least as strict as the Orchestrator, never more permissive.

**v2 goal**: COMMAND_REGISTRY becomes the SSOT. PIPELINE_MAP is generated from it. Orchestrator queries it for preconditions.

In v1, only Preflight consumes COMMAND_REGISTRY. CLI and Orchestrator will migrate in v2. Core never imports CLI.

---

## Data Model

```python
# harness/domain/command_spec.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

@dataclass(frozen=True)
class CommandSpec:
    """Specification for a single CLI command.

    v1 scope: TRANSITORY MIRROR of existing metadata.
    Dispatch remains authoritative. Parity tests detect divergence.
    """

    # Identity
    id: str                                    # canonical ID, e.g. "draft:outline"
    dispatch_key: str | None                   # PIPELINE_MAP key, e.g. "draft:outline" (None for Phase 0)
    cli_path: tuple[str, ...]                  # CLI invocation, e.g. ("draft", "outline")

    # Classification
    operation: Literal["create", "audit", "revise", "unknown"]
    handler_kind: Literal["orchestrated", "callback_direct"]
    owner_kind: Literal["core", "integration", "local_subproject"]

    # Stage requirements (pipeline_governed only)
    minimum_stage: str                         # earliest stage where command is available
    required_gates: tuple[str, ...] = ()       # gates that must be True (empty for standalone)

    # Pipeline progression (for next_action computation)
    advances_pipeline: bool = False            # does this command move the pipeline forward?
    produced_gates: tuple[str, ...] = ()       # gates this command can set to True upon completion
    next_stage: str | None = None              # which stage does the pipeline transition to?
    workflow_rank: int | None = None           # ordering for next_action (lower = higher priority)
    recommended_when_gates_missing: tuple[str, ...] = ()  # recommend this command when these gates are missing

    # What it produces
    target: str | None = None                  # primary artifact (human-readable)

    # Mutation info
    mutates_project: bool = False              # does it write to outputs/?
    creates_run: bool = False                  # does it create a new run directory?

    # Network requirements
    network_policy: Literal["local_only", "external_allowed", "external_required"] = "local_only"
    # v1 NOTE: network_policy is descriptive only. Does NOT prove runtime availability.
    # CapabilityResolver is deferred to v2.

    # Arguments
    requires_args: tuple[str, ...] = ()        # mandatory CLI args (info only, not validated by preflight)

    # State policy
    state_policy: Literal["pipeline_initializer", "pipeline_governed", "standalone_allowed"] = "pipeline_governed"
    # pipeline_initializer: creates state.yaml (e.g., init); does NOT require state.yaml
    # pipeline_governed: requires state.yaml, stage, and gates
    # standalone_allowed: eligible regardless of pipeline state (parser validates args)

    # Human info
    description: str = ""
```

### Field Notes

- **`dispatch_key`**: Matches `PIPELINE_MAP` key exactly. `None` for Phase 0 commands (not in PIPELINE_MAP). Used by parity test.
- **`cli_path`**: Tuple of CLI tokens. `("draft", "outline")` means `paper draft outline`. Used for documentation and future CLI generation.
- **`required_gates`**: Empty tuple for standalone commands. Including gates here would be misleading since standalone commands ignore them.
- **`advances_pipeline`**: `True` for commands that transition the pipeline to the next stage. `False` for audits, utilities, and repeatable commands.
- **`produced_gates`**: Gates that this command can set to `True` upon successful completion. Empty tuple if the command doesn't set gates. May include multiple gates (e.g., `check:refs` can set `refs_validated`, `citations_resolved`, and `citation_verified`).
- **`next_stage`**: The stage the pipeline transitions to after this command completes. `None` if no stage change.
- **`workflow_rank`**: Lower number = higher priority for `next_action`. `None` if the command should not be recommended. Used to break ties when multiple commands can produce missing gates.
- **`recommended_when_gates_missing`**: Recommend this command when these gates are currently `False`. Used by `next_action` algorithm to find commands that can unblock the pipeline.

---

## Registry

```python
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
        required_gates=("style_passed", "reporting_passed", "bib_normalized", "refs_validated", "citations_resolved"),
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
```

---

## State Policy Summary

| Policy | Meaning | Requires state.yaml | Requires stage | Requires gates |
|--------|---------|---------------------|----------------|----------------|
| `pipeline_initializer` | Creates state.yaml (e.g., init) | No | No | No |
| `pipeline_governed` | Command is part of the orchestrated pipeline | Yes | Yes | Yes (from `required_gates`) |
| `standalone_allowed` | Command can execute independently | No | No | No (`required_gates` is empty) |

**pipeline_initializer**: The command creates state.yaml. It does NOT require state.yaml to exist. It is part of the pipeline and advances it.

**Standalone commands**: Eligible regardless of pipeline state. `required_gates` is empty tuple — including gates would be misleading since standalone commands ignore them. The parser validates their specific arguments.

**Pipeline-governed commands**: Require valid state.yaml, appropriate stage, and satisfied gates.

---

## Pipeline Progression

For `next_action` computation, the registry includes progression metadata:

| Command | advances_pipeline | produced_gates | next_stage | workflow_rank |
|---------|-------------------|----------------|------------|---------------|
| `init` | ✅ | `repo_initialized` | `search` | 0 |
| `search` | ✅ | `search_completed` | `screen` | 1 |
| `screen` | ✅ | `screened_evidence` | `outline` | 2 |
| `draft:outline` | ✅ | `outline_drafted` | `drafting` | 3 |
| `draft:all` | ✅ | `sections_completed` | `validating` | 4 |
| `render` | ✅ | `render_passed` | `rendered` | 5 |
| `import:bib` | ✅ | `bib_imported` | — | — |
| `lint:bib` | ❌ | `bib_normalized` | — | 10 |
| `lint:style` | ❌ | `style_passed` | — | 11 |
| `check:refs` | ❌ | `refs_validated`, `citations_resolved` | — | 12 |
| `audit:reporting` | ❌ | `reporting_passed` | — | 13 |
| `verify` | ❌ | `ready_for_delivery` | — | 20 |
| All others | ❌ | — | — | — |

`next_action` recommendation logic:
1. Collect all commands where `workflow_rank is not None`
2. Filter to commands that are available at current stage with required gates satisfied
3. Filter to commands that have at least one gate in `produced_gates` that is currently `False`
4. Sort by `workflow_rank` (lower = higher priority)
5. Return the first match

---

## Parity Tests (v1)

```python
def test_parity_with_pipeline_map():
    """Every PIPELINE_MAP key must have a matching dispatch_key in COMMAND_REGISTRY."""
    from cli.paper.dispatch import PIPELINE_MAP
    registry_by_dispatch_key = {
        spec.dispatch_key: spec
        for spec in COMMAND_REGISTRY.values()
        if spec.dispatch_key is not None
    }
    for key in PIPELINE_MAP:
        assert key in registry_by_dispatch_key, (
            f"PIPELINE_MAP key '{key}' has no matching dispatch_key in COMMAND_REGISTRY"
        )

def test_parity_with_parser():
    """Every parser leaf subcommand must have a matching cli_path in COMMAND_REGISTRY.
    
    NOTE: Only compares executable leaves, not intermediate group commands
    like 'draft', 'lint', 'audit', 'zotero', 'thesaurus', 'mesh'.
    """
    # Build set of CLI paths from parser registration (leaves only)
    # Compare against COMMAND_REGISTRY cli_path values
    registry_cli_paths = {spec.cli_path for spec in COMMAND_REGISTRY.values()}
    for cli_path in PARSED_CLI_PATHS:
        # Skip intermediate group commands (single-element tuples that are groups)
        if len(cli_path) == 1 and cli_path[0] in ("draft", "lint", "audit", "zotero", "thesaurus", "mesh"):
            continue
        assert cli_path in registry_cli_paths, (
            f"CLI path {cli_path} has no matching entry in COMMAND_REGISTRY"
        )

def test_standalone_commands_have_empty_gates():
    """Standalone commands must have empty required_gates."""
    for spec in COMMAND_REGISTRY.values():
        if spec.state_policy == "standalone_allowed":
            assert spec.required_gates == (), (
                f"Standalone command '{spec.id}' has non-empty required_gates: {spec.required_gates}"
            )

def test_pipeline_initializer_commands_have_empty_gates():
    """Pipeline initializer commands must have empty required_gates."""
    for spec in COMMAND_REGISTRY.values():
        if spec.state_policy == "pipeline_initializer":
            assert spec.required_gates == (), (
                f"Pipeline initializer command '{spec.id}' has non-empty required_gates: {spec.required_gates}"
            )

def test_all_ids_in_stage_order():
    """All minimum_stage values must be valid stage names."""
    from harness.domain.state import ManuscriptState
    for spec in COMMAND_REGISTRY.values():
        assert spec.minimum_stage in ManuscriptState.STAGE_ORDER, (
            f"Command '{spec.id}' has invalid minimum_stage: {spec.minimum_stage}"
        )

def test_semantic_parity_chain_minimum_stage():
    """chain must require stage 'screen' (verified against Orchestrator)."""
    spec = COMMAND_REGISTRY["chain"]
    assert spec.minimum_stage == "screen", (
        f"chain minimum_stage should be 'screen', got '{spec.minimum_stage}'"
    )

def test_semantic_parity_init_state_policy():
    """init must have state_policy='pipeline_initializer'."""
    spec = COMMAND_REGISTRY["init"]
    assert spec.state_policy == "pipeline_initializer", (
        f"init state_policy should be 'pipeline_initializer', got '{spec.state_policy}'"
    )

def test_semantic_parity_no_excessive_gates():
    """Pipeline-governed commands should not require gates the Orchestrator doesn't check.
    
    NOTE: This is a documentation test. The Orchestrator's _validate_preconditions()
    primarily checks stage. For v1, we mirror what we believe the intent is.
    If this test fails, adjust the registry to match actual Orchestrator behavior.
    """
    # verify is the only command with an explicit gate check in the Orchestrator
    # Other commands may have gates in the registry for future strictness
    # This test ensures we don't add gates we're not prepared to enforce
    pass  # Placeholder for when Orchestrator gate checks are audited
```

---

## Usage

### Preflight — available_commands

```python
from harness.domain.command_spec import COMMAND_REGISTRY

def compute_available_commands(stage: str, gates: dict[str, bool]) -> list[str]:
    """Return commands available at current stage with gates satisfied.

    Standalone commands are always available (parser validates args).
    Pipeline-governed commands require stage + gates.
    """
    available = []
    for cmd_id, spec in COMMAND_REGISTRY.items():
        if spec.state_policy == "standalone_allowed":
            available.append(cmd_id)
        elif _stage_index(stage) >= _stage_index(spec.minimum_stage):
            if all(gates.get(g, False) for g in spec.required_gates):
                available.append(cmd_id)
    return available
```

### Preflight — next_action

```python
def compute_next_action(stage: str, gates: dict[str, bool]) -> str | None:
    """Recommend the command that most efficiently advances the pipeline.
    
    Logic:
    1. Find commands with workflow_rank set
    2. Filter to those available at current stage with required gates satisfied
    3. Filter to those that can produce at least one missing gate
    4. Sort by workflow_rank (lower = higher priority)
    5. Return the first match
    """
    candidates = []
    for spec in COMMAND_REGISTRY.values():
        if spec.workflow_rank is None:
            continue
        if not spec.produced_gates:
            continue
        # Check if this command can produce any missing gate
        missing_gates = [g for g in spec.produced_gates if not gates.get(g, False)]
        if not missing_gates:
            continue
        # Check if command is available at current stage
        if _stage_index(stage) < _stage_index(spec.minimum_stage):
            continue
        # Check if required gates are satisfied
        if not all(gates.get(g, False) for g in spec.required_gates):
            continue
        candidates.append((spec.workflow_rank, spec.id))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]
```

### Preflight — invalid state handling

```python
def resolve_preflight(project_root, command=None, review_config=None):
    state = load_state(project_root)
    spec = COMMAND_REGISTRY.get(command) if command else None

    if state is None:
        if spec and spec.state_policy == "standalone_allowed":
            # Standalone: ignore missing state, report as warning
            warnings.append("state.yaml not found (standalone command, not blocking)")
            # Continue with default state
            state = default_state()
        else:
            # Pipeline-governed or general: needs_input
            return PreflightResult(status="needs_input", ...)

    if state is not None and state.is_invalid:
        if spec and spec.state_policy == "standalone_allowed":
            # Standalone: ignore invalid state, report as warning
            warnings.append(f"state.yaml is invalid (standalone command, not blocking): {error}")
            state = default_state()
        else:
            # Pipeline-governed or general: blocked
            return PreflightResult(status="blocked", ...)
```

---

## Migration from PIPELINE_MAP

| PIPELINE_MAP key | CommandSpec id | dispatch_key | cli_path |
|------------------|----------------|--------------|----------|
| `init` | `init` | `init` | `("init",)` |
| `search` | `search` | `search` | `("search",)` |
| `chain` | `chain` | `chain` | `("chain",)` |
| `export-bib` | `export-bib` | `export-bib` | `("export-bib",)` |
| `screen` | `screen` | `screen` | `("screen",)` |
| `draft:outline` | `draft:outline` | `draft:outline` | `("draft", "outline")` |
| `draft:section` | `draft:section` | `draft:section` | `("draft", "section")` |
| `draft:all` | `draft:all` | `draft:all` | `("draft", "all")` |
| `protocol` | `protocol` | `protocol` | `("protocol",)` |
| `lint:bib` | `lint:bib` | `lint:bib` | `("lint", "bib")` |
| `lint:style` | `lint:style` | `lint:style` | `("lint", "style")` |
| `check:refs` | `check:refs` | `check:refs` | `("check", "refs")` |
| `audit:reporting` | `audit:reporting` | `audit:reporting` | `("audit", "reporting")` |
| `import:bib` | `import:bib` | `import:bib` | `("import", "bib")` |
| `render` | `render` | `render` | `("render",)` |
| `verify` | `verify` | `verify` | `("verify",)` |

**Note:** PIPELINE_MAP keys use `:` as separator. CLI uses space-separated subcommands. The `cli_path` tuple represents the actual CLI invocation.

---

## Open Questions (Deferred to v2)

1. **Full migration**: When should PIPELINE_MAP be replaced by COMMAND_REGISTRY? v1 strategy is mirror + parity tests; v2 strategy is full migration.
2. **Orchestrator integration**: When should the Orchestrator query COMMAND_REGISTRY for preconditions instead of using internal logic?
3. **CLI generation**: Should argparse subparsers be generated from COMMAND_REGISTRY?
