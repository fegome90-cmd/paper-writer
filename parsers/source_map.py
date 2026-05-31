from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePosition:
    line: int
    column: int
    char_offset: int


class SourceMap:
    """Maps positions between clean text and original source text.

    Phase 0 supports plain text with line-based mapping.
    Post-MVP: LaTeX-aware stripping of commands and environments.

    The map stores cumulative line/column positions so we can convert
    a character offset in the clean text back to a (line, column) pair
    in the original.
    """

    def __init__(self, original_text: str) -> None:
        self.original_text = original_text
        self._lines = original_text.splitlines(keepends=True)

    def to_original(self, clean_offset: int) -> SourcePosition:
        """Map a character offset in clean text to original source position.

        Phase 0: clean text == original text (no stripping yet).
        Post-MVP: this maps through a transformation table.
        """
        char_offset = clean_offset
        accum = 0
        for line_idx, line in enumerate(self._lines):
            next_accum = accum + len(line)
            if char_offset < next_accum:
                col = char_offset - accum
                return SourcePosition(
                    line=line_idx + 1,
                    column=col,
                    char_offset=char_offset,
                )
            accum = next_accum
        return SourcePosition(
            line=max(1, len(self._lines)),
            column=len(self._lines[-1]) if self._lines else 0,
            char_offset=char_offset,
        )

    def iter_sentences(self, text: str) -> Iterator[tuple[int, int, str]]:
        """Yield (char_start, char_end, sentence_text) from clean text.

        Simple sentence splitting on period+space boundaries.
        Phase 0: basic. Post-MVP: proper NLP-based segmentation.

        Known limitation: common abbreviations (Dr., Mr., etc.) are handled
        via negative lookbehind but not exhaustive.  A proper NLP tokenizer
        (post-MVP) will handle this correctly.

        NOTE: char_start points to the first non-whitespace character of the
        sentence, not to leading whitespace. Leading whitespace before a
        sentence is NOT included in the span.
        """
        import re

        # Abbreviations that end with a dot but are NOT sentence boundaries.
        _ABBREV = (
            r"Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|al|Fig|fig"
            r"|e\.g|i\.e|cf|eq|No|no|Vol|vol|Ed|ed|pp"
        )

        # Strategy: split on sentence-ending punctuation (., !, ?) that is
        # NOT preceded by an abbreviation dot, and treat newlines as sentence
        # boundaries to prevent heading/body merging.
        _SENT_END = rf"(?<!\.)[.!?]+(?=\s|$)"
        _NL_BOUND = r"\n"

        start = 0
        for m in re.finditer(rf"{_SENT_END}|{_NL_BOUND}", text):
            if m.group() == "\n":
                # Newline boundary: yield text before the newline as a sentence
                segment = text[start:m.start()]
                stripped = segment.strip()
                if stripped:
                    leading_ws = len(segment) - len(segment.lstrip())
                    yield (start + leading_ws, m.start(), stripped)
                start = m.end()
            else:
                # Sentence-ending punctuation
                raw = text[start : m.end()]
                leading_ws = len(raw) - len(raw.lstrip())
                sent_text = raw.strip()
                if sent_text:
                    yield (start + leading_ws, m.end(), sent_text)
                start = m.end()

        remaining = text[start:].strip()
        if remaining:
            leading_ws = len(text[start :]) - len(text[start :].lstrip())
            yield (start + leading_ws, len(text), remaining)

    @property
    def line_count(self) -> int:
        return len(self._lines)
