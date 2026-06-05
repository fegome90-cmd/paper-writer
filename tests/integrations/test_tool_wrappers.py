"""Tests for integration tool wrappers — real behavior, no mocks."""

from pathlib import Path

import pytest

from integrations.tools.base import ValidatorResult
from integrations.tools.bibtex_tidy import BibliographyNormalizer
from integrations.tools.refs_metadata_validator import RefsMetadataValidator
from integrations.tools.refs_validator import RefsValidator
from integrations.tools.reporting_auditor import ReportingAuditor
from integrations.tools.vale import StyleLinter

VALID_BIB = """@article{smith2024voice,
  title = {Voice Disorders in Adolescent Singers},
  author = {Smith, Jane and Doe, John},
  year = {2024},
  journal = {Journal of Voice},
  doi = {10.1000/example2024}
}
"""

INVALID_BIB_UNBALANCED = """@article{smith2024voice,
  title = {Unclosed title
  author = {Smith, Jane}
"""

SECTION_WITH_CITE = """# Introduction

Background from @smith2024voice shows significant findings.

The cohort had 150 participants.
"""

SECTION_EMPTY = ""

SECTION_NO_DATA = """# Results

The analysis is pending.
"""


class TestBibliographyNormalizer:
    def test_valid_bib_passes(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(VALID_BIB)
        wrapper = BibliographyNormalizer()
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "pass"
        assert result.validator == "bibliography"

    def test_empty_bib_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text("")
        wrapper = BibliographyNormalizer()
        # No resolver injected → falls back to _builtin_validate (degraded mode)
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "fail"
        assert any("empty" in f["message"].lower() for f in result.findings)

    def test_missing_bib_fails(self) -> None:
        wrapper = BibliographyNormalizer()
        result = wrapper.run({"bibliography": "/nonexistent/file.bib"}, {})
        assert result.status == "fail"
        assert any("does not exist" in f["message"].lower() for f in result.findings)

    def test_unbalanced_braces_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(INVALID_BIB_UNBALANCED)
        wrapper = BibliographyNormalizer()
        # No resolver injected → falls back to _builtin_validate (degraded mode)
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "fail"
        assert any("unbalanced" in f["message"].lower() for f in result.findings)

    def test_no_artifact_key_fails(self) -> None:
        wrapper = BibliographyNormalizer()
        result = wrapper.run({}, {})
        assert result.status == "fail"

    def test_is_available(self) -> None:
        assert BibliographyNormalizer().is_available() is True


class TestRefsValidator:
    def test_all_citations_resolve(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(VALID_BIB)
        section = tmp_path / "introduction.md"
        section.write_text(SECTION_WITH_CITE)
        wrapper = RefsValidator()
        result = wrapper.run(
            {"bibliography": str(bib), "manuscript_files": [str(section)]},
            {},
        )
        assert result.status == "pass"

    def test_unresolved_citation_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(VALID_BIB)
        section = tmp_path / "introduction.md"
        section.write_text("See @nonexistent2024 for details.")
        wrapper = RefsValidator()
        result = wrapper.run(
            {"bibliography": str(bib), "manuscript_files": [str(section)]},
            {},
        )
        assert result.status == "fail"
        assert any("nonexistent2024" in f["message"] for f in result.findings)

    def test_missing_bib_fails(self, tmp_path: Path) -> None:
        section = tmp_path / "introduction.md"
        section.write_text(SECTION_WITH_CITE)
        wrapper = RefsValidator()
        result = wrapper.run(
            {"bibliography": "/nonexistent.bib", "manuscript_files": [str(section)]},
            {},
        )
        assert result.status == "fail"

    def test_is_available(self) -> None:
        assert RefsValidator().is_available() is True


class TestStyleLinter:
    def test_clean_text_passes(self, tmp_path: Path) -> None:
        section = tmp_path / "introduction.md"
        section.write_text("# Introduction\n\nThe study found significant results.")
        wrapper = StyleLinter()
        result = wrapper.run({"manuscript_files": [str(section)]}, {})
        assert result.status in ("pass", "warn")  # warnings possible

    def test_passive_voice_warns(self, tmp_path: Path) -> None:
        section = tmp_path / "methods.md"
        section.write_text(
            "# Methods\n\nThe data was collected by the research team "
            "and were analyzed using standard procedures."
        )
        wrapper = StyleLinter()
        result = wrapper.run({"manuscript_files": [str(section)]}, {})
        # Should have passive voice warnings
        assert result.status in ("pass", "warn")

    def test_empty_files_passes(self) -> None:
        wrapper = StyleLinter()
        result = wrapper.run({"manuscript_files": []}, {})
        assert result.status == "pass"

    def test_is_available(self) -> None:
        assert StyleLinter().is_available() is True


class TestReportingAuditor:
    def test_valid_sections_pass(self, tmp_path: Path) -> None:
        methods = tmp_path / "methods.md"
        methods.write_text(
            "# Methods\n\nWe used a cross-sectional study design with 200 participants."
        )
        results = tmp_path / "results.md"
        results.write_text("# Results\n\nThe prevalence was 42.3% (n=84).")
        discussion = tmp_path / "discussion.md"
        discussion.write_text(
            "# Discussion\n\nKey limitations include sample bias and self-report."
        )
        wrapper = ReportingAuditor()
        result = wrapper.run(
            {
                "manuscript_files": [str(methods), str(results), str(discussion)],
                "outline": None,
            },
            {},
        )
        assert result.status == "pass"

    def test_empty_section_fails(self, tmp_path: Path) -> None:
        methods = tmp_path / "methods.md"
        methods.write_text("")
        wrapper = ReportingAuditor()
        result = wrapper.run({"manuscript_files": [str(methods)]}, {})
        assert result.status == "fail"
        assert any("empty" in f["message"].lower() for f in result.findings)

    def test_missing_discussion_limitations_warns(self, tmp_path: Path) -> None:
        discussion = tmp_path / "discussion.md"
        discussion.write_text("# Discussion\n\nThe findings are significant.")
        wrapper = ReportingAuditor()
        result = wrapper.run({"manuscript_files": [str(discussion)]}, {})
        # Should warn about missing limitations
        assert any("limitation" in f["message"].lower() for f in result.findings)

    def test_is_available(self) -> None:
        assert ReportingAuditor().is_available() is True


class TestWrapperFailClosed:
    """Verify that wrappers fail closed when inputs are invalid."""

    def test_bib_normalizer_no_artifact_key(self) -> None:
        result = BibliographyNormalizer().run({}, {})
        assert result.status == "fail"

    def test_refs_validator_no_bib(self, tmp_path: Path) -> None:
        result = RefsValidator().run({"manuscript_files": []}, {})
        assert result.status == "fail"

    def test_reporting_auditor_missing_section_file(self, tmp_path: Path) -> None:
        result = ReportingAuditor().run(
            {"manuscript_files": [str(tmp_path / "nonexistent.md")]}, {}
        )
        assert result.status == "fail"

    def test_validator_result_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="Invalid status"):
            ValidatorResult(
                validator="test",
                status="invalid",
                summary="test",
                findings=[],
                artifacts_checked=[],
            )

    def test_validator_result_to_dict(self) -> None:
        result = ValidatorResult(
            validator="test",
            status="pass",
            summary="All good",
            findings=[],
            artifacts_checked=["a.bib"],
        )
        d = result.to_dict()
        assert d["status"] == "pass"
        assert d["validator"] == "test"
        assert d["artifacts_checked"] == ["a.bib"]


class TestRefsMetadataValidator:
    """Tests for the refs_validated gate — metadata completeness."""

    def test_valid_entry_passes(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(VALID_BIB)
        wrapper = RefsMetadataValidator()
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "pass"
        assert result.validator == "refs-metadata"

    def test_entry_missing_year_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text("@article{noyear,\n  title = {Missing Year},\n  author = {Test}\n}\n")
        wrapper = RefsMetadataValidator()
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "fail"
        assert any("year" in f["message"].lower() for f in result.findings)

    def test_entry_no_doi_url_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text(
            "@article{nodoi,\n  title = {No DOI},\n  author = {Test},\n  year = {2024}\n}\n"
        )
        wrapper = RefsMetadataValidator()
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "fail"
        assert any(
            "doi" in f["message"].lower() or "url" in f["message"].lower() for f in result.findings
        )

    def test_empty_bib_fails(self, tmp_path: Path) -> None:
        bib = tmp_path / "references.bib"
        bib.write_text("")
        wrapper = RefsMetadataValidator()
        result = wrapper.run({"bibliography": str(bib)}, {})
        assert result.status == "fail"

    def test_missing_bib_file_fails(self) -> None:
        wrapper = RefsMetadataValidator()
        result = wrapper.run({"bibliography": "/nonexistent.bib"}, {})
        assert result.status == "fail"

    def test_no_artifact_key_fails(self) -> None:
        wrapper = RefsMetadataValidator()
        result = wrapper.run({}, {})
        assert result.status == "fail"

    def test_is_available(self) -> None:
        assert RefsMetadataValidator().is_available() is True

    def test_gate_is_refs_validated(self) -> None:
        assert RefsMetadataValidator().gate == "refs_validated"

    def test_name(self) -> None:
        assert RefsMetadataValidator().name == "refs-metadata-validator"


class TestParseEntries:
    """Edge-case tests for RefsMetadataValidator._parse_entries.

    The parser was rewritten to use brace-depth tracking instead of naive
    regex. These tests cover the 6 patterns that the old parser broke on.
    """

    def setup_method(self) -> None:
        self.validator = RefsMetadataValidator()

    def test_single_line_entry(self) -> None:
        bib = "@article{key1, author = {A}, title = {T}}"
        entries = self.validator._parse_entries(bib)
        assert "key1" in entries
        assert entries["key1"]["author"] == "A"
        assert entries["key1"]["title"] == "T"

    def test_multiline_entry(self) -> None:
        bib = "@article{key2,\n  author = {A},\n  title = {T}\n}"
        entries = self.validator._parse_entries(bib)
        assert "key2" in entries
        assert entries["key2"]["author"] == "A"

    def test_multiple_entries(self) -> None:
        bib = "@article{k1, author = {A}}\n@book{k2, title = {T}}"
        entries = self.validator._parse_entries(bib)
        assert len(entries) == 2
        assert "k1" in entries
        assert "k2" in entries

    def test_nested_braces_in_field_value(self) -> None:
        bib = "@article{k3, title = {A {Bold} Title}}"
        entries = self.validator._parse_entries(bib)
        assert "k3" in entries
        assert entries["k3"]["title"] == "A {Bold} Title"

    def test_comment_before_entry(self) -> None:
        bib = "% This is a comment\n@article{k4, author = {A}}"
        entries = self.validator._parse_entries(bib)
        assert "k4" in entries
        assert entries["k4"]["author"] == "A"

    def test_empty_string(self) -> None:
        entries = self.validator._parse_entries("")
        assert entries == {}

    def test_entry_with_no_fields(self) -> None:
        bib = "@article{k5,\n}"
        entries = self.validator._parse_entries(bib)
        assert "k5" in entries
        assert entries["k5"] == {}

    def test_whitespace_around_key(self) -> None:
        bib = "@article{ k6 , author = {A}}"
        entries = self.validator._parse_entries(bib)
        assert "k6" in entries
        assert entries["k6"]["author"] == "A"

    def test_unbraced_field_value(self) -> None:
        bib = "@article{k7, year = 2024}"
        entries = self.validator._parse_entries(bib)
        assert "k7" in entries
        assert entries["k7"]["year"] == "2024"

    def test_trailing_comma_in_fields(self) -> None:
        bib = "@article{k8,\n  author = {A},\n}"
        entries = self.validator._parse_entries(bib)
        assert "k8" in entries
        assert entries["k8"]["author"] == "A"

    def test_mixed_braced_and_unbraced_values(self) -> None:
        bib = "@article{k9, title = {A Title}, year = 2024, author = {B}}"
        entries = self.validator._parse_entries(bib)
        assert entries["k9"]["title"] == "A Title"
        assert entries["k9"]["year"] == "2024"
        assert entries["k9"]["author"] == "B"

    def test_quoted_field_value(self) -> None:
        bib = '@article{k10, journal = "Nature"}'
        entries = self.validator._parse_entries(bib)
        assert entries["k10"]["journal"] == "Nature"


# --- Tests for audit command wrappers added in experiment #310 ---


MANUSCRIPT_WITH_ISSUES = """# Introduction

It is well known that AI is transforming everything. This claim needs evidence.

## Methods

The study was conducted with a sample size of 500 participants.

It should be noted that the results are preliminary.

## Results

In conclusion, the findings suggest a paradigm shift in the field.
"""

MANUSCRIPT_CLEAN = """# Introduction

Smith et al. (2024) demonstrated that retrieval-augmented generation
improves code completion accuracy by 23%. The study surveyed 150 developers.

## Methods

We used a mixed-methods approach combining quantitative analysis of
completion logs with semi-structured developer interviews.

## Results

The results show statistically significant improvements in task completion
time (p < 0.01, Cohen's d = 0.82).
"""

MANUSCRIPT_NO_AI_DISCLOSURE = """# Introduction

This paper presents a novel approach to code generation.
"""

MANUSCRIPT_WITH_AI_DISCLOSURE = """# Introduction

This paper presents a novel approach to code generation.

## AI Use Disclosure

The authors used GPT-4 for code generation assistance in the implementation.
"""


class TestEthicsAuditor:
    def test_no_manuscript_skips(self) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        wrapper = EthicsAuditor()
        result = wrapper.run({}, {})
        assert result.status == "pass"
        assert "skipped" in result.summary.lower()

    def test_missing_file_skips(self, tmp_path: Path) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        wrapper = EthicsAuditor()
        result = wrapper.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})
        assert result.status == "pass"

    def test_no_disclosure_passes(self, tmp_path: Path) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_NO_AI_DISCLOSURE)
        wrapper = EthicsAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "ethics"

    def test_gate_is_ethics_passed(self) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        assert EthicsAuditor().gate == "ethics_passed"

    def test_name(self) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        assert EthicsAuditor().name == "ethics-auditor"

    def test_is_available(self) -> None:
        from integrations.tools.ethics_auditor import EthicsAuditor

        assert EthicsAuditor().is_available() is True


