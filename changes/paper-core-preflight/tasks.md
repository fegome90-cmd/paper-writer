# Tasks: paper-core-preflight

## Exploration and Documentation Tasks (Completed)

These tasks were completed during the exploration phase and do NOT require implementation:

| Task | Status | Artifacts |
|------|--------|-----------|
| Full repository exploration | ✅ Complete | capability-ledger.yaml, REPORT.md |
| Structural map | ✅ Complete | structural-map.md |
| Invocation map | ✅ Complete | invocation-map.md |
| Data flow map | ✅ Complete | data-flow.md |
| Orphan and overlap report | ✅ Complete | orphan-and-overlap-report.md |
| Core boundary decisions | ✅ Complete | core-boundary-decisions.md |
| Roadmap coverage matrix | ✅ Complete | roadmap-coverage-matrix.md |
| Contract reconciliation | ✅ Complete | contract-reconciliation.md |
| Command registry design | ✅ Complete | command-registry.md |
| SDD artifacts reconciliation | ✅ Complete | proposal.md, spec.md, design.md updated |

---

## Slice A: OrchestratorResult JSON Completion

**Goal:** Add `gate_changes`, `state_changes`, and `failure_policy` to the OrchestratorResult JSON serialization. Independent of preflight — can be shipped first.

### Task A1: Extend `_serialize_result()` in output.py

**Objective:** Add 3 missing fields to the JSON output of OrchestratorResult.

**Probable Files:**
- `cli/paper/output.py` (modify `_serialize_result` function at line 147)

**Tests:**
- `tests/test_cli/test_output.py` (add tests)
  - `test_serialize_result_includes_gate_changes` — gate_changes dict present in JSON output
  - `test_serialize_result_includes_state_changes` — state_changes dict present in JSON output
  - `test_serialize_result_includes_failure_policy` — failure_policy string present in JSON output
  - `test_serialize_result_backward_compat` — existing 9 fields still present and unchanged
  - `test_serialize_result_empty_gate_changes` — empty dict serializes correctly
  - `test_serialize_result_nested_state_changes` — stage_before/stage_after inside state_changes serialize correctly

**Dependencies:** None

**Completion Criteria:**
- `_serialize_result` adds three new keys:
  - `"gate_changes": to_json_value(result.gate_changes)`
  - `"state_changes": to_json_value(result.state_changes)`
  - `"failure_policy": to_json_value(result.failure_policy)`
- Existing 9 fields remain unchanged (backward compatible)
- All existing tests in `tests/test_cli/` still pass
- New tests pass

**Verification:** `uv run pytest tests/test_cli/test_output.py -v`

---

### Task A2: Verify command-log contract

**Objective:** Verify that `_build_command_log_payload()` already includes `gate_changes`, `state_changes`, and `failure_policy`. This is a test-only task — no production code changes.

**Probable Files:**
- `tests/harness/test_orchestrator_payload.py` (new or modify existing)

**Tests:**
- `tests/harness/test_orchestrator_payload.py`
  - `test_build_command_log_payload_includes_gate_changes` — gate_changes dict present in payload
  - `test_build_command_log_payload_includes_state_changes` — state_changes dict present in payload
  - `test_build_command_log_payload_includes_failure_policy` — failure_policy string present in payload
  - `test_build_command_log_payload_backward_compat` — existing fields still present and unchanged

**Dependencies:** None (can run parallel with A1)

**Completion Criteria:**
- `_build_command_log_payload` already includes `gate_changes`, `state_changes`, `failure_policy` (verified by code inspection)
- Tests confirm these fields are present in the serialized payload
- No production code changes needed
- All existing tests still pass
- New verification tests pass

**Note:** If `_build_command_log_payload` does NOT include these fields, escalate to user — this contradicts the codebase exploration findings.

**Verification:** `uv run pytest tests/harness/test_orchestrator_payload.py -v`

---

## Slice B: Preflight System

**Goal:** Implement the preflight resolver, CommandRegistry, and CLI command.

### Task B1: Create CommandSpec and COMMAND_REGISTRY

