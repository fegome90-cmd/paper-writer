import argparse
import json

import pytest
from mesh_import.cli import _cmd_expand, _cmd_import, _cmd_resolve


def _import_args(xml_path, db_path):
    return argparse.Namespace(
        xml_path=xml_path, dtd_path=None, db_path=db_path, progress_interval=5000
    )


def test_cmd_import_success(sample_xml_path, tmp_path, capsys):
    db_path = str(tmp_path / "mesh.db")
    _cmd_import(_import_args(sample_xml_path, db_path))
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["descriptors"] == 2
    assert result["concepts"] == 3
    assert result["terms"] == 4
    assert "elapsed" in result
    assert "sha256" in result
    assert len(result["sha256"]) == 64


def test_cmd_import_file_not_found(tmp_path, capsys):
    db_path = str(tmp_path / "mesh.db")
    with pytest.raises(SystemExit) as exc_info:
        _cmd_import(_import_args("/nonexistent/path.xml", db_path))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    err = json.loads(captured.err)
    assert "error" in err
    assert err["phase"] == "xml_parse"


def test_cmd_resolve_returns_json(populated_db, capsys):
    capsys.readouterr()
    args = argparse.Namespace(term="Aspirin", db_path=populated_db)
    _cmd_resolve(args)
    captured = capsys.readouterr()
    results = json.loads(captured.out)
    assert isinstance(results, list)
    assert len(results) >= 1
    entry = results[0]
    assert entry["descriptor_ui"] == "D000002"
    assert entry["descriptor_name"] == "Aspirin"
    assert "match_type" in entry
    assert "tree_numbers" in entry


def test_cmd_expand_returns_json(populated_db, capsys):
    capsys.readouterr()
    args = argparse.Namespace(descriptor_ui="D000001", db_path=populated_db)
    _cmd_expand(args)
    captured = capsys.readouterr()
    results = json.loads(captured.out)
    assert isinstance(results, list)
    assert len(results) >= 2

    entry = results[0]
    assert entry["tree_number"] == "A01"
    assert entry["descriptor_ui"] == "D000001"
    assert entry["descriptor_name"] == "Café"
    assert entry["depth"] == 0

    depth_1 = [r for r in results if r["depth"] == 1]
    assert len(depth_1) >= 1
    assert any(r["tree_number"] == "A01.123" for r in depth_1)


def test_cmd_import_checksum_mismatch(sample_xml_path, tmp_path, capsys):
    db_path = str(tmp_path / "mesh.db")
    _cmd_import(_import_args(sample_xml_path, db_path))
    capsys.readouterr()

    tampered = tmp_path / "tampered.xml"
    tampered.write_text(
        '<?xml version="1.0"?>'
        "<DescriptorRecordSet>"
        "<DescriptorRecord>"
        "<DescriptorUI>D999</DescriptorUI>"
        "<DescriptorName><String>X</String></DescriptorName>"
        "<ConceptList>"
        '<Concept PreferredConcept="Y">'
        "<ConceptUI>M999</ConceptUI>"
        "<ConceptName><String>X</String></ConceptName>"
        "<TermList>"
        '<Term TermPreferred="Y">'
        "<TermUI>T999</TermUI>"
        "<String>X</String>"
        "</Term>"
        "</TermList>"
        "</Concept>"
        "</ConceptList>"
        "</DescriptorRecord>"
        "</DescriptorRecordSet>"
    )

    with pytest.raises(SystemExit) as exc_info:
        _cmd_import(_import_args(str(tampered), db_path))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    err = json.loads(captured.err)
    assert "error" in err
    assert err["phase"] == "xml_parse"


def test_fts5_query_sanitization(populated_db, capsys):
    capsys.readouterr()
    args_bool = argparse.Namespace(term="Aspirin OR coffee", db_path=populated_db)
    _cmd_resolve(args_bool)
    captured = capsys.readouterr()
    results_bool = json.loads(captured.out)
    assert results_bool == []

    capsys.readouterr()
    args_exact = argparse.Namespace(term="Aspirin", db_path=populated_db)
    _cmd_resolve(args_exact)
    captured2 = capsys.readouterr()
    results_exact = json.loads(captured2.out)
    assert len(results_exact) >= 1
    assert results_exact[0]["descriptor_ui"] == "D000002"
