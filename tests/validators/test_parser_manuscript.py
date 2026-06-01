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

    # === Regression: S2 — expanded SECTION_ALIASES ===
    def test_section_alias_study_design(self) -> None:
        text = "# Study Design\nWe used a randomized design."
        ms = ManuscriptParser().parse_text(text)
        assert "methods" in ms.sections

    def test_section_alias_statistical_analysis(self) -> None:
        text = "# Statistical Analysis\nWe used t-tests."
        ms = ManuscriptParser().parse_text(text)
        assert "methods" in ms.sections

    def test_section_alias_limitations(self) -> None:
        text = "# Limitations\nSome limitations exist."
        ms = ManuscriptParser().parse_text(text)
        assert "discussion" in ms.sections

    def test_section_alias_strengths_and_limitations(self) -> None:
        text = "# Strengths and limitations\nSeveral strengths."
        ms = ManuscriptParser().parse_text(text)
        assert "discussion" in ms.sections

    # === Regression: C2 — Section line_end with blank lines ===
    def test_section_line_end_with_blank_lines(self) -> None:
        text = "# Introduction\nLine one.\n\nLine two.\n\n# Methods\nContent."
        ms = ManuscriptParser().parse_text(text)
        intro = ms.sections["introduction"]
        # line_end should be the last non-blank content line (line 3 = "Line two."),
        # NOT the trailing blank line before Methods.
        assert intro.line_end == 3, f"Expected line_end=3, got {intro.line_end}"

    def test_section_line_end_no_trailing_blank(self) -> None:
        text = "# Intro\nLine one.\n# Methods\nContent."
        ms = ManuscriptParser().parse_text(text)
        assert ms.sections["intro"].line_end == 1

    def test_preamble_line_end_updated(self) -> None:
        text = "Preamble line 1.\nPreamble line 2.\n# Introduction\nBody."
        ms = ManuscriptParser().parse_text(text)
        assert "__preamble__" in ms.sections
        assert ms.sections["__preamble__"].line_end >= 1, (
            f"Expected preamble line_end >= 1, got {ms.sections['__preamble__'].line_end}"
        )


class TestManuscriptParserTitleCaseHeadings:
    # === Regression: W2 — Title Case heading detection ===
    def test_title_case_heading_detected(self) -> None:
        text = "# Data Analysis\nWe analyzed the data.\n# Results\nFindings."
        ms = ManuscriptParser().parse_text(text)
        assert "data analysis" in ms.sections

    def test_plain_text_title_case_heading(self) -> None:
        text = "Data Analysis\nWe analyzed the data.\nResults\nFindings."
        ms = ManuscriptParser().parse_text(text)
        assert "data analysis" in ms.sections

    def test_title_case_maps_to_section(self) -> None:
        text = "Study Design\nWe designed a study.\nResults\nThe results show."
        ms = ManuscriptParser().parse_text(text)
        assert "methods" in ms.sections


class TestSourceMapSentences:
    # === Regression: C6 — iter_sentences char_start with whitespace ===
    def test_iter_sentences_double_space(self) -> None:
        sm = SourceMap("")
        sentences = list(sm.iter_sentences("Hello.  World."))
        assert len(sentences) == 2
        # "World." should have char_start pointing to 'W', not to the space
        world_start, _world_end, world_text = sentences[1]
        assert world_text == "World."
        sample = "Hello.  World."
        char = sample[world_start] if world_start < len(sample) else "EOF"
        assert sample[world_start] == "W", f"Expected 'W' at char_start={world_start}, got '{char}'"

    def test_iter_sentences_trailing_whitespace(self) -> None:
        sm = SourceMap("")
        sentences = list(sm.iter_sentences("First. Second.  "))
        assert len(sentences) == 2
        assert sentences[0][2] == "First."
        assert sentences[1][2] == "Second."

    def test_iter_sentences_leading_whitespace_after_punct(self) -> None:
        sm = SourceMap("")
        sentences = list(sm.iter_sentences("A.  B.  C."))
        assert len(sentences) == 3
        assert sentences[1][2] == "B."
        assert "A.  B.  C."[sentences[1][0]] == "B"