**Objective:** Define the transitory command registry in the core layer. In v1, this mirrors existing metadata from `PIPELINE_MAP` and Phase 0 registrations. Dispatch remains authoritative. Parity tests detect divergence.

**Probable Files:**
- `harness/domain/command_spec.py` (new)

**Tests:**
- `tests/harness/test_command_spec.py` (new)
  - `test_command_registry_has_all_orchestrated_commands` — verify all PIPELINE_MAP keys have a CommandSpec
  - `test_command_registry_has_all_phase0_commands` — verify audit, zotero, thesaurus, mesh commands
  - `test_command_registry_parity_with_pipeline_map` — parity test: every PIPELINE_MAP dispatch_key exists in COMMAND_REGISTRY
  - `test_command_registry_parity_with_parser` — parity test: every parser subcommand has a matching cli_path
  - `test_command_spec_frozen` — CommandSpec is immutable
  - `test_command_spec_tuples` — required_gates and requires_args are tuples, not lists
  - `test_minimum_stage_is_valid` — all minimum_stage values are in STAGE_ORDER
  - `test_required_gates_are_valid` — all gate names are in ManuscriptState.REQUIRED_GATES or SOFT_GATES
  - `test_operation_is_valid` — all operation values are in {create, audit, revise, unknown}
  - `test_handler_kind_is_valid` — all handler_kind values are in {orchestrated, callback_direct}
  - `test_owner_kind_is_valid` — all owner_kind values are in {core, integration, local_subproject}
  - `test_standalone_commands_have_empty_gates` — standalone commands have required_gates=()
  - `test_pipeline_initializer_commands_have_empty_gates` — pipeline_initializer commands have required_gates=()
  - `test_standalone_commands_have_state_policy` — audit:prose, audit:claims, gate:method have state_policy="standalone_allowed"
  - `test_init_has_pipeline_initializer_policy` — init has state_policy="pipeline_initializer"
  - `test_workflow_rank_fields` — commands with workflow_rank have produced_gates and recommended_when_gates_missing

**Dependencies:** None

**Completion Criteria:**
- `CommandSpec` dataclass with all fields from design.md:
  - Identity: `id`, `dispatch_key`, `cli_path` (tuple)
  - Classification: `operation`, `handler_kind`, `owner_kind`
  - Stage: `minimum_stage`, `required_gates` (tuple)
  - Progression: `advances_pipeline`, `produced_gates`, `next_stage`, `workflow_rank`, `recommended_when_gates_missing`
  - Production: `target`, `mutates_project`, `creates_run`
  - Network: `network_policy`
  - Arguments: `requires_args` (tuple)
  - State: `state_policy`
  - Info: `description`
- `COMMAND_REGISTRY` dict with all 40+ commands (orchestrated + Phase 0 + external)
- All orchestrated commands from PIPELINE_MAP are present
- All Phase 0 commands (audit, gate:method, trace, graph-overview) are present
- All Zotero subcommands are present (including zotero:template)
- All thesaurus subcommands are present
- All mesh subcommands are present
- Standalone commands have `state_policy="standalone_allowed"` and `required_gates=()`
- `init` has `state_policy="pipeline_initializer"` and `required_gates=()`
- All commands with `workflow_rank` have `produced_gates` and `recommended_when_gates_missing`
- Parity test verifies PIPELINE_MAP dispatch_keys ⊆ COMMAND_REGISTRY dispatch_keys
- Semantic parity test verifies chain minimum_stage == "screen"
- All tests pass

**Verification:** `uv run pytest tests/harness/test_command_spec.py -v`

---

### Task B2: Create PreflightResult dataclasses

**Objective:** Define the core data model — `PreflightResult`, `PreflightBlocker`, and `BlockedCommand` — as frozen dataclasses.

**Probable Files:**
- `harness/services/review_config.py` (modify — add `ReviewConfigSnapshot` dataclass and `load_review_config_snapshot()` function)
- `harness/services/preflight.py` (new — resolver only, imports from review_config.py)

