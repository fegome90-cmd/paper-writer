"""AI disclosure compliance validator.

Checks for AI disclosure statement in methods or acknowledgments.
Pattern-based (not LLM-based) — catches obvious omissions.
"""
from __future__ import annotations

import re
from typing import Any

from engine.deduplicator import deduplicate_findings
from engine.loader import load_rules
from parsers.manuscript import Manuscript


class EthicsValidator:
    """Check for AI disclosure compliance and attribution integrity."""

    def __init__(self) -> None:
        self.rules: list[dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self) -> None:
        from harness.ports.assets import get_rules_dir

        rules_dir = get_rules_dir("ethics")
        self.rules = load_rules(rules_dir)
        for rule in self.rules:
            rule["command"] = "audit_ethics"

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Check for AI disclosure statement in methods/acknowledgments."""
        findings: list[dict[str, Any]] = []

        # Check if any AI disclosure pattern exists anywhere in the manuscript
        has_disclosure = False
        for rule in self.rules:
            patterns = rule.get("patterns", [])
            for pattern in patterns:
                try:
                    if re.search(pattern, manuscript.clean_text):
                        has_disclosure = True
                        break
                except re.error:
                    continue
            if has_disclosure:
                break

        if not has_disclosure:
            findings.append({
                "command": "audit_ethics",
                "rule_id": "ethics.missing_ai_disclosure",
                "finding_id": "",
                "severity": "P0",
                "file": manuscript.path,
                "line": 0,
                "column": 0,
                "span": [0, 0],
                "message": "No AI disclosure statement found in methods or acknowledgments",
                "section": "methods",
                "evidence": {"patterns_checked": len(self.rules)},
                "recommendation": (
                    "Add explicit AI disclosure: which tools, how used, who is accountable."
                ),
            })

        return deduplicate_findings(findings)
