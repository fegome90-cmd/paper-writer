# Specification: Paper Core Preflight Resolution

## 0. Capability Inventory (Full Repository)

The preflight resolver MUST be aware of all repository capabilities. The capability ledger at `changes/paper-core-preflight/capability-ledger.yaml` defines 60+ entries across these layers:

| Layer | Count | Examples |
|-------|-------|---------|
| core | 8 | Orchestrator, ManuscriptState, StateManager, Gates, Assembler, VerifyArtifacts, ReviewConfig, PreflightResolver |
| cli | 27+ | init, search, screen, draft, render, verify, 11 audits, gate method, trace, graph-overview, import bib, lint bib, lint style, check refs, doctor, zotero (8 subcommands), thesaurus (5 subcommands), mesh (4 subcommands) |
| validation | 23 | refs, citations, citation_verify, bibliography, structure, prose, claims, claim_alignment, ethics, writing_quality, style, reporting, method_gate, code_health, quality_appraisal, preset, gate_verdict, contamination_signals, academic_evidence, table_figure, citation_format, claim_evidence, protocol_generator |
| integration | 14 tool wrappers (registered in OrchestratorBuilder) + 2 MCP clients + 1 search provider | tool_wrappers: pandoc, vale, bibtex-tidy, refs, refs_metadata, reporting, ethics, prose, claims, citations, writing_quality, code_health, zotero_import, zotero_sync; external_providers: consensus_client, consensus_mcp_client, mcp_paper_client; search: fixture |
| clients | 9 | crossref, semantic_scholar, openalex, arxiv, zotero, trifecta, llm_content, _text_similarity, _retry |
| skills | 8 | literature_search, academic_writer, thesaurus, mesh-import, trifecta-mcp, science-bundle, essay_crafter, workflow_skill_creator |
| engine | 3 | deduplicator, formatter, loader |
| parsers | 2 | manuscript, source_map |
| rules | 6 | prose, claims, ethics, citations, writing_quality, method_gate |
| schemas | 5 | claim_audit, finding, method_gate, preflight, prose_audit |
| templates | 3 | journal presets (Nature, Elsevier, Springer) |
| styles | 6 | vale rules (4) + CSL styles (2) |
| platform | 4 | CI pipeline, security scanning, release workflow, real-material validation |

The preflight resolver MUST use `CommandRegistry` (not the capability ledger) to compute `available_commands` and `blocked_commands`. The capability ledger at `changes/paper-core-preflight/capability-ledger.yaml` documents design coverage but is NOT the runtime source for command eligibility.

## 1. Preflight Resolution

### 1.1 Input