**Tests:**
- `tests/harness/test_preflight.py` (new)
  - `test_preflight_result_construction` — build with all required fields, assert types
  - `test_preflight_blocker_construction` — code, scope, message, resolution all populated
  - `test_blocked_command_construction` — command, reason, required_stage, missing_gates all populated
  - `test_blocked_command_missing_gates_tuple` — missing_gates is tuple, not list
  - `test_preflight_result_immutability` — attempt attribute reassignment raises FrozenInstanceError
  - `test_preflight_result_defaults` — empty lists/None defaults where specified
  - `test_review_config_snapshot_construction` — values, source, warnings all populated
  - `test_review_config_snapshot_source_file` — source="file" when loaded from file
  - `test_review_config_snapshot_source_default_missing` — source="default_missing" when file missing
  - `test_review_config_snapshot_source_default_invalid` — source="default_invalid" when file corrupt
  - `test_review_config_snapshot_immutability` — attempt attribute reassignment raises FrozenInstanceError
  - `test_legacy_loader_matches_snapshot_values_for_valid_config` — both loaders return same `mode` for valid YAML
  - `test_legacy_loader_matches_snapshot_values_for_invalid_yaml` — both loaders return defaults for corrupt file
  - `test_legacy_loader_matches_snapshot_values_for_unknown_mode` — both loaders normalize `"turbo"` → `"rapid"`
  - `test_can_proceed_false_when_no_command` — can_proceed is False when command is None, even with no blockers
  - `test_can_proceed_true_when_command_eligible` — can_proceed is True when command passes eligibility
  - `test_can_proceed_false_when_init_with_corrupt_state` — init with corrupt state → can_proceed=False, status=blocked (corrupt state blocks pipeline_initializer)

**Dependencies:** None (can run parallel with B1)

**Completion Criteria:**
- `BlockedCommand` dataclass with fields:
  - `command: str`
  - `reason: str`
  - `required_stage: str | None = None`
  - `missing_gates: tuple[str, ...] = ()`
- `PreflightResult` dataclass with exactly these fields:
  - `schema_version: str` (always "1.0")
  - `status: str` (ready | needs_input | blocked)
  - `operation: str` (create | audit | revise | unknown)
  - `review_mode: str` (rapid | academic)
  - `current_stage: str`
  - `current_gates: dict[str, bool]`
  - `available_commands: list[str]`
  - `blocked_commands: list[BlockedCommand]` (typed, not dict)
  - `next_action: str | None`
  - `blockers: list[PreflightBlocker]`
  - `warnings: list[str]`
  - `can_proceed: bool` (whether command can execute NOW)
  - `readiness_scope: str` (always "workflow_preconditions_only" in v1)
  - `command: str | None`
- `PreflightBlocker` dataclass with `code`, `scope`, `message`, `resolution`
- `ReviewConfigSnapshot` dataclass with `values`, `source`, `warnings`
- All four are `frozen=True`
- Module has proper `__all__` export list including `BlockedCommand` (exported from `preflight.py`) and `ReviewConfigSnapshot` (exported from `review_config.py`)
- All tests pass

**Verification:** `uv run pytest tests/harness/test_preflight.py -v`

---

### Task B3: Implement resolve_preflight()

**Objective:** Implement the core resolution function that reads existing state and computes a `PreflightResult`. Read-only — no mutations, no side effects.

**Probable Files:**
- `harness/services/preflight.py` (add `resolve_preflight()` function)

