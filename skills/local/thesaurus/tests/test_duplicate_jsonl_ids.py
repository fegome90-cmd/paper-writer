"""Tests for duplicate IDs within single JSONL file."""

import json

from thesaurus.mesh_loader import load_jsonl


def test_duplicate_ids_parsed_both_lines(tmp_path):
    """Both lines with duplicate IDs are parsed (INSERT OR REPLACE handles at DB level)."""
    jsonl = tmp_path / "dupes.jsonl"
    lines = [
        json.dumps({"id": "C1", "preferred_label": "First"}),
        json.dumps({"id": "C1", "preferred_label": "Second"}),
    ]
    jsonl.write_text("\n".join(lines), encoding="utf-8")

    concepts = load_jsonl(jsonl)
    assert len(concepts) == 2  # Both parsed
    # Last one wins on import
    assert concepts[-1]["preferred_label"] == "Second"


def test_duplicate_ids_last_write_wins_on_import(tmp_thesaurus):
    """Import with duplicate IDs: last-write-wins via INSERT OR REPLACE."""
    concepts1 = [
        {
            "id": "C1",
            "preferred_label": "First",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "synthetic",
        },
    ]
    concepts2 = [
        {
            "id": "C1",
            "preferred_label": "Second",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "synthetic",
        },
    ]

    tmp_thesaurus.import_concepts(concepts1)
    tmp_thesaurus.import_concepts(concepts2)

    assert tmp_thesaurus.concept_count == 1
    results = tmp_thesaurus.list_concepts()
    assert results[0]["preferred_label"] == "Second"
