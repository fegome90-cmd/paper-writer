# TrifectaBench v0.1 — Specification

> **Status**: Exploratory research synthesis. Not yet implemented.
> **Source**: Conversation session 2026-06-02 (morning, post-compaction).
> **Replaces**: Manual A/B tests as the primary evaluation vehicle.

## Why this document exists

The current A/B tests (T1-T10, see `docs/ab-test-results.md`) serve as exploratory proof that Trifecta context injection provides value, but they are not a permanent evaluation system. They are too concentrated on answering questions about a single repository, and they still mix three different things:

1. Whether the Trifecta index is correct
2. Whether the Oracle retrieves useful context
3. Whether an agent works better when it receives that context

The existing documents already cover basic edge cases, graph robustness, impact queries, orphans, and ten A/B categories. That work detected real value in structural navigation and revealed gaps: staleness, missing `test_roots`, incomplete orphan classification, and lack of snapshot traceability.

Web research confirms the next correct step is to create an in-house benchmark: **TrifectaBench**. It is not appropriate to limit ourselves to copying SWE-bench or to keep accumulating manual questions.

---

## 1. How similar systems are tested

The literature and mature tools divide evaluation into layers.

**RepoBench** separates retrieval, completion, and full pipeline. It does not assume that retrieving the right file and producing a correct answer are the same capability. It also distinguishes situations with cross-file dependencies from cases that can be resolved within the same file.

**RepoQA** uses a simple and useful test: deliver a functional description without revealing the symbol name and require finding the correct function within a long repository. Its *Search Needle Function* task includes 500 cases in five languages and validates the result by comparing against the gold function via Tree-sitter parsing.

**CodeRAG-Bench** evaluates retrieval independently before measuring generation. Its implementation reports NDCG@k, MRR@k, Recall@k, and Precision@k, and then reuses retrieved results in subsequent RAG evaluations. It also allows comparing BM25, dense embeddings, and embedding APIs.

**SWE-QA** evaluates real repository comprehension via questions about intent, cross-file reasoning, and multi-hop dependencies. Its dataset was built from questions observed in GitHub issues, not only from artificial examples.

**SWE-QA-Pro** (published 2026) improves on that idea using long-tail repositories, executable environments, questions derived from issues, human review, and filtering out questions a model can answer without exploring the repository. Its explicit goal is to prevent the benchmark from measuring memorization or parametric knowledge disguised as comprehension.

**Code-QA-Bench** (preprint, 28 May 2026) proposes two controls especially useful for Trifecta: generate verified gold answers first and then derive questions, and evaluate each question under three conditions: without repo, with code without documentation, and with full documented repo. That allows separating structural reasoning, documentation help, and possible memorization.

**SWE-bench** takes the evaluation to actual execution: it creates reproducible Docker environments, applies the patch, runs tests, and determines whether the issue was resolved. That approach is necessary to test practical value, although the full harness is heavy: the documentation recommends at least 120 GB free, 16 GB RAM, and eight cores.

**SWE-eval and OpenHands** show that the final outcome is not enough. It is also worth inspecting trajectories: resource consumption, logical consistency, quality of tool use, loops, shallow exploration, and absence of backtracking. OpenHands even detected a defective benchmark because some agents exploited Git history to copy removed implementations; they later had to limit clones to depth one.

---

## 2. What benchmark Trifecta needs

You do not need a single number like CVR = 1.37×. You need a dashboard with separated metrics.

| Layer | Question it answers |
|-------|---------------------|
| Index accuracy | Does the graph correctly represent the repository? |
| Retrieval quality | Does Trifecta return the relevant context first? |
| Structural intelligence | Does it correctly answer relationships between symbols? |
| Agent benefit | Does the agent actually improve over the control? |
| Operational robustness | Does it remain reliable with changes, failures, and complex scopes? |
| Practical impact | Does it reduce time, cost, and errors in real tasks? |
| Discovery | What new capabilities appear when analyzing trajectories and graphs? |

