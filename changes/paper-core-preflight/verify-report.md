# Verification Report: paper-core-preflight

**Change**: paper-core-preflight
**Verification date**: 2026-06-22
**Verifier**: sdd-verify (independent contract conformity check)
**Overall verdict**: ✅ **PASS** (9/9 checks pass, 138 related tests pass)

---

## Summary Table

| # | Check | Verdict | Notes |
|---|-------|---------|-------|
| 1 | Parity parser/PIPELINE_MAP/COMMAND_REGISTRY | ✅ PASS | 16 PIPELINE_MAP = 16 dispatch_keys; 47 parser leaves = 47 registry ids |
| 2 | State semantics for 3 state_policies | ✅ PASS | All 6 scenarios match spec |
| 3 | audit:reporting is pipeline_governed | ✅ PASS | 1 pipeline_governed + 9 standalone_allowed |
| 4 | Invariants (can_proceed, next_action, precedence) | ✅ PASS | All 5 invariants + 11 precedence rules pass |
| 5 | load_review_config() == snapshot values | ✅ PASS | All 4 cases produce identical mode |
| 6 | Exit codes in both dispatch paths | ✅ PASS | type(...) is int, bool safe, SystemExit propagates |
| 7 | Dataclass ↔ JSON ↔ Schema correspondence | ✅ PASS | All 13 fields × 13 schema props, tuple→array confirmed |
| 8 | Preflight is read-only | ✅ PASS | No writes, state.yaml mtime preserved across 5 calls |
| 9 | Tasks compliance (negative cases) | ✅ PASS | All 5 negative test cases pass |

---

### Check 1: Parity parser/PIPELINE_MAP/COMMAND_REGISTRY
**Spec says**: "v1 scope: COMMAND_REGISTRY is a transitory mirror of existing metadata. Dispatch remains authoritative. Parity tests detect divergence." (spec.md:59)
**Implementation**: `harness/domain/command_spec.py` defines 47 CommandSpecs; 16 have non-None `dispatch_key` mirroring `PIPELINE_MAP`.
**Evidence**:
- PIPELINE_MAP entries: 16 ✅
- COMMAND_REGISTRY dispatch_keys (non-None): 16 ✅ — exact match
- COMMAND_REGISTRY all ids: 47
- Parser leaves: 47 — exact match with cli_path set
- PARITY 1: All 16 PIPELINE_MAP keys have matching dispatch_key ✅
- PARITY 2: All 47 parser leaves have matching cli_path ✅
**Verdict**: PASS

### Check 2: State semantics for 3 state_policies
**Spec says**: Status precedence rules 1-8 (spec.md:410-419)
**Implementation**: `harness/services/preflight.py:386-407` implements exact precedence ladder.
**Evidence** (6 scenarios, all PASS):
1. Missing state + pipeline_governed (search) → needs_input, can_proceed=False ✅
2. Missing state + standalone (audit:prose) → ready, warning emitted ✅
3. Missing state + pipeline_initializer (init) → ready, warning emitted ✅
4. Corrupt state + pipeline_governed (search) → blocked ✅
5. Corrupt state + standalone (audit:prose) → ready, warning, can_proceed=True ✅
6. Corrupt state + pipeline_initializer (init) → blocked ✅ (corrupt state blocks init)
**Verdict**: PASS

### Check 3: audit:reporting is pipeline_governed
**Spec says**: "audit:reporting is an exception — it is pipeline_governed and goes through the Orchestrator." (spec.md:445)
**Implementation**: `command_spec.py:292-309` sets `state_policy="pipeline_governed"` for `audit:reporting`; all other 9 audit commands are `standalone_allowed`.
**Evidence**:
- audit:reporting.state_policy = 'pipeline_governed' ✅
- 9 other audit commands: all 'standalone_allowed' ✅
**Verdict**: PASS

### Check 4: Invariants
**Spec says**: "can_proceed: true IMPLIES status: ready" (spec.md:306); next_action rules (spec.md:171-183)
**Implementation**: `preflight.py:280-299` computes can_proceed via `_is_policy_eligible`; next_action via 3-condition rule.
**Evidence** (all PASS):
- Invariant 1: can_proceed=True IMPLIES status='ready' — verified across 6 projects × 49 commands (294 calls) ✅
- Invariant 2: next_action=None when command is not None — verified for all 47 commands ✅
- Invariant 3: next_action=None when state_invalid — all corrupt-state calls ✅
- Invariant 4: next_action='init' when state_missing and no command ✅
- Invariant 5: All 11 status precedence rules pass ✅
**Verdict**: PASS

