"""Crossref API client for DOI verification.

Verifies DOIs against the Crossref REST API to catch fabricated citations.
Uses stdlib only (urllib, json). Returns CrossrefResult(found=False) on
any network error — never raises.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from clients._retry import retry_with_backoff
from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD, title_similarity


@dataclass
class CrossrefResult:
    """Result of a Crossref lookup."""

    found: bool
    doi: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    is_oa: bool | None = None
    score: float = 0.0


def _extract_title(message: dict[str, Any]) -> str:
    """Crossref returns title as a list of language variants. Take first."""
    titles = message.get("title") or []
    return titles[0] if titles else ""


def _extract_year(item: dict[str, Any]) -> int | None:
    """Extract publication year from Crossref date-parts."""
    for key in ("issued", "published-print", "published-online"):
        val = item.get(key)
        if not isinstance(val, dict):
            continue
        date_parts = val.get("date-parts")
        if date_parts and date_parts[0]:
            return int(date_parts[0][0])
    return None


def _extract_authors(item: dict[str, Any]) -> list[str]:
    """Extract author names from Crossref response."""
    authors = []
    for author in item.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        if given or family:
            authors.append(f"{given} {family}".strip())
    return authors


class CrossrefClient:
    """Crossref API client for DOI verification.

    Uses the polite pool (mailto in User-Agent) when email is provided.
    Returns CrossrefResult(found=False) on any error — never raises.
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(
        self,
        email: str | None = None,
        timeout: int = 10,
        offline: bool = False,
    ) -> None:
        self.email = email
        self.timeout = timeout
        self.offline = offline

    def verify_doi(self, doi: str) -> CrossrefResult:
        """Verify a DOI against Crossref.

        Returns CrossrefResult with found=True and metadata on success,
        or found=False on 404, network error, or offline mode.
        """
        if self.offline:
            return CrossrefResult(found=False)

        try:
            data = self._get(f"/works/{doi}", {})
            if not data:
                return CrossrefResult(found=False)

            message = data.get("message", {})
            title = _extract_title(message)
            authors = _extract_authors(message)
            year = _extract_year(message)
            venue_list = message.get("container-title") or []
            venue = venue_list[0] if venue_list else None
            is_oa = None
            licenses = message.get("license") or []
            if licenses:
                is_oa = any(
                    "creativecommons" in lic.get("URL", "") for lic in licenses
                )

            return CrossrefResult(
                found=True,
                doi=doi,
                title=title,
                authors=authors,
                year=year,
                venue=venue,
                is_oa=is_oa,
                score=1.0,
            )
        except Exception:
            return CrossrefResult(found=False)

    def search_by_title(self, title: str) -> list[CrossrefResult]:
        """Search Crossref by title, return results ranked by similarity.

        Returns list of CrossrefResult with score = title_similarity.
        """
        if self.offline:
            return []

        try:
            data = self._get("/works", {"query.title": title, "rows": "5"})
            if not data:
                return []

            candidates = data.get("message", {}).get("items", [])
            results: list[CrossrefResult] = []

            for cand in candidates:
                cand_title = _extract_title(cand)
                sim = title_similarity(cand_title, title)
                if sim < TITLE_SIMILARITY_THRESHOLD:
                    continue

                authors = _extract_authors(cand)
                year = _extract_year(cand)
                venue_list = cand.get("container-title") or []
                venue = venue_list[0] if venue_list else None
                results.append(CrossrefResult(
                    found=True,
                    doi=cand.get("DOI"),
                    title=cand_title,
                    authors=authors,
                    year=year,
                    venue=venue,
                    score=sim,
                ))

            results.sort(key=lambda r: -r.score)
            return results
        except Exception:
            return []

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any] | None:
        """Single GET request with retry on 429."""
        url = f"{self.BASE_URL}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)

        ua = "paper-writer/0.1"
        if self.email:
            ua += f" (mailto:{self.email})"

        req = urllib.request.Request(url, headers={"User-Agent": ua})

        def _do_request() -> dict[str, Any]:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]

        try:
            return retry_with_backoff(_do_request)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            return None
        except Exception:
            return None