The preflight resolver MUST accept the following inputs:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_root` | `Path` | Yes | Resolved project root directory |
| `command` | `str \| None` | No | Specific command to preflight for. When `None`, returns general pipeline state |
| `review_config` | `ReviewConfigSnapshot \| None` | No | Pre-loaded review config snapshot. If `None`, loads from `outputs/review_config.yaml` via `load_review_config_snapshot()` |

The resolver MUST reject `project_root` values that do not point to an existing directory. The resolver MUST handle `command` values that are not recognized by returning a blocker.

### 1.2 Resolution Order

For each resolvable field, the resolver MUST evaluate sources in this precedence (highest wins):

1. **Explicit CLI flags** — values passed directly via command-line arguments
2. **review_config.yaml values** — values from the project's review configuration
3. **Inferred from current state.yaml** — values derived from pipeline state
4. **Defaults** — hardcoded fallback values

When a higher-precedence source provides a value, lower-precedence sources MUST NOT override it.

### 1.3 CommandRegistry

The preflight resolver MUST resolve commands via `CommandRegistry` (core layer), NOT via `PIPELINE_MAP` (CLI layer). The `CommandRegistry` provides:

- Command name → stage mapping (minimum stage requirement)
- Command name → gate requirements (required gates)
- Command name → operation classification (`create` | `audit` | `revise`)
- Command name → state policy (`pipeline_initializer` | `pipeline_governed` | `standalone_allowed`)

**v1 scope**: `COMMAND_REGISTRY` is a transitory mirror of existing metadata. Dispatch remains authoritative. Parity tests detect divergence. Full migration of Dispatch and Orchestrator to consume COMMAND_REGISTRY is a v2 concern.

The resolver MUST NOT reach into CLI-layer constants to determine command metadata.

### 1.4 Fields

#### 1.4.1 `operation`

| Property | Value |
|----------|-------|
| Type | `str` — one of `create`, `audit`, `revise`, `unknown` |
| Source | Inferred from `command` parameter via `CommandRegistry` |
| Default | `"unknown"` when `command` is `None` |
| Required | No |
| Changes gates | No |
| Changes instructions | No |

Resolution rules:
- `create` when command produces new artifacts (e.g., `init`, `search`, `screen`, `draft:outline`, `draft:section`, `draft:all`, `render`)
- `audit` when command evaluates existing artifacts (e.g., `lint:bib`, `check:refs`, `lint:style`, `audit:reporting`, `audit:ethics`, `audit:factuality`, `audit:tables`, `audit:quality-appraisal`, `audit:prose`, `audit:claims`, `audit:citations`, `audit:writing-quality`, `audit:code-health`, `gate:method`, `verify`)
- `revise` when command modifies existing artifacts (e.g., `import:bib`, `zotero:sync`)
- `create` when command generates a new artifact (e.g., `protocol`, `draft:outline`)
- `unknown` when no command is specified (general preflight)

#### 1.4.2 `review_mode`

| Property | Value |
|----------|-------|
| Type | `str` — one of `rapid`, `academic` |
| Source | `review_config.yaml["mode"]` |
| Default | `"rapid"` |
| Required | No |
| Changes gates | No |
| Changes instructions | No |

In v1, `review_mode` is reported and may produce warnings (e.g., "review_mode is academic but search window not configured"). It does NOT modify persisted gates or command eligibility in this sprint. If `review_mode` must affect eligibility in the future, the rules should be added to `CommandSpec` or an explicit policy mechanism.

#### 1.4.3 `current_stage`

| Property | Value |
|----------|-------|
| Type | `str` |
| Source | `state.yaml["stage"]` |
| Default | `"bootstrap"` if state.yaml missing |
| Required | Yes |
| Changes gates | No |
| Changes instructions | No |

Valid values: `bootstrap`, `search`, `screen`, `outline`, `drafting`, `validating`, `rendering`, `rendered`.

#### 1.4.4 `current_gates`

| Property | Value |
|----------|-------|
| Type | `dict[str, bool]` |
| Source | `state.yaml["gates"]` |
| Default | All required gates `False` if state.yaml missing |
| Required | Yes |
| Changes gates | No |
| Changes instructions | No |

The resolver MUST return all 13 required gates plus any soft gates present in state.yaml.

Required gates: `repo_initialized`, `search_completed`, `screened_evidence`, `outline_drafted`, `sections_completed`, `bib_imported`, `bib_normalized`, `citations_resolved`, `refs_validated`, `style_passed`, `reporting_passed`, `render_passed`, `ready_for_delivery`.

Soft gates: `citation_verified`, `ethics_passed`.

#### 1.4.5 `available_commands`

| Property | Value |
|----------|-------|
| Type | `list[str]` |
| Source | Computed from `current_stage`, `current_gates`, and `state_missing`/`state_invalid` via `_is_policy_eligible()` |
| Default | `[]` |
| Required | Yes |
| Changes gates | No |
| Changes instructions | Yes |

A command belongs to `available_commands` if and only if `_is_policy_eligible(spec, current_stage, current_gates, state_missing=..., state_invalid=...)` returns `True`. There are no additional prose rules — `_is_policy_eligible` is the single authority.

#### 1.4.6 `blocked_commands`

| Property | Value |
|----------|-------|
| Type | `list[BlockedCommand]` |
| Source | Computed from `current_stage`, `current_gates`, and command preconditions via `CommandRegistry` |
| Default | `[]` |
| Required | Yes |
| Changes gates | No |
| Changes instructions | Yes |

Each `BlockedCommand` MUST contain:
- `command`: the command name
- `reason`: human-readable explanation of why the command is blocked
- `required_stage`: the minimum stage required (if stage is the blocker), else `None`
- `missing_gates`: tuple of gates that must be True (if gates are the blocker), else empty tuple

This is a comprehensive list of ALL commands not eligible at the current state, regardless of whether a specific command was requested.

#### 1.4.7 `next_action`

| Property | Value |
|----------|-------|
| Type | `str \| None` |
| Source | Pipeline logic — the command that advances the pipeline most efficiently |
| Default | `None` |
| Required | No |
| Changes gates | No |
| Changes instructions | Yes |

**When `next_action` is computed:**

```python
if command is not None:
    # Command-specific preflight: no recommendation needed
    next_action = None