### Check 5: load_review_config() == snapshot values
**Spec says**: "The legacy load_review_config() MUST delegate to the snapshot to ensure both Preflight and Dispatch see identical values." (design.md:486-491)
**Implementation**: `review_config.py:91-103` — `load_review_config` delegates to `load_review_config_snapshot` and returns `dict(snapshot.values)`.
**Evidence** (4 cases, all PASS):
1. Valid YAML mode=academic → both return 'academic' ✅
2. Invalid YAML → both return 'rapid' (default_invalid) ✅
3. Unknown mode 'turbo' → both normalize to 'rapid' ✅
4. Missing file → both return 'rapid' (default_missing) ✅
**Verdict**: PASS

### Check 6: Exit codes in both dispatch paths
**Spec says**: "The `type(callback_result) is int` check (NOT `isinstance` — avoids `bool` being treated as `int`)" (design.md:30)
**Implementation**: `dispatch.py:236-250` — single shared capture block; both normal and clean_cancel paths merge into one `if type(callback_result) is int:` check.
**Evidence**:
- 6.1: Normal path uses `type(...) is int` ✅
- 6.2: clean_cancel path merges into same check (not different logic) ✅
- 6.3: Uses type() is, NOT isinstance (bool safe) ✅
- 6.4: No SystemExit/BaseException catch ✅
- Empirical: True→0, 2→2, None→0, SystemExit(1) propagates with code 1 ✅
**Verdict**: PASS

### Check 7: Dataclass ↔ JSON ↔ Schema correspondence
**Spec says**: PreflightResult fields (spec.md:348-364); JSON schema (spec.md §2.3)
**Implementation**: 13 dataclass fields; `schemas/preflight.schema.json` has 13 properties; `to_json_value()` serializes all.
**Evidence**:
- All 13 dataclass fields have schema properties ✅
- All 13 properties are in `required` ✅
- additionalProperties: false ✅
- BlockedCommand.missing_gates: tuple[str,...] in DC, array in schema ✅
- schema_version = "1.0" at runtime, type "string" in schema ✅
- JSON output includes all 13 fields ✅
- BlockedCommand (4 fields) and PreflightBlocker (4 fields) match schema ✅
**Verdict**: PASS

### Check 8: Preflight is read-only
**Spec says**: "Be read-only — MUST NOT modify state.yaml, review_config.yaml, run.yaml, or any other project file" (spec.md:478)
**Implementation**: `preflight.py` only calls `repository.exists()` and `state_manager.load_state()`.
**Evidence**:
- No open(...,'w'), .write(), .save(), .dump(), .unlink(), .mkdir(), .touch(), .rename(), .replace() in preflight.py ✅
- No save_state() or set_gate() calls ✅
- repository/state_manager method calls: only {'exists', 'load_state'} ✅
- Empirical: state.yaml mtime preserved across 5 preflight calls ✅
- No new files created in outputs/ ✅
**Verdict**: PASS

### Check 9: Tasks compliance (negative cases)
**Spec says**: Tasks B2/B3/B5a specify these negative test cases.
**Implementation**: Tests exist in `tests/harness/test_preflight.py` and `tests/test_cli/test_dispatch_exit_codes.py`.
**Evidence**:
- 9.1 init with corrupt state → blocked (test_resolve_preflight_pipeline_initializer_corrupt_state) PASS ✅
  - Note: tasks.md named this `test_can_proceed_false_when_init_with_corrupt_state`; impl uses clearer name; same behavior
- 9.2 test_callback_return_bool_not_treated_as_int PASS ✅
- 9.3 test_callback_raises_system_exit PASS ✅
- 9.4 Unknown command produces complete PreflightResult (not early return): all 13 fields populated, unknown_command blocker present, 32 available_commands, 15 blocked_commands computed ✅
- 9.5 test_resolve_preflight_standalone_corrupt_state PASS ✅ (standalone IS exempt from corrupt state)
**Verdict**: PASS

---

## Issues Found

**CRITICAL** (must fix before archive): None

**WARNING** (should fix):
- Tasks.md B2 specifies test name `test_can_proceed_false_when_init_with_corrupt_state` but the actual test is named `test_resolve_preflight_pipeline_initializer_corrupt_state`. Both verify the same behavior. Consider aligning the name or documenting the rename. This is a documentation drift, not a behavioral issue.

**SUGGESTION** (nice to have): None

---

## Verdict

**PASS** — The implementation conforms to the specification across all 9 contract checks. The preflight resolver is read-only, implements correct status precedence for all 3 state_policies, maintains all invariants, and the COMMAND_REGISTRY maintains exact parity with PIPELINE_MAP (16) and parser registrations (47). Exit code capture is correct (type-is-int, bool-safe, SystemExit propagates). The dataclass ↔ JSON ↔ schema correspondence is complete with no missing or extra fields.
