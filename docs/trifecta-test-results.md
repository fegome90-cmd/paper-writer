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

### Bug 1: Oracle misses "what breaks if" impact classification

**Severity**: Medium (functional gap)

**Symptom**: Queries like "what breaks if I change run_gate" and "consequences of removing GateResult" return `fidelity=fallback` with NO graph data, even though the graph has precise impact data for these symbols.

**Expected**: These queries should be classified as `impact` queries and return the same data as `"impact of changing GateResult"` (which correctly returns fidelity=full with 16 upstream dependents).

**Root cause**: The Oracle's query classifier only recognizes the pattern `"impact of changing X"` but not semantically equivalent phrasings like:
- "what breaks if I change X"
- "consequences of removing X"
- "who depends on X"
- "blast radius of X"
- "if I modify X"

**Reproduction**:
```bash
# Works correctly:
trifecta ctx oracle -s . -q "impact of changing GateResult"
# → fidelity=full, graph_data with 16 upstream

# Misses the graph:
trifecta ctx oracle -s . -q "what breaks if I change run_gate"
# → fidelity=fallback, NO graph data
```

**Fix**: Expand the impact query classifier to match common English phrasings. The pattern should be:
```python
IMPACT_PATTERNS = [
    r"impact of (?:changing|modifying|removing|renaming)\s+(.+)",
    r"what (?:breaks|changes|happens) if (?:I |we )?(?:change|modify|remove|rename)\s+(.+)",
    r"(?:consequences|effects|implications) of (?:changing|removing|modifying)\s+(.+)",
    r"(?:who|what) (?:depends|rely) on\s+(.+)",
    r"blast radius of\s+(.+)",
]
```

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

### O-4: Context Pack Diff Tracking

**Current**: `ctx validate` detects stale chunks but doesn't show WHAT changed.
**Proposal**: Show diff stats: "3 chunks stale, 1 new file, 2 files modified."

**Effort**: Low (2-4h).

### O-5: Graph Staleness Auto-Detection

**Current**: Users must manually run `graph index` after code changes.
**Proposal**: Track file modification times. If source files are newer than the graph DB, flag as stale in `graph status` and `graph overview`.

**Evidence**: After our edits to paper-writer, the graph showed 268 nodes but some files had been modified. No warning was emitted.

**Effort**: Low (2-4h). Compare `os.path.getmtime` of source files vs graph DB.

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

### O-7: Oracle Confidence Score

**Current**: Fidelity is categorical (full/degraded/fallback). No numeric confidence.
**Proposal**: Add a confidence score 0-1 based on:
- Number of signals that returned data (3/4 = high)
- Score of top PRIME chunk (>10 = high)
- Whether AST symbols were found
- Whether graph data was returned

**Value**: AI agents can use the score to decide whether to trust the answer or fall back to reading files.

**Effort**: Medium (4-8h). Scoring algorithm + testing.

---

## 4. Performance Summary

| Operation | Latency (paper-writer, 268 nodes) |
|-----------|----------------------------------|
| Graph index | ~2s (one-time) |
| Oracle (fallback, PRIME+AST only) | 19-25ms |
| Oracle (full, PRIME+AST+Graph) | 88-302ms |
| Graph search | ~10ms |
| Graph callers/impact | ~5-25ms |
| Graph orphans | ~50ms |
| Graph overview | ~60ms |
| AST symbols | ~100ms |
| PRIME search | ~20-100ms |
| ctx sync (build+validate) | ~3s |

---

## 5. Security Test Results

| Attack Vector | Result |
|---------------|--------|
| SQL injection in graph search | ✅ Safe (parameterized queries, 0 results returned) |
| SQL injection in oracle | ✅ Safe (no crash, treated as nonsense query) |
| Path traversal in symbol names | ✅ Safe (validated against graph DB) |
| Special characters in queries | ✅ Graceful handling |
| Ambiguous targets | ✅ Fail-closed (AMBIGUOUS error, not first-match) |