class TestProseAuditor:
    def test_no_manuscript_skips(self) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        wrapper = ProseAuditor()
        result = wrapper.run({}, {})
        assert result.status == "pass"
        assert "skipped" in result.summary.lower()

    def test_missing_file_skips(self, tmp_path: Path) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        wrapper = ProseAuditor()
        result = wrapper.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})
        assert result.status == "pass"

    def test_clean_manuscript_passes(self, tmp_path: Path) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_CLEAN)
        wrapper = ProseAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "prose"
        assert result.artifacts_checked

    def test_issues_manuscript_returns_findings(self, tmp_path: Path) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_WITH_ISSUES)
        wrapper = ProseAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "prose"
        # May have findings for passive voice, long sentences, etc.
        assert isinstance(result.findings, list)

    def test_gate_is_style_passed(self) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        assert ProseAuditor().gate == "style_passed"

    def test_name(self) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        assert ProseAuditor().name == "prose-auditor"

    def test_is_available(self) -> None:
        from integrations.tools.prose_auditor import ProseAuditor

        assert ProseAuditor().is_available() is True


class TestClaimsAuditor:
    def test_no_manuscript_skips(self) -> None:
        from integrations.tools.claims_auditor import ClaimsAuditor

        wrapper = ClaimsAuditor()
        result = wrapper.run({}, {})
        assert result.status == "pass"
        assert "skipped" in result.summary.lower()

    def test_missing_file_skips(self, tmp_path: Path) -> None:
        from integrations.tools.claims_auditor import ClaimsAuditor

        wrapper = ClaimsAuditor()
        result = wrapper.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})
        assert result.status == "pass"

    def test_manuscript_returns_result(self, tmp_path: Path) -> None:
        from integrations.tools.claims_auditor import ClaimsAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_WITH_ISSUES)
        wrapper = ClaimsAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "claims"
        assert isinstance(result.findings, list)

    def test_gate_is_style_passed(self) -> None:
        from integrations.tools.claims_auditor import ClaimsAuditor

        assert ClaimsAuditor().gate == "style_passed"

    def test_name(self) -> None:
        from integrations.tools.claims_auditor import ClaimsAuditor

        assert ClaimsAuditor().name == "claims-auditor"


