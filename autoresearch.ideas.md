# Autoresearch Ideas — Session 2 (CVR 0.90 → 1.26, recall 0.63 → 0.88)

## Applied fixes (7 experiments, 6 kept)

1. **Nested call visiting** — self.generic_visit(node) in visit_Call (+57 edges)
2. **Closure edge extraction** — nested function def→call edges (+4 edges)
3. **Import-based name resolution** — module.name→node_id map + per-file import parsing (17→0 wrong)
4. **Stop word removal** — shared _STOP_WORDS set in production + benchmark (T-S1, T-S2 fixed)
5. **Dynamic import detection** — module nodes tagged with has_dynamic_imports metadata (T-W2 fixed)
6. **Orphan detection filter** — exclude methods on reachable classes + their parent classes (77→8 orphans)

## Failed experiments

- **file_rel token matching** — CVR 1.26→1.18. Broader matching diluted precision on semantic tasks.
  Architecture queries need a DIFFERENT search mode, not broader token matching.

## Remaining gaps (fundamental or high-risk)

- **Orphan precision 0.60**: 2 false alarms remain — argparse callbacks (set_defaults pattern)
  and entry point name collision (verification/main.py matching cli/main.py::main).
  Would need callback flow analysis or scoring fix.

- **T-D2 callers R=0.50**: All arms tied. Graph misses indirect callers (callbacks, DI dispatch).
  Would need callback flow analysis or DI-aware edge extraction.

- **T-A1 architecture R=0.60**: Trifecta can't match directory names via token search.
  File_rel matching was tried but hurt precision. Needs a dedicated directory search mode.

- **T-D1 paper-writer R=1.00**: Trifecta already wins. No action needed.

## Key insight

The biggest wins came from graph ACCURACY fixes (name resolution +17% CVR) and 
search QUALITY fixes (stop words +15%, dynamic imports +14%). Graph COVERAGE fixes
(nested calls +8% edges) had smaller CVR impact but improved edge count.
The orphan filter is correct behavior but doesn't change scored metrics.
