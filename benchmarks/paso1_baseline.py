"""Baseline validation for Paso 1: DI-aware static analysis.

Measures non-test orphan count and DI orphan count.
"""
import sqlite3

DB_PATH = ".trifecta/cache/graph_paper-writer_0a9954b4.db"

db = sqlite3.connect(DB_PATH)

# Total non-test orphans
total = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.id NOT IN (SELECT DISTINCT to_node_id FROM edges)
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
""").fetchone()[0]

# DI orphans (adapters/ports/integrations)
di = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('method', 'init')
    AND n.symbol_name != '__init__'
    AND n.id NOT IN (SELECT DISTINCT to_node_id FROM edges)
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND (n.file_rel LIKE '%adapters/%' OR n.file_rel LIKE '%ports/%' OR n.file_rel LIKE '%integrations/%')
""").fetchone()[0]

# Inheritance edges
inh = db.execute("SELECT COUNT(*) FROM edges WHERE edge_kind = 'inherits'").fetchone()[0]

# Override edges (should be 0 at baseline)
ovr = db.execute("SELECT COUNT(*) FROM edges WHERE edge_kind = 'overrides'").fetchone()[0]

db.close()

print(f"METRIC non_test_orphans={total}")
print(f"METRIC di_orphans={di}")
print(f"METRIC inherits_edges={inh}")
print(f"METRIC overrides_edges={ovr}")
print(f"SUMMARY {total} orphans ({di} DI), {inh} inherits, {ovr} overrides")
