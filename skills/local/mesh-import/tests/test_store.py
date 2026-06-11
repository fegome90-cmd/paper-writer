import sqlite3

import pytest
from mesh_import.store import ChecksumMismatchError, MeshStore


def test_import_creates_db(populated_store, populated_db):
    import os

    assert os.path.exists(populated_db)

    conn = sqlite3.connect(populated_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    desc_count = conn.execute("SELECT COUNT(*) FROM mesh_descriptor").fetchone()[0]
    assert desc_count == 2

    concept_count = conn.execute("SELECT COUNT(*) FROM mesh_concept").fetchone()[0]
    assert concept_count == 3

    term_count = conn.execute("SELECT COUNT(*) FROM mesh_term").fetchone()[0]
    assert term_count == 4

    release = conn.execute("SELECT * FROM vocabulary_release").fetchone()
    assert release["mesh_version"] == "unknown"
    assert release["descriptor_count"] == 2
    assert release["concept_count"] == 3
    assert release["term_count"] == 4

    conn.close()


def test_fts5_rebuild_and_search(populated_store, populated_db):
    results = populated_store.resolve("cafe")
    assert len(results) >= 1
    assert results[0]["descriptor_ui"] == "D000001"
    assert results[0]["descriptor_name"] == "Café"
    assert "match_type" in results[0]
    assert "tree_numbers" in results[0]

    results2 = populated_store.resolve("aspirin")
    assert len(results2) >= 1
    assert results2[0]["descriptor_ui"] == "D000002"

    assert populated_store.resolve("") == []
    assert populated_store.resolve("   ") == []


def test_idempotent_reimport(populated_store, populated_db, sample_xml_path):
    conn1 = sqlite3.connect(populated_db)
    conn1.row_factory = sqlite3.Row
    tables = [
        "mesh_descriptor",
        "mesh_concept",
        "mesh_term",
        "mesh_tree_node",
        "mesh_descriptor_tree",
        "mesh_concept_relation",
    ]
    counts_before = {}
    rows_before = {}
    for t in tables:
        counts_before[t] = conn1.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        rows_before[t] = conn1.execute(
            f"SELECT * FROM {t} ORDER BY rowid"
        ).fetchall()
    conn1.close()

    populated_store.import_xml(sample_xml_path)

    conn2 = sqlite3.connect(populated_db)
    conn2.row_factory = sqlite3.Row
    for t in tables:
        count_after = conn2.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        assert count_after == counts_before[t], f"{t}: {count_after} != {counts_before[t]}"

        rows_after = conn2.execute(
            f"SELECT * FROM {t} ORDER BY rowid"
        ).fetchall()
        assert len(rows_after) == len(rows_before[t]), f"{t}: row count mismatch after re-import"
    conn2.close()


def test_stale_staging_cleanup(tmp_db, sample_xml_path, tmp_path):
    staging_path = tmp_path / "mesh.db.staging.db"
    staging_path.write_text("stale data")

    store = MeshStore(tmp_db)
    store.import_xml(sample_xml_path)

    assert not staging_path.exists()
    import os

    assert os.path.exists(tmp_db)


def test_checksum_mismatch_error(populated_db, sample_xml_path, tmp_path):
    tampered = tmp_path / "tampered.xml"
    tampered.write_text(
        '<?xml version="1.0"?>'
        "<DescriptorRecordSet>"
        "<DescriptorRecord>"
        "<DescriptorUI>D999</DescriptorUI>"
        "<DescriptorName><String>Tampered</String></DescriptorName>"
        "<ConceptList>"
        '<Concept PreferredConcept="Y">'
        "<ConceptUI>M999</ConceptUI>"
        "<ConceptName><String>T</String></ConceptName>"
        "<TermList>"
        '<Term TermPreferred="Y">'
        "<TermUI>T999</TermUI>"
        "<String>T</String>"
        "</Term>"
        "</TermList>"
        "</Concept>"
        "</ConceptList>"
        "</DescriptorRecord>"
        "</DescriptorRecordSet>"
    )

    store = MeshStore(populated_db)
    with pytest.raises(ChecksumMismatchError, match="differs from file"):
        store.import_xml(str(tampered))


def test_entry_match_type(populated_store, populated_db):
    results = populated_store.resolve("beverage")
    assert len(results) >= 1
    assert results[0]["descriptor_ui"] == "D000001"
    assert results[0]["match_type"] == "entry"


def test_rel_inverse_in_db(populated_db):
    conn = sqlite3.connect(populated_db)
    conn.row_factory = sqlite3.Row

    forward = conn.execute(
        "SELECT * FROM mesh_concept_relation "
        "WHERE source_concept_ui = 'M0000003' AND target_concept_ui = 'M0000001' AND relation_type = 'REL'"
    ).fetchall()
    assert len(forward) >= 1, "REL(M0000003→M0000001) should exist"

    inverse = conn.execute(
        "SELECT * FROM mesh_concept_relation "
        "WHERE source_concept_ui = 'M0000001' AND target_concept_ui = 'M0000003' AND relation_type = 'REL'"
    ).fetchall()
    assert len(inverse) >= 1, "REL(M0000001→M0000003) inverse should exist"

    conn.close()
