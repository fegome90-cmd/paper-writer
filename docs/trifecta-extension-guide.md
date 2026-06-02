# Trifecta Extension — Complete Capability Guide

> Practical documentation of the Trifecta context engine, tested against `paper-writer` (1030 nodes, 838 edges).
> Every example uses real commands and real output.
>
> **Last updated**: 2026-06-02 — Added §12 (Quality Gate Integration), updated stats, new graph commands.

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

**Output**: `{ "node_count": 1030, "edge_count": 838 }` — indexes all Python files in configured source roots.

> **Graph growth**: The paper-writer graph grew from 268 nodes / 230 edges (initial index) to 1030 nodes / 838 edges after adding configurable `source_roots` via `trifecta_config.json` and DI edge resolution (`self.attr.method()` patterns). The 4x growth came from expanding indexing scope beyond `harness/` to include `integrations/`, `validators/`, `engine/`, `parsers/`, and test directories.

### 4.2 Architectural Overview

```bash
$ trifecta graph overview -s . --json
```

**Output for paper-writer** (current):
```json
{
  "node_count": 1030,
  "edge_count": 838,
  "calls_cycles": 0,
  "imports_cycles": 0,
  "inherits_cycles": 0,
  "orphan_count": 757,
  "top_hubs": [
    {"symbol_name": "make_manuscript", "in_degree": 30},
    {"symbol_name": "ManuscriptState", "in_degree": 26},
    {"symbol_name": "_run", "in_degree": 20},
    {"symbol_name": "get_asset_path", "in_degree": 19},
    {"symbol_name": "_load_config", "in_degree": 17}
  ],
  "path_stats": {
    "avg_distance": 2.1,
    "max_distance": 8,
    "reachability_pct": 1.5
  }
}
```

**Use case**: 30-second codebase health check. Zero cycles = clean dependency graph. 757 orphans classified by semantic category (not just "dead code"). Top hubs = architectural keystones.

### 4.3 Callers and Callees

```bash
$ trifecta graph callers -s . --symbol "Orchestrator.execute" --json
```

**Returns**: Direct callers (depth=1) or transitive callers with `--depth 3`.

### 4.4 Orphan Detection

```bash
$ trifecta graph orphans -s . --json
```

**Output for paper-writer**: 757 orphans classified into 5 semantic categories:

| Type | Count | Meaning |
|------|-------|---------|
| `dead_code` | 724 | No callers, not an entry point (91% are test fixtures called by pytest dynamically) |
| `validation_gap` | 13 | Functions with validate/check/verify/ensure names but no callers — potential security gaps |
| `entry_point` | 12 | CLI entry functions, HTTP handlers — expected orphans |
| `data_flow_break` | 5 | Repository load/save methods with no callers in production — data integrity risk |
| `dispatch_target` | 3 | Called via CLI dispatch (argparse), not statically traceable |

The semantic categories go beyond "dead code" to encode **data-flow reasoning**. A `validation_gap` orphan like `StateManager.validate_state` is flagged as CRITICAL because it's a validation function with no caller — meaning validation is never triggered in production. A `data_flow_break` like `YamlFileStateRepository.load` signals that the data pipeline may have a gap where state is written but never read (or vice versa).

**Use case**: See [orphan-detection-use-cases.md](./orphan-detection-use-cases.md) for 10 practical applications.

### 4.5 Hubs — Architectural Keystones

```bash
$ trifecta graph hubs -s . --json
```

**Top 5 hubs in paper-writer** (current):
| Symbol | Called by | Role |
|--------|-----------|------|
| `make_manuscript` | 30 | Test fixture (conftest.py centralization) |
| `ManuscriptState` | 26 | Domain model — core state machine |
| `_run` | 20 | E2E test helper |
| `get_asset_path` | 19 | Asset resolution (used by all validators) |
| `_load_config` | 17 | Packaging test helper |

**Architectural significance**: The top production hubs are `ManuscriptState` (26), `get_asset_path` (19), and `build_orchestrator_dependencies` (15). These form the **architectural spine** — changes to any of these have the highest blast radius. AI agents should read these files first to maximize context coverage per file read.

**Use cases**:
1. New developers read the top 5 hubs to understand the architecture.
2. Quality gates verify that design docs address all affected spine hubs.
3. Refactoring prioritizes spine stability — hubs with in_degree > 15 get extra review scrutiny.

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

## 8. Performance Profile (paper-writer, 1030 nodes)

| Operation | Latency | Notes |
|-----------|---------|-------|
| Graph index | ~3s | One-time, cached in SQLite |
| Oracle (architecture query) | 166ms | PRIME + AST, no graph match |
| Oracle (impact query) | 302ms | PRIME + AST + Graph (23ms graph) |
| Oracle (caller query) | 88ms | Graph-heavy (5.6ms graph) |
| Graph search | ~10ms | Pure SQLite query |
| Graph subclasses | ~15ms | AST-based, finds all including mocks |
| Graph path/impact | ~25ms | BFS on SQLite |
| Graph orphans | ~80ms | Full scan of 1030 nodes with semantic classification |
| Graph hubs | ~60ms | In-degree ranking of all nodes |
| AST symbols | ~100ms | AST parse + cache |
| PRIME search | ~50-100ms | TF-IDF weighted chunk retrieval |
| Graph callers (depth=3) | ~30ms | Transitive BFS |

