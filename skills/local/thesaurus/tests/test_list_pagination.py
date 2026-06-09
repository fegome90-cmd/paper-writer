"""Tests for list pagination and empty store."""

import json


def test_list_pagination(tmp_thesaurus):
    """List returns ≤limit per page, offset works."""
    concepts = [
        {
            "id": f"C{i:03d}",
            "preferred_label": f"Concept {i:03d}",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": f"X{i:02d}",
            "source": "synthetic",
        }
        for i in range(75)
    ]
    tmp_thesaurus.import_concepts(concepts)

    page1 = tmp_thesaurus.list_concepts(offset=0, limit=50)
    assert len(page1) == 50

    page2 = tmp_thesaurus.list_concepts(offset=50, limit=50)
    assert len(page2) == 25

    # No overlap
    ids1 = {r["id"] for r in page1}
    ids2 = {r["id"] for r in page2}
    assert ids1.isdisjoint(ids2)


def test_list_empty_store(tmp_thesaurus):
    """List on empty store returns empty list."""
    results = tmp_thesaurus.list_concepts()
    assert results == []


def test_list_default_limit(tmp_thesaurus):
    """List default limit is 50."""
    concepts = [
        {
            "id": f"C{i:03d}",
            "preferred_label": f"Concept {i}",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "",
            "source": "synthetic",
        }
        for i in range(60)
    ]
    tmp_thesaurus.import_concepts(concepts)
    results = tmp_thesaurus.list_concepts()
    assert len(results) == 50
