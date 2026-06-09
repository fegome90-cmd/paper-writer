"""Stream-parse MeSH desc2026.xml via lxml.etree.iterparse."""

from __future__ import annotations

import hashlib
import json
import sys
from typing import NamedTuple

from lxml import etree

from mesh_import.models import (
    ConceptData,
    ConceptRelation,
    DescriptorData,
    TermData,
    TreeNode,
)
from mesh_import.normalize import normalize_text


class ParseResult(NamedTuple):
    descriptors: list[DescriptorData]
    concepts: list[ConceptData]
    terms: list[TermData]
    tree_nodes: list[TreeNode]
    descriptor_trees: list[tuple[str, str]]
    relations: list[ConceptRelation]
    sha256_hex: str
    dtd_sha256_hex: str | None


class _Sha256Reader:
    """File wrapper that incrementally computes SHA256 while reading."""

    def __init__(self, path: str) -> None:
        self._file = open(path, "rb")
        self._hasher = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self._file.read(size)
        if data:
            self._hasher.update(data)
        return data

    def close(self) -> None:
        self._file.close()

    @property
    def hexdigest(self) -> str:
        return self._hasher.hexdigest()


def _local_name(tag: str | bytes) -> str:
    if isinstance(tag, bytes):
        tag = tag.decode("utf-8")
    return tag.split("}")[-1] if "}" in tag else tag


def _child_text(parent: etree._Element, local_tag: str) -> str | None:
    for child in parent:
        if _local_name(child.tag) == local_tag:
            return (child.text or "").strip() if child.text else None
    return None


def _child_elem(parent: etree._Element, local_tag: str) -> etree._Element | None:
    for child in parent:
        if _local_name(child.tag) == local_tag:
            return child
    return None


def _children(parent: etree._Element, local_tag: str) -> list[etree._Element]:
    return [c for c in parent if _local_name(c.tag) == local_tag]


def _derive_parent(tree_number: str) -> str | None:
    """Decision #1: split on '.', rejoin all but last segment."""
    if "." not in tree_number:
        return None
    return tree_number.rsplit(".", 1)[0]


