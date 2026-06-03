# Autoresearch Next Steps — Trifecta Tools Integration (Comprehensive)

> **Created**: 2026-06-03
> **Status**: PROPOSED
> **Priority**: HIGH (user's explicit focus)

## Context

We just completed 6 autoresearch experiments (#188-#194) improving Trifecta's graph
indexer: overrides, decorates, type_ref edges, same-file duplicate resolution.
Result: paper-writer 67→4 orphans (-94%), trifecta_dope 494→236 (-52%).

**This is INTERNAL Trifecta improvement, not INTEGRATION.**
The user's request: focus on **integrating Trifecta tools into paper-writer's
pipeline**. paper-writer should USE Trifecta (as a client) to enhance its own
analysis.

---

## Part 1: Biases We Found in Trifecta Benchmarks

Source: `benchmarks/fair/AUDIT.md` — comprehensive self-audit conducted after the
initial CVR=1.37x claim was challenged.

### Critical bugs that inflated/invalidated Trifecta's apparent advantage

| ID | Bug | Impact | Status |
|----|-----|--------|--------|
| **B1** | Gold answer T-P1: `DataProcessor.process` vs actual `process` | All 3 arms got recall=0.00 on T-P1 (invalidating that task) | ✅ Fixed |
| **B2** | Runner hardcoded `BaseTransformer`/`normalize`, ignored `gold_descendants` | T-W1 paper-writer reported 0.00 for RAG and Trifecta (both would have found the right subclasses) | ✅ Fixed |
| **B3** | `fibonacci` recursive function incorrectly listed as orphan | Trifecta correctly didn't report it; scoring penalized Trifecta for being right | ✅ Fixed |
| **B4** | Orphan scoring only penalized 2/13 false positives | RAG/LSP reported 80%+ false positives with high "precision" | ✅ Fixed |

### Significant biases (some by-design, some fixed)

| ID | Bias | Impact | Status |
|----|------|--------|--------|
| **S1** | "LSP" baseline was really `grep + pyright confirm` | Inflated Trifecta's latency advantage (grep is slower than a real LSP) | ✅ Renamed to `grep_pyright` |
| **S2** | RAG baseline used TF-IDF, not dense embeddings | Trifecta looked better on semantic tasks (e.g. T-S1 "deduplicate" vs "deduplicate") | ⚠️ By design (no LLM) |
| **S3** | Trifecta search threshold 0.3 too high for verbose queries | Trifecta missed T-D1/T-A1 synthetic due to threshold, not inability | ✅ Fixed (lower to 0.15) |
| **S4** | Sample size still small (16 tasks) | Single bug disproportionately moves aggregate | ⚠️ Needs 3rd repo |

### Minor issues

| ID | Issue | Status |
|----|-------|--------|
| **M1** | RAG `find_orphans` did substring matching (`validate` ⊂ `invalidate`) | ✅ Fixed (word boundary regex) |
| **M2** | LSP `find_callers` didn't handle `async def` or decorators | ⚠️ Non-material (no async defs in test repos) |
| **M3** | Index time not included in Trifecta cost | ⚠️ Cosmetic (precomputed graph) |
| **M4** | Paper-writer had only 5/11 task categories | ✅ Fixed (expanded to 11, 60 total tasks) |

### Honest bias reduction trajectory

| Iteration | Bias reduction | CVR | What happened |
|-----------|----------------|-----|---------------|
| Pre-audit | 29% "advantage" was bias | 1.37x (unreliable) | Straw-man benchmark, no real LSP |
| After B1-B4, M1, M4, S1, S3 | 8% bias | 0.97 | Bugs revealed Trifecta was barely better |
| After additional fixes (#176-#187) | 1% bias | 1.36 | Trifecta genuinely wins 5/6 categories |

**Key insight**: Most of Trifecta's initial "advantage" was measurement bias.
After honest benchmarking, Trifecta genuinely wins most categories — but
**only by 8% to 1%** depending on how strict the bias correction.

---

## Part 2: Tools Already Wired in Trifecta (16 MCP tools)

Source: `trifecta_dope/src/interfaces/mcp/server.py` + `autoresearch.jsonl`
run #47 (8 opportunities resolved, 6→11 tools wired).

### 16 MCP tools (current state)

| # | Tool | What it does | When wired | Status |
|---|------|--------------|------------|--------|
| 1 | `ctx_search` | F1 full-text + graph search | Original | ✅ |
| 2 | `ctx_get` | F1 chunk retrieval | Original | ✅ |
| 3 | `ctx_oracle` | F1 unified semantic oracle (LSP+AST+PRIME) | Original | ✅ |
| 4 | `ctx_calibrate` | F1 autonomous calibration | Original | ✅ |
| 5 | `ctx_init` | F1 bootstrap segment | Original | ✅ |
| 6 | `ast_analyze` | F1 AST structural analysis | Original | ✅ |
| 7 | `ctx_health` | F1 health check | Original | ✅ |
| 8 | `ctx_graph` | 14 actions: callers, callees, importers, import_targets, subclasses, parents, path, cycles, orphans, hubs, overview, impact, search, status | Run #36 | ✅ Wired |
| 9 | `ctx_graph_metrics` | Aggregate oracle query latency/fidelity | Run #36 | ✅ Wired |
| 10 | `ctx_reindex_graph` | Force re-index of code graph | Run #41 (O-8 partial) | ✅ Wired |
| 11 | `ctx_oracle_health` | Oracle diagnostic: freshness, LSP, pack status, issues + auto-fix hints | Run #42 (O-Diagnose) | ✅ Wired |
| 12 | `ctx_validate` | F1 context pack validation | Original | ✅ |
| 13 | `ctx_reset` | F1 context reset (destructive) | Original | ✅ |
| 14 | `ctx_plan` | F1 task planning | Original | ✅ |
| 15 | `ast_hover` | F1 LSP hover | Original | ✅ |
| 16 | (implicit) graph search via `ctx_graph (action: search)` | Within ctx_graph | Run #36 | ✅ |

**The "11 tools" count from run #47 was before the runs that added the diagnostics
ones. After the current state we have 15 explicit tools + ctx_graph's 14 actions.**

### Tool validation: 100-call stress test (run #39)

- 9 tools, 0.8s total
- `ctx_oracle`: 100% full (33 calls, 11.1ms avg)
- `ctx_graph`: 88.4% full (43 calls, 1.3ms avg — 5 failures were empty symbol params in test)
- `ctx_graph_metrics`: 100% (5 calls, instant)
- `ctx_search`: 100% (10 calls, 15.4ms)

---

## Part 3: O-* Opportunities Resolved (8 of 11)

| O | What | Resolved by | Status |
|---|------|-------------|--------|
| **O-1** | Class→method granularity in path finding | `ctx_graph (action: path)` | ✅ Run #21 |
| **O-2** | Multiple symbol candidates (callers/callees) | `ctx_graph (action: callers)` returns all candidates | ✅ |
| **O-3** | Context pack diff tracking (8h, P1) | **NOT RESOLVED** | ⛔ Remaining |
| **O-4** | Multi-project mode (cwd hardcodes) | `multi-project-mode` SDD change (commit `204c2c0`) | ✅ Run #35-#41 |
| **O-5** | Impact queries | `ctx_graph (action: impact)` | ✅ |
| **O-6** | Calibrate signal-level metrics | `ctx_graph_metrics` | ✅ |
| **O-7** | Path stats | `ctx_graph (action: path)` with metadata | ✅ |
| **O-8** | Auto-reindex on stale graph | `ctx_reindex_graph` (manual, NOT auto) | ⚠️ Partial |
| **O-9** | Validation gap classification (orphan types) | Added `validation_gap` orphan type | ✅ |
| **O-10** | Multi-project repo resolution | `resolve_project_root()` | ✅ Run #35-#41 |
| **O-11** | MetricsRecorder JSONL | Implemented | ✅ |

### Remaining un-resolved opportunities

| O | What | Why remaining |
|---|------|--------------|
| **O-3** | Context pack diff tracking (8h) | Effort — explicit decision to defer |
| **O-8** | Auto-reindex on stale (full version) | Risk — requires integrating GraphIndexer into Oracle query path. Current: explicit `ctx_reindex_graph` tool (manual). |
| 2 hidden failure modes | Symbol-not-in-graph, query-class misclassification | Medium effort |

---

## Part 4: Critical Bug Discoveries from the Audit

From `docs/graph-audit-findings.md` (T8 A/B test, 758 orphans analyzed):

### Phantom Validation (CRITICAL)
- `ManuscriptState.validate()` — appeared orphan
- `StateManager.validate_state()` — appeared orphan
- **REAL BUG**: Service-layer `validate_state` was never called in production
- **Fix applied** (commit `fb9b143`): added `self.state_manager.validate_state(state_dict)` after `load_state()`
- Also fixed test fixture bugs that were silently passing broken state

### Persistence Methods (MEDIUM — graph quality issue, not code bug)
- `StateManager.set_stage/set_gate/reset_downstream_gates` — appeared orphan
- **REAL**: Called from `Orchestrator.execute()` via `self.state_manager.X()`
- **Graph limitation**: Indexer captures only `self.X()` and `X()` — misses `self.attr.X()`
- **Improvement candidate** (O-8): Track `self.attr.X()` via type annotations on `__init__`

### Vale Integration Code Smell (LOW)
- `StyleLinter._run_vale` and `_run_vale_builtin_lint` — both private, conditional
- **Pattern**: `if condition: call_X else: call_Y` makes dispatch hard to follow
- **Recommendation**: Strategy table or refactor for testability

### The 705 false positives (95% of "orphans")
| Source | Count | Why false |
|--------|-------|-----------|
| pytest calls by name | 676 (91%) | Pytest discovers via `inspect.signature()`, graph can't see |
| Mixin inheritance | 28 (4%) | 8 tool classes inherit 4 methods from `ToolWrapper` |
| argparse dispatch | 1 | `_get_version` called via `__init__` |
| Genuine source orphans | 38 (5%) | Real candidates |

**Lesson**: orphan status is **necessary but not sufficient** evidence of a bug.
A function being orphan could be: (1) actually unused [real bug], (2) called via a
graph-invisible path [false positive], (3) replaced by an equivalent call to a
different method [often a real issue].

---

## Part 5: Integration Targets — paper-writer using Trifecta as a client

### High-Value Tools for Integration

| Tool | Target validator in paper-writer | Effort | Value |
|------|----------------------------------|--------|-------|
| `ctx_graph (action: orphans)` | NEW: `validators/code_health.py` | 1 day | Medium (new feature) |
| `ctx_graph (action: callers)` | `validators/method_gate.py` | 2-3 days | High (cross-file traceability) |
| `ctx_graph (action: callees)` | `validators/method_gate.py` | (combined) | High |
| `ctx_graph (action: path)` | `validators/method_gate.py` | (combined) | High |
| `ctx_graph (action: overview)` | `validators/preset.py` | 1 day | Medium |
| `ctx_graph (action: hubs)` | NEW: `validators/code_health.py` | (combined) | Medium |
| `ctx_oracle_health` | `validators/reporting.py` | 1 day | Medium (always-on health) |
| `ctx_reindex_graph` | `harness/services/orchestrator.py` | 1 day | High (auto-recovery) |
| `ast_analyze` | `parsers/manuscript.py` (for cited code) | 2 days | High (new feature) |
| `ctx_search` | `engine/deduplicator.py` | 2 days | Medium (better dedup) |

### Target validators and their current state

```
paper-writer/validators/:
  bibliography.py    257 lines  — bib normalization
  citations.py        36 lines
  claims.py          263 lines  — claim detection (could use ctx_graph for cross-ref)
  method_gate.py     360 lines  — METHODOLOGY gates (could use ctx_graph callers/path)
  preset.py          107 lines
  prose.py           179 lines
  refs.py             52 lines
  reporting.py        90 lines  — REPORTING audit (could use ctx_oracle_health)
  structure.py        39 lines
  style.py           183 lines
```

---

## Part 6: Phased Plan (4 phases)

### Phase 0 (P0, BLOCKING): Subprocess Wrapper

**Goal**: Make paper-writer reliably use Trifecta as a subprocess client.

1. **`clients/trifecta.py`** — wrapper for Trifecta MCP server
   - Subprocess management (start/stop with health check)
   - Fallback to direct CLI calls if MCP unavailable
   - **Graceful degradation**: if Trifecta down, skip Trifecta features silently
   - **Strict TDD**: tests must come first

2. **Configuration**:
   - `TRIFECTA_DOPE_DIR` env var
   - `MCP_TRIFECTA_MODE=real` for production
   - `MCP_TRIFECTA_MODE=off` (default) for safety — paper-writer doesn't require Trifecta
   - `MCP_TRIFECTA_MODE=mock` for tests

3. **Error handling**:
   - Trifecta unavailable → skip Trifecta features
   - Trifecta timeout (5s default) → log + continue
   - Trifecta crash → log + continue
   - **CRITICAL**: paper-writer must NOT fail because Trifecta is down

**Deliverables**:
- `clients/trifecta.py` (~200 lines, with strict TDD)
- `tests/clients/test_trifecta.py` (unit tests, mocked)
- `tests/integrations/test_trifecta_integration.py` (with real Trifecta)
- Updated `pyproject.toml` (no new dependencies)
- `docs/integration/trifecta-wrapper.md` (usage docs)

### Phase 1 (P1): First Integration — Code Health

**Goal**: Add dead code + orphan detection to paper-writer's audit output.

1. **`validators/code_health.py`** (NEW)
   - Uses `ctx_graph (action: orphans)` via `clients/trifecta.py`
   - Returns dead code warnings (filtered: skip tests, skip mixin, skip CLI dispatch)
   - **Strict TDD**
   - **Fallback**: skip if Trifecta unavailable

2. **CLI integration** — `cli/paper/main.py`
   - New subcommand: `paper audit code-health`
   - Or add to existing `paper audit` output

3. **Update reporting** — `validators/reporting.py`
   - Include code health section in audit report
   - Use `ctx_oracle_health` to surface issues

**Deliverables**:
- `validators/code_health.py` (~150 lines)
- Updated `validators/reporting.py`
- New CLI subcommand
- Tests (unit + integration)

### Phase 1 (P1, parallel): Method Gate Integration

**Goal**: Cross-file traceability in method_gate.py.

1. **Extend `validators/method_gate.py`**
   - Current: regex + local AST
   - New: Trifecta for cross-file analysis
   - Use: `ctx_graph (action: callers)`, `ctx_graph (action: callees)`, `ctx_graph (action: path)`
   - **Fallback**: regex if Trifecta unavailable

2. **Tests**: mocks for Trifecta + integration tests

**Deliverables**:
- Updated `validators/method_gate.py` (~50 lines added)
- New tests with Trifecta mocks
- Backward compat verified

### Phase 0 (parallel): Benchmark Validation

**Goal**: Prove Trifecta integration improves paper-writer.

1. **Extend `benchmarks/fair/`** — add integration tests
   - Not just Trifecta as a competitor, but Trifecta INSIDE paper-writer
   - Measure: does paper-writer find MORE issues with Trifecta enabled?

2. **A/B test**:
   - `paper audit` without Trifecta (`MCP_TRIFECTA_MODE=off`)
   - `paper audit` with Trifecta (`MCP_TRIFECTA_MODE=real`)
   - Compare: orphan count, issue detection rate, false positives

3. **Document results** — `docs/integration/trifecta-results.md`

**Deliverables**:
- Updated `benchmarks/fair/runner.py` (Trifecta-enabled mode)
- `docs/integration/trifecta-results.md` (measurable improvement proof)

---

## Part 7: Non-Goals

- **Do NOT** make paper-writer require Trifecta to run
- **Do NOT** break existing tests
- **Do NOT** add new external dependencies (use stdlib + subprocess)
- **Do NOT** port Trifecta's CLI as a library (use subprocess)
- **Do NOT** fix the 60 pre-existing test failures in trifecta_dope (out of scope)
- **Do NOT** resolve O-3 (context pack diff, 8h) or full O-8 (auto-reindex) yet

---

## Part 8: Success Criteria

1. `paper audit` runs with `MCP_TRIFECTA_MODE=off` and `=real` — both must work
2. When Trifecta is available, `paper audit` finds **MORE** issues
3. All existing tests still pass
4. New tests cover Trifecta integration (unit + integration)
5. `docs/integration/trifecta-results.md` shows measurable improvement
6. Trifecta subprocess failure does NOT crash paper-writer (graceful degradation)
7. False positive rate from orphans is documented (we know it's ~95% from audit)

---

## Part 9: Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Trifecta subprocess flakiness | Medium | Medium | Graceful degradation, retry with backoff, 5s timeout |
| Trifecta performance | Low | Low | Cache results, async where possible |
| Test instability | Medium | Medium | Mock layer, integration tests separate |
| Breaking existing behavior | Low | High | Strict TDD, fallback to current implementation |
| 95% false positive rate confuses users | High | Medium | Filter in `code_health.py` (skip tests, mixins, dispatch) |
| Trifecta subprocess spawn overhead | Low | Low | Reuse subprocess across calls |

---

## Part 10: Effort Estimate

| Phase | Effort | Value |
|-------|--------|-------|
| Phase 0: Subprocess wrapper | 2 days | Blocking (enables all integration) |
| Phase 0: Benchmark validation | 1 day | Validates value |
| Phase 1: code_health validator | 1 day | Medium value, easiest integration |
| Phase 1: method_gate integration | 2-3 days | High value, harder |
| **Total** | **6-7 days** | **First measurable integration of Trifecta in paper-writer** |

---

## Part 11: SDD Change Recommendation

**Suggested change name**: `trifecta-tools-integration` (not `ars-adoption`)

**Why not `ars-adoption`**:
- `ars-adoption` is about porting ARS framework into paper-writer
- `trifecta-tools-integration` is about paper-writer USING Trifecta
- These are **different concerns** — don't conflate them
- `ars-adoption` should remain a separate SDD cycle (its proposal already exists)

**Change dependencies**:
- None (Trifecta already exists as installed package)
- Optional: depends on `multi-project-mode` (already archived)

**Spec items needed**:
1. `clients/trifecta.py` subprocess wrapper spec
2. `validators/code_health.py` spec
3. `validators/method_gate.py` extension spec
4. `benchmarks/fair/` integration test spec
5. Configuration env vars
6. Graceful degradation behavior

---

## Part 12: Open Questions

1. **Should Trifecta integration be opt-in (env var) or opt-out (default on)?**
   - **Decision**: opt-in via `MCP_TRIFECTA_MODE=real|off` (default off for safety)
2. **How to handle Trifecta version mismatches?**
   - **Decision**: pin to specific commit in `pyproject.toml` (e.g. editable install)
3. **How to test integration without running full Trifecta?**
   - **Decision**: mock layer in `clients/trifecta.py` + `MCP_TRIFECTA_MODE=mock`
4. **What about the 95% false positive rate from orphans?**
   - **Decision**: filter at the `code_health.py` level (skip tests/, skip mixin, skip dispatch)
5. **Should we also expose paper-writer's own validators as MCP tools?**
   - **Decision**: NO (per `mcp-tools-candidates.md` — paper-writer is a CONSUMER, not a PROVIDER)

---

## Reference: Files & Documentation

- Bias audit: `benchmarks/fair/AUDIT.md` (12 findings, 8 fixed)
- Graph audit: `docs/graph-audit-findings.md` (T8 results, 3 real bugs, 705 false positives)
- Trifecta server: `trifecta_dope/src/interfaces/mcp/server.py` (15 tools + ctx_graph actions)
- Trifecta benchmark arms: `benchmarks/fair/arms/trifecta_arm.py`
- MCP candidates (paper-writer perspective): `docs/research/mcp-tools-candidates.md`
- Indexer improvement (O-8): `docs/graph-audit-findings.md` §5
- Multi-project-mode (completed): `openspec/changes/archive/2026-06-01-multi-project-mode/`
