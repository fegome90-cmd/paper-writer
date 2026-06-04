"""Semantic Scholar API client for source verification.

Verifies sources and gets citation counts via the Semantic Scholar API.
Uses stdlib only (urllib, json). Returns S2Result(found=False) on
any network error — never raises.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from clients._retry import retry_with_backoff
from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD, title_similarity


@dataclass
class S2Result:
    """Result of a Semantic Scholar lookup."""

    found: bool
    paper_id: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    citation_count: int | None = None
    is_open_access: bool | None = None
    score: float = 0.0


class SemanticScholarClient:
    """Semantic Scholar API client for citation verification.

    Returns S2Result(found=False) on any error — never raises.
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    FIELDS = "title,authors,year,venue,citationCount,isOpenAccess,externalIds"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 10,
        offline: bool = False,
        sleep: Any = time.sleep,
        clock: Any = time.time,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.offline = offline
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float = 0.0
        self._latched_unavailable: bool = False

    def reset_outage_latch(self) -> None:
        """Reset the fail-fast outage latch."""
        self._latched_unavailable = False

    def verify_doi(self, doi: str) -> S2Result:
        """Verify a DOI against Semantic Scholar.

        Returns S2Result with found=True and metadata on success,
        or found=False on 404, network error, or offline mode.
        """
        if self.offline:
            return S2Result(found=False)

        try:
            encoded_doi = urllib.parse.quote(doi, safe="")
            path = f"/paper/DOI:{encoded_doi}?fields={self.FIELDS}"
            data = self._get(path)

            if not data or not data.get("paperId"):
                return S2Result(found=False)

            authors = [a.get("name", "") for a in data.get("authors", []) if a.get("name")]

            return S2Result(
                found=True,
                paper_id=data.get("paperId"),
                title=data.get("title"),
                authors=authors,
                year=data.get("year"),
                venue=data.get("venue"),
                citation_count=data.get("citationCount"),
                is_open_access=data.get("isOpenAccess"),
                score=1.0,
            )
        except Exception:
            return S2Result(found=False)

    def search_by_title(self, title: str, year: int | None = None) -> list[S2Result]:
        """Search Semantic Scholar by title, return results ranked by similarity.

        Returns list of S2Result with score = title_similarity.
        """
        if self.offline:
            return []

        try:
            encoded_title = urllib.parse.quote(title)
            path = f"/paper/search?query={encoded_title}&limit=5&fields={self.FIELDS}"
            data = self._get(path)

            if not data:
                return []

            candidates = data.get("data") or []
            results: list[S2Result] = []

            for cand in candidates:
                cand_title = cand.get("title") or ""
                sim = title_similarity(cand_title, title)
                if sim < TITLE_SIMILARITY_THRESHOLD:
                    continue

                authors = [a.get("name", "") for a in cand.get("authors", []) if a.get("name")]
                item_year = cand.get("year")
                
                # Tiebreaker logic (Item 7)
                year_match = year is not None and item_year == year
                score = sim + (0.05 if year_match else 0.0)

                results.append(
                    S2Result(
                        found=True,
                        paper_id=cand.get("paperId"),
                        title=cand_title,
                        authors=authors,
                        year=item_year,
                        venue=cand.get("venue"),
                        citation_count=cand.get("citationCount"),
                        is_open_access=cand.get("isOpenAccess"),
                        score=score,
                    )
                )

            results.sort(key=lambda r: -r.score)
            return results
        except Exception:
            return []

    def _get(self, path: str) -> dict[str, Any] | None:
        if self._latched_unavailable:
            logging.warning("S2 API latched unavailable (fail-fast)")
            return None

        """Single GET request with retry on 429."""
        url = f"{self.BASE_URL}{path}"
        headers = {"User-Agent": "paper-writer/0.1"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        req = urllib.request.Request(url, headers=headers)

        def _do_request() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]

        try:
            res = retry_with_backoff(
                _do_request,
                on_retry=lambda: setattr(self, "_last_request_at", self._clock()),
                sleep_fn=self._sleep,
            )
            if res:
                self._last_request_at = self._clock()
            return res
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            return None
        except (OSError, TimeoutError, urllib.error.URLError) as e:
            # Latch ONLY on transport errors, NOT on HTTP 404
            self._latched_unavailable = True
            logging.warning("S2 API I/O failure: %s", e)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.warning("Request failed: %s: %s", type(e).__name__, e)
            return None
        except Exception as e:
            logging.warning("S2 _get failed: %s: %s", type(e).__name__, e)
            return None
