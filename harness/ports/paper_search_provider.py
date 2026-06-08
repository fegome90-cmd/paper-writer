"""Port for paper search providers.

Defines the PaperSearchProvider interface with two implementations:
- FixturePaperSearchProvider: deterministic test data from JSON fixture
- McpPaperSearchProvider: real academic search via paper-mcp server

Provider selection is explicit via PAPER_SEARCH_PROVIDER env var.
No silent fallback between providers.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Data types ────────────────────────────────────────────────────────


class NormalizedPaper:
    """A paper normalized from MCP (or fixture) into paper-writer format.

    Tracks which fields were defaulted so consumers can distinguish
    'MCP returned null' from 'field was computed'.
    """

    def __init__(
        self,
        *,
        title: str,
        doi: str | None,
        pmid: str | None,
        year: int,
        authors: str,
        abstract: str,
        url: str | None,
        pdf_url: str | None,
        source_platform: str,
        source_id: str,
        categories: list[str],
        citations_count: int,
        extra_fields: dict[str, Any] | None = None,
        defaulted_fields: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.title = title
        self.doi = doi
        self.pmid = pmid
        self.year = year
        self.authors = authors
        self.abstract = abstract
        self.url = url
        self.pdf_url = pdf_url
        self.source_platform = source_platform
        self.source_id = source_id
        self.categories = categories
        self.citations_count = citations_count
        self.extra_fields = extra_fields or {}
        self.defaulted_fields = defaulted_fields or []
        self.warnings = warnings or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to paper-writer internal dict format."""
        d: dict[str, Any] = {
            "title": self.title,
            "doi": self.doi,
            "pmid": self.pmid,
            "year": self.year,
            "authors": self.authors,
            "abstract": self.abstract,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "source_platform": self.source_platform,
            "source_id": self.source_id,
            "categories": self.categories,
            "citations_count": self.citations_count,
            "normalization": {
                "defaulted_fields": self.defaulted_fields,
                "warnings": self.warnings,
            },
        }
        if self.extra_fields:
            d["extra_fields"] = self.extra_fields
        return d


class SearchProvenance:
    """Metadata tracking where search results came from."""

    def __init__(
        self,
        *,
        provider: str,
        query: str,
        retrieved_at: str,
        tool_name: str,
        sources: list[str],
        schema_version: str = "1.0",
        server_info: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.query = query
        self.retrieved_at = retrieved_at
        self.tool_name = tool_name
        self.sources = sources
        self.schema_version = schema_version
        self.server_info = server_info or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "retrieved_at": self.retrieved_at,
            "tool_name": self.tool_name,
            "sources": self.sources,
            "schema_version": self.schema_version,
            "server_info": self.server_info,
        }


class SearchProviderResult:
    """Result from a paper search provider."""

    def __init__(
        self,
        *,
        papers: list[NormalizedPaper],
        raw_payload: dict[str, Any],
        provenance: SearchProvenance,
    ) -> None:
        self.papers = papers
        self.raw_payload = raw_payload
        self.provenance = provenance

    @property
    def total_from_source(self) -> int:
        return self.raw_payload.get("total", 0)


# ── Protocol ──────────────────────────────────────────────────────────


