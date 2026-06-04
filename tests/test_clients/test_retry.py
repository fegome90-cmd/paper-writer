"""Tests for clients._retry — exponential backoff retry utility."""
from __future__ import annotations

import urllib.error
from unittest.mock import MagicMock

import pytest

from clients._retry import MAX_RETRIES, retry_with_backoff


class TestRetryWithBackoff:
    def test_success_on_first_try(self):
        fn = MagicMock(return_value="ok")
        result = retry_with_backoff(fn)
        assert result == "ok"
        assert fn.call_count == 1

    def test_retries_on_429_then_succeeds(self):
        fn = MagicMock(side_effect=[
            urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None),
            "ok",
        ])
        mock_sleep = MagicMock()
        result = retry_with_backoff(fn, sleep_fn=mock_sleep)
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once()

    def test_exhausts_retries_then_raises(self):
        error = urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None)
        fn = MagicMock(side_effect=error)
        mock_sleep = MagicMock()
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            retry_with_backoff(fn, sleep_fn=mock_sleep)
        assert exc_info.value.code == 429
        assert fn.call_count == MAX_RETRIES + 1

    def test_non_429_error_raises_immediately(self):
        error = urllib.error.HTTPError(None, 500, "Server Error", {}, None)
        fn = MagicMock(side_effect=error)
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            retry_with_backoff(fn)
        assert exc_info.value.code == 500
        assert fn.call_count == 1

    def test_non_http_error_raises_immediately(self):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError, match="bad input"):
            retry_with_backoff(fn)
        assert fn.call_count == 1

    def test_backoff_delays_are_exponential(self):
        fn = MagicMock(side_effect=[
            urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None),
            urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None),
            "ok",
        ])
        mock_sleep = MagicMock()
        result = retry_with_backoff(fn, sleep_fn=mock_sleep)
        assert result == "ok"
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        # BACKOFF_SECONDS=2.0, attempt 0: 2*1=2, attempt 1: 2*2=4
        assert calls == [2.0, 4.0]

    def test_on_retry_callback_invoked_after_each_backoff(self):
        fn = MagicMock(side_effect=[
            urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None),
            urllib.error.HTTPError(None, 429, "Too Many Requests", {}, None),
            "ok",
        ])
        on_retry = MagicMock()
        mock_sleep = MagicMock()
        result = retry_with_backoff(fn, on_retry=on_retry, sleep_fn=mock_sleep)
        assert result == "ok"
        assert on_retry.call_count == 2

    def test_on_retry_not_called_without_backoff(self):
        fn = MagicMock(return_value="ok")
        on_retry = MagicMock()
        result = retry_with_backoff(fn, on_retry=on_retry)
        assert result == "ok"
        on_retry.assert_not_called()
