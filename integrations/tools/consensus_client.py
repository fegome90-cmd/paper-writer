"""Consensus search provider — academic paper search via Consensus API.

Searches 200M+ peer-reviewed papers via the Consensus REST API.
OpenAPI spec: https://docs.consensus.app/reference/v1_quick_search

Supports filter parameters: year_min/max, study_types, human,
sample_size_min, sjr_max, exclude_preprints, medical_mode.

Requires CONSENSUS_API_KEY env var for authenticated access.
Falls back to unauthenticated mode (3 results/search) if no key is set.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from harness.ports.paper_search_provider import (
    NormalizedPaper,
    PaperSearchProvider,
    SearchProvenance,
    SearchProviderResult,
    _validate_query_and_limit,
    deduplicate_papers,
)

_BASE_URL = "https://api.consensus.app"
_SEARCH_PATH = "/v1/quick_search"
_REQUEST_TIMEOUT = 15  # seconds
_USER_AGENT = "paper-writer/1.0"


def _stable_hash(text: str) -> str:
    """Deterministic hash for source_id fallback. Not cryptographically secure."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# Valid study types from Consensus API spec
VALID_STUDY_TYPES = frozenset(
    {
        "rct",
        "meta-analysis",
        "systematic review",
        "literature review",
        "case report",
        "non-rct experimental",
        "non-rct observational study",
        "non-rct in vitro",
        "animal",
    }
)


class ConsensusSearchProvider(PaperSearchProvider):
    """Search academic papers via the Consensus REST API.

    Authentication:
        - Set CONSENSUS_API_KEY env var for Pro access (20 results/search)
        - Without key: unauthenticated mode (3 results/search, unlimited queries)

    Graceful degradation:
        - No API key → unauthenticated mode with warning
        - Network errors → RuntimeError with details
        - Malformed responses → skip bad results, keep good ones
    """

    def __init__(self, *, api_key: str | None = None, timeout: int = _REQUEST_TIMEOUT) -> None:
        self._api_key = api_key or os.environ.get("CONSENSUS_API_KEY", "")
        self._timeout = timeout

    @property
    def is_authenticated(self) -> bool:
        """Whether an API key is configured."""
        return bool(self._api_key)

    _MAX_RESULTS_PER_PAGE = 20

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        limit: int = 20,
    ) -> SearchProviderResult:
        """Search Consensus for peer-reviewed papers.

        Args:
            query: Natural language research question or keywords.
            sources: Ignored — Consensus searches its own index.
            limit: Max results (1-20). API limit is 20 per page.

        Returns:
            SearchProviderResult with normalized papers.

        Raises:
            RuntimeError: Network or API errors.
            TimeoutError: If the request times out.
            ValueError: Invalid query or limit > 20.
        """
        # Shared baseline validation first, then provider-specific constraint
        _validate_query_and_limit(query, limit)
        if limit > self._MAX_RESULTS_PER_PAGE:
            raise ValueError(
                f"Consensus limit must be 1-{self._MAX_RESULTS_PER_PAGE}, got {limit}. "
                "The Consensus API returns at most 20 results per page."
            )

        raw_payload = self._call_api(query, limit)
        results = raw_payload.get("results", [])

        papers: list[NormalizedPaper] = []
        for raw in results:
            try:
                papers.append(self._normalize(raw))
            except (KeyError, TypeError, ValueError) as exc:
                # Skip malformed results — log for debugging
                logger.warning("Skipping malformed Consensus paper: %s", exc)
                continue

        papers = deduplicate_papers(papers)[:limit]

        return SearchProviderResult(
            papers=papers,
            raw_payload=raw_payload,
            provenance=SearchProvenance(
                provider="consensus",
                query=query,
                retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
                tool_name="consensus_quick_search",
                sources=["consensus"],
                server_info={
                    "authenticated": str(self.is_authenticated),
                    "base_url": _BASE_URL,
                },
            ),
        )

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _call_api(self, query: str, limit: int, **filters: Any) -> dict[str, Any]:
        """Make the HTTP GET request to Consensus quick_search.

        Per OpenAPI spec: only `query` is required. No `limit` param —
        result count is determined by plan tier (3/10/20).
        """
        params: dict[str, str | list[str]] = {"query": query}

        # Apply OpenAPI spec filter parameters
        if filters.get("year_min"):
            params["year_min"] = str(filters["year_min"])
        if filters.get("year_max"):
            params["year_max"] = str(filters["year_max"])
        if filters.get("study_types"):
            params["study_types"] = filters["study_types"]
        if filters.get("human"):
            params["human"] = "true"
        if filters.get("sample_size_min"):
            params["sample_size_min"] = str(filters["sample_size_min"])
        if filters.get("sjr_max"):
            params["sjr_max"] = str(filters["sjr_max"])
        if filters.get("exclude_preprints"):
            params["exclude_preprints"] = "true"
        if filters.get("medical_mode"):
            params["medical_mode"] = "true"

        encoded = urllib.parse.urlencode(params, doseq=True)
        url = f"{_BASE_URL}{_SEARCH_PATH}?{encoded}"

        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key

        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)  # type: ignore[no-any-return]
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except (OSError, ConnectionError):
                detail = "(no response body)"
            raise RuntimeError(f"Consensus API HTTP {e.code}: {detail}") from e
        except TimeoutError as e:
            raise TimeoutError(f"Consensus API request timed out after {self._timeout}s") from e
        except urllib.error.URLError as e:
            if "timed out" in str(e.reason):
                raise TimeoutError(f"Consensus API request timed out after {self._timeout}s") from e
            raise RuntimeError(f"Consensus API network error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Consensus API returned invalid JSON: {e}") from e

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> NormalizedPaper:
        """Convert a Consensus API result to NormalizedPaper.

        Consensus returns: title, authors, abstract, journal_name,
        publish_year, doi, url, citation_count, study_type, takeaway.
        """
        defaulted: list[str] = []
        warnings: list[str] = []

        title = raw.get("title", "")
        if not title:
            raise ValueError("Paper has no title — skipping")

        doi = raw.get("doi") or None
        if not doi:
            defaulted.append("doi")

        year = raw.get("publish_year", 0)
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

        # Extract extra Consensus-specific fields (per OpenAPI spec)
        extra_fields: dict[str, Any] = {}
        if raw.get("study_type"):
            if raw["study_type"] in VALID_STUDY_TYPES:
                extra_fields["study_type"] = raw["study_type"]
            else:
                extra_fields["study_type"] = raw["study_type"]
                warnings.append(f"Unknown study_type: {raw['study_type']}")
        if raw.get("takeaway"):
            extra_fields["takeaway"] = raw["takeaway"]
        if raw.get("journal_name"):
            extra_fields["journal_name"] = raw["journal_name"]
        if raw.get("volume"):
            extra_fields["volume"] = raw["volume"]
        if raw.get("pages"):
            extra_fields["pages"] = raw["pages"]

        return NormalizedPaper(
            title=title,
            doi=doi,
            pmid=None,
            year=year if isinstance(year, int) and year >= 1900 else 0,
            authors=authors,
            abstract=abstract,
            url=url,
            pdf_url=None,
            source_platform="consensus",
            source_id=doi or raw.get("url", "") or f"consensus:{_stable_hash(title)}",
            categories=[],
            citations_count=citations_count,
            extra_fields=extra_fields if extra_fields else None,
            defaulted_fields=defaulted,
            warnings=warnings,
        )
