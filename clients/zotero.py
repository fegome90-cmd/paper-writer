"""Zotero Web API v3 client.

Connects to a Zotero account to fetch bibliography data. Supports three modes:

- Cloud API (default): requires ZOTERO_USER_ID + ZOTERO_API_KEY
- Local API (Zotero 7): requires ZOTERO_USER_ID, set ZOTERO_LOCAL=true
- BBT Local Pull: requires Better BibTeX plugin, set ZOTERO_BBT_LOCAL=true

Follows the same patterns as clients/crossref.py and clients/semantic_scholar.py:
- stdlib only (urllib, no requests)
- 429 + Retry-After handling with anchor refresh (ARS pattern)
- Pagination via Link: rel=next header
- Incremental sync via Last-Modified-Version / If-Modified-Since-Version
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["ZoteroClient", "ZoteroConfig", "ZoteroError"]

ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_LOCAL_BASE = "http://localhost:23119/api"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3


class ZoteroError(Exception):
    """Raised when Zotero API is unreachable or returns unexpected errors."""


class ZoteroUnavailableError(ZoteroError):
    """Raised when Zotero is unreachable (HTTP errors, URL errors, timeouts)."""


@dataclass(frozen=True)
class ZoteroConfig:
    """Immutable configuration for ZoteroClient.

    Build from environment with ``ZoteroConfig.from_env()``.
    """

    user_id: str
    api_key: str | None = None
    library_type: str = "user"  # "user" | "group"
    local_mode: bool = False  # True → localhost:23119/api/
    bbt_local: bool = False  # True → Better BibTeX pull endpoint

    @staticmethod
    def from_env(bbt_local_override: bool = False) -> ZoteroConfig:
        """Build config from environment variables.

        Required:
            ZOTERO_USER_ID — numeric user ID (visible at zotero.org/settings/keys)

        Optional:
            ZOTERO_API_KEY       — API key (required for cloud mode)
            ZOTERO_LIBRARY_TYPE  — "user" (default) or "group"
            ZOTERO_LOCAL         — "true" → use localhost:23119
            ZOTERO_BBT_LOCAL     — "true" → use Better BibTeX pull endpoint

        Raises:
            KeyError if ZOTERO_USER_ID is not set.
        """
        bbt_local = bbt_local_override or (os.environ.get("ZOTERO_BBT_LOCAL", "").lower() == "true")
        user_id = os.environ.get("ZOTERO_USER_ID", "").strip()
        if not bbt_local and not user_id:
            raise KeyError(
                "ZOTERO_USER_ID is not set. "
                "Find your user ID at https://www.zotero.org/settings/keys"
            )
        return ZoteroConfig(
            user_id=user_id or "1",
            api_key=os.environ.get("ZOTERO_API_KEY") or None,
            library_type=os.environ.get("ZOTERO_LIBRARY_TYPE", "user").strip(),
            local_mode=os.environ.get("ZOTERO_LOCAL", "").lower() == "true",
            bbt_local=bbt_local,
        )


@dataclass
class ZoteroClient:
    """Zotero API client.

    Usage::

        client = ZoteroClient()                              # reads env
        client = ZoteroClient(ZoteroConfig.from_env())      # explicit
        bibtex = client.fetch_bibtex()                       # full library
        bibtex = client.fetch_bibtex(collection_key="ABC1") # single collection

    Incremental sync::

        first = client.fetch_bibtex()
        version = client.last_version          # save this
        # later:
        delta = client.fetch_bibtex(since_version=version)  # only changes
    """

    config: ZoteroConfig = field(default_factory=ZoteroConfig.from_env)
    timeout: int = DEFAULT_TIMEOUT
    last_version: int | None = field(default=None, init=False, compare=False)

    def fetch_bibtex(
        self,
        collection_key: str | None = None,
        since_version: int | None = None,
    ) -> str:
        """Fetch library or collection as BibTeX string.

        Handles pagination automatically (Link: rel=next).
        Updates ``self.last_version`` with the library version after fetching.

        Args:
            collection_key: Zotero collection key (8-char string). None → full library.
            since_version: Only return items changed since this version (incremental sync).

        Returns:
            BibTeX string (may be empty if nothing changed since ``since_version``).

        Raises:
            ZoteroError: on network errors, auth failures, or unexpected HTTP errors.
        """
        if self.config.bbt_local:
            if since_version is not None:
                raise ValueError("Incremental sync (--since) is not supported with Better BibTeX local pull (--bbt-local)")
            return self._fetch_bbt_local(collection_key)

        chunks: list[str] = []
        url: str | None = self._build_items_url(collection_key, since_version)

        while url:
            body, headers = self._get(url, expect_text=True)
            chunks.append(body if isinstance(body, str) else "")

            raw_version = headers.get("Last-Modified-Version") or headers.get(
                "last-modified-version"
            )
            if raw_version:
                try:
                    self.last_version = int(raw_version)
                except ValueError:
                    pass

            url = self._parse_next_link(headers.get("Link") or headers.get("link") or "")

        return "\n".join(filter(None, chunks))

    def fetch_collections(self) -> list[dict[str, object]]:
        """Fetch all collections in the library.

        Returns:
            List of collection dicts with keys: key, name, parentCollection.

        Raises:
            ZoteroError: on network or API errors.
        """
        lib = f"{self.config.library_type}s/{self.config.user_id}"
        base = ZOTERO_LOCAL_BASE if self.config.local_mode else ZOTERO_API_BASE
        url: str | None = f"{base}/{lib}/collections?limit=100"
        collections: list[dict[str, object]] = []

        while url:
            body, headers = self._get(url, expect_text=False)
            if isinstance(body, list):
                for item in body:
                    if isinstance(item, dict):
                        data = item.get("data", {})
                        if isinstance(data, dict):
                            collections.append(
                                {
                                    "key": data.get("key", ""),
                                    "name": data.get("name", ""),
                                    "parentCollection": data.get("parentCollection", False),
                                }
                            )
            url = self._parse_next_link(headers.get("Link") or headers.get("link") or "")

        return collections

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_bbt_local(self, collection_key: str | None) -> str:
        """Pull BibTeX from Better BibTeX local server (localhost:23119)."""
        uid = self.config.user_id
        if self.config.library_type == "user":
            uid = "1"
        if collection_key:
            import urllib.parse
            encoded_key = urllib.parse.quote(collection_key)
            path = f"/better-bibtex/export/collection?/{uid}/{encoded_key}.bibtex"
        else:
            path = f"/better-bibtex/export/library?/{uid}/library.bibtex"
        body, _ = self._get(f"http://localhost:23119{path}", expect_text=True)
        return body if isinstance(body, str) else ""

    def _build_items_url(self, collection_key: str | None, since_version: int | None) -> str:
        base = ZOTERO_LOCAL_BASE if self.config.local_mode else ZOTERO_API_BASE
        lib = f"{self.config.library_type}s/{self.config.user_id}"
        if collection_key:
            import urllib.parse
            encoded_key = urllib.parse.quote(collection_key)
            url = f"{base}/{lib}/collections/{encoded_key}/items?format=bibtex&limit=100"
        else:
            url = f"{base}/{lib}/items/top?format=bibtex&limit=100"
        if since_version is not None:
            url += f"&since={since_version}"
        return url

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Zotero-API-Version": "3"}
        if self.config.api_key:
            h["Zotero-API-Key"] = self.config.api_key
        return h

    def _get(
        self, url: str, *, expect_text: bool, attempt: int = 0
    ) -> tuple[str | list[object], dict[str, str]]:
        """HTTP GET with 429 / Retry-After handling.

        Returns (body, response_headers). Body is str when expect_text=True,
        list when expect_text=False (JSON array).

        Raises ZoteroError on unrecoverable errors.
        """
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                resp_headers: dict[str, str] = dict(resp.headers)
                if expect_text:
                    try:
                        return raw.decode("utf-8"), resp_headers
                    except UnicodeDecodeError as e:
                        raise ZoteroError(f"Zotero response decode failed: {e}") from e
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                    return parsed, resp_headers
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise ZoteroUnavailableError(f"Zotero JSON parse failed: {e}") from e

        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                try:
                    retry_after = int(e.headers.get("Retry-After", 10))
                except ValueError:
                    retry_after = 10
                time.sleep(retry_after)
                # ARS pattern: refresh anchor after backoff sleep
                return self._get(url, expect_text=expect_text, attempt=attempt + 1)
            if e.code == 304:
                # Not Modified — return empty body, preserve headers
                return ("" if expect_text else []), dict(e.headers)
            raise ZoteroUnavailableError(f"Zotero HTTP {e.code}: {e.reason} — {url}") from e
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise ZoteroUnavailableError(f"Zotero unreachable or invalid URL: {e}") from e

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        """Parse rel=next URL from HTTP Link header.

        Example header:
            <https://api.zotero.org/users/1/items?start=100>; rel="next"
        """
        for part in link_header.split(","):
            stripped = part.strip()
            if 'rel="next"' in stripped:
                url_part = stripped.split(";")[0].strip()
                return url_part.strip("<>")
        return None
