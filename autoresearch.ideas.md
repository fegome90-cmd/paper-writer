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
