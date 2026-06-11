-- Thesaurus schema v2 — normalize alt_labels and relationships
-- Migrates v1 columns (alt_labels TEXT, broader, narrower, related)
-- into dedicated normalized tables: alt_labels, concept_relations.
-- Rebuilds FTS5 with alt_labels column for synonym search.
-- Forward-only: no down migration.

-- Create normalized tables (idempotent)
CREATE TABLE IF NOT EXISTS alt_labels (
    concept_id TEXT NOT NULL,
    label TEXT NOT NULL,
    PRIMARY KEY (concept_id, label),
    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS concept_relations (
    concept_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    PRIMARY KEY (concept_id, target_id, relation_type),
    FOREIGN KEY(concept_id) REFERENCES concepts(id) ON DELETE CASCADE
    -- NOTE: target_id has NO FK — MeSH hierarchies have forward references
    -- (a concept can be broader/narrower of a concept not yet imported)
);

-- Migrate alt_labels from JSON array text column to row-per-label
INSERT OR IGNORE INTO alt_labels (concept_id, label)
SELECT c.id, trim(j.value)
FROM concepts c, json_each(
    CASE
        WHEN json_valid(COALESCE(c.alt_labels, '[]')) THEN COALESCE(c.alt_labels, '[]')
        ELSE '[]'
    END
) j
WHERE trim(j.value) <> '';

-- Also capture non-JSON alt_labels as a single label.
-- NOTE: This treats the entire string as one label, including commas.
-- The primary path is the JSON array branch above. This is a fallback for v1 data.
INSERT OR IGNORE INTO alt_labels (concept_id, label)
SELECT c.id, trim(c.alt_labels)
FROM concepts c
WHERE c.alt_labels IS NOT NULL
  AND c.alt_labels <> ''
  AND trim(c.alt_labels) <> '[]'
  AND trim(c.alt_labels) <> ''
  AND NOT json_valid(c.alt_labels);

-- Migrate broader, narrower, related from comma-separated text to rows
-- Uses recursive CTE to split comma-separated IDs.

-- Broader
INSERT OR IGNORE INTO concept_relations (concept_id, target_id, relation_type)
WITH RECURSIVE split(concept_id, rest) AS (
    SELECT id, COALESCE(broader, '') || ',' FROM concepts WHERE COALESCE(broader, '') <> ''
    UNION ALL
    SELECT concept_id, substr(rest, instr(rest, ',') + 1)
    FROM split
    WHERE rest <> '' AND length(rest) < 10000
)
SELECT concept_id, trim(substr(rest, 1, instr(rest, ',') - 1)), 'broader'
FROM split
WHERE rest <> ''
  AND instr(rest, ',') > 0
  AND trim(substr(rest, 1, instr(rest, ',') - 1)) <> '';

-- Narrower
INSERT OR IGNORE INTO concept_relations (concept_id, target_id, relation_type)
WITH RECURSIVE split(concept_id, rest) AS (
    SELECT id, COALESCE(narrower, '') || ',' FROM concepts WHERE COALESCE(narrower, '') <> ''
    UNION ALL
    SELECT concept_id, substr(rest, instr(rest, ',') + 1)
    FROM split
    WHERE rest <> '' AND length(rest) < 10000
)
SELECT concept_id, trim(substr(rest, 1, instr(rest, ',') - 1)), 'narrower'
FROM split
WHERE rest <> ''
  AND instr(rest, ',') > 0
  AND trim(substr(rest, 1, instr(rest, ',') - 1)) <> '';

-- Related
INSERT OR IGNORE INTO concept_relations (concept_id, target_id, relation_type)
WITH RECURSIVE split(concept_id, rest) AS (
    SELECT id, COALESCE(related, '') || ',' FROM concepts WHERE COALESCE(related, '') <> ''
    UNION ALL
    SELECT concept_id, substr(rest, instr(rest, ',') + 1)
    FROM split
    WHERE rest <> '' AND length(rest) < 10000
)
SELECT concept_id, trim(substr(rest, 1, instr(rest, ',') - 1)), 'related'
FROM split
WHERE rest <> ''
  AND instr(rest, ',') > 0
  AND trim(substr(rest, 1, instr(rest, ',') - 1)) <> '';

-- Rebuild FTS5 with alt_labels column for synonym search
DROP TABLE IF EXISTS concepts_fts;

CREATE VIRTUAL TABLE concepts_fts USING fts5(
    id UNINDEXED,
    preferred_label,
    notation,
    alt_labels
);

INSERT INTO concepts_fts (id, preferred_label, notation, alt_labels)
SELECT c.id, c.preferred_label, COALESCE(c.notation, ''),
    COALESCE(GROUP_CONCAT(a.label, ' '), '')
FROM concepts c
LEFT JOIN alt_labels a ON a.concept_id = c.id
GROUP BY c.id, c.preferred_label, c.notation;

-- Record schema version
INSERT OR REPLACE INTO meta (key, value)
VALUES ('schema_version', '2');
