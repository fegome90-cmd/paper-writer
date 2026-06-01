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

        Simple sentence splitting on period+space boundaries, with
        abbreviation awareness and newline-as-boundary support.

        Known limitation: abbreviation list is non-exhaustive.  A proper
        NLP tokenizer (post-MVP) will handle this correctly.

        NOTE: char_start points to the first non-whitespace character of the
        sentence, not to leading whitespace. Leading whitespace before a
        sentence is NOT included in the span.
        """

        if not text:
            return

        # Common abbreviations whose trailing dot is NOT a sentence boundary.
        abbrevs = [
            "Mr.",
            "Mrs.",
            "Ms.",
            "Dr.",
            "Prof.",
            "Sr.",
            "Jr.",
            "St.",
            "vs.",
            "etc.",
            "al.",
            "e.g.",
            "i.e.",
            "fig.",
            "eq.",
            "cf.",
        ]

        # Mark every dot that belongs to an abbreviation so we skip it.
        _protected: set[int] = set()
        for _a in abbrevs:
            _idx = 0
            while True:
                _pos = text.find(_a, _idx)
                if _pos == -1:
                    break
                for _j, _c in enumerate(_a):
                    if _c == ".":
                        _protected.add(_pos + _j)
                _idx = _pos + 1

        # Collect sentence break positions: punctuation NOT in an abbreviation,
        # and newlines (to prevent heading/body merging).
        _breaks: list[tuple[str, int]] = []
        for _i, _c in enumerate(text):
            if _c == "\n":
                _breaks.append(("nl", _i))
            elif _c in ".!?" and _i not in _protected:
                _breaks.append(("punct", _i))

        # Walk breaks and yield spans.
        start = 0
        for kind, idx in _breaks:
            if kind == "nl":
                segment = text[start:idx]
                stripped = segment.strip()
                if stripped:
                    leading_ws = len(segment) - len(segment.lstrip())
                    yield (start + leading_ws, idx, stripped)
                start = idx + 1
            else:
                raw = text[start : idx + 1]
                stripped = raw.strip()
                if stripped:
                    leading_ws = len(raw) - len(raw.lstrip())
                    yield (start + leading_ws, idx + 1, stripped)
                start = idx + 1

        remaining = text[start:].strip()
        if remaining:
            leading_ws = len(text[start:]) - len(text[start:].lstrip())
            yield (start + leading_ws, len(text), remaining)

    @property
    def line_count(self) -> int:
        return len(self._lines)
