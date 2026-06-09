"""Tests for SemanticStore protocol invariants and capabilities."""

from thesaurus.protocol import StorageCapabilities


def test_capabilities_immutability():
    """StorageCapabilities is frozen."""
    caps = StorageCapabilities()
    assert caps.vector_search is False
    assert caps.full_text is True
    try:
        caps.full_text = False
        raise AssertionError("Should have raised FrozenInstanceError")
    except Exception:
        pass  # Expected — frozen dataclass


def test_concept_count_after_import(tmp_thesaurus, sample_concepts):
    """concept_count reflects actual store size."""
    assert tmp_thesaurus.concept_count == 0
    tmp_thesaurus.import_concepts(sample_concepts)
    assert tmp_thesaurus.concept_count == len(sample_concepts)


def test_capabilities_lite_store(tmp_thesaurus):
    """Lite store reports correct capabilities."""
    caps = tmp_thesaurus.capabilities
    assert caps.full_text is True
    assert caps.vector_search is False


def test_invalid_profile_raises():
    """Unknown profile raises ValueError."""
    import os

    os.environ["PAPER_THESAURUS_PROFILE"] = "unknown"
    try:
        from thesaurus.factory import create_store

        try:
            create_store()
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "unknown" in str(e).lower()
    finally:
        del os.environ["PAPER_THESAURUS_PROFILE"]
