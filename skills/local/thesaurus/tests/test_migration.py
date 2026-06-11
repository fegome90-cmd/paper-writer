"""Tests for thesaurus migration protocol — v1 and v2."""

import sqlite3
import typing
from pathlib import Path

from thesaurus.lite import LiteSemanticStore
from thesaurus.migration import run_migration

V1_SCHEMA = """
CREATE TABLE concepts (
    id TEXT PRIMARY KEY,
    preferred_label TEXT NOT NULL,
    alt_labels TEXT DEFAULT '[]',
    broader TEXT DEFAULT '',
    narrower TEXT DEFAULT '',
    related TEXT DEFAULT '',
    notation TEXT DEFAULT '',
    source TEXT DEFAULT ''
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
INSERT INTO schema_migrations (version, applied_at) VALUES (1, datetime('now'));
CREATE VIRTUAL TABLE concepts_fts USING fts5(
    id UNINDEXED, preferred_label, notation
);
"""


def test_migration_creates_normalized_tables(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn.close()

    assert "concepts" in tables
    assert "alt_labels" in tables
    assert "concept_relations" in tables
    assert "meta" in tables
    assert "schema_migrations" in tables


def test_migration_creates_fts5_with_alt_labels(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    fts_row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='concepts_fts'"
    ).fetchone()
    conn.close()

    assert fts_row is not None
    assert "alt_labels" in fts_row[0]


def test_migration_records_versions(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    versions = [r[0] for r in rows]
    conn.close()

    assert 1 in versions
    assert 2 in versions


def test_migration_idempotent(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    alt_before = conn.execute("SELECT COUNT(*) FROM alt_labels").fetchone()[0]
    rel_before = conn.execute("SELECT COUNT(*) FROM concept_relations").fetchone()[0]
    fts_before = conn.execute("SELECT COUNT(*) FROM concepts_fts").fetchone()[0]
    mig_before = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    alt_after = conn.execute("SELECT COUNT(*) FROM alt_labels").fetchone()[0]
    rel_after = conn.execute("SELECT COUNT(*) FROM concept_relations").fetchone()[0]
    fts_after = conn.execute("SELECT COUNT(*) FROM concepts_fts").fetchone()[0]
    mig_after = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()

    assert alt_after == alt_before
    assert rel_after == rel_before
    assert fts_after == fts_before
    assert mig_after == mig_before


def test_migration_migrates_v1_alt_labels(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'Asthma', '["Bronchial Asthma"]',
            'P01', 'C002', 'C003', 'A01', 'mesh'
        );
        INSERT INTO concepts VALUES (
            'C002', 'Asthma in Children', '["Pediatric Asthma"]',
            'C001', '', '', 'A02', 'mesh'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    store = LiteSemanticStore(db_path=str(db_path))
    results = store.search("Bronchial Asthma")
    assert len(results) == 1
    assert results[0]["id"] == "C001"
    assert results[0]["match_type"] == "synonym"


def test_migration_migrates_v1_relations(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'Asthma', '["Bronchial Asthma"]',
            'P01', 'C002', 'C003', 'A01', 'mesh'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT target_id, relation_type"
        " FROM concept_relations"
        " WHERE concept_id = 'C001'"
        " ORDER BY relation_type"
    ).fetchall()
    relations = {r[0]: r[1] for r in rows}
    conn.close()

    assert "P01" in relations
    assert relations["P01"] == "broader"
    assert "C002" in relations
    assert relations["C002"] == "narrower"
    assert "C003" in relations
    assert relations["C003"] == "related"


def test_migration_empty_v1_db(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(V1_SCHEMA)
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    alt_count = conn.execute("SELECT COUNT(*) FROM alt_labels").fetchone()[0]
    rel_count = conn.execute("SELECT COUNT(*) FROM concept_relations").fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM concepts_fts").fetchone()[0]
    conn.close()

    assert alt_count == 0
    assert rel_count == 0
    assert fts_count == 0


def test_migration_handles_invalid_json_alt_labels(
    tmp_path: typing.Any,
) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'Diabetes', 'Sugar Disease',
            '', '', '', 'D01', 'mesh'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT label FROM alt_labels WHERE concept_id = 'C001'").fetchall()
    labels = [r[0] for r in rows]
    conn.close()

    assert "Sugar Disease" in labels


def test_store_works_after_migration(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'Automobile', '["Car", "Vehicle"]',
            '', '', '', 'A.01', 'synthetic'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    store = LiteSemanticStore(db_path=str(db_path))
    assert store.concept_count == 1

    results = store.search("Car")
    assert len(results) == 1
    assert results[0]["id"] == "C001"
    assert results[0]["match_type"] == "synonym"

    results2 = store.search("Automobile")
    assert len(results2) == 1
    assert results2[0]["match_type"] == "preferred_label"


def test_migration_comma_separated_relations(
    tmp_path: typing.Any,
) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'Concept A', '[]',
            'P01,P02', '', '', 'A01', 'mesh'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT target_id, relation_type"
        " FROM concept_relations"
        " WHERE concept_id = 'C001'"
        " ORDER BY target_id"
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    assert rows[0] == ("P01", "broader")
    assert rows[1] == ("P02", "broader")


def test_migration_null_empty_json_alt_labels(
    tmp_path: typing.Any,
) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript(
        V1_SCHEMA
        + """
        INSERT INTO concepts VALUES (
            'C001', 'With Null', NULL,
            '', '', '', 'N01', 'mesh'
        );
        INSERT INTO concepts VALUES (
            'C002', 'With Empty', '',
            '', '', '', 'N02', 'mesh'
        );
        INSERT INTO concepts VALUES (
            'C003', 'With Empty Array', '[]',
            '', '', '', 'N03', 'mesh'
        );
    """
    )
    conn.close()

    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"
    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM alt_labels").fetchone()[0]
    conn.close()

    assert count == 0
