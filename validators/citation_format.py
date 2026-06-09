"""Citation format converter: (Author, Year) → @key.

Converts inline author-year citations to BibTeX key references
that pandoc can resolve. Works by:

1. Parsing a .bib file to build author+year → key mappings
2. Scanning text for (Author, Year) patterns
3. Replacing with @key format

Typical usage::

    from validators.citation_format import convert_citations

    text = "Recent work (Lewis et al., 2020) shows..."
    bib_text = Path("references.bib").read_text()
    converted = convert_citations(text, bib_text)
    # → "Recent work @lewis2020_rag shows..."
"""

from __future__ import annotations

import re
from typing import Any

_BIBTEX_META_TYPES = frozenset({"string", "comment", "preamble"})


def parse_bib_keys(bib_text: str) -> dict[str, dict[str, str]]:
    """Parse a BibTeX file to extract keys and author/year metadata.

    Uses brace-depth-aware parsing. Skips non-entry types
    (@string, @comment, @preamble).

    Returns:
        Dict mapping bib_key → {"authors": str, "year": str, "title": str}.
    """
    entries: dict[str, dict[str, str]] = {}

    for m in re.finditer(r"@(\w+)\s*\{", bib_text, re.IGNORECASE):
        entry_type = m.group(1).lower()
        if entry_type in _BIBTEX_META_TYPES:
            continue

        # Find matching closing brace via depth tracking
        start = m.end()
        depth = 1
        pos = start
        while pos < len(bib_text) and depth > 0:
            if bib_text[pos] == "{":
                depth += 1
            elif bib_text[pos] == "}":
                depth -= 1
            pos += 1
        if depth != 0:
            continue

        entry_body = bib_text[start : pos - 1]
        comma_pos = entry_body.find(",")
        if comma_pos == -1:
            continue

        key = entry_body[:comma_pos].strip()
        body = entry_body[comma_pos + 1 :]

        # Extract fields with brace-depth tracking for nested braces
        fields: dict[str, str] = {}
        for field_match in re.finditer(r"(\w+)\s*=\s*", body):
            field_name = field_match.group(1).lower()
            val_start = field_match.end()
            if val_start >= len(body):
                continue
            if body[val_start] == "{":
                depth = 1
                pos = val_start + 1
                while pos < len(body) and depth > 0:
                    if body[pos] == "{":
                        depth += 1
                    elif body[pos] == "}":
                        depth -= 1
                    pos += 1
                fields[field_name] = body[val_start + 1 : pos - 1].strip()
            else:
                end = body.find(",", val_start)
                if end == -1:
                    end = len(body)
                fields[field_name] = body[val_start:end].strip().strip('"').strip("'")

        entries[key] = {
            "authors": fields.get("author", ""),
            "year": fields.get("year", ""),
            "title": fields.get("title", ""),
        }

    return entries


def build_author_year_index(
    bib_entries: dict[str, dict[str, str]],
) -> dict[str, str]:
    """Build an index from (lastname, year) → bib_key.

    Handles multiple authors by indexing the first author's last name.
    Also indexes "FirstAuthor et al." patterns.

    Returns:
        Dict mapping "lastname_year" → bib_key.
    """
    index: dict[str, str] = {}

    for key, entry in bib_entries.items():
        authors = entry.get("authors", "")
        year = entry.get("year", "")

        if not authors or not year:
            continue

        # Split on " and " to get individual authors
        author_list = [a.strip() for a in authors.split(" and ") if a.strip()]

        for author in author_list:
            # Extract last name: "Smith, J." → "smith", "J. Smith" → "smith"
            if "," in author:
                last_name = author.split(",")[0].strip()
            else:
                parts = author.strip().split()
                last_name = parts[-1] if parts else ""

            if last_name:
                # Normalize: lowercase, remove diacritics approximation
                normalized = re.sub(r"[^a-z]", "", last_name.lower())
                if normalized:
                    lookup_key = f"{normalized}_{year}"
                    # Only index if not already taken (first entry wins)
                    if lookup_key not in index:
                        index[lookup_key] = key

    return index


