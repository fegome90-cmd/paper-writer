"""arXiv API client for citation verification.

Verifies arXiv IDs and titles against the arXiv API.
Uses stdlib only (urllib, xml.etree.ElementTree). Returns
ArxivResult(found=False) on any network error — never raises.

Key differences from Crossref/OpenAlex clients:
  - arXiv API returns Atom 1.0 XML, NOT JSON.
  - Namespace: {http://www.w3.org/2005/Atom}
  - Lookup by arXiv ID via ?id_list={id}
  - Title search via ?search_query=ti:"{title}"
  - arXiv asks callers to wait ~3s between requests
    (https://info.arxiv.org/help/api/tou.html)

Ported from ARS arxiv_client.py (Delta 1) adapted to our
data model (ArxivResult dataclass, outage latch, retry_with_backoff).
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from clients._retry import retry_with_backoff
from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD, title_similarity

# arXiv Atom namespace
_ATOM_NS = "{http://www.w3.org/2005/Atom}"

# arXiv API Terms of Use ask callers to pace requests ~3s apart.
_ARXIV_MIN_INTERVAL = 3.0


@dataclass
class ArxivResult:
    """Result of an arXiv lookup."""

    found: bool
    arxiv_id: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    categories: list[str] = field(default_factory=list)
    score: float = 0.0


def _extract_title(entry: ET.Element) -> str:
    """Extract and normalize title from Atom <entry>.

    arXiv collapses internal whitespace/newlines in the title,
    so normalize runs of whitespace to single spaces.
    """
    node = entry.find(f"{_ATOM_NS}title")
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.split())


def _extract_year(entry: ET.Element) -> int | None:
    """Extract year from Atom <entry><published>.

    ISO-8601 format (e.g. 2017-06-12T...). Returns None when absent.
    """
    node = entry.find(f"{_ATOM_NS}published")
    if node is None or not node.text:
        return None
    head = node.text[:4]
    return int(head) if head.isdigit() else None


def _extract_authors(entry: ET.Element) -> list[str]:
    """Extract author names from Atom <entry><author><name>."""
    names: list[str] = []
    for author_node in entry.findall(f"{_ATOM_NS}author"):
        name_node = author_node.find(f"{_ATOM_NS}name")
        if name_node is not None and name_node.text:
            names.append(name_node.text.strip())
    return names


def _extract_arxiv_id(entry: ET.Element) -> str | None:
    """Extract arXiv ID from Atom <entry><id>.

    Format: http://arxiv.org/abs/2301.00001v1
    Returns just the ID portion: 2301.00001v1
    """
    node = entry.find(f"{_ATOM_NS}id")
    if node is None or not node.text:
        return None
    url = node.text.strip()
    # Extract ID from URL
    if "/abs/" in url:
        return url.rsplit("/abs/", 1)[-1]
    return url


def _extract_categories(entry: ET.Element) -> list[str]:
    """Extract category terms from Atom <entry><category>."""
    cats: list[str] = []
    for cat_node in entry.findall(f"{_ATOM_NS}category"):
        term = cat_node.get("term", "")
        if term:
            cats.append(term)
    return cats


class ArxivClient:
    """arXiv API client for citation verification.

    Follows CrossrefClient/OpenAlexClient pattern with arXiv-specific
    adaptations: XML parsing, 3s rate limit, arXiv ID lookup.
    Returns ArxivResult(found=False) on any error — never raises.
    """

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(
        self,
        timeout: int = 30,
        offline: bool = False,
        sleep: Any = time.sleep,
        clock: Any = time.monotonic,
    ) -> None:
        self.timeout = timeout
        self.offline = offline
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float = 0.0
        self._latched_unavailable: bool = False

    def reset_outage_latch(self) -> None:
        """Reset the fail-fast outage latch."""
        self._latched_unavailable = False

    def verify_arxiv_id(self, arxiv_id: str) -> ArxivResult:
        """Verify an arXiv ID against the arXiv API.

        Returns ArxivResult with found=True and metadata on success,
        or found=False on 404, network error, or offline mode.
        """
        if self.offline:
            return ArxivResult(found=False)

        try:
            entries = self._get({"id_list": arxiv_id})
            if not entries:
                return ArxivResult(found=False)

            return self._parse_entry(entries[0], score=1.0)
        except Exception:
            return ArxivResult(found=False)

    def search_by_title(
        self,
        title: str,
        year: int | None = None,
    ) -> list[ArxivResult]:
        """Search arXiv by title, return results ranked by similarity.

        Returns list of ArxivResult with score = title_similarity.
        """
        if self.offline:
            return []

        try:
            entries = self._get(
                {"search_query": f'ti:"{title}"', "max_results": "5"},
            )
            if not entries:
                return []

            results: list[ArxivResult] = []
            for entry in entries:
                result = self._parse_entry(entry)
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

    def _parse_entry(
        self,
        entry: ET.Element,
        score: float = 0.0,
    ) -> ArxivResult:
        """Parse an Atom <entry> element into ArxivResult."""
        return ArxivResult(
            found=True,
            arxiv_id=_extract_arxiv_id(entry),
            title=_extract_title(entry) or None,
            authors=_extract_authors(entry),
            year=_extract_year(entry),
            categories=_extract_categories(entry),
            score=score,
        )

    def _get(self, query: dict[str, str]) -> list[ET.Element]:
        """GET the arXiv API and return Atom <entry> elements.

        Enforces 3s minimum interval between requests per arXiv ToU.
        Returns empty list on no results (miss), None is never returned.
        Raises on network failure (caught by callers).
        """
        if self._latched_unavailable:
            logging.warning("arXiv API latched unavailable (fail-fast)")
            return []

        url = self.BASE_URL
        if query:
            url += "?" + urllib.parse.urlencode(query)

        ua = "paper-writer/0.1"
        req = urllib.request.Request(url, headers={"User-Agent": ua})

        # Rate limiting: 3s between requests
        self._throttle()
        self._last_request_at = self._clock()

        def _do_request() -> list[ET.Element]:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                root = ET.fromstring(body)
                return root.findall(f"{_ATOM_NS}entry")

        try:
            res = retry_with_backoff(
                _do_request,
                on_retry=lambda: setattr(
                    self,
                    "_last_request_at",
                    self._clock(),
                ),
                sleep_fn=self._sleep,
            )
            if res is not None:
                self._last_request_at = self._clock()
                return res
            return []
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            self._latched_unavailable = True
            logging.warning("arXiv API HTTP error: %s %s", e.code, e.reason)
            return []
        except (OSError, TimeoutError, urllib.error.URLError) as e:
            self._latched_unavailable = True
            logging.warning("arXiv API I/O failure: %s", e)
            return []
        except ET.ParseError as e:
            logging.warning("arXiv API XML parse error: %s", e)
            return []
        except Exception as e:
            logging.warning("_get failed: %s: %s", type(e).__name__, e)
            return []

    def _throttle(self) -> None:
        """Enforce minimum interval between API requests."""
        if self._last_request_at == 0.0:
            return
        elapsed = self._clock() - self._last_request_at
        if elapsed < _ARXIV_MIN_INTERVAL:
            self._sleep(_ARXIV_MIN_INTERVAL - elapsed)