The benchmark must use three types of repository:

| Corpus | Purpose |
|--------|---------|
| Synthetic micro-repositories | Deterministic gold for unit tests and edge cases |
| Frozen internal repositories | Real dogfooding: Trifecta, paper-writer, and other own projects |
| External long-tail repositories | Reduce memorization risk and test generalization |

Each snapshot must fix `repo_root`, `segment_id`, `commit_sha`, dirty state, indexing date, schema version, indexed roots, ignored paths, and parser used. Without that, there is no reproducibility.

---

## 3. Recommended test list: TrifectaBench v0.1

The first version should have approximately 60 test families. Each family may contain several cases. Not all need to be implemented at the same time.

### Suite A — Indexer Deterministic Correctness

These tests are P0. Without them, any later result can be misleading.

| ID | Test | Expected gold |
|----|------|---------------|
| IDX-01 | Simple functions, classes, and methods | Exact number and location |
| IDX-02 | Async, static, and class methods | Correct kind |
| IDX-03 | Nested functions and closures | Correct scope |
| IDX-04 | Absolute, relative imports and aliases | Correct edges |
| IDX-05 | Simple and multiple inheritance | Correct hierarchy |
| IDX-06 | Decorators | Symbol preserved |
| IDX-07 | Files with syntax error | Bounded failure, no global corruption |
| IDX-08 | Unicode and Spanish names | Stable indexing |
| IDX-09 | Ignored files | Absent from graph |
| IDX-10 | `source_roots` and `test_roots` separated | Correct provenance |
| IDX-11 | Nested repo and worktree | No cross-contamination |
| IDX-12 | Symlinks | No duplication or scope escape |
| IDX-13 | Incremental reindex after editing a file | Only the expected delta changes |
| IDX-14 | Interruption during indexing | Previous index remains usable |
| IDX-15 | Corrupted DB | Explicit detection and safe recovery |

This approach resembles the snapshot tests used by `scip-python`, where indexer fixtures are compared against expected outputs and specific subsets can be executed. CodeQL adopts a similar discipline: run queries over test files and fail if the real result differs from the expected one.

### Suite B — Precise Code Navigation

The current benchmark covers symbols, callers, paths, and some impact. Navigation needs to become a contractual surface.

| ID | Test | Metric |
|----|------|--------|
| NAV-01 | Find exact definition | Exact file and line match |
| NAV-02 | Find all references | Precision, recall |
| NAV-03 | Incoming calls | Precision, recall |
| NAV-04 | Outgoing calls | Precision, recall |
| NAV-05 | Interface implementations | Precision, recall |
| NAV-06 | Child and parent classes | Precision, recall |
| NAV-07 | Workspace symbol search | Recall@k |
| NAV-08 | Ambiguous symbols with the same name | Correct abstention |
| NAV-09 | Shortest path between symbols | Path exactness |
| NAV-10 | Cross-repo navigation | Correct scope and provenance |
| NAV-11 | Symbol rename | Potentially affected references |
| NAV-12 | Fallback with daemon off | Explicit degradation |

Sourcegraph distinguishes heuristic navigation (based on search) from precise navigation (based on language indexes). The first is fast and always available, but can produce false positives and negatives; the second seeks compiler-equivalent precision and can operate across repositories.

The LSP standard also exposes surfaces that do not yet appear clearly covered in Trifecta: references, implementations, call hierarchy, workspace symbols, hover, and type hierarchy. Version 3.17 added type hierarchies as an explicit protocol capability.

### Suite C — Context Retrieval and Ranking

Here you must not only measure whether some reasonable file appeared. You must evaluate ranking.

