"""Frozen dataclasses for MeSH descriptor/concept/term/tree/relation data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DescriptorData:
    descriptor_ui: str
    descriptor_name: str
    tree_numbers_json: str | None
    annotation: str | None
    pharmacological_action_json: str | None
    registry_number: str | None
    scope_note: str | None


@dataclass(frozen=True)
class ConceptData:
    concept_ui: str
    descriptor_ui: str
    concept_name: str
    cui: str | None
    semantic_type_list_json: str | None
    is_preferred: bool


@dataclass(frozen=True)
class TermData:
    term_ui: str
    concept_ui: str
    term_text: str
    normalized_text: str
    descriptor_name: str
    term_type: str | None
    is_preferred: bool


@dataclass(frozen=True)
class TreeNode:
    tree_number: str
    descriptor_ui: str
    parent_tree_number: str | None


@dataclass(frozen=True)
class ConceptRelation:
    source_concept_ui: str
    target_concept_ui: str
    relation_type: str
