# Trifecta Extension — Complete Capability Guide

> Practical documentation of the Trifecta context engine, tested against `paper-writer` (268 nodes, 230 edges).
> Every example uses real commands and real output.

---

## 1. What Trifecta Does

Trifecta is a **local code intelligence engine** that provides three layers of context to AI agents:

| Layer | Source | Speed | What it provides |
|-------|--------|-------|-----------------|
| **PRIME** | Context Pack (chunked repo) | ~50-100ms | Semantic search over code, docs, and tests |
| **AST** | Python AST parser | ~50-100ms | Symbol extraction without running code |
| **Graph** | SQLite code graph | ~5-50ms | Call/import/inheritance relationships |
| **LSP** | Language server (optional) | ~100-300ms | Type info, hover, definition jump |

The **Oracle** fuses all four layers in a single query with automatic fallback and fidelity reporting.

---

## 2. CLI Surface

```
trifecta graph <command>   # 15 graph commands
trifecta ctx <command>     # 13 context/Oracle commands
trifecta ast <command>     # 5 AST commands
trifecta status            # Repo health check
trifecta doctor            # Diagnose issues
```

---

## 3. Oracle — The Unified Query Interface

The Oracle is the primary interface for AI agents. One query triggers all four signal layers.

### 3.1 Architecture Discovery

```bash
$ trifecta ctx oracle -s . -q "What are the main stages of the manuscript pipeline?"
```

**Returns**: PRIME chunks (relevant files with scoring), AST symbols (matching functions), graph data (if applicable).

**Fidelity**: `fallback` (no graph predicate matches "what are" — natural language query).

**Use case**: An agent entering a new codebase asks broad questions and gets the most relevant files + symbols in ~166ms.

### 3.2 Symbol Location

```bash
$ trifecta ctx oracle -s . -q "where is ManuscriptState defined"
```

**Returns**:
- AST symbols: `DomainStateError`, `ManuscriptState`, `validate`, `set_gate`, `transition_to`, etc.
- PRIME chunks: `state.py` (score 0.97), `TECHNICAL_BOOTSTRAP.md` (0.96), `state_repository.py` (0.73)

**Latency**: 105ms. The agent knows exactly which file and which symbols to read.

### 3.3 Impact Analysis

```bash
$ trifecta ctx oracle -s . -q "impact of changing GateResult"
```

**Returns**: Graph data with 16 upstream dependents:
- `run_gate`, `validate_validator_gate`, 8 `validate_*` functions
- `Orchestrator._run_wrapper_gate`, `Orchestrator._run_gate_verification`
- `Orchestrator._get_next_stage`, `Orchestrator.execute`, `main`

**Fidelity**: `full` — graph signal used successfully.

**Use case**: Before refactoring `GateResult`, the agent knows the blast radius is 16 symbols across 3 files.

### 3.4 Caller Tracing

```bash
$ trifecta ctx oracle -s . -q "who calls run_gate"
```

**Returns**: 8 direct callers, all in `gates.py`:
`validate_repo_initialized`, `validate_search_completed`, `validate_screened_evidence`, `validate_outline_drafted`, `validate_sections_completed`, `validate_bib_normalized`, `validate_render_passed`, `validate_ready_for_delivery`.

**Latency**: 88ms total (graph signal only 5.6ms).

### 3.5 Path Finding

```bash
$ trifecta ctx oracle -s . -q "path from ManuscriptState to Orchestrator"
```

