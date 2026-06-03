"""
Arm C: Trifecta
Pre-computed graph (AST + imports + inheritance) + PRIME semantic search.
The full Trifecta pipeline as it was tested in the original study.

DB Schema:
  nodes(id, segment_id, file_rel, symbol_name, qualified_name, kind, line, metadata_json)
  edges(id, segment_id, from_node_id, to_node_id, edge_kind, source, confidence)
"""

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TrifectaResult:
    """Result from Trifecta graph query."""

    query: str
    matches: list[dict[str, Any]]
    latency_ms: int
    arm: str = "trifecta"


@dataclass
class TrifectaArm:
    """
    Trifecta graph arm — queries the pre-computed SQLite graph directly.
    No LLM involved — pure structural query quality measurement.
    """

    repo_root: Path
    graph_db_path: Path | None = None
    _conn: sqlite3.Connection | None = None
    _indexed: bool = False
    index_time_ms: int = 0

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            # Try explicit path first
            if self.graph_db_path and self.graph_db_path.exists():
                self._conn = sqlite3.connect(str(self.graph_db_path))
                self._conn.row_factory = sqlite3.Row
                self._indexed = True
                return self._conn

            # Search common locations
            cache_dir = self.repo_root / ".trifecta" / "cache"
            if cache_dir.exists():
                for f in cache_dir.glob("graph_*.db"):
                    self._conn = sqlite3.connect(str(f))
                    self._conn.row_factory = sqlite3.Row
                    self._indexed = True
                    self.graph_db_path = f
                    return self._conn

            # Old location
            old_db = self.repo_root / ".trifecta" / "graph.db"
            if old_db.exists():
                # Check if it has nodes
                conn = sqlite3.connect(str(old_db))
                cur = conn.execute("SELECT COUNT(*) FROM nodes")
                if cur.fetchone()[0] > 0:
                    self._conn = conn
                    self._conn.row_factory = sqlite3.Row
                    self._indexed = True
                    self.graph_db_path = old_db
                    return self._conn
                conn.close()

            raise FileNotFoundError(f"No Trifecta graph DB found for {self.repo_root}")
        return self._conn

    def _resolve_symbol(
        self,
        symbol_name: str,
    ) -> list[dict[str, Any]]:
        """Find nodes matching a symbol name."""
        conn = self._get_conn()
        # Try exact match first
        cur = conn.execute(
            "SELECT * FROM nodes WHERE symbol_name = ?",
            (symbol_name,),
        )
        nodes = [dict(r) for r in cur.fetchall()]
        if nodes:
            return nodes

        # Fallback to LIKE
        cur = conn.execute(
            "SELECT * FROM nodes WHERE symbol_name LIKE ?",
            (f"%{symbol_name}%",),
        )
        return [dict(r) for r in cur.fetchall()]

    def find_definition(self, symbol_name: str) -> TrifectaResult:
        """Find definition using pre-computed graph."""
        t0 = time.perf_counter()

        nodes = self._resolve_symbol(symbol_name)

        matches = []
        for node in nodes:
            matches.append(
                {
                    "file": node.get("file_rel", ""),
                    "line": node.get("line", 0),
                    "name": node.get("symbol_name", ""),
                    "text": (f"{node.get('kind', '')} {node.get('qualified_name', '')}"),
                    "score": 1.0,
                }
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query=f"definition of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_callers(self, symbol_name: str) -> TrifectaResult:
        """Find callers using graph edges."""
        t0 = time.perf_counter()

        conn = self._get_conn()

        # Find the target node(s)
        nodes = self._resolve_symbol(symbol_name)
        target_ids = [n["id"] for n in nodes]

        if not target_ids:
            return TrifectaResult(
                query=f"callers of {symbol_name}",
                matches=[],
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Find edges pointing TO the target (from_node_id calls to_node_id)
        matches = []
        seen: set[str] = set()

        for target_id in target_ids:
            cur = conn.execute(
                "SELECT e.id as edge_id, n.* FROM edges e "
                "JOIN nodes n ON e.from_node_id = n.id "
                "WHERE e.to_node_id = ? AND e.edge_kind = 'calls'",
                (target_id,),
            )
            for row in cur.fetchall():
                r = dict(row)
                key = f"{r.get('file_rel', '')}:{r.get('symbol_name', '')}"
                if key not in seen:
                    seen.add(key)
                    matches.append(
                        {
                            "file": r.get("file_rel", ""),
                            "line": r.get("line", 0),
                            "name": r.get("symbol_name", ""),
                            "text": (f"{r.get('qualified_name', '')} calls {symbol_name}"),
                            "score": 1.0,
                        }
                    )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query=f"callers of {symbol_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_orphans(self) -> TrifectaResult:
        """Find orphans using pre-computed graph.

        Excludes methods on reachable classes — if a class is
        instantiated or referenced, its methods are accessible via DI.
        """
        t0 = time.perf_counter()

        conn = self._get_conn()

        # Step 1: Find classes that ARE reachable (have incoming call/import edges)
        # Note: inheritance alone does NOT make a class reachable —
        # a subclass inheriting doesn't mean the parent's methods are called.
        # But if a class has reachable SUBCLASSES, its methods are accessible
        # via polymorphism / DI through the subclass instances.
        reachable_classes: set[str] = set()
        cur_classes = conn.execute(
            "SELECT DISTINCT n.id FROM nodes n "
            "WHERE n.kind = 'class' "
            "AND n.id IN (SELECT DISTINCT to_node_id FROM edges "
            "WHERE edge_kind IN ('calls', 'imports'))"
        )
        for row in cur_classes.fetchall():
            reachable_classes.add(row[0])

        # Also include parent classes of reachable classes
        # (their methods are accessible via subclass instances)
        for cls_id in list(reachable_classes):
            cur_parents = conn.execute(
                "SELECT DISTINCT e.to_node_id FROM edges e "
                "WHERE e.edge_kind = 'inherits' AND e.from_node_id = ?",
                (cls_id,),
            )
            for row in cur_parents.fetchall():
                reachable_classes.add(row[0])

        # Step 2: Find files containing reachable classes
        reachable_class_files: dict[str, set[str]] = {}  # file_rel -> {class_name}
        for cls_id in reachable_classes:
            cur_rc = conn.execute(
                "SELECT file_rel, symbol_name FROM nodes WHERE id = ?",
                (cls_id,),
            )
            row = cur_rc.fetchone()
            if row:
                reachable_class_files.setdefault(row[0], set()).add(row[1])

        # Step 3: Find orphans, excluding methods on reachable classes
        cur = conn.execute(
            "SELECT n.* FROM nodes n WHERE n.kind NOT IN ('module', 'class') "
            "AND n.id NOT IN "
            "(SELECT DISTINCT to_node_id FROM edges "
            "WHERE edge_kind IN ('calls', 'imports'))"
        )

        matches = []
        for row in cur.fetchall():
            r = dict(row)
            file_rel = r.get("file_rel", "")
            qual = r.get("qualified_name", "")
            kind = r.get("kind", "")

            # Skip methods/init on reachable classes
            if kind in ("method", "init") and "." in qual:
                class_name = qual.rsplit(".", 1)[0]
                reachable_in_file = reachable_class_files.get(file_rel, set())
                if class_name in reachable_in_file:
                    continue

            matches.append(
                {
                    "file": file_rel,
                    "line": r.get("line", 0),
                    "name": r.get("symbol_name", ""),
                    "text": (f"orphan {kind}: {qual}"),
                    "score": 1.0,
                }
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query="find orphan functions",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_subclasses(
        self,
        class_name: str,
        *,
        transitive: bool = False,
    ) -> TrifectaResult:
        """Find subclasses using inheritance edges."""
        t0 = time.perf_counter()

        conn = self._get_conn()

        matches = []
        seen: set[str] = set()
        queue = [class_name]
        depth = 0
        max_depth = 5 if transitive else 1

        while queue and depth < max_depth:
            next_queue: list[str] = []
            for parent_name in queue:
                # Find parent node
                parent_nodes = self._resolve_symbol(parent_name)
                for pn in parent_nodes:
                    if pn.get("kind") != "class":
                        continue
                    # Edges where parent is target (X inherits from parent)
                    cur = conn.execute(
                        "SELECT e.*, n.* FROM edges e "
                        "JOIN nodes n ON e.from_node_id = n.id "
                        "WHERE e.to_node_id = ? "
                        "AND e.edge_kind = 'inherits'",
                        (pn["id"],),
                    )
                    for row in cur.fetchall():
                        r = dict(row)
                        child_name = r.get("symbol_name", "")
                        key = f"{r.get('file_rel', '')}:{child_name}"
                        if key not in seen:
                            seen.add(key)
                            matches.append(
                                {
                                    "file": r.get("file_rel", ""),
                                    "line": r.get("line", 0),
                                    "name": child_name,
                                    "text": (f"{child_name} inherits from {parent_name}"),
                                    "score": 1.0,
                                    "depth": depth + 1,
                                }
                            )
                            if transitive:
                                next_queue.append(child_name)
            queue = next_queue
            depth += 1

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query=f"subclasses of {class_name}",
            matches=matches,
            latency_ms=latency_ms,
        )

    def find_dynamic_imports(self) -> TrifectaResult:
        """Find files that use dynamic imports (importlib, __import__)."""
        t0 = time.perf_counter()

        conn = self._get_conn()

        # Query module nodes with has_dynamic_imports metadata
        cur = conn.execute(
            "SELECT * FROM nodes WHERE kind = 'module' "
            "AND metadata_json LIKE '%has_dynamic_imports%'"
        )

        matches = []
        seen_files: set[str] = set()
        for row in cur.fetchall():
            r = dict(row)
            file_rel = r.get("file_rel", "")
            if file_rel and file_rel not in seen_files:
                seen_files.add(file_rel)
                matches.append(
                    {
                        "file": file_rel,
                        "line": r.get("line", 0),
                        "name": r.get("symbol_name", ""),
                        "text": "File uses dynamic imports (importlib/__import__)",
                        "score": 0.8,
                    }
                )

        # Fallback: if no metadata tags, search for importlib in node names
        if not matches:
            cur2 = conn.execute(
                "SELECT DISTINCT file_rel FROM nodes WHERE "
                "qualified_name LIKE '%importlib%' OR file_rel LIKE '%importlib%'"
            )
            for row in cur2.fetchall():
                file_rel = row[0]
                if file_rel and file_rel not in seen_files:
                    seen_files.add(file_rel)
                    matches.append(
                        {
                            "file": file_rel,
                            "line": 0,
                            "name": "",
                            "text": "File references importlib",
                            "score": 0.3,
                        }
                    )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query="dynamic imports",
            matches=matches,
            latency_ms=latency_ms,
        )

    # Stop words shared with production GraphStore.search_nodes
    _STOP_WORDS = frozenset(
        {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "were",
            "will",
            "with",
            "find",
            "get",
            "show",
            "all",
            "any",
            "can",
            "do",
            "does",
            "how",
            "i",
            "if",
            "me",
            "my",
            "no",
            "not",
            "or",
            "so",
            "this",
            "what",
            "when",
            "which",
            "who",
            "why",
            "function",
            "class",
            "method",
            "module",
            "file",
        }
    )

    def search(self, query: str, top_k: int = 10) -> TrifectaResult:
        """Search using graph symbol names with stop word removal."""
        t0 = time.perf_counter()

        conn = self._get_conn()
        raw_tokens = re.findall(r"[a-z0-9_]+", query.lower())
        # Remove stop words and short tokens (matches production logic)
        tokens = [t for t in raw_tokens if t not in self._STOP_WORDS and len(t) > 1]

        if not tokens:
            tokens = raw_tokens  # fallback if all were stop words

        # Score nodes by token overlap with symbol name
        scored: list[tuple[float, dict[str, Any]]] = []
        cur = conn.execute("SELECT * FROM nodes")

        for row in cur.fetchall():
            r = dict(row)
            name = r.get("symbol_name", "").lower()
            qual = r.get("qualified_name", "").lower()

            raw_score = sum(1 for t in tokens if t in name or t in qual)
            score = raw_score / max(len(tokens), 1)

            if score > 0.15:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)

        matches = []
        for score, r in scored[:top_k]:
            matches.append(
                {
                    "file": r.get("file_rel", ""),
                    "line": r.get("line", 0),
                    "name": r.get("symbol_name", ""),
                    "text": (f"{r.get('kind', '')} {r.get('qualified_name', '')}"),
                    "score": round(score, 2),
                }
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        return TrifectaResult(
            query=query,
            matches=matches,
            latency_ms=latency_ms,
        )

    def get_graph_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        conn = self._get_conn()
        cur = conn.execute("SELECT COUNT(*) as n FROM nodes")
        nodes = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) as n FROM edges")
        edges = cur.fetchone()[0]
        return {"nodes": nodes, "edges": edges}