| ID | Test | Metric |
|----|------|--------|
| RET-01 | Find function from description without using its name | MRR, Recall@k |
| RET-02 | Query with low lexical overlap | Recall@k |
| RET-03 | Broad architecture question | NDCG@k |
| RET-04 | Question in Spanish | Delta vs English |
| RET-05 | Query with exact symbol name | MRR |
| RET-06 | Query with minor typo | Recall@k |
| RET-07 | Absurd query | Abstention |
| RET-08 | Very long query | Latency and ranking |
| RET-09 | Small, medium, large context budget | Quality per token |
| RET-10 | Stale index | Quality drop and warning |
| RET-11 | Repo without docs | Code-only delta |
| RET-12 | Documented repo | Per-documentation delta |
| RET-13 | PRIME vs plain BM25 | Retrieval delta |
| RET-14 | PRIME vs AST vs Graph fused | Ablation |

For this suite, use CodeRAG-Bench metrics: NDCG@1/3/5/10, MRR@1/3/5/10, Recall@1/3/5/10, and Precision@1/3/5/10.

Test RET-01 should copy RepoQA's logic: natural description without filtering the symbol identifier. That prevents the benchmark from being a disguised grep.

### Suite D — Graph Structural Reasoning

This is probably the area where Trifecta has the most differentiation.

| ID | Test | Expected result |
|----|------|-----------------|
| GRA-01 | Direct callers | Exact list |
| GRA-02 | Transitive callers at depth N | Exact list and levels |
| GRA-03 | Callees | Exact list |
| GRA-04 | Impact of modifying a function | Structural blast radius |
| GRA-05 | Impact of modifying a base class | Consumers and implementations |
| GRA-06 | Call cycles | Expected SCCs |
| GRA-07 | Import cycles | Expected SCCs |
| GRA-08 | Hubs | Stable ranking |
| GRA-09 | Simple orphans | Correct classification |
| GRA-10 | CLI entry points | Not classified as dead code |
| GRA-11 | Dynamic dispatch | Mark uncertainty |
| GRA-12 | Protocols and interfaces | Not suggested for deletion |
| GRA-13 | Test-to-source mapping | Potentially affected tests |
| GRA-14 | Public API | Exports and consumers |
| GRA-15 | External dependency | Explicit boundary |
| GRA-16 | Stale graph after editing code | Authority degraded |
| GRA-17 | Dirty repo graph | Snapshot and warning |
| GRA-18 | Cross-segment leakage | Zero foreign symbols |

Do not present impact analysis as proof that something will actually break. It must be declared as static structural blast radius. Neither present orphan as confirmed dead code. Trifecta must distinguish at least:

- `confirmed_dead_candidate`
- `likely_dead_candidate`
- `entry_point`
- `dispatch_target`
- `protocol_or_interface`
- `test_only`
- `external_consumer_unknown`
- `dynamic_resolution_unknown`
- `planned_scaffold`

### Suite E — Agent Benefit Ablation A/B

This suite documents the real benefit. It should replace the current binary A/B.

Evaluate each task under these conditions:

| Arm | Context delivered |
|-----|-------------------|
| A | Without Trifecta |
| B | PRIME only |
| C | AST only |
| D | Graph only |
| E | PRIME + AST + Graph |
| F | Oracle available on demand |
| G | Automatic injection + Oracle on demand |

Add these variants:

| Dimension | Minimum values |
|-----------|----------------|
| Index state | fresh, stale, dirty |
| Documentation | closed-book, code-only, documented |
| Model | one small local and one more capable |
| Repository | microfixture, medium internal, external long-tail |
| Language | English, Spanish |
| Budget | limited tokens and broad tokens |

The tasks should include:

