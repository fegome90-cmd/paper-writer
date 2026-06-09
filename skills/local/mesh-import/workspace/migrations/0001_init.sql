-- MeSH schema v1
-- Tables: vocabulary_release, mesh_descriptor, mesh_concept, mesh_term,
--         mesh_tree_node, mesh_descriptor_tree, mesh_concept_relation
-- FTS5 virtual table for full-text search on term_text + normalized_text + descriptor_name

PRAGMA foreign_keys = ON;

CREATE TABLE vocabulary_release (
    release_id    TEXT PRIMARY KEY,
    mesh_version  TEXT NOT NULL,
    xml_sha256    TEXT NOT NULL UNIQUE,
    dtd_sha256    TEXT,
    imported_at   TEXT NOT NULL,
    descriptor_count INTEGER NOT NULL,
    concept_count    INTEGER NOT NULL,
    term_count       INTEGER NOT NULL
);

CREATE TABLE mesh_descriptor (
    descriptor_ui TEXT PRIMARY KEY,
    descriptor_name TEXT NOT NULL,
    tree_numbers_json TEXT,
    annotation TEXT,
    pharmacological_action_json TEXT,
    registry_number TEXT,
    scope_note TEXT
);

CREATE TABLE mesh_concept (
    concept_ui TEXT PRIMARY KEY,
    descriptor_ui TEXT NOT NULL REFERENCES mesh_descriptor(descriptor_ui) ON DELETE CASCADE,
    concept_name TEXT NOT NULL,
    cui TEXT,
    semantic_type_list_json TEXT,
    is_preferred INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE mesh_term (
    term_ui TEXT PRIMARY KEY,
    concept_ui TEXT NOT NULL REFERENCES mesh_concept(concept_ui) ON DELETE CASCADE,
    term_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    descriptor_name TEXT NOT NULL,
    term_type TEXT,
    is_preferred INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE mesh_tree_node (
    tree_number TEXT PRIMARY KEY,
    descriptor_ui TEXT NOT NULL REFERENCES mesh_descriptor(descriptor_ui) ON DELETE CASCADE,
    parent_tree_number TEXT
);

CREATE TABLE mesh_descriptor_tree (
    descriptor_ui TEXT NOT NULL REFERENCES mesh_descriptor(descriptor_ui) ON DELETE CASCADE,
    tree_number TEXT NOT NULL REFERENCES mesh_tree_node(tree_number) ON DELETE CASCADE,
    PRIMARY KEY (descriptor_ui, tree_number)
);

CREATE TABLE mesh_concept_relation (
    source_concept_ui TEXT NOT NULL REFERENCES mesh_concept(concept_ui) ON DELETE CASCADE,
    target_concept_ui TEXT NOT NULL REFERENCES mesh_concept(concept_ui) ON DELETE CASCADE,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('BRD', 'NRW', 'REL')),
    PRIMARY KEY (source_concept_ui, target_concept_ui, relation_type)
);

CREATE INDEX idx_mesh_concept_descriptor ON mesh_concept(descriptor_ui);
CREATE INDEX idx_mesh_term_concept ON mesh_term(concept_ui);
CREATE INDEX idx_mesh_tree_parent ON mesh_tree_node(parent_tree_number);
CREATE INDEX idx_mesh_tree_descriptor ON mesh_tree_node(descriptor_ui);
CREATE INDEX idx_mesh_desc_tree_number ON mesh_descriptor_tree(tree_number);

CREATE VIRTUAL TABLE mesh_term_fts USING fts5(
    term_text,
    normalized_text,
    descriptor_name,
    content=mesh_term,
    content_rowid=rowid,
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