def extract_author_year_citations(text: str) -> list[dict[str, Any]]:
    """Extract (Author, Year) citations from text.

    Matches patterns like:
    - (Lewis et al., 2020)
    - (Vaswani et al., 2017)
    - (Devlin et al., 2019)
    - (Smith and Jones, 2023)
    - (Smith, 2023)

    Returns:
        List of dicts with: raw, authors, year, start, end.
    """
    citations: list[dict[str, Any]] = []

    # Parenthetical format: (Author, Year) or (Author et al., Year)
    pattern_parenthetical = re.compile(
        r"\("
        r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?(?:\s+and\s+[A-Z][a-zA-Z\s]+(?:et\s+al\.)?)*)"
        r"\s*,\s*"
        r"(\d{4})"
        r"\)"
    )

    # Narrative format: Author (Year) — author outside parens
    # Matches: Smith (2020), Wang et al. (2023), Smith and Jones (2023)
    pattern_narrative = re.compile(
        r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?(?:\s+and\s+[A-Z][a-zA-Z\s]+(?:et\s+al\.)?)*)"
        r"\s+"
        r"\((\d{4})\)"
    )

    for match in pattern_parenthetical.finditer(text):
        raw_authors = match.group(1).strip()
        year = match.group(2)

        # Extract last names from the author string
        last_names: list[str] = []
        # Split on " and " first
        author_parts = re.split(r"\s+and\s+", raw_authors)
        for part in author_parts:
            # Remove "et al." suffix
            part = re.sub(r"\s*et\s+al\.?\s*$", "", part).strip()
            # Last word is typically the last name (if no comma)
            # If comma: "Smith, J." → "Smith"
            if "," in part:
                last_name = part.split(",")[0].strip()
            else:
                words = part.split()
                last_name = words[-1] if words else ""
            if last_name:
                normalized = re.sub(r"[^a-z]", "", last_name.lower())
                if normalized:
                    last_names.append(normalized)

        citations.append(
            {
                "raw": match.group(0),
                "authors": last_names,
                "year": year,
                "start": match.start(),
                "end": match.end(),
            }
        )

    # Also detect narrative format: Author (Year)
    for match in pattern_narrative.finditer(text):
        raw_authors = match.group(1).strip()
        year = match.group(2)

        narr_last_names: list[str] = []
        author_parts = re.split(r"\s+and\s+", raw_authors)
        for part in author_parts:
            part = re.sub(r"\s*et\s+al\.?\s*$", "", part).strip()
            if "," in part:
                last_name = part.split(",")[0].strip()
            else:
                words = part.split()
                last_name = words[-1] if words else ""
            if last_name:
                normalized = re.sub(r"[^a-z]", "", last_name.lower())
                if normalized:
                    narr_last_names.append(normalized)

        citations.append(
            {
                "raw": match.group(0),
                "authors": narr_last_names,
                "year": year,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return citations


def resolve_citation(
    citation: dict[str, Any],
    author_year_index: dict[str, str],
) -> str | None:
    """Resolve an author-year citation to a BibTeX key.

    Tries each author's last name combined with the year.
    Returns None if no match found.
    """
    year = citation.get("year", "")
    authors = citation.get("authors", [])

    for last_name in authors:
        lookup_key = f"{last_name}_{year}"
        if lookup_key in author_year_index:
            return author_year_index[lookup_key]

    return None


def convert_citations(text: str, bib_text: str) -> str:
    """Convert all (Author, Year) citations in text to @key format.

    Args:
        text: Manuscript text with (Author, Year) citations.
        bib_text: BibTeX file content for key resolution.

    Returns:
        Text with @key citations replacing (Author, Year) patterns.
    """
    bib_entries = parse_bib_keys(bib_text)
    author_year_index = build_author_year_index(bib_entries)
    citations = extract_author_year_citations(text)

    if not citations:
        return text

    # Sort by start position descending to replace from end to start
    # (preserves earlier positions during replacement)
    resolved_count = 0
    result = text
    for citation in sorted(citations, key=lambda c: c["start"], reverse=True):
        bib_key = resolve_citation(citation, author_year_index)
        if bib_key:
            result = result[: citation["start"]] + f"@{bib_key}" + result[citation["end"] :]
            resolved_count += 1

    return result


def audit_citation_format(text: str, bib_text: str) -> list[dict[str, Any]]:
    """Audit text for unresolved (Author, Year) citations.

    Returns findings for citations that couldn't be resolved to @key.
    Also returns info findings for successfully resolved citations.
    """
    bib_entries = parse_bib_keys(bib_text)
    author_year_index = build_author_year_index(bib_entries)
    citations = extract_author_year_citations(text)

    findings: list[dict[str, Any]] = []
    resolved = 0
    unresolved = 0

    for citation in citations:
        bib_key = resolve_citation(citation, author_year_index)
        if bib_key:
            resolved += 1
            findings.append(
                {
                    "gate": "citation_format",
                    "severity": "info",
                    "message": (f"Resolved: {citation['raw']} → @{bib_key}"),
                }
            )
        else:
            unresolved += 1
            findings.append(
                {
                    "gate": "citation_format",
                    "severity": "P1",
                    "message": (
                        f"Unresolved author-year citation: {citation['raw']}. "
                        f"No matching BibTeX key found."
                    ),
                }
            )

    # Summary
    findings.append(
        {
            "gate": "citation_format",
            "severity": "info",
            "message": (
                f"Citation format audit: {resolved} resolved, "
                f"{unresolved} unresolved out of {len(citations)} citations"
            ),
        }
    )

    return findings