**Key insight**: Graph operations remain 10-50x faster than PRIME/AST even at 1030 nodes. SQLite scales well — the bottleneck is always the embedding/search layer, never the graph. For structural queries (callers, impact, path, subclasses), the graph is the fastest path to precise answers.

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
| `graph impact` uses call edges only | Inheritance-based blast radius requires `graph subclasses` separately |
| `graph subclasses` does not resolve transitive inheritance | Chain queries manually: `graph parents` → `graph subclasses` |

---

## 12. Quality Gate Integration (autoresearch-gate)

Trifecta graph queries are integrated into the `autoresearch-gate` skill (v1.2.0) as a **second verification pass** during Phase 0.5 (Code-Anchored Verification). When the graph index is available, the gate runs structural checks that grep cannot perform.

### 12.1 Subclass Coverage Audit

**Problem**: When a design modifies a base class constructor (e.g., adding `resolver` parameter to `ToolWrapper.__init__`), the designer must enumerate ALL subclasses. Missed subclasses = hidden blast radius.

**Graph solution**:
```bash
$ trifecta graph subclasses --symbol ToolWrapper -s . --json
# Returns: 8 subclasses (BibliographyNormalizer, PandocRenderer,
#   RefsMetadataValidator, RefsValidator, ReportingAuditor,
#   StyleLinter, ZoteroImporter, InMemoryToolWrapper)
```

**grep** finds 7 (misses `InMemoryToolWrapper` in test mocks). **Graph** finds 8 via AST inheritance analysis.

**Real case**: The ToolResolver design listed 4 wrappers. Graph found 8. The gate auto-generated a HIGH finding: "Design covers 4 of 8 subclasses. Missing: RefsValidator, RefsMetadataValidator, InMemoryToolWrapper."

### 12.2 Spine Coverage Verification

**Problem**: Changes to top-hub symbols (the architectural spine) have disproportionate blast radius. Design docs must explicitly address spine impacts.

**Graph solution**:
```bash
$ trifecta graph hubs -s . --json
# Returns top-10 hubs with in-degree counts
```

The gate cross-references each hub against the design's "Affected Areas" table. If a hub is affected but not listed → HIGH finding.

**Real case**: `build_orchestrator_dependencies` (in_degree=15) was affected by the ToolResolver change. The gate confirmed it was listed in the design's scope table.

### 12.3 Layer Boundary Detection

**Problem**: Code that appears duplicated across files may be an **intentional architectural layer** — different process boundaries, different error handling, different testing scopes.

**Graph solution**:
```bash
$ trifecta graph path -f "run_real_validation" -t "Orchestrator.execute" -s .
# If no path exists → separate layers, not duplication
```

**Real case**: `verification/run_real_validation.py` (1110 lines) appeared to duplicate Orchestrator logic. Graph showed no call path between them → intentional layer boundary (subprocess runner vs in-process orchestrator). Gate marked as INFO, not a finding.

### 12.4 Orphan Delta (Pre/Post Change)

**Problem**: Refactoring can create new orphans — symbols that lost their callers.

**Graph solution**: Compare orphan counts before and after implementation. New orphans in production code → WARNING.

### 12.5 Dead Symbol Detection

**Problem**: Unused exception classes, dead imports, and unreachable code accumulate over time.

**Graph solution**:
```bash
$ trifecta graph orphans -s . --json | jq '.orphans[] | select(.orphan_type == "dead_code")'
```

**Real case**: `ToolResolutionError` was defined in `harness/ports/tool_resolver.py` but never raised or caught anywhere. The graph flagged it as `dead_code`, and the gate generated a LOW finding.

### 12.6 Integration Pattern

The gate follows this two-pass pattern:

```
Phase 0.5 (Code-Anchored Verification):
  Pass 1: grep/ls/read — string-level checks (file existence, import counts)
  Pass 2: Trifecta graph — structural checks (subclasses, hubs, paths, orphans)
  Merge:  Deduplicate findings, tag graph-confirmed findings
```

| Check Available | Confidence | Method |
|----------------|------------|--------|
| Trifecta + grep | HIGH | Graph first, grep confirms |
| Trifecta only | MEDIUM | Verify edge cases with manual read |
| grep only | STANDARD | Standard code-anchor procedure |
| Neither | LOW | Flag as risk |

### 12.7 Fidelity Gating

Graph findings inherit the Oracle's fidelity model:

| Fidelity | Gate Action |
|----------|------------|
| `full` | Use as primary evidence |
| `partial` | Confirm with grep before generating finding |
| `degraded` | Skip graph result, rely on grep |

### 12.8 Commands Used by the Gate

| Gate Check | Graph Command | What It Catches |
|------------|--------------|-----------------|
| Subclass coverage | `graph subclasses --symbol <Base>` | Missing subclasses in design scope |
| Blast radius | `graph callers --symbol <X> --depth 3` | Hidden transitive dependents |
| Spine verification | `graph hubs -s .` | Unaddressed high-impact changes |
| Orphan delta | `graph orphans -s .` | New dead code from refactoring |
| Layer boundary | `graph path -f <A> -t <B>` | Intentional vs accidental duplication |
| Dead symbols | `graph orphans -s .` (filter dead_code) | Unused exception classes, dead imports |
