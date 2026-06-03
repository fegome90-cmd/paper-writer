"""Shared retry utility for API clients.

Exponential backoff on HTTP 429: 2s, 4s, 8s, max 3 retries.
Ported from ARS scripts/_text_similarity.py retry constants.
"""
from __future__ import annotations

import time
import urllib.error
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

BACKOFF_SECONDS = 2.0
MAX_RETRIES = 3


def retry_with_backoff(
    fn: Callable[[], T],
    on_retry: Callable[[], None] | None = None,
) -> T:
    """Call fn() with exponential backoff on HTTP 429.

    Retries up to MAX_RETRIES times with increasing delays:
    2s, 4s, 8s. Non-429 errors are re-raised immediately.

    Args:
        fn: Callable that performs the HTTP request.
        on_retry: Optional callback invoked after each backoff sleep.
            Used by clients to refresh `_last_request_at` timestamp.

    Returns:
        Result of fn() on success.

    Raises:
        Re-raises whatever fn() raises if not a 429, or if retries exhausted.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                time.sleep(BACKOFF_SECONDS * (2**attempt))
                if on_retry is not None:
                    on_retry()
                last_error = e
                continue
            raise
    raise last_error  # type: ignore[misc]
