from __future__ import annotations

import re
from typing import Any

from parsers.manuscript import Manuscript


def apply_rule_to_manuscript(
    rule: dict[str, Any],
    manuscript: Manuscript,
    whitelist: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Apply a single rule against the parsed manuscript.

    Respects the rule's scope: 'sentence', 'section', or 'document'.

    Args:
        rule: Rule dict with 'patterns', 'scope', 'severity', etc.
        manuscript: Parsed manuscript.
        whitelist: Set of terms to skip.

    Returns:
        List of raw match results (partial findings without position info).
    """
    whitelist = whitelist or set()
    scope = rule.get("scope", "sentence")
    patterns: list[str] = rule.get("patterns", [])
    if not patterns:
        return []

    compiled: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error:
            continue

    matches: list[dict[str, Any]] = []

    if scope == "document":
        for cp in compiled:
            for m in cp.finditer(manuscript.clean_text):
                if m.group().lower() in whitelist:
                    continue
                matches.append(
                    {
                        "match_text": m.group(),
                        "char_start": m.start(),
                        "char_end": m.end(),
                    }
                )

    elif scope == "section":
        target = rule.get("target_section", "")
        if target and target in manuscript.sections:
            sec_text = manuscript.sections[target].text
            for cp in compiled:
                for m in cp.finditer(sec_text):
                    if m.group().lower() in whitelist:
                        continue
                    matches.append(
                        {
                            "match_text": m.group(),
                            "char_start": m.start(),
                            "char_end": m.end(),
                        }
                    )

    elif scope == "sentence":
        for sent in manuscript.sentences:
            for cp in compiled:
                for m in cp.finditer(sent.text):
                    if m.group().lower() in whitelist:
                        continue
                    matches.append(
                        {
                            "match_text": m.group(),
                            "char_start": sent.char_start + m.start(),
                            "char_end": sent.char_start + m.end(),
                            "line": sent.line,
                            "column": sent.col + m.start(),
                        }
                    )

    return matches


def build_finding(
    rule: dict[str, Any],
    match: dict[str, Any],
    manuscript: Manuscript,
) -> dict[str, Any]:
    """Build a Finding dict from a rule and match result.

    Args:
        rule: The rule that matched.
        match: Raw match from apply_rule_to_manuscript.
        manuscript: Parsed manuscript (for source map).

    Returns:
        Finding dict conforming to schemas/finding.schema.json.
    """
    char_start = match.get("char_start", 0)
    char_end = match.get("char_end", 0)
    orig_pos = manuscript.source_map.to_original(char_start)

    return {
        "finding_id": "",
        "command": rule.get("command", "audit_prose"),
        "rule_id": rule.get("id", "unknown"),
        "severity": rule.get("severity", "P2"),
        "file": manuscript.path,
        "line": match.get("line", orig_pos.line),
        "column": match.get("column", orig_pos.column),
        "span": [char_start, char_end],
        "message": rule.get("message", ""),
        "recommendation": rule.get("recommendation", ""),
        "context": match.get("match_text", ""),
        "evidence_required": rule.get("evidence_required", []),
    }