| ID | Task |
|----|------|
| AGT-01 | Locate a function from description |
| AGT-02 | Explain a call chain |
| AGT-03 | Identify blast radius |
| AGT-04 | Map architecture of a module |
| AGT-05 | Find affected tests |
| AGT-06 | Diagnose a local bug |
| AGT-07 | Prepare a refactor plan |
| AGT-08 | Detect dead code candidates |
| AGT-09 | Answer 20 rapid questions |
| AGT-10 | Distinguish public API from internals |
| AGT-11 | Navigate nested repo without scope leak |
| AGT-12 | Resolve ambiguity and abstain |
| AGT-13 | Identify that the index is stale |
| AGT-14 | Decide when to read full files |
| AGT-15 | Detect that the graph is not enough |

Measure:

- `task_success`
- `answer_accuracy`
- `answer_completeness`
- `specificity`
- `hallucination_count`
- `abstention_quality`
- `latency`
- `tokens_in`
- `tokens_out`
- `context_tokens_injected`
- `tool_calls`
- `unique_files_read`
- `repeated_reads`
- `unnecessary_reads`
- `cost`

The closed-book, code-only, and documented comparison is directly inspired by Code-QA-Bench. The use of long-tail repositories and filtering out answerable questions without exploring the repo follow SWE-QA-Pro's logic.

### Suite F — End-to-End Executable Tasks

You do not need to mount a full SWE-bench during the first stage. You can create your own mini-harness Docker with ten internal tasks.

| ID | Task | Verification |
|----|------|--------------|
| E2E-01 | Localized fix of a function | Hidden tests |
| E2E-02 | Cross-cutting change of a shared type | Hidden tests |
| E2E-03 | Refactor with equivalent behavior | Regression suite |
| E2E-04 | Rename internal API | Tests + references |
| E2E-05 | Remove truly dead code | Tests + graph delta |
| E2E-06 | Detect that a supposed orphan was an entry point | Do not delete |
| E2E-07 | Update tests after a contract change | Tests |
| E2E-08 | Fix a bug with stale index | Reindex or degradation |
| E2E-09 | Resolve a change across multiple files | Tests |
| E2E-10 | Work in a worktree without contaminating another segment | Scope assertions |

Each task must include frozen repository, instruction, gold solution, minimum visible tests, hidden tests, and diff report. SWE-bench uses precisely a sequence of setup, patch application, test execution, grading, and reporting inside reproducible environments.

### Suite G — Operational Robustness and Security

The current document already covers SQL injection, Unicode, empty queries, ambiguous symbols, and special characters. The operational surface needs to be expanded.

| ID | Test |
|----|------|
| OPS-01 | Non-existent DB |
| OPS-02 | Corrupted DB |
| OPS-03 | Old schema |
| OPS-04 | Canceled indexing |
| OPS-05 | Two concurrent indexings |
| OPS-06 | Query during reindex |
| OPS-07 | Daemon down |
| OPS-08 | LSP unavailable |
| OPS-09 | Dirty repo |
| OPS-10 | Worktree |
| OPS-11 | Nested repo |
| OPS-12 | Symlink outside scope |
| OPS-13 | Path traversal |
| OPS-14 | SQL injection |
| OPS-15 | Unicode query |
| OPS-16 | Huge file |
| OPS-17 | Thousands of files |
| OPS-18 | Monorepo |
| OPS-19 | Editable install vs installed package |
| OPS-20 | `--json` flag parity |
| OPS-21 | Stable result ordering |
| OPS-22 | Secret redaction in outputs |
| OPS-23 | Memory limits |
| OPS-24 | Cold cache vs warm cache |

The need to measure memory and cache is not theoretical: the `scip-typescript` indexer documented OOM issues in large repositories and offers options to disable global caches at the cost of speed.

### Suite H — Agent Trajectories

This suite is the most likely to discover new capabilities.

| ID | Signal |
|----|--------|
| TRJ-01 | Loop of equivalent queries |
| TRJ-02 | Repeated reading of the same file |
| TRJ-03 | Shallow exploration |
| TRJ-04 | Not using Graph when it was sufficient |
| TRJ-05 | Using Graph when it was stale |
| TRJ-06 | Not falling back to full read |
| TRJ-07 | Tool call that adds no information |
| TRJ-08 | Injected context never used |
| TRJ-09 | Context over-injection |
| TRJ-10 | Correct backtracking after failed hypothesis |
| TRJ-11 | Shortcut or reward hacking |
| TRJ-12 | Out-of-scope modification |

