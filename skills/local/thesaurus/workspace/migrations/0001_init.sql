-- Thesaurus schema v1
-- Tables: concepts, meta, schema_migrations
-- FTS5 virtual table for full-text search on preferred_label + notation

CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    preferred_label TEXT NOT NULL,
    alt_labels TEXT DEFAULT '[]',
    broader TEXT DEFAULT '',
    narrower TEXT DEFAULT '',
    related TEXT DEFAULT '',
    notation TEXT DEFAULT '',
    source TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS concepts_fts USING fts5(
    id UNINDEXED,
    preferred_label,
    notation
);