class PaperSearchProvider(ABC):
    """Minimal interface for paper search providers.

    Implementations must NOT silently fall back to another provider.
    Fail visibly in case of errors.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> SearchProviderResult:
        """Search for academic papers.

        Args:
            query: Search query string.
            sources: Platform sources to search (e.g., ["arxiv", "pubmed"]).
            limit: Maximum results per platform (1-100).
            **kwargs: Provider-specific filter parameters (e.g., year_min,
                study_types for Consensus). Ignored by providers that don't
                support them.

        Returns:
            SearchProviderResult with normalized papers and provenance.

        Raises:
            RuntimeError: If the provider fails to return results.
            TimeoutError: If the provider times out.
            ValueError: If query is empty or limit is out of range.
        """
        ...


# ── Normalization ─────────────────────────────────────────────────────


def _normalize_paper(raw: dict[str, Any]) -> NormalizedPaper:
    """Normalize a single MCP result into paper-writer format.

    Tracks defaulted fields to avoid silent semantic loss.
    """
    defaulted: list[str] = []
    warnings: list[str] = []

    # Title — required
    title = raw.get("title", "")
    if not title:
        title = "(untitled)"
        defaulted.append("title")
        warnings.append("Paper has no title — using placeholder")

    # DOI — optional
    doi = raw.get("doi")
    if doi is None:
        defaulted.append("doi")

    # PMID — only for pubmed
    pmid: str | None = None
    if raw.get("source") == "pubmed":
        pmid = str(raw.get("id", ""))
        if not pmid:
            defaulted.append("pmid")

    # Year from published
    published = raw.get("published", "")
    year = 0
    if published and len(published) >= 4:
        try:
            year = int(published[:4])
        except ValueError:
            defaulted.append("year")
            warnings.append(f"Could not parse year from published: {published}")
    else:
        defaulted.append("year")
        warnings.append("No published date available")

    # Authors — format as string
    raw_authors = raw.get("authors", [])
    if raw_authors:
        if len(raw_authors) > 3:
            authors = ", ".join(str(a) for a in raw_authors[:3]) + " et al."
        else:
            authors = ", ".join(str(a) for a in raw_authors)
    else:
        authors = ""
        defaulted.append("authors")

    # Abstract — may be empty, None, or absent
    abstract = raw.get("abstract") or ""
    if abstract == "":
        defaulted.append("abstract")

    # URL — optional
    url = raw.get("url")

    # PDF URL — optional
    pdf_url = raw.get("pdfUrl")
    if pdf_url is None:
        defaulted.append("pdf_url")

    # Source platform
    source_platform = raw.get("source", "unknown")

    # Source ID
    source_id = str(raw.get("id", ""))
    if not source_id:
        defaulted.append("source_id")

    # Categories — may be absent
    categories = raw.get("categories") or []

    # Citations count — may be absent (OpenAlex-only)
    if "citations" in raw:
        citations_count = raw["citations"] or 0
    else:
        citations_count = 0
        defaulted.append("citations_count")

    # Capture unexpected extra fields
    known_keys = {
        "id",
        "title",
        "authors",
        "abstract",
        "published",
        "source",
        "doi",
        "pdfUrl",
        "url",
        "categories",
        "fullTextAvailable",
        "citations",
    }
    extra_fields = {k: v for k, v in raw.items() if k not in known_keys}

    return NormalizedPaper(
        title=title,
        doi=doi,
        pmid=pmid,
        year=year,
        authors=authors,
        abstract=abstract,
        url=url,
        pdf_url=pdf_url,
        source_platform=source_platform,
        source_id=source_id,
        categories=categories,
        citations_count=citations_count,
        extra_fields=extra_fields if extra_fields else None,
        defaulted_fields=defaulted,
        warnings=warnings,
    )


def deduplicate_papers(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    """Remove duplicates based on DOI or title similarity across sources.

    Keeps the version with more populated fields.
    """
    seen_dois: dict[str, int] = {}
    seen_titles: dict[str, int] = {}
    result: list[NormalizedPaper] = []

    for i, paper in enumerate(papers):
        # DOI-based dedup
        if paper.doi:
            doi_key = paper.doi.lower().strip().rstrip("/")
            if doi_key in seen_dois:
                # Keep the one with fewer defaulted fields
                existing_idx = seen_dois[doi_key]
                existing_defaults = len(papers[existing_idx].defaulted_fields)
                current_defaults = len(paper.defaulted_fields)
                if current_defaults < existing_defaults:
                    # Replace with richer version
                    result[existing_idx] = paper
                continue
            seen_dois[doi_key] = i

        # Title-based dedup (normalized)
        title_key = paper.title.lower().strip()
        if title_key in seen_titles:
            continue
        seen_titles[title_key] = i

        result.append(paper)

    return result


# ── Fixture Provider ──────────────────────────────────────────────────

_DEFAULT_FIXTURE_PATH = (
    Path(__file__).parent.parent.parent
    / "tests"
    / "fixtures"
    / "paper_mcp"
    / "search_papers_response.v1.json"
)

_DEFAULT_SOURCES = ["openalex", "pubmed", "arxiv", "consensus"]


class FixturePaperSearchProvider(PaperSearchProvider):
    """Deterministic provider from JSON fixture for tests."""

    def __init__(self, fixture_path: Path | None = None) -> None:
        self._fixture_path = fixture_path or _DEFAULT_FIXTURE_PATH

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> SearchProviderResult:
        _validate_query_and_limit(query, limit)

        if not self._fixture_path.exists():
            raise RuntimeError(f"Fixture file not found: {self._fixture_path}")

        raw = json.loads(self._fixture_path.read_text(encoding="utf-8"))

        papers = [_normalize_paper(r) for r in raw.get("results", [])]
        papers = deduplicate_papers(papers)[:limit]

        return SearchProviderResult(
            papers=papers,
            raw_payload=raw,
            provenance=SearchProvenance(
                provider="fixture",
                query=query,
                retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
                tool_name="search_papers",
                sources=sources or _DEFAULT_SOURCES,
            ),
        )


# ── Validation helpers ────────────────────────────────────────────────


def _validate_query_and_limit(query: str, limit: int) -> None:
    """Shared validation for all providers."""
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    if limit < 1 or limit > 100:
        raise ValueError(f"Limit must be between 1 and 100, got {limit}")


# ── Provider factory ──────────────────────────────────────────────────


def create_search_provider(
    *,
    fixture_path: Path | None = None,
) -> PaperSearchProvider:
    """Create the appropriate provider based on PAPER_SEARCH_PROVIDER env var.

    Modes:
        - "fixture": deterministic test data (default)
        - "mcp": real MCP server via SDK
        - "consensus": Consensus REST API (200M+ peer-reviewed papers)

    Never falls back silently. In MCP/Consensus mode, failures are visible errors.
    """
    mode = os.environ.get("PAPER_SEARCH_PROVIDER", "fixture").lower()

    if mode == "fixture":
        return FixturePaperSearchProvider(fixture_path=fixture_path)

    if mode == "mcp":
        # Import here to avoid requiring mcp SDK for fixture mode
        from integrations.tools.mcp_paper_client import McpPaperSearchProvider

        return McpPaperSearchProvider()

    if mode == "consensus":
        from integrations.tools.consensus_client import ConsensusSearchProvider

        return ConsensusSearchProvider()

    raise ValueError(
        f"Unknown PAPER_SEARCH_PROVIDER: {mode!r}. Must be 'fixture', 'mcp', or 'consensus'."
    )