elif state_invalid:
    # Corrupt state: cannot safely recommend an action
    next_action = None
elif state_missing:
    # Missing state: recommend the concrete resolution
    next_action = "init"
else:
    next_action = _compute_next_action(current_stage, current_gates)
```

**The `_compute_next_action` algorithm** filters by eligibility:

```python
candidates = [
    spec for spec in COMMAND_REGISTRY.values()
    if spec.workflow_rank is not None
    and _is_policy_eligible(spec, current_stage, current_gates, state_missing=False, state_invalid=False)
    and any(
        not current_gates.get(gate, False)
        for gate in spec.recommended_when_gates_missing
    )
]
candidates.sort(key=lambda s: s.workflow_rank)
next_action = candidates[0].id if candidates else None
```

**Why `recommended_when_gates_missing` not `produced_gates`:**
- `produced_gates` describes what a command CAN set to True
- `recommended_when_gates_missing` determines WHEN to recommend the command
- Example: `import:bib` produces `("bib_imported", "bib_normalized")` but is recommended only when `("bib_imported",)` is missing. If only `bib_normalized` is missing, `lint:bib` should be recommended instead.

#### 1.4.8 `blockers`

| Property | Value |
|----------|-------|
| Type | `list[PreflightBlocker]` |
| Source | Computed from state consistency checks and command eligibility |
| Default | `[]` |
| Required | Yes |
| Changes gates | No |
| Changes instructions | No |

Each `PreflightBlocker` MUST contain:
- `code`: machine-readable blocker code (e.g., `state_missing`, `state_invalid`, `unknown_command`, `stage_gates_inconsistency`, `gate_not_passed`, `stage_not_reached`)
- `scope`: `"pipeline"` (blocks all workflow-governed commands; standalone commands remain eligible) or `"command"` (blocks a specific command)
- `message`: human-readable explanation of the blocker
- `resolution`: what to do about it

**Scoping rules:**
- For **general preflight** (no command specified): `blockers` contains only pipeline-level blockers (scope=`"pipeline"`). These are conditions that prevent workflow-governed commands from executing; standalone commands remain eligible.
- For **command-specific preflight** (`command` specified): `blockers` contains the specific reasons the requested command cannot execute (scope=`"command"`). Pipeline-level blockers are also included if they exist.

Examples:
- Pipeline blocker: missing state.yaml, invalid state.yaml, stage-gates inconsistency
- Command blocker: gate not passed (e.g., `verify` requires `render_passed`), stage not reached (e.g., `render` requires stage `rendering`)

#### 1.4.9 `warnings`

| Property | Value |
|----------|-------|
| Type | `list[str]` |
| Source | Computed from state consistency checks and configuration analysis |
| Default | `[]` |
| Required | Yes |
| Changes gates | No |
| Changes instructions | No |

Warnings indicate conditions that do not block execution but may affect quality. Examples:
- review_mode is `rapid` but command might benefit from `academic`
- Search window not configured in academic mode
- State has legacy stage name (auto-upgraded)
- network_policy indicates external dependency but availability not verified (v1 limitation)

#### 1.4.10 `can_proceed`

| Property | Value |
|----------|-------|
| Type | `bool` |
| Source | CommandRegistry policy |
| Default | `False` |
| Required | Yes |
| Changes gates | No |
| Changes instructions | No |

The resolver MUST compute `can_proceed` using a single eligibility function that considers state validity:

```python
def _is_policy_eligible(
    spec: CommandSpec,
    current_stage: str,
    current_gates: dict[str, bool],
    *,
    state_missing: bool,
    state_invalid: bool,
) -> bool:
    """Unified eligibility check for can_proceed, available_commands, blocked_commands, next_action."""
    if state_invalid:
        # Corrupt state blocks everything except standalone commands
        return spec.state_policy == "standalone_allowed"

    if state_missing:
        # Missing state blocks pipeline-governed commands; standalone and init allowed
        return spec.state_policy in {"standalone_allowed", "pipeline_initializer"}

    if spec.state_policy in {"standalone_allowed", "pipeline_initializer"}:
        return True

    return (
        _stage_index(current_stage) >= _stage_index(spec.minimum_stage)
        and all(current_gates.get(gate, False) for gate in spec.required_gates)
    )
