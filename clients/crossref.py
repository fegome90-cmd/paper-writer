"""Crossref API client for DOI verification.

Verifies DOIs against the Crossref REST API to catch fabricated citations.
Uses stdlib only (urllib, json). Returns CrossrefResult(found=False) on
any network error — never raises. Transient failures (e.g. rate-limiting
exhausted) are surfaced via CrossrefResult.transient_error=True so callers
can distinguish them from genuine "not found".
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

from clients._retry import MAX_RETRIES, retry_with_backoff
from clients._text_similarity import TITLE_SIMILARITY_THRESHOLD, title_similarity

# Outage latch auto-reset cooldown (seconds). After a transport failure,
# the latch stays active for this duration; the next request after it
# expires re-attempts the API instead of fail-fast.
LATCH_COOLDOWN_SECONDS = 300.0


class _TransientError(Exception):
    """Internal signal: the request failed due to a transient condition
    (e.g. rate-limiting exhausted). Caught by ``verify_doi`` /
    ``search_by_title`` and surfaced as ``CrossrefResult(transient_error=True)``.
    Never escapes the public API.
    """


@dataclass
class CrossrefResult:
    """Result of a Crossref lookup.

    ``transient_error`` is True when the lookup failed due to a transient
    condition (e.g. rate-limiting exhausted) — distinct from a genuine
    "not found". Upstream classifiers should treat transient results as
    "unknown / retry later", NOT as evidence the citation is fabricated.
    """

    found: bool
    doi: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    is_oa: bool | None = None
    score: float = 0.0
    transient_error: bool = False


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
    for author in item.get("author") or []:
        given = author.get("given", "")
        family = author.get("family", "")
        if given or family:
            authors.append(f"{given} {family}".strip())
    return authors


class CrossrefClient:
    """Crossref API client for DOI verification.

    Uses the polite pool (mailto in User-Agent) when email is provided
    (falls back to CROSSREF_POLITE_EMAIL env var).
    Returns CrossrefResult(found=False) on any error — never raises.
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(
        self,
        email: str | None = None,
        timeout: int = 10,
        offline: bool = False,
        sleep: Any = time.sleep,
        clock: Any = time.time,
    ) -> None:
        self.email = email or os.environ.get("CROSSREF_POLITE_EMAIL")
        self.timeout = timeout
        self.offline = offline
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float = 0.0
        self._latched_unavailable: bool = False
        # Timestamp when the latch was ACTIVATED. The cooldown is measured
        # from this, NOT from _last_request_at (which tracks the last
        # successful request and can be stale/zero, defeating the latch).
        self._latch_set_at: float = 0.0

    def reset_outage_latch(self) -> None:
        """Reset the fail-fast outage latch.

        Also clears ``_latch_set_at`` (W1, Judgment Day) so a subsequent
        transport failure records a fresh activation timestamp instead
        of inheriting a stale one from a prior outage.
        """
        self._latched_unavailable = False
        self._latch_set_at = 0.0

    def verify_doi(self, doi: str) -> CrossrefResult:
        """Verify a DOI against Crossref.

        Returns CrossrefResult with found=True and metadata on success,
        or found=False on 404, network error, or offline mode.
        transient_error=True signals a transient failure (rate-limiting),
        distinct from a genuine 404.
        """
        if self.offline:
            return CrossrefResult(found=False)

        try:
            data = self._get(f"/works/{doi}", {})
            if not data or not data.get("message"):
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
                is_oa = any("creativecommons" in lic.get("URL", "") for lic in licenses)

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
        except _TransientError as e:
            logging.warning("Crossref transient failure: %s", e)
            return CrossrefResult(found=False, doi=doi, transient_error=True)
        except Exception:
            return CrossrefResult(found=False)

    def search_by_title(self, title: str, year: int | None = None) -> list[CrossrefResult]:
        """Search Crossref by title, return results ranked by similarity.

        Returns list of CrossrefResult with score = title_similarity.
        On transient failure (rate-limiting) returns a single-element list
        with a CrossrefResult(transient_error=True) so callers can detect it.
        """
        if self.offline:
            return []

        try:
            data = self._get("/works", {"query.title": title, "rows": "5"})
            if not data:
                return []

            candidates = (data.get("message") or {}).get("items") or []
            results: list[CrossrefResult] = []

            for cand in candidates:
                cand_title = _extract_title(cand)
                sim = title_similarity(cand_title, title)
                if sim < TITLE_SIMILARITY_THRESHOLD:
                    continue

                authors = _extract_authors(cand)
                item_year = _extract_year(cand)
                venue_list = cand.get("container-title") or []
                venue = venue_list[0] if venue_list else None

                # Tiebreaker logic (Item 7): +0.05 bonus for year match
                year_match = year is not None and item_year == year
                score = sim + (0.05 if year_match else 0.0)

                results.append(
                    CrossrefResult(
                        found=True,
                        doi=cand.get("DOI"),
                        title=cand_title,
                        authors=authors,
                        year=item_year,
                        venue=venue,
                        score=score,
                    )
                )

            results.sort(key=lambda r: -r.score)
            return results
        except _TransientError as e:
            logging.warning("Crossref transient failure (search): %s", e)
            # B8 (Judgment Day): return a single-element list with the
            # transient flag so _query_crossref's `results[0] if results`
            # propagates it. This is intentionally shaped differently from
            # the generic `except Exception: return []` below: a generic
            # error is a dead-end (empty), while a transient error is a
            # "retry later" signal the caller must distinguish.
            return [CrossrefResult(found=False, transient_error=True)]
        except Exception:
            return []

    def _get(self, path: str, query: dict[str, str]) -> dict[str, Any] | None:
        """Single GET request with retry on 429.

        Returns parsed JSON dict on success, {} on 404, None on other
        errors (transport, malformed JSON, latched outage).

        Raises ``_TransientError`` (internal) when rate-limit retries are
        exhausted. The public API translates it into a CrossrefResult with
        ``transient_error=True`` so callers distinguish "rate limited" from
        "genuinely not found" — critical to avoid false fabrication flags.

        The outage latch auto-resets after ``LATCH_COOLDOWN_SECONDS`` so a
        single transient transport failure does not skip an entire batch.
        The cooldown is measured from when the latch was ACTIVATED
        (``_latch_set_at``), not from the last successful request.
        """
        now = self._clock()
        # Record request start so _last_request_at always reflects the
        # most recent attempt, regardless of outcome (success/retry/error).
        self._last_request_at = now

        if self._latched_unavailable:
            # Auto-reset after cooldown measured from latch ACTIVATION.
            # W2 (Judgment Day): clamp to >=0 so a backwards clock jump
            # (NTP slew, VM migration) cannot leave the latch stuck forever.
            elapsed = max(0.0, now - self._latch_set_at)
            if elapsed < LATCH_COOLDOWN_SECONDS:
                logging.warning("Crossref API latched unavailable (fail-fast)")
                # W4 (Judgment Day): signal transient, NOT plain not-found.
                # Returning None here would make verify_doi produce a bare
                # found=False, classifying every latched citation as
                # not_found/P0 (false fabrication). Raising _TransientError
                # lets the callers surface transient_error=True.
                raise _TransientError(
                    f"Crossref API latched unavailable (fail-fast, {elapsed:.0f}s into cooldown)"
                )
            self._latched_unavailable = False
            logging.info("Crossref API latch auto-reset after %.0fs cooldown", elapsed)

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
            if e.code == 429:
                # Retries exhausted: rate-limited, NOT a genuine 404.
                # Surface as transient so callers don't classify the
                # citation as not_found/fabricated.
                raise _TransientError(f"Crossref rate-limited after {MAX_RETRIES} retries") from e
            return None
        except (OSError, TimeoutError, urllib.error.URLError) as e:
            # Latch ONLY on transport errors, NOT on HTTP 404.
            # Record activation time so the cooldown is measured from
            # THIS moment, not from a stale _last_request_at.
            self._latched_unavailable = True
            self._latch_set_at = self._clock()
            logging.warning("Crossref API I/O failure: %s", e)
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.warning("Request failed: %s: %s", type(e).__name__, e)
            return None
        except Exception as e:
            logging.warning("_get failed: %s: %s", type(e).__name__, e)
            return None
