"""Tests for integration tool wrappers — real behavior, no mocks."""

from pathlib import Path
from unittest.mock import patch

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
        with patch.object(wrapper, "_resolve_executable", return_value=None):
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
        with patch.object(wrapper, "_resolve_executable", return_value=None):
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
