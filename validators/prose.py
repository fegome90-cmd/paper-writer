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

    def _load_rules(self) -> None:
        """Load all prose rules from rules/prose/*.yml.

        Uses engine/loader.py.
        Each rule has: id, patterns[], message, severity, scope, recommendation
        """
        raise NotImplementedError("Phase 0-b: implement when building prose module")

    def validate(self, manuscript: Any) -> list[dict[str, Any]]:
        """Run all prose rules against the parsed manuscript.

        Args:
            manuscript: Manuscript dataclass from parsers/manuscript.py

        Returns:
            List of finding dicts conforming to schemas/finding.schema.json
        """
        findings: list[dict[str, Any]] = []

        for rule in self.registry:
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
                        findings.append(finding)
            elif scope == "section":
                # Apply to specific sections
                section = rule.get("target_section", "")
                if section and section in manuscript.sections:
                    matches = self._apply_rule(
                        rule, manuscript.sections[section].text
                    )
                    for m in matches:
                        findings.append(self._build_finding(rule, m, manuscript))

        # Deduplicate overlapping matches
        findings = self._deduplicate(findings)
        return findings

    def _apply_rule(
        self,
        rule: dict[str, Any],
        text: str,
    ) -> list[re.Match]:
        """Apply a single rule's patterns to text.

        Args:
            rule: Rule dict with 'patterns' list
            text: Text to search

        Returns:
            List of regex matches
        """
        matches: list[re.Match] = []
        for pattern in rule.get("patterns", []):
            for m in re.finditer(pattern, text, re.IGNORECASE):
                if m.group().lower() in self.whitelist:
                    continue
                matches.append(m)
        return matches

    def _build_finding(
        self,
        rule: dict[str, Any],
        match: re.Match,
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
        span_start = manuscript.source_map.to_original(match.start()).char_offset
        span_end = manuscript.source_map.to_original(match.end()).char_offset

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
        """Resolve overlapping matches: longest match wins.

        When two findings overlap (same span range), keep the one with
        the longer match text.

        Args:
            findings: Raw findings that may overlap

        Returns:
            Deduplicated findings
        """
        if not findings:
            return []

        # Sort by span start, then by span length descending
        sorted_findings = sorted(
            findings,
            key=lambda f: (f.get("span", [0, 0])[0], -(
                f.get("span", [0, 0])[1] - f.get("span", [0, 0])[0]
            )),
        )

        # Greedy: take non-overlapping longest matches
        deduplicated: list[dict[str, Any]] = []
        last_end = -1

        for f in sorted_findings:
            start, end = f.get("span", [0, 0])
            if start >= last_end:
                deduplicated.append(f)
                last_end = end

        # Assign finding IDs
        for i, f in enumerate(deduplicated):
            f["finding_id"] = f"F-{i + 1:03d}"

        return deduplicated