**Returns**: `fidelity=degraded` — graph correctly reports no direct call path between these two (ManuscriptState is a data class, Orchestrator imports it but doesn't call it).

**Fidelity levels**:
| Level | Meaning |
|-------|---------|
| `full` | Graph signal used, data returned |
| `degraded` | Graph worked but no path/result found |
| `fallback` | No graph predicate, relied on PRIME/AST only |

---

## 4. Graph Commands — Code Relationship Intelligence

### 4.1 Indexing

```bash
$ trifecta graph index -s . --json
```

**Output**: `{ "node_count": 268, "edge_count": 230 }` — indexes all Python files in configured source roots.

### 4.2 Architectural Overview

```bash
$ trifecta graph overview -s . --json
```

**Output for paper-writer**:
```json
{
  "node_count": 268,
  "edge_count": 230,
  "calls_cycles": 0,
  "imports_cycles": 0,
  "inherits_cycles": 0,
  "orphan_count": 97,
  "top_hubs": [
    {"symbol_name": "get_asset_path", "in_degree": 9},
    {"symbol_name": "ValidatorResult", "in_degree": 8},
    {"symbol_name": "run_gate", "in_degree": 8}
  ],
  "path_stats": {
    "avg_distance": 1.93,
    "max_distance": 6,
    "reachability_pct": 1.3
  }
}
```

**Use case**: 30-second codebase health check. Zero cycles = clean dependency graph. 97 orphans = dead code candidates. Top hubs = architectural keystones.

### 4.3 Callers and Callees

```bash
$ trifecta graph callers -s . --symbol "Orchestrator.execute" --json
```

**Returns**: Direct callers (depth=1) or transitive callers with `--depth 3`.

### 4.4 Orphan Detection

```bash
$ trifecta graph orphans -s . --json
```

**Output for paper-writer**: 97 orphans classified into:
| Type | Count | Meaning |
|------|-------|---------|
| `dead_code` | 82 | No callers, not an entry point |
| `dispatch_target` | 3 | Called via CLI dispatch (argparse), not statically traceable |
| `entry_point` | 12 | CLI entry functions, HTTP handlers — expected orphans |

**Use case**: See [orphan-detection-use-cases.md](./orphan-detection-use-cases.md) for 10 practical applications.

### 4.5 Hubs — Architectural Keystones

```bash
$ trifecta graph hubs -s . --json
```

**Top 5 hubs in paper-writer**:
| Symbol | Called by | Role |
|--------|-----------|------|
| `get_asset_path` | 9 | Asset resolution (used by all validators) |
| `ValidatorResult` | 8 | Return type for all tool wrappers |
| `run_gate` | 8 | Gate execution (called by all 8 validate_* functions) |
| `harness.ports.assets` (module) | 7 | Most-imported module |
| `ToolWrapper` | 7 | Base class for all integrations |

**Use case**: New developers read the top 5 hubs to understand the architecture. AI agents prioritize reading hub code to maximize coverage per file read.

### 4.6 Impact Analysis (Blast Radius)

```bash
$ trifecta graph impact -s . "ManuscriptState"
```

Returns all symbols that would be affected by changing the target — transitive callers up the graph.

### 4.7 Path Finding

```bash
$ trifecta graph path -s . -f "ManuscriptState" -t "main" --json
```

Returns shortest path between two symbols. Useful for understanding dependency chains.

### 4.8 Cycle Detection

```bash
$ trifecta graph cycles -s . --json
```

Returns all circular dependencies. Paper-writer has 0 cycles — clean graph.

### 4.9 Import Analysis

```bash
$ trifecta graph importers -s . --symbol "ManuscriptState" --json   # Who imports it
$ trifecta graph import-targets -s . --symbol "ManuscriptState" --json  # What it imports
```

### 4.10 Inheritance Analysis

```bash
$ trifecta graph subclasses -s . --symbol "ManuscriptState" --json  # Who extends it
$ trifecta graph parents -s . --symbol "Orchestrator" --json        # What it extends
```

### 4.11 Symbol Search

```bash
$ trifecta graph search -s . -q "gate" --json
```

**Returns**: 20 symbols containing "gate" — classes, methods, functions, modules. Fuzzy matching on symbol names.

---

## 5. Context Pack — Just-in-Time Code Retrieval

### 5.1 Building

```bash
$ trifecta ctx sync -s .
# Build + Validate in one command
```

### 5.2 Searching

```bash
$ trifecta ctx search -s . -q "how does the gate system work" -l 3
```

**Returns**: Ranked chunks with scoring:
```
1. GATE_SYSTEM.md        Score: 15.85  Tokens: ~785
2. test_filesystem...    Score: 9.18   Tokens: ~206
3. filesystem_action...  Score: 9.13   Tokens: ~3399
```

**Use case**: An agent needs to understand the gate system. Instead of reading 5 files, it gets the most relevant chunk in one query. The IDF-weighted scoring (`gate` has high IDF = rare term = more informative).

### 5.3 Retrieving

```bash
$ trifecta ctx get -s . --ids "repo:harness/domain/state.py:95dd8ff926"
```

**Returns**: Full chunk content — the entire `state.py` file content. Supports `mode=raw` for untruncated output.

**Use case**: An agent found a relevant chunk via search and now retrieves the full content for deeper analysis.

---

## 6. AST Commands — Deterministic Code Intelligence

### 6.1 Symbol Extraction

```bash
$ trifecta ast symbols "sym://python/mod/harness.domain.state" --segment .
```

**Returns**:
```json
{
  "symbols": [
    {"kind": "class", "name": "DomainStateError", "line": 5},
    {"kind": "class", "name": "ManuscriptState", "line": 12},
    {"kind": "method", "name": "validate", "line": 72},
    {"kind": "method", "name": "set_gate", "line": 122},
    {"kind": "method", "name": "transition_to", "line": 128}
  ]
}
```

**Use case**: Get the full API surface of a module without reading the file. 7 symbols returned in <100ms vs reading a 200-line file.

### 6.2 LSP Hover (requires daemon)

```bash
$ trifecta ast hover "harness/domain/state.py" --line 22 --char 7 --segment .
```

**Returns**: Type info, docstring, signature at cursor position. Requires the Trifecta daemon to be running. Falls back gracefully with `fallback_reason: "daemon_unavailable"`.

---

## 7. Fidelity Reporting — How to Trust the Results

Every Oracle response includes `fidelity` and `explanation`:

| Fidelity | When | Trust level |
|----------|------|-------------|
| `full` | Graph signal used, data returned | High — the graph has precise structural data |
| `degraded` | Graph used but no result (no path, target not found) | Medium — the absence IS the answer |
| `fallback` | No graph predicate matched, PRIME/AST only | Low — semantic search, may miss context |

**Example**:
```json
{
  "fidelity": "full",
  "explanation": "fidelity=full: graph signal used; AST: no symbols",
  "metadata": {
    "latency_ms": 88,
    "timings": {
      "pack_load_and_search_ms": 35,
      "ast_resolution_ms": 47,
      "graph_signal_ms": 5,
      "lsp_signal_ms": 0
    }
  }
}
```

An AI agent should:
- **Full fidelity**: Trust the graph data, use it as primary source
- **Degraded**: Use the explanation field to understand WHY (no path? target not found?)
- **Fallback**: Fall back to reading files — the search results are hints, not facts

---

## 8. Performance Profile (paper-writer, 268 nodes)

| Operation | Latency | Notes |
|-----------|---------|-------|
| Graph index | ~2s | One-time, cached in SQLite |
| Oracle (architecture query) | 166ms | PRIME + AST, no graph match |
| Oracle (impact query) | 302ms | PRIME + AST + Graph (23ms graph) |
| Oracle (caller query) | 88ms | Graph-heavy (5.6ms graph) |
| Graph search | ~10ms | Pure SQLite query |
| Graph path/impact | ~25ms | BFS on SQLite |
| Graph orphans | ~50ms | Full scan of 268 nodes |
| AST symbols | ~100ms | AST parse + cache |
| PRIME search | ~50-100ms | TF-IDF weighted chunk retrieval |

**Key insight**: Graph operations are 10-50x faster than PRIME/AST. For structural queries (callers, impact, path), the graph is the fastest path to precise answers.

---

## 9. Practical Workflows

### 9.1 Onboarding a New Agent

```
1. trifecta graph overview -s .          → 30-second health check
2. trifecta graph hubs -s .              → read the 5 most-connected files
3. trifecta graph orphans -s .           → know what to skip
4. trifecta ctx oracle -s . -q "..."     → ask domain questions
```

### 9.2 Pre-Refactor Impact Assessment

```
1. trifecta ctx oracle -s . -q "impact of changing X"
   → Get blast radius (16 dependents for GateResult)
2. trifecta graph callers -s . --symbol "X" --depth 3
   → Transitive callers, not just direct
3. trifecta graph path -s . -f "X" -t "entry_point"
   → Shortest path to the entry point
```

### 9.3 Dead Code Audit

```
1. trifecta graph orphans -s . --json    → Get orphan list
2. Filter: orphan_type == "dead_code"    → Remove dispatch targets and entry points
3. Cross-reference with test coverage    → Is it tested?
4. Group by file                         → Entire-file deletions if density > 90%
```

### 9.4 Code Review Assistance

```
1. For each changed symbol in the PR:
   trifecta graph callers -s . --symbol "X" --depth 2
   → "Changing X affects Y, Z, and W (2 hops away)"
2. trifecta ctx oracle -s . -q "what tests cover X"
   → Relevant test files for the review
```

---

## 10. MCP Integration

The Trifecta F1 MCP Server exposes all capabilities as MCP tools:

| MCP Tool | CLI Equivalent | Description |
|----------|---------------|-------------|
| `ctx_search` | `ctx search` | Semantic chunk search |
| `ctx_get` | `ctx get` | Retrieve full chunk content |
| `ctx_oracle` | `ctx oracle` | Unified query (4-signal fusion) |
| `ctx_calibrate` | `ctx calibrate` | Autonomous weight calibration |
| `ctx_init` | `create` | Bootstrap segment |
| `ast_analyze` | `ast symbols` | AST-based symbol extraction |
| `ctx_health` | `doctor` | Health check |

AI agents connect via stdio or Unix socket. The daemon handles connection pooling, caching, and graceful degradation.

---

## 11. Limitations and Edge Cases

| Limitation | Workaround |
|-----------|-----------|
| AST symbols require `sym://python/mod/` URI format | Use dotted module path, not file path |
| LSP hover requires running daemon | `trifecta daemon start` first, or accept AST fallback |
| `main` is ambiguous (multiple files) | Use qualified name: `cli.paper.main` or file path |
| Graph only indexes Python source roots | Configure `source_roots` in `trifecta_config.json` |
| PRIME search is TF-IDF, not semantic | Use specific terms; broad queries get lower scores |
| Import edges track module-level imports only | Dynamic imports (`importlib.import_module`) are invisible |
