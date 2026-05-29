"""Tests for parsers/manuscript.py and parsers/source_map.py."""

from pathlib import Path

from parsers.manuscript import IMRAD_HEADINGS, ManuscriptParser
from parsers.source_map import SourceMap

SAMPLE_MANUSCRIPT = """# Introduction

This study examines the effects of exercise on cognitive function.

Previous research has suggested a positive association.

# Methods

We conducted a randomized controlled trial with 200 participants.

Participants were assigned to either the intervention or control group.

# Results

The intervention group showed significant improvement (p < 0.05).

# Discussion

These findings suggest that exercise improves cognitive function.

However, several limitations should be noted.

# Conclusions

Exercise is associated with improved cognitive outcomes.
"""


class TestManuscriptParser:
    def test_parse_sections(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text(SAMPLE_MANUSCRIPT, "test.md", "markdown")

        assert "introduction" in ms.sections
        assert "methods" in ms.sections
        assert "results" in ms.sections
        assert "discussion" in ms.sections
        assert "conclusions" in ms.sections

    def test_section_content(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text(SAMPLE_MANUSCRIPT)

        intro = ms.sections.get("introduction")
        assert intro is not None
        assert "exercise" in intro.text
        assert "cognitive function" in intro.text

    def test_sentences_parsed(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text("First sentence. Second sentence. Third one.")

        assert len(ms.sentences) >= 2

    def test_format_detection(self) -> None:
        parser = ManuscriptParser()
        assert parser._detect_format(Path("paper.md")) == "markdown"
        assert parser._detect_format(Path("paper.qmd")) == "markdown"
        assert parser._detect_format(Path("paper.tex")) == "latex"
        assert parser._detect_format(Path("paper.txt")) == "txt"
        assert parser._detect_format(Path("paper")) == "txt"

    def test_imrad_headings_structure(self) -> None:
        for _name, pattern in IMRAD_HEADINGS:
            assert pattern.startswith(r"^\s*")
            assert pattern.endswith(r"\s*$")

    def test_source_map_to_original(self) -> None:
        text = "line one\nline two\nline three"
        sm = SourceMap(text)

        pos0 = sm.to_original(0)
        assert pos0.line == 1
        assert pos0.column == 0

        pos_mid = sm.to_original(5)
        assert pos_mid.line == 1
        assert pos_mid.column == 5

        pos_line2 = sm.to_original(9)
        assert pos_line2.line == 2
        assert pos_line2.column == 0

    def test_source_map_line_count(self) -> None:
        sm = SourceMap("a\nb\nc")
        assert sm.line_count == 3

        sm_empty = SourceMap("")
        assert sm_empty.line_count == 0

    def test_iter_sentences(self) -> None:
        sm = SourceMap("")
        sentences = list(sm.iter_sentences("First. Second. Third."))
        assert len(sentences) == 3
        assert sentences[0][2] == "First."
        assert sentences[1][2] == "Second."
        assert sentences[2][2] == "Third."

    def test_iter_sentences_no_trailing_punct(self) -> None:
        sm = SourceMap("")
        sentences = list(sm.iter_sentences("No period here"))
        assert len(sentences) == 1
        assert sentences[0][2] == "No period here"


class TestManuscriptParserEmpty:
    def test_empty_text(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text("")
        assert ms.clean_text == ""
        assert len(ms.sentences) == 0

    def test_newlines_only(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text("\n\n\n")
        assert ms.clean_text == "\n\n\n"

    def test_normalize_newlines(self) -> None:
        parser = ManuscriptParser()
        ms = parser.parse_text("line1\r\nline2\rline3")
        assert ms.clean_text == "line1\nline2\nline3"


class TestManuscriptParserSectionEdgeCases:
    def test_section_aliases(self) -> None:
        text = "# Background\nSome background.\n# Methods\nSome methods."
        parser = ManuscriptParser()
        ms = parser.parse_text(text)
        assert "introduction" in ms.sections
        assert ms.sections["introduction"].text == "Some background."