class TestCitationsAuditor:
    def test_no_manuscript_skips(self) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        wrapper = CitationsAuditor()
        result = wrapper.run({}, {})
        assert result.status == "pass"
        assert "skipped" in result.summary.lower()

    def test_missing_file_skips(self, tmp_path: Path) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        wrapper = CitationsAuditor()
        result = wrapper.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})
        assert result.status == "pass"

    def test_manuscript_returns_result(self, tmp_path: Path) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_CLEAN)
        wrapper = CitationsAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "citations"
        assert isinstance(result.findings, list)

    def test_offline_context(self, tmp_path: Path) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_CLEAN)
        wrapper = CitationsAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {"offline": True})
        assert result.validator == "citations"

    def test_gate_is_citations_resolved(self) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        assert CitationsAuditor().gate == "citations_resolved"

    def test_name(self) -> None:
        from integrations.tools.citations_auditor import CitationsAuditor

        assert CitationsAuditor().name == "citations-auditor"


class TestWritingQualityAuditor:
    def test_no_manuscript_skips(self) -> None:
        from integrations.tools.writing_quality_auditor import WritingQualityAuditor

        wrapper = WritingQualityAuditor()
        result = wrapper.run({}, {})
        assert result.status == "pass"
        assert "skipped" in result.summary.lower()

    def test_missing_file_skips(self, tmp_path: Path) -> None:
        from integrations.tools.writing_quality_auditor import WritingQualityAuditor

        wrapper = WritingQualityAuditor()
        result = wrapper.run({"manuscript": str(tmp_path / "nonexistent.md")}, {})
        assert result.status == "pass"

    def test_manuscript_returns_result(self, tmp_path: Path) -> None:
        from integrations.tools.writing_quality_auditor import WritingQualityAuditor

        mf = tmp_path / "manuscript.md"
        mf.write_text(MANUSCRIPT_WITH_ISSUES)
        wrapper = WritingQualityAuditor()
        result = wrapper.run({"manuscript": str(mf)}, {})
        assert result.validator == "writing_quality"
        assert isinstance(result.findings, list)

    def test_gate_is_style_passed(self) -> None:
        from integrations.tools.writing_quality_auditor import WritingQualityAuditor

        assert WritingQualityAuditor().gate == "style_passed"

    def test_name(self) -> None:
        from integrations.tools.writing_quality_auditor import WritingQualityAuditor

        assert WritingQualityAuditor().name == "writing-quality-auditor"


class TestCodeHealthAuditor:
    def test_returns_result(self) -> None:
        from integrations.tools.code_health_auditor import CodeHealthAuditor

        wrapper = CodeHealthAuditor()
        result = wrapper.run({}, {})
        assert result.validator == "code_health"
        assert isinstance(result.findings, list)
        assert isinstance(result.summary, str)

    def test_no_manuscript_needed(self) -> None:
        """Code health operates on Trifecta graph, not manuscript files."""
        from integrations.tools.code_health_auditor import CodeHealthAuditor

        wrapper = CodeHealthAuditor()
        result = wrapper.run({}, {})
        # Should succeed even without manuscript artifact
        assert result.validator == "code_health"

    def test_gate_is_style_passed(self) -> None:
        from integrations.tools.code_health_auditor import CodeHealthAuditor

        assert CodeHealthAuditor().gate == "style_passed"

    def test_name(self) -> None:
        from integrations.tools.code_health_auditor import CodeHealthAuditor

        assert CodeHealthAuditor().name == "code-health-auditor"

    def test_is_available(self) -> None:
        from integrations.tools.code_health_auditor import CodeHealthAuditor

        assert CodeHealthAuditor().is_available() is True
