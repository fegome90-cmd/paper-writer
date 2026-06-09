"""Migration runner — wraps SQL in transactions with rollback."""

import sqlite3
from pathlib import Path


def run_migration(db_path: str | Path, sql_dir: str | Path | None = None) -> None:
    """Run all .sql migration files against the database.

    Each migration runs in a single transaction. On failure, full rollback.

    Args:
        db_path: Path to the SQLite database file.
        sql_dir: Directory containing .sql files. Defaults to workspace/migrations/.
    """
    db_path = Path(db_path)
    if sql_dir is None:
        # Default: workspace/migrations/ relative to the DB's workspace dir
        sql_dir = db_path.parent / "migrations"
    else:
        sql_dir = Path(sql_dir)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")

        sql_files = sorted(sql_dir.glob("*.sql"))
        for sql_file in sql_files:
            _run_single_migration(conn, sql_file)
    finally:
        conn.close()


def _run_single_migration(conn: sqlite3.Connection, sql_file: Path) -> None:
    """Execute a single SQL migration file in a transaction."""
    try:
        version = int(sql_file.stem.split("_")[0])
    except (ValueError, IndexError) as exc:
        raise ValueError(
            f"Migration file '{sql_file.name}' must follow naming convention NNNN_name.sql"
        ) from exc

    # Check if already applied (skip if schema_migrations doesn't exist yet)
    try:
        cursor = conn.execute(
            "SELECT version FROM schema_migrations WHERE version = ?", (version,)
        )
        if cursor.fetchone() is not None:
            return
    except sqlite3.OperationalError:
        pass  # schema_migrations table doesn't exist yet — first migration

    sql = sql_file.read_text(encoding="utf-8")
    # NOTE: This split-by-semicolon is safe only for DDL migrations (no string literals
    # or comments containing semicolons). Do not use for arbitrary SQL with user data.
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with conn:
        for stmt in statements:
            conn.execute(stmt)
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
