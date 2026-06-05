"""Scientific prose analysis for paper audit prose.

Phase 0: check-registry based, pattern-matching, section-aware.
Post-MVP: discourse-level analysis, hedging consistency scoring, LLM-assisted.

Detects:
  - Overclaim language (definitive causal, absolute, novelty claims)
  - Hedging language and hedging conflicts
  - Weasel words (empty authoritative phrases)
  - Causal/effect language
  - Vague quantifiers
  - Nominalization (verbs converted to nouns)
  - Unsupported certainty markers

Inspired by:
  - proselint (Check Registry pattern, namespacing)
  - write-good (simple output format, plugin system)
  - TeXtidote (offset mapping for markup-aware parsing)
  - Vale (YAML rule files, scoping, check types)
"""

from __future__ import annotations

import re
from typing import Any

from engine.deduplicator import deduplicate_findings

# Citation marker patterns in academic text
CITATION_MARKER_RE = re.compile(
    r"\[@[^]]+\]"  # Pandoc [@key] or [@key, p. 15]
    r"|@\w+[\w:-]*"  # Bare Pandoc @key (narrative)
    r"|\\cite\{[^}]+\}"  # LaTeX \cite{key}
    r"|\[\d+\]"  # Numeric [1]
    r"|\[[\d,\s-]+\]"  # Numeric ranges [1-3, 5]
    r"|\(\w+\s*,\s*\d{4}\)"  # (Author, Year)
    r"|\(\w+\s+et\s+al\.\s*,\s*\d{4}\)"  # (Author et al., Year)
)

# Definitional sentence patterns — excluded from uncited assertion detection.
# Ported from ARS uncited_assertion_detector condition 3 (v3.8 §"D4-c").
# These sentences state definitions rather than empirical claims,
# so flagging them as "uncited" produces false positives.
DEFINITIONAL_SENTENCE_RE = re.compile(
    r"\b(refers?\s+to|is\s+defined\s+as|we\s+define"
    r"|for\s+the\s+purposes\s+of"
    r"|can\s+be\s+(?:defined|understood)\s+as"
    r"|is\s+a\s+(?:type|kind|form|class)\s+of"
    r"|means?\s+(?:that|the)\b)"
    ,
    re.IGNORECASE,
)


class ProseValidator:
    """Analyze scientific prose for overclaim, hedging, weasel words.

    Uses a Check Registry pattern: each rule is a module with an id,
    patterns, severity, and scope. Rules are loaded from YAML files
    and registered at initialization.

    Pattern resolution:
      - Longest match wins for overlapping patterns
      - Whitelist terms are excluded (technical vocabulary)
      - Section-scoped rules only apply to their target sections
    """

    def __init__(self, whitelist: set[str] | None = None) -> None:
        self.whitelist = whitelist or set()
        self.registry: list[dict[str, Any]] = []
        self._load_rules()

    @property
    def rules_count(self) -> int:
        return len(self.registry)

    def _load_rules(self) -> None:
        """Load all prose rules from rules/prose/*.yml."""
        from engine.loader import load_rules
        from harness.ports.assets import get_rules_dir

        rules_dir = get_rules_dir("prose")
        rules = load_rules(rules_dir)
        for rule in rules:
            rule["command"] = "audit_prose"
        self.registry = rules

    def validate(self, manuscript: Any) -> list[dict[str, Any]]:
        """Run all prose rules against the parsed manuscript.

        Args:
            manuscript: Manuscript dataclass from parsers/manuscript.py

        Returns:
            List of finding dicts conforming to schemas/finding.schema.json
        """
        findings: list[dict[str, Any]] = []

        for rule in self.registry:
            # Skip suppressed rules (disabled but kept for future reference)
            if rule.get("suppressed", False):
                continue

            scope = rule.get("scope", "sentence")

            if scope == "document":
                # Apply to entire text
                matches = self._apply_rule(rule, manuscript.clean_text)
                for m in matches:
                    findings.append(self._build_finding(rule, m, manuscript))
            elif scope == "sentence":
                # Apply per sentence
                for sent in manuscript.sentences:
                    matches = self._apply_rule(rule, sent.text)
                    for m in matches:
                        finding = self._build_finding(rule, m, manuscript)
                        finding["line"] = sent.line
                        finding["column"] = sent.col + m.start()
                        finding["span"] = [
                            sent.char_start + m.start(),
                            sent.char_start + m.end(),
                        ]

                        # Check citation requirement
                        ev = rule.get("evidence_required", [])
                        if "citation" in ev:
                            has_cite = bool(CITATION_MARKER_RE.search(sent.text))
                            is_definitional = bool(
                                DEFINITIONAL_SENTENCE_RE.search(sent.text)
                            )
                            finding["evidence"] = {
                                "citation_present": has_cite,
                                "definitional": is_definitional,
                                "sentence_text": sent.text[:120],
                            }
                            if not has_cite and not is_definitional:
                                finding["rule_id"] = finding["rule_id"].replace(
                                    "prose.", "prose.uncited_"
                                )
                                finding["message"] = (
                                    f"Uncited empirical claim: {rule.get('message', '')} "
                                    f"— no citation marker found in sentence."
                                )

                        findings.append(finding)
            elif scope == "section":
                # Apply to specific sections.
                # Search the FULL clean_text but filter matches to section boundaries.
                # This ensures match.start() is a clean_text offset (correct for to_original).
                section = rule.get("target_section", "")
                if section and section in manuscript.sections:
                    sec = manuscript.sections[section]
                    matches = self._apply_rule(rule, manuscript.clean_text)
                    for m in matches:
                        pos = manuscript.source_map.to_original(m.start())
                        if sec.line_start <= pos.line <= sec.line_end:
                            findings.append(self._build_finding(rule, m, manuscript))

        # Deduplicate overlapping matches
        findings = self._deduplicate(findings)
        return findings

    def _apply_rule(
        self,
        rule: dict[str, Any],
        text: str,
    ) -> list[re.Match[str]]:
        """Apply a single rule's patterns to text.

        Args:
            rule: Rule dict with 'patterns' list
            text: Text to search

        Returns:
            List of regex matches
        """
        matches: list[re.Match[str]] = []
        for pattern in rule.get("patterns", []):
            for m in re.finditer(pattern, text, re.IGNORECASE):
                if m.group().lower() in self.whitelist:
                    continue
                matches.append(m)
        return matches

    def _build_finding(
        self,
        rule: dict[str, Any],
        match: re.Match[str],
        manuscript: Any,
    ) -> dict[str, Any]:
        """Build a Finding dict from a rule and match.

        Args:
            rule: The rule that matched
            match: The regex match object
            manuscript: Parsed manuscript (for position mapping)

        Returns:
            Finding dict
        """
        # Map clean-text position to original file position via source_map
        orig_pos = manuscript.source_map.to_original(match.start())
        span_end_pos = manuscript.source_map.to_original(match.end())
        span_start = orig_pos.char_offset
        span_end = span_end_pos.char_offset

        return {
            "finding_id": "TBD",  # Assigned during deduplication
            "command": "audit_prose",
            "rule_id": rule.get("id", "unknown"),
            "severity": rule.get("severity", "P2"),
            "file": manuscript.path,
            "line": orig_pos.line,
            "column": orig_pos.column,
            "span": [span_start, span_end],
            "message": rule.get("message", ""),
            "recommendation": rule.get("recommendation", ""),
            "evidence_required": rule.get("evidence_required", []),
        }

    def _deduplicate(
        self,
        findings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Delegates to engine.deduplicator.deduplicate_findings (SSOT)."""
        return deduplicate_findings(findings)