```

Then:

```python
if command is None:
    can_proceed = False
else:
    spec = COMMAND_REGISTRY.get(command)
    if spec is None:
        can_proceed = False
    else:
        can_proceed = _is_policy_eligible(
            spec, current_stage, current_gates,
            state_missing=state_missing, state_invalid=state_invalid,
        )
```

The resolver MUST NOT derive `can_proceed` solely from `len(blockers) == 0`. A pipeline with no blockers but no command specified must return `can_proceed: false`.

**Key invariant:** `can_proceed: true` IMPLIES `status: "ready"`. If a command cannot proceed, the state MUST be `blocked` or `needs_input`. There is no valid combination of `can_proceed: true` + `status: "blocked"` or `can_proceed: true` + `status: "needs_input"`.

**Scope of preflight validation (v1):**
- Existence and validity of `state.yaml` (when applicable)
- Current stage
- Gate values
- `state_policy` (standalone vs pipeline-governed)

**NOT validated by preflight (v1):**
- Command-specific arguments (`section_name`, `manuscript_path`, query, etc.)
- Runtime tool availability (Pandoc, Zotero, etc.)
- Network connectivity

The real parser is responsible for validating command-specific arguments. Preflight evaluates **workflow preconditions only**.

#### 1.4.11 `command`

| Property | Value |
|----------|-------|
| Type | `str \| None` |
| Source | Echo of input `command` parameter |
| Default | `None` when `command` is `None` |
| Required | No |
| Changes gates | No |
| Changes instructions | No |

This field echoes the input command for machine consumption. It is `None` for general (command-less) preflight calls.

### 1.5 PreflightResult

The resolver MUST return a `PreflightResult` dataclass:

```python
@dataclass(frozen=True)
class BlockedCommand:
    """A command that is not eligible at the current pipeline state."""
    command: str
    reason: str
    required_stage: str | None = None
    missing_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreflightResult:
    """Read-only snapshot of pipeline status for agents and CLI."""
    schema_version: str                   # "1.0"
    status: str                          # ready | needs_input | blocked
    operation: str                       # create | audit | revise | unknown
    review_mode: str                     # rapid | academic
    current_stage: str                   # bootstrap..rendered
    current_gates: dict[str, bool]       # all gates with bool values
    available_commands: list[str]        # commands executable at current state
    blocked_commands: list[BlockedCommand]  # typed blocked command entries
    next_action: str | None              # recommended next command
    blockers: list[PreflightBlocker]     # structured blockers (scope-aware)
    warnings: list[str]                  # non-blocking observations
    can_proceed: bool                    # whether command can execute NOW (policy-eligible)
    command: str | None                  # echo of input command (if any)
    readiness_scope: str                 # always "workflow_preconditions_only" in v1
```

The resolver MUST NOT expose fields that lack an implementable source in v1. Specifically, the following fields are NOT part of `PreflightResult` and MUST NOT be computed, serialized, or documented as available:

- `release_profile` — no authoritative source in v1; deferred to v2+
- `execution_mode` — no authoritative source in v1; deferred to v2+
- `evidence_access` — no authoritative source in v1; deferred to v2+
- `target` — no authoritative source in v1; deferred to v2+

### 1.6 States

The preflight resolver MUST report one of these states:

| State | Meaning | Exit Code |
|-------|---------|-----------|
| `ready` | Pipeline state is valid and resolvable, no pipeline blockers | 0 |
| `needs_input` | Requires human input to resolve fields (e.g., missing state for pipeline-governed command) | 2 |
| `blocked` | Has blockers that prevent execution (e.g., invalid state, unknown command, command not eligible) | 1 |

The state MUST be computed with this precedence:

```python
spec = COMMAND_REGISTRY.get(command) if command else None

