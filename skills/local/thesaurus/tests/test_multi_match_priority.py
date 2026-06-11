"""Tests for match_type priority when multiple fields match."""

import typing


def test_preferred_label_wins_over_notation(tmp_thesaurus: typing.Any) -> None:
    """When query matches both preferred_label and notation, preferred_label wins."""
    concepts = [
        {
            "id": "C1",
            "preferred_label": "Aspirin",
            "alt_labels": "[]",
            "broader": "",
            "narrower": "",
            "related": "",
            "notation": "Aspirin",  # Same as preferred_label
            "source": "synthetic",
        },
    ]
    tmp_thesaurus.import_concepts(concepts)
    results = tmp_thesaurus.search("Aspirin")
    assert len(results) > 0
    assert results[0]["match_type"] == "preferred_label"
