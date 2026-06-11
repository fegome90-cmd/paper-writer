"""Tests for audit output."""

import typing


def test_audit_after_import(tmp_thesaurus: typing.Any, sample_concepts: typing.Any) -> None:
    """Audit shows correct info after import."""
    tmp_thesaurus.import_concepts(sample_concepts)
    info = tmp_thesaurus.audit()

    assert info["concept_count"] == len(sample_concepts)
    assert info["profile"] == "lite"
    assert info["last_import"] != ""
    assert info["last_import"] != "Never"


def test_audit_no_imports(tmp_thesaurus: typing.Any) -> None:
    """Audit shows 'Never' for last_import when no imports done."""
    info = tmp_thesaurus.audit()
    assert info["concept_count"] == 0
    assert info["last_import"] == "Never"
    assert info["profile"] == "lite"
