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

        NOTE: char_start points to the first non-whitespace character of the
        sentence, not to leading whitespace. Leading whitespace before a
        sentence is NOT included in the span.
        """
        import re

        # Phase 0 known limitation: common abbreviations that should not
        # trigger a sentence split.  The list is non-exhaustive; a proper
        # NLP tokenizer (post-MVP) will handle this correctly.
        _ABBREV = r"(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|al|e\.g|i\.e|fig|eq|cf)"

        start = 0
        # Split on sentence-ending punctuation NOT preceded by a period
        # (i.e. abbreviation dots) and NOT followed by a lowercase letter
        # (which often indicates a decimal or abbreviation continuation).
        # Also split on newlines to prevent heading/body merging.
        for m in re.finditer(
            rf"(?:{_ABBREV}\.)|[.!?]+(?=\s)|\n",
            text,
        ):
            if m.group().strip() == "":
                # newline boundary — yield text up to this point as a sentence
                # if it contains substantive content
                segment = text[start:m.start()].strip()
                if segment:
                    leading_ws = len(text[start:m.start()]) - len(text[start:m.start()].lstrip())
                    yield (start + leading_ws, m.start(), segment)
                start = m.end()
                continue
            # abbreviation match — skip, don't treat as sentence boundary
            if m.group().endswith("."):
                continue
            # sentence-ending punctuation
            raw = text[start:m.end()]
            leading_ws = len(raw) - len(raw.lstrip())
            sent_text = raw.strip()
            if sent_text:
                yield (start + leading_ws, m.end(), sent_text)
            start = m.end()

        remaining = text[start:].strip()
        if remaining:
            leading_ws = len(text[start:]) - len(text[start:].lstrip())
            yield (start + leading_ws, len(text), remaining)

    @property
    def line_count(self) -> int:
        return len(self._lines)