**Tests:**
- `tests/harness/test_preflight.py` (add tests)
  - `test_resolve_preflight_bootstrap_stage` — state at bootstrap → status ready, can_proceed=False, next_action="init"
  - `test_resolve_preflight_search_stage` — state at screen with search_completed=True → ready, next_action="screen"
  - `test_resolve_preflight_rendered_stage` — rendered stage, render_passed=True, ready_for_delivery=False → ready, next_action="verify"
  - `test_resolve_preflight_missing_state_yaml` — no state.yaml exists + no command → status needs_input, blocker state_missing
  - `test_resolve_preflight_invalid_state_yaml` — malformed YAML → status blocked, blocker with parse error
  - `test_resolve_preflight_missing_review_config` — no review_config.yaml → review_mode="rapid", warning emitted, status NOT affected
  - `test_resolve_preflight_invalid_review_config` — corrupt review_config.yaml → review_mode="rapid", warning emitted, status NOT affected
  - `test_resolve_preflight_valid_review_config` — valid review_config.yaml → review_mode from file, no warnings
  - `test_resolve_preflight_next_action_computation` — stage=bootstrap→"init", stage=search→"search", etc.
  - `test_resolve_preflight_available_commands_per_stage` — bootstrap includes init, standalone always available; search includes search but not chain (requires screen); etc.
  - `test_resolve_preflight_blocked_commands` — commands below current stage are blocked with reasons
  - `test_resolve_preflight_status_ready` — no blockers → ready
  - `test_resolve_preflight_status_needs_input` — missing state + pipeline_governed command → needs_input
  - `test_resolve_preflight_status_blocked` — invalid state → blocked
  - `test_resolve_preflight_review_mode_academic` — academic mode reflected
  - `test_resolve_preflight_review_mode_rapid` — rapid mode (default) reflected
  - `test_resolve_preflight_command_specific` — pass command="search" → focused output
  - `test_resolve_preflight_blocker_structure` — blockers have code, scope, message, resolution
  - `test_resolve_preflight_blocker_scope_pipeline` — pipeline blockers have scope="pipeline"
  - `test_resolve_preflight_blocker_scope_command` — command blockers have scope="command"
  - `test_resolve_preflight_can_proceed_false_no_command` — general preflight → can_proceed=False
  - `test_resolve_preflight_can_proceed_true_command_eligible` — command eligible → can_proceed=True
  - `test_resolve_preflight_can_proceed_false_command_blocked` — command blocked → can_proceed=False, status=blocked
  - `test_resolve_preflight_standalone_not_blocked` — audit:prose NOT in blocked_commands when pipeline gates fail
  - `test_resolve_preflight_pipeline_initializer_no_state` — init without state.yaml → status ready, not needs_input
  - `test_resolve_preflight_pipeline_initializer_corrupt_state` — init with corrupt state.yaml → status blocked (pipeline_initializer NOT exempt from corrupt state)
  - `test_resolve_preflight_standalone_corrupt_state` — audit:prose with corrupt state.yaml → status ready + warning (standalone IS exempt from corrupt state)
  - `test_resolve_preflight_unknown_command` — unknown command → status blocked, blocker unknown_command

**Dependencies:** Tasks B1, B2

**Completion Criteria:**
- `resolve_preflight(project_root, command, review_config) -> PreflightResult`
- `load_review_config_snapshot(project_root) -> ReviewConfigSnapshot` lives in `harness/services/review_config.py` (NOT in preflight.py)
- Resolution order:
  1. Load `state.yaml` via `StateManager` → `current_stage`, gate values (or defaults if missing), `state_missing`, `state_invalid`
  2. Lookup `command` in `COMMAND_REGISTRY` → `spec` (None if not provided or unknown)
  3. Load `review_config.yaml` via `load_review_config_snapshot()` → `ReviewConfigSnapshot` (or use pre-loaded snapshot)
  4. Evaluate gates → `current_gates` dict
  5. Compute `available_commands` using `_is_policy_eligible()` — single authority for all eligibility
  6. Compute `blocked_commands` using `_is_policy_eligible()` — all commands, not just requested
  7. Compute `can_proceed`: False if no command or unknown command, else `_is_policy_eligible(spec, ..., state_missing, state_invalid)`
  8. Compute `next_action`:
      - `command is not None` → None
      - `state_invalid` → None
      - `state_missing` → "init"
      - else → eligibility-filtered `_compute_next_action()`
  9. Compute `blockers`: pipeline-level for general, command-specific for command preflight
  10. Compute `status` with correct precedence:
      - unknown command → blocked
      - state_missing + pipeline_governed → needs_input
      - state_missing + standalone/init → ready + warning
      - state_invalid + standalone → ready + warning
      - state_invalid + pipeline_initializer → blocked (corrupt state blocks init)
      - state_invalid → blocked
      - command not eligible → blocked
      - otherwise → ready
  11. Add `review_config` warnings to warnings list
  12. Return frozen `PreflightResult`

