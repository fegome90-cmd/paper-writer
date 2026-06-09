"""MeshStore — SQLite staging-based MeSH import with FTS5 search."""

from __future__ import annotations

import errno
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from mesh_import.migration import run_migration
from mesh_import.parser import parse_descriptor_xml
from mesh_import.validation import validate_db

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "workspace" / "migrations"


class ChecksumMismatchError(Exception):
    """Raised when XML SHA256 doesn't match the stored checksum."""


class MeshStore:
    """Staging-based MeSH import with atomic swap, FTS5 resolve, tree expand."""

    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)

    @staticmethod
    def _connect(db_path: str | Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _read_stored_sha256(self) -> str | None:
        if not self._db_path.exists():
            return None
        try:
            conn = sqlite3.connect(str(self._db_path))
            try:
                row = conn.execute(
                    "SELECT xml_sha256 FROM vocabulary_release ORDER BY imported_at DESC LIMIT 1"
                ).fetchone()
                return row[0] if row else None
            finally:
                conn.close()
        except sqlite3.OperationalError:
            return None

    @staticmethod
    def _cleanup_staging(staging_path: Path) -> None:
        for suffix in ("", "-journal", "-wal", "-shm"):
            try:
                Path(str(staging_path) + suffix).unlink(missing_ok=True)
            except OSError as exc:
                print(
                    f"WARNING: Could not remove {staging_path}{suffix}: {exc}",
                    file=sys.stderr,
                )

    @staticmethod
    def _atomic_swap(staging_path: Path, target_path: Path) -> None:
        """Decision #5: shutil.move with EXDEV fallback."""
        try:
            os.rename(str(staging_path), str(target_path))
        except OSError as exc:
            if exc.errno == errno.EXDEV:
                print(
                    "WARNING: Cross-device rename; falling back to copy+delete",
                    file=sys.stderr,
                )
                shutil.copy2(str(staging_path), str(target_path))
                os.remove(str(staging_path))
            else:
                raise

    @staticmethod
    def _derive_mesh_version(xml_path: str) -> str:
        match = re.search(r"desc(\d+)", xml_path, re.IGNORECASE)
        return match.group(1) if match else "unknown"

    def import_xml(self, xml_path: str, dtd_path: str | None = None) -> dict[str, Any]:
        """Full import pipeline per Decision #3 7-step sequence.

        1. Compute SHA256 (via parser)
        2. Check against stored checksum
        3. Create staging DB + run migration
        4. BEGIN IMMEDIATE
        5. INSERT all data
        6. FTS5 rebuild
        7. COMMIT → validate → atomic swap
        """
        start = time.time()

        result = parse_descriptor_xml(xml_path, dtd_path)
        sha256_hex = result.sha256_hex

        stored = self._read_stored_sha256()
        if stored is not None and stored != sha256_hex:
            raise ChecksumMismatchError(
                f"Stored SHA256 {stored} differs from file SHA256 {sha256_hex}. "
                f"Delete the database to import a different release."
            )

        staging_path = Path(str(self._db_path) + ".staging.db")
        self._cleanup_staging(staging_path)
        staging_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            run_migration(staging_path, sql_dir=_MIGRATIONS_DIR)

            conn = sqlite3.connect(str(staging_path), isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row

            try:
                conn.execute("BEGIN IMMEDIATE")

                mesh_version = self._derive_mesh_version(xml_path)
                release_id = f"mesh-{mesh_version}-{sha256_hex[:12]}"
                conn.execute(
                    """INSERT INTO vocabulary_release
                       (release_id, mesh_version, xml_sha256, dtd_sha256,
                        imported_at, descriptor_count, concept_count, term_count)
                       VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?)""",
                    (
                        release_id,
                        mesh_version,
                        sha256_hex,
                        result.dtd_sha256_hex,
                        len(result.descriptors),
                        len(result.concepts),
                        len(result.terms),
                    ),
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO mesh_descriptor
                       (descriptor_ui, descriptor_name, tree_numbers_json,
                        annotation, pharmacological_action_json,
                        registry_number, scope_note)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            d.descriptor_ui,
                            d.descriptor_name,
                            d.tree_numbers_json,
                            d.annotation,
                            d.pharmacological_action_json,
                            d.registry_number,
                            d.scope_note,
                        )
                        for d in result.descriptors
                    ],
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO mesh_concept
                       (concept_ui, descriptor_ui, concept_name, cui,
                        semantic_type_list_json, is_preferred)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            c.concept_ui,
                            c.descriptor_ui,
                            c.concept_name,
                            c.cui,
                            c.semantic_type_list_json,
                            int(c.is_preferred),
                        )
                        for c in result.concepts
                    ],
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO mesh_term
                       (term_ui, concept_ui, term_text, normalized_text,
                        descriptor_name, term_type, is_preferred)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            t.term_ui,
                            t.concept_ui,
                            t.term_text,
                            t.normalized_text,
                            t.descriptor_name,
                            t.term_type,
                            int(t.is_preferred),
                        )
                        for t in result.terms
                    ],
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO mesh_tree_node
                       (tree_number, descriptor_ui, parent_tree_number)
                       VALUES (?, ?, ?)""",
                    [
                        (tn.tree_number, tn.descriptor_ui, tn.parent_tree_number)
                        for tn in result.tree_nodes
                    ],
                )

                conn.executemany(
                    """INSERT OR REPLACE INTO mesh_descriptor_tree
                       (descriptor_ui, tree_number) VALUES (?, ?)""",
                    result.descriptor_trees,
                )

                conn.executemany(
                    """INSERT OR IGNORE INTO mesh_concept_relation
                       (source_concept_ui, target_concept_ui, relation_type)
                       VALUES (?, ?, ?)""",
                    [
                        (r.source_concept_ui, r.target_concept_ui, r.relation_type)
                        for r in result.relations
                    ],
                )

                conn.execute("INSERT INTO mesh_term_fts(mesh_term_fts) VALUES('rebuild')")

                conn.execute("COMMIT")
            except BaseException:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

            vconn = self._connect(staging_path)
            try:
                warnings = validate_db(vconn)
                for w in warnings:
                    print(f"VALIDATION WARNING: {w}", file=sys.stderr)
            finally:
                vconn.close()

            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_swap(staging_path, self._db_path)

        except BaseException:
            self._cleanup_staging(staging_path)
            raise

        self._cleanup_staging(staging_path)

        elapsed = time.time() - start
        return {
            "descriptors": len(result.descriptors),
            "concepts": len(result.concepts),
            "terms": len(result.terms),
            "elapsed": f"{elapsed:.1f}s",
            "sha256": sha256_hex,
        }

    def resolve(self, term: str) -> list[dict[str, Any]]:
        """FTS5 MATCH with double-quoted phrase (REQ-M5)."""
        if not term or not term.strip():
            return []

        conn = self._connect(self._db_path)
        try:
            escaped = term.replace('"', '""')
            fts_query = f'"{escaped}"'

            rows = conn.execute(
                """SELECT mt.descriptor_name, mc.descriptor_ui, mt.is_preferred,
                          mc.is_preferred as concept_is_preferred
                   FROM mesh_term_fts mtf
                   JOIN mesh_term mt ON mt.rowid = mtf.rowid
                   JOIN mesh_concept mc ON mc.concept_ui = mt.concept_ui
                   WHERE mesh_term_fts MATCH ?
                   ORDER BY mc.is_preferred DESC, mt.is_preferred DESC
                   LIMIT 200""",
                (fts_query,),
            ).fetchall()

            results: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                dui = row["descriptor_ui"]
                if dui in seen:
                    continue
                seen.add(dui)
                if row["concept_is_preferred"]:
                    match_type = "preferred" if row["is_preferred"] else "synonym"
                else:
                    match_type = "entry"

                tn_rows = conn.execute(
                    "SELECT tree_number FROM mesh_descriptor_tree WHERE descriptor_ui = ?",
                    (dui,),
                ).fetchall()

                results.append(
                    {
                        "descriptor_ui": dui,
                        "descriptor_name": row["descriptor_name"],
                        "match_type": match_type,
                        "tree_numbers": [r["tree_number"] for r in tn_rows],
                    }
                )

            return results
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def expand_tree(self, descriptor_ui: str) -> list[dict[str, Any]]:
        """Tree traversal via parent_tree_number self-join, depth 0-indexed."""
        conn = self._connect(self._db_path)
        try:
            tree_rows = conn.execute(
                "SELECT tree_number FROM mesh_descriptor_tree WHERE descriptor_ui = ?",
                (descriptor_ui,),
            ).fetchall()

            if not tree_rows:
                return []

            results: list[dict[str, Any]] = []
            for row in tree_rows:
                root_tn = row["tree_number"]
                desc_rows = conn.execute(
                    """WITH RECURSIVE tree AS (
                        SELECT tree_number, descriptor_ui,
                               parent_tree_number, 0 as depth
                        FROM mesh_tree_node
                        WHERE tree_number = ?
                        UNION ALL
                        SELECT c.tree_number, c.descriptor_ui,
                               c.parent_tree_number, p.depth + 1
                        FROM mesh_tree_node c
                        JOIN tree p ON c.parent_tree_number = p.tree_number
                    )
                    SELECT t.tree_number, t.descriptor_ui,
                           md.descriptor_name, t.depth
                    FROM tree t
                    JOIN mesh_descriptor md ON md.descriptor_ui = t.descriptor_ui
                    ORDER BY t.depth, t.tree_number""",
                    (root_tn,),
                ).fetchall()

                for r in desc_rows:
                    results.append(
                        {
                            "tree_number": r["tree_number"],
                            "descriptor_ui": r["descriptor_ui"],
                            "descriptor_name": r["descriptor_name"],
                            "depth": r["depth"],
                        }
                    )

            return results
        finally:
            conn.close()
