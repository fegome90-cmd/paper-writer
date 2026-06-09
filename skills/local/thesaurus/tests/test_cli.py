"""Integration tests for CLI entry points."""

import json
import os
from types import SimpleNamespace

import pytest


def test_cmd_import_success(tmp_path, sample_concepts):
    """_cmd_import loads concepts from valid JSONL."""
    from thesaurus.cli import _cmd_import

    jsonl_path = tmp_path / "concepts.jsonl"
    lines = []
    for c in sample_concepts:
        record = dict(c)
        record["alt_labels"] = json.loads(c["alt_labels"])
        lines.append(json.dumps(record))
    jsonl_path.write_text("\n".join(lines), encoding="utf-8")

    # Create manifest
    import hashlib
    content = jsonl_path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    manifest = {
        "source_file": "concepts.jsonl",
        "sha256": sha,
        "concept_count": len(lines),
        "schema_version": "1",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_path / "thesaurus.db")
    try:
        args = SimpleNamespace(file=str(jsonl_path))
        _cmd_import(args)
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_import_file_not_found(capsys):
    """_cmd_import exits with error for missing file."""
    from thesaurus.cli import _cmd_import

    args = SimpleNamespace(file="/nonexistent/file.jsonl")
    with pytest.raises(SystemExit) as exc_info:
        _cmd_import(args)
    assert exc_info.value.code == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_cmd_search(tmp_thesaurus, sample_concepts):
    """_cmd_search returns results for matching query."""
    from thesaurus.cli import _cmd_search

    tmp_thesaurus.import_concepts(sample_concepts)
    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace(query="Asthma", limit=10)
        _cmd_search(args)
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_search_no_results(tmp_thesaurus, capsys):
    """_cmd_search prints 'No concepts found' for empty results."""
    from thesaurus.cli import _cmd_search

    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace(query="nonexistent_xyz", limit=10)
        _cmd_search(args)
        output = capsys.readouterr().out
        assert "No concepts found" in output
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_list(tmp_thesaurus, sample_concepts):
    """_cmd_list prints concepts."""
    from thesaurus.cli import _cmd_list

    tmp_thesaurus.import_concepts(sample_concepts)
    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace(offset=0, limit=10)
        _cmd_list(args)
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_list_empty(tmp_thesaurus, capsys):
    """_cmd_list prints 'No concepts found' when empty."""
    from thesaurus.cli import _cmd_list

    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace(offset=0, limit=10)
        _cmd_list(args)
        output = capsys.readouterr().out
        assert "No concepts found" in output
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_audit(tmp_thesaurus, sample_concepts):
    """_cmd_audit prints audit info."""
    from thesaurus.cli import _cmd_audit

    tmp_thesaurus.import_concepts(sample_concepts)
    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace()
        _cmd_audit(args)
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db


def test_cmd_rebuild(tmp_thesaurus, sample_concepts):
    """_cmd_rebuild recreates the database."""
    from thesaurus.cli import _cmd_rebuild

    tmp_thesaurus.import_concepts(sample_concepts)
    assert tmp_thesaurus.concept_count == 3

    old_db = os.environ.get("PAPER_THESAURUS_DB")
    os.environ["PAPER_THESAURUS_DB"] = str(tmp_thesaurus._db_path)
    try:
        args = SimpleNamespace()
        _cmd_rebuild(args)
        # After rebuild with no manifest in tmp dir, should be empty
        assert tmp_thesaurus.concept_count == 0
    finally:
        if old_db is None:
            os.environ.pop("PAPER_THESAURUS_DB", None)
        else:
            os.environ["PAPER_THESAURUS_DB"] = old_db