if command is not None and spec is None:
    # Unknown command
    status = "blocked"
elif state_missing:
    if command is None or spec.state_policy == "pipeline_governed":
        status = "needs_input"
    else:
        # Standalone or pipeline_initializer: ignore missing state, report as warning
        status = "ready"
elif state_invalid:
    if command is not None and spec.state_policy == "standalone_allowed":
        # Standalone command: ignore invalid state, report as warning
        status = "ready"
    else:
        # pipeline_initializer or pipeline_governed: corrupt state blocks
        status = "blocked"
elif command is not None and not workflow_eligible:
    status = "blocked"
else:
    status = "ready"
```

**Precedence order:**
1. `command is not None` and `spec is None` → `blocked` (unknown command)
2. `state_missing` + `(command is None or pipeline_governed)` → `needs_input` (human must run `paper init`)
3. `state_missing` + `(standalone or pipeline_initializer)` → `ready` + warning (no state required)
4. `state_invalid` + `standalone` → `ready` + warning (standalone exempt from corrupt state)
5. `state_invalid` + `pipeline_initializer` → `blocked` (corrupt state blocks init)
6. `state_invalid` → `blocked` (corrupted state, cannot proceed)
7. Command not workflow-eligible → `blocked` (stage or gates not met)
8. Otherwise → `ready`

**Standalone commands are exempt from corrupt state (#4):** They can execute regardless of state.yaml validity.
**pipeline_initializer commands are NOT exempt from corrupt state (#5):** If state.yaml exists and is corrupt, init is blocked. The init command creates state.yaml; if one already exists and is corrupt, the human must fix it first.

#### 1.6.1 `ready` Semantics

The `ready` state has two distinct meanings depending on context:

- **General preflight** (no `command` specified): `ready` means the pipeline state is valid and resolvable. The response includes `next_action` with a recommended command, but `can_proceed` is `False` (no command was requested, so there is nothing to "proceed" with).

- **Command-specific preflight** (`command` specified): `ready` IMPLIES `can_proceed: true`. The resolver MUST NOT return `status: "ready"` with `can_proceed: false` when a specific command is requested. If the command cannot proceed, the state MUST be `blocked` or `needs_input`.

| Scenario | status | can_proceed | next_action |
|----------|--------|-------------|-------------|
| General preflight, pipeline valid | `ready` | `False` | `str` (recommended command) |
| General preflight, pipeline invalid | `blocked` | `False` | `None` |
| Command preflight, command available | `ready` | `True` | `None` |
| Command preflight, command blocked | `blocked` | `False` | `None` |
| Command preflight, needs input | `needs_input` | `False` | `None` |

The resolver MUST NEVER return `status: "ready"` + `can_proceed: false` when a `command` parameter is provided.

### 1.7 External Audit Without state.yaml

For v1, `paper init` is REQUIRED before any **pipeline-governed** command can execute. The preflight resolver MUST return `needs_input` when state.yaml is missing and the requested command has `state_policy="pipeline_governed"`.

**Standalone commands are exempt.** Commands with `state_policy="standalone_allowed"` (Phase 0 audit commands: `audit:prose`, `audit:claims`, `audit:citations`, `audit:ethics`, `audit:writing-quality`, `audit:factuality`, `audit:tables`, `audit:quality-appraisal`, `audit:code-health`, plus `gate:method`, Zotero, thesaurus, mesh, doctor, trace, graph-overview) can execute without `state.yaml`. They are eligible regardless of pipeline state. Note: `audit:reporting` is an exception — it is `pipeline_governed` and goes through the Orchestrator.

External audit without a prior `paper init` is a v2 limitation **only for pipeline-governed commands**. In v2, the resolver MAY support bootstrapping state from review_config.yaml alone for read-only pipeline-governed audit commands. This is explicitly out of scope for v1.

### 1.8 Deferred Decisions (v2)

The following behaviors are explicitly deferred to v2:

- **`automatic` mode**: When `execution_mode` is `automatic`, human-in-the-loop prompts are suppressed. `stop_on_error` remains the safe default. The `automatic` mode only controls interaction semantics, not error policy. This is deferred because `execution_mode` has no authoritative source in v1.
- **`release_profile`**: Profile-specific behavior (e.g., fast vs. thorough). Deferred because no config source exists in v1.
- **`evidence_access`**: Whether external APIs are available. Deferred because `CapabilityResolver` is a v2 concern.
- **CapabilityResolver**: Runtime availability checking (is Consensus MCP authenticated? Is Pandoc installed?). The static `CommandRegistry` doesn't answer this. Deferred to v2.

## 2. CLI Command

### 2.1 Usage

```
paper [--output-format json|text] [--project PATH] preflight [--command CMD]
```

Note: `--output-format` and `--project` are **root-level flags** defined before the subcommand. The `--command` flag is specific to the `preflight` subcommand.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output-format` | `json\|text` | `text` | Output format (root-level flag) |
| `--project` | `Path` | auto-detect | Project root directory (root-level flag) |
| `--command` | `str` | `None` | Specific command to preflight for (subcommand flag) |

