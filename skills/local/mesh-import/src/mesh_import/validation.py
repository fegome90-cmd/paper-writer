"""Post-import validation for MeSH SQLite database."""

from __future__ import annotations

import sqlite3


def validate_db(conn: sqlite3.Connection) -> list[str]:
    """Validate a MeSH database after import. Returns list of warnings.

    Checks per Decision #9:
    (a) FK integrity via PRAGMA foreign_key_check
    (b) Unique UIs via GROUP BY HAVING COUNT(*) > 1
    (c) Tree parent existence via self-join (WARNING only)
    (d) Count thresholds: descriptor [25000, 35000], concept [150000, 250000]
    (e) Any FK table with 0 rows
    """
    warnings: list[str] = []

    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        warnings.append(f"FK violations: {len(fk_violations)}")

    for table, col in [
        ("mesh_descriptor", "descriptor_ui"),
        ("mesh_concept", "concept_ui"),
        ("mesh_term", "term_ui"),
    ]:
        dupes = conn.execute(
            f"SELECT {col}, COUNT(*) as n FROM {table} GROUP BY {col} HAVING n > 1"
        ).fetchall()
        if dupes:
            warnings.append(f"Duplicate {col} in {table}: {len(dupes)}")

    orphan_parents = conn.execute(
        """SELECT DISTINCT t.parent_tree_number
           FROM mesh_tree_node t
           WHERE t.parent_tree_number IS NOT NULL
             AND NOT EXISTS (
               SELECT 1 FROM mesh_tree_node p
               WHERE p.tree_number = t.parent_tree_number
             )"""
    ).fetchall()
    if orphan_parents:
        examples = [r[0] for r in orphan_parents[:5]]
        warnings.append(
            f"Tree numbers with missing parents: {len(orphan_parents)} (examples: {examples})"
        )

    desc_count = conn.execute("SELECT COUNT(*) FROM mesh_descriptor").fetchone()[0]
    if desc_count < 25000 or desc_count > 35000:
        warnings.append(f"Descriptor count {desc_count} outside expected range [25000, 35000]")

    concept_count = conn.execute("SELECT COUNT(*) FROM mesh_concept").fetchone()[0]
    if concept_count < 150000 or concept_count > 250000:
        warnings.append(f"Concept count {concept_count} outside expected range [150000, 250000]")

    for table in [
        "mesh_concept",
        "mesh_term",
        "mesh_tree_node",
        "mesh_descriptor_tree",
        "mesh_concept_relation",
    ]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count == 0:
            warnings.append(f"Table {table} has 0 rows")

    return warnings
