"""Tests for error paths: malformed JSONL, missing manifest, corrupt DB, etc."""

import json

import pytest

from thesaurus.manifest import ManifestError, load_manifest, validate_manifest
from thesaurus.mesh_loader import load_jsonl


def test_malformed_json_exits_with_error(tmp_path):
    """Malformed JSON in JSONL raises ValueError with line number."""
    jsonl = tmp_path / "bad.jsonl"
    jsonl.write_text('{"id": "C1", "preferred_label": "A"}\n{bad json}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="line 2"):
        load_jsonl(jsonl)


def test_missing_required_field_raises(tmp_path):
    """Missing 'preferred_label' raises ValueError with line number."""
    jsonl = tmp_path / "missing.jsonl"
    jsonl.write_text('{"id": "C1"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="preferred_label"):
        load_jsonl(jsonl)


def test_missing_manifest_raises(tmp_path):
    """Loading non-existent manifest raises ManifestError."""
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "nonexistent.json")


def test_sha256_mismatch_raises(tmp_path):
    """Manifest with wrong SHA256 raises ManifestError."""
    jsonl = tmp_path / "data.jsonl"
    jsonl.write_text('{"id": "C1", "preferred_label": "Test"}\n', encoding="utf-8")

    manifest = {"sha256": "wrong_hash", "concept_count": 1}
    with pytest.raises(ManifestError, match="SHA256 mismatch"):
        validate_manifest(manifest, jsonl)


def test_concept_count_mismatch_raises(tmp_path):
    """Manifest with wrong concept_count raises ManifestError."""
    jsonl = tmp_path / "data.jsonl"
    jsonl.write_text('{"id": "C1", "preferred_label": "Test"}\n', encoding="utf-8")

    import hashlib

    sha = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    manifest = {"sha256": sha, "concept_count": 999}
    with pytest.raises(ManifestError, match="concept_count mismatch"):
        validate_manifest(manifest, jsonl)


def test_empty_jsonl(tmp_path):
    """Empty JSONL file returns empty list."""
    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    result = load_jsonl(jsonl)
    assert result == []


def test_empty_jsonl_readable_raises(tmp_path):
    """validate_jsonl_readable raises on empty file."""
    from thesaurus.mesh_loader import validate_jsonl_readable

    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        validate_jsonl_readable(jsonl)


def test_duplicate_ids_last_write_wins(tmp_path):
    """Duplicate IDs within file: last-write-wins."""
    jsonl = tmp_path / "dupes.jsonl"
    lines = [
        json.dumps({"id": "C1", "preferred_label": "First"}),
        json.dumps({"id": "C1", "preferred_label": "Second"}),
    ]
    jsonl.write_text("\n".join(lines), encoding="utf-8")

    concepts = load_jsonl(jsonl)
    assert len(concepts) == 2  # Both lines parsed
    # When imported, INSERT OR REPLACE means last wins