### 2.2 Behavior

The `preflight` command MUST:

1. **Be read-only** — MUST NOT modify state.yaml, review_config.yaml, run.yaml, or any other project file
2. **Return exit code 0** when preflight state is `ready`
3. **Return exit code 2** when preflight state is `needs_input`
4. **Return exit code 1** when preflight state is `blocked` or an internal error occurs
5. **Support `--output-format json`** for machine/agent consumption
6. **Support `--output-format text`** for human consumption
7. **Validate `--command`** against the `CommandRegistry`; reject unknown commands with exit code 1
8. **Handle missing state.yaml** gracefully — general preflight or pipeline_governed command → `needs_input` with message "Project not initialized. Run `paper init` first."; pipeline_initializer init → `ready` + warning; standalone_allowed command → `ready` + warning
9. **Handle missing review_config.yaml** gracefully — use defaults (already safe)
10. **Handle invalid state.yaml** gracefully — return `blocked` with the parse error message
11. **Preserve standalone command semantics** — commands with `state_policy="standalone_allowed"` are NOT blocked by pipeline gates

### 2.3 JSON Output Schema

When `--output-format json`, the command MUST output the following JSON structure to stdout:

```json
{
  "schema_version": "1.0",
  "status": "ready",
  "operation": "create",
  "review_mode": "rapid",
  "current_stage": "drafting",
  "current_gates": {
    "repo_initialized": true,
    "search_completed": true,
    "screened_evidence": true,
    "outline_drafted": true,
    "sections_completed": false,
    "bib_imported": false,
    "bib_normalized": false,
    "citations_resolved": false,
    "refs_validated": false,
    "style_passed": false,
    "reporting_passed": false,
    "render_passed": false,
    "ready_for_delivery": false
  },
  "available_commands": ["draft:section", "draft:all", "audit:prose", "audit:claims", "audit:citations", "audit:ethics", "audit:writing-quality", "audit:factuality", "audit:tables", "audit:quality-appraisal", "audit:code-health", "gate:method"],
  "blocked_commands": [
    {
      "command": "render",
      "reason": "requires stage 'rendering'",
      "required_stage": "rendering",
      "missing_gates": []
    }
  ],
  "next_action": null,
  "blockers": [],
  "warnings": [],
  "can_proceed": true,
  "command": "draft:section"
}
```

The JSON MUST be valid JSON (no trailing commas, proper quoting). The JSON MUST be emitted to stdout. Diagnostic messages MUST be emitted to stderr, not stdout.

The following fields MUST NOT appear in the JSON output:
- `release_profile`
- `execution_mode`
- `evidence_access`
- `target`
- `project_root` (this is an input, not an output)
- `preflight_state` (replaced by `status`)

### 2.4 Text Output Format

When `--output-format text`, the command MUST output human-readable text to stdout:

```
Preflight: ready
Stage: drafting
Command: draft:section
Operation: create
Review Mode: rapid

Available Commands:
  - draft:section
  - draft:all

Blocked Commands:
  - render: requires stage 'rendering' (current: drafting)
  - verify: requires gate 'render_passed'
  - lint:bib: requires stage 'validating' (current: drafting)
  - check:refs: requires stage 'validating' (current: drafting)

Next Action: (none — command-specific preflight)

Blockers: (none)
Warnings:
  - Search window not configured for academic mode

Can Proceed: yes
```

