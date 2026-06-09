"""Tests for validators.ethics — AI disclosure compliance."""

from __future__ import annotations

from parsers.manuscript import Manuscript, Section, Sentence
from parsers.source_map import SourceMap
from validators.ethics import EthicsValidator


def _make_manuscript(text: str = "") -> Manuscript:
    source_map = SourceMap(text)
    sections: dict[str, Section] = {}
    sentences = []
    for i, line in enumerate(text.split("\n")):
        if line.strip():
            sentences.append(
                Sentence(
                    text=line.strip(),
                    line=i + 1,
                    col=0,
                    char_start=text.find(line),
                    char_end=text.find(line) + len(line),
                )
            )
    return Manuscript(
        path="test.md",
        format="markdown",
        clean_text=text,
        source_map=source_map,
        sections=sections,
        sentences=sentences,
    )


class TestEthicsValidator:
    def test_manuscript_with_ai_disclosure_passes(self):
        text = "Methods\nAI tools were used to assist with data analysis."
        manuscript = _make_manuscript(text)
        validator = EthicsValidator()
        findings = validator.validate(manuscript)
        assert len(findings) == 0

    def test_manuscript_without_ai_disclosure_fails(self):
        text = "Methods\nData was analyzed using standard statistical methods."
        manuscript = _make_manuscript(text)
        validator = EthicsValidator()
        findings = validator.validate(manuscript)
        assert len(findings) > 0
        assert findings[0]["severity"] == "P0"

    def test_pattern_covers_common_phrasings(self):
        for phrasing in [
            "ChatGPT was used",
            "LLM assistance was provided",
            "Large language model was employed",
        ]:
            text = f"Methods\n{phrasing}."
            manuscript = _make_manuscript(text)
            validator = EthicsValidator()
            findings = validator.validate(manuscript)
            assert len(findings) == 0, f"Failed for phrasing: {phrasing}"
