from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


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
            line=len(self._lines),
            column=len(self._lines[-1]) if self._lines else 0,
            char_offset=char_offset,
        )

    def iter_sentences(self, text: str) -> Iterator[tuple[int, int, str]]:
        """Yield (char_start, char_end, sentence_text) from clean text.

        Simple sentence splitting on period+space boundaries.
        Phase 0: basic. Post-MVP: proper NLP-based segmentation.
        """
        import re

        start = 0
        for m in re.finditer(r"[^.!?]*[.!?]", text):
            raw = m.group()
            yield (start, m.end(), raw.strip())
            start = m.end()

        remaining = text[start:].strip()
        if remaining:
            yield (start, len(text), remaining)

    @property
    def line_count(self) -> int:
        return len(self._lines)
