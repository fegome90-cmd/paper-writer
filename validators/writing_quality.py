"""AI-typical term detection validator.

Detects AI-typical writing patterns (delve, tapestry, landscape, etc.)
with section-aware severity overrides (abstract/conclusions → P1).
"""

from __future__ import annotations

import re
from typing import Any

from engine.deduplicator import deduplicate_findings
from engine.loader import load_rules
from parsers.manuscript import Manuscript

# Sections where severity is elevated
ELEVATED_SECTIONS = {"abstract", "conclusions"}


class WritingQualityValidator:
    """Detect AI-typical writing patterns with section-aware severity."""

    def __init__(self, whitelist: set[str] | None = None) -> None:
        self.whitelist = {t.lower() for t in (whitelist or set())}
        self.rules: list[dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self) -> None:
        from harness.ports.assets import get_rules_dir

        rules_dir = get_rules_dir("writing_quality")
        self.rules = load_rules(rules_dir)
        for rule in self.rules:
            rule["command"] = "audit_writing_quality"

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Run all writing quality rules against the manuscript."""
        if manuscript is None:
            return []
        findings: list[dict[str, Any]] = []

        for rule in self.rules:
            if rule.get("suppressed", False):
                continue

            scope = rule.get("scope", "sentence")

            if scope == "sentence":
                for sent in manuscript.sentences:
                    section = self._detect_section(sent.char_start, manuscript)
                    matches = self._apply_rule(rule, sent.text)
                    for m in matches:
                        finding = self._build_finding(rule, m, manuscript, section)
                        finding["line"] = sent.line
                        finding["column"] = sent.col + m.start()
                        finding["span"] = [
                            sent.char_start + m.start(),
                            sent.char_start + m.end(),
                        ]
                        findings.append(finding)

        return deduplicate_findings(findings)

    def _apply_rule(self, rule: dict[str, Any], text: str) -> list[re.Match[str]]:
        matches: list[re.Match[str]] = []
        for pattern in rule.get("patterns", []):
            for m in re.finditer(pattern, text, re.IGNORECASE):
                matched = m.group().lower()
                # Check: exact match, stem match (delves→delve), or contained
                if any(
                    matched == w or matched.startswith(w) or w in matched for w in self.whitelist
                ):
                    continue
                matches.append(m)
        return matches

    def _build_finding(
        self,
        rule: dict[str, Any],
        match: re.Match[str],
        manuscript: Manuscript,
        section: str,
    ) -> dict[str, Any]:
        severity = rule.get("severity", "P2")

        # Section-severity override
        section_severity = rule.get("section_severity", {})
        if section in ELEVATED_SECTIONS and section in section_severity:
            severity = section_severity[section]

        return {
            "command": "audit_writing_quality",
            "rule_id": rule.get("id", "unknown"),
            "finding_id": "",
            "severity": severity,
            "file": manuscript.path,
            "line": 0,
            "column": 0,
            "span": [0, 0],
            "message": rule.get("message", ""),
            "section": section,
            "evidence": {"term": match.group(), "context": match.string[:100]},
            "recommendation": rule.get("recommendation", ""),
        }

    @staticmethod
    def _detect_section(char_offset: int, manuscript: Manuscript) -> str:
        pos = manuscript.source_map.to_original(char_offset)
        char_line = pos.line
        for sec_name, sec in manuscript.sections.items():
            if sec.line_start < char_line <= sec.line_end + 1:
                return sec_name
        return "unknown"
