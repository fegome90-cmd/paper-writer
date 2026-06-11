"""H-B01: Rebuild does not revalidate manifest — hypothesis test.

Hypothesis: `paper thesaurus rebuild` re-reads JSONL without verifying
checksum or concept_count.

VERDICT: REFUTATED. Rebuild validates manifest (SHA256 + concept_count)
BEFORE deleting the DB, at lite.py:291. These tests confirm that behavior.
"""

import hashlib
import json
import typing
from pathlib import Path

import pytest

from thesaurus.lite import LiteSemanticStore
from thesaurus.manifest import ManifestError


def _make_concept(i: int) -> dict[str, typing.Any]:
    return {
        "id": f"TEST{i:04d}",
        "preferred_label": f"Test Concept {i}",
        "alt_labels": [f"TC{i}"],
        "broader": "",
        "narrower": "",
        "related": "",
        "notation": f"TEST.{i}",
        "source": "test",
    }


def _write_jsonl(path: Path, concepts: list[dict[str, typing.Any]]) -> bytes:
    lines = [json.dumps(c, ensure_ascii=False) for c in concepts]
    content = "\n".join(lines).encode("utf-8")
    path.write_bytes(content)
    return content


def _write_manifest(
    manifest_path: Path,
    source_file: str,
    jsonl_content: bytes,
    concept_count: int,
) -> None:
    sha = hashlib.sha256(jsonl_content).hexdigest()
    manifest = {
        "source_file": source_file,
        "sha256": sha,
        "concept_count": concept_count,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _setup_workspace(workspace: Path, num_concepts: int = 3) -> Path:
    vocab_dir = workspace / "vocabulary"
    vocab_dir.mkdir(parents=True, exist_ok=True)

    concepts = [_make_concept(i) for i in range(num_concepts)]
    jsonl_path = vocab_dir / "test.jsonl"
    content = _write_jsonl(jsonl_path, concepts)

    manifest_path = vocab_dir / "manifest.json"
    _write_manifest(manifest_path, "test.jsonl", content, num_concepts)

    db_path = workspace / "thesaurus.db"
    return db_path


class TestRebuildValidatesManifestBeforeProceeding:
    """Rebuild succeeds when manifest is valid."""

    def test_rebuild_succeeds_with_valid_manifest(self, tmp_path: typing.Any) -> None:
        db_path = _setup_workspace(tmp_path, num_concepts=3)
        store = LiteSemanticStore(db_path=str(db_path))

        store.rebuild()
        assert store.concept_count == 3


class TestRebuildDetectsTamperedJSONL:
    """Rebuild rejects JSONL whose checksum doesn't match manifest."""

    def test_tampered_jsonl_raises_manifest_error(self, tmp_path: typing.Any) -> None:
        db_path = _setup_workspace(tmp_path, num_concepts=3)

        jsonl_path = tmp_path / "vocabulary" / "test.jsonl"
        content = bytearray(jsonl_path.read_bytes())
        content[0] ^= 0xFF
        jsonl_path.write_bytes(bytes(content))

        store = LiteSemanticStore(db_path=str(db_path))

        with pytest.raises(ManifestError, match="SHA256 mismatch"):
            store.rebuild()


class TestRebuildDetectsWrongConceptCount:
    """Rebuild rejects manifest with incorrect concept_count."""

    def test_wrong_concept_count_raises_manifest_error(self, tmp_path: typing.Any) -> None:
        vocab_dir = tmp_path / "vocabulary"
        vocab_dir.mkdir(parents=True, exist_ok=True)

        concepts = [_make_concept(i) for i in range(3)]
        jsonl_path = vocab_dir / "test.jsonl"
        content = _write_jsonl(jsonl_path, concepts)

        manifest_path = vocab_dir / "manifest.json"
        _write_manifest(manifest_path, "test.jsonl", content, concept_count=999)

        db_path = tmp_path / "thesaurus.db"
        store = LiteSemanticStore(db_path=str(db_path))

        with pytest.raises(ManifestError, match="concept_count mismatch"):
            store.rebuild()


class TestRebuildPreservesDBOnTamper:
    """Rebuild does NOT replace DB when JSONL is tampered."""

    def test_original_db_preserved_after_tamper(self, tmp_path: typing.Any) -> None:
        db_path = _setup_workspace(tmp_path, num_concepts=3)
        store = LiteSemanticStore(db_path=str(db_path))

        original_concepts = [_make_concept(i) for i in range(3)]
        store.import_concepts(original_concepts)
        extra_concept = _make_concept(100)
        store.import_concepts([extra_concept])
        count_before = store.concept_count
        assert count_before == 4

        jsonl_path = tmp_path / "vocabulary" / "test.jsonl"
        content = bytearray(jsonl_path.read_bytes())
        content[0] ^= 0xFF
        jsonl_path.write_bytes(bytes(content))

        with pytest.raises(ManifestError, match="SHA256 mismatch"):
            store.rebuild()

        assert store.concept_count == count_before, "DB must be unchanged after failed rebuild"
