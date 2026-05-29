"""Claim candidate detection for paper audit claims.

Phase 0: trigger-lexicon based, section-aware claim candidate detection.
Post-MVP: semantic decomposition, evidence mapping.

Core principle: Phase 0 detects risk, does not verify truth.
Each finding is a candidate that must be manually reviewed.

Inspired by:
  - detecting-scientific-claim (section-aware, sentence-level)
  - SciFact (claim/evidence/status schema — post-MVP)
  - RIGOURATE (evidential proportionality concept)
  - statcheck (statistical verification — post-MVP)
"""

from __future__ import annotations

from typing import Any


class ClaimsValidator:
    """Detect claim candidates in manuscript text.

    Steps:
    1. Sentence segmentation via ManuscriptParser
    2. Section detection (Abstract, Introduction, Methods, Results, Discussion, Conclusions)
    3. Per-category rule application (causal, comparative, descriptive, prescriptive)
    4. Section-aware risk adjustment (claims in Conclusions > claims in Methods)
    5. Evidence required mapping (what evidence would be needed for verification)
    6. Deduplication of overlapping matches (longest match wins)
    """

    def __init__(self, whitelist: set[str] | None = None) -> None:
        self.whitelist = whitelist or set()

    def validate(self, manuscript: Any) -> list[dict[str, Any]]:
        """Run all claim rules against the parsed manuscript.

        Args:
            manuscript: Manuscript dataclass from parsers/manuscript.py
                        Must have: .sections, .sentences, .source_map

        Returns:
            List of finding dicts conforming to schemas/finding.schema.json
        """
        findings: list[dict[str, Any]] = []

        # 1. Load rules from rules/claims/*.yml
        # 2. For each rule:
        #    a. Get scope-appropriate text segments (sentences for sentence-scope rules)
        #    b. Apply pattern matching
        #    c. Skip whitelisted terms
        #    d. Create finding with position, message, severity
        # 3. Apply section risk modifiers from rules/claims/risk_by_section.yml
        # 4. Deduplicate overlapping matches

        return findings

    def _load_rules(self) -> None:
        """Load YAML rules from rules/claims/ directory.

        Uses engine/loader.py to parse YAML rules into rule objects.
        """
        raise NotImplementedError("Phase 0-d: implement when building claims module")

    def _apply_section_risk(
        self,
        finding: dict[str, Any],
        section: str,
    ) -> dict[str, Any]:
        """Modify finding severity based on section risk multiplier.

        Args:
            finding: Raw finding from pattern matching
            section: Detected section name

        Returns:
            Finding with adjusted severity
        """
        # Load risk modifiers from rules/claims/risk_by_section.yml
        # Apply multiplier to severity:
        #   Abstract: +1 level
        #   Conclusions: +1 level
        #   Methods: -1 level (procedural)
        #   Results, Discussion: no change
        return finding


def format_claims_report(
    findings: list[dict[str, Any]],
    output_format: str = "json",
) -> str:
    """Format findings for output.

    Args:
        findings: List of finding dicts
        output_format: 'json' (default) or 'terminal'

    Returns:
        Formatted string
    """
    if output_format == "json":
        import json
        return json.dumps({"candidates": findings}, indent=2)
    else:
        # Terminal format: per-finding lines with severity icon
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
