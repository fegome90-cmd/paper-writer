"""Tests for GateVerdict — tiered gate verdict system."""
from __future__ import annotations

import pytest

from validators.gate_verdict import (
    ALL_TIERS,
    ANNOT_FABRICATED_REFERENCE,
    ANNOT_NOT_FOUND,
    ANNOT_OVERCLAIM,
    ANNOT_PREPRINT_SOURCE,
    GATE_REFUSING_TIERS,
    GATE_WARNING_TIERS,
    TIER_HIGH_WARN,
    TIER_LOW_WARN,
    TIER_MED_WARN,
    TIER_NONE,
    GateVerdict,
    severity_to_tier,
    tier_from_findings,
)


class TestGateVerdict:
    def test_none_tier_passes(self) -> None:
        v = GateVerdict(tier=TIER_NONE, message="clean")
        assert v.gate_refuse is False
        assert v.tier == "none"

    def test_low_warn_passes(self) -> None:
        v = GateVerdict(tier=TIER_LOW_WARN, message="info")
        assert v.gate_refuse is False

    def test_med_warn_passes(self) -> None:
        v = GateVerdict(tier=TIER_MED_WARN, message="should fix")
        assert v.gate_refuse is False

    def test_high_warn_refuses(self) -> None:
        v = GateVerdict(tier=TIER_HIGH_WARN, message="must fix")
        assert v.gate_refuse is True

    def test_high_warn_auto_refuse(self) -> None:
        """high_warn should auto-set gate_refuse=True."""
        v = GateVerdict(tier=TIER_HIGH_WARN, gate_refuse=False, message="auto")
        # post_init overrides
        assert v.gate_refuse is True

    def test_invalid_tier_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tier"):
            GateVerdict(tier="invalid_tier")

    def test_annotation(self) -> None:
        v = GateVerdict(
            tier=TIER_HIGH_WARN,
            annotation=ANNOT_FABRICATED_REFERENCE,
            message="Fabricated DOI",
        )
        assert v.annotation == "[FABRICATED-REFERENCE]"

    def test_to_dict(self) -> None:
        v = GateVerdict(
            tier=TIER_MED_WARN,
            annotation=ANNOT_PREPRINT_SOURCE,
            message="Preprint citation",
        )
        d = v.to_dict()
        assert d["tier"] == "med_warn"
        assert d["annotation"] == "[PREPRINT-SOURCE]"
        assert d["gate_refuse"] is False

    def test_frozen(self) -> None:
        v = GateVerdict(tier=TIER_NONE)
        with pytest.raises(AttributeError):
            v.tier = TIER_HIGH_WARN  # type: ignore[misc]


class TestSeverityToTier:
    def test_p0_high(self) -> None:
        assert severity_to_tier("P0") == TIER_HIGH_WARN

    def test_p1_med(self) -> None:
        assert severity_to_tier("P1") == TIER_MED_WARN

    def test_p2_low(self) -> None:
        assert severity_to_tier("P2") == TIER_LOW_WARN

    def test_p3_none(self) -> None:
        assert severity_to_tier("P3") == TIER_NONE

    def test_info_none(self) -> None:
        assert severity_to_tier("info") == TIER_NONE

    def test_unknown_defaults_low(self) -> None:
        assert severity_to_tier("unknown") == TIER_LOW_WARN


class TestTierFromFindings:
    def test_empty_findings(self) -> None:
        v = tier_from_findings([])
        assert v.tier == TIER_NONE
        assert v.gate_refuse is False

    def test_single_p0(self) -> None:
        findings = [{"severity": "P0", "rule_id": "citation.not_found", "message": "Not found"}]
        v = tier_from_findings(findings)
        assert v.tier == TIER_HIGH_WARN
        assert v.gate_refuse is True
        assert v.annotation == "citation.not_found"

    def test_single_p2(self) -> None:
        findings = [{"severity": "P2", "rule_id": "preprint", "message": "Preprint"}]
        v = tier_from_findings(findings)
        assert v.tier == TIER_LOW_WARN
        assert v.gate_refuse is False

    def test_mixed_takes_worst(self) -> None:
        findings = [
            {"severity": "P2", "rule_id": "preprint", "message": "Preprint"},
            {"severity": "P0", "rule_id": "not_found", "message": "Not found"},
            {"severity": "P1", "rule_id": "mismatch", "message": "Mismatch"},
        ]
        v = tier_from_findings(findings)
        assert v.tier == TIER_HIGH_WARN
        assert v.annotation == "not_found"

    def test_all_info(self) -> None:
        findings = [
            {"severity": "info", "rule_id": "info1"},
            {"severity": "P3", "rule_id": "info2"},
        ]
        v = tier_from_findings(findings)
        assert v.tier == TIER_NONE


class TestConstants:
    def test_all_tiers_count(self) -> None:
        assert len(ALL_TIERS) == 4

    def test_refusing_tiers(self) -> None:
        assert GATE_REFUSING_TIERS == {TIER_HIGH_WARN}

    def test_warning_tiers(self) -> None:
        assert GATE_WARNING_TIERS == {TIER_LOW_WARN, TIER_MED_WARN}

    def test_annotations_are_bracketed(self) -> None:
        for annot in [
            ANNOT_FABRICATED_REFERENCE,
            ANNOT_NOT_FOUND,
            ANNOT_OVERCLAIM,
            ANNOT_PREPRINT_SOURCE,
        ]:
            assert annot.startswith("[") and annot.endswith("]")
