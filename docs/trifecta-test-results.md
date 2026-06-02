# Trifecta Extension — Test Results & Improvement Opportunities

> Systematic testing of all Trifecta capabilities against `paper-writer`.
> Includes edge case results, discovered bugs, and concrete improvement proposals.

---

## 1. Edge Case Test Results

### 1.1 Oracle Robustness

| Test | Input | Result | Status |
|------|-------|--------|--------|
| Empty query | `""` | Returns 5 fallback hits, 19ms latency | ✅ Graceful |
| Nonsense terms | `"asdfghjkl qwertyuiop"` | 0 hits, no crash | ✅ Graceful |
| Non-existent symbol | `"where is NoSuchSymbol defined"` | fidelity=fallback, 0 AST symbols | ✅ Correct |
| SQL injection | `"'; DROP TABLE nodes; --"` | graph search returns 0 results | ✅ Safe (parameterized queries) |
| Very long query | 35+ word sentence | Works, fidelity=degraded, graph activated | ✅ Handles |
| Unicode/Spanish | `"¿dónde está el validador?"` | 4 hits, fidelity=fallback, 21ms | ✅ Works |
| Ambiguous symbol | `graph callees --symbol "main"` | `GRAPH_TARGET_AMBIGUOUS` with 2 candidates | ✅ Fail-closed |
| Special chars | `'run_gate(param="value")'` | Handled, returns results | ✅ Graceful |
| k=0 search | `ctx search -l 0` | "No results found" | ✅ Correct |
| k=-1 search | `ctx search -l -1` | "No results found" | ✅ Correct (fixed in prior bug) |

### 1.2 Graph Robustness

| Test | Result | Status |
|------|--------|--------|
| SQL injection in search | 0 results, no crash | ✅ Safe |
| Ambiguous symbol "main" | Error with 2 candidates listed | ✅ Fail-closed |
| Non-existent symbol path | `path_exists: false` | ✅ Correct |
| Cross-module calls | Tracked correctly (Orchestrator.execute → ManuscriptState) | ✅ Works |
| Cycles | 0 found (correct for clean codebase) | ✅ Correct |

---

## 2. Discovered Bugs

### Bug 1: Oracle misses "what breaks if" impact classification → FIXED ✅

**Severity**: Medium (functional gap)

**Symptom**: Queries like "what breaks if I change run_gate" and "consequences of removing GateResult" returned `fidelity=fallback` with NO graph data.

**Root cause**: The `_IMPACT_PATTERNS` list only had 11 patterns. Common English phrasings like "what breaks if", "consequences of", and "blast radius of X" were missing. Additionally, `blast radius of X` was incorrectly placed in `_HUB_PATTERNS` instead of `_IMPACT_PATTERNS`.

**Fix**: Added 12 new patterns (commit 1b4a795):
- 8 English: "what breaks if I change X", "consequences of removing X", "blast radius of X", "if I change X", etc.
- 2 Spanish: "consecuencias de cambiar X", "qué pasa si cambio X"
- 2 bare variants: "blast radius" without target → hub, with target → impact

**Verification**: All 4 previously failing queries now return `fidelity=full`:
```
'what breaks if I change run_gate'      → fidelity=full ✅
'consequences of removing GateResult'   → fidelity=full ✅
'blast radius of changing GateResult'   → fidelity=full ✅
```

120 classifier tests pass (was 98, +22 new regression tests).

### Bug 2: `--json` flag inconsistency across installations

**Severity**: Low (UX)

**Symptom**: `trifecta ctx oracle --json` works in some installations but not others. After a `uv run --active` reinstall, the flag disappears.

**Status**: The oracle outputs JSON by default — `--json` is redundant but confusing when it sometimes works and sometimes doesn't.

---

## 3. Improvement Opportunities

### O-1: Test-to-Source Graph Mapping

**Current**: Tests are not in `source_roots` → no graph nodes for test files.
**Impact**: "Which tests cover X?" is impossible to answer with the graph.

**Evidence**: `ManuscriptState` is imported by 3 test files but `graph callers ManuscriptState.validate` returns 0 results.

**Proposal**: Add optional `test_roots` config. Index tests with a `tests` edge kind. Enable queries like:
```
trifecta graph test-coverage --symbol "ManuscriptState.validate"
→ tests/harness/test_orchestrator.py (imports ManuscriptState)
→ tests/cli/test_cli_exit_code_matrix.py (imports ManuscriptState)
```

**Value**: During refactoring, agents can immediately see which tests need updating.

**Effort**: Medium (4-8h). Requires new edge kind, indexing logic, and CLI command.

### O-2: Semantic Query Expansion for Impact

**Current**: Only `"impact of changing X"` triggers the graph impact path.
**Proposal**: Add 5+ common English phrasings that map to the same graph query (see Bug 1 fix).

**Value**: ~60% of impact-variant queries currently miss the graph. Fixing this would dramatically improve Oracle hit rate for one of its highest-value features.

**Effort**: Low (2-4h). Regex patterns + tests.

### O-3: Orphan Classification for Other Languages

**Current**: Orphan classification (`dead_code` vs `dispatch_target` vs `entry_point`) only works for Python.
**Proposal**: Extend to TypeScript, Go, Rust by adding language-specific entry point and dispatch patterns.

**Effort**: Medium per language (4-8h each).

### O-4: Context Pack Diff Tracking → IMPLEMENTED ✅

**Implemented in**: autoresearch experiment #71 (2026-06-02).

