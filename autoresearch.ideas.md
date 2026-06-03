# Autoresearch Ideas — Deferred Optimizations

## Session results (CVR 0.90 → 1.26, recall 0.63 → 0.88)

5 fixes applied, all legitimate product improvements:
1. Nested call visiting in _DirectCallCollector (+57 edges)
2. Closure edge extraction (+4 edges)
3. Import-based name resolution (17→0 wrong edges)
4. Stop word removal in search (T-S1, T-S2 fixed)
5. Dynamic import detection (T-W2 fixed)

## Remaining gaps

- **Orphan precision**: Paper-writer T-O1 P=0.60 vs RAG P=1.00. Trifecta reports
  false orphans (_get_version, _cmd_audit_prose, _assert_gate_true) that ARE called
  but via argparse callbacks or same-file patterns the graph misses. Fixing this
  risks losing recall on synthetic (currently R=1.00). Precision/recall tradeoff.

- **T-D2 callers**: All arms R=0.50 on synthetic. The graph misses indirect callers
  (callbacks passed as arguments). Would need callback flow analysis.

- **T-A1 architecture**: Paper-writer Trifecta R=0.60 vs RAG R=0.80. Trifecta's
  search returns fewer relevant files for "map architecture layers" queries.
  Could boost results for directory-level matching.

## Ideas for future sessions

- **Inheritance-based method resolution**: When code calls validator.validate(),
  resolve to the concrete class method, not the abstract base.
- **Callback flow analysis**: Track functions passed as arguments to detect
  indirect call edges (e.g., set_defaults(func=_cmd_audit_prose)).
- **File-level node weighting**: Boost nodes imported by many files (high fan-in).
