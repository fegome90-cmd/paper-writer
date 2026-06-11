"""LiteSemanticStore — SQLite+FTS5 implementation of SemanticStore."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from thesaurus.migration import run_migration
from thesaurus.protocol import SemanticStore, StorageCapabilities

_DEFAULT_DB_DIR = Path(__file__).parent.parent.parent / "workspace"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "thesaurus.db"
_MIGRATIONS_DIR = _DEFAULT_DB_DIR / "migrations"


class LiteSemanticStore(SemanticStore):  # type: ignore[misc]
    """SQLite + FTS5 concept store."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        run_migration(self._db_path, sql_dir=_MIGRATIONS_DIR)

    def _connect(self) -> sqlite3.Connection:
        """Open a connection with WAL mode."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _upsert_fts(self, conn: sqlite3.Connection, concept: dict[str, Any]) -> None:
        """Insert or replace a concept in the FTS5 index."""
        # Delete existing FTS entry if any
        conn.execute("DELETE FROM concepts_fts WHERE id = ?", (concept["id"],))

        alt_labels = concept.get("alt_labels") or []
        if isinstance(alt_labels, str):
            try:
                alt_labels = json.loads(alt_labels)
            except (json.JSONDecodeError, TypeError):
                alt_labels = []
        alt_str = " ".join(alt_labels)

        # Insert new FTS entry
        conn.execute(
            """INSERT INTO concepts_fts
               (id, preferred_label, notation, alt_labels)
               VALUES (?, ?, ?, ?)""",
            (concept["id"], concept["preferred_label"], concept.get("notation", ""), alt_str),
        )

    @property
    def capabilities(self) -> StorageCapabilities:
        return StorageCapabilities(vector_search=False, full_text=True)

    @property
    def concept_count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()
            return int(row[0])
        finally:
            conn.close()

    def add_concept(self, concept: dict[str, Any]) -> None:
        """Add or replace a single concept against normalized schema.

        Writes to concepts table, then inserts alt_labels and
        concept_relations rows for broader/narrower/related.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._upsert_fts(conn, concept)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO concepts
                      (id, preferred_label, notation, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        concept["id"],
                        concept["preferred_label"],
                        concept.get("notation", ""),
                        concept.get("source", ""),
                    ),
                )

                # Alt labels
                conn.execute("DELETE FROM alt_labels WHERE concept_id = ?", (concept["id"],))
                alt_labels = concept.get("alt_labels") or []
                if isinstance(alt_labels, str):
                    try:
                        alt_labels = json.loads(alt_labels)
                    except (json.JSONDecodeError, TypeError):
                        alt_labels = []
                for label in alt_labels:
                    conn.execute(
                        "INSERT INTO alt_labels (concept_id, label) VALUES (?, ?)",
                        (concept["id"], label),
                    )

                # Relations
                conn.execute("DELETE FROM concept_relations WHERE concept_id = ?", (concept["id"],))
                for rel_type in ["broader", "narrower", "related"]:
                    val = concept.get(rel_type, "")
                    if not val:
                        continue
                    targets = [t.strip() for t in val.split(",") if t.strip()]
                    for target in targets:
                        conn.execute(
                            """INSERT INTO concept_relations
                               (concept_id, target_id, relation_type)
                               VALUES (?, ?, ?)""",
                            (concept["id"], target, rel_type),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        finally:
            conn.close()

    def import_concepts(self, concepts: list[dict[str, Any]]) -> int:
        """Import pre-validated concept dicts. Transactional with INSERT OR REPLACE."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for concept in concepts:
                    self._upsert_fts(conn, concept)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO concepts
                          (id, preferred_label, notation, source)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            concept["id"],
                            concept["preferred_label"],
                            concept.get("notation", ""),
                            concept.get("source", ""),
                        ),
                    )

                    conn.execute("DELETE FROM alt_labels WHERE concept_id = ?", (concept["id"],))
                    alt_labels = concept.get("alt_labels") or []
                    if isinstance(alt_labels, str):
                        try:
                            alt_labels = json.loads(alt_labels)
                        except (json.JSONDecodeError, TypeError):
                            alt_labels = []
                    for label in alt_labels:
                        conn.execute(
                            "INSERT INTO alt_labels (concept_id, label) VALUES (?, ?)",
                            (concept["id"], label),
                        )

                    conn.execute(
                        "DELETE FROM concept_relations WHERE concept_id = ?", (concept["id"],)
                    )
                    for rel_type in ["broader", "narrower", "related"]:
                        val = concept.get(rel_type, "")
                        if not val:
                            continue
                        targets = [t.strip() for t in val.split(",") if t.strip()]
                        for target in targets:
                            conn.execute(
                                """INSERT INTO concept_relations
                                   (concept_id, target_id, relation_type)
                                   VALUES (?, ?, ?)""",
                                (concept["id"], target, rel_type),
                            )
                # Update last_import timestamp
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) "
                    "VALUES ('last_import', datetime('now'))"
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return len(concepts)
        finally:
            conn.close()

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search concepts via FTS5 + LIKE fallback."""
        limit = max(0, limit)
        if not query or not query.strip():
            return []

        conn = self._connect()
        try:
            fts_query = '"' + query.replace('"', '""') + '"'
            try:
                rows = conn.execute(
                    """SELECT id, preferred_label, notation, alt_labels,
                              rank
                       FROM concepts_fts
                       WHERE concepts_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
                results = []
                for row in rows:
                    match_type = "preferred_label"
                    if (
                        query.lower() in (row["alt_labels"] or "").lower()
                        and query.lower() not in row["preferred_label"].lower()
                    ):
                        match_type = "synonym"
                    results.append(
                        {
                            "id": row["id"],
                            "preferred_label": row["preferred_label"],
                            "match_type": match_type,
                            "notation": row["notation"],
                        }
                    )
                return results
            except sqlite3.OperationalError:
                escaped_query = query.replace("%", r"\%").replace("_", r"\_")
                like_pattern = f"%{escaped_query}%"
                rows = conn.execute(
                    """SELECT c.id, c.preferred_label, c.notation,
                              COALESCE(
                                (
                                  SELECT json_group_array(label)
                                  FROM alt_labels
                                  WHERE concept_id = c.id
                                ),
                                '[]'
                              ) as alt_labels_str
                       FROM concepts c
                       WHERE c.preferred_label LIKE ? ESCAPE '\\'
                          OR c.notation LIKE ? ESCAPE '\\'
                          OR EXISTS(
                            SELECT 1
                            FROM alt_labels a
                            WHERE a.concept_id = c.id
                              AND a.label LIKE ? ESCAPE '\\'
                          )
                       LIMIT ?""",
                    (like_pattern, like_pattern, like_pattern, limit),
                ).fetchall()
                results = []
                for row in rows:
                    match_type = "preferred_label"
                    alt_list = json.loads(row["alt_labels_str"])
                    query_lower = query.lower()
                    preferred_lower = row["preferred_label"].lower()
                    if any(query_lower in alt.lower() for alt in alt_list) and (
                        query_lower not in preferred_lower
                    ):
                        match_type = "synonym"
                    results.append(
                        {
                            "id": row["id"],
                            "preferred_label": row["preferred_label"],
                            "match_type": match_type,
                            "notation": row["notation"],
                        }
                    )
                return results
        finally:
            conn.close()

    def list_concepts(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        offset = max(0, offset)
        limit = max(0, limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT c.id, c.preferred_label, c.notation, c.source,
                          COALESCE(
                            (
                              SELECT json_group_array(label)
                              FROM alt_labels
                              WHERE concept_id = c.id
                            ),
                            '[]'
                          ) as alt_labels,
                          (
                            SELECT GROUP_CONCAT(target_id, ',')
                            FROM concept_relations
                            WHERE concept_id = c.id
                              AND relation_type = 'broader'
                          ) as broader,
                          (
                            SELECT GROUP_CONCAT(target_id, ',')
                            FROM concept_relations
                            WHERE concept_id = c.id
                              AND relation_type = 'narrower'
                          ) as narrower,
                          (
                            SELECT GROUP_CONCAT(target_id, ',')
                            FROM concept_relations
                            WHERE concept_id = c.id
                              AND relation_type = 'related'
                          ) as related
                   FROM concepts c
                   ORDER BY c.preferred_label
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "preferred_label": row["preferred_label"],
                    "alt_labels": json.loads(row["alt_labels"]),
                    "broader": row["broader"] or "",
                    "narrower": row["narrower"] or "",
                    "related": row["related"] or "",
                    "notation": row["notation"],
                    "source": row["source"],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def audit(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
            row = conn.execute("SELECT value FROM meta WHERE key = 'last_import'").fetchone()
            last_import = row[0] if row else ""
            source = self._detect_source(conn)
            return {
                "concept_count": count,
                "last_import": last_import or "Never",
                "profile": "lite",
                "manifest_sha256": self._get_manifest_sha(),
                "source": source,
            }
        finally:
            conn.close()

    def _detect_source(self, conn: sqlite3.Connection) -> str:
        manifest_path = self._db_path.parent / "vocabulary" / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                source = manifest.get("source")
                if source:
                    return str(source)
            except (json.JSONDecodeError, OSError):
                pass
        row = conn.execute("SELECT source FROM concepts WHERE source != '' LIMIT 1").fetchone()
        return row["source"] if row else ""

    def stats(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
            total_alt = conn.execute("SELECT COUNT(*) FROM alt_labels").fetchone()[0]
            db_size = self._db_path.stat().st_size if self._db_path.exists() else 0
            return {
                "total_concepts": count,
                "total_alt_labels": total_alt,
                "fts5_enabled": True,
                "db_size_bytes": db_size,
            }
        finally:
            conn.close()

    def rebuild(self) -> None:
        """Rebuild DB from JSONL using atomic swap.

        Validates manifest (SHA256 + concept_count) before touching anything.
        Creates a staging DB, migrates and imports into it, then atomically
        swaps it with the live DB. If anything fails, the live DB is preserved.
        """

        workspace = self._db_path.parent
        manifest_path = workspace / "vocabulary" / "manifest.json"

        if not manifest_path.exists():
            return  # No manifest → nothing to rebuild from, preserve DB

        # Validate manifest against JSONL before touching the DB
        from thesaurus.manifest import load_manifest, validate_manifest

        manifest = load_manifest(manifest_path)
        source_file = manifest.get("source_file", "")
        if not source_file:
            return  # No source_file in manifest → nothing to import

        jsonl_path = manifest_path.parent / source_file
        if not jsonl_path.exists():
            return  # Source JSONL missing → nothing to import

        validate_manifest(manifest, jsonl_path)  # Raises ManifestError on mismatch

        # Build staging DB alongside the live one
        staging_path = self._db_path.with_suffix(".staging.db")
        staging_path.unlink(missing_ok=True)

        try:
            run_migration(staging_path, sql_dir=_MIGRATIONS_DIR)

            from thesaurus.mesh_loader import load_jsonl

            concepts = load_jsonl(jsonl_path)
            if concepts:
                # Import into staging DB
                staging_store = self.__class__(str(staging_path))
                staging_store.import_concepts(concepts)

            # Atomic swap: use SQLite Backup API (handles WAL, locks, and cross-device)
            live_conn = sqlite3.connect(str(self._db_path))
            staging_conn = sqlite3.connect(str(staging_path))
            try:
                staging_conn.backup(live_conn)
            finally:
                staging_conn.close()
                live_conn.close()

            # Cleanup staging
            for ext in ["", "-wal", "-shm"]:
                Path(str(staging_path) + ext).unlink(missing_ok=True)

        except Exception as e:
            # On any failure, clean up staging and preserve live DB
            for ext in ["", "-wal", "-shm"]:
                Path(str(staging_path) + ext).unlink(missing_ok=True)
            from thesaurus.errors import RebuildError

            raise RebuildError(f"Atomic rebuild failed: {e}") from e

    def _get_manifest_sha(self) -> str:
        """Get SHA256 of manifest file."""
        import hashlib

        manifest_path = self._db_path.parent / "vocabulary" / "manifest.json"
        if manifest_path.exists():
            content = manifest_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        return ""
