from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from parsers.source_map import SourceMap


@dataclass
class Sentence:
    """A single sentence extracted from manuscript text."""

    text: str
    line: int
    col: int
    char_start: int
    char_end: int


@dataclass
class Section:
    """A manuscript section identified by heading."""

    heading: str
    text: str
    line_start: int
    line_end: int


@dataclass
class Manuscript:
    """Parsed manuscript with sections, sentences, and source mapping."""

    path: str
    format: str
    clean_text: str
    source_map: SourceMap
    sections: dict[str, Section] = field(default_factory=dict)
    sentences: list[Sentence] = field(default_factory=list)


IMRAD_HEADINGS: list[tuple[str, str]] = [
    ("abstract", r"^\s*(abstract|summary)\s*$"),
    ("introduction", r"^\s*(introduction|background)\s*$"),
    (
        "methods",
        r"^\s*(methods?|materials?\s+(and|&)\s+methods?|"
        r"methodology|patients?\s+(and|&)\s+methods?)\s*$",
    ),
    ("results", r"^\s*results?\s*$"),
    ("discussion", r"^\s*discussion\s*$"),
    ("conclusions", r"^\s*conclusions?\s*$"),
    ("declarations", r"^\s*(declarations|acknowledgments?|acknowledgements?)\s*$"),
    ("references", r"^\s*references?\s*$"),
]

SECTION_ALIASES: dict[str, str] = {
    "background": "introduction",
    "materials and methods": "methods",
    "materials & methods": "methods",
    "patients and methods": "methods",
    "patients & methods": "methods",
    "study design": "methods",
    "statistical analysis": "methods",
    "summary": "abstract",
    "conclusion": "conclusions",
    "limitations": "discussion",
    "strengths and limitations": "discussion",
    "acknowledgment": "declarations",
    "acknowledgement": "declarations",
    "acknowledgments": "declarations",
    "acknowledgements": "declarations",
}


class ManuscriptParser:
    """Parse manuscript text into structured sections and sentences.

    Phase 0: plain text and basic markdown support.
    Post-MVP: LaTeX parsing with command stripping, pandoc AST.
    """

    def parse(self, path: str | Path) -> Manuscript:
        path = Path(path)
        raw = path.read_text(encoding="utf-8")

        fmt = self._detect_format(path)
        clean = self._normalize_newlines(raw)

        source_map = SourceMap(clean)
        sections = self._parse_sections(clean)
        sentences = self._parse_sentences(clean, source_map)

        return Manuscript(
            path=str(path),
            format=fmt,
            clean_text=clean,
            source_map=source_map,
            sections=sections,
            sentences=sentences,
        )

    def parse_text(self, text: str, path: str = "<text>", fmt: str = "txt") -> Manuscript:
        clean = self._normalize_newlines(text)
        source_map = SourceMap(clean)
        sections = self._parse_sections(clean)
        sentences = self._parse_sentences(clean, source_map)

        return Manuscript(
            path=path,
            format=fmt,
            clean_text=clean,
            source_map=source_map,
            sections=sections,
            sentences=sentences,
        )

    @staticmethod
    def _detect_format(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".md", ".qmd", ".rmd", ".markdown"}:
            return "markdown"
        elif suffix in {".tex", ".ltx", ".cls"}:
            return "latex"
        elif suffix == ".txt":
            return "txt"
        else:
            return "txt"

    @staticmethod
    def _normalize_newlines(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _parse_sections(text: str) -> dict[str, Section]:
        sections: dict[str, Section] = {}
        lines = text.split("\n")

        current_heading: str | None = None
        current_start = 0
        section_lines: list[str] = []
        last_content_line: int = 0  # tracks last non-blank line index

        def flush(end_idx: int) -> None:
            """Flush current section with end_idx as its last line index."""
            if current_heading is None:
                return
            body = "\n".join(section_lines).strip()
            key = current_heading.lower().strip()
            key = SECTION_ALIASES.get(key, key)
            if key not in sections:
                sections[key] = Section(
                    heading=current_heading.strip(),
                    text=body,
                    line_start=current_start,
                    line_end=end_idx,
                )

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            matched_heading: str | None = None
            # Markdown heading
            m = re.match(r"^#{1,6}\s+(.+)$", stripped)
            if m:
                matched_heading = m.group(1)

            # Plain text heading (all caps or Title Case, short, standalone)
            if not matched_heading:
                m = re.match(r"^([A-Z][A-Z\s]+)$", stripped)
                if m and len(stripped.split()) <= 4:
                    matched_heading = stripped
            if not matched_heading:
                # Title Case heading (e.g. "Data Analysis", "Study Design")
                m = re.match(
                    r"^(?:[A-Z][a-z]*(?:\s+[A-Z][a-z]*){0,3})$",
                    stripped,
                )
                if m and len(stripped.split()) <= 4:
                    matched_heading = stripped

            # IMRAD heading match
            if not matched_heading:
                for _name, pattern in IMRAD_HEADINGS:
                    if re.match(pattern, stripped, re.IGNORECASE):
                        matched_heading = stripped
                        break

            if matched_heading:
                # End previous section at last non-blank content line before this heading
                flush(last_content_line)
                current_heading = matched_heading
                current_start = idx
                section_lines = []
            else:
                last_content_line = idx
                if current_heading is not None:
                    section_lines.append(stripped)
                else:
                    if "__preamble__" not in sections:
                        sections["__preamble__"] = Section(
                            heading="",
                            text="",
                            line_start=0,
                            line_end=0,
                        )
                    existing = sections["__preamble__"]
                    existing.text = (existing.text + "\n" + stripped).strip()
                    existing.line_end = idx

        # Final flush: last section goes to last content line
        if current_heading is not None:
            flush(last_content_line)
        elif "__preamble__" in sections:
            sections["__preamble__"].line_end = last_content_line if lines else 0
        return sections

    @staticmethod
    def _parse_sentences(text: str, source_map: SourceMap) -> list[Sentence]:
        sentences: list[Sentence] = []
        for char_start, char_end, sent_text in source_map.iter_sentences(text):
            pos = source_map.to_original(char_start)
            sentences.append(
                Sentence(
                    text=sent_text,
                    line=pos.line,
                    col=pos.column,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
        return sentences