SWE-eval proposes measuring efficiency, logical consistency, and Info-gain of tools. LangChain documented trajectory evaluators with strict, unordered, subset, superset comparison and qualitative evaluation via LLM judge. OpenHands records model calls, tool calls, times, and costs to inspect how the outcome was reached, not only whether it was reached.

---

## 4. Capabilities that probably had not been detected

The search does not justify implementing all of them now. It does justify converting them into experiments.

### P0 — Necessary to trust Trifecta

| Capability | Why |
|------------|-----|
| Snapshot Manifest | Avoid mixing indices, commits, and segments |
| Real staleness gate | A stale graph cannot maintain authority silently |
| `test_roots` | Blast radius without tests is incomplete |
| Anti-cross-segment leakage | Avoid contamination between worktrees or repos |
| CLI provenance | Resolve drift like the inconsistent `--json` behavior |
| Safe orphan classification | Avoid incorrect deletions |

### P1 — High operational value

| Capability | Source of the idea |
|------------|---------------------|
| Precise find references | SCIP and LSP |
| go to implementation | LSP |
| Type hierarchy | LSP 3.17 |
| Incoming and outgoing call hierarchy | LSP |
| Cross-repo navigation | SCIP |
| Context Pack diff | Necessary to explain staleness |
| Test-to-source graph | Safer refactors |
| Context budget optimizer | Reduce over-injection |
| Explicit abstention | Do not respond with false precision |

SCIP was designed to support precise navigation like go to definition and find references; Sourcegraph highlights that these indexes are a basis for broader code intelligence capabilities.

### P2 — Advanced exploration

| Capability | Potential value |
|------------|-----------------|
| Public API modeling | Separate internals from contracts |
| External dependency modeling | Understand boundaries absent from the repo |
| Data-flow paths | Follow value propagation |
| Taint analysis | Security and untrusted sources |
| Constant propagation | Improve precision |
| Dynamic dispatch models | Reduce false orphans |
| Trajectory clustering | Find unforeseen anti-patterns |
| Economic value report | Translate technical improvement into avoided cost |

CodeQL treats code as queryable data, allows modeling external and public APIs, and offers data-flow analysis via source, sink, and flow summary models.

The goal is not to turn Trifecta into a CodeQL clone. That would inflate scope. But yes, use those concepts to detect where the current graph ends and where its limits begin.

---

## 5. Metrics that must appear in the final report

Do not use a single aggregate metric as the main headline. Use five blocks.

### Engine quality

- `index_precision`
- `index_recall`
- `edge_precision`
- `edge_recall`
- `orphan_classification_precision`
- `cross_segment_leakage_count`
- `staleness_detection_rate`

### Retrieval

- NDCG@1/3/5/10
- MRR@1/3/5/10
- Recall@1/3/5/10
- Precision@1/3/5/10
- `latency_p50`
- `latency_p95`

### Agent benefit

- `task_success_delta`
- `accuracy_delta`
- `hallucination_delta`
- `abstention_delta`
- `tokens_delta`
- `tool_calls_delta`
- `unique_files_read_delta`
- `time_to_answer_delta`

### Real execution

- `patch_apply_rate`
- `hidden_test_pass_rate`
- `regression_rate`
- `scope_violation_count`
- `recovery_rate_after_stale_detection`

### Economic impact

- `indexing_cost`
- `agent_cost`
- `human_review_minutes`
- `correction_minutes`
- `estimated_minutes_saved`
- `cost_per_successful_task`

GitTaskBench proposes measuring economic value by combining success, token cost, and human labor cost. Its formula would not be copied without validation for this case, but the principle would be preserved: a technically interesting improvement may not justify its operational cost.

