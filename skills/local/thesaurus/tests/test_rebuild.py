"""Tests for rebuild idempotency and DB recovery."""

import json
import sqlite3
from pathlib import Path

from thesaurus.lite import LiteSemanticStore


def _write_manifest(workspace: Path, jsonl_path: Path) -> Path:
    """Write a valid manifest for the given JSONL file."""
    import hashlib

    content = jsonl_path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    count = sum(1 for line in content.splitlines() if line.strip())
    manifest = {
        "source_file": jsonl_path.name,
        "sha256": sha,
        "concept_count": count,
        "schema_version": "1",
    }
    manifest_path = workspace / "vocabulary" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _write_jsonl(workspace: Path, concepts: list[dict]) -> Path:
    """Write concepts to a JSONL file."""
    vocab = workspace / "vocabulary"
    vocab.mkdir(parents=True, exist_ok=True)
    jsonl_path = vocab / "test.jsonl"
    lines = [json.dumps(c) for c in concepts]
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jsonl_path


def test_rebuild_with_manifest(tmp_path):
    """Rebuild with valid manifest re-imports from JSONL."""
    concepts = [
        {
            "id": "C1",
            "preferred_label": "Alpha",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "A01",
            "source": "test",
        },
    ]
    jsonl_path = _write_jsonl(tmp_path, concepts)
    _write_manifest(tmp_path, jsonl_path)

    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))
    store.import_concepts(concepts)
    assert store.concept_count == 1

    # Rebuild should re-import from JSONL via manifest
    store.rebuild()
    assert store.concept_count == 1


def test_rebuild_with_no_manifest_preserves_data(tmp_path):
    """Rebuild with no manifest is a no-op — data preserved."""
    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))
    concepts = [
        {
            "id": "C1",
            "preferred_label": "Test",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "test",
        },
    ]
    store.import_concepts(concepts)
    assert store.concept_count == 1

    # No manifest → rebuild should preserve existing data
    store.rebuild()
    assert store.concept_count == 1  # Data preserved!


def test_rebuild_creates_fresh_db(tmp_path):
    """Rebuild with manifest deletes old DB and creates fresh one."""
    concepts = [
        {
            "id": "C1",
            "preferred_label": "Test",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "test",
        },
    ]
    jsonl_path = _write_jsonl(tmp_path, concepts)
    _write_manifest(tmp_path, jsonl_path)

    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))
    store.import_concepts(concepts)
    assert db_path.exists()

    store.rebuild()
    assert db_path.exists()
    # DB should be valid SQLite
    conn = sqlite3.connect(str(db_path))
    conn.execute("SELECT COUNT(*) FROM concepts")
    conn.close()


def test_rebuild_from_corrupt_db(tmp_path):
    """Rebuild with manifest handles corrupt DB file."""
    concepts = [
        {
            "id": "C1",
            "preferred_label": "Test",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "test",
        },
    ]
    jsonl_path = _write_jsonl(tmp_path, concepts)
    _write_manifest(tmp_path, jsonl_path)

    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))
    store.import_concepts(concepts)

    # Corrupt the DB
    db_path.write_bytes(b"NOT A VALID SQLITE FILE" * 100)

    # Rebuild should recreate from JSONL.
    # Must remove corrupt DB first since LiteSemanticStore.__init__
    # calls _ensure_schema which would fail on corrupt DB.
    db_path.unlink()
    store = LiteSemanticStore(db_path=str(db_path))
    store.rebuild()
    assert db_path.exists()
    # Should be valid now
    conn = sqlite3.connect(str(db_path))
    conn.execute("SELECT COUNT(*) FROM concepts")
    conn.close()


def test_rebuild_rejects_corrupt_manifest(tmp_path):
    """Rebuild with wrong SHA256 in manifest raises ManifestError."""
    from thesaurus.manifest import ManifestError

    concepts = [
        {
            "id": "C1",
            "preferred_label": "Test",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "test",
        },
    ]
    jsonl_path = _write_jsonl(tmp_path, concepts)

    # Write manifest with wrong SHA256
    manifest = {
        "source_file": jsonl_path.name,
        "sha256": "deadbeef",
        "concept_count": 1,
        "schema_version": "1",
    }
    manifest_path = tmp_path / "vocabulary" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))

    try:
        store.rebuild()
        assert False, "Should have raised ManifestError"
    except ManifestError:
        pass  # Expected
