import hashlib
import json
import typing
from unittest.mock import patch

import pytest
from thesaurus.errors import RebuildError
from thesaurus.lite import LiteSemanticStore


def test_rebuild_atomic_failure_preserves_live_db(tmp_path: typing.Any) -> None:
    db_path = tmp_path / "thesaurus.db"
    store = LiteSemanticStore(db_path=str(db_path))

    # Seed live DB
    store.import_concepts([{"id": "LIVE1", "preferred_label": "Live Concept"}])
    assert store.concept_count == 1

    # Setup files for rebuild
    vocab_dir = tmp_path / "vocabulary"
    vocab_dir.mkdir(parents=True)
    jsonl_path = vocab_dir / "test.jsonl"
    jsonl_path.write_text(json.dumps({"id": "NEW1", "preferred_label": "New Concept"}) + "\n")

    sha = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    manifest_path = vocab_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_file": "test.jsonl",
                "sha256": sha,
                "concept_count": 1,
                "schema_version": "1",
            }
        )
    )

    # Mock import_concepts to fail during rebuild
    with patch.object(
        LiteSemanticStore, "import_concepts", side_effect=Exception("Simulated failure")
    ):
        with pytest.raises(RebuildError, match="Atomic rebuild failed"):
            store.rebuild()

    # Verify staging DB is cleaned up
    staging_path = tmp_path / "thesaurus.staging.db"
    assert not staging_path.exists(), "Staging DB should be deleted on failure"

    # Verify live DB is intact and not replaced
    assert store.concept_count == 1
    results = store.search("Live")
    assert len(results) == 1
    assert results[0]["id"] == "LIVE1"
