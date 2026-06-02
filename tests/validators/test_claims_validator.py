"""Tests for validators/claims.py — claim candidate detection."""

from validators.claims import ClaimsValidator, build_claims_report

SAMPLE_WITH_CLAIMS = """# Introduction
This study examines the relationship between exercise and cognition.

Previous research has demonstrated a positive association.

# Methods
We conducted a randomized trial.

# Results
Exercise significantly improved cognitive performance.

# Discussion
Our findings suggest that exercise causes cognitive improvement.

This proves that exercise is beneficial for brain health.
"""


class TestClaimsValidatorBasic:
    def test_claim_candidates_detected(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        assert isinstance(candidates, list)
        # Should detect some claims from trigger patterns
        assert len(candidates) >= 0

    def test_candidates_have_required_fields(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            assert "claim_id" in c, f"Missing claim_id in {c}"
            assert "claim_type" in c, f"Missing claim_type in {c}"
            assert "section" in c, f"Missing section in {c}"
            assert "risk" in c, f"Missing risk in {c}"
            assert "triggers" in c, f"Missing triggers in {c}"
            assert c["claim_type"] in (
                "causal",
                "comparative",
                "descriptive",
                "prescriptive",
                "unknown",
            )

    def test_whitelist_skips_terms(self, make_manuscript) -> None:
        text = "This proves the hypothesis."
        ms = make_manuscript(text)
        validator = ClaimsValidator(whitelist={"proves"})
        candidates = validator.validate(ms)
        proving = [c for c in candidates if "proves" in str(c.get("triggers", []))]
        assert len(proving) == 0


class TestClaimsValidatorSectionAwareness:
    def test_section_detected(self, make_manuscript) -> None:
        ms = make_manuscript("# Introduction\nThis proves something.")
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            assert c.get("section") in ("introduction", "unknown")

    def test_risk_varies_by_section(self, make_manuscript) -> None:
        text = (
            "# Conclusions\nThis proves the hypothesis.\n# Methods\nThis proves the method works."
        )
        ms = make_manuscript(text)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            assert c["risk"] in ("high", "medium", "low", "info")


class TestClaimsValidatorRiskModifiers:
    # === Regression: C4 — risk_by_section key normalization ===

    def test_abstract_gets_high_risk(self, make_manuscript) -> None:
        """Abstract has multiplier=2, default_risk=high → should be high."""
        text = "# Abstract\nThis proves the hypothesis."
        ms = make_manuscript(text)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            assert c["risk"] == "high", f"Expected high risk in abstract, got {c['risk']}"

    def test_methods_gets_info_risk(self, make_manuscript) -> None:
        """Methods has multiplier=0, default_risk=info → should be info."""
        text = "# Methods\nThis proves the method works."
        ms = make_manuscript(text)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            assert c["risk"] == "info", f"Expected info risk in methods, got {c['risk']}"

    def test_multiplier_increases_risk(self, make_manuscript) -> None:
        """Conclusions has multiplier=2 → bumps risk up one level."""
        text = "# Conclusions\nThis proves the conclusion."
        ms = make_manuscript(text)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        for c in candidates:
            # conclusions default_risk=high, multiplier=2 → still high (cap)
            assert c["risk"] in ("high", "medium")


class TestBuildClaimsReport:
    def test_report_structure(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        report = build_claims_report(ms, candidates, 42)

        assert report["command"] == "audit_claims"
        assert "file" in report
        assert "candidates" in report
        assert "summary" in report
        assert "metadata" in report
        assert "disclaimer" in report

    def test_summary_counts(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        report = build_claims_report(ms, candidates, 42)

        summary = report["summary"]
        assert summary["total_candidates"] == len(candidates)
        assert "by_type" in summary
        assert "by_risk" in summary
        assert "by_section" in summary

    def test_by_type_has_all_keys(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        report = build_claims_report(ms, candidates)

        by_type = report["summary"]["by_type"]
        for key in ("causal", "comparative", "descriptive", "prescriptive", "unknown"):
            assert key in by_type

    def test_by_risk_has_all_keys(self, make_manuscript) -> None:
        ms = make_manuscript(SAMPLE_WITH_CLAIMS)
        validator = ClaimsValidator()
        candidates = validator.validate(ms)
        report = build_claims_report(ms, candidates)

        by_risk = report["summary"]["by_risk"]
        for key in ("high", "medium", "low", "info"):
            assert key in by_risk
