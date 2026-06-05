"""Tiered gate verdict system for validator gate decisions.

Provides a shared GateVerdict dataclass that replaces boolean gate_passed
with a 4-tier severity system + annotation strings + selective gate refusal.
Ported from ARS claim_audit_finalizer (simplified for paper-writer).

Tiers:
    none      — No finding. Gate passes cleanly.
    low_warn  — Informational. Gate passes; finding is advisory.
    med_warn  — Should fix. Gate passes but finding is flagged for review.
    high_warn — Must fix. Gate REFUSED; finding blocks progression.

Annotation strings are human-readable codes that identify the specific
issue category (e.g. "[FABRICATED-REFERENCE]", "[PREPRINT-SOURCE]").
Downstream formatters can match these for selective surfacing.

This module is the single source of truth for gate verdicts.
All validators should use GateVerdict instead of ad-hoc boolean fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Tiers ────────────────────────────────────────────────────────────

TIER_NONE = "none"
TIER_LOW_WARN = "low_warn"
TIER_MED_WARN = "med_warn"
TIER_HIGH_WARN = "high_warn"

ALL_TIERS = frozenset({TIER_NONE, TIER_LOW_WARN, TIER_MED_WARN, TIER_HIGH_WARN})

# Tiers that cause gate refusal (formatter must surface these)
GATE_REFUSING_TIERS = frozenset({TIER_HIGH_WARN})

# Tiers that pass the gate but carry warnings
GATE_WARNING_TIERS = frozenset({TIER_LOW_WARN, TIER_MED_WARN})


# ── Annotations ──────────────────────────────────────────────────────
# Canonical annotation strings — coordinated with formatters.
# Changing these MUST be reflected in any downstream matching.

ANNOT_FABRICATED_REFERENCE = "[FABRICATED-REFERENCE]"
ANNOT_NOT_FOUND = "[CITATION-NOT-FOUND]"
ANNOT_TITLE_MISMATCH = "[TITLE-MISMATCH]"
ANNOT_PARTIAL_VERIFY = "[PARTIAL-VERIFICATION]"
ANNOT_PREPRINT_SOURCE = "[PREPRINT-SOURCE]"
ANNOT_CONTAMINATION_RISK = "[CONTAMINATION-RISK]"
ANNOT_UNCITED_ASSERTION = "[UNCITED-ASSERTION]"
ANNOT_METHOD_MISSING = "[METHOD-ITEM-MISSING]"
ANNOT_OVERCLAIM = "[OVERCLAIM]"
ANNOT_WEASEL_WORD = "[WEASEL-WORD]"
ANNOT_VAGUE_LANGUAGE = "[VAGUE-LANGUAGE]"


@dataclass(frozen=True)
class GateVerdict:
    """Tiered gate verdict for a single finding or gate decision.

    Attributes:
        tier: Severity tier (none/low_warn/med_warn/high_warn).
        annotation: Canonical annotation string identifying the issue.
        gate_refuse: Whether this verdict should block progression.
        message: Human-readable description of the finding.
        evidence: Supporting evidence dict (optional).
    """

    tier: str
    annotation: str = ""
    gate_refuse: bool = False
    message: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tier not in ALL_TIERS:
            msg = f"Invalid tier: {self.tier!r}. Must be one of {sorted(ALL_TIERS)}"
            raise ValueError(msg)
        # Auto-set gate_refuse based on tier if not explicitly set
        if self.tier in GATE_REFUSING_TIERS and not self.gate_refuse:
            object.__setattr__(self, "gate_refuse", True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON output."""
        return {
            "tier": self.tier,
            "annotation": self.annotation,
            "gate_refuse": self.gate_refuse,
            "message": self.message,
        }


def severity_to_tier(severity: str) -> str:
    """Map paper-writer severity codes (P0-P3) to gate tiers.

    Mapping:
        P0 → high_warn (must fix, gate refuses)
        P1 → med_warn (should fix, gate passes but flagged)
        P2 → low_warn (informational, gate passes)
        P3/info → none (no gate impact)
        Any other → low_warn (safe default)
    """
    mapping: dict[str, str] = {
        "P0": TIER_HIGH_WARN,
        "P1": TIER_MED_WARN,
        "P2": TIER_LOW_WARN,
        "P3": TIER_NONE,
        "info": TIER_NONE,
        "none": TIER_NONE,
    }
    return mapping.get(severity, TIER_LOW_WARN)


def tier_from_findings(findings: list[dict[str, Any]]) -> GateVerdict:
    """Compute aggregate gate verdict from a list of findings.

    The highest-severity finding determines the tier.
    Returns a GateVerdict with the worst tier found.
    """
    if not findings:
        return GateVerdict(tier=TIER_NONE, message="No findings")

    worst_tier = TIER_NONE
    worst_annotation = ""
    worst_message = ""
    worst_evidence: dict[str, Any] = {}

    # Priority order: high_warn > med_warn > low_warn > none
    tier_priority = {
        TIER_NONE: 0,
        TIER_LOW_WARN: 1,
        TIER_MED_WARN: 2,
        TIER_HIGH_WARN: 3,
    }

    for f in findings:
        severity = f.get("severity", "info")
        tier = severity_to_tier(severity)

        if tier_priority.get(tier, 0) > tier_priority.get(worst_tier, 0):
            worst_tier = tier
            worst_annotation = f.get("rule_id", "")
            worst_message = f.get("message", "")
            worst_evidence = f.get("evidence", {})

    return GateVerdict(
        tier=worst_tier,
        annotation=worst_annotation,
        message=worst_message,
        evidence=worst_evidence,
    )