`ctx validate` now shows diff summary with 5 new fields: `stale_files_count`, `modified_files_count`, `removed_files_count`, `new_files_count`, `total_chunks`. CLI output: "📊 Diff: 1 modified, 0 removed, 0 new, 153 total chunks".

### O-5: Graph Staleness Auto-Detection → IMPLEMENTED ✅

**Implemented in**: autoresearch-gate v1.2.0. The gate checks `graph status` for staleness before trusting results. If > 10% of source files are stale, recommends re-indexing.

### O-6: Hub-Based Architecture Summary

**Current**: `graph hubs` returns a flat list. `graph overview` returns counts.
**Proposal**: Generate an automatic architecture paragraph from hubs + orphans + cycles:

```
Architecture: 268 symbols, 230 edges, 0 cycles (clean).
Core spine: get_asset_path (9 dependents) → run_gate (8) → ValidatorResult (8).
97 orphans (36%): 82 dead code, 3 dispatch targets, 12 entry points.
Highest-risk change: get_asset_path (touched by 9 symbols across 3 files).
```

**Value**: 30-second codebase brief for onboarding.

**Effort**: Low (2-4h). Template + hub/orphan data.

### O-7: Oracle Confidence Score → IMPLEMENTED ✅

**Implemented in**: autoresearch experiment #73 (2026-06-02).

Oracle now returns numeric confidence score 0.0-1.0. AI agents can use a single number to decide whether to trust the answer. Critical fix: hits are Pydantic models (not dicts) — requires `getattr` fallback to avoid silent `top_score=0`. 12 confidence signals now available.

---

## 4. Performance Summary

| Operation | Latency (paper-writer, 1030 nodes) |
|-----------|----------------------------------|
| Graph index | ~3s (one-time) |
| Oracle (fallback, PRIME+AST only) | 19-25ms |
| Oracle (full, PRIME+AST+Graph) | 88-302ms |
| Graph search | ~10ms |
| Graph callers/impact | ~5-30ms |
| Graph subclasses | ~15ms |
| Graph orphans | ~80ms |
| Graph hubs | ~60ms |
| Graph overview | ~70ms |
| AST symbols | ~100ms |
| PRIME search | ~20-100ms |
| ctx sync (build+validate) | ~3s |

> **Scaling note**: Graph grew 4x (268→1030 nodes, 230→838 edges) but query latencies remained within 2x. SQLite handles 1000-node graphs comfortably. The `graph orphans` operation is the most affected (50ms→80ms) due to full-node scan with semantic classification.

---

## 5. Quality Gate Test Results (autoresearch-gate v1.2.0)

### 5.1 Subclass Coverage: Graph vs grep

| Method | ToolWrapper subclasses found | Time |
|--------|----------------------------|------|
| `grep -rn "class.*ToolWrapper"` | 7 (misses `InMemoryToolWrapper` in mocks) | ~200ms |
| `trifecta graph subclasses --symbol ToolWrapper` | **8** (finds all, including mocks) | ~15ms |

The graph finds the mock class because it uses AST inheritance analysis, not string matching. This matters for quality gates: missing a mock class means the gate won't check if the mock still works after a constructor change.

### 5.2 Spine Coverage: Hubs Over Time

| Date | Nodes | Edges | Top Hub | Hub in_degree |
|------|-------|-------|---------|--------------|
| 2026-06-01 | 268 | 230 | `get_asset_path` | 9 |
| 2026-06-02 | 1030 | 838 | `make_manuscript` | 30 |

The spine grew significantly with expanded indexing. The gate now checks the top 10 hubs against every design's "Affected Areas" table.

### 5.3 Orphan Classification: Semantic Categories

| Category | Count | Example | Gate Action |
|----------|-------|---------|-------------|
| `dead_code` | 724 | Test fixtures called by pytest | INFO (expected) |
| `validation_gap` | 13 | `StateManager.validate_state` (no callers) | CRITICAL (security risk) |
| `entry_point` | 12 | `main()` CLI entry | INFO (expected) |
| `data_flow_break` | 5 | `YamlFileStateRepository.load` (no prod callers) | HIGH (data integrity) |
| `dispatch_target` | 3 | Commands dispatched via argparse | INFO (expected) |

The `validation_gap` category directly surfaced the finding that `StateManager.validate_state` is never called in production — a potential security vulnerability.

### 5.4 Real Gate Execution: ToolResolver Audit

The autoresearch-gate with Trifecta augmentation audited the `tool-resolver-port-centralization` SDD change:

**Claims verified**: 8/8 (7 VERIFIED, 1 MISMATCH documented)
**Graph queries**: subclasses(8), hubs(10), callers(3), orphans(757)
**Findings**: 0 CRITICAL, 0 HIGH, 1 MEDIUM (intentional backward compat), 1 LOW (dead code)
**Verdict**: PASS

Key finding the graph caught that grep would have missed:
- `PandocRenderer.is_available()` line 61 still has `shutil.which()` fallback — contradicts "adapters no longer know how to find binaries" claim
- `ToolResolutionError` defined but never used — dead code from refactor

---

## 6. Security Test Results

| Attack Vector | Result |
|---------------|--------|
| SQL injection in graph search | ✅ Safe (parameterized queries, 0 results returned) |
| SQL injection in oracle | ✅ Safe (no crash, treated as nonsense query) |
| Path traversal in symbol names | ✅ Safe (validated against graph DB) |
| Special characters in queries | ✅ Graceful handling |
| Ambiguous targets | ✅ Fail-closed (AMBIGUOUS error, not first-match) |