**Important:** There is NO special-case jump for unknown_command. The resolver always builds a complete `PreflightResult` with all fields populated. When `command is not None` and `spec is None`, `can_proceed` is `False`, `status` is `blocked`, `next_action` is `None`, and a blocker with code `unknown_command` is appended. All other fields (`review_mode`, `current_gates`, `available_commands`, `blocked_commands`, `blockers`, `warnings`) are still computed normally.
- `_is_policy_eligible()` is the SINGLE authority used for: `can_proceed`, `available_commands`, `blocked_commands`, and `next_action` candidates
- Missing state.yaml + pipeline_governed → status needs_input, single blocker with code `state_missing`, scope `pipeline`
- Missing state.yaml + pipeline_initializer → status ready, warning about missing state
- Invalid state.yaml + pipeline_initializer → status blocked (corrupt state blocks init)
- Invalid state.yaml → status blocked, blocker with code `state_invalid`, scope `pipeline`
- Unknown command → status blocked, blocker with code `unknown_command`
- Missing review_config.yaml → review_mode defaults to "rapid", warning emitted, status NOT affected. (Tests of `source` belong to B2 snapshot tests, not B3 resolver tests.)
- Standalone commands are NOT blocked by pipeline gates or corrupt state
- All tests pass

**Verification:** `uv run pytest tests/harness/test_preflight.py -v`

---

### Task B4: Create JSON Schema

**Objective:** Create the canonical JSON schema for PreflightResult validation.

**Probable Files:**
- `schemas/preflight.schema.json` (new — must be created from scratch)

**Tests:**
- `tests/harness/test_preflight.py` (add test)
  - `test_preflight_result_matches_schema` — validate a sample PreflightResult against the schema

**Dependencies:** Task B2

**Completion Criteria:**
- `schemas/preflight.schema.json` exists with all fields from reconciled contract
- Schema validates a sample PreflightResult
- All tests pass

**Verification:** `python -m json.tool schemas/preflight.schema.json`

---

### Task B5: Implement CLI command `paper preflight`

**Objective:** Register and implement the `paper preflight` subcommand with text and JSON output modes.

**Probable Files:**
- `cli/paper/commands/preflight.py` (new — handler function)
- `cli/paper/parser.py` (modify — register `preflight` subparser)

**Tests:**
- `tests/test_cli/test_preflight_cmd.py` (new)
  - `test_preflight_help` — `--help` exits 0 and shows usage text
  - `test_preflight_text_output` — default text output contains Status/Stage/Next/Blockers sections
  - `test_preflight_json_output` — `paper --output-format json preflight` produces valid JSON with all contract fields
  - `test_preflight_exit_code_ready` — status ready → exit code 0
  - `test_preflight_exit_code_needs_input` — status needs_input → exit code 2
  - `test_preflight_exit_code_blocked` — status blocked → exit code 1
  - `test_preflight_missing_project` — no project dir → stderr error, exit code 2 (UserInputError)
  - `test_preflight_json_schema` — JSON output matches schemas/preflight.schema.json
  - `test_preflight_text_blockers_section` — when blockers exist, text shows code and resolution
  - `test_preflight_command_specific` — --command flag narrows output
  - `test_preflight_command_blocked` — --command render at stage drafting → blocked, exit code 1

**Dependencies:** Tasks B3, B4, B5a

**Completion Criteria:**
- `preflight` subparser added to `build_parser()` in `cli/paper/parser.py`
- Handler function calls `resolve_preflight` and formats output
- Text output format matches design.md
- JSON output matches `schemas/preflight.schema.json`
- Exit codes: 0 (ready), 2 (needs_input), 1 (blocked/error)
- `--project` flag respected
- `--command` flag optional
- Global flags (`--project`, `--output-format`) placed BEFORE subcommand
- All tests pass

