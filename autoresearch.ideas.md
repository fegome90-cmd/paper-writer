# Autoresearch Ideas — Session 4 (CVR 1.30 → 1.33, recall 0.91 → 0.93)

## Applied (10 experiments, 8 kept, 2 discarded)

8. **find_callers qualified_name** — return qualified_name in results. T-D2 synthetic fixed. CVR +3%.
9. ~~file_rel token matching~~ — diluted precision. CVR 1.26→1.18.
10. ~~search dedup by file~~ — hid correct results. CVR 1.30→1.22.
11. **find_callers substring matching** — also resolve symbols containing query. T-D2 paper-writer R=0.50→1.00. CVR +2%.

## Final state: CVR=1.33, recall=0.93, bias_reduction=3%

Only 2 tasks remain non-perfect for Trifecta:
- **T-O1 paper-writer R=0.00 P=0.60**: Precision-only task. 2 false alarms from
  argparse callbacks and entry point name collision. Fundamental static analysis gap.
  
- **T-A1 paper-writer R=0.60**: Architecture search. Test files dominate results.
  File_rel matching and dedup both regressed CVR. Needs directory-level search mode.

## Key insight: Bias reduction 29% → 3%

Most of Trifecta's initial "advantage" was measurement bias from dead tasks,
false gold answers, and substring matching. After honest benchmarking, 
Trifecta genuinely wins most categories. The remaining 3% bias is from
the RAG text-search advantage on argparse callback names.

---

# REFOCUS (2026-06-03): Integration, not internal improvement

**6 experiments (#189-#194) on orphan reduction are COMPLETE.**
- paper-writer 67→4 (-94%), trifecta_dope 494→236 (-52%), CVR 1.36 stable.
- See `docs/integration/TRIFECTA_NEXT_STEPS.md` for full plan.

**Next phase: paper-writer should USE Trifecta as a CLIENT.**

The 16 Trifecta MCP tools are the value — paper-writer integrating them is the goal.
Continuing to optimize Trifecta's internal metrics (more orphan reductions) is
diminishing returns vs. the integration opportunity.

## Deferred orphan reduction ideas (low priority now)

These were ideas to push orphan count further but are now DEPRIORITIZED:

- **H1: Protocol/ABC implementation matching** — If `class FooImpl(AstCache):` and
  `AstCache` is used, then `FooImpl` is reachable by implementation. Would resolve
  ~24 abstract Protocol methods in trifecta_dope.

- **H3: Exception catching edges** — `except SomeError:` references the class.
  Would resolve ~15 dead error classes in trifecta_dope.

- **H4: String-based dispatch** — `getattr(obj, method_name)()` patterns.
  Estimated <10 orphans resolved.

- **H2: Variable assignment** — `x = SomeClass()` makes x reference the class.
  Already partially handled in DI field analysis.

## Integration priorities (P0/P1)

| Priority | Target | Effort | Value |
|----------|--------|--------|-------|
| P0 | `clients/trifecta.py` subprocess wrapper + graceful degradation | 1-2 days | Blocking |
| P1 | `validators/code_health.py` using `ctx_graph (orphans)` | 1 day | Medium |
| P1 | `validators/method_gate.py` using `ctx_graph (callers/callees/path)` | 2-3 days | High |
| P0 | A/B benchmark: paper-writer with/without Trifecta | 1 day | Validates value |

**Strict TDD required for all phases. No new external dependencies (stdlib + subprocess only).**

## Integration Experiments (#249-#252)

### Baseline (#249)
- Trifecta mock mode: 50 orphan findings (1066 total → 1016 filtered → 50 actionable)
- Without Trifecta: 0 findings. Delta = 50.

### Dead Hubs (#250)
- Cross-referenced hubs (top 50) with orphans. 0 dead hubs found.
- **Insight**: Dead hubs are structurally rare — hubs are the OPPOSITE of orphans.
- Delta: 50→53 (noise from code changes)

### Coupling Hotspots (#251)
- Used find_callees() on hubs to find high fan-out (>8 source callees).
- Found: build_orchestrator_dependencies (fan_out=13). Architecturally significant.
- Delta: 53→54 (+1 genuine new finding)

### Threshold/Reachability (#252)
- Lowered coupling threshold to 6, added reachability check (0.6).
- No new findings: reachability is 80% (healthy), only 1 hotspot exists.
- Delta: 54 (stable)

### Key conclusion
Trifecta integration value is bounded by the codebase's actual issues:
- 53 genuine dead code findings + 1 coupling hotspot = 54 total
- Architecture is clean: 0 dead hubs, 80% reachability, 0 import cycles
- Further optimization requires either (a) a messier codebase or (b) different tool usage

### Deferred ideas
- **I1: Module-level coupling** — count imports per module, flag high fan-out modules
- **I2: Change impact analysis** — given a file, show all affected symbols via path
- **I3: Cycle detection alert** — flag when cycles appear (currently 0)
- **I4: API boundary analysis** — find symbols used across package boundaries
- **I5: Test coverage gap** — find source orphans that have no test caller

---

# GAP-007: Literature chaining quality (Session 5, 2026-06-03)

## Applied (6 experiments, 4 kept, 2 discarded)

### Baseline (#258)
- 80 total papers, 75 Tier 3+ (93.8%). Uniform mock data, high quality.

### Realistic diverse mock (#259)
- 34 total papers, 28 Tier 3+ (82.4%). More realistic mix of high/medium/noise/edge.
- 6 discards: 5 noise + 1 edge. 88% precision for chaining-discovered papers.
- Round 2 saturated at 0 new papers with threshold=0.25.

### Threshold 0.25→0.15 (#260) — KEEP
- Unlocks round 2: 0→66 papers. Total: 100, 86 T3+ (86%).
- Deeper chaining works when threshold allows marginal-relevance papers through.
- API calls: 14 (2 rounds).

### Hybrid keyword+chaining (#261) — KEEP (best: 101 T3+)
- Single keyword search + chaining from enriched seeds.
- 120 total, 101 T3+ (84.2%). Keyword adds 5 extra seeds.
- Best approach: keyword search finds papers outside citation graph, chaining expands.

### Multi-query enrichment (#262) — DISCARD
- 5 sub-queries, 8 kw papers. 150 total, 74 T3+ (49.3%).
- Over-expansion: bigger frontier → more noise. Precision loss > recall gain.

### Extended cross-domain mock (#263) — DISCARD
- ViT, DALL-E, Whisper papers. 87 total, 61 T3+ (70.1%).
- Cross-domain papers increase noise proportionally.

## Key insights
1. **Threshold 0.15 is sweet spot**: enables round 2 chaining without excess noise.
2. **Single-query hybrid is best**: keyword search + chaining > pure chaining.
3. **Multi-query is counterproductive**: precision loss from over-expanded frontier.
4. **Citation graph diversity helps but bounded**: cross-domain papers introduce noise.

## Remaining ideas
- **Q1: Adaptive threshold by citation count** — lower threshold for high-cited papers (likely relevant even with marginal keyword overlap).
- **Q2: Venue-aware relevance** — boost relevance score for papers from top venues (ICSE, NeurIPS, etc).
- **Q3: Dedup by DOI/title fuzzy match** — prevent papers with slight title variations from being counted twice.
- **Q4: Early stopping by saturation** — stop chaining when round N discovers <5 new papers.
- **Q5: Re-rank by combined score** — after chaining, re-score all papers with full CS weights for final ranking.
