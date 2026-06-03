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
