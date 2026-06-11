"""Shared fixtures for thesaurus tests."""

import json
import typing

import pytest


@pytest.fixture
def tmp_thesaurus(tmp_path: typing.Any) -> typing.Any:
    """Create a temporary thesaurus store with sample data."""
    db_path = tmp_path / "thesaurus.db"
    from thesaurus.lite import LiteSemanticStore

    store = LiteSemanticStore(db_path=str(db_path))
    return store


@pytest.fixture
def sample_concepts() -> typing.Any:
    """Return a list of sample concept dicts."""
    return [
        {
            "id": "C001",
            "preferred_label": "Asthma",
            "alt_labels": json.dumps(["Bronchial Asthma"]),
            "broader": "",
            "narrower": "C002",
            "related": "C003",
            "notation": "A01",
            "source": "synthetic",
        },
        {
            "id": "C002",
            "preferred_label": "Asthma in Children",
            "alt_labels": json.dumps(["Pediatric Asthma"]),
            "broader": "C001",
            "narrower": "",
            "related": "",
            "notation": "A02",
            "source": "synthetic",
        },
        {
            "id": "C003",
            "preferred_label": "Bronchitis",
            "alt_labels": json.dumps(["Bronchial Inflammation"]),
            "broader": "",
            "narrower": "",
            "related": "C001",
            "notation": "A03",
            "source": "synthetic",
        },
    ]


@pytest.fixture
def sample_jsonl(tmp_path: typing.Any, sample_concepts: typing.Any) -> typing.Any:
    """Write sample concepts to a JSONL file and return the path."""
    jsonl_path = tmp_path / "sample.jsonl"
    lines = []
    for c in sample_concepts:
        # Convert alt_labels back to list for JSONL format
        record = dict(c)
        record["alt_labels"] = json.loads(c["alt_labels"])
        lines.append(json.dumps(record))
    jsonl_path.write_text("\n".join(lines), encoding="utf-8")
    return jsonl_path


@pytest.fixture
def sample_manifest(tmp_path: typing.Any, sample_jsonl: typing.Any) -> typing.Any:
    """Create a valid manifest.json for the sample JSONL."""
    import hashlib

    content = sample_jsonl.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    lines = sample_jsonl.read_text().strip().split("\n")

    manifest = {
        "source_file": sample_jsonl.name,
        "sha256": sha,
        "concept_count": len(lines),
        "schema_version": "1",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
