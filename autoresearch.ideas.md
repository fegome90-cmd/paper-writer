# Autoresearch Ideas — Deferred Optimizations

## High potential (not pursued yet)

- **Hybrid text+graph search for T-W2**: Add keyword fallback for "which files modify X" when graph has no match. Would close the T-W2 gap (RAG=1.00, Trifecta=0.00). Risk: turns Trifecta into RAG-lite.

- **Fix T-S1 dead task**: All arms score R=0.00. Gold answer is likely wrong or task is unscorable. Audit the gold data for T-S1.

- **Inheritance-based method resolution**: When engine.py calls `validator.validate()`, resolve `validate` to the concrete class method, not the abstract base. This would improve T-D2 (callers) accuracy.

## Medium potential

- **AST pattern matching for callers**: T-D2 scores 0.50 across all arms. The graph misses indirect callers (e.g. callbacks passed as arguments). Could add callback flow analysis.

- **File-level node weighting**: Currently all nodes have equal weight. Boost nodes that are imported by many files (high fan-in = likely important API surface).

## Low potential / fundamental

- **Dynamic import detection**: Trifecta misses `importlib.import_module()` and `__import__()`. Fundamental limitation of static analysis.

- **Cross-repo call resolution**: Trifecta indexes one segment at a time. Cross-repo calls (e.g. to `trifecta_dope` from `paper-writer`) are orphans by design.
