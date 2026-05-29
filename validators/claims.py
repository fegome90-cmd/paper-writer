from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from engine.loader import load_rules
from parsers.manuscript import Manuscript

SECTION_RISK: dict[str, str] = {
    "abstract": "high",
    "conclusions": "high",
    "introduction": "medium",
    "discussion": "medium",
    "results": "low",
    "methods": "low",
    "__preamble__": "info",
}

CLAIM_TAG_MAP: dict[str, str] = {
    "claims.causal": "causal",
    "claims.comparative": "comparative",
    "claims.descriptive": "descriptive",
    "claims.prescriptive": "prescriptive",
}


class ClaimsValidator:
    """Detect claim candidates in manuscript text.

    Phase 0: trigger-lexicon based, section-aware claim candidate detection.
    Post-MVP: semantic decomposition, evidence mapping.

    Core principle: Phase 0 detects risk, does not verify truth.
    Each finding is a candidate that must be manually reviewed.
    """

    def __init__(self, whitelist: set[str] | None = None) -> None:
        self.whitelist = whitelist or set()
        self.rules: list[dict[str, Any]] = []
        self.risk_modifiers: dict[str, dict[str, Any]] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        rules_dir = Path(__file__).resolve().parent.parent / "rules" / "claims"
        self.rules = load_rules(rules_dir)
        for r in self.rules:
            r["command"] = "audit_claims"

        risk_file = rules_dir / "risk_by_section.yml"
        if risk_file.is_file():
            with open(risk_file) as f:
                data = yaml.safe_load(f)
            if data:
                self.risk_modifiers = {
                    entry.get("section", ""): entry for entry in data.get("risk_modifiers", [])
                }

    def validate(self, manuscript: Manuscript) -> list[dict[str, Any]]:
        """Run all claim rules against the parsed manuscript.

        Args:
            manuscript: Parsed manuscript with sections and sentences.

        Returns:
            List of claim candidate dicts (not finding.schema.json — uses
            claim_audit.schema.json format).
        """
        candidates: list[dict[str, Any]] = []

        for rule in self.rules:
            rule_group = rule.get("rule_group", "")
            claim_type = CLAIM_TAG_MAP.get(rule_group, "unknown")
            patterns: list[str] = rule.get("patterns", [])
            if not patterns:
                continue

            compiled = self._compile_patterns(patterns)
            scope = rule.get("scope", "sentence")

            if scope == "sentence":
                for sent in manuscript.sentences:
                    section = self._detect_section(sent.char_start, manuscript)
                    for cp in compiled:
                        m = cp.search(sent.text)
                        if m and m.group().lower() not in self.whitelist:
                            risk = self._compute_risk(section, rule.get("severity", "P2"))
                            candidates.append(
                                {
                                    "text": sent.text,
                                    "claim_type": claim_type,
                                    "section": section,
                                    "risk": risk,
                                    "triggers": [m.group()],
                                    "evidence_required": rule.get("evidence_required", []),
                                    "line": sent.line,
                                    "column": sent.col + m.start(),
                                    "span": [
                                        sent.char_start + m.start(),
                                        sent.char_start + m.end(),
                                    ],
                                }
                            )
            elif scope == "document":
                for cp in compiled:
                    for m in cp.finditer(manuscript.clean_text):
                        if m.group().lower() in self.whitelist:
                            continue
                        section = self._detect_section(m.start(), manuscript)
                        risk = self._compute_risk(section, rule.get("severity", "P2"))
                        candidates.append(
                            {
                                "text": m.group(),
                                "claim_type": claim_type,
                                "section": section,
                                "risk": risk,
                                "triggers": [m.group()],
                                "evidence_required": rule.get("evidence_required", []),
                                "line": manuscript.source_map.to_original(m.start()).line,
                                "column": manuscript.source_map.to_original(m.start()).column,
                                "span": [m.start(), m.end()],
                            }
                        )

        # Deduplicate overlapping spans
        candidates = self._deduplicate_candidates(candidates)

        # Assign IDs
        for i, c in enumerate(candidates):
            c["claim_id"] = f"CC-{i + 1:03d}"

        return candidates

    def _compile_patterns(self, patterns: list[str]) -> list[re.Pattern[str]]:
        compiled: list[re.Pattern[str]] = []
        for p in patterns:
            try:
                compiled.append(re.compile(p, re.IGNORECASE))
            except re.error:
                continue
        return compiled

    @staticmethod
    def _detect_section(char_offset: int, manuscript: Manuscript) -> str:
        for sec_name, sec in manuscript.sections.items():
            offset_map = manuscript.source_map.to_original(char_offset)
            char_line = offset_map.line
            if sec.line_start <= char_line <= sec.line_end:
                return sec_name
        return "unknown"

    def _compute_risk(self, section: str, default_severity: str) -> str:
        section = section.lower().strip()
        base_risk = SECTION_RISK.get(section, "info")

        modifier = self.risk_modifiers.get(section, {})
        risk_adjust = int(modifier.get("risk_adjustment", 0))
        levels = ["info", "low", "medium", "high"]
        try:
            idx = levels.index(base_risk)
            idx = max(0, min(len(levels) - 1, idx + risk_adjust))
            return levels[idx]
        except ValueError:
            return base_risk

    @staticmethod
    def _deduplicate_candidates(
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        sorted_c = sorted(
            candidates,
            key=lambda c: (
                c.get("span", [0, 0])[0],
                -(c.get("span", [0, 0])[1] - c.get("span", [0, 0])[0]),
            ),
        )
        deduped: list[dict[str, Any]] = []
        last_end = -1
        for c in sorted_c:
            start, end = c.get("span", [0, 0])
            if start >= last_end:
                deduped.append(c)
                last_end = end
        return deduped


def build_claims_report(
    manuscript: Manuscript,
    candidates: list[dict[str, Any]],
    execution_time_ms: int = 0,
) -> dict[str, Any]:
    """Build the full claims audit result dict.

    Args:
        manuscript: The parsed manuscript.
        candidates: List of claim candidate dicts.
        execution_time_ms: Execution time in milliseconds.

    Returns:
        Dict conforming to claim_audit.schema.json.
    """
    by_type: dict[str, int] = {
        "causal": 0,
        "comparative": 0,
        "descriptive": 0,
        "prescriptive": 0,
        "unknown": 0,
    }
    by_risk: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "info": 0}
    by_section: dict[str, int] = {}

    for c in candidates:
        ct = c.get("claim_type", "unknown")
        by_type[ct] = by_type.get(ct, 0) + 1

        r = c.get("risk", "info")
        by_risk[r] = by_risk.get(r, 0) + 1

        sec = c.get("section", "unknown")
        by_section[sec] = by_section.get(sec, 0) + 1

    return {
        "command": "audit_claims",
        "file": manuscript.path,
        "format": manuscript.format,
        "candidates": candidates,
        "summary": {
            "total_candidates": len(candidates),
            "by_type": by_type,
            "by_risk": by_risk,
            "by_section": by_section,
        },
        "metadata": {
            "parser_version": "1.0",
            "rules_loaded": 0,
            "execution_time_ms": execution_time_ms,
        },
        "disclaimer": (
            "Phase 0: claims are candidate detections based on linguistic triggers. "
            "This is NOT claim verification. Each candidate should be manually reviewed."
        ),
    }


def format_claims_report(
    findings: list[dict[str, Any]],
    output_format: str = "json",
) -> str:
    """Format findings for output.

    Args:
        findings: List of finding dicts.
        output_format: 'json' (default) or 'terminal'.

    Returns:
        Formatted string.
    """
    if output_format == "json":
        import json

        return json.dumps({"candidates": findings}, indent=2)
    else:
        lines: list[str] = []
        icons = {"P0": "[!!]", "P1": "[!]", "P2": "[i]"}
        for f in findings:
            icon = icons.get(f.get("severity", "P2"), "[?]")
            lines.append(
                f"{icon} {f.get('rule_id', 'unknown')}: "
                f"{f.get('message', '')} "
                f"(line {f.get('line', '?')})"
            )
        return "\n".join(lines)
