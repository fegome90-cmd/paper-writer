"""Tests for JSONL format validation."""

import json

import pytest

from thesaurus.mesh_loader import load_jsonl


def test_missing_required_field_skipped_with_error(tmp_path):
    """Missing 'id' field raises ValueError."""
    jsonl = tmp_path / "no_id.jsonl"
    jsonl.write_text(json.dumps({"preferred_label": "Test"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="id"):
        load_jsonl(jsonl)


def test_empty_file(tmp_path):
    """Empty JSONL file returns empty list."""
    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    assert load_jsonl(jsonl) == []


def test_blank_lines_skipped(tmp_path):
    """Blank lines in JSONL are skipped."""
    jsonl = tmp_path / "blanks.jsonl"
    lines = [
        '{"id": "C1", "preferred_label": "A"}',
        "",
        "",
        '{"id": "C2", "preferred_label": "B"}',
    ]
    jsonl.write_text("\n".join(lines), encoding="utf-8")
    concepts = load_jsonl(jsonl)
    assert len(concepts) == 2
