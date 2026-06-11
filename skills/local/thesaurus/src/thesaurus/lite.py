"""LiteSemanticStore — SQLite+FTS5 implementation of SemanticStore."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from thesaurus.migration import run_migration
from thesaurus.protocol import SemanticStore

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
        conn.row_factory = sqlite3.Row
        return conn

    def _upsert_fts(self, conn: sqlite3.Connection, concept: dict[str, Any]) -> None:
        """Insert or replace a concept in the FTS5 index."""
        # Delete existing FTS entry if any
        conn.execute("DELETE FROM concepts_fts WHERE id = ?", (concept["id"],))
        # Insert new FTS entry
        conn.execute(
            "INSERT INTO concepts_fts (id, preferred_label, notation) VALUES (?, ?, ?)",
            (concept["id"], concept["preferred_label"], concept.get("notation", "")),
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
        """Add or replace a single concept. Transactional via context manager."""
        # Normalize alt_labels: accept list or JSON string
        alt_labels = concept.get("alt_labels", "[]")
        if isinstance(alt_labels, list):
            alt_labels = json.dumps(alt_labels)

        conn = self._connect()
        try:
            with conn:
                self._upsert_fts(conn, concept)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO concepts
                      (id, preferred_label, alt_labels,
                       broader, narrower, related, notation, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        concept["id"],
                        concept["preferred_label"],
                        alt_labels,
                        concept.get("broader", ""),
                        concept.get("narrower", ""),
                        concept.get("related", ""),
                        concept.get("notation", ""),
                        concept.get("source", ""),
                    ),
                )
        finally:
            conn.close()

    def import_concepts(self, concepts: list[dict[str, Any]]) -> int:
        """Import pre-validated concept dicts. Transactional with INSERT OR REPLACE."""
        conn = self._connect()
        try:
            with conn:
                for concept in concepts:
                    # Normalize alt_labels: accept list or JSON string
                    alt_labels = concept.get("alt_labels", "[]")
                    if isinstance(alt_labels, list):
                        alt_labels = json.dumps(alt_labels)

                    self._upsert_fts(conn, concept)
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO concepts
                          (id, preferred_label, alt_labels,
                           broader, narrower, related, notation, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            concept["id"],
                            concept["preferred_label"],
                            alt_labels,
                            concept.get("broader", ""),
                            concept.get("narrower", ""),
                            concept.get("related", ""),
                            concept.get("notation", ""),
                            concept.get("source", ""),
                        ),
                    )
                # Update last_import timestamp
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) "
                    "VALUES ('last_import', datetime('now'))"
                )
            return len(concepts)
        finally:
            conn.close()

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search concepts via FTS5 + JSON alt_labels parsing."""
        limit = max(0, limit)

        # Guard: empty or whitespace-only queries return nothing
        if not query or not query.strip():
            return []

        conn = self._connect()
        try:
            # FTS5 search on preferred_label + notation.
            # Wrap query in double quotes so FTS5 treats user input as a
            # literal phrase, preventing operator injection (AND, OR, NOT, *).
            fts_query = '"' + query.replace('"', '""') + '"'
            fts_results: dict[str, dict[str, Any]] = {}
            try:
                rows = conn.execute(
                    """SELECT id, preferred_label, notation,
                              rank
                       FROM concepts_fts
                       WHERE concepts_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (fts_query, limit),
                ).fetchall()
                for row in rows:
                    fts_results[row["id"]] = {
                        "id": row["id"],
                        "preferred_label": row["preferred_label"],
                        "match_type": "preferred_label",
                        "notation": row["notation"],
                    }
            except sqlite3.OperationalError:
                # Any FTS5 error (syntax, unterminated string, etc.) —
                # skip FTS results entirely, LIKE fallback handles it.
                pass

            # Also search alt_labels (JSON column) for synonym matches
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like_pattern = f"%{escaped}%"
            alt_rows = conn.execute(
                "SELECT id, preferred_label, alt_labels, notation "
                "FROM concepts WHERE alt_labels LIKE ? ESCAPE '\\'",
                (like_pattern,),
            ).fetchall()

            results = list(fts_results.values())
            seen_ids = {r["id"] for r in results}

            for row in alt_rows:
                if row["id"] not in seen_ids:
                    # Check if query matches any alt_label
                    try:
                        alt_list = json.loads(row["alt_labels"])
                    except (json.JSONDecodeError, TypeError):
                        alt_list = []

                    matched = any(query.lower() in alt.lower() for alt in alt_list)
                    if matched:
                        results.append(
                            {
                                "id": row["id"],
                                "preferred_label": row["preferred_label"],
                                "match_type": "synonym",
                                "notation": row["notation"],
                            }
                        )
                        seen_ids.add(row["id"])

            return results[:limit]
        finally:
            conn.close()

    def list_concepts(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        offset = max(0, offset)
        limit = max(0, limit)
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, preferred_label, alt_labels, "
                "broader, narrower, related, notation, source "
                "FROM concepts ORDER BY preferred_label LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "preferred_label": row["preferred_label"],
                    "alt_labels": row["alt_labels"],
                    "broader": row["broader"],
                    "narrower": row["narrower"],
                    "related": row["related"],
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
        row = conn.execute(
            "SELECT source FROM concepts WHERE source != '' LIMIT 1"
        ).fetchone()
        return row["source"] if row else ""

    def stats(self) -> dict[str, Any]:
        conn = self._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
            # Count total alt_labels across all concepts
            total_alt = 0
            rows = conn.execute("SELECT alt_labels FROM concepts").fetchall()
            for row in rows:
                try:
                    alts = json.loads(row["alt_labels"]) if row["alt_labels"] else []
                    total_alt += len(alts)
                except (json.JSONDecodeError, TypeError):
                    pass
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
        import errno
        import shutil

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

            # Atomic swap: rename staging to live (same filesystem = atomic)
            try:
                os.rename(str(staging_path), str(self._db_path))
            except OSError as exc:
                if exc.errno == errno.EXDEV:
                    # Cross-device: fallback to copy+delete
                    shutil.copy2(str(staging_path), str(self._db_path))
                    os.remove(str(staging_path))
                else:
                    raise
        except Exception:
            # On any failure, clean up staging and preserve live DB
            staging_path.unlink(missing_ok=True)
            raise

    def _get_manifest_sha(self) -> str:
        """Get SHA256 of manifest file."""
        import hashlib

        manifest_path = self._db_path.parent / "vocabulary" / "manifest.json"
        if manifest_path.exists():
            content = manifest_path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        return ""