def _parse_one_descriptor(
    elem: etree._Element,
) -> tuple[
    DescriptorData,
    list[ConceptData],
    list[TermData],
    list[TreeNode],
    list[tuple[str, str]],
    list[ConceptRelation],
]:
    dui = _child_text(elem, "DescriptorUI") or ""
    dn_elem = _child_elem(elem, "DescriptorName")
    descriptor_name = _child_text(dn_elem, "String") if dn_elem is not None else ""

    annotation = _child_text(elem, "Annotation")
    registry_number = _child_text(elem, "RegistryNumber")
    scope_note: str | None = _child_text(elem, "ScopeNote")

    tree_numbers: list[str] = []
    tn_list = _child_elem(elem, "TreeNumberList")
    if tn_list is not None:
        for tn_el in _children(tn_list, "TreeNumber"):
            if tn_el.text:
                tree_numbers.append(tn_el.text.strip())

    pharma: list[str] = []
    pa_list = _child_elem(elem, "PharmacologicalActionList")
    if pa_list is not None:
        for pa_el in _children(pa_list, "PharmacologicalAction"):
            ref = _child_elem(pa_el, "DescriptorReferredTo")
            if ref is not None:
                pa_dui = _child_text(ref, "DescriptorUI")
                if pa_dui:
                    pharma.append(pa_dui)

    tree_nodes: list[TreeNode] = []
    desc_trees: list[tuple[str, str]] = []
    for tn in tree_numbers:
        tree_nodes.append(
            TreeNode(
                tree_number=tn,
                descriptor_ui=dui,
                parent_tree_number=_derive_parent(tn),
            )
        )
        desc_trees.append((dui, tn))

    concepts: list[ConceptData] = []
    terms: list[TermData] = []
    relations: list[ConceptRelation] = []

    cl = _child_elem(elem, "ConceptList")
    if cl is not None:
        for c_el in _children(cl, "Concept"):
            cui = _child_text(c_el, "ConceptUI") or ""
            cn_elem = _child_elem(c_el, "ConceptName")
            concept_name = _child_text(cn_elem, "String") if cn_elem is not None else ""
            concept_cui = _child_text(c_el, "CUI")
            is_pref_concept = c_el.get("PreferredConcept") == "Y"

            if scope_note is None and is_pref_concept:
                scope_note = _child_text(c_el, "ScopeNote")

            stypes: list[str] = []
            st_list = _child_elem(c_el, "SemanticTypeList")
            if st_list is not None:
                for st_el in _children(st_list, "SemanticType"):
                    if st_el.text:
                        stypes.append(st_el.text.strip())

            concepts.append(
                ConceptData(
                    concept_ui=cui,
                    descriptor_ui=dui,
                    concept_name=concept_name or "",
                    cui=concept_cui,
                    semantic_type_list_json=json.dumps(stypes) if stypes else None,
                    is_preferred=is_pref_concept,
                )
            )

            for rel_el in _children(c_el, "ConceptRelation"):
                rel_name = rel_el.get("RelationName", "")
                target_ui = _child_text(rel_el, "ConceptUI")
                if not target_ui or target_ui == cui:
                    continue
                if rel_name in ("BRD", "NRW", "REL"):
                    relations.append(
                        ConceptRelation(
                            source_concept_ui=cui,
                            target_concept_ui=target_ui,
                            relation_type=rel_name,
                        )
                    )
                    inv = "NRW" if rel_name == "BRD" else rel_name
                    relations.append(
                        ConceptRelation(
                            source_concept_ui=target_ui,
                            target_concept_ui=cui,
                            relation_type=inv,
                        )
                    )

            tl = _child_elem(c_el, "TermList")
            if tl is not None:
                for t_el in _children(tl, "Term"):
                    term_ui = _child_text(t_el, "TermUI") or ""
                    term_text = _child_text(t_el, "String") or ""
                    is_pref_term = t_el.get("TermPreferred") == "Y"
                    terms.append(
                        TermData(
                            term_ui=term_ui,
                            concept_ui=cui,
                            term_text=term_text,
                            normalized_text=normalize_text(term_text),
                            descriptor_name=descriptor_name or "",
                            term_type=None,
                            is_preferred=is_pref_term,
                        )
                    )

    descriptor = DescriptorData(
        descriptor_ui=dui,
        descriptor_name=descriptor_name or "",
        tree_numbers_json=json.dumps(tree_numbers) if tree_numbers else None,
        annotation=annotation,
        pharmacological_action_json=json.dumps(pharma) if pharma else None,
        registry_number=registry_number,
        scope_note=scope_note,
    )

    return descriptor, concepts, terms, tree_nodes, desc_trees, relations


def parse_descriptor_xml(
    xml_path: str,
    dtd_path: str | None = None,
    progress_interval: int = 5000,
) -> ParseResult:
    """Stream-parse MeSH desc2026.xml with bounded memory.

    Uses lxml.etree.iterparse with namespace-agnostic element matching.
    SHA256 computed incrementally during parse (Decision #3).
    Memory bounded via elem.clear() + sibling removal (Decision #7).
    """
    reader = _Sha256Reader(xml_path)

    all_desc: list[DescriptorData] = []
    all_concept: list[ConceptData] = []
    all_term: list[TermData] = []
    all_tn: list[TreeNode] = []
    all_dt: list[tuple[str, str]] = []
    all_rel: list[ConceptRelation] = []

    try:
        context = etree.iterparse(
            reader,
            events=("end",),
            tag="{*}DescriptorRecord",
            recover=True,
            huge_tree=True,
        )
        count = 0
        for _event, elem in context:
            desc, concepts, terms, tree_nodes, desc_trees, relations = _parse_one_descriptor(elem)

            all_desc.append(desc)
            all_concept.extend(concepts)
            all_term.extend(terms)
            all_tn.extend(tree_nodes)
            all_dt.extend(desc_trees)
            all_rel.extend(relations)

            count += 1
            if count % progress_interval == 0:
                print(f"  parsed {count} descriptors...", file=sys.stderr)

            elem.clear()
            while elem.getprevious() is not None:
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem.getprevious())
    finally:
        reader.close()

    sha256_hex = reader.hexdigest

    dtd_sha256_hex: str | None = None
    if dtd_path is not None:
        try:
            with open(dtd_path, "rb") as f:
                dtd_sha256_hex = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            pass

    return ParseResult(
        descriptors=all_desc,
        concepts=all_concept,
        terms=all_term,
        tree_nodes=all_tn,
        descriptor_trees=all_dt,
        relations=all_rel,
        sha256_hex=sha256_hex,
        dtd_sha256_hex=dtd_sha256_hex,
    )
