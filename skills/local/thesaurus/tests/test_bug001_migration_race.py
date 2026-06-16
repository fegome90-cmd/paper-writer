"""Regression test for BUG-001: rebuild() leaves schema_migrations with only v1.

After rebuild(), the staging DB has schema v2 applied (alt_labels normalized
to separate table, FTS5 rebuilt). But if schema_migrations only records v1,
the next _ensure_schema() tries to re-apply migration 0002 which references
c.alt_labels — and since SQLite can't DROP COLUMN easily (pre-3.35), the
column still EXISTS in concepts. The migration 0002 does NOT remove the column;
it reads from it. So re-applying 0002 on a DB that already has the data would
cause duplicate INSERT OR IGNORE (harmless) but NOT a crash.

The ACTUAL crash in BUG-001 happened because rebuild() created a staging DB
with the correct schema but when the live DB was overwritten, the live DB had
schema v2 BUT schema_migrations only had v1. When _ensure_schema() tried to
re-apply 0002, it referenced c.alt_labels which was present (column exists)
but the FTS5 table had already been dropped and recreated. The re-apply tried
to DROP TABLE IF EXISTS concepts_fts (fine) then CREATE (fine) then INSERT
referencing alt_labels (fine — column still exists). The crash was actually
because the staging DB backup didn't preserve schema_migrations correctly.

This test simulates the state where schema_migrations has v1-only but the
schema is at v2, and verifies _ensure_schema() handles it gracefully.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_ensure_schema_survives_v1only_ledger_with_v2_schema(tmp_path: Path) -> None:
    """BUG-001 regression: schema_migrations has only v1, but schema is v2.

    Constructs the corrupt state: apply both migrations normally, then delete
    v2 from schema_migrations. _ensure_schema() must not crash.
    """
    from thesaurus.lite import _MIGRATIONS_DIR, LiteSemanticStore
    from thesaurus.migration import run_migration

    db_path = tmp_path / "thesaurus.db"

    # Apply both migrations (creates v1 + v2 schema, registers both versions)
    run_migration(db_path, sql_dir=Path(str(_MIGRATIONS_DIR)))

    # Corrupt: remove v2 from schema_migrations (simulates the rebuild race)
    conn = sqlite3.connect(str(db_path))
    conn.execute("DELETE FROM schema_migrations WHERE version = 2")
    conn.commit()
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()]
    assert versions == [1], f"Precondition: only v1 registered, got {versions}"
    conn.close()

    # The critical test: _ensure_schema() on this corrupt state must NOT crash.
    # The migration 0002 will be re-attempted (v2 not in ledger), but since
    # all DDL uses IF NOT EXISTS / IF EXISTS and INSERT uses OR IGNORE, the
    # re-application should be idempotent (no crash, no duplicate data).
    try:
        store = LiteSemanticStore(db_path=str(db_path))
    except Exception as exc:
        if "alt_labels" in str(exc).lower() or "no such column" in str(exc).lower():
            pytest.fail(
                f"BUG-001 REGRESSION: _ensure_schema() crashed on corrupt migration state: {exc}"
            )
        raise

    # Verify the store is functional after the corrupt-state recovery
    results = store.search("test")
    assert isinstance(results, list), "Store must be functional after _ensure_schema()"