The text format MUST include all of the following sections, in order:
1. Preflight status header
2. Current stage
3. Command being prefighted (if any)
4. Operation type
5. Review mode
6. Available commands list
7. Blocked commands list with reasons
8. Next action (recommended command)
9. Blockers list (or "(none)")
10. Warnings list (or "(none)")
11. Can proceed indicator

The text format MUST NOT include any of the following:
- `release_profile`
- `execution_mode`
- `evidence_access`
- `target`

## 3. OrchestratorResult Enhancement

### 3.1 Fields to Add to JSON Serialization

The following fields MUST be present in the OrchestratorResult JSON serialization. There are TWO serialization points:

1. **`_serialize_result()`** in `cli/paper/output.py:147` — CLI JSON output for `--output-format json`
2. **`_build_command_log_payload()`** in `harness/services/orchestrator.py:73` — structured command log for run lineage

Both MUST include these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gate_changes` | `dict[str, bool]` | `{}` | Which gates changed during execution |
| `state_changes` | `dict[str, Any]` | `{}` | What state changed (stage_before, stage_after) |
| `failure_policy` | `str` | `"stop_on_error"` | How errors are handled |

These fields are ALREADY present on the `OrchestratorResult` dataclass (`harness/services/orchestrator.py:51-53`). The specification confirms they MUST be included in both JSON payloads.

### 3.2 Backward Compatibility

- New fields MUST have defaults — `gate_changes` defaults to `{}`, `state_changes` defaults to `{}`
- Existing fields MUST NOT change their names, types, or semantics
- Old consumers that do not read the new fields MUST NOT break
- The `failure_policy` field is already present on OrchestratorResult and MUST be serialized

## 4. Integration Points

### 4.1 review_config.yaml

- Preflight MUST read from `review_config.yaml` via `harness.services.review_config.load_review_config_snapshot()` (or use a pre-loaded `ReviewConfigSnapshot`)
- Preflight MUST NOT write to `review_config.yaml`
- If `review_config.yaml` is missing, defaults apply (`mode=rapid`, `search_window=None`)

#### Scenario: review_config.yaml exists with mode=academic

- GIVEN `review_config.yaml` contains `mode: academic`
- WHEN preflight resolves `review_mode`
- THEN `review_mode` is `"academic"`
- AND a warning may be emitted if search window is not configured

#### Scenario: review_config.yaml missing

- GIVEN `review_config.yaml` does not exist at `outputs/review_config.yaml`
- WHEN preflight resolves `review_mode`
- THEN `review_mode` is `"rapid"` (default)
- AND a warning is emitted: "review_config.yaml not found, using defaults"

### 4.2 state.yaml

- Preflight MUST read from `state.yaml` via `harness.services.state_manager.StateManager`
- Preflight MUST NOT modify `state.yaml`
- Preflight MUST handle missing `state.yaml` conditionally: general preflight or pipeline_governed command → `needs_input`; pipeline_initializer init → `ready` + warning; standalone_allowed command → `ready` + warning
- Preflight MUST handle invalid `state.yaml` by returning `blocked` state with parse error
- Preflight MUST detect stage-gates inconsistency and report it as a blocker

#### Scenario: state.yaml exists with valid state

- GIVEN `outputs/state.yaml` contains `stage: drafting` with `outline_drafted: true`
- WHEN preflight resolves `current_stage`
- THEN `current_stage` is `"drafting"`
- AND `available_commands` includes `draft:section`, `draft:all` (lint:bib and check:refs require stage `validating`)

#### Scenario: state.yaml missing

- GIVEN `outputs/state.yaml` does not exist
- WHEN preflight is invoked with `command=search`
- THEN preflight state is `needs_input`
- AND `blockers` contains "Project not initialized. Run `paper init` first."
- AND exit code is 2

#### Scenario: state.yaml invalid

- GIVEN `outputs/state.yaml` contains malformed YAML
- WHEN preflight attempts to load state
- THEN preflight state is `blocked`
- AND `blockers` contains the parse error message
- AND exit code is 1

### 4.3 run.yaml

run.yaml integration is deferred to v2+. The preflight resolver MUST NOT read from or write to `run.yaml` in v1. No run.yaml-related fields are part of `PreflightResult`.

### 4.4 OrchestratorRequest

OrchestratorRequest integration is deferred to v2. Preflight is an independent query — it does not couple with the execution contract. In v2, preflight metadata MAY be passed via the existing `args: dict[str, Any]` field on `OrchestratorRequest`.

## 5. Error Handling

| Condition | Preflight State | Exit Code | Message |
|-----------|----------------|-----------|---------|
| Missing state.yaml, command is `pipeline_governed` and not `init` | `needs_input` | 2 | "Project not initialized. Run `paper init` first." |
| Missing state.yaml, command is `standalone_allowed` | `ready` | 0 | (standalone command, no state required) |
| Missing state.yaml, command is `init` | `ready` | 0 | (no error) |
| Invalid state.yaml (parse error) | `blocked` | 1 | "Invalid state.yaml: {parse_error}" |
| Invalid state.yaml (schema violation) | `blocked` | 1 | "State schema violation: {validation_error}" |
| Missing review_config.yaml | `ready` | 0 | (defaults applied, no error) |
| Unknown command | `blocked` | 1 | "Unknown command: {command}" |
| Stage-gates inconsistency | `blocked` | 1 | "State inconsistency: {inconsistency_detail}" |
| Command not eligible (gate not passed, pipeline_governed) | `blocked` | 1 | "Command '{command}' requires gate '{gate}' which is not passed" |
| Command not eligible (stage not reached, pipeline_governed) | `blocked` | 1 | "Command '{command}' requires stage '{stage}' (current: {current_stage})" |

#### Scenario: Unknown command preflighted

- GIVEN preflight is invoked with `--command nonexistent_cmd`
- WHEN command is validated against the `CommandRegistry`
- THEN preflight state is `blocked`
- AND `blockers` contains "Unknown command: nonexistent_cmd"
- AND exit code is 1

#### Scenario: Stage-gates inconsistency detected

- GIVEN state.yaml has `stage: rendering` but `sections_completed: false`
- WHEN preflight validates stage consistency
- THEN preflight state is `blocked`
- AND `blockers` contains "Stage-gates inconsistency: stage 'rendering' requires gate 'sections_completed' which is False"
- AND exit code is 1

#### Scenario: Standalone command not blocked by pipeline gates

- GIVEN state.yaml has `stage: bootstrap` with all gates `false`
- WHEN preflight is invoked with `--command audit:prose`
- AND `audit:prose` has `state_policy="standalone_allowed"`
- THEN `audit:prose` is NOT in `blocked_commands` (pipeline gates don't apply)
- AND `can_proceed` is `True` (standalone commands are always eligible)
- AND status is `ready`

#### Scenario: Standalone command without state.yaml

- GIVEN `outputs/state.yaml` does not exist
- WHEN preflight is invoked with `--command audit:prose`
- AND `audit:prose` has `state_policy="standalone_allowed"`
- THEN preflight state is `ready` (standalone command, no state required)
- AND `can_proceed` is `True`
- AND no `state_missing` blocker is emitted

## 6. Compatibility

- All existing commands MUST continue working without preflight
- Preflight is additive, not a replacement for existing orchestration
- JSON output is new; text output is new; no existing output format changes
- The preflight command is registered as a new subcommand; existing subcommands are unaffected
- Existing `--output-format` flag on other commands is unchanged
- Existing exit code contracts on other commands are unchanged
- Standalone commands (`audit:prose`, `audit:claims`, `gate:method`, etc.) retain their existing behavior — preflight does not change their eligibility rules

#### Scenario: Existing command works without preflight

- GIVEN a project with valid state.yaml at stage `drafting`
- WHEN `paper draft section introduction` is invoked (no preflight)
- THEN the command executes normally through the Orchestrator
- AND exit code follows existing contracts

#### Scenario: Preflight does not mutate state

- GIVEN a project with state.yaml at stage `search`
- WHEN `paper preflight --command screen` is invoked
- THEN state.yaml is not modified
- AND the stage remains `search` after preflight completes
