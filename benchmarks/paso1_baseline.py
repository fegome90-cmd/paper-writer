"""Baseline validation for Paso 1: DI-aware static analysis.

Measures non-test orphan count with overrides reachability.
"""
import sqlite3

DB_PATH = ".trifecta/cache/graph_paper-writer_0a9954b4.db"

db = sqlite3.connect(DB_PATH)

# Collect nodes with incoming edges
incoming = db.execute("""
    SELECT DISTINCT to_node_id FROM edges
""").fetchall()
nodes_with_incoming = {row[0] for row in incoming}

# Overrides reachability: if a method overrides a reachable
# method, the overriding method is also reachable.
if nodes_with_incoming:
    ov_rows = db.execute(
        "SELECT from_node_id FROM edges "
        "WHERE edge_kind = 'overrides' "
        "AND to_node_id IN ("
        + ",".join("?" for _ in nodes_with_incoming)
        + ")",
        list(nodes_with_incoming),
    ).fetchall()
    for row in ov_rows:
        nodes_with_incoming.add(row[0])

# Total non-test orphans (excluding overrides-reachable)
total = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
""").fetchone()[0]

# Count actual orphans (no incoming edges, not overrides-reachable)
orphans = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND n.id NOT IN (
        SELECT DISTINCT to_node_id FROM edges
    )
""").fetchone()[0]

# Of those, how many are overrides-reachable?
raw_orphans = db.execute("""
    SELECT n.id FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND n.id NOT IN (
        SELECT DISTINCT to_node_id FROM edges
    )
""").fetchall()
raw_orphan_ids = {row[0] for row in raw_orphans}
resolved = raw_orphan_ids & nodes_with_incoming
actual_orphans = len(raw_orphan_ids) - len(resolved)

# DI orphans
di = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('method', 'init')
    AND n.symbol_name != '__init__'
    AND n.id NOT IN (
        SELECT DISTINCT to_node_id FROM edges
    )
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND (
        n.file_rel LIKE '%adapters/%'
        OR n.file_rel LIKE '%ports/%'
        OR n.file_rel LIKE '%integrations/%'
    )
""").fetchone()[0]

# Override edges
ovr = db.execute(
    "SELECT COUNT(*) FROM edges WHERE edge_kind = 'overrides'"
).fetchone()[0]
inh = db.execute(
    "SELECT COUNT(*) FROM edges WHERE edge_kind = 'inherits'"
).fetchone()[0]

db.close()

print(f"METRIC non_test_orphans={actual_orphans}")
print(f"METRIC raw_orphans={orphans}")
print(f"METRIC overrides_resolved={len(resolved)}")
print(f"METRIC di_orphans={di}")
print(f"METRIC inherits_edges={inh}")
print(f"METRIC overrides_edges={ovr}")
print(
    f"SUMMARY {actual_orphans} orphans "
    f"({orphans} raw - {len(resolved)} overrides-resolved), "
    f"{di} DI, {inh} inherits, {ovr} overrides"
)
