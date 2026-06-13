"""Consensus remote MCP search provider — academic search via Consensus MCP Server.

Connects to the official remote Consensus MCP server over HTTP SSE transport:
https://mcp.consensus.app/mcp

Supports authenticated access via Bearer Token (using CONSENSUS_MCP_API_KEY)
or unauthenticated access (anonymous mode, returns 3 papers per query).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from harness.ports.paper_search_provider import (
    NormalizedPaper,
    PaperSearchProvider,
    SearchProvenance,
    SearchProviderResult,
    _validate_query_and_limit,
    deduplicate_papers,
)

logger = logging.getLogger(__name__)

_DEFAULT_URL = "https://mcp.consensus.app/mcp"
_REQUEST_TIMEOUT = 15  # seconds


def _stable_hash(text: str) -> str:
    """Deterministic hash for source_id fallback. Not cryptographically secure."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


class ConsensusRemoteMcpSearchProvider(PaperSearchProvider):
    """Search academic papers via the remote Consensus MCP server over SSE.

    Authentication:
        - Set CONSENSUS_MCP_API_KEY env var for Bearer auth (Pro/Enterprise tier limits)
        - Without key: unauthenticated mode (3 results/search, unlimited queries)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        url: str | None = None,
        timeout: int = _REQUEST_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.environ.get("CONSENSUS_MCP_API_KEY", "")
        self._url = url or os.environ.get("CONSENSUS_MCP_URL", _DEFAULT_URL)
        self._timeout = timeout

        if not self._url.startswith("https://") and not (
            self._url.startswith("http://localhost") or self._url.startswith("http://127.0.0.1")
        ):
            raise ValueError(f"Consensus remote MCP URL must be secure HTTPS: {self._url}")

    @property
    def supported_filters(self) -> list[str]:
        """Filter parameters supported by the Consensus MCP search tool."""
        return [
            "year_min",
            "year_max",
            "study_types",
            "human",
            "sample_size_min",
            "sjr_max",
            "duration_min",
            "duration_max",
            "exclude_preprints",
            "medical_mode",
        ]

    @property
    def is_authenticated(self) -> bool:
        """Whether an API key (Bearer token) is configured."""
        return bool(self._api_key)

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
        **filters: Any,
    ) -> SearchProviderResult:
        """Search Consensus for peer-reviewed papers.

        Args:
            query: Natural language research question or keywords.
            sources: Ignored.
            limit: Max results (1-20). MCP server defaults results based on plan.
            **filters: Filter parameters forwarded to the MCP search tool.

        Returns:
            SearchProviderResult with normalized papers.
        """
        _validate_query_and_limit(query, limit)

        # Run async implementation in event loop using ThreadPoolExecutor bridge
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._search_async(query, limit=limit, **filters),
                )
                return future.result(timeout=self._timeout + 5)
        else:
            return asyncio.run(self._search_async(query, limit=limit, **filters))

    async def _search_async(self, query: str, limit: int = 20, **filters: Any) -> SearchProviderResult:
        """Async implementation of search connecting over SSE."""
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        else:
            logger.warning(
                "No CONSENSUS_MCP_API_KEY set. Running Consensus MCP in unauthenticated mode "
                "(limit: 3 papers per query)."
            )

        # Build parameters
        arguments: dict[str, Any] = {"query": query}

        if filters.get("year_min") is not None:
            arguments["year_min"] = int(filters["year_min"])
        if filters.get("year_max") is not None:
            arguments["year_max"] = int(filters["year_max"])
        if filters.get("study_types") is not None:
            study_val = filters["study_types"]
            if isinstance(study_val, list):
                arguments["study_types"] = [str(v) for v in study_val]
            else:
                arguments["study_types"] = [str(study_val)]
        if filters.get("human") is not None:
            arguments["human"] = bool(filters["human"])
        if filters.get("sample_size_min") is not None:
            arguments["sample_size_min"] = int(filters["sample_size_min"])
        if filters.get("sjr_max") is not None:
            sjr = int(filters["sjr_max"])
            if not (1 <= sjr <= 4):
                raise ValueError(f"sjr_max must be between 1 and 4, got {sjr}")
            arguments["sjr_max"] = sjr
        if filters.get("exclude_preprints") is not None:
            arguments["exclude_preprints"] = bool(filters["exclude_preprints"])
        if filters.get("medical_mode") is not None:
            arguments["medical_mode"] = bool(filters["medical_mode"])
        if filters.get("duration_min") is not None:
            arguments["duration_min"] = int(filters["duration_min"])
        if filters.get("duration_max") is not None:
            arguments["duration_max"] = int(filters["duration_max"])

        try:
            # 1. Establish Streamable HTTP Connection
            async with httpx.AsyncClient(headers=headers) as http_client:
                async with streamable_http_client(self._url, http_client=http_client) as streams:
                    read_stream, write_stream = streams[0], streams[1]
                    # 2. Establish Client Session
                    async with ClientSession(read_stream, write_stream) as session:
                        # 3. Negotiate capabilities (Initialize)
                        try:
                            init_result = await asyncio.wait_for(
                                session.initialize(),
                                timeout=self._timeout,
                            )
                        except asyncio.TimeoutError as exc:
                            raise TimeoutError(
                                f"Consensus remote MCP initialization timed out after {self._timeout}s"
                            ) from exc

                        server_info = {
                            "name": init_result.serverInfo.name,
                            "version": init_result.serverInfo.version,
                            "url": self._url,
                            "authenticated": str(self.is_authenticated),
                        }

                        # 4. Call search tool
                        try:
                            tool_result = await asyncio.wait_for(
                                session.call_tool("search", arguments=arguments),
                                timeout=self._timeout,
                            )
                        except asyncio.TimeoutError as exc:
                            raise TimeoutError(
                                f"Consensus remote MCP search tool timed out after {self._timeout}s"
                            ) from exc

                        # 5. Parse response content
                        if not tool_result.content:
                            raise RuntimeError("Consensus remote MCP search returned empty response content")

                        from mcp.types import TextContent

                        first_content = tool_result.content[0]
                        if not isinstance(first_content, TextContent):
                            raise RuntimeError(
                                f"Consensus remote MCP returned non-text response type: {type(first_content).__name__}"
                            )

                        text = first_content.text
                        try:
                            raw = json.loads(text)
                        except (json.JSONDecodeError, ValueError) as exc:
                            raise RuntimeError(f"Consensus remote MCP returned invalid JSON: {exc}") from exc

                        if "error" in raw:
                            raise RuntimeError(f"Consensus remote MCP tool error: {raw['error']}")

                        # The search tool response schema returns a dictionary with key "papers" (array)
                        # and "total_results" (int)
                        papers_raw = raw.get("papers", [])
                        if not isinstance(papers_raw, list):
                            raise RuntimeError(
                                f"Consensus remote MCP returned non-list papers: {type(papers_raw).__name__}"
                            )

                        normalized_papers: list[NormalizedPaper] = []
                        for p_raw in papers_raw:
                            if not isinstance(p_raw, dict):
                                continue
                            try:
                                normalized_papers.append(self._normalize(p_raw))
                            except (ValueError, KeyError, TypeError) as exc:
                                logger.warning("Skipping malformed Consensus remote MCP paper: %s", exc)
                                continue

                        normalized_papers = deduplicate_papers(normalized_papers)[:limit]

                        return SearchProviderResult(
                            papers=normalized_papers,
                            raw_payload=raw,
                            provenance=SearchProvenance(
                                provider="consensus_mcp_remote",
                                query=query,
                                retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
                                tool_name="search",
                                sources=["consensus"],
                                server_info=server_info,
                            ),
                        )

        except TimeoutError:
            raise
        except Exception as exc:
            # Translate HTTP exceptions or rate limit warnings when possible
            exc_str = str(exc)
            if "401" in exc_str:
                raise RuntimeError(
                    f"Consensus remote MCP authentication failed (401). "
                    f"Please verify your CONSENSUS_MCP_API_KEY."
                ) from exc
            if "429" in exc_str:
                raise RuntimeError(
                    f"Consensus remote MCP rate limit exceeded (429). Please try again later."
                ) from exc
            raise RuntimeError(f"Consensus remote MCP connection failed: {exc}") from exc

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> NormalizedPaper:
        """Convert a Consensus MCP paper object to NormalizedPaper."""
        defaulted: list[str] = []
        warnings: list[str] = []

        title = raw.get("title", "")
        if not title:
            raise ValueError("Paper has no title — skipping")

        doi = raw.get("doi") or None
        if not doi:
            defaulted.append("doi")

        year = raw.get("year", 0)
        if not isinstance(year, int) or year < 1900:
            defaulted.append("year")

        raw_authors = raw.get("authors", [])
        if raw_authors:
            if len(raw_authors) > 3:
                authors = ", ".join(str(a) for a in raw_authors[:3]) + " et al."
            else:
                authors = ", ".join(str(a) for a in raw_authors)
        else:
            authors = ""
            defaulted.append("authors")

        abstract = raw.get("abstract") or ""
        if not abstract:
            defaulted.append("abstract")

        url = raw.get("url")

        citations_count = raw.get("citation_count", 0) or 0

        # Extract extra fields
        extra_fields: dict[str, Any] = {}
        if raw.get("study_type"):
            extra_fields["study_type"] = raw["study_type"]
        if raw.get("takeaway"):
            extra_fields["takeaway"] = raw["takeaway"]
        if raw.get("journal"):
            extra_fields["journal_name"] = raw["journal"]

        # Parse Consensus paper ID if possible
        paper_id = raw.get("id")
        if not paper_id and url:
            import re

            match = re.search(r"/papers/details/([a-zA-Z0-9]{32})", url)
            if match:
                paper_id = match.group(1)

        source_id = doi or paper_id or url or f"consensus_mcp:{_stable_hash(title)}"

        return NormalizedPaper(
            title=title,
            doi=doi,
            pmid=None,
            year=year if isinstance(year, int) and year >= 1900 else 0,
            authors=authors,
            abstract=abstract,
            url=url,
            pdf_url=None,
            source_platform="consensus_mcp_remote",
            source_id=source_id,
            categories=[],
            citations_count=citations_count,
            extra_fields=extra_fields if extra_fields else None,
            defaulted_fields=defaulted,
            warnings=warnings,
        )
