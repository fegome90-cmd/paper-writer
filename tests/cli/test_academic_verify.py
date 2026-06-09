"""Tests for academic-evidence-curation mode: PR3 verify/gate/protocol.

Covers: academic validators, gate wiring, verify artifacts, and protocol output.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# PR3 Task 3.1: Academic validators
# ---------------------------------------------------------------------------


class TestAcademicValidator:
    """validators/academic_evidence.py validates academic artifacts."""

    def test_validate_scope_discipline_passes_core(self) -> None:
        """Core scope with observed evidence passes."""
        from validators.academic_evidence import validate_scope_discipline

        findings = validate_scope_discipline(
            {"scope_classification": "core", "epistemic_classification": "observed"}
        )
        assert len(findings) == 0

    def test_validate_scope_discipline_fails_missing_scope(self) -> None:
        """Missing scope_classification fails."""
        from validators.academic_evidence import validate_scope_discipline

        findings = validate_scope_discipline({"epistemic_classification": "observed"})
        assert any("scope" in f.get("message", "").lower() for f in findings)

    def test_validate_scope_discipline_flags_protocol_as_core(self) -> None:
        """protocol_only narrated as core evidence is flagged."""
        from validators.academic_evidence import validate_scope_discipline

        findings = validate_scope_discipline(
            {"scope_classification": "protocol_only", "epistemic_classification": "observed"}
        )
        assert len(findings) > 0

    def test_validate_search_window_in_window_passes(self) -> None:
        """In-window record passes search window check."""
        from validators.academic_evidence import validate_search_window_integrity

        findings = validate_search_window_integrity(
            records=[{"year": 2022, "doi": "10.1000/test"}],
            search_window={"start_year": 2020, "end_year": 2024},
            amendments=[],
        )
        assert len(findings) == 0

    def test_validate_search_window_out_of_window_fails(self) -> None:
        """Out-of-window record without amendment fails."""
        from validators.academic_evidence import validate_search_window_integrity

        findings = validate_search_window_integrity(
            records=[{"year": 2018, "doi": "10.1000/old"}],
            search_window={"start_year": 2020, "end_year": 2024},
            amendments=[],
        )
        assert len(findings) > 0

    def test_validate_search_window_amendment_passes(self) -> None:
        """Out-of-window record WITH amendment passes."""
        from validators.academic_evidence import validate_search_window_integrity

        findings = validate_search_window_integrity(
            records=[{"year": 2018, "doi": "10.1000/old"}],
            search_window={"start_year": 2020, "end_year": 2024},
            amendments=[{"reason": "Seminal paper", "records": ["10.1000/old"]}],
        )
        assert len(findings) == 0

    def test_validate_metadata_unresolved_blocks(self) -> None:
        """Unresolved critical claim blocks academic completeness."""
        from validators.academic_evidence import validate_metadata_resolution

        findings = validate_metadata_resolution(
            [
                {
                    "doi": "10.1000/critical",
                    "supports_critical_claim": True,
                    "metadata_resolution": {"status": "unresolved"},
                }
            ]
        )
        assert len(findings) > 0

    def test_validate_metadata_resolved_passes(self) -> None:
        """Resolved metadata passes."""
        from validators.academic_evidence import validate_metadata_resolution

        findings = validate_metadata_resolution(
            [
                {
                    "doi": "10.1000/resolved",
                    "supports_critical_claim": True,
                    "metadata_resolution": {"status": "resolved", "doi": "10.1000/resolved"},
                }
            ]
        )
        assert len(findings) == 0


class TestAcademicVerifyArtifacts:
    """verify_artifacts.py produces academic-specific outputs."""

    def test_academic_verify_produces_screening_ledger(self, tmp_path: Path) -> None:
        """Academic mode verify produces screening_ledger.csv."""
        from harness.services.verify_artifacts import generate_academic_artifacts

        # Set up minimal project state
        search_dir = tmp_path / "outputs" / "runs" / "latest" / "search"
        search_dir.mkdir(parents=True)
        (search_dir / "screened_evidence.json").write_text(
            json.dumps({
                "query": "test",
                "evidence": [
                    {
                        "title": "Test Paper",
                        "doi": "10.1000/test",
                        "scope_classification": "core",
                        "epistemic_classification": "observed",
                    }
                ],
                "screening_records": [
                    {
                        "record_id": "10.1000/test",
                        "included": True,
                        "screening_history": [
                            {"stage": "title_abstract", "decision": "proceed", "reason": "match"},
                            {"stage": "full_text", "decision": "included", "reason": "Tier 2"},
                        ],
                    }
                ],
            }),
            encoding="utf-8",
        )

        verify_dir = tmp_path / "outputs" / "runs" / "latest" / "verify"
        verify_dir.mkdir(parents=True)

        artifacts = generate_academic_artifacts(
            project_root=tmp_path,
            output_dir=verify_dir,
        )

        # screening_ledger.csv should exist
        ledger_path = verify_dir / "screening_ledger.csv"
        assert ledger_path.exists(), "screening_ledger.csv should be generated in academic mode"

    def test_rapid_verify_no_screening_ledger(self, tmp_path: Path) -> None:
        """Rapid mode verify does NOT produce screening_ledger.csv (no screening_records)."""
        from harness.services.verify_artifacts import generate_academic_artifacts

        # Minimal state without screening_records
        search_dir = tmp_path / "outputs" / "runs" / "latest" / "search"
        search_dir.mkdir(parents=True)
        (search_dir / "screened_evidence.json").write_text(
            json.dumps({"query": "test", "evidence": []}),
            encoding="utf-8",
        )

        verify_dir = tmp_path / "outputs" / "runs" / "latest" / "verify"
        verify_dir.mkdir(parents=True)

        generate_academic_artifacts(project_root=tmp_path, output_dir=verify_dir)

        ledger_path = verify_dir / "screening_ledger.csv"
        assert not ledger_path.exists(), "screening_ledger.csv should NOT exist without screening_records"


class TestAcademicProtocolOutput:
    """protocol_generator reflects academic classification in output."""

    def test_protocol_includes_screening_data(self, tmp_path: Path) -> None:
        """Protocol output includes screening and classification from academic mode."""
        from validators.protocol_generator import generate_protocol

        # Set up minimal academic evidence
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        (search_dir / "screened_evidence.json").write_text(
            json.dumps({
                "query": "test query",
                "evidence": [
                    {
                        "title": "Test Paper",
                        "doi": "10.1000/test",
                        "scope_classification": "core",
                        "epistemic_classification": "observed",
                        "screening_stage": "included",
                    }
                ],
                "screening_records": [
                    {
                        "record_id": "10.1000/test",
                        "included": True,
                        "screening_history": [
                            {"stage": "title_abstract", "decision": "proceed", "reason": "match"},
                        ],
                    }
                ],
            }),
            encoding="utf-8",
        )

        output_path = tmp_path / "protocol.md"
        protocol_text = generate_protocol(
            search_dir=search_dir,
            output_path=output_path,
            project_name="Test Review",
        )
        # Protocol should reflect academic screening data
        assert "screening" in protocol_text.lower() or "test paper" in protocol_text.lower()
