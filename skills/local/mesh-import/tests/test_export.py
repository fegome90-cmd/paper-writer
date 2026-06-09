"""Tests for mesh_import.export — Phase 3 (Unit) and Phase 4 (Integration)."""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mesh_import.export import export_jsonl

MESH_SRC = Path(__file__).parent.parent / "src"
THESAURUS_SRC = Path(__file__).parent.parent.parent / "thesaurus" / "src"


def _create_mesh_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mesh_descriptor (
            descriptor_ui TEXT PRIMARY KEY,
            descriptor_name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mesh_concept (
            concept_ui TEXT PRIMARY KEY,
            descriptor_ui TEXT NOT NULL,
            concept_name TEXT NOT NULL,
            is_preferred INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mesh_term (
            term_ui TEXT PRIMARY KEY,
            concept_ui TEXT NOT NULL,
            term_text TEXT NOT NULL,
            normalized_text TEXT NOT NULL DEFAULT '',
            descriptor_name TEXT NOT NULL DEFAULT '',
            is_preferred INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mesh_descriptor_tree (
            descriptor_ui TEXT NOT NULL,
            tree_number TEXT NOT NULL,
            PRIMARY KEY (descriptor_ui, tree_number)
        );
        CREATE TABLE IF NOT EXISTS mesh_concept_relation (
            source_concept_ui TEXT NOT NULL,
            target_concept_ui TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            PRIMARY KEY (source_concept_ui, target_concept_ui, relation_type)
        );
    """)
    return conn


def _insert_descriptor(conn, dui, name):
    conn.execute(
        "INSERT INTO mesh_descriptor (descriptor_ui, descriptor_name) VALUES (?, ?)",
        (dui, name),
    )


def _insert_concept(conn, cui, dui, name, is_preferred=1):
    conn.execute(
        "INSERT INTO mesh_concept (concept_ui, descriptor_ui, concept_name, is_preferred) "
        "VALUES (?, ?, ?, ?)",
        (cui, dui, name, is_preferred),
    )


def _insert_term(conn, tui, cui, text, is_preferred=1):
    conn.execute(
        "INSERT INTO mesh_term (term_ui, concept_ui, term_text, normalized_text, descriptor_name, is_preferred) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (tui, cui, text, text.lower(), text, is_preferred),
    )


def _insert_tree(conn, dui, tree_number):
    conn.execute(
        "INSERT INTO mesh_descriptor_tree (descriptor_ui, tree_number) VALUES (?, ?)",
        (dui, tree_number),
    )


def _insert_relation(conn, src_cui, tgt_cui, rel_type):
    conn.execute(
        "INSERT INTO mesh_concept_relation (source_concept_ui, target_concept_ui, relation_type) "
        "VALUES (?, ?, ?)",
        (src_cui, tgt_cui, rel_type),
    )


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ─── Phase 3: Unit Tests ─────────────────────────────────────────────────


class TestExportEmptyDB:
    def test_empty_db_zero_byte_jsonl_and_manifest_count_zero(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)
        conn.close()

        result = export_jsonl(str(db_path), str(out_path))

        assert out_path.exists()
        assert out_path.read_bytes() == b""
        assert result["concept_count"] == 0

        manifest_path = tmp_path / "manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert manifest["concept_count"] == 0
        assert manifest["sha256"] == hashlib.sha256(b"").hexdigest()


class TestExportAllFields:
    def test_descriptor_with_all_fields(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)

        _insert_descriptor(conn, "D001", "TestDescriptor")
        _insert_concept(conn, "M001", "D001", "TestConcept", is_preferred=1)
        _insert_concept(conn, "M002", "D001", "AltConcept", is_preferred=0)
        _insert_term(conn, "T001", "M001", "TestDescriptor", is_preferred=1)
        _insert_term(conn, "T002", "M001", "AltTerm1", is_preferred=0)
        _insert_term(conn, "T003", "M002", "AltTerm2", is_preferred=1)

        _insert_descriptor(conn, "D002", "BroaderDesc")
        _insert_concept(conn, "M101", "D002", "BroaderConcept")
        _insert_descriptor(conn, "D003", "NarrowerDesc")
        _insert_concept(conn, "M102", "D003", "NarrowerConcept")
        _insert_descriptor(conn, "D004", "RelatedDesc")
        _insert_concept(conn, "M103", "D004", "RelatedConcept")

        _insert_relation(conn, "M001", "M101", "BRD")
        _insert_relation(conn, "M001", "M102", "NRW")
        _insert_relation(conn, "M001", "M103", "REL")
        _insert_tree(conn, "D001", "A01")

        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out_path))

        records = _read_jsonl(out_path)
        d001 = next(r for r in records if r["id"] == "D001")

        assert d001["preferred_label"] == "TestDescriptor"
        assert d001["alt_labels"] == ["AltTerm1", "AltTerm2"]
        assert d001["broader"] == "D002"
        assert d001["narrower"] == "D003"
        assert d001["related"] == "D004"
        assert d001["notation"] == "A01"
        assert d001["source"] == "mesh"


class TestExportNoRelations:
    def test_no_relations_empty_strings_and_empty_alt_labels(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D010", "NoRelations")
        _insert_concept(conn, "M010", "D010", "NoRelConcept")
        _insert_term(conn, "T010", "M010", "NoRelations")
        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out_path))

        records = _read_jsonl(out_path)
        d010 = records[0]

        assert d010["broader"] == ""
        assert d010["narrower"] == ""
        assert d010["related"] == ""
        assert d010["alt_labels"] == []


class TestSelfReferenceFiltering:
    def test_self_reference_excluded_from_broader(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D020", "SelfRef")
        _insert_concept(conn, "M020", "D020", "SelfRefConcept")
        _insert_term(conn, "T020", "M020", "SelfRef")
        _insert_descriptor(conn, "D021", "Other")
        _insert_concept(conn, "M021", "D021", "OtherConcept")
        _insert_term(conn, "T021", "M021", "Other")
        _insert_relation(conn, "M020", "M020", "BRD")
        _insert_relation(conn, "M020", "M021", "BRD")
        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out_path))

        records = _read_jsonl(out_path)
        d020 = next(r for r in records if r["id"] == "D020")

        assert d020["broader"] == "D021"


class TestMultiValueCollapse:
    def test_multi_broader_sorted_pipe_single_value_no_pipe(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)

        _insert_descriptor(conn, "D030", "MultiBroader")
        _insert_concept(conn, "M030", "D030", "MultiConcept")
        _insert_term(conn, "T030", "M030", "MultiBroader")

        for dui, name, cui in [
            ("D033", "B3", "M033"),
            ("D031", "B1", "M031"),
            ("D032", "B2", "M032"),
        ]:
            _insert_descriptor(conn, dui, name)
            _insert_concept(conn, cui, dui, name)
            _insert_term(conn, f"T{cui}", cui, name)
            _insert_relation(conn, "M030", cui, "BRD")

        _insert_descriptor(conn, "D034", "SingleBroader")
        _insert_concept(conn, "M034", "D034", "SingleConcept")
        _insert_term(conn, "T034", "M034", "SingleBroader")
        _insert_descriptor(conn, "D035", "SingleTarget")
        _insert_concept(conn, "M035", "D035", "SingleTargetConcept")
        _insert_term(conn, "T035", "M035", "SingleTarget")
        _insert_relation(conn, "M034", "M035", "BRD")

        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out_path))

        records = _read_jsonl(out_path)
        d030 = next(r for r in records if r["id"] == "D030")
        d034 = next(r for r in records if r["id"] == "D034")

        assert d030["broader"] == "D031|D032|D033"
        assert d034["broader"] == "D035"
        assert "|" not in d034["broader"]


class TestDeterminism:
    def test_same_db_exported_twice_produces_byte_identical_jsonl(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out1 = tmp_path / "export1.jsonl"
        out2 = tmp_path / "export2.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D001", "Alpha")
        _insert_concept(conn, "M001", "D001", "AlphaConcept")
        _insert_term(conn, "T001", "M001", "Alpha")
        _insert_descriptor(conn, "D002", "Beta")
        _insert_concept(conn, "M002", "D002", "BetaConcept")
        _insert_term(conn, "T002", "M002", "Beta")
        _insert_relation(conn, "M001", "M002", "BRD")
        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out1))
        export_jsonl(str(db_path), str(out2))

        assert out1.read_bytes() == out2.read_bytes()


class TestManifestSHA256:
    def test_manifest_sha256_matches_file_and_count_matches_lines(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D001", "First")
        _insert_concept(conn, "M001", "D001", "FirstConcept")
        _insert_term(conn, "T001", "M001", "First")
        _insert_descriptor(conn, "D002", "Second")
        _insert_concept(conn, "M002", "D002", "SecondConcept")
        _insert_term(conn, "T002", "M002", "Second")
        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(out_path))

        actual_sha256 = hashlib.sha256(out_path.read_bytes()).hexdigest()
        manifest_path = tmp_path / "manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["sha256"] == actual_sha256
        lines = [l for l in out_path.read_text().splitlines() if l.strip()]
        assert manifest["concept_count"] == len(lines)


# ─── Phase 4: Integration Tests ──────────────────────────────────────────


class TestCLISubprocess:
    def test_cli_success_exit0_files_exist(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        out_path = tmp_path / "output.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D001", "Test")
        _insert_concept(conn, "M001", "D001", "TestConcept")
        _insert_term(conn, "T001", "M001", "Test")
        conn.commit()
        conn.close()

        result = export_jsonl(str(db_path), str(out_path))

        assert result["concept_count"] == 1
        assert out_path.exists()
        assert (tmp_path / "manifest.json").exists()

    def test_cli_nonexistent_db_raises_error(self, tmp_path):
        out_path = tmp_path / "output.jsonl"

        with pytest.raises(FileNotFoundError):
            export_jsonl("/nonexistent/path/mesh.db", str(out_path))


class TestRoundTrip:
    def test_export_then_thesaurus_load_and_search(self, tmp_path):
        db_path = tmp_path / "mesh.db"
        jsonl_path = tmp_path / "export.jsonl"

        conn = _create_mesh_db(db_path)
        _insert_descriptor(conn, "D000002", "Aspirin")
        _insert_concept(conn, "M000002", "D000002", "Aspirin", is_preferred=1)
        _insert_term(conn, "T000001", "M000002", "Aspirin", is_preferred=1)
        _insert_term(conn, "T000002", "M000002", "Acetylsalicylic Acid", is_preferred=0)
        conn.commit()
        conn.close()

        export_jsonl(str(db_path), str(jsonl_path))

        sys.path.insert(0, str(THESAURUS_SRC))
        from thesaurus.mesh_loader import load_jsonl

        concepts = load_jsonl(jsonl_path)
        assert len(concepts) == 1
        assert concepts[0]["id"] == "D000002"

        from thesaurus.lite import LiteSemanticStore

        store = LiteSemanticStore(str(tmp_path / "thesaurus.db"))
        store.import_concepts(concepts)

        results = store.search("Aspirin")
        assert len(results) >= 1
        assert results[0]["id"] == "D000002"
        assert results[0]["preferred_label"] == "Aspirin"
