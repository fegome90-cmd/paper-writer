"""OpenAlex API client for citation verification.

Verifies DOIs and titles against the OpenAlex REST API.
Uses stdlib only (urllib, json). Returns OpenAlexResult(found=False) on
any network error — never raises.

OpenAlex provides open metadata for academic works, including
citation counts, open access status, and venue information.
Useful as a third verification source alongside Crossref and S2.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from clients._retry import retry_with_backoff
from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD, title_similarity


@dataclass
class OpenAlexResult:
    """Result of an OpenAlex lookup."""

    found: bool
    doi: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    is_oa: bool | None = None
    citation_count: int | None = None
    openalex_id: str | None = None
    score: float = 0.0


def _extract_authors(work: dict[str, Any]) -> list[str]:
    """Extract author display names from OpenAlex authorships."""
    names: list[str] = []
    for authorship in work.get("authorships", []):
        author = authorship.get("author", {})
        name = author.get("display_name", "")
        if name:
            names.append(name)
    return names


def _extract_venue(work: dict[str, Any]) -> str | None:
    """Extract venue name from OpenAlex primary_location."""
    location = work.get("primary_location")
    if not isinstance(location, dict):
        return None
    source = location.get("source")
    if not isinstance(source, dict):
        return None
    return source.get("display_name") or None


class OpenAlexClient:
    """OpenAlex API client for citation verification.

    Uses the polite pool (mailto parameter) when email is provided
    (falls back to OPENALEX_EMAIL env var).
    Returns OpenAlexResult(found=False) on any error — never raises.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        email: str | None = None,
        timeout: int = 10,
        offline: bool = False,
        sleep: Any = time.sleep,
        clock: Any = time.time,
    ) -> None:
        self.email = email or os.environ.get("OPENALEX_EMAIL")
        self.timeout = timeout
        self.offline = offline
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float = 0.0
        self._latched_unavailable: bool = False

    def reset_outage_latch(self) -> None:
        """Reset the fail-fast outage latch."""
        self._latched_unavailable = False

    def verify_doi(self, doi: str) -> OpenAlexResult:
        """Verify a DOI against OpenAlex.

        Returns OpenAlexResult with found=True and metadata on success,
        or found=False on 404, network error, or offline mode.
        """
        if self.offline:
            return OpenAlexResult(found=False)

        # OpenAlex uses DOI URL as identifier: https://doi.org/10.1234/...
        encoded = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
        try:
            data = self._get(f"/works/doi:{encoded}", {})
            if not data:
                return OpenAlexResult(found=False)

            return self._parse_work(data, score=1.0)
        except Exception:
            return OpenAlexResult(found=False)

    def search_by_title(self, title: str, year: int | None = None) -> list[OpenAlexResult]:
        """Search OpenAlex by title, return results ranked by similarity.

        Returns list of OpenAlexResult with score = title_similarity.
        """
        if self.offline:
            return []

        try:
            params: dict[str, str] = {
                "search": title,
                "per_page": "5",
            }
            if year is not None:
                params["filter"] = f"publication_year:{year}"

            data = self._get("/works", params)
            if not data:
                return []

            results: list[OpenAlexResult] = []
            for work in data.get("results", []):
                result = self._parse_work(work)
                if result.title is None:
                    continue

                sim = title_similarity(result.title, title)
                if sim < TITLE_SIMILARITY_THRESHOLD:
                    continue

                # Year match tiebreaker
                year_match = year is not None and result.year == year
                result.score = sim + (0.05 if year_match else 0.0)
                results.append(result)

            results.sort(key=lambda r: -r.score)
            return results
        except Exception:
            return []

    def _parse_work(self, work: dict[str, Any], score: float = 0.0) -> OpenAlexResult:
        """Parse an OpenAlex work JSON into OpenAlexResult."""
        title = work.get("title") or work.get("display_name")
        doi_raw = work.get("doi") or ""
        # OpenAlex returns DOIs as full URLs: strip the prefix
        doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
        authors = _extract_authors(work)
        year = work.get("publication_year")
        venue = _extract_venue(work)
        is_oa = work.get("open_access", {}).get("is_oa")
        citation_count = work.get("cited_by_count")
        openalex_id = work.get("id")

        return OpenAlexResult(
            found=True,
            doi=doi,
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            is_oa=is_oa,
            citation_count=citation_count,
            openalex_id=openalex_id,
            score=score,
        )

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any] | None:
        """Single GET request with retry on 429."""
        if self._latched_unavailable:
            logging.warning("OpenAlex API latched unavailable (fail-fast)")
            return None

        url = f"{self.BASE_URL}{path}"
        if self.email:
            query["mailto"] = self.email
        if query:
            url += "?" + urllib.parse.urlencode(query)

        ua = "paper-writer/0.1"
        req = urllib.request.Request(url, headers={"User-Agent": ua})

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
            self._latched_unavailable = True
            logging.warning("OpenAlex API I/O failure: %s", e)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.warning("Request failed: %s: %s", type(e).__name__, e)
            return None
        except Exception as e:
            logging.warning("_get failed: %s: %s", type(e).__name__, e)
            return None
