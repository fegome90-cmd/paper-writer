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

### Baseline (#258) — KEEP
- 80 total papers, 75 Tier 3+ (93.8%). Uniform mock data.

### Realistic diverse mock (#259) — KEEP
- 34 total, 28 Tier 3+ (82.4%). Realistic mix. Round 2 saturated at 0.

### Threshold 0.25→0.15 (#260) — KEEP
- Unlocks round 2: 0→66 papers. 100 total, 86 T3+ (86%).

### Hybrid keyword+chaining (#261) — KEEP (prev best: 101 T3+)
- 120 total, 101 T3+ (84.2%). Single keyword search + chaining.

### Adaptive citation-weighted threshold (#264) — KEEP (BEST: 112 T3+)
- 150 total, 112 T3+ (74.7%). 0.5x for cites>=1000, 0.75x for cites>=100.
- Captures high-cited papers with marginal keyword overlap.

### Multi-query enrichment (#262) — DISCARD
- Over-expansion: 50.7% discard rate.

### Venue+citation adaptive (#265) — DISCARD
- Compound multipliers: NeurIPS+2000 cites → threshold=0.051 (no filter).

### Threshold 0.10 + adaptive (#266) — DISCARD
- Too aggressive: 68% discard rate.

### 3 rounds, 200 cap (#267) — DISCARD
- Over-expansion: 42% precision.

## Key insights
1. **Threshold 0.15 is sweet spot**: enables round 2 chaining without excess noise.
2. **Single-query hybrid is best**: keyword search + chaining > pure chaining.
3. **Multi-query is counterproductive**: precision loss from over-expanded frontier.
4. **Citation graph diversity helps but bounded**: cross-domain papers introduce noise.

## Remaining ideas
- **Q1: Adaptive threshold by citation count** — ✅ DONE (run #264, +49.3%). Citation-only. 0.5x for cites>=1000, 0.75x for cites>=100.
- **Q2: Venue-aware relevance** — ❌ REJECTED (run #265). Compound multiplier too aggressive for top-venue papers.
- **Q3: Dedup by DOI/title fuzzy match** — ✅ DONE (run #279). DOI exact + title normalized (lowercase, strip punctuation). Prevents cross-source duplicates.
- **Q4: Early stopping by saturation** — stop chaining when round N discovers <5 new papers.
- **Q5: Re-rank by combined score** — ✅ VALIDATED (run #277). CS scoring already ranks high-impact papers higher (top-20: 1490 cites avg vs bottom-20: 1315). No additional optimization needed.
- **Q6: Multi-query enrichment** — ❌ REJECTED (run #262). Over-expansion creates noise.
- **Q7: Round-aware threshold decay** — ❌ REJECTED (run #280). Saturation is structural (citation graph exhausted), not threshold-driven. Decay adds noise without solving the limitation.

---

# Session 6 (2026-06-05): ARS Diff Integration + Preprint Detection

## Applied (4 experiments, 4 kept)

1. **MCP Provider Wiring** — PaperSearchProvider integrated into LiteratureSearchAdapter. Fixture mode for tests, MCP mode for real. 4 smoke tests pass against real MCP server.

2. **Preprint Venue Detection** — _detect_preprint() in citation_verify uses venue+year from Crossref/S2 API results. 12 known preprint venues. P2 informational findings. missing_data_fields: 3 → 0.

3. **Uncited Assertion Detection** — 9 empirical prose rules now check citation presence (CITATION_MARKER_RE). Uncited claims get 'uncited_' prefix. Covers causal, overclaim, quantifier groups.

4. **Bibliography Preprint Check** — bibliography.py already has detect_preprint_venues() from prior session. Verified working with 69 tests.

## Key Insights

- **source_pointer was a red herring**: API results (Crossref/S2) provide venue directly. No need to parse BibTeX for preprint detection.
- **Prose rules detect WORDS but not CITED STATUS**: The critical gap was citation-presence checking, not more patterns.
- **Pre-existing test failures**: 13 E2E tests in tests/cli/ were already broken before any changes. Not related to integration work.
- **Test count**: 1189 → 1203 (+14 uncited assertion + other tests)

## Remaining ARS Diff Gaps (from runs #302-#312)

### High Priority
- **Claim audit finalizer (tiered gates)**: Our boolean gate system (pass/fail) blocks minor warnings the same as fabricated references. ARS uses 4 severity levels + annotation strings + selective gate refusal. Affects ALL validators. ~400 loc.
- **Contamination signals**: compute_preprint_signal is pure logic (zero API deps), but multi-resolver triangulation needs OpenAlex + arXiv clients. ~200 loc + client porting.
- **Uncited assertion detector (full)**: Current implementation covers citation presence but not the definitional exception (mathematical/definitional statements shouldn't require citations). ARS has 3-condition check.

### Medium Priority
- **OpenAlex client porting**: Same JSON pattern as CrossrefClient. ~120-150 loc. Enables better citation verification + contamination detection.
- **arXiv client porting**: XML parsing (ElementTree + Atom namespace). ~160-200 loc. Harder but enables preprint-specific workflows.

### Low Priority
- **Claim audit calibration**: FNR/FPR benchmarking. ~400 loc. Nice-to-have for production.
- **Module-level coupling analysis**: Count imports per module, flag high fan-out.
