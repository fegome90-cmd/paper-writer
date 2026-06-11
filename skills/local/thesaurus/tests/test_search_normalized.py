import typing

from thesaurus.lite import LiteSemanticStore


def test_search_normalized_synonym(tmp_path: typing.Any) -> None:
    store = LiteSemanticStore(db_path=str(tmp_path / "test.db"))
    store.import_concepts(
        [
            {
                "id": "C1",
                "preferred_label": "Automobile",
                "alt_labels": ["Car", "Vehicle"],
                "notation": "A.01",
            }
        ]
    )

    # Search for synonym
    results = store.search("Car")
    assert len(results) == 1
    assert results[0]["id"] == "C1"
    assert results[0]["match_type"] == "synonym"

    # Search for preferred label
    results2 = store.search("Automobile")
    assert len(results2) == 1
    assert results2[0]["id"] == "C1"
    assert results2[0]["match_type"] == "preferred_label"
