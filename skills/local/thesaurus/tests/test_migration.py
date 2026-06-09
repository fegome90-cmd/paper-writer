"""Tests for migration protocol."""

import sqlite3
from pathlib import Path

from thesaurus.migration import run_migration


def test_migration_creates_tables(tmp_path):
    """Successful migration creates all expected tables."""
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    tables = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()

    assert "concepts" in tables
    assert "meta" in tables
    assert "schema_migrations" in tables


def test_migration_idempotent(tmp_path):
    """Running migration twice doesn't fail."""
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)
    run_migration(db_path,  sql_dir)  # Second run should be no-op


def test_migration_records_version(tmp_path):
    """Migration records applied version in schema_migrations."""
    db_path = tmp_path / "test.db"
    sql_dir = Path(__file__).parent.parent / "workspace" / "migrations"

    run_migration(db_path, sql_dir)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT version FROM schema_migrations").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == 1  # Version from 0001_init.sql