**Verification:** `uv run paper --help && uv run pytest tests/test_cli/test_preflight_cmd.py -v`

---

### Task B5a: Modify dispatch.py callback exit code capture

**Objective:** Modify `dispatch.py` to capture callback return values and use them as exit codes. This is a BLOCKING prerequisite for Task B5 — preflight needs explicit exit codes (0, 1, 2) but the current dispatch always returns 0.

**Probable Files:**
- `cli/paper/dispatch.py` (modify — capture callback return value in both normal and clean_cancel paths)

**Tests:**
- `tests/test_cli/test_dispatch_exit_codes.py` (new)
  - `test_callback_return_int_uses_as_exit_code` — callback returns 2 → process exits 2
  - `test_callback_return_none_defaults_to_zero` — callback returns None → process exits 0 (backward compat)
  - `test_callback_return_non_int_defaults_to_zero` — callback returns "ok" → process exits 0
  - `test_callback_return_bool_not_treated_as_int` — callback returns True → process exits 0 (bool is not int)
  - `test_callback_raises_system_exit` — callback raises SystemExit(1) → Dispatch does NOT intercept; propagates
  - `test_existing_phase0_callback_behavior_unchanged` — covers all Phase 0 return patterns:
    - return None → dispatch returns 0
    - return int exacto → dispatch returns that value
    - return bool → dispatch returns 0
    - raise SystemExit → propagates without interception
  - `test_clean_cancel_returns_zero` — clean cancel path with None → 0
  - `test_clean_cancel_returns_int` — clean cancel path with int → that value

**Dependencies:** None (can run parallel with B1-B4)

**Completion Criteria:**
- In the normal path: `callback_result = func(args)` then `return callback_result if type(callback_result) is int else 0`
- In the clean_cancel path: same capture and `type(...) is int` check
- Existing Phase 0 callbacks: None → 0, int → that value, bool → 0, SystemExit → propagates (no change to existing behavior)
- Preflight handler can return 0, 1, or 2 explicitly
- All existing tests still pass
- New exit code tests pass

**Code change (both paths):**
```python
# Before:
func(args)
return 0

# After:
callback_result = func(args)
return callback_result if type(callback_result) is int else 0
```

**Verification:** `uv run pytest tests/test_cli/test_dispatch_exit_codes.py -v && make test`

---

### Task B6: Integration tests

**Objective:** End-to-end tests verifying the complete preflight flow from state initialization through CLI invocation.

**Probable Files:**
- `tests/harness/test_preflight_integration.py` (new)

**Tests:**
- `test_preflight_after_init` — run `paper init` then `paper preflight` → status ready, stage=search, next_action="search"
- `test_preflight_after_search` — run init+search then preflight → stage=screen, available_commands include screen
- `test_preflight_with_missing_state_pipeline_governed` — empty project dir + pipeline_governed command → status needs_input, blocker state_missing
- `test_preflight_with_missing_state_standalone` — empty project dir + standalone command → status ready, warning about missing state
- `test_preflight_json_output_matches_schema` — validate JSON against schema
- `test_preflight_text_output_readability` — text output contains all sections
- `test_existing_commands_still_work` — `paper init` still exits 0, no regression
- `test_preflight_academic_mode` — init with `--mode academic` → preflight review_mode=academic
- `test_preflight_after_render` — full pipeline to rendered → preflight shows verify as next_action
- `test_slice_a_json_completion` — run any orchestrated command → JSON includes gate_changes, state_changes, failure_policy
- `test_standalone_command_not_blocked` — audit:prose available even at bootstrap stage

**Dependencies:** Tasks B1–B5, A1

**Completion Criteria:**
- All integration tests pass using real filesystem (tmp_path fixture)
- Tests exercise the full path: CLI → parser → handler → resolve_preflight → output
- No regression in existing test suite

**Verification:** `uv run pytest tests/harness/test_preflight_integration.py -v && make verify`

---

### Task B7: Documentation

**Objective:** Document the preflight system: purpose, architecture, resolution logic, CLI usage, and agent integration patterns.

