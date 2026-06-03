"""Baseline validation for Paso 3: Decorator-call resolution.

Measures orphan count across overrides + constructor + decorator reachability.
Works on any repo with a Trifecta graph DB.
"""

import sqlite3
import sys

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else ".trifecta/cache/graph_paper-writer_0a9954b4.db"

db = sqlite3.connect(DB_PATH)

# Raw orphans (no incoming edges of any kind, non-test)
raw = db.execute("""
    SELECT COUNT(*) FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND n.id NOT IN (SELECT DISTINCT to_node_id FROM edges)
""").fetchone()[0]

# Build incoming set with overrides reachability
incoming = {r[0] for r in db.execute("SELECT DISTINCT to_node_id FROM edges").fetchall()}
if incoming:
    ph = ",".join("?" for _ in incoming)
    ov = db.execute(
        f"SELECT from_node_id FROM edges WHERE edge_kind='overrides' AND to_node_id IN ({ph})",
        list(incoming),
    ).fetchall()
    for r in ov:
        incoming.add(r[0])

# Constructor reachability: classes with incoming calls
constructed_classes = db.execute(
    "SELECT to_node_id FROM edges WHERE edge_kind='calls' "
    "AND to_node_id IN (SELECT id FROM nodes WHERE kind='class')"
).fetchall()
class_ids = {r[0] for r in constructed_classes}
constructed_keys = set()
if class_ids:
    ph2 = ",".join("?" for _ in class_ids)
    ck = db.execute(
        f"SELECT file_rel, symbol_name FROM nodes WHERE id IN ({ph2})",
        list(class_ids),
    ).fetchall()
    for r in ck:
        constructed_keys.add((r[0], r[1]))

# Count final orphans
raw_orphans = db.execute("""
    SELECT n.id, n.qualified_name, n.kind, n.file_rel FROM nodes n
    WHERE n.kind IN ('function', 'method', 'class')
    AND n.symbol_name != '__init__'
    AND n.file_rel NOT LIKE 'tests/%'
    AND n.file_rel NOT LIKE 'verification/%'
    AND n.id NOT IN (SELECT DISTINCT to_node_id FROM edges)
""").fetchall()

overrides_resolved = 0
constructor_resolved = 0
final = 0
for o in raw_orphans:
    if o[0] in incoming:
        overrides_resolved += 1
        continue
    qname, kind, file_rel = o[1], o[2], o[3]
    if kind in ("method", "init") and "." in qname:
        class_name = qname.rsplit(".", 1)[0]
        if (file_rel, class_name) in constructed_keys:
            constructor_resolved += 1
            continue
    final += 1

ovr_count = db.execute("SELECT COUNT(*) FROM edges WHERE edge_kind='overrides'").fetchone()[0]

db.close()

print(f"METRIC non_test_orphans={final}")
print(f"METRIC raw_orphans={raw}")
print(f"METRIC overrides_resolved={overrides_resolved}")
print(f"METRIC constructor_resolved={constructor_resolved}")
print(f"METRIC overrides_edges={ovr_count}")
print(
    f"SUMMARY {final} orphans ({raw} raw "
    f"- {overrides_resolved} overrides "
    f"- {constructor_resolved} constructor)"
)
