"""Tests for FTS5 search and match_type behavior."""

import json


def test_search_preferred_label(tmp_thesaurus, sample_concepts):
    """Search matches preferred_label."""
    tmp_thesaurus.import_concepts(sample_concepts)
    results = tmp_thesaurus.search("Asthma")
    assert len(results) > 0
    assert any(r["preferred_label"] == "Asthma" for r in results)


def test_search_alt_labels_as_synonym(tmp_thesaurus, sample_concepts):
    """Search matches alt_labels with match_type='synonym'."""
    tmp_thesaurus.import_concepts(sample_concepts)
    results = tmp_thesaurus.search("Bronchial Asthma")
    # Should find Asthma concept via alt_labels match
    asthm_results = [r for r in results if r["id"] == "C001"]
    assert len(asthm_results) > 0
    assert asthm_results[0]["match_type"] == "synonym"


def test_search_no_results(tmp_thesaurus, sample_concepts):
    """Search returns empty list for unmatched query."""
    tmp_thesaurus.import_concepts(sample_concepts)
    results = tmp_thesaurus.search("xyznonexistent")
    assert results == []


def test_search_match_type_priority(tmp_thesaurus):
    """When concept matches both preferred_label and alt_labels, preferred wins."""
    concepts = [
        {
            "id": "C100",
            "preferred_label": "Diabetes",
            "alt_labels": json.dumps(["Diabetes Mellitus", "Sugar Diabetes"]),
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "M01",
            "source": "synthetic",
        },
    ]
    tmp_thesaurus.import_concepts(concepts)
    results = tmp_thesaurus.search("Diabetes")
    assert len(results) > 0
    # Should match preferred_label, not synonym
    assert results[0]["match_type"] == "preferred_label"


def test_search_limit(tmp_thesaurus):
    """Search respects limit parameter."""
    concepts = [
        {
            "id": f"C{i:03d}",
            "preferred_label": f"Concept {i}",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": f"X{i:02d}",
            "source": "synthetic",
        }
        for i in range(30)
    ]
    tmp_thesaurus.import_concepts(concepts)
    results = tmp_thesaurus.search("Concept", limit=5)
    assert len(results) <= 5