**Probable Files:**
- `docs/architecture/PREFLIGHT.md` (new)

**Tests:** None

**Dependencies:** Tasks B1–B6

**Completion Criteria:**
- `docs/architecture/PREFLIGHT.md` exists with sections:
  - **Purpose** — why preflight exists, what problem it solves
  - **Architecture** — read-only resolver, CommandRegistry (mirror in v1), Phase 0 command
  - **Data Model** — PreflightResult, PreflightBlocker (field tables)
  - **Resolution Order** — step-by-step from state.yaml → status
  - **Status Semantics** — ready/needs_input/blocked definitions
  - **can_proceed Semantics** — False when no command, True when command eligible
  - **Blocker Scoping** — pipeline vs command scope
  - **Standalone Commands** — state_policy, how standalone commands are handled
  - **Stage→Action Mapping** — table of stage → next_action
  - **Available Commands** — which commands are available at each stage
  - **CLI Usage** — text and JSON examples with real stage/gate IDs
  - **Agent Integration** — how agents should consume preflight JSON
  - **Extension Points** — how to add new commands, blockers, or gates
  - **Open Questions** — v2 concerns (external audit, CapabilityResolver, persistence)
- All examples verified against actual CLI
- Cross-references to `GATE_SYSTEM.md`, `TESTING_STRATEGY.md`

**Verification:** `uv run paper --output-format json preflight | python -m json.tool`

---

## Dependency Graph

```
Slice A (independent):
  Task A1 (JSON completion)
  Task A2 (command-log payload)     ← parallel with A1

Slice B:
  Task B5a (dispatch.py exit codes) ← parallel with B1-B4, BLOCKING for B5
  Task B1 (CommandRegistry)
  Task B2 (dataclasses)        ← parallel with B1
       │
       ├──→ Task B3 (resolver) ← depends on B1 + B2
       │         │
       │         ├──→ Task B5 (CLI command) ← depends on B3 + B4 + B5a
       │         │         │
       │         │         └──→ Task B6 (integration) ← depends on all
       │         │                   │
       │         │                   └──→ Task B7 (docs) ← final
       │         │
       │         └──→ Task B6 (integration)
       │
       └──→ Task B4 (JSON schema) ← depends on B2
                 │
                 └──→ Task B5 (CLI command)
```

## Execution Order

| Phase | Tasks | Notes |
|-------|-------|-------|
| 1 | Task A1, Task A2, Task B1, Task B2, Task B5a | Foundation — JSON fix + command-log + CommandRegistry + dataclasses + dispatch exit codes (parallel) |
| 2 | Task B3, Task B4 | Resolver + schema (parallel after B1+B2) |
| 3 | Task B5 | CLI command (after B3+B4+B5a) |
| 4 | Task B6 | Integration tests (after all code) |
| 5 | Task B7 | Documentation (final) |

## File Summary

| File | Action | Tasks |
|------|--------|-------|
| `cli/paper/output.py` | Modify | A1 |
| `harness/services/orchestrator.py` | No change (verification target) | A2 |
| `cli/paper/dispatch.py` | Modify | B5a |
| `harness/domain/command_spec.py` | Create | B1 |
| `harness/services/preflight.py` | Create | B2, B3 |
| `cli/paper/commands/preflight.py` | Create | B5 |
| `cli/paper/parser.py` | Modify | B5 |
| `schemas/preflight.schema.json` | Create | B4 |
| `tests/test_cli/test_output.py` | Modify | A1 |
| `tests/harness/test_orchestrator_payload.py` | Create/Modify | A2 |
| `tests/test_cli/test_dispatch_exit_codes.py` | Create | B5a |
| `tests/harness/test_command_spec.py` | Create | B1 |
| `tests/harness/test_preflight.py` | Create | B2, B3, B4 |
| `tests/test_cli/test_preflight_cmd.py` | Create | B5 |
| `tests/harness/test_preflight_integration.py` | Create | B6 |
| `docs/architecture/PREFLIGHT.md` | Create | B7 |
