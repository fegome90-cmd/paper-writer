import sqlite3
from pathlib import Path

from mesh_import.migration import run_migration
from mesh_import.validation import validate_db

MIGRATIONS_DIR = Path(__file__).parent.parent / "workspace" / "migrations"


def _make_db_with_schema(tmp_path):
    db_path = tmp_path / "validate.db"
    run_migration(db_path, sql_dir=MIGRATIONS_DIR)
    return db_path


def _insert_minimal(conn):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D001', 'Test')"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M001', 'D001', 'TestConcept', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, "
        "descriptor_name, is_preferred) VALUES ('T001', 'M001', 'Test', 'test', 'Test', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_tree_node (tree_number, descriptor_ui, parent_tree_number) "
        "VALUES ('A01', 'D001', NULL)"
    )
    conn.execute(
        "INSERT INTO mesh_descriptor_tree (descriptor_ui, tree_number) VALUES ('D001', 'A01')"
    )
    conn.execute(
        "INSERT INTO mesh_concept_relation (source_concept_ui, target_concept_ui, relation_type) "
        "VALUES ('M001', 'M001', 'BRD')"
    )
    conn.commit()


def test_fk_violation_detected(tmp_path):
    db_path = _make_db_with_schema(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D001', 'Test')"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M001', 'D999', 'Orphan', 0)"
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    warnings = validate_db(conn)
    conn.close()

    assert any("FK violations" in w for w in warnings)


def test_duplicate_ui_detected():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE mesh_descriptor (descriptor_ui TEXT, descriptor_name TEXT)")
    conn.execute("CREATE TABLE mesh_concept (concept_ui TEXT, descriptor_ui TEXT, concept_name TEXT, is_preferred INTEGER DEFAULT 0)")  # noqa: E501
    conn.execute("CREATE TABLE mesh_term (term_ui TEXT, concept_ui TEXT, term_text TEXT, normalized_text TEXT, descriptor_name TEXT, is_preferred INTEGER DEFAULT 0)")  # noqa: E501
    conn.execute("CREATE TABLE mesh_tree_node (tree_number TEXT, descriptor_ui TEXT, parent_tree_number TEXT)")  # noqa: E501
    conn.execute("CREATE TABLE mesh_descriptor_tree (descriptor_ui TEXT, tree_number TEXT)")
    conn.execute("CREATE TABLE mesh_concept_relation (source_concept_ui TEXT, target_concept_ui TEXT, relation_type TEXT)")  # noqa: E501
    conn.execute("INSERT INTO mesh_descriptor VALUES ('D001', 'First')")
    conn.execute("INSERT INTO mesh_descriptor VALUES ('D001', 'Duplicate')")

    warnings = validate_db(conn)
    conn.close()

    assert any("Duplicate descriptor_ui" in w for w in warnings)


def test_missing_tree_parent_warning_only(tmp_path):
    db_path = _make_db_with_schema(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D001', 'Test')"
    )
    conn.execute(
        "INSERT INTO mesh_tree_node (tree_number, descriptor_ui, parent_tree_number) "
        "VALUES ('A01.456', 'D001', 'A01')"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M001', 'D001', 'C', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, "
        "descriptor_name, is_preferred) VALUES ('T001', 'M001', 'T', 't', 'Test', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_descriptor_tree (descriptor_ui, tree_number) "
        "VALUES ('D001', 'A01.456')"
    )
    conn.execute(
        "INSERT INTO mesh_concept_relation (source_concept_ui, target_concept_ui, relation_type) "
        "VALUES ('M001', 'M001', 'BRD')"
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    warnings = validate_db(conn)
    conn.close()

    assert any("missing parents" in w for w in warnings)
    fk_warnings = [w for w in warnings if "FK violations" in w]
    assert len(fk_warnings) == 0


def test_count_thresholds_warning(tmp_path):
    db_path = _make_db_with_schema(tmp_path)
    conn = sqlite3.connect(str(db_path))
    _insert_minimal(conn)
    conn.close()

    conn = sqlite3.connect(str(db_path))
    warnings = validate_db(conn)
    conn.close()

    assert any("Descriptor count" in w for w in warnings)
    assert any("Concept count" in w for w in warnings)


def test_empty_fk_table_warning(tmp_path):
    db_path = _make_db_with_schema(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D001', 'Test')"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M001', 'D001', 'C', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, "
        "descriptor_name, is_preferred) VALUES ('T001', 'M001', 'T', 't', 'Test', 1)"
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    warnings = validate_db(conn)
    conn.close()

    assert any("mesh_tree_node has 0 rows" in w for w in warnings)
    assert any("mesh_concept_relation has 0 rows" in w for w in warnings)


def test_non_contiguous_tree_numbers_ok(tmp_path):
    db_path = _make_db_with_schema(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D001', 'Alpha')"
    )
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES ('D002', 'Gamma')"
    )
    conn.execute(
        "INSERT INTO mesh_tree_node (tree_number, descriptor_ui, parent_tree_number) "
        "VALUES ('A01', 'D001', NULL)"
    )
    conn.execute(
        "INSERT INTO mesh_tree_node (tree_number, descriptor_ui, parent_tree_number) "
        "VALUES ('A03', 'D002', NULL)"
    )
    conn.execute(
        "INSERT INTO mesh_descriptor_tree (descriptor_ui, tree_number) VALUES ('D001', 'A01')"
    )
    conn.execute(
        "INSERT INTO mesh_descriptor_tree (descriptor_ui, tree_number) VALUES ('D002', 'A03')"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M001', 'D001', 'C1', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES ('M002', 'D002', 'C2', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, "
        "descriptor_name, is_preferred) VALUES ('T001', 'M001', 'Alpha', 'alpha', 'Alpha', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, "
        "descriptor_name, is_preferred) VALUES ('T002', 'M002', 'Gamma', 'gamma', 'Gamma', 1)"
    )
    conn.execute(
        "INSERT INTO mesh_concept_relation (source_concept_ui, target_concept_ui, relation_type) "
        "VALUES ('M001', 'M002', 'BRD')"
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(str(db_path))
    warnings = validate_db(conn)
    conn.close()

    gap_warnings = [
        w for w in warnings if "gap" in w.lower() or "contiguous" in w.lower() or "missing" in w.lower() and "A02" in w
    ]
    assert len(gap_warnings) == 0, f"Gaps in TreeNumbers should not produce warnings: {gap_warnings}"
