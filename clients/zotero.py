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
import re as _re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["ZoteroClient", "ZoteroConfig", "ZoteroError"]

ZOTERO_API_BASE = "https://api.zotero.org"
ZOTERO_LOCAL_BASE = "http://localhost:23119/api"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
MIN_WRITE_INTERVAL = 0.5  # Seconds between write requests (rate limiting)

# Valid Zotero item/collection key: 8 chars from [23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]

_ZOTERO_KEY_RE = _re.compile(r"^[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}$", _re.IGNORECASE)


def _validate_key(key: str, param_name: str = "item_key") -> None:
    """Raise ValueError if key is not a valid 8-char Zotero key."""
    if not _ZOTERO_KEY_RE.match(key):
        raise ValueError(
            f"Invalid {param_name}: '{key}'. "
            f"Must be 8 characters from [23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]."
        )


def _parse_retry_after(error: urllib.error.HTTPError, default: int = 10) -> int:
    """Parse Retry-After header from HTTP error response."""
    try:
        return int(error.headers.get("Retry-After", default))
    except (ValueError, TypeError):
        return default


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

    def validate(self) -> None:
        """Validate Zotero API credentials with a lightweight probe.

        Performs a single GET to ``/users/{user_id}/items?limit=1``.
        Raises ``ZoteroUnavailableError`` on any failure; returns silently on success.
        """
        if self.local_mode or self.bbt_local:
            # local_mode: probe Zotero's local HTTP server to confirm it's reachable.
            # bbt_local: skip — BBT is a plugin that may not expose a stable endpoint.
            if self.local_mode:
                local_url = f"http://localhost:23119/api/users/{self.user_id}/items?limit=1"
                local_req = urllib.request.Request(
                    local_url, headers={"Zotero-API-Version": "3"}
                )
                try:
                    with urllib.request.urlopen(local_req, timeout=3):
                        pass
                except (urllib.error.URLError, OSError) as exc:
                    raise ZoteroUnavailableError(
                        "Could not reach local Zotero at localhost:23119 — "
                        "ensure Zotero desktop is running with local API enabled."
                    ) from exc
            return
        url = f"{ZOTERO_API_BASE}/users/{self.user_id}/items?limit=1"
        headers: dict[str, str] = {"Zotero-API-Version": "3"}
        if self.api_key:
            headers["Zotero-API-Key"] = self.api_key
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT):
                pass
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ZoteroUnavailableError(
                    "API key is missing or unrecognized. "
                    "Set ZOTERO_API_KEY in your environment."
                ) from e
            if e.code == 403:
                raise ZoteroUnavailableError(
                    "API key is invalid or expired. "
                    "Generate a new key at https://www.zotero.org/settings/keys"
                ) from e
            if e.code == 429:
                raise ZoteroUnavailableError(
                    "Zotero API rate limit reached — try again in a moment"
                ) from e
            if e.code >= 500:
                raise ZoteroUnavailableError(
                    "Zotero server error — try again later"
                ) from e
            raise ZoteroUnavailableError(
                f"Zotero HTTP {e.code}: {e.reason}"
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise ZoteroUnavailableError(
                "Could not reach Zotero API — check network connection"
            ) from e

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
    _last_write_time: float = field(default=0.0, init=False, compare=False, repr=False)
    _opener: urllib.request.OpenerDirector | None = field(
        default=None,
        init=False,
        compare=False,
        repr=False,
    )

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
                raise ValueError(
                    "Incremental sync (--since) not supported with BBT local pull (--bbt-local)"
                )
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

    @staticmethod
    def _make_opener() -> urllib.request.OpenerDirector:
        """Build an opener that strips API key on cross-domain redirects."""

        class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(
                self,
                req: urllib.request.Request,
                fp: object,
                code: int,
                msg: str,
                headers: object,
                newurl: str,
            ) -> urllib.request.Request | None:
                # Check if redirecting to a different domain
                from urllib.parse import urlparse

                old_host = urlparse(req.full_url).hostname
                new_host = urlparse(newurl).hostname
                if old_host != new_host:
                    # Strip sensitive headers on cross-domain redirect
                    safe_req = urllib.request.Request(
                        newurl,
                        method=req.method,
                        data=req.data,
                    )
                    for k, v in req.headers.items():
                        if k.lower() not in ("zotero-api-key", "x-api-key", "authorization"):
                            safe_req.add_header(k, v)
                    return safe_req
                return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]

        return urllib.request.build_opener(_SafeRedirectHandler)

    def _get(
        self, url: str, *, expect_text: bool, attempt: int = 0
    ) -> tuple[str | list[object], dict[str, str]]:
        """HTTP GET with 429 / Retry-After handling.

        Returns (body, response_headers). Body is str when expect_text=True,
        list when expect_text=False (JSON array).

        Raises ZoteroError on unrecoverable errors.
        """
        req = urllib.request.Request(url, headers=self._headers())
        if self._opener is None:
            self._opener = self._make_opener()
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
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

    # ------------------------------------------------------------------
    # Write HTTP methods
    # ------------------------------------------------------------------

    def _require_api_key(self) -> str:
        """Return api_key or raise ZoteroError if write access is unavailable."""
        if not self.config.api_key:
            raise ZoteroError(
                "Zotero API key is required for write operations. "
                "Set ZOTERO_API_KEY with write access."
            )
        return self.config.api_key

    def _throttle_write(self) -> None:
        """Enforce minimum interval between write requests.

        Sleeps if the last write was too recent to avoid hitting
        Zotero's rate limits proactively.
        """
        now = time.monotonic()
        elapsed = now - self._last_write_time
        if elapsed < MIN_WRITE_INTERVAL:
            time.sleep(MIN_WRITE_INTERVAL - elapsed)
        self._last_write_time = time.monotonic()

    def _write_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Headers for write requests. Includes API key."""
        h = self._headers()
        h["Content-Type"] = "application/json"
        if extra:
            h.update(extra)
        return h

    def _lib_prefix(self) -> str:
        """Return the library URL prefix, e.g. '/users/12345'."""
        base = ZOTERO_LOCAL_BASE if self.config.local_mode else ZOTERO_API_BASE
        return f"{base}/{self.config.library_type}s/{self.config.user_id}"

    def _post(
        self,
        url: str,
        data: bytes | str | None = None,
        *,
        headers: dict[str, str] | None = None,
        expect_json: bool = True,
        attempt: int = 0,
    ) -> tuple[object, dict[str, str]]:
        """HTTP POST with 429 / Retry-After handling.

        Returns (parsed_body, response_headers).
        Raises ZoteroError on unrecoverable errors.
        """
        self._require_api_key()
        self._throttle_write()
        hdrs = self._write_headers(headers)
        if isinstance(data, str):
            data = data.encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        if self._opener is None:
            self._opener = self._make_opener()
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                resp_headers: dict[str, str] = dict(resp.headers)
                if not raw:
                    return None, resp_headers
                try:
                    return json.loads(raw.decode("utf-8")), resp_headers
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return raw.decode("utf-8", errors="replace"), resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                retry_after = _parse_retry_after(e)
                time.sleep(retry_after)
                return self._post(
                    url, data, headers=headers, expect_json=expect_json, attempt=attempt + 1
                )
            if e.code in (412, 409, 413, 428):
                raise ZoteroError(f"Zotero write error HTTP {e.code}: {e.reason}") from e
            raise ZoteroUnavailableError(f"Zotero HTTP {e.code}: {e.reason} — {url}") from e
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise ZoteroUnavailableError(f"Zotero unreachable: {e}") from e

    def _put(
        self,
        url: str,
        data: bytes | str | None = None,
        *,
        headers: dict[str, str] | None = None,
        attempt: int = 0,
    ) -> tuple[object, dict[str, str]]:
        """HTTP PUT with 429 / Retry-After handling."""
        self._require_api_key()
        self._throttle_write()
        hdrs = self._write_headers(headers)
        if isinstance(data, str):
            data = data.encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=hdrs, method="PUT")
        if self._opener is None:
            self._opener = self._make_opener()
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                resp_headers: dict[str, str] = dict(resp.headers)
                if not raw:
                    return None, resp_headers
                try:
                    return json.loads(raw.decode("utf-8")), resp_headers
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return raw.decode("utf-8", errors="replace"), resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                retry_after = _parse_retry_after(e)
                time.sleep(retry_after)
                return self._put(url, data, headers=headers, attempt=attempt + 1)
            if e.code in (412, 409, 413, 428):
                raise ZoteroError(f"Zotero write error HTTP {e.code}: {e.reason}") from e
            raise ZoteroUnavailableError(f"Zotero HTTP {e.code}: {e.reason} — {url}") from e
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise ZoteroUnavailableError(f"Zotero unreachable: {e}") from e

    def _patch(
        self,
        url: str,
        data: bytes | str | None = None,
        *,
        headers: dict[str, str] | None = None,
        attempt: int = 0,
    ) -> tuple[object, dict[str, str]]:
        """HTTP PATCH with 429 / Retry-After handling."""
        self._require_api_key()
        self._throttle_write()
        hdrs = self._write_headers(headers)
        if isinstance(data, str):
            data = data.encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=hdrs, method="PATCH")
        if self._opener is None:
            self._opener = self._make_opener()
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                resp_headers: dict[str, str] = dict(resp.headers)
                if not raw:
                    return None, resp_headers
                try:
                    return json.loads(raw.decode("utf-8")), resp_headers
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return raw.decode("utf-8", errors="replace"), resp_headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                retry_after = _parse_retry_after(e)
                time.sleep(retry_after)
                return self._patch(url, data, headers=headers, attempt=attempt + 1)
            if e.code in (412, 409, 413, 428):
                raise ZoteroError(f"Zotero write error HTTP {e.code}: {e.reason}") from e
            raise ZoteroUnavailableError(f"Zotero HTTP {e.code}: {e.reason} — {url}") from e
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise ZoteroUnavailableError(f"Zotero unreachable: {e}") from e

    def _delete(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        attempt: int = 0,
    ) -> dict[str, str]:
        """HTTP DELETE with 429 / Retry-After handling.

        Returns response headers on success.
        """
        self._require_api_key()
        self._throttle_write()
        hdrs = self._write_headers(headers)
        req = urllib.request.Request(url, headers=hdrs, method="DELETE")
        if self._opener is None:
            self._opener = self._make_opener()
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                return dict(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                retry_after = _parse_retry_after(e)
                time.sleep(retry_after)
                return self._delete(url, headers=headers, attempt=attempt + 1)
            if e.code in (412, 409, 428):
                raise ZoteroError(f"Zotero write error HTTP {e.code}: {e.reason}") from e
            raise ZoteroUnavailableError(f"Zotero HTTP {e.code}: {e.reason} — {url}") from e
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
            raise ZoteroUnavailableError(f"Zotero unreachable: {e}") from e

    # ------------------------------------------------------------------
    # Public write API methods
    # ------------------------------------------------------------------

    def get_item_template(
        self, item_type: str, *, link_mode: str | None = None
    ) -> dict[str, object]:
        """Get an empty JSON template for creating a new Zotero item.

        Args:
            item_type: Zotero item type (e.g. 'journalArticle', 'book', 'attachment').
            link_mode: Required for attachment type. One of 'imported_file',
                'imported_url', 'linked_file', 'linked_url'.

        Returns:
            Dict with template fields for the given item type.

        Raises:
            ZoteroError: on network or API errors.
        """
        import urllib.parse

        base = ZOTERO_LOCAL_BASE if self.config.local_mode else ZOTERO_API_BASE
        params = f"itemType={urllib.parse.quote(item_type)}"
        if link_mode:
            params += f"&linkMode={urllib.parse.quote(link_mode)}"
        url = f"{base}/items/new?{params}"
        body, _ = self._get(url, expect_text=False)
        if isinstance(body, dict):
            return body
        raise ZoteroError(f"Unexpected template response type: {type(body).__name__}")

    def create_items(
        self,
        items: list[dict[str, object]],
        *,
        library_version: int | None = None,
        write_token: str | None = None,
    ) -> dict[str, object]:
        """Create one or more items in the Zotero library.

        Args:
            items: List of item data dicts (use get_item_template() to get structure).
            library_version: If provided, sets If-Unmodified-Since-Version header.
            write_token: Optional idempotency token (Zotero-Write-Token).

        Returns:
            Dict with 'successful', 'unchanged', and 'failed' keys.

        Raises:
            ZoteroError: on write errors (412, 409, etc.) or network errors.
        """
        extra: dict[str, str] = {}
        if library_version is not None:
            extra["If-Unmodified-Since-Version"] = str(library_version)
        elif write_token:
            extra["Zotero-Write-Token"] = write_token
        else:
            # Auto-generate idempotency token to prevent duplicate creation on 429 retry
            import secrets

            extra["Zotero-Write-Token"] = secrets.token_hex(16)

        url = f"{self._lib_prefix()}/items"
        body, _ = self._post(url, json.dumps(items).encode("utf-8"), headers=extra or None)
        if isinstance(body, dict):
            return body
        raise ZoteroError(f"Unexpected create_items response: {type(body).__name__}")

    def create_collection(
        self,
        data: dict[str, object],
        *,
        library_version: int | None = None,
        write_token: str | None = None,
    ) -> dict[str, object]:
        """Create a collection in the Zotero library.

        Args:
            data: Collection data dict with at minimum 'name' key.
            library_version: If provided, sets If-Unmodified-Since-Version header.
            write_token: Optional idempotency token.

        Returns:
            Dict with 'successful', 'unchanged', and 'failed' keys.

        Raises:
            ZoteroError: on write errors or network errors.
        """
        extra: dict[str, str] = {}
        if library_version is not None:
            extra["If-Unmodified-Since-Version"] = str(library_version)
        elif write_token:
            extra["Zotero-Write-Token"] = write_token
        else:
            # Auto-generate idempotency token to prevent duplicate creation on 429 retry
            import secrets

            extra["Zotero-Write-Token"] = secrets.token_hex(16)

        url = f"{self._lib_prefix()}/collections"
        body, _ = self._post(url, json.dumps([data]).encode("utf-8"), headers=extra or None)
        if isinstance(body, dict):
            return body
        raise ZoteroError(f"Unexpected create_collection response: {type(body).__name__}")

    def update_item(
        self,
        item_key: str,
        data: dict[str, object],
        *,
        version: int,
    ) -> dict[str, str]:
        """Full update of an existing Zotero item (PUT).

        Args:
            item_key: 8-character Zotero item key.
            data: Complete item data dict (must include 'key' and 'version').
            version: Current item version for optimistic concurrency.

        Returns:
            Response headers dict.

        Raises:
            ZoteroError: on 412 Precondition Failed or other write errors.
            ValueError: if item_key is not a valid Zotero key.
        """
        _validate_key(item_key)
        extra = {"If-Unmodified-Since-Version": str(version)}
        url = f"{self._lib_prefix()}/items/{item_key}"
        _, headers = self._put(url, json.dumps(data).encode("utf-8"), headers=extra)
        return headers

    def partial_update_item(
        self,
        item_key: str,
        data: dict[str, object],
        *,
        version: int,
    ) -> dict[str, str]:
        """Partial update of an existing Zotero item (PATCH).

        Only specified fields are modified; others are left untouched.

        Args:
            item_key: 8-character Zotero item key.
            data: Dict with only the fields to change.
            version: Current item version for optimistic concurrency.

        Returns:
            Response headers dict.

        Raises:
            ZoteroError: on 412 Precondition Failed or other write errors.
            ValueError: if item_key is not a valid Zotero key.
        """
        _validate_key(item_key)
        extra = {"If-Unmodified-Since-Version": str(version)}
        url = f"{self._lib_prefix()}/items/{item_key}"
        _, headers = self._patch(url, json.dumps(data).encode("utf-8"), headers=extra)
        return headers

    def delete_item(
        self,
        item_key: str,
        *,
        version: int,
    ) -> dict[str, str]:
        """Delete an item from the Zotero library.

        Args:
            item_key: 8-character Zotero item key.
            version: Current item version for optimistic concurrency.

        Returns:
            Response headers dict.

        Raises:
            ZoteroError: on 412 Precondition Failed or other write errors.
            ValueError: if item_key is not a valid Zotero key.
        """
        _validate_key(item_key)
        extra = {"If-Unmodified-Since-Version": str(version)}
        url = f"{self._lib_prefix()}/items/{item_key}"
        return self._delete(url, headers=extra)

    def create_attachment(
        self,
        parent_key: str,
        filename: str,
        content_type: str = "application/pdf",
        *,
        title: str = "",
        link_mode: str = "imported_file",
    ) -> str:
        """Create an attachment item and return its key.

        This creates the attachment metadata only. Use upload_file() to
        upload the actual file content.

        Args:
            parent_key: Key of the parent item.
            filename: Filename for the attachment (e.g. 'paper.pdf').
            content_type: MIME type (default 'application/pdf').
            title: Attachment title (defaults to filename).
            link_mode: One of 'imported_file', 'imported_url', 'linked_file', 'linked_url'.

        Returns:
            The created attachment item key.

        Raises:
            ZoteroError: on write errors or network errors.
            ValueError: if parent_key is not a valid Zotero key.
        """
        _validate_key(parent_key, "parent_key")
        template = self.get_item_template("attachment", link_mode=link_mode)
        if isinstance(template, dict):
            template["parentItem"] = parent_key
            template["linkMode"] = link_mode
            template["title"] = title or filename
            template["filename"] = filename
            template["contentType"] = content_type
            # Clear template fields that should not be sent
            template.pop("md5", None)
            template.pop("mtime", None)

            result = self.create_items([template])
            if isinstance(result, dict):
                successful = result.get("successful") or {}
                if successful and isinstance(successful, dict):
                    first = next(iter(successful.values()))
                    if isinstance(first, dict):
                        key = first.get("key", "")
                        if isinstance(key, str) and key:
                            _validate_key(key, "attachment_key")
                            return key
                    if isinstance(first, str) and first:
                        _validate_key(first, "attachment_key")
                        return first
            raise ZoteroError("Failed to create attachment: no successful key returned")
        raise ZoteroError("Failed to get attachment template")

    def upload_file(
        self,
        item_key: str,
        file_path: str,
        *,
        existing_md5: str | None = None,
        force_update: bool = False,
    ) -> dict[str, object]:
        """Upload a file to a Zotero attachment item (3-step process).

        1. Get upload authorization from Zotero.
        2. Upload the file content to the authorized URL.
        3. Register the upload with Zotero.

        Args:
            item_key: Key of the attachment item to upload to.
            file_path: Local path to the file to upload.
            existing_md5: Previous file MD5 hash. Required for updating existing files.
                Per Zotero API spec, existing files must use If-Match: <md5>.
            force_update: If True and file already exists on server, re-upload anyway.

        Returns:
            Dict with upload status information.

        Raises:
            ZoteroError: on upload errors, quota exceeded, or network errors.
            ValueError: if item_key is not a valid Zotero key.
        """
        import hashlib
        import urllib.parse

        _validate_key(item_key)

        path = Path(file_path)
        if not path.is_file():
            raise ZoteroError(f"File not found: {file_path}")

        file_data = path.read_bytes()
        file_md5 = hashlib.md5(file_data).hexdigest()
        file_mtime = str(int(path.stat().st_mtime * 1000))
        file_size = len(file_data)
        filename = path.name

        self._require_api_key()

        # Step 1: Get upload authorization
        auth_url = f"{self._lib_prefix()}/items/{item_key}/file"
        auth_body = urllib.parse.urlencode(
            {
                "md5": file_md5,
                "filename": filename,
                "filesize": file_size,
                "mtime": file_mtime,
            }
        ).encode("utf-8")

        # Use If-Match for updates (existing_md5), If-None-Match for new uploads
        precondition_header: str
        if existing_md5:
            precondition_header = existing_md5
        else:
            precondition_header = "*"

        auth_headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
            "If-None-Match" if not existing_md5 else "If-Match": precondition_header,
        }

        body, _ = self._post(auth_url, auth_body, headers=auth_headers)

        # Check if file already exists (only for new uploads, not updates)
        if not existing_md5 and isinstance(body, dict) and body.get("exists"):
            if not force_update:
                return {"status": "exists", "message": "File already exists on server"}

        if not isinstance(body, dict):
            raise ZoteroError(f"Unexpected upload authorization response: {type(body).__name__}")

        upload_url = body.get("url") or ""
        content_type = body.get("contentType") or ""
        prefix = body.get("prefix") or ""
        suffix = body.get("suffix") or ""
        upload_key = body.get("uploadKey") or ""

        if not upload_url or not upload_key:
            raise ZoteroError("Upload authorization missing url or uploadKey")

        # Step 2: Upload file to authorized URL
        # Concatenate prefix + file bytes + suffix
        upload_data = prefix.encode("utf-8") + file_data + suffix.encode("utf-8")
        upload_headers: dict[str, str] = {
            "Content-Type": content_type,
        }

        upload_req = urllib.request.Request(
            upload_url,
            data=upload_data,
            headers=upload_headers,
            method="POST",
        )
        try:
            if self._opener is None:
                self._opener = self._make_opener()
            with self._opener.open(upload_req, timeout=max(self.timeout, 120)) as resp:
                resp.read()  # Consume response
        except urllib.error.HTTPError as e:
            raise ZoteroError(f"File upload failed HTTP {e.code}: {e.reason}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ZoteroUnavailableError(f"File upload unreachable: {e}") from e

        # Step 3: Register upload
        register_body = urllib.parse.urlencode({"upload": upload_key}).encode("utf-8")
        register_headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        # Use same precondition as auth step (If-Match for updates, If-None-Match for new)
        if existing_md5:
            register_headers["If-Match"] = existing_md5
        else:
            register_headers["If-None-Match"] = "*"
        self._post(auth_url, register_body, headers=register_headers)

        return {
            "status": "uploaded",
            "item_key": item_key,
            "filename": filename,
            "md5": file_md5,
            "size": file_size,
        }

    # ------------------------------------------------------------------
    # Additional read/write methods
    # ------------------------------------------------------------------

    def get_item(self, item_key: str) -> dict[str, object]:
        """Fetch a single item by its key.

        Args:
            item_key: 8-character Zotero item key.

        Returns:
            Item data dict with all fields including key, version, itemType,
            creators, tags, collections, relations, etc.

        Raises:
            ZoteroError: on network or API errors.
            ValueError: if item_key is not a valid Zotero key.
        """
        _validate_key(item_key)
        url = f"{self._lib_prefix()}/items/{item_key}"
        body, _ = self._get(url, expect_text=False)
        if isinstance(body, dict):
            return body
        raise ZoteroError(f"Unexpected get_item response: {type(body).__name__}")

    def delete_items(
        self,
        item_keys: list[str],
        *,
        library_version: int,
    ) -> dict[str, str]:
        """Delete multiple items in a single request (up to 50).

        Args:
            item_keys: List of 8-character Zotero item keys (max 50).
            library_version: Current library version for optimistic concurrency.

        Returns:
            Response headers dict.

        Raises:
            ZoteroError: on write errors or network errors.
            ValueError: if any item_key is invalid or more than 50 keys provided.
        """
        if len(item_keys) > 50:
            raise ValueError(f"Cannot delete more than 50 items at once. Got {len(item_keys)}.")
        if not item_keys:
            raise ValueError("Must provide at least one item key.")
        for key in item_keys:
            _validate_key(key)

        import urllib.parse

        keys_param = ",".join(item_keys)
        url = f"{self._lib_prefix()}/items?itemKey={urllib.parse.quote(keys_param, safe=',')}"
        extra = {"If-Unmodified-Since-Version": str(library_version)}
        return self._delete(url, headers=extra)

    def search_items(
        self,
        query: str,
        *,
        item_type: str | None = None,
        tag: str | None = None,
        collection_key: str | None = None,
        limit: int = 25,
        start: int = 0,
    ) -> list[dict[str, object]]:
        """Search items in the library using full-text search.

        Uses the Zotero API ``q`` parameter for full-text search across
        titles, creators, and other fields.

        Args:
            query: Search string.
            item_type: Filter by item type (e.g. 'journalArticle', 'book').
            tag: Filter by tag name.
            collection_key: Limit to items in this collection.
            limit: Maximum items to return (default 25, max 100).
            start: Offset for pagination.

        Returns:
            List of item data dicts.

        Raises:
            ZoteroError: on network or API errors.
            ValueError: if collection_key is provided but invalid.
        """
        import urllib.parse

        if collection_key:
            _validate_key(collection_key, "collection_key")

        params: list[str] = [
            f"q={urllib.parse.quote(query)}",
            f"limit={min(limit, 100)}",
            f"start={start}",
        ]
        if item_type:
            params.append(f"itemType={urllib.parse.quote(item_type)}")
        if tag:
            params.append(f"tag={urllib.parse.quote(tag)}")

        base_prefix = self._lib_prefix()
        endpoint = (
            f"{base_prefix}/collections/{collection_key}/items"
            if collection_key
            else f"{base_prefix}/items"
        )
        url: str | None = f"{endpoint}?{'&'.join(params)}"

        results: list[dict[str, object]] = []
        while url:
            body, headers = self._get(url, expect_text=False)
            if isinstance(body, list):
                for item in body:
                    if isinstance(item, dict):
                        data = item.get("data")
                        if isinstance(data, dict):
                            results.append(data)

            # Track library version for incremental sync (same as fetch_bibtex)
            raw_version = headers.get("Last-Modified-Version") or headers.get(
                "last-modified-version"
            )
            if raw_version:
                try:
                    self.last_version = int(raw_version)
                except ValueError:
                    pass

            next_url: str | None = self._parse_next_link(
                headers.get("Link") or headers.get("link") or ""
            )
            url = next_url

        return results

    @staticmethod
    def _parse_next_link(link_header: str) -> str | None:
        """Parse rel=next URL from HTTP Link header.

        Example header:
            <https://api.zotero.org/users/1/items?start=100>; rel="next"
        """
        for part in link_header.split(","):
            stripped = part.strip()
            if 'rel="next"' in stripped or "rel=next" in stripped:
                url_part = stripped.split(";")[0].strip()
                return url_part.strip("<>")
        return None