---

## 6. What to implement first

Do not start with all 60 families. Do it in three batches.

### Batch 1 — Reliable baseline

Implement first:

- IDX-01 to IDX-15
- NAV-01 to NAV-09
- RET-01 to RET-10
- GRA-01 to GRA-12
- OPS-01 to OPS-15

Expected result: know whether the index is reliable and whether the Oracle retrieves useful information.

### Batch 2 — Real benefit

Add:

- AGT-01 to AGT-15
- TRJ-01 to TRJ-12

Execute at least arms A, D, E, F, and G. Repeat each cell several times and preserve prompts, raw outputs, tool calls, times, and costs.

Expected result: demonstrate where Trifecta improves the agent, where it does not contribute, and when it hurts.

### Batch 3 — Practical value and new capabilities

Add:

- E2E-01 to E2E-10
- NAV-10 to NAV-12
- GRA-13 to GRA-18
- OPS-16 to OPS-24

Expected result: certify use in refactors, bug fixing, and multi-repo work; also decide with evidence which P1 features deserve implementation.

---

## 7. Concrete decision

The next artifact should not be another narrative report. It should be:

```
docs/benchmarks/TRIFECTA-BENCHMARK-SPEC-v0.1.md
benchmarks/fixtures/
benchmarks/cases/
benchmarks/gold/
benchmarks/runners/
benchmarks/reports/
benchmarks/trajectories/
```

And the first WO should have a strict scope:

### WO-TRIFECTA-BENCHMARK-FOUNDATION

**Objective**: Build a reproducible suite of indexer correctness, retrieval, and structural reasoning before expanding graph features.

The architecture rule must be written from the start:

> **Trifecta is not evaluated by how many answers it produces. It is evaluated by how much correct context it contributes, how many errors it avoids, how much useless work it reduces, and with what level of authority it can sustain each claim.**

---

## Appendix A — Already Resolved Items (carried from previous sessions)

These are already implemented and validated through the autoresearch loop. They are baseline, not future work:

| ID | Item | Status | Source |
|----|------|--------|--------|
| IDX-partial | `tests/` added to source_roots | Done | O-1 (commit `036597a`) |
| IDX-13 | Staleness detection in `graph status` | Done | O-5 (commit `333d934`) |
| OPS-15 | SQL injection, special chars, Unicode | Done | O-2 era + edge case tests |
| RET-partial | Context pack diff summary | Done | O-4 (commit `be0f0a0`) |
| GRA-partial | Architecture summary (core_spine, highest_risk) | Done | O-6 (commit `015e597`) |
| AGT-partial | 10 A/B test categories with T8 (orphan) exceptional case | Done | `docs/ab-test-results.md` |
| NAV-08 | Ambiguous symbol handling (`GRAPH_TARGET_AMBIGUOUS`) | Done | Built-in |
| NAV-12 | Daemon-down fallback (LSP) | Done | Built-in |

These items should be migrated to the TrifectaBench format (gold files, deterministic assertions) in Batch 1.

## Appendix B — Direct A/B Coverage Map

| A/B Test | Maps to TrifectaBench Suite |
|----------|------------------------------|
| T1 Precision | NAV-01, RET-05 |
| T2 Discovery | NAV-02, GRA-01 |
| T3 Architecture | AGT-04, GRA-08 |
| T4 Debugging | AGT-06, TRJ-05 |
| T5 MCP/Dispatch | GRA-11, OPS-07 |
| T6 Concise | RET-05, AGT-09 |
| T7 Impact | GRA-04, AGT-03 |
| T8 Orphans (exceptional) | GRA-09, GRA-10, AGT-08 |
| T9 Speed Run | AGT-09, TRJ-04 |
| T10 Cycles | GRA-06, GRA-07 |

The A/B tests are exploratory data; TrifectaBench is the verification system.
