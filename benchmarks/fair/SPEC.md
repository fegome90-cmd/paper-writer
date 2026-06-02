# Fair Benchmark Specification — Addressing Study Biases

> **Status**: Active
> **Created**: 2026-06-02
> **Purpose**: Correct the 4 critical biases in the original Trifecta A/B study

## Biases Being Addressed

| # | Bias | Original Flaw | Correction |
|---|------|---------------|------------|
| B1 | Straw-man control | Compared Trifecta vs BLIND agent (no tools at all) | 3 arms: RAG baseline, LSP baseline, Trifecta |
| B2 | Restrictive timeout | 300s killed baselines on O(n²) tasks | Differentiated timing: index vs query measured separately |
| B3 | Single repo | Only paper-writer (77 files, 1030 nodes) | 3 repos: tiny (9 files), medium (220 files), synthetic |
| B4 | No weakness testing | Only tested strengths | Target dynamic imports, transitive inheritance, cross-file gaps |

## Arms

### Arm A: TF-IDF RAG Baseline
- Pure text retrieval using TF-IDF over file contents
- No structural knowledge, no AST, no graph
- Represents the "current industry standard" for RAG code search
- Top-k file retrieval, context from matching chunks

### Arm B: LSP Baseline
- pyright-based: definitions, references, hover, type info
- No pre-computed graph, no call hierarchy (pyright doesn't expose call hierarchy via CLI)
- Interactive — each query triggers LSP operations
- Represents what a developer gets from their IDE

### Arm C: Trifecta
- Pre-computed graph (1029 nodes, 838 edges)
- PRIME semantic search (TF-IDF based, same as Arm A)
- AST-level symbol resolution
- Call/import/inheritance edges

## Repositories

| Repo | Size | Purpose |
|------|------|---------|
| `constitucion-ai` | 9 files, ~3268 LOC | Tiny — baseline where all arms should perform similarly |
| `paper-writer` | 220 files, ~30773 LOC, 1029 nodes | Medium — primary benchmark target |
| `synthetic-fixture` | ~15 files, ~800 LOC | Controlled — known gold answers for deterministic validation |

## Task Categories

### Category 1: Precision (targets Trifecta STRENGTH)
- T-P1: Find exact definition of specific functions
- T-P2: Return exact line numbers for symbol locations

### Category 2: Discovery (targets Trifecta STRENGTH)
- T-D1: Trace call chain from entry point to leaf
- T-D2: Find all callers of a specific function

### Category 3: Orphan Detection (targets Trifecta EXCEPTIONAL case)
- T-O1: Find all functions with zero callers
- T-O2: Classify orphans (entry points vs dead code)

### Category 4: Weakness Probing (targets Trifecta WEAKNESSES)
- T-W1: Transitive inheritance (A→B→C) — Trifecta only resolves direct
- T-W2: Dynamic imports (importlib) — Trifecta is blind to these
- T-W3: Cross-file method resolution — known gap
- T-W4: Protocol/interface implementations — often missed

### Category 5: Architecture (expected TIE)
- T-A1: Map high-level architecture layers
- T-A2: Identify core abstractions

### Category 6: Semantic Search (fair fight — both use TF-IDF)
- T-S1: Find function from description (low lexical overlap)
- T-S2: Find function by synonym (e.g., "authenticate" vs "login")

## Metrics

### Per-task metrics
- `recall`: Fraction of gold items found (0.0-1.0)
- `precision`: Fraction of returned items that are correct (0.0-1.0)
- `mrr`: Reciprocal rank of first correct item (0.0-1.0)
- `latency_ms`: Wall-clock time for the query
- `completeness`: Whether the task was fully completed (boolean)

### Aggregate metrics
- `honest_cvr`: Weighted CVR across all tasks WITH proper baselines
- `bias_reduction_score`: How much the original 1.37x claim shrinks
- `weakness_exposure_rate`: % of weakness tasks where Trifecta underperforms
- `marginal_value`: Trifecta's advantage OVER the best baseline (not over blind agent)

## Evaluation Protocol

1. **Index phase**: Measure indexing time separately (Trifecta only)
2. **Query phase**: Each arm processes same tasks, same repo
3. **Scoring**: Deterministic comparison against gold answers
4. **No timeout**: All arms complete all tasks; latency measured but never used to fail

## Expected Results (Honest Hypotheses)

| Category | RAG | LSP | Trifecta | Expected Outcome |
|----------|-----|-----|----------|-----------------|
| Precision | 0.4 | 0.7 | 0.9 | Trifecta wins (exact AST locations) |
| Discovery | 0.3 | 0.5 | 0.9 | Trifecta wins (pre-computed edges) |
| Orphans | 0.0 | 0.0 | 0.8 | Trifecta wins (O(1) vs O(n²)) |
| **Weakness** | **0.3** | **0.6** | **0.2** | **LSP wins** (dynamic/transitive) |
| Architecture | 0.7 | 0.6 | 0.7 | Tie (all arms can read files) |
| Semantic | 0.5 | 0.3 | 0.5 | Tie (same TF-IDF) |

The key metric: **honest CVR should be ~1.15x, NOT 1.37x**, when measured against proper baselines.
The weakness exposure rate should reveal that Trifecta genuinely fails at transitive inheritance and dynamic imports.
