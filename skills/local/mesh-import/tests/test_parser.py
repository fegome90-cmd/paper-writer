import hashlib
from pathlib import Path

import pytest
from lxml import etree
from mesh_import.parser import parse_descriptor_xml

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parse_result(sample_xml_path):
    return parse_descriptor_xml(sample_xml_path)


@pytest.fixture
def malformed_xml_path():
    return str(FIXTURES / "malformed_desc.xml")


def test_parse_counts(parse_result):
    assert len(parse_result.descriptors) == 2
    assert len(parse_result.concepts) == 3
    assert len(parse_result.terms) == 4
    assert len(parse_result.relations) > 0


def test_sha256_matches_file(parse_result, sample_xml_path):
    with open(sample_xml_path, "rb") as f:
        expected = hashlib.sha256(f.read()).hexdigest()
    assert parse_result.sha256_hex == expected


def test_descriptor_data(parse_result):
    cafe = next(d for d in parse_result.descriptors if d.descriptor_ui == "D000001")
    assert cafe.descriptor_name == "Café"
    assert cafe.annotation == "A brewed beverage annotation"
    assert cafe.registry_number == "0"
    assert cafe.scope_note is not None
    assert "A01" in cafe.tree_numbers_json
    assert "A01.123" in cafe.tree_numbers_json

    aspirin = next(d for d in parse_result.descriptors if d.descriptor_ui == "D000002")
    assert aspirin.descriptor_name == "Aspirin"
    assert aspirin.registry_number == "R16CO5Y76E"
    assert "D000001" in aspirin.pharmacological_action_json


def test_tree_nodes(parse_result):
    tn_map = {tn.tree_number: tn for tn in parse_result.tree_nodes}
    assert "A01" in tn_map
    assert tn_map["A01"].parent_tree_number is None
    assert "A01.123" in tn_map
    assert tn_map["A01.123"].parent_tree_number == "A01"
    assert "D02.123" in tn_map
    assert tn_map["D02.123"].parent_tree_number == "D02"


def test_concept_relations(parse_result):
    brd = [
        r for r in parse_result.relations
        if r.source_concept_ui == "M0000001" and r.relation_type == "BRD"
    ]
    assert len(brd) == 1
    assert brd[0].target_concept_ui == "M0000002"

    nrw = [
        r for r in parse_result.relations
        if r.source_concept_ui == "M0000002" and r.relation_type == "NRW"
    ]
    assert len(nrw) == 1
    assert nrw[0].target_concept_ui == "M0000001"


def test_term_normalized_text(parse_result):
    cafe_term = next(t for t in parse_result.terms if t.term_ui == "T000001")
    assert cafe_term.term_text == "Café"
    assert cafe_term.normalized_text == "cafe"


def test_concept_preferred_flag(parse_result):
    pref = [c for c in parse_result.concepts if c.is_preferred]
    assert len(pref) == 2
    pref_uis = {c.concept_ui for c in pref}
    assert "M0000001" in pref_uis
    assert "M0000003" in pref_uis


def test_malformed_xml_raises_parse_error(malformed_xml_path):
    with pytest.raises(etree.XMLSyntaxError) as exc_info:
        etree.parse(malformed_xml_path)
    error_msg = str(exc_info.value)
    assert error_msg, "XMLSyntaxError should contain an error message"
