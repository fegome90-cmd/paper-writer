# Autoresearch Ideas — Session 3 (CVR 1.26 → 1.30, recall 0.88 → 0.91)

## Applied fixes (9 experiments, 7 kept, 2 discarded)

### Kept:
1-6. From session 2 (see compaction summary)
7. **find_callers qualified_name** — return qualified_name instead of symbol_name
   in caller results. T-D2 synthetic R=0.50→1.00. CVR +3%.

### Discarded:
8. **file_rel token matching** — diluted precision, CVR 1.26→1.18
9. **search dedup by file** — hid correct results, CVR 1.30→1.22

## Remaining gaps (fundamental or high-risk)

- **T-D2 paper-writer R=0.50**: Graph only does 1-hop callers. Gold expects 
  transitive (2+ hop) caller detection. Would need find_callers(depth=N).
  
- **T-O1 paper-writer P=0.60**: 2/5 false alarms remain — argparse callbacks
  (set_defaults pattern) and entry point name collision. Fundamental static analysis gap.

- **T-A1 paper-writer R=0.60**: Test files dominate search (score 0.40 vs 
  production 0.20). Dedup and file_rel matching both broke other tasks.
  Needs a fundamentally different approach (e.g., directory-level search mode).

## Key learnings from failed experiments

- **File path matching** hurts because tokens like "items" or "from" match 
  file paths adding noise. Precision matters more than recall in token search.
- **Dedup by file** hides correct results when multiple nodes from the same
  file match and the wrong one scores higher. Slugify lost to safe_get.
- Both attempts confirm: search quality requires carefully scoped changes,
  not broader matching strategies.
